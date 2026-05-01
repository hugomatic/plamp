from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, TextIO


class InputError(RuntimeError):
    pass


def load_json_input(value: str, stdin: TextIO | None = None) -> Any:
    source = stdin or sys.stdin
    if value == "-":
        raw = source.read()
    elif value.startswith("@"):
        raw = Path(value[1:]).read_text(encoding="utf-8")
    else:
        raise InputError("expected @file.json or - for stdin")

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise InputError(f"invalid JSON input: {exc.msg}") from exc


def format_json_output(data: Any, pretty: bool = False) -> str:
    if pretty:
        return json.dumps(data, indent=2, sort_keys=True) + "\n"
    return json.dumps(data, sort_keys=True) + "\n"


def render_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""

    columns: list[str] = list(rows[0].keys())
    for row in rows[1:]:
        for key in row:
            if key not in columns:
                columns.append(key)

    widths = {column: len(column) for column in columns}
    for row in rows:
        for column in columns:
            value = "" if row.get(column) is None else str(row.get(column))
            if len(value) > widths[column]:
                widths[column] = len(value)

    header = " | ".join(column.ljust(widths[column]) for column in columns)
    separator = "+".join("-" * widths[column] for column in columns)
    body = [
        " | ".join(
            ("" if row.get(column) is None else str(row.get(column))).ljust(widths[column])
            for column in columns
        )
        for row in rows
    ]
    return "\n".join([header, separator, *body]) + "\n"
