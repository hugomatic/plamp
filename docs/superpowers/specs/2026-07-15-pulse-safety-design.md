# Pulse safety

A GPIO pulse is a temporary force-on overlay, not a saved-state override.

- Reject a pulse when the latest host report already shows the channel on.
- The Pico independently rejects a pulse when the physical output is already on, covering stale-host-report races and overlapping pulses.
- While a pulse is active, the base schedule continues advancing.
- At pulse completion, remove the overlay and immediately apply the base schedule's current state. Never restore the value from pulse start.
- API rejection uses HTTP 409 with a clear `pin is already on` message. The existing UI displays that error; agents receive the same contract.

Tests execute generated firmware with a fake GPIO pin to prove rejection and the off-to-on schedule transition during a pulse.
