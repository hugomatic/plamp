"""Pure Plamp8 controller-profile conversion helpers."""

import json
import re
from dataclasses import asdict, dataclass
from collections.abc import Callable
from pathlib import Path
from typing import Any

from plamp.config import (
    ConfigError,
    atomic_write_json,
    load_config,
    save_config,
    validate_config,
)
from plamp.locks import exclusive_lock
from plamp.pico_commands import upgrade_scheduler
from plamp.pico_firmware import firmware_revision
from plamp.pico_transport import request_report
from plamp.scheduler_state import (
    EXPECTED_FIRMWARE_PROTOCOL,
    FirmwareIdentity,
    firmware_identity,
    normalize_scheduler_state,
)


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

_SAFE_PATH_COMPONENT_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def display_device_id(device_id: str) -> str:
    text = device_id.replace("_", " ")
    return text[:1].upper() + text[1:]


def _report_devices(report: Any) -> list[dict[str, Any]]:
    if not isinstance(report, dict) or report.get("type") != "report":
        raise ValueError("controller response must be a report")
    content = report.get("content") if isinstance(report, dict) else None
    devices = content.get("devices") if isinstance(content, dict) else None
    if not isinstance(devices, list):
        raise ValueError("report must contain devices")
    if not all(isinstance(device, dict) for device in devices):
        raise ValueError("report devices must be objects")
    return devices


def _supported_identity(report: Any) -> FirmwareIdentity:
    identity = firmware_identity(report)
    if identity is None:
        raise ValueError("report must contain a firmware identity")
    if identity.name != "pico_scheduler":
        raise ValueError("report firmware must be pico_scheduler")
    if not identity.revision:
        raise ValueError("report firmware revision must be a non-empty string")
    if identity.protocol not in {2, EXPECTED_FIRMWARE_PROTOCOL}:
        raise ValueError(f"unsupported firmware protocol: {identity.protocol}")
    return identity


def _report_integer(
    value: Any, label: str, *, maximum: int | None = None
) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be an integer >= 0")
    if maximum is not None and value > maximum:
        raise ValueError(f"{label} must be <= {maximum}")
    return value


def _profile_report_devices(
    report: Any,
) -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]], FirmwareIdentity]:
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
    return devices, devices_by_pin, identity


def _validated_report_state(
    report: Any,
) -> tuple[dict[str, Any], dict[int, dict[str, Any]], FirmwareIdentity]:
    report_devices, devices_by_pin, identity = _profile_report_devices(report)
    required = {
        "id",
        "type",
        "pin",
        "elapsed_t",
        "current_value",
        "reschedule",
        "pattern",
    }
    if identity.protocol == EXPECTED_FIRMWARE_PROTOCOL:
        required.add("enabled")
    state_devices = []
    for index, source in enumerate(report_devices):
        if not required <= set(source):
            raise ValueError(f"device {index} has invalid fields")
        _report_integer(source["elapsed_t"], f"device {index} elapsed_t")
        cycle_t = _report_integer(
            source.get("cycle_t", source["elapsed_t"]),
            f"device {index} cycle_t",
        )
        current_value = _report_integer(
            source["current_value"], f"device {index} current_value", maximum=1
        )
        if source.get("enabled") is False and current_value != 0:
            raise ValueError(f"device {index} disabled current_value must be integer 0")
        state_devices.append(
            {
                "id": source.get("id"),
                "type": source.get("type"),
                "pin": source.get("pin"),
                "enabled": (
                    source.get("enabled")
                    if identity.protocol == EXPECTED_FIRMWARE_PROTOCOL
                    else True
                ),
                "current_t": cycle_t,
                "reschedule": source.get("reschedule"),
                "pattern": source.get("pattern"),
            }
        )
    return normalize_scheduler_state({"devices": state_devices}), devices_by_pin, identity


def _matches_plamp8_profile(state: dict[str, Any]) -> bool:
    devices_by_pin = {device["pin"]: device for device in state["devices"]}
    return all(
        devices_by_pin[channel.pin]["id"] == channel.device_id
        and devices_by_pin[channel.pin]["type"] == "gpio"
        and devices_by_pin[channel.pin]["enabled"] is channel.enabled
        for channel in PLAMP8_CHANNELS
    )


def _is_importable(
    identity: FirmwareIdentity,
    expected_identity: FirmwareIdentity,
    state: dict[str, Any],
) -> bool:
    return identity == expected_identity and _matches_plamp8_profile(state)


