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


def _events_by_pin(events: list[dict[str, Any]] | None) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    for event in events or []:
        if not isinstance(event, dict):
            continue
        try:
            pin = int(event.get("ch"))
        except (TypeError, ValueError):
            continue
        if 0 <= pin <= 29:
            result[pin] = event
    return result


def channel_metadata_for_role(role: str, config: dict[str, Any], state: dict[str, Any] | None) -> list[dict[str, Any]]:
    devices = config.get("devices", {})
    if not isinstance(devices, dict):
        raise ValueError("devices must be an object")

    events = state.get("events", []) if isinstance(state, dict) else []
    if not isinstance(events, list):
        events = []
    live_by_pin = _events_by_pin(events)

    result: list[dict[str, Any]] = []
    for device_id in sorted(devices):
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
        live_event = live_by_pin.get(pin)
        event_type = live_event.get("type", "gpio") if isinstance(live_event, dict) else "gpio"
        if event_type not in {"gpio", "pwm"}:
            event_type = "gpio"
        live_pin = pin
        if isinstance(live_event, dict):
            try:
                candidate_pin = int(live_event.get("ch"))
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


def inspect_two_step_pattern(event: dict[str, Any]) -> dict[str, int] | None:
    pattern = event.get("pattern")
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


def cycle_t_from_event(event: dict[str, Any] | None) -> int | None:
    if not isinstance(event, dict):
        return None
    raw = event.get("cycle_t", event.get("elapsed_t", event.get("current_t")))
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
    pin = event.get("ch")
    return f"pin-{pin if pin is not None else index}"


def _live_event_by_id(live_events: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for index, event in enumerate(live_events or []):
        if isinstance(event, dict):
            result[_event_key(event, index)] = event
    return result


def _channel_by_id(channels: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(channel["id"]): channel for channel in channels if isinstance(channel, dict) and "id" in channel}


def _resync_unedited_event(event: dict[str, Any], live_event: dict[str, Any] | None) -> dict[str, Any]:
    updated = dict(event)
    pattern = inspect_two_step_pattern(updated)
    live_cycle = cycle_t_from_event(live_event)
    if live_cycle is not None and pattern:
        updated["current_t"] = live_cycle % pattern["total_seconds"]
    return updated


def _new_channel_event(channel: dict[str, Any], channel_id: str) -> dict[str, Any]:
    return {
        "id": channel_id,
        "type": channel.get("type", "gpio"),
        "ch": channel.get("pin"),
        "current_t": 0,
        "reschedule": 1,
    }


def patch_channel_schedule(
    state: dict[str, Any],
    channels: list[dict[str, Any]],
    channel_id: str,
    schedule: dict[str, Any],
    *,
    live_events: list[dict[str, Any]] | None = None,
    now: time | None = None,
) -> dict[str, Any]:
    events = state.get("events")
    if not isinstance(events, list):
        raise ValueError("state events must be a list")
    channels_by_id = _channel_by_id(channels)
    channel = channels_by_id.get(channel_id)
    if channel is None:
        raise ValueError(f"unknown channel: {channel_id}")
    live_by_id = _live_event_by_id(live_events)
    live_by_pin = _events_by_pin(live_events)
    updated_events = []
    found = False
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            updated_events.append(event)
            continue
        event_id = _event_key(event, index)
        live_event = live_by_id.get(event_id)
        if live_event is None:
            live_event = live_by_pin.get(event.get("ch"))
        if event_id == channel_id or event.get("ch") == channel.get("pin"):
            found = True
            updated_event = dict(event)
            updated_event["id"] = channel_id
            if updated_event.get("ch") != channel.get("pin") or updated_event.get("type") != channel.get("type"):
                raise ValueError(f"channel {channel_id} does not match scheduler event pin/type")
            mode = schedule.get("mode")
            if mode == "cycle":
                updated_events.append(
                    apply_cycle_schedule(
                        updated_event,
                        on_seconds=_as_int(schedule.get("on_seconds"), "on_seconds"),
                        off_seconds=_as_int(schedule.get("off_seconds"), "off_seconds"),
                        start_at_seconds=_as_int(schedule.get("start_at_seconds", 0), "start_at_seconds"),
                    )
                )
            elif mode == "clock_window":
                updated_events.append(
                    apply_clock_window_schedule(
                        updated_event,
                        on_time=str(schedule.get("on_time", "")),
                        off_time=str(schedule.get("off_time", "")),
                        now=now,
                    )
                )
            else:
                raise ValueError("mode must be cycle or clock_window")
        else:
            updated_events.append(_resync_unedited_event(event, live_event))
    if not found:
        base_event = _new_channel_event(channel, channel_id)
        mode = schedule.get("mode")
        if mode == "cycle":
            updated_events.append(
                apply_cycle_schedule(
                    base_event,
                    on_seconds=_as_int(schedule.get("on_seconds"), "on_seconds"),
                    off_seconds=_as_int(schedule.get("off_seconds"), "off_seconds"),
                    start_at_seconds=_as_int(schedule.get("start_at_seconds", 0), "start_at_seconds"),
                )
            )
        elif mode == "clock_window":
            updated_events.append(
                apply_clock_window_schedule(
                    base_event,
                    on_time=str(schedule.get("on_time", "")),
                    off_time=str(schedule.get("off_time", "")),
                    now=now,
                )
            )
        else:
            raise ValueError("mode must be cycle or clock_window")
    updated = dict(state)
    updated["events"] = updated_events
    return updated
