# Main Page Timer Schedule UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a polished main-page schedule editor for arbitrary configured Pico timer channels while keeping board/channel setup in JSON config for now.

**Architecture:** Add focused server-side timer config and schedule helper code, then expose read-only channel metadata, a host-time endpoint, and a channel schedule update endpoint that uses the existing board-level apply path. Keep the existing main-page live status visualization and add a schedule edit panel per channel that posts schedule changes instead of raw JSON.

**Tech Stack:** Python 3.11, FastAPI, plain server-rendered HTML, vanilla browser JavaScript, MicroPython-compatible scheduler state JSON, stdlib `unittest`.

---

## File Structure

- Create `plamp_web/timer_schedule.py`: Pure helper functions for channel config normalization, two-step pattern inspection, cycle schedule generation, 24-hour clock schedule generation, and board state patching.
- Modify `plamp_web/server.py`: Import helpers, expose config metadata via `/api/timer-config`, expose host time via `/api/host-time`, expose server-side schedule updates via `/api/timers/{role}/channels/{channel_id}/schedule`, and pass channel metadata plus initial host time to the main page renderer.
- Modify `plamp_web/pages.py`: Keep the current status-card visualization, display host/server time at minute accuracy, add channel metadata and initial host seconds-since-midnight into the page bootstrap JSON, refresh host time through `/api/host-time`, add edit controls and the schedule editor JavaScript.
- Create `tests/test_timer_schedule.py`: Unit tests for pure helper behavior.
- Modify `plamp_web/README.md`: Document the optional `channels` config shape and the main-page schedule editor.

## Task 1: Add Pure Schedule Helpers

**Files:**
- Create: `plamp_web/timer_schedule.py`
- Create: `tests/test_timer_schedule.py`

- [ ] **Step 1: Write failing tests for channel metadata and cycle helpers**

Create `tests/test_timer_schedule.py` with these initial tests:

```python
import unittest
from datetime import time

from plamp_web.timer_schedule import (
    apply_cycle_schedule,
    channel_metadata_for_role,
    inspect_two_step_pattern,
)


class TimerScheduleTests(unittest.TestCase):
    def test_channel_metadata_uses_configured_channels(self):
        role_config = {
            "role": "sprouter",
            "pico_serial": "abc123",
            "channels": [
                {"id": "lamp", "name": "Lamp", "pin": 2, "type": "gpio", "default_editor": "clock_window"},
                {"id": "fan", "name": "Fan", "pin": 3, "type": "gpio", "default_editor": "cycle"},
            ],
        }
        state = {"events": [{"id": "lamp", "type": "gpio", "ch": 2}, {"id": "fan", "type": "gpio", "ch": 3}]}

        self.assertEqual(
            channel_metadata_for_role("sprouter", role_config, state),
            [
                {"role": "sprouter", "id": "lamp", "name": "Lamp", "pin": 2, "type": "gpio", "default_editor": "clock_window"},
                {"role": "sprouter", "id": "fan", "name": "Fan", "pin": 3, "type": "gpio", "default_editor": "cycle"},
            ],
        )

    def test_channel_metadata_falls_back_to_state_events(self):
        role_config = {"role": "sprouter", "pico_serial": "abc123"}
        state = {"events": [{"id": "lamp", "type": "gpio", "ch": 2}, {"type": "gpio", "ch": 3}]}

        self.assertEqual(
            channel_metadata_for_role("sprouter", role_config, state),
            [
                {"role": "sprouter", "id": "lamp", "name": "lamp", "pin": 2, "type": "gpio", "default_editor": "cycle"},
                {"role": "sprouter", "id": "pin-3", "name": "pin 3", "pin": 3, "type": "gpio", "default_editor": "cycle"},
            ],
        )

    def test_inspect_two_step_pattern_accepts_on_off(self):
        event = {"pattern": [{"val": 1, "dur": 30}, {"val": 0, "dur": 600}], "current_t": 10}

        self.assertEqual(inspect_two_step_pattern(event), {"on_seconds": 30, "off_seconds": 600, "total_seconds": 630})

    def test_apply_cycle_schedule_can_start_now(self):
        event = {"id": "fan", "type": "gpio", "ch": 3, "current_t": 200, "reschedule": 1, "pattern": [{"val": 1, "dur": 30}, {"val": 0, "dur": 600}]}

        updated = apply_cycle_schedule(event, on_seconds=10, off_seconds=20, apply_behavior="start_now", live_event={"cycle_t": 12})

        self.assertEqual(updated["pattern"], [{"val": 1, "dur": 10}, {"val": 0, "dur": 20}])
        self.assertEqual(updated["current_t"], 0)
        self.assertEqual(updated["id"], "fan")
        self.assertEqual(updated["type"], "gpio")
        self.assertEqual(updated["ch"], 3)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m unittest discover -s tests -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'plamp_web.timer_schedule'`.

