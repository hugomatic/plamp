# Atomic Scheduler Apply Design

## Goal

Save all channel schedules and flash the Pico once. Keep user-entered clock times and units in configuration; use Pico reports for runtime status.

## Invariants

- One editor save causes at most one Pico flash.
- Opening an editor never changes a saved schedule.
- `06:00` stays `06:00`; `5 minutes` may compile to 300 seconds but reopens as minutes.
- Firmware always contains the complete enabled channel set.
- A missing report never causes an automatic second flash.

## Algorithm

### Open editor

For each channel:

1. If saved configuration contains a schedule, copy it into the form exactly. This preserves values such as `06:00`, `23:00`, and `minutes`.
2. Otherwise, for legacy configuration only, derive form values from the latest Pico report.

### Save editor

1. Browser reads every channel form.
2. Browser sends one complete controller configuration to `PUT /api/config/controllers`.
3. Browser calls `POST /api/controllers/{controller}/apply` once.
4. Server loads the newly saved schedules and builds one timer state:
   - Cycle: pattern is ON/OFF seconds; phase is `start_at_seconds`.
   - Daily window: pattern durations come from ON/OFF clock times; phase is calculated from the host clock.
5. Server atomically writes the timer state.
6. Server generates one `main.py` containing every enabled channel.
7. Server flashes the Pico once.
8. After reconnecting, the existing monitor sends `r` once.
9. The next report updates current ON/OFF status and displayed runtime progress.

The browser removes its current per-channel schedule POST loop. The per-channel API remains available for CLI use, but becomes a wrapper that updates semantic configuration and calls the same whole-controller compile/apply operation. It must not patch compiled timer state directly.

## Implementation Boundaries

- `plamp_web/pages.py`
  - Change `clockValuesForEvent` to accept the channel and return saved daily-window values when present; retain report reconstruction only as its fallback.
  - Keep building the complete controller configuration from the form.
  - Delete the per-channel schedule request loop after the controller apply request.
- `plamp_web/timer_schedule.py`
  - Add one function that compiles every configured channel into a complete timer state.
  - Reuse `apply_cycle_schedule` and `apply_clock_window_schedule`; do not create a second schedule compiler.
- `plamp_web/server.py`
  - Change `post_controller_apply` to compile from current controller configuration, validate and atomically write the resulting timer state, then call `apply_timer_state` once.
  - Change the per-channel endpoint to update that channel's semantic schedule and delegate to the same controller apply function.
  - Keep the existing post-flash reconnect and `r` request.
- API test page in `plamp_web/pages.py`
  - Provide runnable examples for reading controller state, saving complete controller configuration, applying once, requesting a report, and updating one channel through the compatibility endpoint.
  - Examples must show both cycle and daily-window request bodies where applicable.
- Tests belong in `tests/test_pages.py`, `tests/test_timer_schedule.py`, and `tests/test_config_api.py` at the corresponding boundary.

## Non-goals

- Do not remove the per-channel API or CLI, but do remove their direct compiled-state mutation path.
- Do not change Pico firmware protocol or report shape.
- Do not add another persisted schedule representation.
- Do not make applying configuration wait synchronously for telemetry.

## Errors

- Invalid configuration stops before flashing.
- Flash failure leaves the saved configuration and timer state available for retry.
- A missing `r` response does not trigger another flash; the UI waits for normal telemetry.

## Tests

- Editor renders saved daily-window and unit values instead of reconstructing them.
- Applying a mixed cycle/daily controller creates the expected patterns and phases.
- One editor save calls the controller apply endpoint once and never calls the per-channel endpoint.
- Controller apply writes one complete state and invokes the flash operation once.
- API test page exposes examples for every supported scheduler write/report workflow.
