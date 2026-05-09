# Controller-Owned Timers And Agri Dashboard Design

## Overview

Move Plamp from a flat controller/device config toward a controller-owned model where each controller contains its devices, timers, reporting cadence, and telemetry-derived health. The user edits one controller at a time, and applying any timer change reprograms the whole controller state.

The UI should move closer to the `agri-ui.png` direction: stronger visual hierarchy, device icons, a sequence/timeline view, and a controller health summary that makes sync freshness obvious.

This is a breaking config change, but the migration must preserve current values so existing controller names, device pins, editor types, labels, and timer settings are not lost.

## Goals

- Make the controller the primary unit of ownership in config, UI, and runtime state.
- Keep telemetry separate from telecommand so live widgets can continue showing actual device/controller state while edits are staged.
- Make it obvious that applying one timer change reprograms the whole controller.
- Include `report every N seconds` in controller edit mode because it is part of the same controller state.
- Add a controller health signal that reflects whether the periodic controller message is fresh or late.
- Update the dashboard look and information density toward the agri-style layout with icons, sequence view, and health.
- Preserve current values during migration from the existing flat schema.

## Non-Goals

- No per-timer partial apply in v1.
- No new event/command transport in v1.
- No attempt to keep the old flat schema as the canonical persisted shape.
- No redesign of unrelated settings pages outside the controller flow.
- No requirement to perfectly copy the reference image; the goal is to converge on its structure and feel.

## Proposed Config Shape

Canonical persisted state should be controller-owned.

Example:

```json
{
  "controllers": {
    "pump_n_lights": {
      "label": "Pump and lights",
      "pico_serial": "E661...",
      "report_every": 10,
      "devices": {
        "pumpON": {
          "pin": 3,
          "type": "gpio",
          "editor": "cycle"
        },
        "lightsON": {
          "pin": 2,
          "type": "gpio",
          "editor": "clock_window"
        }
      },
      "timers": [
        {
          "id": "pumpON",
          "pin": 3,
          "type": "gpio",
          "editor": "cycle",
          "schedule": {
            "on_at": "22:00",
            "off_at": "22:15"
          }
        },
        {
          "id": "lightsON",
          "pin": 2,
          "type": "gpio",
          "editor": "clock_window",
          "schedule": {
            "on_at": "06:00",
            "off_at": "23:00"
          }
        }
      ]
    }
  }
}
```

Rules:

- The controller owns both device metadata and timer state.
- Timer rows live inside the controller record.
- `report_every` is a controller-level setting and is edited with the controller.
- Existing values from the current schema must be migrated into the new shape.
- The migration should preserve stable ids, labels, pins, editor values, and schedule values.

## State Model

Use two separate state layers:

- Telemetry: the live controller state reported by the hardware.
- Telecommand: the staged edits the user is preparing to send.

Telemetry is the source of truth for the widgets shown during normal viewing. Telecommand is the source of truth for the edit form.

Telemetry should be able to represent at least:

- current timer state
- current reporting cadence
- last periodic message time
- controller identity and firmware/version metadata
- current sync status

The UI must not pretend telecommand is already active when the controller has not applied it yet.

## Apply Semantics

There is one apply action for the whole controller.

Behavior:

- Editing a timer stages a telecommand change.
- Editing `report every N seconds` stages a controller-level telecommand change.
- Pressing `Apply controller` sends the full controller state.
- Applying one timer change reprograms every timer in that controller.
- The controller state should be treated as a full sync payload, not a partial patch.

The UI should make the reset behavior explicit before saving. The warning should say, in substance, that updating any timer will reset and resend all timers in the controller.

## Health Model

Keep health simple and derived from telemetry freshness.

Proposed states:

- `Good` when the controller periodic message is current.
- `Bad` when the periodic message is late.

Implementation should avoid inventing extra health states unless a later transport problem makes them necessary. The key signal for now is whether the controller is talking on time.

If the system restarts and the controller is not yet synced, health should reflect that the controller is not in a trusted fresh state until telemetry resumes and a sync has happened.

## UI Design

The dashboard should move toward an agri-style controller card layout:

- controller summary at the top
- icon-driven device cards
- a sequence/timeline view for the controller
- a health strip that shows freshness clearly
- a controller edit view with all timers visible at once

Editing rules:

- When edit mode is on, each timer shows its parameters inline.
- Live widgets continue to show telemetry.
- Edit fields represent telecommand.
- There is one `Apply controller` button for the controller.
- `report every N seconds` appears in the same edit surface as the timers, but visually as a controller-level setting.

Suggested layout:

- Top row: controller name, health, report cadence, firmware/version, last message age
- Middle: timer sequence view and current-state cards
- Lower: controller device cards with icons and status
- Edit mode overlay or panel: timer fields and controller settings side by side

The UI should emphasize that the controller is one unit, not a set of unrelated rows.

## Migration

The migration must preserve current values.

Rules:

- Existing controller ids remain the controller ids.
- Existing labels, pico serial bindings, device pins, editor values, and schedule values are copied into the controller-owned shape.
- Legacy flat device records are not discarded during migration.
- The first save after migration should rewrite the new canonical controller-owned shape.
- If the old config cannot be mapped cleanly, the migration should fail loudly rather than silently dropping values.

Recommended migration strategy:

- Read the current flat schema.
- Group devices under their controller.
- Copy controller-level values into the controller record.
- Copy timer-specific values into controller timer rows.
- Rewrite the canonical config on next save.

## API And Runtime Implications

- The controller GET/PUT path remains the primary interface for controller state.
- The API should treat the whole controller payload as the unit of sync.
- The current implementation can keep using the existing full-state reprogramming path under the hood.
- The UI should not expose transport details beyond the controller apply warning.

Future command/event transport is intentionally out of scope for v1, but the schema should not block it later.

## Testing

- Migration tests that preserve current controller and device values.
- Tests that the controller-owned schema round-trips through config save/load.
- Tests that edit mode shows timer parameters without replacing telemetry widgets.
- Tests that one apply action sends a full controller state.
- Tests that `report_every` is part of controller editing and payload generation.
- Tests that health is `Good` for fresh telemetry and `Bad` for late telemetry.
- UI tests for the controller summary, icon-driven device cards, sequence view, and apply warning copy.
