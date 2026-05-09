# Controller-Owned Timers And Agri Dashboard Design

## Overview

Move Plamp from the current flat `controllers` + `devices` config toward a controller-owned model. A controller owns the devices it programs, each device owns its timer schedule, and cameras remain top-level peripherals that can opt into the same timeline view.

The UI should follow the agri dashboard direction: a compact hostname chip, one top-level health light, controller cards, explicit device icons, centered timeline lanes, per-camera snapshot sections, and an edit panel that appears only when the user is changing controller state.

This is a breaking config change, but migration must preserve current values: controller ids, serial bindings, report cadence, device ids, pins, pin types, timer editor modes, schedule values, camera settings, capture paths, and the new host color choice.

## Goals

- Make each controller the primary owner of its programmable devices.
- Keep cameras top-level, while allowing each camera to appear in the same timeline as a controller.
- Keep telemetry and telecommand separate: widgets show live reported state, edit fields show staged commands.
- Make one controller apply action send a full controller state.
- Preserve distinct timer editor modes: `cycle`, `clock_window` / 24h, and future `events`.
- Move disabled and hidden behavior out of timer editor mode so the timer editor remains about how time is specified.
- Persist the hostname chip color in `config.json` so different Plamps can be visually distinguished.
- Persist device icon and display order in config.
- Render a generic `other` icon for unforeseen devices such as ionizers or air purifiers.
- Show one camera section per camera, with snapshot preview, same-scale timeline lane, capture delay, and capture list.

## Non-Goals

- No partial per-timer apply in v1.
- No command/event transport in v1.
- No weekly or monthly scheduling in this controller timer slice.
- No hidden inference from ids such as mapping `lights` to the light icon.
- No prominent firmware-version dashboard hero item.
- No always-visible controller reset warning.
- No attempt to keep the old flat `devices` object as canonical.

## Canonical Config Shape

`data/config.json` remains the persisted authority for user-editable intent. Runtime telemetry, capture files, health, uptime, and hostname are not persisted here unless explicitly listed.

```json
{
  "appearance": {
    "host_color": "#204b33"
  },
  "controllers": {
    "pump_n_lights": {
      "type": "pico_scheduler",
      "label": "Pump and lights",
      "pico_serial": "e66038b71387a039",
      "report_every": 10,
      "devices": {
        "pump": {
          "label": "Pump",
          "display_order": 0,
          "pin": 3,
          "type": "gpio",
          "icon": "pump",
          "visibility": "visible",
          "programming": "enabled",
          "timer": {
            "editor": "cycle",
            "schedule": {
              "mode": "cycle",
              "on_seconds": 90,
              "off_seconds": 810,
              "start_at_seconds": 0
            }
          }
        },
        "lights": {
          "label": "Lights",
          "display_order": 1,
          "pin": 2,
          "type": "gpio",
          "icon": "light",
          "visibility": "visible",
          "programming": "enabled",
          "timer": {
            "editor": "clock_window",
            "schedule": {
              "mode": "clock_window",
              "on_time": "06:00",
              "off_time": "23:00"
            }
          }
        },
        "fan": {
          "label": "Fan",
          "display_order": 2,
          "pin": 4,
          "type": "gpio",
          "icon": "fan",
          "visibility": "visible",
          "programming": "enabled",
          "timer": {
            "editor": "clock_window",
            "schedule": {
              "mode": "clock_window",
              "on_time": "08:00",
              "off_time": "22:00"
            }
          }
        }
      }
    }
  },
  "cameras": {
    "rpicam_cam0": {
      "label": "Tent camera",
      "detected_key": "rpicam_cam0",
      "capture_dir": "data/grow/grows/grow-thai-basil-siam-queen-2026-03-27/captures",
      "enabled": true,
      "auto_enabled": true,
      "capture_every_seconds": 3600,
      "manual_prefix": "manual",
      "auto_prefix": "auto",
      "autofocus_mode": "auto",
      "autofocus_delay_ms": 1500,
      "timeline": {
        "controller": "pump_n_lights",
        "display_order": 3,
        "icon": "camera",
        "capture_delay_seconds": 300,
        "align_with": {
          "device": "fan",
          "transition": "off"
        }
      }
    }
  }
}
```

