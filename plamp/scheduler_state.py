from dataclasses import dataclass
from typing import Any

EXPECTED_FIRMWARE_PROTOCOL = 4
DEVICE_MODES = frozenset({"scheduled", "ready"})


@dataclass(frozen=True)
class FirmwareIdentity:
    name: str
    revision: str
    protocol: int


def _integer(value: Any, label: str, *, minimum: int, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{label} must be an integer >= {minimum}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{label} must be <= {maximum}")
    return value


def _device_mode(source: dict[str, Any], index: int) -> str:
    mode = source.get("mode")
    enabled = source.get("enabled")
    if mode is not None:
        if mode not in DEVICE_MODES:
            raise ValueError(f"device {index} mode must be scheduled or ready")
        if enabled is not None and isinstance(enabled, bool):
            legacy = "scheduled" if enabled else "ready"
            if legacy != mode:
                raise ValueError(f"device {index} mode conflicts with enabled")
        return mode
    if isinstance(enabled, bool):
        return "scheduled" if enabled else "ready"
    raise ValueError(f"device {index} mode must be scheduled or ready")


def normalize_scheduler_state(raw: Any) -> dict[str, Any]:
    """Return only Pico-owned state or raise ValueError before side effects."""
    if not isinstance(raw, dict) or set(raw) - {"devices", "report_every"}:
        raise ValueError("scheduler state must contain only devices and report_every")
    if not isinstance(raw.get("devices"), list):
        raise ValueError("devices must be a list")
    normalized, ids, pins = [], set(), set()
    for index, source in enumerate(raw["devices"]):
        if not isinstance(source, dict):
            raise ValueError(f"device {index} must be an object")
        allowed = {"id", "type", "pin", "mode", "enabled", "current_t", "reschedule", "pattern"}
        if set(source) - allowed:
            raise ValueError(f"device {index} has invalid fields")
        mode = _device_mode(source, index)
        required_core = {"type", "pin", "current_t", "reschedule", "pattern"}
        if not required_core <= set(source):
            raise ValueError(f"device {index} has invalid fields")
        if "mode" not in source and "enabled" not in source:
            raise ValueError(f"device {index} mode must be scheduled or ready")
        device_type = source["type"]
        if device_type != "gpio":
            raise ValueError(f"device {index} has unsupported type: {device_type}")
        pin = _integer(source["pin"], f"device {index} pin", minimum=0, maximum=29)
        if pin in pins:
            raise ValueError(f"duplicate pin: {pin}")
        pins.add(pin)
        device_id = source.get("id")
        if device_id is not None:
            if not isinstance(device_id, str) or not device_id:
                raise ValueError(f"device {index} id must be a non-empty string")
            if device_id in ids:
                raise ValueError(f"duplicate device id: {device_id}")
            ids.add(device_id)
        current_t = _integer(source["current_t"], f"device {index} current_t", minimum=0)
        reschedule = _integer(source["reschedule"], f"device {index} reschedule", minimum=0, maximum=1)
        if not isinstance(source["pattern"], list) or not source["pattern"]:
            raise ValueError(f"device {index} pattern must be a non-empty list")
        pattern = []
        for step_index, source_step in enumerate(source["pattern"]):
            if not isinstance(source_step, dict) or set(source_step) != {"val", "dur"}:
                raise ValueError(f"device {index} pattern {step_index} must contain val and dur")
            value = _integer(source_step["val"], f"device {index} pattern {step_index} val", minimum=0, maximum=1)
            duration = _integer(source_step["dur"], f"device {index} pattern {step_index} dur", minimum=1)
            pattern.append({"val": value, "dur": duration})
        item = {"type": device_type, "pin": pin, "mode": mode, "current_t": current_t,
                "reschedule": reschedule, "pattern": pattern}
        if device_id is not None:
            item["id"] = device_id
        normalized.append(item)
    return {"devices": normalized}


def firmware_identity(report: Any) -> FirmwareIdentity | None:
    """Return identity for a valid new report; return None for a legacy report."""
    content = report.get("content") if isinstance(report, dict) else None
    raw = content.get("firmware") if isinstance(content, dict) else None
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("report firmware must be an object")
    name, revision, protocol = raw.get("name"), raw.get("revision"), raw.get("protocol")
    if not isinstance(name, str) or not isinstance(revision, str):
        raise ValueError("report firmware name and revision must be strings")
    protocol = _integer(protocol, "report firmware protocol", minimum=1)
    return FirmwareIdentity(name, revision, protocol)


def report_matches_state(report: Any, state: Any) -> bool:
    """Compare normalized static scheduler fields in stable order."""
    expected = normalize_scheduler_state(state)["devices"]
    content = report.get("content") if isinstance(report, dict) else None
    devices = content.get("devices") if isinstance(content, dict) else None
    if not isinstance(devices, list) or len(devices) != len(expected):
        return False
    fields = ("id", "type", "pin", "mode", "reschedule", "pattern")
    observed_state = []
    for item in devices:
        if not isinstance(item, dict):
            return False
        mode = item.get("mode")
        if mode is None and isinstance(item.get("enabled"), bool):
            mode = "scheduled" if item["enabled"] else "ready"
        if mode == "ready" and (
            type(item.get("current_value")) is not int
            or item["current_value"] != 0
        ):
            return False
        observed = {key: item[key] for key in fields if key in item}
        if "mode" not in observed and mode in DEVICE_MODES:
            observed["mode"] = mode
        observed_state.append({
            **observed,
            "current_t": 0,
        })
    try:
        normalized_observed = normalize_scheduler_state(
            {"devices": observed_state}
        )["devices"]
    except ValueError:
        return False
    observed = [{key: item[key] for key in fields if key in item}
                for item in normalized_observed]
    static_expected = [{key: item[key] for key in fields if key in item}
                       for item in expected]
    return observed == static_expected