- [ ] **Step 3: Implement helper module**

Create `plamp_web/timer_schedule.py`:

```python
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
            result.append({"role": role, "id": channel_id, "name": name, "pin": pin_int, "type": event_type, "default_editor": default_editor})
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
        result.append({"role": role, "id": event_id, "name": name, "pin": pin, "type": event.get("type", "gpio"), "default_editor": "cycle"})
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


def _copy_event_base(event: dict[str, Any]) -> dict[str, Any]:
    updated = dict(event)
    updated["reschedule"] = 1
    return updated


def apply_cycle_schedule(event: dict[str, Any], *, on_seconds: int, off_seconds: int, apply_behavior: str, live_event: dict[str, Any] | None = None) -> dict[str, Any]:
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
        source_cycle = cycle_t_from_event(live_event or event)
        if source_cycle is None:
            source_cycle = 0
        in_on = source_cycle < on_seconds
        boundary = on_seconds if in_on else total
        current_t = max(0, boundary - 5)
    elif apply_behavior == "preserve":
        source_cycle = cycle_t_from_event(live_event or event)
        current_t = source_cycle if source_cycle is not None else _as_int(event.get("current_t", 0), "current_t")
    else:
        raise ValueError("apply_behavior must be preserve, start_now, or jump_to_next_change")
    updated["current_t"] = current_t % total
    return updated


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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m unittest discover -s tests -v`

Expected: PASS for the four `TimerScheduleTests` tests.

- [ ] **Step 5: Commit Task 1**

```bash
git add plamp_web/timer_schedule.py tests/test_timer_schedule.py
git commit -m "Add timer schedule helper tests"
```

## Task 2: Add Clock Schedule and Board Patch Helpers

**Files:**
- Modify: `plamp_web/timer_schedule.py`
- Modify: `tests/test_timer_schedule.py`

- [ ] **Step 1: Add failing tests for clock schedules and board patching**

Append these test methods inside `TimerScheduleTests` before the `if __name__ == "__main__"` block:

```python
    def test_apply_clock_schedule_uses_host_time(self):
        event = {"id": "lamp", "type": "gpio", "ch": 2, "current_t": 0, "reschedule": 1, "pattern": [{"val": 1, "dur": 1}, {"val": 0, "dur": 1}]}

        updated = apply_clock_schedule(event, on_time="06:00", off_time="18:30", now=time(7, 0, 0))

        self.assertEqual(updated["pattern"], [{"val": 1, "dur": 45000}, {"val": 0, "dur": 41400}])
        self.assertEqual(updated["current_t"], 3600)

    def test_apply_clock_schedule_rejects_identical_times(self):
        event = {"id": "lamp", "type": "gpio", "ch": 2, "current_t": 0, "reschedule": 1, "pattern": [{"val": 1, "dur": 1}, {"val": 0, "dur": 1}]}

        with self.assertRaisesRegex(ValueError, "ON and OFF times must be different"):
            apply_clock_schedule(event, on_time="06:00", off_time="06:00", now=time(7, 0, 0))

    def test_patch_channel_schedule_replaces_only_target_event(self):
        state = {
            "report_every": 1,
            "events": [
                {"id": "fan", "type": "gpio", "ch": 3, "current_t": 4, "reschedule": 1, "pattern": [{"val": 1, "dur": 10}, {"val": 0, "dur": 50}]},
                {"id": "lamp", "type": "gpio", "ch": 2, "current_t": 0, "reschedule": 1, "pattern": [{"val": 1, "dur": 3600}, {"val": 0, "dur": 82800}]},
            ],
        }
        channels = [
            {"id": "fan", "pin": 3, "type": "gpio", "default_editor": "cycle"},
            {"id": "lamp", "pin": 2, "type": "gpio", "default_editor": "clock_window"},
        ]
        live_events = [{"id": "fan", "cycle_t": 25}, {"id": "lamp", "cycle_t": 7200}]

        updated = patch_channel_schedule(
            state,
            channels,
            "fan",
            {"mode": "cycle", "on_seconds": 20, "off_seconds": 40, "apply_behavior": "preserve"},
            live_events=live_events,
            now=time(12, 0, 0),
        )

        self.assertEqual(updated["events"][0]["pattern"], [{"val": 1, "dur": 20}, {"val": 0, "dur": 40}])
        self.assertEqual(updated["events"][0]["current_t"], 25)
        self.assertEqual(updated["events"][1]["pattern"], [{"val": 1, "dur": 3600}, {"val": 0, "dur": 82800}])
        self.assertEqual(updated["events"][1]["current_t"], 7200)
```

