# Pico Scheduler Controller Type Design

## Overview

Plamp needs controller settings that distinguish Pico scheduler controllers from future controller types. The immediate problem is that the Pico scheduler reporting interval is not configurable from settings, and putting scheduler-only fields on every controller would make future controls such as pH dosing confusing.

This design adds an explicit controller `type`, keeps scheduler output devices in the existing flat `devices` map, and renames the settings UI section so users understand those devices belong to Pico scheduler firmware.

## Goals

- Let settings edit the Pico scheduler reporting interval in seconds.
- Make controller firmware/runtime type explicit with `controllers.<id>.type`.
- Keep existing configs working by treating missing controller `type` as `pico_scheduler`.
- Keep the current flat `devices` config shape for this slice.
- Rename the settings device section to make it scheduler-specific.
- Limit timer dashboards, timer APIs, and Pico scheduler monitors to scheduler controllers.
- Leave room for future controller types without implementing them now.

## Non-Goals

- No migration to nested scheduler outputs under each controller.
- No pH dosing UI or runtime behavior in this slice.
- No generated single-file firmware bundle in this slice.
- No change to the Pico scheduler event format beyond sourcing `report_every` from controller config.
- No broad settings page redesign beyond the scheduler-specific fields and labels.

## Config Model

Controllers gain a `type` field. Existing controllers that omit it are interpreted as `pico_scheduler`.

```json
{
  "controllers": {
    "pump_n_lights": {
      "type": "pico_scheduler",
      "pico_serial": "e66038b71387a039",
      "report_every": 10
    }
  },
  "devices": {
    "pump": {
      "controller": "pump_n_lights",
      "pin": 3,
      "type": "gpio",
      "editor": "cycle"
    }
  },
  "cameras": {
    "picam0": {
      "detected_key": "rpicam_cam0"
    }
  }
}
```

Rules:

- `controllers.<id>.type` identifies the controller runtime or firmware type.
- The only implemented controller type in this slice is `pico_scheduler`.
- Missing controller `type` defaults to `pico_scheduler`.
- `controllers.<id>.report_every` is valid only for `type: "pico_scheduler"`.
- `report_every` is a positive integer number of seconds.
- Scheduler devices must reference a controller whose resolved type is `pico_scheduler`.
- Device `type` remains the output type for scheduler devices: `gpio` or `pwm`.

The overloaded field name `type` is acceptable because controller type and device output type live in different objects. The settings UI should label them distinctly as `Type` for controllers and `Output type` for scheduler devices.

## Settings UI

The controller table gains:

- `Type`
- `Report every seconds`

The `Type` selector includes `pico_scheduler` now. Future values can be added when their UI and validation exist.

`Report every seconds` is shown and saved for `pico_scheduler` controllers. Non-scheduler controller types should not allow scheduler-specific fields.

The `Devices` section is renamed to `Pico scheduler devices`.

Scheduler device rows keep the current fields:

- `ID`
- `Label`
- `Controller`
- `Pin`
- `Output type`
- `Editor`

The scheduler device `Controller` dropdown only lists controllers whose resolved type is `pico_scheduler`. This prevents users from assigning timer outputs to future non-scheduler controllers.

## Reporting Interval Ownership

`data/config.json` is the authoritative source for reporting cadence:

```text
controllers.<controller-id>.report_every
```

Timer state files remain the source for schedule events:

```text
data/timers/<controller-id>.json
```

Old timer files may still contain a top-level `report_every`, but it is treated as legacy data. It should not override controller config.

When applying state to a Pico scheduler controller, the server generates the Pico `state.json` from two sources:

- `report_every` from `data/config.json`
- `events` from `data/timers/<controller-id>.json`

The current firmware can continue to read `state.json` with both fields. The important change is that the generated file no longer treats timer JSON as the source of reporting cadence.

## Runtime Scope

Timer-specific runtime behavior only uses scheduler controllers:

- timer role discovery
- timer dashboard roles
- configured timer channel discovery
- monitor reconciliation
- Pico scheduler apply flow

Controllers with future non-scheduler types should remain visible in controller settings, but they should not appear in timer dashboards or scheduler device dropdowns.

## Validation

Validation should enforce:

- controller ids remain valid ids
- controller `type` defaults to `pico_scheduler` when missing
- unknown controller types are rejected until implemented
- `report_every` is positive integer seconds for scheduler controllers
- scheduler devices reference known scheduler controllers
- duplicate pin checks still apply per scheduler controller
- device `type` remains one of `gpio` or `pwm`
- device `editor` remains one of `cycle` or `clock_window`

Rejecting scheduler-only fields on non-scheduler controllers is preferred over silently ignoring them. Silent ignored config makes hardware setup harder to reason about.

## Firmware Generation Direction

This slice should not require a full firmware templating system. It should keep copying the existing `pico_scheduler/main.py`, but generate the copied `state.json` from config plus timer events at apply time.

A later slice can generate a single firmware file from config if that simplifies deployment. That later design should preserve the same ownership rule: controller config owns scheduler controller settings, and timer state owns schedule events.

## Testing

Tests should cover:

- controller validation accepts and defaults `type: "pico_scheduler"`
- controller validation accepts positive `report_every`
- controller validation rejects invalid `report_every`
- scheduler device validation rejects controllers that are not resolved as `pico_scheduler`
- settings page renders controller type and report interval fields
- settings page labels the section `Pico scheduler devices`
- scheduler device controller options exclude non-scheduler controllers
- timer role discovery excludes non-scheduler controllers
- generated Pico state uses controller `report_every` instead of timer JSON `report_every`

## Future Work

Future controller types need names and field models when they are implemented. A likely pH controller type can be added later without changing the scheduler design.
