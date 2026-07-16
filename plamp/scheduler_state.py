from dataclasses import dataclass
from typing import Any

EXPECTED_FIRMWARE_PROTOCOL = 2


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
        allowed = {"id", "type", "pin", "current_t", "reschedule", "pattern"}
        if set(source) - allowed or not {"type", "pin", "current_t", "reschedule", "pattern"} <= set(source):
            raise ValueError(f"device {index} has invalid fields")
        device_type = source["type"]
        if device_type not in {"gpio", "pwm"}:
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
            maximum = 1 if device_type == "gpio" else 65535
            value = _integer(source_step["val"], f"device {index} pattern {step_index} val", minimum=0, maximum=maximum)
            duration = _integer(source_step["dur"], f"device {index} pattern {step_index} dur", minimum=1)
            pattern.append({"val": value, "dur": duration})
        item = {"type": device_type, "pin": pin, "current_t": current_t,
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
    """Compare normalized id/type/pin/reschedule/pattern fields in stable order."""
    expected = normalize_scheduler_state(state)["devices"]
    content = report.get("content") if isinstance(report, dict) else None
    devices = content.get("devices") if isinstance(content, dict) else None
    if not isinstance(devices, list) or len(devices) != len(expected):
        return False
    fields = ("id", "type", "pin", "reschedule", "pattern")
    observed = [{key: item.get(key) for key in fields if key in item}
                for item in devices if isinstance(item, dict)]
    static_expected = [{key: item[key] for key in fields if key in item}
                       for item in expected]
    return observed == static_expected