## Config Ownership Map

These fields are persisted in `config.json`:

| Concept | Config path | Notes |
| --- | --- | --- |
| Host chip color | `appearance.host_color` | Used to distinguish Plamps. Hostname itself comes from the OS. |
| Controller identity | `controllers.<id>` | Controller id remains the stable config key. |
| Controller label | `controllers.<id>.label` | Human label, optional. |
| Pico serial | `controllers.<id>.pico_serial` | Binding to hardware. |
| Report cadence | `controllers.<id>.report_every` | Edited in controller edit mode and applied with the full controller. |
| Device identity | `controllers.<id>.devices.<device_id>` | Device id remains stable and is not inferred from label/icon. |
| Device hardware | `pin`, `type` | `type` remains `gpio` or `pwm`. |
| Device icon | `icon` | User-selected. Unknown devices use `other`. |
| Device order | `display_order` | Drives device card order and timeline lane order. |
| Device visibility | `visibility` | `visible` or `hidden`. Hidden devices are omitted from the dashboard. |
| Device programming | `programming` | `enabled` or `disabled`. Disabled devices can be visible but are not programmed. |
| Timer editor | `timer.editor` | `cycle`, `clock_window`, or future `events`. |
| Timer schedule | `timer.schedule` | Shape depends on `timer.editor`. |
| Camera settings | `cameras.<id>` | Existing camera settings stay top-level. |
| Camera timeline placement | `cameras.<id>.timeline` | Lets camera lanes align visually with controller device lanes. |
| Camera capture delay | `cameras.<id>.timeline.capture_delay_seconds` | Shows intended delay such as capture 5 minutes after fan off. |

These are runtime-only and are not persisted in `config.json`:

- live GPIO value
- current timer position
- last heartbeat time
- controller health
- uptime
- snapshot thumbnails and capture list contents
- current hostname
- firmware version unless a later feature makes version reconciliation user-editable

## Timer Editors

Timer editor mode is not the same as visibility or programming state.

- `cycle`: repeating on/off duration, such as pump on for 90 seconds and off for 810 seconds.
- `clock_window`: a daily 24h window, such as lights on at `06:00` and off at `23:00`.
- `events`: reserved for later event-based scheduling.

Disabled and hidden behavior should not remain editor modes in the new schema:

- current `editor: "disabled"` migrates to `programming: "disabled"` and `visibility: "visible"`
- current `editor: "hidden"` migrates to `programming: "disabled"` and `visibility: "hidden"`
- current `editor: "cycle"` migrates to `timer.editor: "cycle"`
- current `editor: "clock_window"` migrates to `timer.editor: "clock_window"`

If an old device has no explicit schedule, migration should preserve the editor mode and create the smallest valid default schedule for that editor, then let the user adjust it in edit mode.

## Telemetry And Telecommand

Use two separate state layers:

- Telemetry is live controller truth reported by hardware.
- Telecommand is the staged config the user is editing.

Normal widgets show telemetry. Edit fields show telecommand. The UI must not make staged values look applied before the controller accepts them.

Telemetry should include enough state to show:

- device on/off value
- timer progress and next transition when available
- report cadence currently running on the controller
- last heartbeat age
- sync status

## Apply Semantics

There is one apply action for the whole controller.

Behavior:

- Editing any timer stages a controller telecommand change.
- Editing `report_every`, icon, device order, visibility, or programming state stages a controller telecommand change.
- Pressing `Apply all changes to Controller` sends the full controller state.
- The reset warning appears only inside edit mode, next to the fields and apply button.
- The UI copy should be direct: updating any timer resets and resends all timers in this controller.