Also update the import block to include:

```python
    apply_clock_schedule,
    patch_channel_schedule,
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m unittest discover -s tests -v`

Expected: FAIL with import errors for `apply_clock_schedule` and `patch_channel_schedule`.

- [ ] **Step 3: Implement clock and patch helpers**

Append this code to `plamp_web/timer_schedule.py`:

```python

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


def apply_clock_schedule(event: dict[str, Any], *, on_time: str, off_time: str, now: time | None = None) -> dict[str, Any]:
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
        event_channel = channels_by_id.get(event_id)
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
                    apply_clock_schedule(
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
```

- [ ] **Step 4: Run tests and fix any exact arithmetic failures**

Run: `uv run python -m unittest discover -s tests -v`

Expected: PASS for all seven tests. If the `test_patch_channel_schedule_replaces_only_target_event` expected `current_t` differs, inspect whether the helper is preserving the latest live phase for unedited events per the plan; fix the helper, not the assertion, unless the assertion contradicts this plan.

- [ ] **Step 5: Commit Task 2**

```bash
git add plamp_web/timer_schedule.py tests/test_timer_schedule.py
git commit -m "Add timer schedule conversion helpers"
```

## Task 3: Add Server APIs for Channel Metadata and Schedule Updates

**Files:**
- Modify: `plamp_web/server.py`
- Modify: `tests/test_timer_schedule.py`

- [ ] **Step 1: Add failing tests for schedule payload validation at helper level**

Append this test inside `TimerScheduleTests`:

```python
    def test_patch_channel_schedule_rejects_pin_type_mismatch(self):
        state = {"report_every": 1, "events": [{"id": "fan", "type": "gpio", "ch": 4, "current_t": 0, "reschedule": 1, "pattern": [{"val": 1, "dur": 10}, {"val": 0, "dur": 50}]}]}
        channels = [{"id": "fan", "pin": 3, "type": "gpio", "default_editor": "cycle"}]

        with self.assertRaisesRegex(ValueError, "pin/type"):
            patch_channel_schedule(state, channels, "fan", {"mode": "cycle", "on_seconds": 20, "off_seconds": 40, "apply_behavior": "preserve"})
```

- [ ] **Step 2: Run tests to verify the new behavior**

Run: `uv run python -m unittest discover -s tests -v`

Expected: PASS if Task 2 already validates pin/type. If it fails, add the validation shown in Task 2.

- [ ] **Step 3: Modify server imports**

In `plamp_web/server.py`, replace the current pages import:

```python
from plamp_web.pages import render_settings_page, render_timer_dashboard_page, render_timer_test_page
```

with:

```python
from plamp_web.pages import render_settings_page, render_timer_dashboard_page, render_timer_test_page
from plamp_web.timer_schedule import channel_metadata_for_role, patch_channel_schedule
```

- [ ] **Step 4: Add server helper functions**

Add these functions near `configured_timer_roles()` in `plamp_web/server.py`:

```python
def state_for_role(role: str) -> dict[str, Any]:
    latest = latest_timer_state(role)
    if latest is not None:
        return latest
    path = timer_state_path(role)
    state = load_json_file(path)
    return state_with_current_values(validate_timer_state(state))


def live_events_for_role(role: str) -> list[dict[str, Any]]:
    latest = latest_timer_state(role)
    events = latest.get("events") if isinstance(latest, dict) else None
    return events if isinstance(events, list) else []


def configured_timer_channels() -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for role, item in timer_roles().items():
        try:
            state = state_for_role(role)
            result[role] = channel_metadata_for_role(role, item, state)
        except (HTTPException, ValueError):
            result[role] = []
    return result
```

