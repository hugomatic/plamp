"""Validation helpers for the persisted hardware config."""

from __future__ import annotations

from collections.abc import Mapping
import re


_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_EDITORS = {"cycle", "clock_window"}
_CONFIG_KEYS = ("controllers", "devices", "cameras")


def empty_config() -> dict:
    return {key: {} for key in _CONFIG_KEYS}


def _is_valid_id(value: object) -> bool:
    return isinstance(value, str) and bool(_ID_RE.fullmatch(value))


def _as_mapping(value: object, label: str) -> Mapping:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a mapping")
    return value


def validate_controllers(value):
    value = _as_mapping(value, "controllers")
    controllers = {}
    for controller_id, controller_value in value.items():
        if not _is_valid_id(controller_id):
            raise ValueError(f"invalid controller id: {controller_id!r}")
        controller_value = _as_mapping(controller_value, f"controller {controller_id}")
        extra_keys = set(controller_value) - {"pico_serial"}
        if extra_keys:
            raise ValueError(f"controller {controller_id} has unknown keys: {sorted(extra_keys)!r}")
        pico_serial = controller_value.get("pico_serial")
        if pico_serial is not None and (not isinstance(pico_serial, str) or not pico_serial):
            raise ValueError(f"controller {controller_id} pico_serial must be a non-empty string")
        controllers[controller_id] = {}
        if pico_serial is not None:
            controllers[controller_id]["pico_serial"] = pico_serial
    return controllers


def validate_devices(value, controllers):
    value = _as_mapping(value, "devices")
    controllers = validate_controllers(controllers)
    devices = {}
    for device_id, device_value in value.items():
        if not _is_valid_id(device_id):
            raise ValueError(f"invalid device id: {device_id!r}")
        device_value = _as_mapping(device_value, f"device {device_id}")
        extra_keys = set(device_value) - {"controller", "pin", "editor"}
        if extra_keys:
            raise ValueError(f"device {device_id} has unknown keys: {sorted(extra_keys)!r}")
        controller = device_value.get("controller")
        pin = device_value.get("pin")
        editor = device_value.get("editor", "cycle")
        if controller not in controllers:
            raise ValueError(f"device {device_id} references unknown controller: {controller!r}")
        if not isinstance(pin, int) or isinstance(pin, bool) or not 0 <= pin <= 29:
            raise ValueError(f"device {device_id} pin must be an int in 0..29")
        if editor not in _EDITORS:
            raise ValueError(f"device {device_id} editor must be one of {sorted(_EDITORS)!r}")
        devices[device_id] = {
            "controller": controller,
            "pin": pin,
            "editor": editor,
        }
    return devices


def validate_cameras(value):
    value = _as_mapping(value, "cameras")
    cameras = {}
    for camera_id, camera_value in value.items():
        if not _is_valid_id(camera_id):
            raise ValueError(f"invalid camera id: {camera_id!r}")
        camera_value = _as_mapping(camera_value, f"camera {camera_id}")
        if camera_value:
            raise ValueError(f"camera {camera_id} must be empty")
        cameras[camera_id] = {}
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
