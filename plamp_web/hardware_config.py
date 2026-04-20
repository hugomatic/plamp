"""Validation helpers for the persisted hardware config."""

from __future__ import annotations

from collections.abc import Mapping
import re


_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_EDITORS = {"cycle", "clock_window"}
_PIN_TYPES = {"gpio", "pwm"}
_CONTROLLER_TYPES = {"pico_scheduler"}
_DEFAULT_CONTROLLER_TYPE = "pico_scheduler"
_DEFAULT_REPORT_EVERY = 10
_CONFIG_KEYS = ("controllers", "devices", "cameras")


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


def validate_controllers(value):
    value = _as_mapping(value, "controllers")
    controllers = {}
    for controller_id, controller_value in value.items():
        if not _is_valid_id(controller_id):
            raise ValueError(f"invalid controller id: {controller_id!r}")
        controller_value = _as_mapping(controller_value, f"controller {controller_id}")
        extra_keys = set(controller_value) - {"pico_serial", "label", "type", "report_every"}
        if extra_keys:
            raise ValueError(f"controller {controller_id} has unknown keys: {sorted(extra_keys)!r}")

        controller_type = controller_value.get("type", _DEFAULT_CONTROLLER_TYPE)
        if controller_type not in _CONTROLLER_TYPES:
            raise ValueError(f"controller {controller_id} type must be one of {sorted(_CONTROLLER_TYPES)!r}")

        pico_serial = controller_value.get("pico_serial")
        if pico_serial is not None and (not isinstance(pico_serial, str) or not pico_serial):
            raise ValueError(f"controller {controller_id} pico_serial must be a non-empty string")
        label = _optional_label(controller_value, f"controller {controller_id}")
        controller = {"type": controller_type}
        if controller_type == "pico_scheduler":
            controller["report_every"] = _required_positive_int(
                controller_value.get("report_every", _DEFAULT_REPORT_EVERY),
                f"controller {controller_id} report_every",
            )
        elif "report_every" in controller_value:
            raise ValueError(f"controller {controller_id} report_every is only valid for pico_scheduler")
        if pico_serial is not None:
            controller["pico_serial"] = pico_serial
        if label:
            controller["label"] = label
        controllers[controller_id] = controller
    return controllers


def validate_devices(value, controllers):
    value = _as_mapping(value, "devices")
    controllers = validate_controllers(controllers)
    devices = {}
    used_pins = set()
    for device_id, device_value in value.items():
        if not _is_valid_id(device_id):
            raise ValueError(f"invalid device id: {device_id!r}")
        device_value = _as_mapping(device_value, f"device {device_id}")
        extra_keys = set(device_value) - {"controller", "pin", "type", "editor", "label"}
        if extra_keys:
            raise ValueError(f"device {device_id} has unknown keys: {sorted(extra_keys)!r}")
        controller = device_value.get("controller")
        pin = device_value.get("pin")
        pin_type = device_value.get("type", "gpio")
        editor = device_value.get("editor", "cycle")
        if controller not in controllers:
            raise ValueError(f"device {device_id} references unknown controller: {controller!r}")
        if not isinstance(pin, int) or isinstance(pin, bool) or not 0 <= pin <= 29:
            raise ValueError(f"device {device_id} pin must be an int in 0..29")
        if pin_type not in _PIN_TYPES:
            raise ValueError(f"device {device_id} type must be one of {sorted(_PIN_TYPES)!r}")
        if editor not in _EDITORS:
            raise ValueError(f"device {device_id} editor must be one of {sorted(_EDITORS)!r}")
        pin_key = (controller, pin)
        if pin_key in used_pins:
            raise ValueError(f"device {device_id} uses duplicate pin {pin} for controller {controller}")
        used_pins.add(pin_key)
        label = _optional_label(device_value, f"device {device_id}")
        devices[device_id] = {
            "controller": controller,
            "pin": pin,
            "type": pin_type,
            "editor": editor,
        }
        if label:
            devices[device_id]["label"] = label
    return devices


def validate_cameras(value):
    value = _as_mapping(value, "cameras")
    cameras = {}
    for camera_id, camera_value in value.items():
        if not _is_valid_id(camera_id):
            raise ValueError(f"invalid camera id: {camera_id!r}")
        camera_value = _as_mapping(camera_value, f"camera {camera_id}")
        extra_keys = set(camera_value) - {"label", "detected_key"}
        if extra_keys:
            raise ValueError(f"camera {camera_id} has unknown keys: {sorted(extra_keys)!r}")
        label = _optional_label(camera_value, f"camera {camera_id}")
        detected_key = camera_value.get("detected_key")
        if detected_key in (None, ""):
            detected_key = None
        elif not _is_valid_id(detected_key):
            raise ValueError(f"camera {camera_id} detected_key must be a valid id")
        cameras[camera_id] = {}
        if label:
            cameras[camera_id]["label"] = label
        if detected_key:
            cameras[camera_id]["detected_key"] = detected_key
    return cameras


def config_view(config):
    config = _as_mapping(config, "config")
    controllers = validate_controllers(config.get("controllers", {}))
    return {
        "controllers": controllers,
        "devices": validate_devices(config.get("devices", {}), controllers),
        "cameras": validate_cameras(config.get("cameras", {})),
    }


def apply_config_section(config, section, value):
    config = config_view(config)
    if section == "controllers":
        config["controllers"] = validate_controllers(value)
        config["devices"] = validate_devices(config["devices"], config["controllers"])
    elif section == "devices":
        config["devices"] = validate_devices(value, config["controllers"])
    elif section == "cameras":
        config["cameras"] = validate_cameras(value)
    else:
        raise ValueError(f"unknown section: {section!r}")
    return config


def runtime_controller_serials(config):
    controllers = config_view(config)["controllers"]
    return {
        controller_id: controller_value["pico_serial"]
        for controller_id, controller_value in controllers.items()
        if "pico_serial" in controller_value
    }



def hardware_view(config):
    return config_view(config)


def apply_hardware_section(config, section, value):
    return apply_config_section(config, section, value)
