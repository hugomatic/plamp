"""Pure Plamp8 controller-profile conversion helpers."""

from dataclasses import asdict, dataclass
from collections.abc import Callable
from pathlib import Path
from typing import Any

from plamp.config import ConfigError, atomic_write_json, load_config, save_config
from plamp.locks import exclusive_lock
from plamp.pico_commands import upgrade_scheduler
from plamp.pico_transport import request_report
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


_PLAMP8_IDENTITY = FirmwareIdentity("pico_scheduler", "plamp8", 3)


def _result(preview: dict[str, Any], *, applied: bool, recovery_path: Path | None) -> dict[str, Any]:
    provisioned = preview["action"] == "provision"
    return {
        **preview,
        "hardware_changed": applied and provisioned,
        "host_config_changed": applied,
        "reset": applied and provisioned,
        "verified": applied,
        "recovery_path": None if recovery_path is None else str(recovery_path),
    }


def _merged_controller_config(
    config: dict[str, Any], controller_id: str, pico_serial: str, report: dict[str, Any]
) -> dict[str, Any]:
    controllers = config.get("controllers")
    if not isinstance(controllers, dict):
        raise ConfigError("controllers must be a mapping")
    existing = controllers.get(controller_id)
    for existing_id, controller in controllers.items():
        payload = controller.get("payload") if isinstance(controller, dict) else None
        serial = payload.get("pico_serial") if isinstance(payload, dict) else None
        if serial == pico_serial and existing_id != controller_id:
            raise ConfigError(f"serial already assigned to controller: {existing_id}")
    if existing is not None:
        payload = existing.get("payload") if isinstance(existing, dict) else None
        serial = payload.get("pico_serial") if isinstance(payload, dict) else None
        devices = existing.get("settings", {}).get("devices") if isinstance(existing, dict) else None
        if serial != pico_serial or not isinstance(devices, dict) or devices:
            raise ConfigError(f"controller already has a configuration: {controller_id}")
    updated = dict(config)
    updated_controllers = dict(controllers)
    updated_controllers[controller_id] = controller_config_from_report(pico_serial, report)
    updated["controllers"] = updated_controllers
    return updated


def _upgrade_report(result: dict[str, Any]) -> dict[str, Any]:
    report = result.get("report") if isinstance(result, dict) else None
    if not isinstance(report, dict):
        raise ConfigError("controller provisioning verification report is missing")
    return report


def add_controller(
    controller_id: str,
    pico_serial: str,
    profile_id: str,
    *,
    apply: bool,
    allow_provision: bool,
    config_file: Path,
    data_dir: Path,
    repo_root: Path,
    lock_dir: Path,
    timeout: float,
    report_func: Callable[..., dict[str, Any]] = request_report,
    upgrade_func: Callable[..., dict[str, Any]] = upgrade_scheduler,
) -> dict[str, Any]:
    """Preview or explicitly import a single Plamp8 controller report."""
    if profile_id != "plamp8":
        raise ConfigError(f"unsupported controller profile: {profile_id}")
    report = report_func(pico_serial, lock_dir=lock_dir, timeout=timeout)
    preview = preview_controller_add(controller_id, pico_serial, report, _PLAMP8_IDENTITY)
    if not apply:
        return _result(preview, applied=False, recovery_path=None)
    if preview["action"] == "provision" and not allow_provision:
        raise ConfigError("controller requires explicit --provision")

    imported_report = report
    recovery_path = None
    if preview["action"] == "provision":
        # Avoid mutating a controller that cannot be represented in host config.
        with exclusive_lock(lock_dir / "config.lock", timeout=timeout):
            _merged_controller_config(load_config(config_file), controller_id, pico_serial, report)
        recovery_path = data_dir / "controller-backups" / f"{controller_id}-{pico_serial}-pre-provision.json"
        atomic_write_json(recovery_path, report)
        upgraded = upgrade_func(
            pico_serial,
            provisioned_plamp8_state(report),
            lock_dir=lock_dir,
            timeout=timeout,
            repo_root=repo_root,
            data_dir=data_dir,
        )
        imported_report = _upgrade_report(upgraded)
        verified_preview = preview_controller_add(
            controller_id, pico_serial, imported_report, _PLAMP8_IDENTITY
        )
        if verified_preview["action"] != "import":
            raise ConfigError("controller provisioning verification failed")

    with exclusive_lock(lock_dir / "config.lock", timeout=timeout):
        save_config(
            config_file,
            _merged_controller_config(load_config(config_file), controller_id, pico_serial, imported_report),
        )
        atomic_write_json(
            data_dir / "timers" / f"{controller_id}.json",
            provisioned_plamp8_state(imported_report),
        )
    return _result(preview, applied=True, recovery_path=recovery_path)
