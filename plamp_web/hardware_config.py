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
        extra_keys = set(controller_value) - {"type", "payload", "config", "settings", "devices"}
        if extra_keys:
            raise ValueError(f"controller {controller_id} has unknown keys: {sorted(extra_keys)!r}")

        controller_type = controller_value.get("type", _DEFAULT_CONTROLLER_TYPE)
        if controller_type not in _CONTROLLER_TYPES:
            raise ValueError(f"controller {controller_id} type must be one of {sorted(_CONTROLLER_TYPES)!r}")

        payload = _as_mapping(controller_value.get("payload", {}), f"controller {controller_id} payload")
        config = _as_mapping(controller_value.get("config", {}), f"controller {controller_id} config")
        settings = _as_mapping(controller_value.get("settings", {}), f"controller {controller_id} settings")
        extra_config = set(config) - {"pico_serial", "label"}
        if extra_config:
            raise ValueError(f"controller {controller_id} config has unknown keys: {sorted(extra_config)!r}")
        extra_settings = set(settings) - {"report_every", "devices", "label"}
        if extra_settings:
            raise ValueError(f"controller {controller_id} settings has unknown keys: {sorted(extra_settings)!r}")
        pico_serial = payload.get("pico_serial", config.get("pico_serial"))
        if pico_serial is not None and (not isinstance(pico_serial, str) or not pico_serial):
            raise ValueError(f"controller {controller_id} pico_serial must be a non-empty string")
        legacy_label = _optional_label(config, f"controller {controller_id}")
        settings_label = _optional_label(settings, f"controller {controller_id}")
        if controller_type == "pico_scheduler":
            if "devices" in settings:
                semantic_devices = _validate_semantic_devices(settings["devices"], controller_id)
                legacy_devices = None
            else:
                legacy_devices = validate_controller_devices(
                    controller_value.get("devices", {}),
                    controller_id,
                    "pico_scheduler",
                )
                semantic_devices = _semantic_devices_from_legacy(legacy_devices)
            controller = {
                "type": controller_type,
                "payload": {
                    "report_every": _required_positive_int(
                        payload.get("report_every", settings.get("report_every", _DEFAULT_REPORT_EVERY)),
                        f"controller {controller_id} report_every",
                    ),
                    "devices": _scheduler_payload_devices(payload.get("devices"), semantic_devices, legacy_devices, controller_id),
                },
                "settings": {"devices": semantic_devices},
            }
            label = settings_label or legacy_label
            if label:
                controller["settings"]["label"] = label
            if pico_serial is not None:
                controller["payload"]["pico_serial"] = pico_serial
        else:
            controller = {"type": controller_type, "config": {}, "settings": {}, "devices": {}}
            if payload:
                raise ValueError(f"controller {controller_id} payload is only valid for pico_scheduler")
            if settings_label:
                raise ValueError(f"controller {controller_id} settings label is only valid for pico_scheduler")
            if "devices" in settings:
                raise ValueError(f"controller {controller_id} settings devices are only valid for pico_scheduler")
            if controller_value.get("devices", {}):
                validate_controller_devices(
                    controller_value.get("devices", {}),
                    controller_id,
                    controller_type,
                )
            if pico_serial is not None:
                controller["config"]["pico_serial"] = pico_serial
            if legacy_label:
                controller["config"]["label"] = legacy_label
        if controller_type != "pico_scheduler" and "report_every" in settings:
            raise ValueError(f"controller {controller_id} report_every is only valid for pico_scheduler")
        controllers[controller_id] = controller
    return controllers


def _semantic_devices_from_legacy(legacy_devices: Mapping) -> dict:
    devices = {}
    for device_id, device in legacy_devices.items():
        config = device["config"]
        settings = device["settings"]
        devices[device_id] = {
            "pin": config["pin"],
            "output_type": config["output_type"],
            "display_order": config["display_order"],
            "visibility": config["visibility"],
            "programming": settings["programming"],
            "editor": settings["schedule"],
        }
        for key in ("label", "icon"):
            if key in config:
                devices[device_id][key] = config[key]
    return devices


