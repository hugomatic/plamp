# Controller Payload And Status Tree Design

## Overview

Refine the controller tree around the real boundary the system has today:

- one controller-native payload goes down to the firmware
- one controller-native telemetry report comes back from the firmware
- host-side settings preserve human meaning that the firmware does not know about

This replaces the earlier assumption that Pico scheduler devices should be first-class child instances with their own telemetry nodes. The current firmware does not expose that boundary, so the persisted tree should not pretend it does.

## Goals

- Keep `/api/config` limited to persisted desired configuration.
- Move discovered hardware and host facts out of config responses.
- Rename the live resolved view from `/runtime` to `/api/status`.
- Represent each controller with `payload`, `settings`, and `telemetry`.
- Keep scheduler payloads pin/channel-oriented and free of semantic names such as `pump`.
- Preserve host-side concepts such as device name, icon, display order, and editor mode outside the firmware payload.
- Keep telemetry as the raw controller report instead of parsing it into host-owned per-device telemetry.

## Non-Goals

- No parsed per-device telemetry tree in this slice.
- No generic child-instance model for firmware-owned scheduler outputs.
- No partial controller updates or separate firmware commands for settings versus config.
- No compatibility promise for the current `/runtime` endpoint name.
- No attempt to redesign the Pico scheduler protocol beyond aligning the persisted model with the protocol that already exists.

## API Boundaries

Use these endpoint names:

| Endpoint | Meaning |
| --- | --- |
| `/api/config` | Persisted desired configuration only. |
| `/api/system` | Host facts and discovered hardware, such as detected Picos and cameras. |
| `/api/status` | Live resolved state: persisted config plus current controller telemetry and derived health/status. |

Rules:

- `/api/config` must not include `detected`.
- The current `detected` payload moves under `/api/system`.
- `/api/status` replaces the user-facing role currently served by `/runtime`.
- A short compatibility alias for `/runtime` is acceptable during implementation if it helps avoid breakage, but docs and UI should move to `/api/status`.

## Controller Shape

The controller node should match the actual system boundary:

```json
{
  "controllers": {
    "pump_n_lights": {
      "type": "pico_scheduler",
      "payload": {
        "pico_serial": "e66038b71387a039",
        "report_every": 10,
        "devices": [
          {
            "pin": 3,
            "type": "gpio",
            "pattern": [
              {"val": 1, "dur": 90},
              {"val": 0, "dur": 810}
            ]
          },
          {
            "pin": 2,
            "type": "gpio",
            "pattern": [
              {"val": 1, "dur": 61200},
              {"val": 0, "dur": 25200}
            ]
          }
        ]
      },
      "settings": {
        "devices": {
          "pump": {
            "pin": 3,
            "label": "Pump",
            "icon": "pump",
            "display_order": 0,
            "editor": {
              "kind": "cycle",
              "on_seconds": 90,
              "off_seconds": 810,
              "start_at_seconds": 0
            }
          },
          "lights": {
            "pin": 2,
            "label": "Lights",
            "icon": "light",
            "display_order": 1,
            "editor": {
              "kind": "daily_window",
              "on_time": "06:00",
              "off_time": "23:00"
            }
          }
        }
      },
      "telemetry": {
        "...": "raw last controller report"
      }
    }
  }
}
```

### Field Meanings

- `payload`: the exact controller-native document that is sent to the firmware.
- `settings`: host-native metadata and editing intent that are not sent to the firmware.
- `telemetry`: the raw controller-native document most recently reported by the firmware.

This vocabulary is deliberate:

- `payload` is clearer than `config` because it means “what this controller consumes.”
- `settings` remains useful for host/UI meaning above the firmware boundary.
- `telemetry` is the observed report from the controller, not a derived host projection.

## Device Identity

The Pico scheduler firmware identifies scheduled outputs by pin. Human concepts such as `pump` and `lights` are host-side meanings.

Rules:

- `payload.devices[*]` must contain only firmware-facing data such as `pin`, output type, and compiled schedule pattern.
- Semantic names such as `pump` must not appear in the payload.
- `settings.devices.<device_id>` stores the host-side mapping from semantic device id to firmware pin.
- The UI resolves a device through:

```text
settings.devices.<device_id>.pin -> payload.devices[*].pin
```

This keeps the human device stable if the physical mapping changes later.

## Editor Semantics

Host-side settings preserve the user's editing model even when several editor forms compile to the same firmware payload.

Initial supported editor kinds remain:

- `cycle`
- `daily_window`
- future `events`

Examples:

- `cycle` can preserve “on 90 seconds, off 810 seconds.”
- `daily_window` can preserve “06:00 to 23:00.”
- both compile into scheduler `pattern` data inside `payload`.

The firmware receives the compiled schedule. The host keeps the richer authoring intent in `settings.devices.<id>.editor`.

## Telemetry

Telemetry remains controller-granular in this slice.

Rules:

- store the last raw controller report at `controllers.<id>.telemetry`
- do not split telemetry into synthetic per-device nodes
- derived UI state may inspect the raw telemetry report as needed
- if a future firmware exposes independently addressable child instances, that firmware may introduce child telemetry later

This avoids unnecessary transformation work and preserves the controller's actual report shape.

## Migration

Migration from the current tree should:

1. Move `controllers.<id>.config.pico_serial` into `controllers.<id>.payload.pico_serial`.
2. Move `controllers.<id>.settings.report_every` into `controllers.<id>.payload.report_every`.
3. Compile current scheduler devices into `controllers.<id>.payload.devices`.
4. Move human-facing device data into `controllers.<id>.settings.devices`.
5. Add `controllers.<id>.telemetry` in live status responses.
6. Remove `detected` from `/api/config`.

Current values must be preserved:

- controller id
- Pico serial
- report cadence
- device ids
- pin assignments
- output types
- schedule meaning
- labels, icons, display order, visibility/programming semantics when present

## UI And CLI Implications

- UI pages continue to render semantic devices from `settings.devices`.
- UI apply actions regenerate the full controller `payload`.
- CLI and firmware-facing commands use `payload`.
- API test pages should demonstrate `/api/config`, `/api/system`, and `/api/status` distinctly.
- Help and README text must stop implying that discovered hardware is config.

## Testing

Required coverage:

- `/api/config` excludes detected hardware.
- `/api/system` includes detected Picos and cameras.
- `/api/status` returns live controller telemetry.
- scheduler payload generation strips semantic names and uses firmware-native pin data.
- `settings.devices` preserves semantic ids and editor metadata.
- editor modes round-trip through persistence and recompile to the same payload meaning.
- UI joins semantic devices to payload entries by pin.
- migration preserves existing live configuration values.

## Follow-Up Questions Explicitly Deferred

- Whether `/runtime` remains as a temporary alias and for how long.
- Whether non-scheduler firmware families also use `payload/settings/telemetry`.
- Whether controller telemetry should eventually persist to disk separately from live memory.
- Whether future independently addressable devices should become real child instances again for other firmware types.