## Health Model

Use one top-level check-engine style health light for the app, with compact per-controller codes.

Base rule:

- `Good` when controller periodic messages are current.
- `Bad` when any expected controller periodic message is late.

The health light is derived from telemetry freshness, not from config. Controller rows can show small codes such as `OK`, `LATE`, `DISABLED`, or `HIDDEN` where useful.

## Dashboard UI

Default view:

- hostname chip showing `tower`, not `tower.local`
- host color from `appearance.host_color`
- uptime
- one top-level health light
- list of controller cards
- nested device cards inside each controller
- timer lanes ordered by `display_order`
- one camera section per camera that has timeline config
- capture list under each camera section

Edit mode:

- opens a controller edit panel above telemetry
- shows controller settings such as `report_every`
- shows each device timer editor
- shows icon selector, order control, visibility, and programming state
- shows one apply button for the controller
- shows the reset warning only while editing

Timeline behavior:

- the 24h view has a 0 to 24 hour scale
- orange means ON for every device
- pump cycle lanes render as segmented/dotted on/off intervals
- current time is a vertical marker
- when zooming, the marker stays centered and the timeline scrolls underneath it
- camera lanes use the same time scale as controller lanes
- camera sections show snapshot preview, capture delay, and capture history

## Camera UI

Each configured camera with timeline metadata gets its own section.

Each camera section shows:

- last or selected snapshot preview
- same-scale timeline lane
- scheduled captures as snapshot markers
- capture delay label such as `5 min after fan off`
- capture list with thumbnails and timestamps

The camera lane does not show on/off state. It shows captures. Camera alignment is visual and config-driven; the agent can later inspect drift by comparing capture timestamps with controller telemetry.

## Migration

Migration reads the current flat shape:

```json
{
  "controllers": {
    "pump_n_lights": {
      "type": "pico_scheduler",
      "report_every": 10,
      "pico_serial": "e66038b71387a039"
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
  "cameras": {}
}
```

Migration writes the new canonical shape:

- controllers stay keyed by the same id
- each flat device moves under `controllers.<controller>.devices`
- device id, label, pin, type, and editor mode are preserved
- `editor` becomes `timer.editor` unless it was `disabled` or `hidden`
- `disabled` becomes `programming: "disabled"`
- `hidden` becomes `visibility: "hidden"`
- existing cameras stay top-level
- existing camera capture settings and capture paths are preserved
- missing icons become `other`
- missing display orders are assigned by stable input order
- missing host color gets a conservative default

Migration must fail loudly if a device references a missing controller, if two devices use the same controller pin, or if a value cannot be mapped without losing meaning.

## API And Runtime Implications

- `GET /api/controllers/{controller}` returns controller telemetry plus controller config context.
- `PUT /api/controllers/{controller}` applies the full controller state.
- Existing full-state Pico programming remains the v1 transport.
- Camera captures and capture lists are served from camera/capture APIs and joined into the dashboard by camera id.
- The UI should not expose transport details beyond the edit-mode reset warning.

Future event transport remains compatible because timer mode is explicit and `events` has a reserved place.

## Testing

- Config validation tests for the new `appearance`, controller-owned devices, camera timeline metadata, and timer editor modes.
- Migration tests that preserve current controller, device, and camera values.
- Tests that old `disabled` and `hidden` editor values migrate into `programming` and `visibility`.
- Tests that unknown device icons render as `other`.
- Tests that controller-owned config round-trips through save/load.
- Tests that edit mode shows telecommand fields without replacing telemetry widgets.
- Tests that apply sends a full controller state.
- Tests that `report_every` is part of controller edit/apply.
- Tests that health is `Good` for fresh telemetry and `Bad` for late telemetry.
- UI tests for hostname chip, host color, controller list, icon selector, order controls, centered timeline, per-camera snapshot sections, capture lists, and edit-only reset warning.
