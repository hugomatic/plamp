# Controller health and honest scheduling

## Intent

Plamp must never imply that a schedule reached hardware when the controller is
unavailable. Controller health is a host observation based on a real protocol
exchange, not merely the existence of a serial device.

## Silent Pico

Pico firmware remains silent unless answering a command. It does not emit
periodic readiness messages, heartbeats, or reports that may accumulate while no
host is listening.

The host owns controller observation:

1. find the configured USB serial;
2. acquire the shared hardware lock;
3. open the current serial port;
4. send `r`;
5. receive and validate one complete report;
6. close the port and release the lock.

A successful exchange is `OK`. Any failed step is `ERROR` with its actual
reason. Temporary lock contention from another Plamp process is not a controller
error.

## Feedback timing

Linux USB add/remove events provide immediate physical connection feedback. An
add event triggers a report request; a remove event immediately marks the
controller `ERROR: not connected`.

While the service runs, the host requests a report every five seconds. This is a
fixed health responsibility, not a plant schedule setting, so the report interval
is removed from the schedule editor.

Operations request reports when evidence matters:

- flashing waits for a valid report after reconnection;
- pulse uses its command response and requests another report after the pulse
  finishes;
- schedule editing requests a fresh report before opening and verifies the report
  produced by flashing.

## Status and diagnostics

The user-facing status has only two outcomes:

- `OK`: the latest health exchange succeeded;
- `ERROR: <reason>`: the latest health exchange failed or no successful exchange
  has occurred.

Diagnostics retain the failed step, configured serial, discovered port when
available, timestamps, timeout information, and malformed or raw response lines.
The controller page and API expose the full record. The main page shows the
concise reason. Logs record state transitions and failed exchanges without
logging every successful heartbeat.

Status changes and reports reach browsers through SSE. The browser animates
deterministic timer progress locally at one-second resolution; this animation is
not presented as one-second hardware verification. The page may show when the
controller was last verified.

## Main-page behavior

The whole controller card is active only while status is `OK`. Otherwise it is
grayed out, displays the error, and disables schedule controls. Last reported
values may remain visible only when clearly marked stale.

USB removal, report failure, and recovery update the card without reloading the
page. A valid report restores the active card.

## Schedule contract

Scheduling is unavailable unless a fresh report succeeds. The browser check is
for immediate feedback; the server enforces the same condition so stale pages or
custom clients cannot bypass it.

A controller-wide schedule operation validates all proposed channel settings,
communicates with the Pico once, waits for its valid post-flash report, and only
then commits the desired configuration. A failed operation returns a non-2xx
response and leaves the previous desired schedule intact. Nothing is queued or
automatically applied after reconnection.

The existing behavior that catches a disconnected apply, saves the schedule,
and returns `success: true` is removed.

## Interfaces and verification

The shared controller library owns report, pulse, flash, locking, and diagnostic
results. The service uses that library and publishes its observations through
REST and SSE; direct CLI operations use the same library without depending on
the service.

Tests cover USB removal/addition, valid and invalid reports, timeouts, lock
contention, SSE status changes, controller-card disabling, schedule rejection
without file changes, successful single-flash scheduling, and pulse completion
verification. Sprout is the disconnected/reconnected hardware test target before
merging.
