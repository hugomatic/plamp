"""Expand validated CAD systems into immutable deterministic render plans."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import re
from types import MappingProxyType

from plamp.cad_system import CadProductItem, CadSystem
from plamp.cad_manufacturing import (
    DirectiveSource,
    ManufacturingPolicy,
    merge_manufacturing,
)
from plamp.cad_profiles import CadProfile, resolve_profile_ids
from plamp.cad_values import ResolvedVariable, parse_raw_defines, resolve_variables


PLANNING_SCHEMA_VERSION = 1
_ARTIFACT_COMPONENT = re.compile(r"[^A-Za-z0-9._-]+")


def _freeze(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _mapping(value: Mapping[str, object]) -> Mapping[str, object]:
    return _freeze(value)  # type: ignore[return-value]


def _plain(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(_plain(value), ensure_ascii=False, allow_nan=False,
                         separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _relative_profile_path(profile: CadProfile, *, repo_root: Path | None,
                           data_dir: Path | None) -> str:
    path = Path(profile.path)
    if not path.is_absolute():
        return path.as_posix()
    root = data_dir if profile.qualified_id.startswith("local:") else repo_root
    if root is not None:
        try:
            return path.relative_to(Path(root).resolve()).as_posix()
        except ValueError:
            pass
    return path.name


def _resolved_profile(profile: CadProfile, *, repo_root: Path | None,
                      data_dir: Path | None) -> ResolvedProfile:
    namespace = profile.qualified_id.split(":", 1)[0]
    return ResolvedProfile(
        name=profile.name,
        qualified_id=profile.qualified_id,
        namespace=namespace,
        source=namespace,
        kind=profile.kind,
        content_hash=profile.content_hash,
        path=_relative_profile_path(profile, repo_root=repo_root, data_dir=data_dir),
    )


def _profile_as_dict(profile: ResolvedProfile) -> dict[str, str]:
    return {
        "name": profile.name,
        "qualified_id": profile.qualified_id,
        "namespace": profile.namespace,
        "source": profile.source,
        "kind": profile.kind,
        "content_hash": profile.content_hash,
        "path": profile.path,
    }


@dataclass(frozen=True)
class CadSelection:
    product: str | None = None
    model: str | None = None
    sets: tuple[str, ...] = ()
    all_sets: bool = False
    defines: Mapping[str, object] = field(default_factory=dict)
    set_defines: Mapping[str, Mapping[str, object]] = field(default_factory=dict)
    raw_defines: tuple[str, ...] = ()
    profiles: tuple[str, ...] = ()
    use_default_profiles: bool = True

    def __post_init__(self) -> None:
        if "set" in self.defines or any(
            "set" in values for values in self.set_defines.values()
        ) or "set" in parse_raw_defines(self.raw_defines):
            raise ValueError(
                "The selector-owned variable 'set' cannot be overridden; "
                "select a set with the CAD set options"
            )
        object.__setattr__(self, "sets", tuple(self.sets))
        object.__setattr__(self, "defines", _mapping(self.defines))
        object.__setattr__(self, "set_defines", MappingProxyType({
            name: _mapping(values) for name, values in self.set_defines.items()
        }))
        object.__setattr__(self, "raw_defines", tuple(self.raw_defines))
        object.__setattr__(self, "profiles", tuple(self.profiles))


@dataclass(frozen=True)
class ResolvedProfile:
    name: str
    qualified_id: str
    namespace: str
    source: str
    kind: str
    content_hash: str
    path: str


@dataclass(frozen=True)
class RenderJob:
    artifact_id: str
    model_id: str
    set_name: str
    variant_name: str
    variables: Mapping[str, object]
    raw_defines: Mapping[str, str]
    variable_sources: Mapping[str, ResolvedVariable]
    profiles: tuple[ResolvedProfile, ...]
    manufacturing: ManufacturingPolicy
    product_paths: tuple[tuple[str, ...], ...]
    geometry_fingerprint: str
    manufacturing_fingerprint: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "variables", _mapping(self.variables))
        object.__setattr__(self, "raw_defines", MappingProxyType(dict(self.raw_defines)))
        object.__setattr__(self, "variable_sources",
                           MappingProxyType(dict(self.variable_sources)))
        object.__setattr__(self, "profiles", tuple(self.profiles))
        object.__setattr__(self, "product_paths",
                           tuple(tuple(path) for path in self.product_paths))

    @property
    def profile_ids(self) -> tuple[str, ...]:
        return tuple(profile.qualified_id for profile in self.profiles)


@dataclass(frozen=True)
class RenderPlan:
    system_name: str
    system_path: Path
    selection: CadSelection
    jobs: tuple[RenderJob, ...]
    system_manifest_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "jobs", tuple(self.jobs))


@dataclass(frozen=True)
class _Candidate:
    model_id: str
    set_name: str
    variant: str | None
    path: tuple[str, ...] | None
    layers: tuple[tuple[str, int, CadProductItem], ...]


def _selection_candidates(system: CadSystem, selection: CadSelection) -> list[_Candidate]:
    direct_options = selection.model is not None or selection.sets or selection.all_sets
    if selection.product is not None and direct_options:
        raise ValueError("A product selection cannot be combined with direct model or sets")
    if (selection.sets or selection.all_sets) and selection.model is None:
        raise ValueError("Direct set selection requires a model")
    if selection.sets and selection.all_sets:
        raise ValueError("Named sets cannot be combined with all sets")

    product_name = selection.product
    if product_name is None and not direct_options:
        product_name = system.default_product
    candidates: list[_Candidate] = []

    def expand(name: str, path: tuple[str, ...],
               layers: tuple[tuple[str, int, CadProductItem], ...],
               stack: tuple[str, ...]) -> None:
        if name in stack:
            start = stack.index(name)
            cycle = stack[start:] + (name,)
            raise ValueError(f"Product cycle: {' -> '.join(cycle)}")
        if name not in system.products:
            raise ValueError(f"Unknown product {name!r}")
        current_path = path + (name,)
        product = system.products[name]
        for index, product_item in enumerate(product.items):
            current_layers = layers + ((name, index, product_item),)
            if product_item.product is not None:
                expand(product_item.product, current_path, current_layers, stack + (name,))
            else:
                assert product_item.model is not None and product_item.set_name is not None
                candidates.append(_Candidate(
                    product_item.model, product_item.set_name, product_item.variant,
                    current_path, current_layers,
                ))

    if product_name is not None:
        expand(product_name, (), (), ())
        return candidates

    if selection.model is not None:
        if selection.model not in system.models:
            raise ValueError(f"Unknown model {selection.model!r}")
        model = system.models[selection.model]
        names = tuple(model.sets) if selection.all_sets else selection.sets
        if not names:
            names = (model.default_set,)
        seen: set[str] = set()
        for name in names:
            if name not in model.sets:
                raise ValueError(f"Unknown set {name!r} for model {selection.model!r}")
            if name not in seen:
                candidates.append(_Candidate(selection.model, name, None, None, ()))
                seen.add(name)
        return candidates

    for model_id, model in system.models.items():
        candidates.append(_Candidate(model_id, model.default_set, None, None, ()))
    return candidates


def build_render_plan(system: CadSystem, selection: CadSelection,
                      source_identities: Mapping[str, str], *,
                      local_profiles: Mapping[str, CadProfile] = MappingProxyType({}),
                      default_profile_ids: tuple[str, ...] = (),
                      repo_root: Path | None = None,
                      data_dir: Path | None = None) -> RenderPlan:
    """Expand products or direct sets depth-first and deduplicate render jobs."""

    candidates = _selection_candidates(system, selection)
    manifest_hash = _canonical_hash(system.metadata_snapshot)
    unique: dict[str, dict[str, object]] = {}
    order: list[str] = []

    for candidate in candidates:
        if candidate.model_id not in system.models:
            raise ValueError(f"Unknown model {candidate.model_id!r}")
        if candidate.model_id not in source_identities:
            raise ValueError(f"Missing source identity for model {candidate.model_id!r}")
        model = system.models[candidate.model_id]
        if candidate.set_name not in model.sets:
            raise ValueError(f"Unknown set {candidate.set_name!r} for model {candidate.model_id!r}")
        variable_layers: list[
            tuple[str, str, Mapping[str, object], Mapping[str, str]]
        ] = []
        requested_profiles: list[str] = []
        manufacturing_layers: list[tuple[DirectiveSource, Mapping[str, object]]] = [
            (DirectiveSource(f"model:{candidate.model_id}"), {}),
            (DirectiveSource(f"set:{candidate.model_id}/{candidate.set_name}"),
             model.sets[candidate.set_name].slicing),
        ]

        def layer(values: Mapping[str, object], kind: str, source_id: str,
                  raw_values: Mapping[str, str] | None = None) -> None:
            variable_layers.append((kind, source_id, values, raw_values or {}))

        source_defaults = {
            name: value for name, value in model.source_defaults.items() if name != "set"
        }
        layer(source_defaults, "scad", str(model.source_path))
        layer(model.variables, "model", candidate.model_id)
        layer(model.sets[candidate.set_name].variables, "set",
              f"{candidate.model_id}/{candidate.set_name}")
        if candidate.layers:
            top_product_name = candidate.layers[0][0]
            requested_profiles.extend(system.products[top_product_name].profiles)
            for layer_index, (product_name, _item_index, product_item) in enumerate(
                candidate.layers
            ):
                if layer_index:
                    requested_profiles.extend(system.products[product_name].profiles)
                requested_profiles.extend(product_item.profiles)
        requested_profiles.extend(model.profiles)
        requested_profiles.extend(model.sets[candidate.set_name].profiles)
        requested_profiles.extend(selection.profiles)
        resolved_profiles = resolve_profile_ids(
            system.profiles, local_profiles,
            defaults=default_profile_ids, requested=requested_profiles,
            use_defaults=selection.use_default_profiles,
        )
        for profile in resolved_profiles:
            layer(profile.cad, "profile", profile.qualified_id)
            manufacturing_layers.append(
                (DirectiveSource(profile.qualified_id), profile.slicing)
            )
        for product_name, item_index, product_item in reversed(candidate.layers):
            layer(system.products[product_name].variables, "product", product_name)
            layer(product_item.variables, "item", f"{product_name}[{item_index}]")
            manufacturing_layers.append(
                (DirectiveSource(f"product:{product_name}"),
                 system.products[product_name].slicing)
            )
            manufacturing_layers.append(
                (DirectiveSource(f"item:{product_name}[{item_index}]"),
                 product_item.slicing)
            )
        layer(selection.defines, "cli", "defines")
        layer(selection.set_defines.get(candidate.set_name, {}), "cli", candidate.set_name)
        layer({}, "cli", "raw_defines", parse_raw_defines(selection.raw_defines))
        variables, raw, sources = resolve_variables(variable_layers)
        manufacturing = merge_manufacturing(manufacturing_layers)

        geometry_payload = {
            "planning_schema_version": PLANNING_SCHEMA_VERSION,
            "source_identity": source_identities[candidate.model_id],
            "model_id": candidate.model_id,
            "set_name": candidate.set_name,
            "variables": _plain(variables),
            "raw_defines": raw,
        }
        geometry_fingerprint = _canonical_hash(geometry_payload)
        manufacturing_fingerprint = _canonical_hash({
            "system_manifest_hash": manifest_hash,
            "model_metadata_hash": _canonical_hash(model.metadata_snapshot),
            "profile_hashes": [profile.content_hash for profile in resolved_profiles],
            "policy": manufacturing.fingerprint,
        })
        identity = _canonical_hash({
            "geometry": geometry_fingerprint,
            "manufacturing": manufacturing_fingerprint,
        })
        if identity not in unique:
            unique[identity] = {
                "candidate": candidate, "variables": variables, "raw": raw,
                "sources": sources,
                "profiles": [
                    _resolved_profile(profile, repo_root=repo_root, data_dir=data_dir)
                    for profile in resolved_profiles
                ],
                "manufacturing": manufacturing,
                "geometry_fingerprint": geometry_fingerprint,
                "manufacturing_fingerprint": manufacturing_fingerprint,
                "paths": [],
            }
            order.append(identity)
        if candidate.path is not None:
            paths = unique[identity]["paths"]
            assert isinstance(paths, list)
            if candidate.path not in paths:
                paths.append(candidate.path)

    jobs: list[RenderJob] = []
    used_variant_names: set[str] = set()
    for identity in order:
        details = unique[identity]
        candidate = details["candidate"]
        assert isinstance(candidate, _Candidate)
        base = candidate.variant or candidate.set_name
        base = _ARTIFACT_COMPONENT.sub("-", base).strip("-.") or "set"
        variant_name = base
        suffix = 2
        while variant_name in used_variant_names:
            variant_name = f"{base}-{suffix}"
            suffix += 1
        used_variant_names.add(variant_name)
        jobs.append(RenderJob(
            artifact_id=f"{variant_name}--{str(details['geometry_fingerprint'])[:12]}",
            model_id=candidate.model_id, set_name=candidate.set_name,
            variant_name=variant_name,
            variables=details["variables"],  # type: ignore[arg-type]
            raw_defines=details["raw"],  # type: ignore[arg-type]
            variable_sources=details["sources"],  # type: ignore[arg-type]
            profiles=tuple(details["profiles"]),  # type: ignore[arg-type]
            manufacturing=details["manufacturing"],  # type: ignore[arg-type]
            product_paths=tuple(details["paths"]),  # type: ignore[arg-type]
            geometry_fingerprint=details["geometry_fingerprint"],  # type: ignore[arg-type]
            manufacturing_fingerprint=details["manufacturing_fingerprint"],  # type: ignore[arg-type]
        ))
    return RenderPlan(system.name, system.path, selection, tuple(jobs), manifest_hash)


def plan_as_dict(plan: RenderPlan) -> dict[str, object]:
    """Return a stable JSON-compatible render plan representation."""

    return {
        "system_name": plan.system_name,
        "system_path": str(plan.system_path),
        "system_manifest_hash": plan.system_manifest_hash,
        "selection": {
            "product": plan.selection.product, "model": plan.selection.model,
            "sets": list(plan.selection.sets), "all_sets": plan.selection.all_sets,
            "defines": _plain(plan.selection.defines),
            "set_defines": _plain(plan.selection.set_defines),
            "raw_defines": list(plan.selection.raw_defines),
            "profiles": list(plan.selection.profiles),
            "use_default_profiles": plan.selection.use_default_profiles,
        },
        "jobs": [{
            "artifact_id": job.artifact_id, "model_id": job.model_id,
            "set_name": job.set_name, "variant_name": job.variant_name,
            "variables": _plain(job.variables), "raw_defines": dict(job.raw_defines),
            "variable_sources": {
                name: {
                    "layers": [{
                        "kind": layer.kind,
                        "source_id": layer.source_id,
                        "value": _plain(layer.value),
                        "raw_expression": layer.raw_expression,
                    } for layer in source.layers],
                    "winner": {
                        "kind": source.winner.kind,
                        "source_id": source.winner.source_id,
                        "value": _plain(source.winner.value),
                        "raw_expression": source.winner.raw_expression,
                    },
                }
                for name, source in job.variable_sources.items()
            },
            "profiles": [_profile_as_dict(profile) for profile in job.profiles],
            "manufacturing": {
                "directives": {
                    key: {
                        "value": _plain(directive.value),
                        "strength": directive.strength,
                        "source": directive.source.id,
                    }
                    for key, directive in job.manufacturing.directives.items()
                },
                "notes": [list(note) for note in job.manufacturing.notes],
            },
            "product_paths": [list(path) for path in job.product_paths],
            "geometry_fingerprint": job.geometry_fingerprint,
            "manufacturing_fingerprint": job.manufacturing_fingerprint,
        } for job in plan.jobs],
    }
