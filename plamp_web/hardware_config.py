"""Validation helpers for the persisted hardware config."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import PurePosixPath
import re


_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_SCHEDULE_KINDS = {"cycle", "daily_window", "events"}
_PIN_TYPES = {"gpio", "pwm"}
_CONTROLLER_TYPES = {"pico_scheduler", "pico_doser"}
_DEVICE_TYPES = {"scheduled_output"}
_DEFAULT_CONTROLLER_TYPE = "pico_scheduler"
_DEFAULT_REPORT_EVERY = 10
_CONFIG_KEYS = ("controllers", "cameras")
_RESERVED_CONTROLLER_IDS = {"controllers", "config", "pics", "pico_scheduler", "pico_doser"}
_AUTOFOCUS_MODES = {"auto", "continuous", "manual", "off"}


def empty_config() -> dict:
    return {key: {} for key in _CONFIG_KEYS}


def _is_valid_id(value: object) -> bool:
    return isinstance(value, str) and bool(_ID_RE.fullmatch(value))


def _as_mapping(value: object, label: str) -> Mapping:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a mapping")
    return value


def _optional_label(item: Mapping, label: str) -> str | None:
    value = item.get("label")
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise ValueError(f"{label} label must be a string")
    return value


def _required_positive_int(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{label} must be a positive integer")
    if value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _required_non_negative_int(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{label} must be a non-negative integer")
    if value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def _required_bool(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be a boolean")
    return value


def _optional_repo_relative_path(value: object, label: str) -> str | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    if "\\" in value:
        raise ValueError(f"{label} must be repo-relative")
    path = PurePosixPath(value)
    if path.is_absolute() or path == PurePosixPath(".") or ".." in path.parts:
        raise ValueError(f"{label} must be repo-relative")
    return value


def _optional_name_token(value: object, label: str) -> str | None:
    if value in (None, ""):
        return None
    if not _is_valid_id(value):
        raise ValueError(f"{label} must be a valid id")
    return str(value)


def validate_controllers(value):
    value = _as_mapping(value, "controllers")
    controllers = {}
    for controller_id, controller_value in value.items():
        if not _is_valid_id(controller_id):
            raise ValueError(f"invalid controller id: {controller_id!r}")
        if controller_id in _RESERVED_CONTROLLER_IDS:
            raise ValueError(f"controller id is reserved: {controller_id!r}")
        controller_value = _as_mapping(controller_value, f"controller {controller_id}")
        extra_keys = set(controller_value) - {"type", "config", "settings", "devices"}
        if extra_keys:
            raise ValueError(f"controller {controller_id} has unknown keys: {sorted(extra_keys)!r}")

        controller_type = controller_value.get("type", _DEFAULT_CONTROLLER_TYPE)
        if controller_type not in _CONTROLLER_TYPES:
            raise ValueError(f"controller {controller_id} type must be one of {sorted(_CONTROLLER_TYPES)!r}")

        config = _as_mapping(controller_value.get("config", {}), f"controller {controller_id} config")
        settings = _as_mapping(controller_value.get("settings", {}), f"controller {controller_id} settings")
        extra_config = set(config) - {"pico_serial", "label"}
        if extra_config:
            raise ValueError(f"controller {controller_id} config has unknown keys: {sorted(extra_config)!r}")
        extra_settings = set(settings) - {"report_every"}
        if extra_settings:
            raise ValueError(f"controller {controller_id} settings has unknown keys: {sorted(extra_settings)!r}")
        pico_serial = config.get("pico_serial")
        if pico_serial is not None and (not isinstance(pico_serial, str) or not pico_serial):
            raise ValueError(f"controller {controller_id} pico_serial must be a non-empty string")
        label = _optional_label(config, f"controller {controller_id}")
        controller = {"type": controller_type, "config": {}, "settings": {}}
        if controller_type == "pico_scheduler":
            controller["settings"]["report_every"] = _required_positive_int(
                settings.get("report_every", _DEFAULT_REPORT_EVERY),
                f"controller {controller_id} report_every",
            )
        elif "report_every" in settings:
            raise ValueError(f"controller {controller_id} report_every is only valid for pico_scheduler")
        if pico_serial is not None:
            controller["config"]["pico_serial"] = pico_serial
        if label:
            controller["config"]["label"] = label
        controller["devices"] = validate_controller_devices(
            controller_value.get("devices", {}),
            controller_id,
            controller_type,
        )
        controllers[controller_id] = controller
    return controllers


def controller_type(controller: Mapping) -> str:
    value = controller.get("type", _DEFAULT_CONTROLLER_TYPE)
    return str(value)


def scheduler_controller_ids(controllers) -> set[str]:
    controllers = _as_mapping(controllers, "controllers")
    return {
        controller_id
        for controller_id, controller_value in controllers.items()
        if isinstance(controller_id, str)
        and isinstance(controller_value, Mapping)
        and controller_type(controller_value) == "pico_scheduler"
    }


def _validate_schedule(value: object, label: str) -> dict:
    value = _as_mapping(value, label)
    kind = value.get("kind", "cycle")
    if kind not in _SCHEDULE_KINDS:
        raise ValueError(f"{label} kind must be one of {sorted(_SCHEDULE_KINDS)!r}")
    schedule = {"kind": kind}
    if kind == "cycle":
        schedule["on_seconds"] = _required_positive_int(value.get("on_seconds", 1), f"{label} on_seconds")
        schedule["off_seconds"] = _required_positive_int(value.get("off_seconds", 1), f"{label} off_seconds")
        schedule["start_at_seconds"] = _required_non_negative_int(
            value.get("start_at_seconds", 0), f"{label} start_at_seconds"
        )
    elif kind == "daily_window":
        for key in ("on_time", "off_time"):
            raw = value.get(key)
            if not isinstance(raw, str) or not raw:
                raise ValueError(f"{label} {key} must be a non-empty string")
            schedule[key] = raw
    else:
        events = value.get("events", [])
        if not isinstance(events, list):
            raise ValueError(f"{label} events must be a list")
        schedule["events"] = events
    return schedule


def validate_controller_devices(value, controller_id: str, controller_type: str):
    value = _as_mapping(value, f"controller {controller_id} devices")
    if controller_type != "pico_scheduler" and value:
        raise ValueError(f"controller {controller_id} devices are only valid for pico_scheduler")
    devices = {}
    used_pins = set()
    for device_id, device_value in value.items():
        if not _is_valid_id(device_id):
            raise ValueError(f"invalid device id: {device_id!r}")
        device_value = _as_mapping(device_value, f"device {device_id}")
        extra_keys = set(device_value) - {"type", "config", "settings"}
        if extra_keys:
            raise ValueError(f"device {device_id} has unknown keys: {sorted(extra_keys)!r}")
        device_type = device_value.get("type")
        if device_type not in _DEVICE_TYPES:
            raise ValueError(f"device {device_id} type must be one of {sorted(_DEVICE_TYPES)!r}")
        config = _as_mapping(device_value.get("config", {}), f"device {device_id} config")
        settings = _as_mapping(device_value.get("settings", {}), f"device {device_id} settings")
        extra_config = set(config) - {"label", "pin", "output_type", "icon", "display_order", "visibility"}
        if extra_config:
            raise ValueError(f"device {device_id} config has unknown keys: {sorted(extra_config)!r}")
        extra_settings = set(settings) - {"programming", "schedule"}
        if extra_settings:
            raise ValueError(f"device {device_id} settings has unknown keys: {sorted(extra_settings)!r}")
        pin = config.get("pin")
        pin_type = config.get("output_type", "gpio")
        programming = settings.get("programming", "enabled")
        visibility = config.get("visibility", "visible")
        if not isinstance(pin, int) or isinstance(pin, bool) or not 0 <= pin <= 29:
            raise ValueError(f"device {device_id} pin must be an int in 0..29")
        if pin_type not in _PIN_TYPES:
            raise ValueError(f"device {device_id} output_type must be one of {sorted(_PIN_TYPES)!r}")
        if programming not in {"enabled", "disabled"}:
            raise ValueError(f"device {device_id} programming must be enabled or disabled")
        if visibility not in {"visible", "hidden"}:
            raise ValueError(f"device {device_id} visibility must be visible or hidden")
        pin_key = pin
        if pin_key in used_pins:
            raise ValueError(f"device {device_id} uses duplicate pin {pin} for controller {controller_id}")
        used_pins.add(pin_key)
        label = _optional_label(config, f"device {device_id}")
        display_order = _required_non_negative_int(config.get("display_order", len(devices)), f"device {device_id} display_order")
        devices[device_id] = {
            "type": device_type,
            "config": {
                "pin": pin,
                "output_type": pin_type,
                "display_order": display_order,
                "visibility": visibility,
            },
            "settings": {
                "programming": programming,
                "schedule": _validate_schedule(settings.get("schedule", {}), f"device {device_id} schedule"),
            },
        }
        if label:
            devices[device_id]["config"]["label"] = label
        icon = config.get("icon")
        if icon is not None:
            if not isinstance(icon, str) or not icon:
                raise ValueError(f"device {device_id} icon must be a non-empty string")
            devices[device_id]["config"]["icon"] = icon
    return devices


def validate_devices(value, controllers):
    raise ValueError("top-level devices are no longer supported; nest devices under controllers")


def validate_cameras(value):
    value = _as_mapping(value, "cameras")
    cameras = {}
    for camera_id, camera_value in value.items():
        if not _is_valid_id(camera_id):
            raise ValueError(f"invalid camera id: {camera_id!r}")
        camera_value = _as_mapping(camera_value, f"camera {camera_id}")
        extra_keys = set(camera_value) - {
            "label",
            "detected_key",
            "capture_dir",
            "enabled",
            "auto_enabled",
            "capture_every_seconds",
            "manual_prefix",
            "auto_prefix",
            "autofocus_mode",
            "autofocus_delay_ms",
        }
        if extra_keys:
            raise ValueError(f"camera {camera_id} has unknown keys: {sorted(extra_keys)!r}")
        label = _optional_label(camera_value, f"camera {camera_id}")
        detected_key = camera_value.get("detected_key")
        if detected_key in (None, ""):
            detected_key = None
        elif not _is_valid_id(detected_key):
            raise ValueError(f"camera {camera_id} detected_key must be a valid id")
        capture_dir = _optional_repo_relative_path(camera_value.get("capture_dir"), f"camera {camera_id} capture_dir")
        enabled = None
        if "enabled" in camera_value:
            enabled = _required_bool(camera_value.get("enabled"), f"camera {camera_id} enabled")
        auto_enabled = None
        if "auto_enabled" in camera_value:
            auto_enabled = _required_bool(camera_value.get("auto_enabled"), f"camera {camera_id} auto_enabled")
        capture_every_seconds = None
        if "capture_every_seconds" in camera_value:
            capture_every_seconds = _required_non_negative_int(
                camera_value.get("capture_every_seconds"), f"camera {camera_id} capture_every_seconds"
            )
        # Backward-compat for legacy camera toggles:
        # `enabled=false` or `auto_enabled=false` maps to capture_every_seconds=0.
        if enabled is False or auto_enabled is False:
            capture_every_seconds = 0
        if auto_enabled is True and capture_every_seconds is None:
            raise ValueError(f"camera {camera_id} capture_every_seconds is required when auto_enabled is true")
        if capture_every_seconds is not None and capture_every_seconds > 0 and capture_dir is None:
            raise ValueError(f"camera {camera_id} capture_dir is required when capture_every_seconds is greater than 0")
        if "manual_prefix" in camera_value and camera_value.get("manual_prefix") == "":
            raise ValueError(f"camera {camera_id} manual_prefix must be a valid id")
        if "auto_prefix" in camera_value and camera_value.get("auto_prefix") == "":
            raise ValueError(f"camera {camera_id} auto_prefix must be a valid id")
        manual_prefix = _optional_name_token(camera_value.get("manual_prefix"), f"camera {camera_id} manual_prefix")
        auto_prefix = _optional_name_token(camera_value.get("auto_prefix"), f"camera {camera_id} auto_prefix")
        autofocus_mode = camera_value.get("autofocus_mode")
        if autofocus_mode not in (None, ""):
            if not isinstance(autofocus_mode, str) or autofocus_mode not in _AUTOFOCUS_MODES:
                raise ValueError(f"camera {camera_id} autofocus_mode must be one of {sorted(_AUTOFOCUS_MODES)!r}")
        else:
            autofocus_mode = None
        autofocus_delay_ms = camera_value.get("autofocus_delay_ms")
        if autofocus_delay_ms in (None, ""):
            autofocus_delay_ms = None
        elif not isinstance(autofocus_delay_ms, int) or isinstance(autofocus_delay_ms, bool) or autofocus_delay_ms < 0:
            raise ValueError(f"camera {camera_id} autofocus_delay_ms must be a non-negative integer")
        cameras[camera_id] = {}
        if label:
            cameras[camera_id]["label"] = label
        if detected_key:
            cameras[camera_id]["detected_key"] = detected_key
        if capture_dir is not None:
            cameras[camera_id]["capture_dir"] = capture_dir
        if capture_every_seconds is not None:
            cameras[camera_id]["capture_every_seconds"] = capture_every_seconds
        if manual_prefix is not None:
            cameras[camera_id]["manual_prefix"] = manual_prefix
        if auto_prefix is not None:
            cameras[camera_id]["auto_prefix"] = auto_prefix
        if autofocus_mode is not None:
            cameras[camera_id]["autofocus_mode"] = autofocus_mode
        if autofocus_delay_ms is not None:
            cameras[camera_id]["autofocus_delay_ms"] = autofocus_delay_ms
    return cameras


def config_view(config):
    config = _as_mapping(config, "config")
    if "devices" in config:
        raise ValueError("top-level devices are no longer supported; nest devices under controllers")
    controllers = validate_controllers(config.get("controllers", {}))
    return {
        "controllers": controllers,
        "cameras": validate_cameras(config.get("cameras", {})),
    }


def apply_config_section(config, section, value):
    config = config_view(config)
    if section == "controllers":
        config["controllers"] = validate_controllers(value)
    elif section == "cameras":
        config["cameras"] = validate_cameras(value)
    else:
        raise ValueError(f"unknown section: {section!r}")
    return config


def runtime_controller_serials(config):
    controllers = config_view(config)["controllers"]
    return {
        controller_id: controller_value["config"]["pico_serial"]
        for controller_id, controller_value in controllers.items()
        if "pico_serial" in controller_value["config"]
    }


def scheduler_devices_for_controller(config, controller_id: str) -> dict:
    controller = config_view(config)["controllers"].get(controller_id, {})
    if controller_type(controller) != "pico_scheduler":
        return {}
    return controller.get("devices", {})



def hardware_view(config):
    return config_view(config)


def apply_hardware_section(config, section, value):
    return apply_config_section(config, section, value)
