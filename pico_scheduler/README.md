# Pico Scheduler

`pico_scheduler` generates one generic MicroPython `main.py` for Raspberry Pi
Picos that run Plamp schedules. For a given firmware source revision and build
options, every controller receives the same application.

## Generation

The generator accepts a firmware revision and two build-time options:

```python
GeneratorOptions(loop_sleep_ms=20, pwm_freq=1000)
```

All inputs that can change the rendered application live under `src/`. The
firmware revision is the latest Git commit touching that directory; README and
example changes at the package root do not change firmware identity.

Automatic rendering uses these defaults. Controller IDs, pins, device lists,
and schedules are not generator inputs. The embedded revision identifies the
firmware sources that produced the application.

`plamp firmware generate` can render the generic source for inspection. The
normal upgrade path is `python -m plamp pico upgrade`, which also seeds both
persistent state slots and verifies the report after reset.

## Firmware contract

Generated firmware:

- runs GPIO and PWM schedules without the host;
- stays silent during routine schedule transitions;
- answers `r` with one newline-delimited JSON report;
- accepts one complete JSON `configure` document, persists it in alternating
  generation-numbered state files, applies it, and returns a matching report;
- answers `p <pin> <seconds>` with a report or error;
- rejects a pulse when the GPIO is already on;
- applies a pulse as a temporary overlay, then restores the scheduler's value.

The host requests a report before a schedule transaction. If the reported
firmware identity is missing or outdated, it seeds the committed state, copies
the generated application with `mpremote`, resets once, rediscovers USB, and
requires a valid matching report. Otherwise it sends the proposed state without
flashing or resetting the Pico.

The Pico reloads its newest valid persisted state after power loss. It resumes
the stored phase but cannot reconstruct time spent without power, so the host
must not claim wall-clock alignment without later clock reconciliation. See
[the current contract](../docs/spec-current.md).
