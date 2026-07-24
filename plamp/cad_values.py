"""Shared deterministic OpenSCAD value handling."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json
import math
from types import MappingProxyType


def _freeze(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


@dataclass(frozen=True)
class VariableLayer:
    """One typed or raw assignment contributing to a resolved CAD variable."""

    kind: str
    source_id: str
    value: object | None = None
    raw_expression: str | None = None


@dataclass(frozen=True)
class ResolvedVariable:
    """Complete low-to-high assignment history for one CAD variable."""

    name: str
    layers: tuple[VariableLayer, ...]

    @property
    def winner(self) -> VariableLayer:
        return self.layers[-1]

    @property
    def kind(self) -> str:
        """Return the winner kind for transitional callers."""
        return self.winner.kind

    @property
    def source_id(self) -> str:
        """Return the winner source for transitional callers."""
        return self.winner.source_id


def resolve_variables(
    layers: Sequence[
        tuple[str, str, Mapping[str, object], Mapping[str, str]]
    ],
) -> tuple[
    Mapping[str, object], Mapping[str, str], Mapping[str, ResolvedVariable]
]:
    """Resolve ordered typed/raw overlays while retaining every contributor."""

    typed: dict[str, object] = {}
    raw: dict[str, str] = {}
    history: dict[str, list[VariableLayer]] = {}
    for kind, source_id, typed_values, raw_values in layers:
        for name, value in typed_values.items():
            frozen = _freeze(value)
            typed[name] = frozen
            raw.pop(name, None)
            history.setdefault(name, []).append(
                VariableLayer(kind, source_id, value=frozen)
            )
        for name, expression in raw_values.items():
            raw[name] = expression
            typed.pop(name, None)
            history.setdefault(name, []).append(
                VariableLayer(kind, source_id, raw_expression=expression)
            )
    provenance = {
        name: ResolvedVariable(name, tuple(assignments))
        for name, assignments in history.items()
    }
    return (
        MappingProxyType(typed),
        MappingProxyType(raw),
        MappingProxyType(provenance),
    )


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


def parse_raw_defines(defines: Sequence[str]) -> dict[str, str]:
    """Parse repeatable NAME=EXPRESSION values, retaining the final occurrence."""

    parsed: dict[str, str] = {}
    for define in defines:
        if "=" not in define:
            raise ValueError("Raw defines must use NAME=EXPRESSION")
        name, expression = define.split("=", 1)
        if not name:
            raise ValueError("Raw defines must use NAME=EXPRESSION")
        parsed[name] = expression
    return parsed