def _validate_semantic_devices(value: object, controller_id: str) -> dict:
    value = _as_mapping(value, f"controller {controller_id} settings devices")
    devices = {}
    used_pins = set()
    for device_id, device_value in value.items():
        if not _is_valid_id(device_id):
            raise ValueError(f"invalid device id: {device_id!r}")
        device_value = _as_mapping(device_value, f"device {device_id}")
        extra_keys = set(device_value) - {"pin", "label", "icon", "display_order", "visibility", "programming", "editor", "output_type"}
        if extra_keys:
            raise ValueError(f"device {device_id} has unknown keys: {sorted(extra_keys)!r}")
        pin = device_value.get("pin")
        if not isinstance(pin, int) or isinstance(pin, bool) or not 0 <= pin <= 29:
            raise ValueError(f"device {device_id} pin must be an int in 0..29")
        if pin in used_pins:
            raise ValueError(f"device {device_id} uses duplicate pin {pin} for controller {controller_id}")
        used_pins.add(pin)
        visibility = device_value.get("visibility", "visible")
        programming = device_value.get("programming", "enabled")
        output_type = device_value.get("output_type", "gpio")
        if visibility not in {"visible", "hidden"}:
            raise ValueError(f"device {device_id} visibility must be visible or hidden")
        if programming not in {"enabled", "disabled"}:
            raise ValueError(f"device {device_id} programming must be enabled or disabled")
        if output_type not in _PIN_TYPES:
            raise ValueError(f"device {device_id} output_type must be one of {sorted(_PIN_TYPES)!r}")
        devices[device_id] = {
            "pin": pin,
            "output_type": output_type,
            "display_order": _required_non_negative_int(
                device_value.get("display_order", len(devices)),
                f"device {device_id} display_order",
            ),
            "visibility": visibility,
            "programming": programming,
            "editor": _validate_schedule(device_value.get("editor", {}), f"device {device_id} editor"),
        }
        label = _optional_label(device_value, f"device {device_id}")
        if label:
            devices[device_id]["label"] = label
        icon = device_value.get("icon")
        if icon is not None:
            if not isinstance(icon, str) or not icon:
                raise ValueError(f"device {device_id} icon must be a non-empty string")
            devices[device_id]["icon"] = icon
    return devices


def _scheduler_payload_devices(
    value: object,
    semantic_devices: Mapping,
    legacy_devices: Mapping | None,
    controller_id: str,
) -> list[dict]:
    if value is not None:
        if not isinstance(value, list):
            raise ValueError(f"controller {controller_id} payload devices must be a list")
        devices = [_validate_payload_device(device, controller_id) for device in value]
        _validate_payload_pins_match_settings(devices, semantic_devices, controller_id)
        return devices
    if legacy_devices is not None:
        return [_compile_legacy_payload_device(device) for device in legacy_devices.values()]
    return [_compile_payload_device(device) for device in semantic_devices.values()]


def _validate_payload_pins_match_settings(payload_devices: list[dict], semantic_devices: Mapping, controller_id: str) -> None:
    payload_pins = []
    for device in payload_devices:
        pin = device["pin"]
        if pin in payload_pins:
            raise ValueError(f"controller {controller_id} has duplicate payload pin {pin}")
        payload_pins.append(pin)
    semantic_pins = {device["pin"] for device in semantic_devices.values()}
    if set(payload_pins) != semantic_pins:
        raise ValueError(f"controller {controller_id} payload devices pins must match settings devices pins")


def _validate_payload_device(value: object, controller_id: str) -> dict:
    value = _as_mapping(value, f"controller {controller_id} payload device")
    extra_keys = set(value) - {"pin", "type", "pattern"}
    if extra_keys:
        raise ValueError(f"controller {controller_id} payload device has unknown keys: {sorted(extra_keys)!r}")
    pin = value.get("pin")
    output_type = value.get("type")
    pattern = value.get("pattern")
    if not isinstance(pin, int) or isinstance(pin, bool) or not 0 <= pin <= 29:
        raise ValueError(f"controller {controller_id} payload device pin must be an int in 0..29")
    if output_type not in _PIN_TYPES:
        raise ValueError(f"controller {controller_id} payload device type must be one of {sorted(_PIN_TYPES)!r}")
    if not isinstance(pattern, list):
        raise ValueError(f"controller {controller_id} payload device pattern must be a list")
    return {"pin": pin, "type": output_type, "pattern": pattern}


