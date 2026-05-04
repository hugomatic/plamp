from __future__ import annotations

import re
from datetime import datetime, time
from typing import Any

CLOCK_DAY_SECONDS = 24 * 60 * 60
CLOCK_TIME_RE = re.compile(r"^(\d{2}):(\d{2})(?::(\d{2}))?$")


def _as_int(value: Any, field: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an integer") from exc


def _devices_by_pin(devices: list[dict[str, Any]] | None) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    for device in devices or []:
        if not isinstance(device, dict):
            continue
        try:
            pin = int(device.get("pin"))
        except (TypeError, ValueError):
            continue
        if 0 <= pin <= 29:
            result[pin] = device
    return result


def channel_metadata_for_role(role: str, config: dict[str, Any], state: dict[str, Any] | None) -> list[dict[str, Any]]:
    devices = config.get("devices", {})
    if not isinstance(devices, dict):
        raise ValueError("devices must be an object")

    devices_state = state.get("devices", []) if isinstance(state, dict) else []
    if not isinstance(devices_state, list):
        devices_state = []
    live_by_pin = _devices_by_pin(devices_state)

    result: list[dict[str, Any]] = []
    for device_id in devices:
        device = devices[device_id]
        if not isinstance(device, dict):
            raise ValueError(f"device {device_id} must be an object")
        if device.get("controller") != role:
            continue
        pin = _as_int(device.get("pin"), f"device {device_id} pin")
        if pin < 0 or pin > 29:
            raise ValueError(f"device {device_id} pin must be in range 0..29")
        default_editor = device.get("editor", "cycle")
        if default_editor not in {"cycle", "clock_window"}:
            default_editor = "cycle"
        live_device = live_by_pin.get(pin)
        configured_type = device.get("type")
        if configured_type in {"gpio", "pwm"}:
            event_type = configured_type
        elif isinstance(live_device, dict):
            event_type = live_device.get("type", "gpio")
        else:
            event_type = "gpio"
        if event_type not in {"gpio", "pwm"}:
            event_type = "gpio"
        live_pin = pin
        if isinstance(live_device, dict):
            try:
                candidate_pin = int(live_device.get("pin"))
            except (TypeError, ValueError):
                candidate_pin = pin
            if 0 <= candidate_pin <= 29:
                live_pin = candidate_pin
        result.append(
            {
                "role": role,
                "id": device_id,
                "name": device_id,
                "pin": live_pin,
                "type": event_type,
                "default_editor": default_editor,
            }
        )
    return result


def inspect_two_step_pattern(device: dict[str, Any]) -> dict[str, int] | None:
    pattern = device.get("pattern")
    if not isinstance(pattern, list) or len(pattern) != 2:
        return None
    first, second = pattern
    if not isinstance(first, dict) or not isinstance(second, dict):
        return None
    try:
        first_val = int(first["val"])
        second_val = int(second["val"])
        first_dur = int(first["dur"])
        second_dur = int(second["dur"])
    except (KeyError, TypeError, ValueError):
        return None
    if first_val <= 0 or second_val != 0 or first_dur <= 0 or second_dur <= 0:
        return None
    return {"on_seconds": first_dur, "off_seconds": second_dur, "total_seconds": first_dur + second_dur}


def cycle_t_from_device(device: dict[str, Any] | None) -> int | None:
    if not isinstance(device, dict):
        return None
    raw = device.get("cycle_t", device.get("elapsed_t", device.get("current_t")))
    if raw is None:
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return max(0, value)


def _copy_event_base(event: dict[str, Any]) -> dict[str, Any]:
    updated = dict(event)
    updated["reschedule"] = 1
    return updated


def apply_cycle_schedule(
    event: dict[str, Any],
    *,
    on_seconds: int,
    off_seconds: int,
    start_at_seconds: int = 0,
) -> dict[str, Any]:
    if on_seconds <= 0:
        raise ValueError("on_seconds must be > 0")
    if off_seconds <= 0:
        raise ValueError("off_seconds must be > 0")
    if start_at_seconds < 0:
        raise ValueError("start_at_seconds must be >= 0")
    updated = _copy_event_base(event)
    updated["pattern"] = [{"val": 1, "dur": on_seconds}, {"val": 0, "dur": off_seconds}]
    updated["current_t"] = start_at_seconds % (on_seconds + off_seconds)
    return updated


def parse_clock_time(value: str) -> int:
    match = CLOCK_TIME_RE.match(value)
    if not match:
        raise ValueError("time must use HH:MM or HH:MM:SS")
    hour = int(match.group(1))
    minute = int(match.group(2))
    second = int(match.group(3) or 0)
    if hour > 23 or minute > 59 or second > 59:
        raise ValueError("time must be within a 24-hour day")
    return hour * 3600 + minute * 60 + second


def seconds_for_time(value: time) -> int:
    return value.hour * 3600 + value.minute * 60 + value.second


def apply_clock_window_schedule(event: dict[str, Any], *, on_time: str, off_time: str, now: time | None = None) -> dict[str, Any]:
    on_seconds = parse_clock_time(on_time)
    off_seconds = parse_clock_time(off_time)
    if on_seconds == off_seconds:
        raise ValueError("ON and OFF times must be different")
    on_duration = (off_seconds - on_seconds) % CLOCK_DAY_SECONDS
    off_duration = CLOCK_DAY_SECONDS - on_duration
    updated = _copy_event_base(event)
    updated["pattern"] = [{"val": 1, "dur": on_duration}, {"val": 0, "dur": off_duration}]
    now_seconds = seconds_for_time(now or datetime.now().time())
    updated["current_t"] = (now_seconds - on_seconds) % CLOCK_DAY_SECONDS
    return updated


def _event_key(event: dict[str, Any], index: int) -> str:
    event_id = event.get("id")
    if isinstance(event_id, str) and event_id:
        return event_id
    pin = event.get("pin")
    return f"pin-{pin if pin is not None else index}"


def _live_device_by_id(live_devices: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for index, device in enumerate(live_devices or []):
        if isinstance(device, dict):
            result[_event_key(device, index)] = device
    return result


def _channel_by_id(channels: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(channel["id"]): channel for channel in channels if isinstance(channel, dict) and "id" in channel}


def _resync_unedited_device(device: dict[str, Any], live_device: dict[str, Any] | None) -> dict[str, Any]:
    updated = dict(device)
    pattern = inspect_two_step_pattern(updated)
    live_cycle = cycle_t_from_device(live_device)
    if live_cycle is not None and pattern:
        updated["current_t"] = live_cycle % pattern["total_seconds"]
    return updated


def _new_channel_device(channel: dict[str, Any], channel_id: str) -> dict[str, Any]:
    return {
        "id": channel_id,
        "type": channel.get("type", "gpio"),
        "pin": channel.get("pin"),
        "current_t": 0,
        "reschedule": 1,
    }


def patch_channel_schedule(
    state: dict[str, Any],
    channels: list[dict[str, Any]],
    channel_id: str,
    schedule: dict[str, Any],
    *,
    live_devices: list[dict[str, Any]] | None = None,
    now: time | None = None,
) -> dict[str, Any]:
    devices = state.get("devices")
    if not isinstance(devices, list):
        raise ValueError("state devices must be a list")
    channels_by_id = _channel_by_id(channels)
    channel = channels_by_id.get(channel_id)
    if channel is None:
        raise ValueError(f"unknown channel: {channel_id}")
    live_by_id = _live_device_by_id(live_devices)
    live_by_pin = _devices_by_pin(live_devices)
    updated_devices = []
    found = False
    for index, device in enumerate(devices):
        if not isinstance(device, dict):
            updated_devices.append(device)
            continue
        device_id = _event_key(device, index)
        live_device = live_by_id.get(device_id)
        if live_device is None:
            live_device = live_by_pin.get(device.get("pin"))
        if device_id == channel_id or device.get("pin") == channel.get("pin"):
            found = True
            updated_device = dict(device)
            updated_device["id"] = channel_id
            if device_id == channel_id:
                updated_device["pin"] = channel.get("pin")
                updated_device["type"] = channel.get("type")
            elif updated_device.get("pin") != channel.get("pin") or updated_device.get("type") != channel.get("type"):
                raise ValueError(f"channel {channel_id} does not match scheduler event pin/type")
            mode = schedule.get("mode")
            if mode == "cycle":
                updated_devices.append(
                    apply_cycle_schedule(
                        updated_device,
                        on_seconds=_as_int(schedule.get("on_seconds"), "on_seconds"),
                        off_seconds=_as_int(schedule.get("off_seconds"), "off_seconds"),
                        start_at_seconds=_as_int(schedule.get("start_at_seconds", 0), "start_at_seconds"),
                    )
                )
            elif mode == "clock_window":
                updated_devices.append(
                    apply_clock_window_schedule(
                        updated_device,
                        on_time=str(schedule.get("on_time", "")),
                        off_time=str(schedule.get("off_time", "")),
                        now=now,
                    )
                )
            else:
                raise ValueError("mode must be cycle or clock_window")
        else:
            updated_devices.append(_resync_unedited_device(device, live_device))
    if not found:
        base_device = _new_channel_device(channel, channel_id)
        mode = schedule.get("mode")
        if mode == "cycle":
            updated_devices.append(
                apply_cycle_schedule(
                    base_device,
                    on_seconds=_as_int(schedule.get("on_seconds"), "on_seconds"),
                    off_seconds=_as_int(schedule.get("off_seconds"), "off_seconds"),
                    start_at_seconds=_as_int(schedule.get("start_at_seconds", 0), "start_at_seconds"),
                )
            )
        elif mode == "clock_window":
            updated_devices.append(
                apply_clock_window_schedule(
                    base_device,
                    on_time=str(schedule.get("on_time", "")),
                    off_time=str(schedule.get("off_time", "")),
                    now=now,
                )
            )
        else:
            raise ValueError("mode must be cycle or clock_window")
    updated = dict(state)
    updated["devices"] = updated_devices
    updated.pop("events", None)
    return updated
