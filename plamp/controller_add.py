"""Pure Plamp8 controller-profile conversion helpers."""

from dataclasses import asdict, dataclass
from typing import Any

from plamp.scheduler_state import FirmwareIdentity, firmware_identity, normalize_scheduler_state


@dataclass(frozen=True)
class ProfileChannel:
    pin: int
    device_id: str
    enabled: bool


PLAMP8_CHANNELS = (
    ProfileChannel(21, "ph_up", False),
    ProfileChannel(20, "ph_down", False),
    ProfileChannel(19, "agitator", False),
    ProfileChannel(18, "nutrients", False),
    ProfileChannel(17, "pump", True),
    ProfileChannel(16, "fan", True),
    ProfileChannel(15, "lights_1", True),
    ProfileChannel(14, "lights_2", True),
)


def display_device_id(device_id: str) -> str:
    text = device_id.replace("_", " ")
    return text[:1].upper() + text[1:]


def _report_devices(report: Any) -> list[dict[str, Any]]:
    content = report.get("content") if isinstance(report, dict) else None
    devices = content.get("devices") if isinstance(content, dict) else None
    if not isinstance(devices, list):
        raise ValueError("report must contain devices")
    if not all(isinstance(device, dict) for device in devices):
        raise ValueError("report devices must be objects")
    return devices


def _supported_identity(report: Any) -> FirmwareIdentity | None:
    identity = firmware_identity(report)
    if identity is None:
        return None
    if identity.name != "pico_scheduler" or identity.protocol != 3:
        raise ValueError("report firmware must be pico_scheduler protocol 3")
    return identity


def _profile_report_devices(report: Any) -> tuple[list[dict[str, Any]], FirmwareIdentity | None]:
    identity = _supported_identity(report)
    devices = _report_devices(report)
    if len(devices) != len(PLAMP8_CHANNELS):
        raise ValueError("report must contain exactly eight profile devices")
    devices_by_pin: dict[int, dict[str, Any]] = {}
    for device in devices:
        pin = device.get("pin")
        if not isinstance(pin, int) or isinstance(pin, bool):
            raise ValueError("report devices must use integer pins")
        if pin in devices_by_pin:
            raise ValueError("report must contain unique profile pins")
        devices_by_pin[pin] = device
    profile_pins = {channel.pin for channel in PLAMP8_CHANNELS}
    if set(devices_by_pin) != profile_pins:
        raise ValueError("report must contain exactly the Plamp8 profile pins")
    return [devices_by_pin[channel.pin] for channel in PLAMP8_CHANNELS], identity


def _captured_phase(device: dict[str, Any]) -> Any:
    cycle_t = device.get("cycle_t")
    if cycle_t is not None:
        return cycle_t
    elapsed_t = device.get("elapsed_t")
    if elapsed_t is not None:
        return elapsed_t
    return device.get("current_t", 0)


def provisioned_plamp8_state(report: Any) -> dict[str, Any]:
    """Map a complete report onto the canonical Plamp8 scheduler state."""
    report_devices, _ = _profile_report_devices(report)
    devices = []
    for channel, source in zip(PLAMP8_CHANNELS, report_devices):
        devices.append({
            "id": channel.device_id,
            "type": source.get("type"),
            "pin": channel.pin,
            "enabled": channel.enabled,
            "current_t": _captured_phase(source),
            "reschedule": source.get("reschedule"),
            "pattern": source.get("pattern"),
        })
    return normalize_scheduler_state({"devices": devices})


def _editor_from_device(device: dict[str, Any]) -> dict[str, Any]:
    pattern = device["pattern"]
    phase = device["current_t"]
    if len(pattern) == 2 and pattern[0]["val"] > 0 and pattern[1]["val"] == 0:
        return {
            "kind": "cycle",
            "on_seconds": pattern[0]["dur"],
            "off_seconds": pattern[1]["dur"],
            "start_at_seconds": phase,
        }
    return {"kind": "events", "events": pattern, "start_at_seconds": phase}


def controller_config_from_report(pico_serial: str, report: Any) -> dict[str, Any]:
    """Convert a fresh Plamp8 report into persisted controller configuration."""
    state = provisioned_plamp8_state(report)
    devices = {
        device["id"]: {
            "pin": device["pin"],
            "output_type": device["type"],
            "display_order": index,
            "visibility": "visible",
            "programming": "enabled" if device["enabled"] else "disabled",
            "editor": _editor_from_device(device),
        }
        for index, device in enumerate(state["devices"])
    }
    return {
        "type": "pico_scheduler",
        "payload": {"pico_serial": pico_serial, "report_every": 10},
        "settings": {"devices": devices},
    }


def _identity_json(identity: FirmwareIdentity | None) -> dict[str, Any] | None:
    return asdict(identity) if identity is not None else None


def _channel_rows(devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"pin": device["pin"], "id": device.get("id"), "enabled": device.get("enabled")}
        for device in devices
    ]


def preview_controller_add(
    controller_id: str,
    pico_serial: str,
    report: Any,
    expected_identity: FirmwareIdentity,
) -> dict[str, Any]:
    """Describe whether a fresh report can be imported or needs provisioning."""
    before, observed = _profile_report_devices(report)
    after = provisioned_plamp8_state(report)["devices"]
    action = "import" if observed == expected_identity else "provision"
    return {
        "controller": controller_id,
        "serial": pico_serial,
        "profile": "plamp8",
        "action": action,
        "observed_identity": _identity_json(observed),
        "expected_identity": _identity_json(expected_identity),
        "requires_reset": action == "provision",
        "before": _channel_rows(before),
        "after": _channel_rows(after),
    }