- [ ] **Step 5: Use `state_for_role()` in `get_timer()`**

Replace the non-stream body of `get_timer()` with:

```python
    return state_for_role(role)
```

The full function should be:

```python
@app.get("/api/timers/{role}", response_model=None)
def get_timer(role: str, stream: bool = Query(False)) -> Any:
    if stream:
        return stream_timer_events(role)
    return state_for_role(role)
```

- [ ] **Step 6: Add channel config and schedule update routes**

Add these routes before `/api/timers/{role}` in `plamp_web/server.py`:

```python
@app.get("/api/timer-config")
def get_timer_config() -> dict[str, Any]:
    return {"roles": configured_timer_roles(), "channels": configured_timer_channels(), "time_format": configured_time_format()}


@app.get("/api/host-time")
def get_host_time() -> dict[str, Any]:
    now = datetime.now()
    seconds = now.hour * 3600 + now.minute * 60 + now.second
    display = now.strftime("%H:%M") if configured_time_format() == "24h" else now.strftime("%-I:%M %p")
    return {"iso": now.isoformat(timespec="seconds"), "seconds_since_midnight": seconds, "display": display}


@app.post("/api/timers/{role}/channels/{channel_id}/schedule")
def post_timer_channel_schedule(role: str, channel_id: str, schedule: dict[str, Any] = Body(...)) -> dict[str, Any]:
    role_config = timer_role(role)
    current_state = state_for_role(role)
    channels = channel_metadata_for_role(role, role_config, current_state)
    try:
        updated = patch_channel_schedule(
            current_state,
            channels,
            channel_id,
            schedule,
            live_events=live_events_for_role(role),
            now=datetime.now().time(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    validated = validate_timer_state(updated)
    path = timer_state_path(role)
    with lock_for(role_locks, role):
        atomic_write_json(path, validated)
        sent = apply_timer_state(role, path)
    return {"role": role, "channel": channel_id, "success": True, "message": "schedule saved and sent to Pico", "pico": sent, "state": state_with_current_values(validated)}
```

- [ ] **Step 7: Pass channel metadata to the main page**

Change `get_timer_dashboard_page()` to:

```python
@app.get("/", response_class=HTMLResponse)
def get_timer_dashboard_page() -> HTMLResponse:
    return HTMLResponse(
        render_timer_dashboard_page(
            configured_timer_roles(),
            configured_time_format(),
            configured_timer_channels(),
            seconds_since_midnight(),
        )
    )
```

- [ ] **Step 8: Run syntax and helper tests**

Run: `uv run python -m unittest discover -s tests -v`

Expected: PASS.

Run: `uv run python -m py_compile plamp_web/server.py plamp_web/timer_schedule.py`

Expected: no output and exit code 0.

- [ ] **Step 9: Commit Task 3**

```bash
git add plamp_web/server.py plamp_web/timer_schedule.py tests/test_timer_schedule.py
git commit -m "Add timer channel schedule API"
```

## Task 4: Add Main Page Schedule Editor UI

**Files:**
- Modify: `plamp_web/pages.py`

- [ ] **Step 1: Update the renderer signature and bootstrap data**

Change the function signature in `plamp_web/pages.py` from:

```python
def render_timer_dashboard_page(roles: list[str], time_format: str) -> str:
```

to:

```python
def render_timer_dashboard_page(
    roles: list[str],
    time_format: str,
    channels_by_role: dict[str, list[dict[str, Any]]] | None = None,
    host_seconds_since_midnight: int = 0,
) -> str:
```

Inside the returned `<body>`, near the stream status paragraph, add:

```html
  <p class="host-clock">Host time: <span id="host-clock">--:--</span></p>
```

Inside the returned `<script>`, after `const timerRoles = ...`, add:

```javascript
    const timerChannels = {json.dumps(channels_by_role or {})};
    const timerHostSecondsAtLoad = {json.dumps(host_seconds_since_midnight)};
    const timerHostLoadedAt = Date.now();
    const hostClock = document.getElementById("host-clock");
```

- [ ] **Step 2: Add CSS for the editor without changing the existing card visualization**

Inside the existing `<style>` block for `render_timer_dashboard_page()`, add:

