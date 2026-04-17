# Config Model Simplification Design

## Overview

Simplify Plamp config so persisted data contains only user-editable meaning. Live runtime and detected hardware stay separate. The main page must always be driven by config, with Pico data used only as runtime state for configured pins.

This design addresses two issue threads together:

- `#19` settings/config overlap
- `#15` config changes not affecting the main page

## Goals

- Persist only values the user can change.
- Make `data/config.json` the authority for what appears on `/`.
- Remove duplicated config structure that can drift.
- Use one vocabulary across config, UI, and runtime joins.
- Support removing controllers, devices, and cameras cleanly.

## Non-Goals

- No migration layer for older config files.
- No persisted snapshots of network, software, or storage.
- No Pico-owned UI structure.
- No higher-level labeling system in this slice.

## Config Model

`data/config.json` keeps only editable config:

```json
{
  "controllers": {
    "pump_lights": {}
  },
  "devices": {
    "pump": {
      "controller": "pump_lights",
      "pin": 2,
      "editor": "cycle"
    },
    "lights": {
      "controller": "pump_lights",
      "pin": 3,
      "editor": "clock_window"
    }
  },
  "cameras": {
    "cam0": {}
  }
}
```

Rules:

- Controllers are keyed by stable `id`.
- Devices are keyed by stable `id`.
- Cameras are keyed by stable `id`.
- Low-level hardware objects do not need per-object display names in this slice.
- Optional human-facing descriptions belong in a later higher-level layer, not in the hardware mapping model.

## Terminology

Use these terms consistently:

- `pin`, not `channel`
- `id`, not `name`, for hardware identity
- `editor`, not `default_editor`

The Pico firmware should report pin runtime data. It should not define the app's device naming model.

## Runtime Model

The app owns structure. The Pico only supplies runtime state.

- `/` is built from config every time.
- Config defines which devices exist and which controller/pin each one uses.
- Runtime joins use configured `controller` + `pin`.
- If a configured device has no runtime state, it still appears on `/`.
- If the Pico reports pins that are not configured, ignore them.
- If config adds or removes a device, `/` reflects that immediately after save.

This makes config authoritative and prevents Pico responses from changing the visible device list.

## Detected vs Persisted Data

Detected and runtime data remain separate from persisted config:

- detected peripherals
- detected cameras
- network
- software
- storage
- live scheduler or pin state

These belong in read-only settings or runtime responses, not in `data/config.json`.

## Delete Behavior

Delete must be first-class:

- Removing a device removes it from persisted config.
- Removing a controller must also remove or reject dependent devices.
- Removing a camera removes it from persisted config.
- Deleted items disappear from `/` immediately after save.

Validation should reject broken references such as a device pointing at a missing controller.

## API and Page Implications

- `/config` edits only persisted config.
- `/settings` stays read-only and focused on detected state.
- `/` reads config first, then overlays runtime state for configured pins.
- Any existing timer-related APIs should treat config as the source of structure.

The main page must not depend on a duplicated timer layout stored elsewhere.

## Testing

- Config validation tests for create, update, and delete flows.
- Tests that `/` reflects config additions immediately.
- Tests that `/` reflects config removals immediately.
- Tests that extra Pico pin data is ignored when not configured.
- Tests that the app uses `pin` terminology consistently in new behavior.
