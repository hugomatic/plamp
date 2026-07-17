from __future__ import annotations

import json
from typing import Any


class PicoProtocolError(ValueError):
    pass


def decode_message_line(raw: bytes) -> dict[str, Any]:
    if not raw.endswith(b"\n"):
        raise PicoProtocolError("message is not newline terminated")
    try:
        value = json.loads(raw.decode("utf-8").strip())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PicoProtocolError(f"invalid message JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise PicoProtocolError("message JSON must be an object")
    if "type" not in value and "kind" in value:
        value = dict(value)
        value["type"] = value.pop("kind")
    if not isinstance(value.get("type"), str):
        raise PicoProtocolError("message type must be a string")
    return value


def decode_report_line(raw: bytes) -> dict[str, Any]:
    value = decode_message_line(raw)
    if value.get("type") != "report" or not isinstance(value.get("content"), dict):
        raise PicoProtocolError("message is not a report")
    if not isinstance(value["content"].get("devices"), list):
        raise PicoProtocolError("report content.devices must be a list")
    if "firmware" in value["content"] and not isinstance(value["content"]["firmware"], dict):
        raise PicoProtocolError("report content.firmware must be an object")
    return value
