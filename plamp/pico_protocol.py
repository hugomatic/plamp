from __future__ import annotations

import json
from typing import Any


class PicoProtocolError(ValueError):
    pass


def decode_report_line(raw: bytes) -> dict[str, Any]:
    if not raw.endswith(b"\n"):
        raise PicoProtocolError("report is not newline terminated")
    try:
        value = json.loads(raw.decode("utf-8").strip())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PicoProtocolError(f"invalid report JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise PicoProtocolError("report JSON must be an object")
    if "type" not in value and "kind" in value:
        value = dict(value)
        value["type"] = value.pop("kind")
    if value.get("type") != "report" or not isinstance(value.get("content"), dict):
        raise PicoProtocolError("message is not a report")
    if not isinstance(value["content"].get("devices"), list):
        raise PicoProtocolError("report content.devices must be a list")
    return value
