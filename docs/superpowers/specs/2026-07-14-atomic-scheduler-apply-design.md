# Atomic Scheduler Apply Design

## Goal

Make the controller schedule editor save every channel and flash a Pico exactly once, while preserving semantic editor metadata such as clock times and preferred cycle units.

## State Ownership

- Controller configuration is authoritative for editing intent: schedule kind, `on_time`, `off_time`, cycle seconds, and preferred display unit.
- Generated timer state is a compiled artifact containing Pico patterns and phase offsets.
- A fresh Pico `r` report is authoritative for observed runtime state only.
- Live reports may reconstruct editor values only when semantic configuration is absent; they must not overwrite configured editor values during normal editing.

## Save and Apply Flow

The dashboard collects all channel values and sends the complete controller configuration through the existing controllers configuration endpoint. It then calls the controller apply endpoint once.

The apply endpoint recompiles the complete timer state from the newly saved semantic controller configuration using the host clock for daily-window phase. It atomically writes that state, generates one complete `main.py`, and performs one Pico flash under the controller lock. The monitor's existing post-flash behavior reconnects and sends `r` once.

The dashboard removes its per-channel schedule POST loop. Per-channel endpoints remain available for CLI/API compatibility, but the controller editor does not call them.

## Editor Values

- Daily-window fields prefer configured `channel.editor.on_time` and `off_time`.
- Cycle fields continue to prefer configured seconds and `unit`.
- Live pattern reconstruction remains a fallback for legacy controllers without semantic editor metadata.

## Failure Behavior

- Configuration validation or compilation failure prevents flashing and returns an actionable error.
- Flash failure leaves the saved semantic configuration and compiled timer-state file available for retry.
- A temporarily missing post-flash report does not cause another flash. The dashboard reports that the apply was accepted and waits for telemetry.
- The next fresh report supplies runtime pattern and output status. `cycle_t` is not compared exactly because it advances continuously.

## Compatibility and Scope

- The Pico protocol and firmware format do not change.
- The existing `r` command and post-flash report request remain unchanged.
- The per-channel schedule API and CLI remain supported.
- No deployment is included until local tests pass and the user requests or approves deployment.

## Verification

- Unit-test compilation of a controller containing both a cycle channel and a 06:00–23:00 daily window.
- API-test that controller apply writes the newly compiled state and invokes `apply_timer_state` exactly once.
- Page-test that clock fields use saved semantic values and that the controller editor contains one apply request with no per-channel schedule requests.
- Run the narrow timer-schedule, page, and config-API test modules.