```css
    .timer-actions { margin-top: .65rem; }
    .timer-editor { border-top: 1px solid #ddd; display: grid; gap: .65rem; margin-top: .75rem; padding-top: .75rem; }
    .timer-editor[hidden] { display: none; }
    .editor-row { align-items: end; display: flex; flex-wrap: wrap; gap: .75rem; }
    .editor-row label { display: grid; gap: .25rem; }
    .editor-row select, .editor-row input { min-width: 8rem; }
    .host-clock { color: #555; font-size: .95rem; margin: -.5rem 0 1rem; }
    .editor-note { color: #555; font-size: .9rem; }
    .editor-error { color: #9a3412; font-weight: 600; }
    .editor-success { color: #166534; font-weight: 600; }
```

- [ ] **Step 3: Add JavaScript helper functions before `renderTimerStatus()`**

Add these functions in the main page script after `timerEventsFromMessage()`:

```javascript
    function channelForEvent(role, event, index) {
      const channels = timerChannels[role] || [];
      const eventId = event.id || "pin-" + (event.ch ?? index);
      return channels.find((channel) => channel.id === eventId) || {
        role,
        id: eventId,
        name: event.id || "pin " + (event.ch ?? index),
        pin: event.ch,
        type: event.type || "gpio",
        default_editor: "cycle",
      };
    }

    function twoStepDurations(event) {
      const pattern = Array.isArray(event.pattern) ? event.pattern : [];
      if (pattern.length !== 2) return null;
      const on = Number(pattern[0].dur);
      const off = Number(pattern[1].dur);
      const onValue = Number(pattern[0].val);
      const offValue = Number(pattern[1].val);
      if (!Number.isFinite(on) || !Number.isFinite(off) || on <= 0 || off <= 0 || onValue <= 0 || offValue !== 0) return null;
      return {on, off, total: on + off};
    }

    function chooseUnit(seconds) {
      if (seconds % 3600 === 0) return {value: seconds / 3600, unit: "hours"};
      if (seconds % 60 === 0) return {value: seconds / 60, unit: "minutes"};
      return {value: seconds, unit: "seconds"};
    }

    function unitMultiplier(unit) {
      if (unit === "hours") return 3600;
      if (unit === "minutes") return 60;
      return 1;
    }

    function secondsToClock(seconds) {
      const normalized = ((seconds % 86400) + 86400) % 86400;
      const hours = Math.floor(normalized / 3600);
      const minutes = Math.floor((normalized % 3600) / 60);
      return String(hours).padStart(2, "0") + ":" + String(minutes).padStart(2, "0");
    }

    function hostSecondsNow() {
      const elapsed = Math.floor((Date.now() - timerHostLoadedAt) / 1000);
      return (timerHostSecondsAtLoad + elapsed) % 86400;
    }

    async function refreshHostClock() {
      if (!hostClock) return;
      try {
        const response = await fetch("/api/host-time");
        const data = await response.json();
        if (response.ok && typeof data.display === "string") {
          hostClock.textContent = data.display;
          return;
        }
      } catch (error) {}
      hostClock.textContent = secondsToClock(hostSecondsNow());
    }

    function clockValuesForEvent(event) {
      const durations = twoStepDurations(event);
      if (!durations || durations.total !== 86400) return {on: "06:00", off: "18:00"};
      const cycleT = Number(event.cycle_t ?? event.current_t ?? 0) || 0;
      const onSeconds = ((hostSecondsNow() - cycleT) % 86400 + 86400) % 86400;
      return {on: secondsToClock(onSeconds), off: secondsToClock(onSeconds + durations.on)};
    }
```

- [ ] **Step 4: Add editor rendering functions**

Add these functions after the helper functions from Step 3:

