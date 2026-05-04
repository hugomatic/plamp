# Pico Scheduler Devices Payload Design

## Goal

Make the Pico scheduler firmware, server snapshot APIs, and CLI use one consistent domain model for scheduler state:

- firmware-specific command family: `pico-scheduler`
- firmware state field: `devices`
- no firmware-level `id` requirement
- no generic `timers` alias

This removes the confusing leak of the firmware's old internal `events` term into host-facing payloads.

## Problem

Today the system mixes two mental models:

- settings/config model: controllers and devices
- firmware/runtime model: `events`

That mismatch leaks into:

- Pico `state.json` input
- Pico serial report output
- server snapshot APIs
- CLI output
- UI and tests

The result is that host-facing snapshots look like scheduler event lists when the user expects controller state for devices.

## Design

### Firmware payload vocabulary

For the Pico scheduler firmware, the scheduler state is:

```json
{
  "report_every": 10,
  "devices": [
    {
      "pin": 2,
      "type": "gpio",
      "current_t": 0,
      "reschedule": 1,
      "pattern": [
        {"val": 1, "dur": 10},
        {"val": 0, "dur": 20}
      ]
    }
  ]
}
```

Rules:

- rename top-level `events` to `devices`
- keep `devices` as a list
- each list item describes one scheduled output device
- firmware identity is by `pin`
- `id` is not required by firmware input or output
- `pattern` stays as the per-device schedule program
- `devices` is the shared user-facing term across settings, API, CLI, and firmware payloads, even though firmware identity is still pin-based internally

### Firmware report output

Periodic Pico reports should use the same `devices` field:

```json
{
  "kind": "report",
  "content": {
    "devices": [
      {
        "pin": 2,
        "type": "gpio",
        "elapsed_t": 12,
        "cycle_t": 12,
        "reschedule": 1,
        "pattern": [
          {"val": 1, "dur": 10},
          {"val": 0, "dur": 20}
        ],
        "current_value": 0
      }
    ]
  }
}
```

Notes:

- this is still a stream of reports over time
- SSE transport events remain transport concepts only
- the payload content is device state, not domain `events`

### Server behavior

The server should stop exposing firmware `events` as a host-facing snapshot field for Pico scheduler state.

For Pico scheduler state:

- validate timer files using `devices`
- generate Pico `state.json` using `devices`
- read live monitor reports from `content.devices`
- expose snapshot APIs using `devices`

The existing timer routes may stay in place for now if they are still the transport path, but their payloads should use the firmware-specific device model for Pico scheduler controllers.

### CLI behavior

The CLI contract for this firmware family is:

```bash
plamp controllers list
plamp pico-scheduler list
plamp pico-scheduler get pump_lights
plamp pico-scheduler set pump_lights @state.json
plamp pico-scheduler channels set-schedule pump_lights lights @schedule.json
```

Rules:

- remove the `timers` alias
- keep `pico-scheduler` as the only scheduler firmware command family
- `pico-scheduler get` returns scheduler state with `devices`
- `controllers list` continues to group controller ids by firmware family

### Config and host ids

Host config still has user-facing device ids in `config.devices`. Those ids remain useful for UI and config editing.

But:

- Pico scheduler firmware does not require device ids
- firmware state identity is by pin
- host code may enrich firmware state with config metadata when rendering UI, but firmware payloads themselves should not depend on ids

## Compatibility

This slice should prefer consistency over long-lived dual naming, but a short transition in server parsing is acceptable during implementation if it reduces breakage while updating all call sites in one branch.

Acceptable transition behavior during the branch:

- server may temporarily accept both `events` and `devices`
- final outward payloads for this feature must use `devices`
- CLI docs and examples must stop using `timers`

## Impacted areas

- `pico_scheduler/main.py`
- `pico_scheduler/README.md`
- `pico_scheduler/state.json.example`
- `plamp_web/server.py`
- `plamp_web/timer_schedule.py`
- `plamp_web/pages.py`
- `plamp_cli/main.py`
- `plamp_cli/README.md`
- tests for config API, timer schedule, pages, and CLI

## Testing requirements

Required coverage:

- firmware-style state validation accepts `devices`
- generated Pico state uses `devices`
- live monitor snapshot parsing reads `content.devices`
- `/api/timers/{role}` snapshot payloads return `devices`
- schedule editing still works with `devices`
- CLI `pico-scheduler` commands use `devices`
- `timers` alias is removed
- UI pages still render live state correctly from `devices`

## Non-goals

- redesign `pattern`
- add firmware-level device ids
- create a generic multi-firmware scheduler abstraction in this slice
- rename transport-level SSE event names unless needed by the implementation
