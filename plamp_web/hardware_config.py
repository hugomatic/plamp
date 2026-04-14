from __future__ import annotations

import copy
import re
from typing import Any

CONTROLLER_TYPES = {"pico_scheduler", "food_dispenser", "ph_dispenser"}
DEVICE_TYPES = {"gpio"}
DEFAULT_EDITORS = {"cycle", "clock_window"}
IR_FILTERS = {"unknown", "normal", "noir"}
ROLE_RE = re.compile(r"^[A-Za-z0-9_-]+$")
DEVICE_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def controller_key(role: str) -> str:
    return f"controller:{role}"


def empty_hardware() -> dict[str, Any]:
    return {"controllers": {}, "devices": {}, "cameras": {}}


def hardware_config_from_timers(config: dict[str, Any]) -> dict[str, Any]:
    hardware = empty_hardware()
    for timer in config.get("timers", []):
        if not isinstance(timer, dict):
            continue
        role = timer.get("role")
        serial = timer.get("pico_serial")
        if not isinstance(role, str) or not isinstance(serial, str) or not role or not serial:
            continue
        key = controller_key(role)
        hardware["controllers"][key] = {"name": role, "type": "pico_scheduler", "match": {"pico_serial": serial}}
        for channel in timer.get("channels", []):
            if not isinstance(channel, dict):
                continue
            device_id = channel.get("id")
            pin = channel.get("pin")
            if not isinstance(device_id, str) or not isinstance(pin, int):
                continue
            hardware["devices"][device_id] = {
                "name": str(channel.get("name") or device_id),
                "type": str(channel.get("type") or "gpio"),
                "controller": key,
                "pin": pin,
                "default_editor": str(channel.get("default_editor") or "cycle"),
            }
    return hardware


def hardware_view(config: dict[str, Any]) -> dict[str, Any]:
    hardware = config.get("hardware")
    if isinstance(hardware, dict):
        return {
            "controllers": dict(hardware.get("controllers") or {}),
            "devices": dict(hardware.get("devices") or {}),
            "cameras": dict(hardware.get("cameras") or {}),
        }
    return hardware_config_from_timers(config)


def validate_controllers(controllers: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(controllers, dict):
        raise ValueError("controllers must be an object")
    result = {}
    seen_names = set()
    for key, item in controllers.items():
        if not isinstance(key, str) or not key.startswith("controller:"):
            raise ValueError("controller keys must be controller:<role>")
        if not isinstance(item, dict):
            raise ValueError(f"controller {key} must be an object")
        name = item.get("name")
        controller_type = item.get("type")
        match = item.get("match") if isinstance(item.get("match"), dict) else {}
        pico_serial = match.get("pico_serial")
        if pico_serial is not None and not isinstance(pico_serial, str):
            raise ValueError(f"controller {key} has invalid pico_serial")
        if not isinstance(name, str) or not name or not ROLE_RE.match(name):
            raise ValueError(f"controller {key} has invalid name")
        if name in seen_names:
            raise ValueError(f"duplicate controller name: {name}")
        if controller_type not in CONTROLLER_TYPES:
            raise ValueError(f"controller {key} has unsupported type")
        seen_names.add(name)
        result[key] = {"name": name, "type": controller_type, "match": {"pico_serial": pico_serial}}
    return result


def validate_devices(devices: Any, controllers: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if not isinstance(devices, dict):
        raise ValueError("devices must be an object")
    result = {}
    for key, item in devices.items():
        if not isinstance(key, str) or not DEVICE_ID_RE.match(key):
            raise ValueError("device ids must use letters, numbers, underscore, or dash")
        if not isinstance(item, dict):
            raise ValueError(f"device {key} must be an object")
        name = item.get("name")
        device_type = item.get("type")
        controller = item.get("controller")
        pin = item.get("pin")
        default_editor = item.get("default_editor", "cycle")
        if not isinstance(name, str) or not name:
            raise ValueError(f"device {key} has invalid name")
        if device_type not in DEVICE_TYPES:
            raise ValueError(f"device {key} has unsupported type")
        if controller not in controllers:
            raise ValueError(f"device {key} references unknown controller")
        if not isinstance(pin, int) or pin < 0 or pin > 29:
            raise ValueError(f"device {key} has invalid pin")
        if default_editor not in DEFAULT_EDITORS:
            raise ValueError(f"device {key} has unsupported default_editor")
        result[key] = {"name": name, "type": device_type, "controller": controller, "pin": pin, "default_editor": default_editor}
    return result


def validate_cameras(cameras: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(cameras, dict):
        raise ValueError("cameras must be an object")
    result = {}
    for key, item in cameras.items():
        if not isinstance(key, str) or not key.startswith("rpicam:"):
            raise ValueError("camera keys must be rpicam:cam0 or rpicam:cam1")
        if not isinstance(item, dict):
            raise ValueError(f"camera {key} must be an object")
        name = item.get("name")
        ir_filter = item.get("ir_filter", "unknown")
        if not isinstance(name, str) or not name:
            raise ValueError(f"camera {key} has invalid name")
        if ir_filter not in IR_FILTERS:
            raise ValueError(f"camera {key} has unsupported ir_filter")
        result[key] = {"name": name, "ir_filter": ir_filter}
    return result


def apply_hardware_section(config: dict[str, Any], section: str, value: Any) -> dict[str, Any]:
    updated = copy.deepcopy(config)
    hardware = hardware_view(updated)
    if section == "controllers":
        hardware["controllers"] = validate_controllers(value)
        hardware["devices"] = validate_devices(hardware.get("devices", {}), hardware["controllers"])
    elif section == "devices":
        hardware["devices"] = validate_devices(value, hardware.get("controllers", {}))
    elif section == "cameras":
        hardware["cameras"] = validate_cameras(value)
    else:
        raise ValueError(f"unknown hardware section: {section}")
    updated["hardware"] = hardware
    return project_timers_from_hardware(updated)


def project_timers_from_hardware(config: dict[str, Any]) -> dict[str, Any]:
    hardware = hardware_view(config)
    timers = []
    for controller_key, controller in sorted(hardware.get("controllers", {}).items(), key=lambda item: item[1]["name"]):
        if controller.get("type") != "pico_scheduler":
            continue
        channels = []
        for device_id, device in sorted(hardware.get("devices", {}).items()):
            if device.get("controller") != controller_key:
                continue
            channels.append({"id": device_id, "name": device["name"], "pin": device["pin"], "type": device["type"], "default_editor": device["default_editor"]})
        pico_serial = (controller.get("match") or {}).get("pico_serial")
        if not pico_serial:
            continue
        timers.append({"role": controller["name"], "pico_serial": pico_serial, "channels": channels})
    result = copy.deepcopy(config)
    result["hardware"] = hardware
    result["timers"] = timers
    return result
