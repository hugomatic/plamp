# Atomic Scheduler Apply Design

## Goal

Save all channel schedules and flash the Pico once. Keep user-entered clock times and units in configuration; use Pico reports for runtime status.

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

The browser removes its current per-channel schedule POST loop. The per-channel API remains available for CLI use.

## Errors

- Invalid configuration stops before flashing.
- Flash failure leaves the saved configuration and timer state available for retry.
- A missing `r` response does not trigger another flash; the UI waits for normal telemetry.

## Tests

- Editor renders saved daily-window and unit values instead of reconstructing them.
- Applying a mixed cycle/daily controller creates the expected patterns and phases.
- One editor save calls the controller apply endpoint once and never calls the per-channel endpoint.
- Controller apply writes one complete state and invokes the flash operation once.
