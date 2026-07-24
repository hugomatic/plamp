"""Normalize and merge portable CAD manufacturing guidance."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import hashlib
import json
import math
from types import MappingProxyType


_KEYS = frozenset({
    "orientation", "supports", "support_style", "ironing", "material",
    "layer_height", "minimum_perimeters", "adhesion", "notes",
})
_RECOMMENDATIONS = frozenset({
    "required", "recommended", "optional", "discouraged", "forbidden",
})
_REQUIREMENT_VALUES = frozenset({"required", "forbidden"})
_STRENGTHS = {
    "required": "requirement",
    "requirement": "requirement",
    "recommended": "preference",
    "preference": "preference",
}


@dataclass(frozen=True)
class DirectiveSource:
    id: str

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id:
            raise ValueError("directive source id must be a non-empty string")


@dataclass(frozen=True)
class SlicingDirective:
    key: str
    value: object
    strength: str
    source: DirectiveSource


class ManufacturingConflict(ValueError):
    """Two sources impose different hard requirements on one directive."""

    def __init__(self, key: str, sources: tuple[str, str]):
        self.key = key
        self.sources = sources
        super().__init__(
            f"Conflicting requirements for {key!r} from {sources[0]!r} and {sources[1]!r}"
        )


@dataclass(frozen=True)
class ManufacturingPolicy:
    directives: Mapping[str, SlicingDirective]
    notes: tuple[tuple[str, str], ...]
    fingerprint: str


def _freeze(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _unwrap(key: str, raw: object) -> tuple[object, str]:
    if isinstance(raw, Mapping):
        unknown = tuple(item for item in raw if item not in {"value", "strength"})
        if unknown or set(raw) != {"value", "strength"}:
            raise ValueError(
                f"{key} directive object must contain exactly 'value' and 'strength'"
            )
        strength = raw["strength"]
        if not isinstance(strength, str) or strength not in _STRENGTHS:
            raise ValueError(f"{key} has invalid directive strength {strength!r}")
        return raw["value"], _STRENGTHS[strength]
    strength = (
        "requirement"
        if key in {"supports", "ironing"} and raw in _REQUIREMENT_VALUES
        else "preference"
    )
    return raw, strength


def _validate(key: str, value: object) -> object:
    if key in {"supports", "ironing"}:
        if not isinstance(value, str) or value not in _RECOMMENDATIONS:
            raise ValueError(f"{key} must be one of {sorted(_RECOMMENDATIONS)}")
    elif key in {"orientation", "support_style", "material", "adhesion"}:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} must be a non-empty string")
    elif key == "layer_height":
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or value <= 0):
            raise ValueError("layer_height must be a finite positive number")
    elif key == "minimum_perimeters":
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError("minimum_perimeters must be a positive integer")
    return value


def normalize_slicing(
    slicing: Mapping[str, object], source: DirectiveSource
) -> tuple[Mapping[str, SlicingDirective], tuple[tuple[str, str], ...]]:
    """Validate one portable slicing layer and attach provenance."""

    if not isinstance(slicing, Mapping):
        raise ValueError("slicing metadata must be an object")
    unknown = tuple(key for key in slicing if key not in _KEYS)
    if unknown:
        raise ValueError(f"unknown slicing key {unknown[0]!r}")
    raw_notes = slicing.get("notes", ())
    if (not isinstance(raw_notes, (list, tuple))
            or any(not isinstance(note, str) or not note for note in raw_notes)):
        raise ValueError("notes must be an array of non-empty strings")
    directives: dict[str, SlicingDirective] = {}
    for key, raw in slicing.items():
        if key == "notes":
            continue
        value, strength = _unwrap(key, raw)
        directives[key] = SlicingDirective(
            key, _validate(key, value), strength, source
        )
    notes = tuple((source.id, note) for note in raw_notes)
    return MappingProxyType(directives), notes


def validated_slicing(
    slicing: Mapping[str, object], source: DirectiveSource
) -> Mapping[str, object]:
    """Return a validated, recursively immutable copy of raw slicing metadata."""

    normalize_slicing(slicing, source)
    return _freeze(slicing)  # type: ignore[return-value]


def manufacturing_fingerprint(
    directives: Mapping[str, SlicingDirective],
    notes: Iterable[tuple[str, str]],
) -> str:
    """Return a stable SHA-256 identity for resolved manufacturing advice."""

    payload = {
        "directives": {
            key: {
                "value": directive.value,
                "strength": directive.strength,
                "source": directive.source.id,
            }
            for key, directive in sorted(directives.items())
        },
        "notes": [list(note) for note in notes],
    }
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def merge_manufacturing(
    layers: Iterable[tuple[DirectiveSource, Mapping[str, object]]],
) -> ManufacturingPolicy:
    """Merge ordered layers, retaining hard requirements and all notes."""

    merged: dict[str, SlicingDirective] = {}
    notes: list[tuple[str, str]] = []
    for source, slicing in layers:
        normalized, layer_notes = normalize_slicing(slicing, source)
        notes.extend(layer_notes)
        for key, incoming in normalized.items():
            current = merged.get(key)
            if current is None:
                merged[key] = incoming
            elif current.strength == "requirement":
                if (incoming.strength == "requirement"
                        and incoming.value != current.value):
                    raise ManufacturingConflict(
                        key, (current.source.id, incoming.source.id)
                    )
            elif incoming.strength == "requirement" or incoming.strength == "preference":
                merged[key] = incoming
    immutable = MappingProxyType(merged.copy())
    frozen_notes = tuple(notes)
    return ManufacturingPolicy(
        immutable, frozen_notes, manufacturing_fingerprint(immutable, frozen_notes)
    )
