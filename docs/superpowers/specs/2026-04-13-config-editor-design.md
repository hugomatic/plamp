# Config Editor Design

## Overview

Add a Config page for user-maintained hardware meaning and mappings on the local Raspberry Pi. Settings remains the place for runtime status and hardware introspection: host information, connected Pico boards, storage, tools, monitors, and detected Raspberry Pi camera details. Config answers a different question: what do the detected things mean to Plamp?

The first version is local-only. It does not configure remote nodes, USB webcams, or LAN discovery. The design should still produce a clean local config document that can later be served to an agent layer for node discovery.

## Goals

- Let the user name detected Pico controllers before mapping devices to them.
- Let the user map meaningful devices, such as `pump` and `lights`, to a named controller and Pico pin.
- Use existing Pico firmware vocabulary for device types, such as `gpio`, instead of inventing aliases like `gpio_actuator`.
- Let the user name local Raspberry Pi cameras and set the IR filter variant when software cannot detect it.
- Detect camera sensor/family/lens from `rpicam-hello --list-cameras` where available. Wide vs normal is detected when exposed by that command; NoIR remains user-confirmed.
- Keep current timer/Pico runtime state working. The Pico still needs its state file, and the config editor should not replace the runtime state format sent to the Pico.

## Non-Goals

- No remote Raspberry Pi node management in this slice.
- No USB webcam enumeration in this slice.
- No socket/output abstraction yet; use Pico pins directly for now.
- No robot/gantry actuator abstraction yet; reserve `actuator` for later higher-level hardware.
- No raw JSON-first editing experience.

## Conceptual Model

Use two layers:

- Detected status: live facts the server can introspect, such as connected Pico serials, ports, camera sensor, camera lens, and camera index.
- Configured meaning: user-maintained names and mappings, such as `pump_lights`, `pump`, `lights`, pin numbers, and camera IR filter.

Settings displays detected status. Config edits configured meaning.

## Config Shape

Store annotations and mappings under `hardware` in `data/config.json`:

```json
{
  "hardware": {
    "controllers": {
      "pico:e66038b71387a039": {
        "name": "pump_lights",
        "type": "pico_scheduler"
      }
    },
    "devices": {
      "pump": {
        "name": "Pump",
        "type": "gpio",
        "controller": "pico:e66038b71387a039",
        "pin": 3,
        "default_editor": "cycle"
      },
      "lights": {
        "name": "Lights",
        "type": "gpio",
        "controller": "pico:e66038b71387a039",
        "pin": 2,
        "default_editor": "clock_window"
      }
    },
    "cameras": {
      "rpicam:0": {
        "name": "Tent camera",
        "ir_filter": "unknown"
      }
    }
  }
}
```

`controllers` are keyed by stable detected identities. For Pico boards, use `pico:<serial>`. `devices` are keyed by stable device ids used by Plamp and Pico state, such as `pump`. `cameras` are keyed by local camera identifiers. In this slice use `rpicam:<index>`.

Do not persist camera sensor, model family, or lens as authoritative config in the first slice. Those are detected live and merged into the UI. If a camera disappears, the configured camera name remains, and the UI can show it as missing.

## Compatibility

The current app uses `timers` entries with roles, Pico serials, and optional channels. During the transition, keep that behavior working by preserving `timers` as a compatibility projection. The Config page writes the new `hardware` section and, when saving `pico_scheduler` controllers/devices, updates the corresponding `timers` entries so existing dashboard and timer APIs keep working. If `hardware` is absent, the page initializes its controller/device view from the existing `timers` config.

The Pico runtime state files under `data/timers/<role>.json` remain separate. They still contain the firmware event state and are still what the app sends to the Pico.

## UI

Add a `/config` page linked from Settings and the main navigation where practical. Settings remains read-only/status-oriented and should show detected Raspberry Pi camera model/sensor/lens after camera detection exists.

The Config page has three sections with section-level save buttons:

### Controllers

Show detected Pico boards and existing configured controllers. Each controller row includes:

- Detected identity, such as Pico serial and connection status.
- Name, such as `pump_lights`.
- Type, initially including `pico_scheduler`, `food_dispenser`, and `ph_dispenser`.

Users save this section with `Save controllers`.

### Devices

Show configured devices and allow adding rows. Each device row includes:

- Device id, such as `pump`.
- Display name, such as `Pump`.
- Type, initially `gpio`.
- Controller, selected from named controllers.
- Pin number.
- Default editor, such as `cycle` or `clock_window` for scheduler devices.

Users save this section with `Save devices`.

### Cameras

Show detected local Raspberry Pi cameras and existing configured camera names. Each camera row includes:

- Camera key, such as `rpicam:0`.
- Detected sensor/family/lens, such as `imx708 wide`.
- Name, such as `Tent camera`.
- IR filter: `unknown`, `normal`, or `noir`.

Users save this section with `Save cameras`.

## API

Fetch a merged view for the page:

- `GET /api/config`

Return saved config plus detected choices needed for dropdowns and status display. Keep `detected` separate from `config` in the response so clients do not confuse live status with persisted settings.

Save sections independently:

- `PUT /api/config/controllers`
- `PUT /api/config/devices`
- `PUT /api/config/cameras`

Each endpoint validates only its section and preserves the other sections. Invalid mappings should produce clear 422 responses. Missing/unplugged detected hardware should not force deletion of saved config.

## Camera Detection

Detect local Raspberry Pi cameras with `rpicam-hello --list-cameras`, falling back to `libcamera-hello --list-cameras` if needed. Parse camera index, sensor/family, and lens when available. Wide vs normal should be detected when present in command output. NoIR should remain a user-confirmed field because it is not reliably distinguishable from the sensor name alone.

Camera capture remains compatible with the current one-camera capture path in the first slice. Passing a camera selector to the capture script can be added later after the settings/config model is in place.

## Error Handling

- Preserve configured controllers, devices, and cameras even when detected hardware is missing.
- Show missing hardware as missing in the UI rather than deleting it.
- Reject duplicate controller names only if they would make the UI ambiguous; controller keys remain the source of truth.
- Reject device mappings that reference unknown configured controllers.
- Reject invalid pins for `gpio` devices when validation can determine the pin is invalid.
- Reject unsupported `ir_filter` values.

## Testing

- Unit-test config validation for controllers, devices, cameras, invalid references, and invalid camera IR filter values.
- Unit-test camera detection parsing with sample `rpicam-hello --list-cameras` output, including a wide camera case.
- Page-render tests for the Config page sections and section save controls.
- API tests for `GET /api/config` and the section `PUT` endpoints.
- Regression tests that existing timer state APIs continue to work during the transition.
