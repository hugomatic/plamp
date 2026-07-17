# Single Scheduler Firmware Cleanup

## Decision

Plamp currently implements one Pico firmware family: `pico_scheduler`.
`pico_doser` is unused placeholder code and must not be accepted, generated,
listed, or described as a working controller type.

The scheduler generator produces one generic firmware application for a given
firmware source revision and `GeneratorOptions`. Controller IDs, pins, devices,
and schedules are persistent runtime state, not generated Python code. The two
build-time options remain `loop_sleep_ms=20` and `pwm_freq=1000`; automatic
rendering uses those defaults.

## Dosing boundary

Dosing pumps connected to Plamp8 use the existing GPIO pulse mechanism. A
human, fixed host algorithm, or agent may decide to request a dose. Plamp
validates the request and the Pico executes a bounded local pulse, then restores
the configured base state. Intelligence may choose an action but does not bypass
the deterministic pulse safety boundary.

No separate dosing firmware is needed. A future pH, EC, or PPM measurement MCU
may justify another firmware family, but its transport and data contract will be
designed when real hardware requirements exist. This cleanup does not reserve a
fake sensor family.

## Cleanup

- Delete the `pico_doser` generator package.
- Remove it from accepted controller types and firmware-family CLI output.
- Remove doser-specific API and CLI tests; replace them with rejection tests.
- Describe `pico_scheduler` as the only implemented family and its generator as
  schedule-independent.
- Mark the earlier multi-family design and plan as superseded historical work.

Existing configuration that names `pico_doser` fails validation explicitly.
There is no migration because no dosing firmware or deployed doser controller
exists.