def provisioned_plamp8_state(report: Any) -> dict[str, Any]:
    """Map a complete report onto the canonical Plamp8 scheduler state."""
    state, _, _ = _validated_report_state(report)
    devices_by_pin = {device["pin"]: device for device in state["devices"]}
    devices = []
    for channel in PLAMP8_CHANNELS:
        source = devices_by_pin[channel.pin]
        devices.append({
            "id": channel.device_id,
            "type": source["type"],
            "pin": channel.pin,
            "enabled": channel.enabled,
            "current_t": source["current_t"],
            "reschedule": source["reschedule"],
            "pattern": source["pattern"],
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


def _controller_config_from_state(
    pico_serial: str, state: dict[str, Any]
) -> dict[str, Any]:
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


def controller_config_from_report(pico_serial: str, report: Any) -> dict[str, Any]:
    """Convert a validated canonical Plamp8 report without remapping it."""
    state, _, identity = _validated_report_state(report)
    if identity.protocol != EXPECTED_FIRMWARE_PROTOCOL or not _matches_plamp8_profile(state):
        raise ValueError("report does not match the canonical Plamp8 profile")
    return _controller_config_from_state(pico_serial, state)


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
    state, _, observed = _validated_report_state(report)
    action = "import" if _is_importable(observed, expected_identity, state) else "provision"
    before = _report_devices(report)
    after = (
        state["devices"]
        if action == "import"
        else provisioned_plamp8_state(report)["devices"]
    )
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


def _validated_controller_assignment(
    config: dict[str, Any], controller_id: str, pico_serial: str
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
    return controllers


def _merged_controller_config(
    config: dict[str, Any], controller_id: str, pico_serial: str, state: dict[str, Any]
) -> dict[str, Any]:
    controllers = _validated_controller_assignment(config, controller_id, pico_serial)
    imported = _controller_config_from_state(pico_serial, state)
    existing = controllers.get(controller_id)
    if isinstance(existing, dict):
        existing_payload = existing.get("payload")
        preserved_payload = {
            key: value
            for key, value in (
                existing_payload.items() if isinstance(existing_payload, dict) else ()
            )
            if key not in {"devices", "pico_serial"}
        }
        imported["payload"] = {
            **imported["payload"],
            **preserved_payload,
            "pico_serial": pico_serial,
        }
        existing_settings = existing.get("settings")
        preserved_settings = {
            key: value
            for key, value in (
                existing_settings.items() if isinstance(existing_settings, dict) else ()
            )
            if key != "devices"
        }
        imported["settings"] = {
            **preserved_settings,
            "devices": imported["settings"]["devices"],
        }
    updated = dict(config)
    updated_controllers = dict(controllers)
    updated_controllers[controller_id] = imported
    updated["controllers"] = updated_controllers
    return updated


def _upgrade_report(result: dict[str, Any]) -> dict[str, Any]:
    report = result.get("report") if isinstance(result, dict) else None
    if not isinstance(report, dict):
        raise ConfigError("controller provisioning verification report is missing")
    return report


def _validate_safe_path_component(value: str, label: str) -> None:
    if not isinstance(value, str) or not _SAFE_PATH_COMPONENT_RE.fullmatch(value):
        raise ConfigError(f"{label} must be a safe path component")


def _append_error_context(exc: Exception, context: str) -> None:
    if isinstance(exc, OSError) and exc.errno is not None:
        detail = exc.strerror if isinstance(exc.strerror, str) else str(exc)
        exc.strerror = f"{detail}; {context}"
        return
    message = f"{exc}; {context}"
    exc.args = (message, *exc.args[1:]) if exc.args else (message,)


def _annotate_recovery_error(exc: Exception, stage: str, recovery_path: Path) -> None:
    exc.stage = stage
    exc.recovery_path = str(recovery_path)
    _append_error_context(exc, f"stage={stage}; recovery={recovery_path}")


def _next_recovery_path(data_dir: Path, controller_id: str, pico_serial: str) -> Path:
    directory = data_dir / "controller-backups"
    base_name = f"{controller_id}-{pico_serial}-pre-provision"
    candidate = directory / f"{base_name}.json"
    suffix = 2
    while candidate.exists():
        candidate = directory / f"{base_name}-{suffix}.json"
        suffix += 1
    return candidate


def _commit_host_import(
    *,
    config_file: Path,
    data_dir: Path,
    controller_id: str,
    pico_serial: str,
    imported_state: dict[str, Any],
) -> None:
    merged = validate_config(
        _merged_controller_config(
            load_config(config_file), controller_id, pico_serial, imported_state
        )
    )
    timer_path = data_dir / "timers" / f"{controller_id}.json"
    previous_exists = timer_path.exists()
    previous_timer = None
    if previous_exists:
        previous_timer = json.loads(timer_path.read_text(encoding="utf-8"))
    atomic_write_json(timer_path, imported_state)
    try:
        save_config(config_file, merged)
    except Exception as commit_error:
        try:
            if previous_exists:
                atomic_write_json(timer_path, previous_timer)
            else:
                timer_path.unlink(missing_ok=True)
        except Exception as rollback_error:
            _append_error_context(
                commit_error, f"timer rollback failed: {rollback_error}"
            )
        raise


def add_controller(
    controller_id: str,
    pico_serial: str,
    profile_id: str,
    *,
    apply: bool,
    allow_provision: bool,
    expected_action: str | None = None,
    config_file: Path,
    data_dir: Path,
    repo_root: Path,
    lock_dir: Path,
    timeout: float,
    report_func: Callable[..., dict[str, Any]] = request_report,
    upgrade_func: Callable[..., dict[str, Any]] = upgrade_scheduler,
    firmware_revision_func: Callable[[Path], str] = firmware_revision,
) -> dict[str, Any]:
    """Preview or explicitly import a single Plamp8 controller report."""
    if profile_id != "plamp8":
        raise ConfigError(f"unsupported controller profile: {profile_id}")
    _validate_safe_path_component(controller_id, "controller id")
    _validate_safe_path_component(pico_serial, "serial")
    if expected_action not in {None, "import", "provision"}:
        raise ConfigError("expected action must be import or provision")
    expected_revision = firmware_revision_func(repo_root)
    if not isinstance(expected_revision, str) or expected_revision.strip() in {"", "unknown"}:
        raise ConfigError("current generated firmware revision is unavailable")
    expected_identity = FirmwareIdentity(
        "pico_scheduler",
        expected_revision.strip(),
        EXPECTED_FIRMWARE_PROTOCOL,
    )
    report = report_func(pico_serial, lock_dir=lock_dir, timeout=timeout)
    preview = preview_controller_add(controller_id, pico_serial, report, expected_identity)
    if expected_action is not None and preview["action"] != expected_action:
        raise ConfigError(
            "controller action changed since preview: "
            f"expected {expected_action}, now {preview['action']}; preview again"
        )
    if not apply:
        return _result(preview, applied=False, recovery_path=None)
    if preview["action"] == "provision" and not allow_provision:
        raise ConfigError("controller requires explicit --provision")

    imported_state, _, _ = _validated_report_state(report)
    recovery_path = None
    if preview["action"] == "provision":
        planned_state = provisioned_plamp8_state(report)
        # Avoid mutating a controller that cannot be represented in host config.
        with exclusive_lock(lock_dir / "config.lock", timeout=timeout):
            validate_config(
                _merged_controller_config(
                    load_config(config_file), controller_id, pico_serial, planned_state
                )
            )
            recovery_path = _next_recovery_path(data_dir, controller_id, pico_serial)
            atomic_write_json(recovery_path, report)
        try:
            upgraded = upgrade_func(
                pico_serial,
                planned_state,
                lock_dir=lock_dir,
                timeout=timeout,
                repo_root=repo_root,
                data_dir=data_dir,
                inspected_report=report,
            )
        except Exception as exc:
            _annotate_recovery_error(exc, "upgrade", recovery_path)
            raise
        try:
            imported_report = _upgrade_report(upgraded)
            verified_preview = preview_controller_add(
                controller_id, pico_serial, imported_report, expected_identity
            )
            if verified_preview["action"] != "import":
                raise ConfigError("controller provisioning verification failed")
            imported_state, _, _ = _validated_report_state(imported_report)
        except Exception as exc:
            _annotate_recovery_error(exc, "verification", recovery_path)
            raise

    try:
        with exclusive_lock(lock_dir / "config.lock", timeout=timeout):
            _commit_host_import(
                config_file=config_file,
                data_dir=data_dir,
                controller_id=controller_id,
                pico_serial=pico_serial,
                imported_state=imported_state,
            )
    except Exception as exc:
        if recovery_path is not None:
            _annotate_recovery_error(exc, "host-import", recovery_path)
        raise
    return _result(preview, applied=True, recovery_path=recovery_path)
