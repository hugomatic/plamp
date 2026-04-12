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


def channel_metadata_for_role(role: str, role_config: dict[str, Any], state: dict[str, Any] | None) -> list[dict[str, Any]]:
    channels = role_config.get("channels")
    if isinstance(channels, list):
        result: list[dict[str, Any]] = []
        for index, channel in enumerate(channels):
            if not isinstance(channel, dict):
                raise ValueError(f"channel {index} must be an object")
            channel_id = channel.get("id")
            name = channel.get("name") or channel_id
            pin = channel.get("pin")
            event_type = channel.get("type", "gpio")
            default_editor = channel.get("default_editor", "cycle")
            if not isinstance(channel_id, str) or not channel_id:
                raise ValueError(f"channel {index} id must be a non-empty string")
            if not isinstance(name, str) or not name:
                raise ValueError(f"channel {channel_id} name must be a non-empty string")
            pin_int = _as_int(pin, f"channel {channel_id} pin")
            if pin_int < 0 or pin_int > 29:
                raise ValueError(f"channel {channel_id} pin must be in range 0..29")
            if event_type not in {"gpio", "pwm"}:
                raise ValueError(f"channel {channel_id} type must be gpio or pwm")
            if default_editor not in {"cycle", "clock_window"}:
                default_editor = "cycle"
            result.append(
                {
                    "role": role,
                    "id": channel_id,
                    "name": name,
                    "pin": pin_int,
                    "type": event_type,
                    "default_editor": default_editor,
                }
            )
        return result

    events = state.get("events", []) if isinstance(state, dict) else []
    result = []
    if not isinstance(events, list):
        return result
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            continue
        pin = event.get("ch")
        event_id = event.get("id") if isinstance(event.get("id"), str) and event.get("id") else f"pin-{pin if pin is not None else index}"
        name = event.get("id") if isinstance(event.get("id"), str) and event.get("id") else f"pin {pin if pin is not None else index}"
        result.append(
            {
                "role": role,
                "id": event_id,
                "name": name,
                "pin": pin,
                "type": event.get("type", "gpio"),
                "default_editor": "cycle",
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
    apply_behavior: str,
    live_event: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if on_seconds <= 0:
        raise ValueError("on_seconds must be > 0")
    if off_seconds <= 0:
        raise ValueError("off_seconds must be > 0")
    updated = _copy_event_base(event)
    updated["pattern"] = [{"val": 1, "dur": on_seconds}, {"val": 0, "dur": off_seconds}]
    total = on_seconds + off_seconds
    if apply_behavior == "start_now":
        current_t = 0
    elif apply_behavior == "jump_to_next_change":
        source_cycle = cycle_t_from_event(live_event or event) or 0
        source_cycle %= total
        boundary = on_seconds if source_cycle < on_seconds else total
        current_t = max(0, boundary - 5)
    elif apply_behavior == "preserve":
        source_cycle = cycle_t_from_event(live_event or event)
        current_t = source_cycle if source_cycle is not None else _as_int(event.get("current_t", 0), "current_t")
    else:
        raise ValueError("apply_behavior must be preserve, start_now, or jump_to_next_change")
    updated["current_t"] = current_t % total
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
    updated_events = []
    found = False
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            updated_events.append(event)
            continue
        event_id = _event_key(event, index)
        live_event = live_by_id.get(event_id)
        if event_id == channel_id:
            found = True
            if event.get("ch") != channel.get("pin") or event.get("type") != channel.get("type"):
                raise ValueError(f"channel {channel_id} does not match scheduler event pin/type")
            mode = schedule.get("mode")
            if mode == "cycle":
                updated_events.append(
                    apply_cycle_schedule(
                        event,
                        on_seconds=_as_int(schedule.get("on_seconds"), "on_seconds"),
                        off_seconds=_as_int(schedule.get("off_seconds"), "off_seconds"),
                        apply_behavior=str(schedule.get("apply_behavior", "preserve")),
                        live_event=live_event,
                    )
                )
            elif mode == "clock_window":
                updated_events.append(
                    apply_clock_window_schedule(
                        event,
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
        raise ValueError(f"missing scheduler event for channel: {channel_id}")
    updated = dict(state)
    updated["events"] = updated_events
    return updated