```javascript
    function buildScheduleEditor(role, event, index) {
      const channel = channelForEvent(role, event, index);
      const durations = twoStepDurations(event) || {on: 60, off: 60, total: 120};
      const onUnit = chooseUnit(durations.on);
      const offUnit = chooseUnit(durations.off);
      const clock = clockValuesForEvent(event);
      const editor = document.createElement("form");
      editor.className = "timer-editor";
      editor.hidden = true;
      editor.dataset.role = role;
      editor.dataset.channelId = channel.id;
      editor.innerHTML = `
        <div class="editor-row">
          <label>Set as
            <select name="mode">
              <option value="cycle">Cycle set</option>
              <option value="clock_window">24h set</option>
            </select>
          </label>
          <span class="editor-note">${channel.name} uses pin ${channel.pin ?? "?"} as ${channel.type || "gpio"}.</span>
        </div>
        <div class="editor-row cycle-fields">
          <label>On for <input name="onValue" type="number" min="1" step="1" value="${onUnit.value}"></label>
          <label>Unit <select name="onUnit"><option value="seconds">seconds</option><option value="minutes">minutes</option><option value="hours">hours</option></select></label>
          <label>Off for <input name="offValue" type="number" min="1" step="1" value="${offUnit.value}"></label>
          <label>Unit <select name="offUnit"><option value="seconds">seconds</option><option value="minutes">minutes</option><option value="hours">hours</option></select></label>
          <label>When applied <select name="applyBehavior"><option value="preserve">Keep current position</option><option value="start_now">Start cycle now</option><option value="jump_to_next_change">Jump to next change</option></select></label>
        </div>
        <div class="editor-row clock-fields">
          <label>On at <input name="onTime" type="time" value="${clock.on}"></label>
          <label>Off at <input name="offTime" type="time" value="${clock.off}"></label>
          <span class="editor-note">Applies using the host clock.</span>
        </div>
        <div class="editor-row">
          <button type="submit">Apply schedule</button>
          <button type="button" name="cancel">Cancel</button>
          <span class="editor-message" aria-live="polite"></span>
        </div>
      `;
      editor.elements.mode.value = channel.default_editor === "clock_window" ? "clock_window" : "cycle";
      editor.elements.onUnit.value = onUnit.unit;
      editor.elements.offUnit.value = offUnit.unit;
      syncEditorMode(editor);
      editor.elements.mode.addEventListener("change", () => syncEditorMode(editor));
      editor.elements.cancel.addEventListener("click", () => { editor.hidden = true; });
      editor.addEventListener("submit", submitScheduleEditor);
      return editor;
    }

    function syncEditorMode(editor) {
      const clock = editor.elements.mode.value === "clock";
      editor.querySelector(".cycle-fields").hidden = clock;
      editor.querySelector(".clock-fields").hidden = !clock;
    }

    async function submitScheduleEditor(event) {
      event.preventDefault();
      const editor = event.currentTarget;
      const message = editor.querySelector(".editor-message");
      message.className = "editor-message";
      message.textContent = "Saving...";
      const mode = editor.elements.mode.value;
      const body = {mode};
      if (mode === "cycle") {
        body.on_seconds = Number(editor.elements.onValue.value) * unitMultiplier(editor.elements.onUnit.value);
        body.off_seconds = Number(editor.elements.offValue.value) * unitMultiplier(editor.elements.offUnit.value);
        body.apply_behavior = editor.elements.applyBehavior.value;
      } else {
        body.on_time = editor.elements.onTime.value;
        body.off_time = editor.elements.offTime.value;
      }
      try {
        const response = await fetch(`/api/timers/${encodeURIComponent(editor.dataset.role)}/channels/${encodeURIComponent(editor.dataset.channelId)}/schedule`, {
          method: "POST",
          headers: {"content-type": "application/json"},
          body: JSON.stringify(body),
        });
        const text = await response.text();
        let parsed = null;
        try { parsed = JSON.parse(text); } catch (error) {}
        if (!response.ok) {
          throw new Error(parsed?.detail || text || `${response.status} ${response.statusText}`);
        }
        message.className = "editor-message editor-success";
        message.textContent = "Schedule applied. Waiting for report...";
      } catch (error) {
        message.className = "editor-message editor-error";
        message.textContent = String(error.message || error);
      }
    }
```

- [ ] **Step 5: Attach the editor to each timer card**

Inside `renderTimerStatus()`, after `card.append(top, meta, bar);` and before `timerBoard.append(card);`, insert:

```javascript
          const actions = document.createElement("div");
          actions.className = "timer-actions";
          const edit = document.createElement("button");
          edit.type = "button";
          edit.textContent = "Edit schedule";
          const editor = buildScheduleEditor(role, event, index);
          edit.addEventListener("click", () => { editor.hidden = !editor.hidden; });
          actions.append(edit);
          card.append(actions, editor);
```

Also change the card title from:

```javascript
          name.textContent = role + " / " + (event.id || "pin " + (event.ch ?? index));
```

to:

```javascript
          const channel = channelForEvent(role, event, index);
          name.textContent = role + " / " + channel.name;
```

