"""Shared deterministic OpenSCAD value handling."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
import math


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
