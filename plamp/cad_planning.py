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


@dataclass(frozen=True)
class CadSelection:
    product: str | None = None
    model: str | None = None
    sets: tuple[str, ...] = ()
    all_sets: bool = False
    defines: Mapping[str, object] = field(default_factory=dict)
    set_defines: Mapping[str, Mapping[str, object]] = field(default_factory=dict)
    raw_defines: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "sets", tuple(self.sets))
        object.__setattr__(self, "defines", _mapping(self.defines))
        object.__setattr__(self, "set_defines", MappingProxyType({
            name: _mapping(values) for name, values in self.set_defines.items()
        }))
        object.__setattr__(self, "raw_defines", tuple(self.raw_defines))


@dataclass(frozen=True)
class RenderJob:
    artifact_id: str
    model_id: str
    set_name: str
    variant_name: str
    variables: Mapping[str, object]
    raw_defines: Mapping[str, str]
    variable_sources: Mapping[str, ResolvedVariable]
    profiles: tuple[str, ...]
    slicing: Mapping[str, object]
    product_paths: tuple[tuple[str, ...], ...]
    fingerprint: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "variables", _mapping(self.variables))
        object.__setattr__(self, "raw_defines", MappingProxyType(dict(self.raw_defines)))
        object.__setattr__(self, "variable_sources",
                           MappingProxyType(dict(self.variable_sources)))
        object.__setattr__(self, "profiles", tuple(self.profiles))
        object.__setattr__(self, "slicing", _mapping(self.slicing))
        object.__setattr__(self, "product_paths",
                           tuple(tuple(path) for path in self.product_paths))


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
    layers: tuple[tuple[str, CadProductItem], ...]


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
               layers: tuple[tuple[str, CadProductItem], ...],
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
            current_layers = layers + ((name, product_item),)
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
                      source_identities: Mapping[str, str]) -> RenderPlan:
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
        profiles: list[str] = []
        slicing: dict[str, object] = dict(model.sets[candidate.set_name].slicing)

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
        for product_name, product_item in candidate.layers:
            profiles.extend(system.products[product_name].profiles)
            profiles.extend(product_item.profiles)
        for profile_id in profiles:
            profile = system.profiles.get(profile_id)
            if profile is not None:
                layer(profile.cad, "profile", profile.qualified_id)
        for product_name, product_item in reversed(candidate.layers):
            layer(system.products[product_name].variables, "product", product_name)
            index = system.products[product_name].items.index(product_item)
            layer(product_item.variables, "item", f"{product_name}[{index}]")
            slicing.update(system.products[product_name].slicing)
            slicing.update(product_item.slicing)
        layer(selection.defines, "cli", "defines")
        layer(selection.set_defines.get(candidate.set_name, {}), "cli", candidate.set_name)
        layer({}, "cli", "raw_defines", parse_raw_defines(selection.raw_defines))
        variables, raw, sources = resolve_variables(variable_layers)

        payload = {
            "planning_schema_version": PLANNING_SCHEMA_VERSION,
            "system_manifest_hash": manifest_hash,
            "source_identity": source_identities[candidate.model_id],
            "model_id": candidate.model_id,
            "set_name": candidate.set_name,
            "variables": _plain(variables),
            "raw_defines": raw,
            "profiles": profiles,
            "slicing": _plain(slicing),
        }
        fingerprint = _canonical_hash(payload)
        if fingerprint not in unique:
            unique[fingerprint] = {
                "candidate": candidate, "variables": variables, "raw": raw,
                "sources": sources, "profiles": profiles, "slicing": slicing,
                "paths": [],
            }
            order.append(fingerprint)
        if candidate.path is not None:
            paths = unique[fingerprint]["paths"]
            assert isinstance(paths, list)
            if candidate.path not in paths:
                paths.append(candidate.path)

    jobs: list[RenderJob] = []
    base_counts: dict[str, int] = {}
    for fingerprint in order:
        details = unique[fingerprint]
        candidate = details["candidate"]
        assert isinstance(candidate, _Candidate)
        base = candidate.variant or candidate.set_name
        base = _ARTIFACT_COMPONENT.sub("-", base).strip("-.") or "set"
        base_counts[base] = base_counts.get(base, 0) + 1
        variant_name = base if base_counts[base] == 1 else f"{base}-{base_counts[base]}"
        jobs.append(RenderJob(
            artifact_id=f"{variant_name}--{fingerprint[:12]}",
            model_id=candidate.model_id, set_name=candidate.set_name,
            variant_name=variant_name,
            variables=details["variables"],  # type: ignore[arg-type]
            raw_defines=details["raw"],  # type: ignore[arg-type]
            variable_sources=details["sources"],  # type: ignore[arg-type]
            profiles=tuple(details["profiles"]),  # type: ignore[arg-type]
            slicing=details["slicing"],  # type: ignore[arg-type]
            product_paths=tuple(details["paths"]),  # type: ignore[arg-type]
            fingerprint=fingerprint,
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
            "profiles": list(job.profiles), "slicing": _plain(job.slicing),
            "product_paths": [list(path) for path in job.product_paths],
            "fingerprint": job.fingerprint,
        } for job in plan.jobs],
    }
