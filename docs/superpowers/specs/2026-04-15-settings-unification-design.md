# Settings Unification Design

## Overview

Issue `#19` asks for a single page that combines Plamp configuration with the machine and hardware status currently shown elsewhere. The goal is one clear admin page, not a migration or a new workspace model.

This design makes `/settings` the main admin page. It will contain editable Plamp configuration first, then read-only host and hardware status below it. `/config` will become a redirect to `/settings`.

## Goals

- Make `/settings` the single page for Plamp admin work.
- Put editable Plamp config first: controllers, devices, and cameras.
- Keep host and detected hardware information visible on the same page, but read-only in this slice.
- Rename `Picos` to `Peripherals` in the UI.
- Add optional display labels without changing stable ids.
- Keep config as the source of truth for the main page.
- Make config changes affect `/` immediately, as they do now.

## Non-Goals

- No config migration step.
- No workspace or multi-node model.
- No change to the underlying runtime authority rules: config still wins over what a Pico reports.
- No renaming of internal JSON or API fields from `picos` in this slice.
- No editing of network, software, storage, or detected peripheral status in this slice.

## Page Shape

`/settings` becomes the main admin page with this order:

1. Editable Plamp config
2. Read-only machine and hardware status

The editable Plamp config section contains:

- Controllers
- Devices
- Cameras

The read-only status section contains:

- Peripherals
- Network
- Software
- Storage

`/config` will redirect to `/settings`.

## Config Model

Keep the current top-level config-driven model and extend it with optional labels.

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

- Ids stay stable and remain the config keys.
- `label` is optional for controllers, devices, and cameras.
- A blank or missing `label` means the UI falls back to the id.
- Existing configs without labels continue to work.

## Meaning Of Id And Label

Use two levels of naming:

- `id`: stable key used by config, routes, and internal matching
- `label`: optional higher-level display text for the UI

This keeps matching and saved references stable while letting the user show friendlier names.

## UI Behavior

### Controllers

Show both `ID` and `Label` columns.

Each row includes:

- `ID`
- `Label`
- assigned peripheral selector

UI wording says `Peripherals`, but the saved field remains `pico_serial`.

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

This slice keeps camera detection read-only, while camera naming stays editable.

### Status Sections

Peripherals, network, software, and storage stay read-only.

These sections move onto `/settings` below the editable config area. They do not get save controls in this slice.

## Routing

- `GET /settings` renders the combined page.
- `GET /config` redirects to `/settings`.
- Existing config section save endpoints remain in place.

This keeps the current save flow and avoids extra API churn.

## Validation

Continue current validation and add optional label handling.

Rules:

- `ID` is required.
- `Label` is optional.
- Unknown controller references on devices are rejected.
- Duplicate device pin per controller is rejected.
- Existing editor validation remains unchanged.
- Labels are plain strings and do not participate in identity.

## Main Page Behavior

The main page remains config-driven.

Implications:

- Adding or removing devices in config changes what `/` shows.
- Scheduling remains based on configured devices, not stray Pico event names.
- Display text may use labels where appropriate, but matching still uses ids and pins.

## Wording

User-facing wording changes in this slice:

- `Picos` becomes `Peripherals` on `/settings`.
- Internal config keys and APIs may still use existing names such as `pico_serial`.

This keeps the user vocabulary cleaner without creating a migration.

## Error Handling

- Keep partial section saves as they work now.
- Preserve unrelated config sections when saving one section.
- Redirecting `/config` should be simple and unconditional.
- Missing detected peripherals or cameras should not erase saved config.

## Testing

Add or update tests for:

- combined `/settings` page render
- `/config` redirect to `/settings`
- optional `label` support in config validation and section saves
- page render coverage for `ID` and `Label` columns
- existing main-page behavior still reflecting config changes immediately
- existing status sections still render on the merged page

## Recommended Implementation Shape

1. Extend config validation helpers to allow optional `label` fields.
2. Move config form rendering into `/settings`.
3. Append existing read-only status sections below the config forms.
4. Change `/config` to redirect.
5. Update tests.

This keeps the change local, preserves the current config APIs, and matches the current simple-system constraint.