- [ ] **Step 6: Start and refresh the host clock display**

Near the bottom of the main page script, immediately before `startTimerStreams();`, add:

```javascript
    refreshHostClock();
    setInterval(refreshHostClock, 30000);
```

The display polls `/api/host-time` every 30 seconds while showing only `HH:MM`, so it stays tied to the server clock without drawing attention to seconds-level drift.

- [ ] **Step 7: Run syntax check**

Run: `uv run python -m py_compile plamp_web/pages.py plamp_web/server.py plamp_web/timer_schedule.py`

Expected: no output and exit code 0.

- [ ] **Step 8: Commit Task 4**

```bash
git add plamp_web/pages.py plamp_web/server.py plamp_web/timer_schedule.py
git commit -m "Add main page timer schedule editor"
```

## Task 5: Documentation and Manual Verification

**Files:**
- Modify: `plamp_web/README.md`

- [ ] **Step 1: Document the config-backed channel shape**

In `plamp_web/README.md`, after the existing `Timer API` config example, add:

```markdown
Timer roles may also define channels for the main-page schedule editor:

```json
{
  "timers": [
    {
      "role": "pump_lights",
      "pico_serial": "e66038b71387a039",
      "channels": [
        {
          "id": "pump",
          "name": "Pump",
          "pin": 15,
          "type": "gpio",
          "default_editor": "cycle"
        },
        {
          "id": "lights",
          "name": "Lights",
          "pin": 2,
          "type": "gpio",
          "default_editor": "clock_window"
        }
      ]
    }
  ]
}
```

The `id`, `pin`, and `type` fields should match events in `data/timers/<role>.json`. The main page uses this metadata for labels and schedule editing. Board and channel setup still happens by editing JSON; the main page only edits schedules.
```

- [ ] **Step 2: Run automated checks**

Run: `uv run python -m unittest discover -s tests -v`

Expected: PASS.

Run: `uv run python -m py_compile plamp_web/server.py plamp_web/pages.py plamp_web/timer_schedule.py`

Expected: no output and exit code 0.

- [ ] **Step 3: Run the server**

Run: `uv run uvicorn plamp_web.server:app --host 0.0.0.0 --port 8000 --reload`

Expected: Uvicorn starts and serves `http://0.0.0.0:8000`.

- [ ] **Step 4: Verify current config fallback in a browser**

Open `http://localhost:8000/` and verify:

- The existing timer card still renders with the current `pump_lights` role.
- The card still shows ON/OFF state, pin, type, next change, and progress.
- The card has an `Edit schedule` button.
- Host time appears near the timer status with minute accuracy and updates while the page is open.
- Opening the editor defaults to `Cycle set` if the config lacks `channels`.

- [ ] **Step 5: Verify configured channel metadata manually**

Temporarily edit local ignored `data/config.json` to add a `channels` entry matching the current timer state, for example:

```json
{
  "timers": [
    {
      "role": "pump_lights",
      "pico_serial": "e66038b71387a039",
      "channels": [
        {
          "id": "test_pin",
          "name": "Test pin",
          "pin": 25,
          "type": "gpio",
          "default_editor": "cycle"
        }
      ]
    }
  ]
}
```

Reload `http://localhost:8000/` and verify the timer title uses `Test pin`.

- [ ] **Step 6: Verify schedule save behavior without discarding errors**

With hardware connected, edit the test channel and apply a short cycle. Verify:

- The request returns success.
- The stream reconnects or updates.
- The card reflects the new schedule.

With hardware disconnected, edit the test channel and apply a schedule. Verify:

- The editor shows the API error.
- The entered values stay in the editor.

- [ ] **Step 7: Commit documentation and verification updates**

```bash
git add plamp_web/README.md
git commit -m "Document timer channel schedule config"
```

## Final Verification

- [ ] Run: `git status --short --branch`

Expected: feature branch is ahead of `main` and has no unstaged changes.

- [ ] Run: `uv run python -m unittest discover -s tests -v`

Expected: PASS.

- [ ] Run: `uv run python -m py_compile plamp_web/server.py plamp_web/pages.py plamp_web/timer_schedule.py`

Expected: no output and exit code 0.

- [ ] Push the feature branch, not `main`:

```bash
git push origin feature-timer-schedule-ui-plan
```

- [ ] Open a PR from `feature-timer-schedule-ui-plan` into `main`.
