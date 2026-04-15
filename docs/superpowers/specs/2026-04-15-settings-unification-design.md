# Settings Unification Design

## Overview

Issue `#19` should produce a real admin-page redesign, not a light merge of the old `/config` and `/settings` pages. The new `/settings` page becomes the single place to configure Plamp, inspect the machine, and perform careful host-level actions.

This design makes `/settings` the only admin page. The old `/config` route is removed entirely.

## Goals

- Make `/settings` the only admin page.
- Make `Plamp setup` the first and dominant section.
- Keep `System status` available, but visually secondary.
- Add a separate `Device control` section for cautious host-level actions.
- Add optional display labels without changing stable ids.
- Keep config as the source of truth for the main page.
- Make config changes affect `/` immediately, as they do now.
- Add hostname editing with an explicit confirm/apply flow.
- Leave room for future Wi-Fi editing without implementing it in this slice.

## Non-Goals

- No config migration step.
- No workspace or multi-node model.
- No `/config` compatibility route.
- No Wi-Fi editing in this slice.
- No change to the current rule that config wins over stray Pico-reported names.
- No attempt to guarantee the browser session survives risky host changes.

## Page Structure

`/settings` becomes one admin page with three clear bands:

1. `Plamp setup`
2. `System status`
3. `Device control`

The page should feel like one deliberate admin surface, not two old pages stacked together.

### Plamp setup

This is the main purpose of the page and appears first.

It contains editable sections for:

- Controllers
- Devices
- Cameras

Each section is task-oriented, with:

- short intro text
- editable table
- local save control
- clear validation feedback

### System status

This appears below setup and is visually secondary.

It contains compact read-only summaries for:

- Peripherals
- Network
- Software
- Storage

This section is for inspection, not primary workflow.

### Device control

This appears last and is visually cautious.

It contains host-level actions and settings that deserve explicit confirmation.

For this slice it includes:

- current hostname
- pending hostname field
- confirm/apply action
- warning text that reconnect or reboot may be needed

The section should visibly leave room for future controls such as Wi-Fi.

## Navigation

Main navigation becomes:

- `/`
- `/settings`
- `/api/test`

The `/settings` link may include a small gear icon.

There is no `/config` route in this design.

## Config Model

Keep the current top-level config model and extend it with optional `label` fields.

```json
{
  "controllers": {
    "pump_lights": {
      "pico_serial": "e66038b71387a039",
      "label": "Pump and lights"
    }
  },
  "devices": {
    "pump": {
      "controller": "pump_lights",
      "pin": 2,
      "editor": "cycle",
      "label": "Water pump"
    },
    "lights": {
      "controller": "pump_lights",
      "pin": 3,
      "editor": "clock_window",
      "label": "Main lights"
    }
  },
  "cameras": {
    "rpicam_cam0": {
      "label": "Tent camera"
    }
  }
}
```

Rules:

- ids stay stable and remain the config keys
- `label` is optional for controllers, devices, and cameras
- blank or missing `label` falls back to the id in the UI
- existing configs without labels continue to work

## Meaning Of Id And Label

Use two naming levels:

- `id`: stable internal key used by config, routes, and matching
- `label`: optional display text for the UI

This keeps matching stable while allowing higher-level naming.

## UI Behavior

### Controllers

Show both `ID` and `Label` columns.

Each row includes:

- `ID`
- `Label`
- assigned peripheral selector

The user-facing word is `Peripherals`, even if the saved field remains `pico_serial`.

### Devices

Show both `ID` and `Label` columns.

Each row includes:

- `ID`
- `Label`
- `Controller`
- `Pin`
- `Editor`

The editor choices remain `cycle` and `clock_window`.

### Cameras

Show both `ID` and `Label` columns.

Each row includes:

- `ID`
- `Label`
- detected summary

Camera naming is editable in this slice. Camera detection details remain status data.

## Hostname Control Behavior

Hostname editing belongs in `Device control`, not in the normal Plamp config sections.

Behavior:

- user can type a pending hostname
- no change is made until explicit confirm/apply
- apply action returns clear next-step text
- UI warns that reconnect or reboot may be needed
- UI does not pretend the current session will safely survive the change

This makes hostname editing available from the device itself, including a kiosk-style use case, without bundling it into the normal config save flow.

## API Shape

Keep current config section save endpoints for:

- controllers
- devices
- cameras

Add separate host-control endpoints for hostname:

- `GET /api/host-config`
- `POST /api/host-config/hostname`

This keeps risky host operations separate from normal Plamp config saves.

## Validation

Continue current validation and add optional label handling.

Rules:

- `ID` is required
- `Label` is optional
- unknown controller references on devices are rejected
- duplicate device pin per controller is rejected
- existing editor validation remains unchanged
- labels do not participate in identity

For hostname:

- reject invalid or empty hostname values
- return clear error text when apply fails
- return explicit follow-up guidance when apply succeeds

## Main Page Behavior

The main page remains config-driven.

Implications:

- adding or removing devices in config changes what `/` shows
- scheduling remains based on configured devices, not stray Pico event names
- display text may use labels where appropriate, but matching still uses ids and pins

## Wording

User-facing wording changes in this slice:

- `Picos` becomes `Peripherals`
- `/settings` is the admin page
- `Plamp setup`, `System status`, and `Device control` become the major section names

## Error Handling

- keep partial section saves as they work now
- preserve unrelated config sections when saving one section
- missing detected peripherals or cameras must not erase saved config
- hostname apply should be explicit about possible reconnect impact
- risky actions should be isolated in `Device control`

## Testing

Add or update tests for:

- `/settings` rendering the three-band layout
- absence of `/config`
- optional `label` support in config validation and section saves
- page render coverage for `ID` and `Label` columns
- main-page behavior still reflecting config changes immediately
- hostname read/apply endpoint behavior
- nav showing `/settings` and `/api/test`

## Recommended Implementation Shape

1. Extend config validation helpers to allow optional `label` fields.
2. Redesign `/settings` as a single admin page with three bands.
3. Move editable config sections into `Plamp setup`.
4. Move existing host and hardware summaries into `System status`.
5. Add `Device control` with hostname confirm/apply flow.
6. Remove the `/config` route and update navigation.
7. Update tests.

This keeps the system simple, makes `/settings` feel genuinely new, and leaves room for future Wi-Fi controls without taking that risk in this slice.