def _compile_payload_device(device: Mapping) -> dict:
    editor = device["editor"]
    output = {
        "pin": device["pin"],
        "type": device.get("output_type", "gpio"),
    }
    if editor["kind"] == "cycle":
        output["pattern"] = [
            {"val": 1, "dur": editor["on_seconds"]},
            {"val": 0, "dur": editor["off_seconds"]},
        ]
    elif editor["kind"] == "daily_window":
        on_seconds = _clock_seconds(editor["on_time"])
        off_seconds = _clock_seconds(editor["off_time"])
        on_duration = (off_seconds - on_seconds) % (24 * 60 * 60)
        output["pattern"] = [
            {"val": 1, "dur": on_duration},
            {"val": 0, "dur": (24 * 60 * 60) - on_duration},
        ]
    else:
        output["pattern"] = list(editor["events"])
    return output


def _compile_legacy_payload_device(device: Mapping) -> dict:
    semantic_device = {
        "pin": device["config"]["pin"],
        "output_type": device["config"]["output_type"],
        "editor": device["settings"]["schedule"],
    }
    return _compile_payload_device(semantic_device)


def _clock_seconds(value: str) -> int:
    parts = value.split(":")
    if len(parts) not in {2, 3}:
        raise ValueError("clock time must use HH:MM or HH:MM:SS")
    hour, minute, second = (int(part) for part in (*parts, "0")[:3])
    return hour * 3600 + minute * 60 + second


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
        unit = value.get("unit")
        if unit in {"seconds", "minutes", "hours"}:
            schedule["unit"] = unit
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


def _migrate_legacy_config(config: Mapping) -> dict:
    """Normalize older persisted config shapes before strict validation."""
    controllers = {}
    for controller_id, controller_value in _as_mapping(config.get("controllers", {}), "controllers").items():
        controller_value = dict(_as_mapping(controller_value, f"controller {controller_id}"))
        controller_config = dict(_as_mapping(controller_value.get("config", {}), f"controller {controller_id} config"))
        controller_settings = dict(_as_mapping(controller_value.get("settings", {}), f"controller {controller_id} settings"))
        if "pico_serial" in controller_value:
            controller_config.setdefault("pico_serial", controller_value.pop("pico_serial"))
        if "label" in controller_value:
            controller_config.setdefault("label", controller_value.pop("label"))
        if "report_every" in controller_value:
            controller_settings.setdefault("report_every", controller_value.pop("report_every"))
        if controller_config:
            controller_value["config"] = controller_config
        if controller_settings:
            controller_value["settings"] = controller_settings
        controllers[controller_id] = controller_value

    for device_id, device_value in _as_mapping(config.get("devices", {}), "devices").items():
        device_value = _as_mapping(device_value, f"device {device_id}")
        controller_id = device_value.get("controller")
        if not _is_valid_id(controller_id) or controller_id not in controllers:
            raise ValueError(f"legacy device {device_id} references unknown controller {controller_id!r}")
        controller = controllers[controller_id]
        controller_devices = dict(_as_mapping(controller.get("devices", {}), f"controller {controller_id} devices"))
        if device_id in controller_devices:
            raise ValueError(f"legacy device {device_id} duplicates controller device")
        editor = device_value.get("editor", "cycle")
        visibility = "hidden" if editor == "hidden" else "visible"
        programming = "disabled" if editor in {"disabled", "hidden"} else "enabled"
        schedule = {"kind": "daily_window", "on_time": "06:00", "off_time": "18:00"} if editor == "clock_window" else {"kind": "cycle"}
        device_config = {
            "pin": device_value.get("pin"),
            "output_type": device_value.get("type", "gpio"),
            "display_order": len(controller_devices),
            "visibility": visibility,
        }
        label = _optional_label(device_value, f"device {device_id}")
        if label:
            device_config["label"] = label
        icon = device_value.get("icon")
        if icon is not None:
            device_config["icon"] = icon
        controller_devices[device_id] = {
            "type": "scheduled_output",
            "config": device_config,
            "settings": {"programming": programming, "schedule": schedule},
        }
        controller["devices"] = controller_devices

    return {
        "controllers": controllers,
        "cameras": config.get("cameras", {}),
    }


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
    config = _migrate_legacy_config(config)
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
        controller_id: controller_value["payload"]["pico_serial"]
        for controller_id, controller_value in controllers.items()
        if "payload" in controller_value and "pico_serial" in controller_value["payload"]
    }


def scheduler_devices_for_controller(config, controller_id: str) -> dict:
    controller = config_view(config)["controllers"].get(controller_id, {})
    if controller_type(controller) != "pico_scheduler":
        return {}
    return controller.get("settings", {}).get("devices", {})



def hardware_view(config):
    return config_view(config)


def apply_hardware_section(config, section, value):
    return apply_config_section(config, section, value)
