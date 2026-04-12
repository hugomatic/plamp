# Main Page Timer Schedule UI Design

## Goal

Build a polished main-page schedule editor for configured Pico timer channels. The first slice should support arbitrary timers without requiring firmware changes or a settings UI for managing boards and pins.

The main page remains the place to check whether timers are working. It keeps the current live status cards and adds schedule editing for each configured channel. Board setup, timer names, pins, and output types come from JSON config for now; a settings-page editor can be built later as a UI over that config.

## Scope

In scope:

- Extend timer configuration to describe channels under each Pico role.
- Read channel metadata from config: `id`, display `name`, `pin`, output `type`, and default schedule editor.
- Keep the existing main-page live visualization for timer status.
- Add an edit action for each configured channel on the main page.
- Let a channel schedule be edited in either a cycle representation or a 24-hour clock-window representation.
- Save edited schedules through the existing board-level timer PUT flow.
- Recompute timing fields so a Pico reset applies the new board state correctly.

Out of scope for this slice:

- A settings-page editor for roles, serials, timer names, pins, or output types.
- Firmware changes.
- Sensor-driven or conditional scheduling.
- Multi-step schedules beyond the existing simple on/off pattern editor.
- Device-specific timer categories such as fan, lights, pump, or food dispenser.

## Configuration Shape

`data/config.json` should continue to use `timers` as the top-level list of Pico timer roles. Each timer role may add a `channels` list:

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
          "default_editor": "clock"
        }
      ]
    }
  ]
}
```

Rules:

- `role` and `pico_serial` keep their current meaning.
- `channels[].id` maps to the scheduler event `id`.
- `channels[].name` is the user-facing label.
- `channels[].pin` maps to scheduler event `ch`.
- `channels[].type` maps to scheduler event `type`; this slice should support existing `gpio` and keep `pwm` compatible with validation.
- `channels[].default_editor` may be `cycle` or `clock`.

If `channels` is missing, the main page should still fall back to the events reported by the timer state, as it does today. This keeps existing local configs usable.

## Main Page Behavior

The main page keeps the current status-card visualization:

- Board role and timer/channel name.
- ON/OFF value badge.
- Pin, output type, raw value, next change time.
- Progress through the current step.
- Stream status for configured Pico roles.
- Host/server time at minute accuracy, refreshed in the page, so clock-based schedule edits have an obvious time reference.

Each timer card gets an edit action. Editing opens an inline panel or compact dialog for that channel. The editor changes schedule behavior only; it does not change board role, Pico serial, channel name, pin, or output type.

The editor should load from the current board state fetched from `/api/timers/{role}`. Saving one channel should produce a full updated board state and PUT it to `/api/timers/{role}` because the current API and firmware apply scheduler state at board scope.

After save, the UI should wait for stream data to reconnect or update, then show the current status. If saving fails, show the API error near the editor and keep the user's inputs available.

## Schedule Editors

The schedule editor supports two representations over the same firmware-compatible event shape.

### Cycle Set

Cycle set edits a two-step repeating pattern:

- ON duration.
- OFF duration.
- Unit selector for seconds, minutes, or hours.
- Apply behavior:
  - `Keep current position` as the default.
  - `Start cycle now`.
  - `Jump to next change`.

Cycle set can load any two-step on/off pattern. When saving:

- `Start cycle now` sets `current_t` to `0`.
- `Jump to next change` sets `current_t` close to the end of the current step, such as five seconds before the transition when the current step is long enough.
- `Keep current position` uses the latest live report cycle position when available, and otherwise preserves the existing saved `current_t`.

### 24h Set

24h set edits a two-step repeating pattern through clock times:

- ON time.
- OFF time.

When saving, it generates a 24-hour repeating pattern with ON and OFF durations in seconds. It always computes `current_t` from the host server clock, not the browser clock, so the timer phase matches the real day after the Pico resets. The main page should display the host/server time to minute accuracy and refresh it so the user can see which clock is being used.

24h set can be selected even if the current pattern is not already 24 hours. In that case, saving intentionally rewrites the event to a 24-hour cycle.

## Board-Level Reset Handling

The UI should feel like it edits one timer at a time, but the implementation must respect board-level state application:

- Fetch the full state for the selected role.
- Replace only the edited event in the full `events` list.
- Recompute phase for all events on that board before PUT when enough metadata is available.
- PUT the full state to `/api/timers/{role}`.

For unedited events:

- If a channel uses `default_editor: "clock"` and has a simple 24-hour pattern, recompute `current_t` from the host clock.
- Otherwise preserve phase from the latest live report when available.
- If no live report is available, preserve the saved `current_t`.

This prevents editing one timer from unexpectedly restarting every generic cycle at the beginning while still keeping 24-hour timers aligned to the host clock.

## Error Handling

The editor should validate before PUT:

- ON and OFF durations must be positive.
- Pin and output type are read from config and must match the scheduler state event.
- A channel must map to an event by `id`; missing events should produce a clear message.
- 24-hour ON/OFF times must create positive ON and OFF durations. If ON and OFF are identical, reject the schedule with a clear message.

API errors from PUT should be shown without discarding user edits. Stream reconnect or status errors should remain visible in the existing stream status area.

## Testing

Manual test paths:

- Existing config without `channels` still renders timer status cards.
- Config with multiple roles renders timers grouped by board.
- Config with multiple channels under one role renders one card per channel.
- Cycle set can save seconds, minutes, and hours.
- Cycle set apply behavior can preserve phase, start now, and jump to next change.
- 24h set saves ON/OFF clock times and reports a phase aligned with host time after reset.
- Host/server time appears on the main page with minute accuracy and refreshes while the page is open.
- Saving one channel PUTs a full board state and keeps unedited channels in sensible phases.
- PUT failure leaves the edit form intact and shows the error.

Automated tests should cover pure conversion helpers for:

- Cycle durations to scheduler pattern.
- Clock window to 24-hour scheduler pattern.
- Host-time to `current_t`.
- Phase preservation from live report data.
- Config channel lookup and fallback behavior when `channels` is absent.
