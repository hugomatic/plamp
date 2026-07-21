"""Expand typed CAD metadata into deterministic render plans."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import hashlib
import json
import math
import re
from types import MappingProxyType

from plamp.cad_metadata import CadDocument, PresetMetadata


GENERATOR_SCHEMA_VERSION = 1
_ARTIFACT_COMPONENT = re.compile(r"[^A-Za-z0-9._-]+")


def _freeze(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _freeze_mapping(value: Mapping[str, object]) -> Mapping[str, object]:
    return _freeze(value)  # type: ignore[return-value]


def _plain(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


@dataclass(frozen=True)
class Selection:
    preset: str | None = None
    views: tuple[str, ...] = ()
    defines: Mapping[str, object] = field(default_factory=dict)
    view_defines: Mapping[str, Mapping[str, object]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "views", tuple(self.views))
        object.__setattr__(self, "defines", _freeze_mapping(self.defines))
        object.__setattr__(
            self,
            "view_defines",
            MappingProxyType(
                {
                    view: _freeze_mapping(defines)
                    for view, defines in self.view_defines.items()
                }
            ),
        )


@dataclass(frozen=True)
class PresetView:
    name: str | None
    description: str


@dataclass(frozen=True)
class PresetNode:
    name: str
    description: str
    path: tuple[str, ...]
    views: tuple[PresetView, ...] = ()
    children: tuple[PresetNode, ...] = ()


@dataclass(frozen=True)
class RenderJob:
    artifact_id: str
    view: str | None
    variant_name: str
    variables: Mapping[str, object]
    preset_paths: tuple[tuple[str, ...], ...]
    fingerprint: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "variables", _freeze_mapping(self.variables))
        object.__setattr__(
            self,
            "preset_paths",
            tuple(tuple(path) for path in self.preset_paths),
        )


@dataclass(frozen=True)
class RenderPlan:
    selection: Selection
    jobs: tuple[RenderJob, ...]
    preset_tree: tuple[PresetNode, ...]

    @property
    def jobs_by_view(self) -> Mapping[str | None, RenderJob]:
        """Return the last planned variant for each view."""

        return MappingProxyType({job.view: job for job in self.jobs})


@dataclass(frozen=True)
class _Candidate:
    view: str | None
    variables: Mapping[str, object]
    preset_path: tuple[str, ...] | None


def serialize_scad_value(value: object) -> str:
    """Serialize a JSON-like Python value as a deterministic OpenSCAD expression."""

    if value is None:
        return "undef"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("OpenSCAD values must use finite numbers")
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("OpenSCAD object keys must be strings")
        entries = (
            f"[{serialize_scad_value(key)}, {serialize_scad_value(value[key])}]"
            for key in sorted(value)
        )
        return f"[{', '.join(entries)}]"
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return f"[{', '.join(serialize_scad_value(item) for item in value)}]"
    raise TypeError(f"Unsupported OpenSCAD value: {type(value).__name__}")


def _effective_variables(
    document: CadDocument,
    selection: Selection,
    view: str | None,
    preset_scopes: tuple[PresetMetadata, ...],
) -> Mapping[str, object]:
    variables: dict[str, object] = dict(document.global_variables)
    if view is not None and view in document.view_metadata:
        variables.update(document.view_metadata[view].variables)
    for preset in preset_scopes:
        variables.update(preset.variables)
    if view is not None:
        for preset in preset_scopes:
            variables.update(preset.view_variables.get(view, {}))
    variables.update(selection.defines)
    if view is not None:
        variables.update(selection.view_defines.get(view, {}))
    return variables


def _fingerprint(
    source_identity: str, view: str | None, variables: Mapping[str, object]
) -> str:
    payload = {
        "generator_schema_version": GENERATOR_SCHEMA_VERSION,
        "source_identity": source_identity,
        "variables": _plain(variables),
        "view": view,
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _variant_base(view: str | None) -> str:
    base = "default" if view is None else view
    cleaned = _ARTIFACT_COMPONENT.sub("-", base).strip("-.")
    return cleaned or "view"


def _resolve_selection(document: CadDocument, selection: Selection) -> Selection:
    if selection.preset is not None and selection.views:
        raise ValueError("A preset selection cannot be combined with direct views")
    unknown_view_defines = tuple(
        view for view in selection.view_defines if view not in document.views
    )
    if unknown_view_defines:
        raise ValueError(f"Unknown view in view defines: {unknown_view_defines[0]!r}")
    if selection.preset is None and not selection.views and document.default_preset:
        return Selection(
            preset=document.default_preset,
            defines=selection.defines,
            view_defines=selection.view_defines,
        )
    return selection


def build_render_plan(
    document: CadDocument,
    selection: Selection,
    source_identity: str,
) -> RenderPlan:
    """Expand a validated CAD document and runtime selection into render jobs."""

    selection = _resolve_selection(document, selection)
    candidates: list[_Candidate] = []

    def candidate(
        view: str | None,
        path: tuple[str, ...] | None = None,
        scopes: tuple[PresetMetadata, ...] = (),
    ) -> None:
        candidates.append(
            _Candidate(
                view,
                _effective_variables(document, selection, view, scopes),
                path,
            )
        )

    def expand_preset(
        name: str,
        parent_path: tuple[str, ...],
        parent_scopes: tuple[PresetMetadata, ...],
        stack: tuple[str, ...],
    ) -> PresetNode:
        if name in stack:
            start = stack.index(name)
            cycle = stack[start:] + (name,)
            raise ValueError(f"Preset cycle: {' -> '.join(cycle)}")
        if name not in document.presets:
            raise ValueError(f"Unknown preset {name!r}")

        preset = document.presets[name]
        path = parent_path + (name,)
        scopes = parent_scopes + (preset,)
        views: list[PresetView] = []
        children: list[PresetNode] = []
        if not preset.items:
            candidate(None, path, scopes)
            views.append(PresetView(None, ""))
        else:
            for item in preset.items:
                namespace, item_name = item.split(":", 1)
                if namespace == "view":
                    if item_name not in document.views:
                        raise ValueError(f"Unknown view {item_name!r}")
                    candidate(item_name, path, scopes)
                    metadata = document.view_metadata.get(item_name)
                    views.append(
                        PresetView(
                            item_name,
                            "" if metadata is None else metadata.description,
                        )
                    )
                elif namespace == "preset":
                    children.append(
                        expand_preset(item_name, path, scopes, stack + (name,))
                    )
                else:
                    raise ValueError(f"Invalid preset item {item!r}")
        return PresetNode(
            name=name,
            description=preset.description,
            path=path,
            views=tuple(views),
            children=tuple(children),
        )

    tree: list[PresetNode] = []
    if selection.preset == "all-views":
        for view in document.views:
            candidate(view)
    elif selection.preset == "all-presets":
        for preset_name in document.presets:
            tree.append(expand_preset(preset_name, (), (), ()))
    elif selection.preset is not None:
        tree.append(expand_preset(selection.preset, (), (), ()))
    elif selection.views:
        direct_views = [view for view in selection.views if view != "assembly"]
        direct_views.extend(view for view in selection.views if view == "assembly")
        for view in direct_views:
            if view not in document.views:
                raise ValueError(f"Unknown view {view!r}")
            candidate(view)
    else:
        candidate(None)

    unique: dict[str, dict[str, object]] = {}
    order: list[str] = []
    for item in candidates:
        fingerprint = _fingerprint(source_identity, item.view, item.variables)
        if fingerprint not in unique:
            unique[fingerprint] = {
                "view": item.view,
                "variables": item.variables,
                "paths": [],
            }
            order.append(fingerprint)
        if item.preset_path is not None:
            paths = unique[fingerprint]["paths"]
            assert isinstance(paths, list)
            if item.preset_path not in paths:
                paths.append(item.preset_path)

    base_counts: dict[str, int] = {}
    jobs: list[RenderJob] = []
    for fingerprint in order:
        details = unique[fingerprint]
        view = details["view"]
        assert view is None or isinstance(view, str)
        base = _variant_base(view)
        base_counts[base] = base_counts.get(base, 0) + 1
        suffix = base_counts[base]
        variant_name = base if suffix == 1 else f"{base}-{suffix}"
        variables = details["variables"]
        assert isinstance(variables, Mapping)
        paths = details["paths"]
        assert isinstance(paths, list)
        jobs.append(
            RenderJob(
                artifact_id=f"{variant_name}--{fingerprint[:12]}",
                view=view,
                variant_name=variant_name,
                variables=variables,
                preset_paths=tuple(paths),
                fingerprint=fingerprint,
            )
        )

    return RenderPlan(selection, tuple(jobs), tuple(tree))


def plan_as_dict(plan: RenderPlan) -> dict[str, object]:
    """Return a stable JSON-compatible representation of a render plan."""

    def node_as_dict(node: PresetNode) -> dict[str, object]:
        return {
            "name": node.name,
            "description": node.description,
            "path": list(node.path),
            "views": [
                {"name": view.name, "description": view.description}
                for view in node.views
            ],
            "children": [node_as_dict(child) for child in node.children],
        }

    return {
        "selection": {
            "preset": plan.selection.preset,
            "views": list(plan.selection.views),
            "defines": _plain(plan.selection.defines),
            "view_defines": _plain(plan.selection.view_defines),
        },
        "jobs": [
            {
                "artifact_id": job.artifact_id,
                "view": job.view,
                "variant_name": job.variant_name,
                "variables": _plain(job.variables),
                "preset_paths": [list(path) for path in job.preset_paths],
                "fingerprint": job.fingerprint,
            }
            for job in plan.jobs
        ],
        "preset_tree": [node_as_dict(node) for node in plan.preset_tree],
    }
