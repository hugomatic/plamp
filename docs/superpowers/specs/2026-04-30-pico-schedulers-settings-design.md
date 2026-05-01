# Pico Schedulers Settings Redesign

## Goal

Reshape the settings page so Pico scheduler configuration is organized around configured scheduler controllers instead of split across separate top-level Controllers and Devices sections.

The new design should:

- keep `System status / Peripherals` read-only
- show whether each detected peripheral is already assigned
- remove the separate top-level `Controllers` section
- replace the mixed device editor with a `Pico schedulers` section grouped by controller
- keep camera configuration unchanged

## Current Problem

The current settings page separates controller editing from device editing:

- controllers are edited in one table
- devices are edited in another table
- the relationship between a scheduler controller and its owned devices is implicit
- `System status / Peripherals` shows detected hardware, but not whether a peripheral is already assigned

This makes the page harder to scan and makes scheduler configuration feel split across unrelated blocks.

## User-Facing Design

### System Status / Peripherals

Keep this section status-only.

Add one new column:

- `Assigned`

Behavior:

- if a detected peripheral is assigned to a configured Pico scheduler controller, show that controller id
- if it is not assigned, show `Unassigned`
- no editing controls live in this table

This section remains the place to see all detected hardware, including hardware that has no scheduler block yet.

### Pico Schedulers

Replace the current top-level controller and device editing layout with a single `Pico schedulers` section.

Render one scheduler block per configured Pico scheduler controller that currently has at least one assigned device.

Each scheduler block contains two parts.

#### Controller fields

Show editable fields for the controller:

- `ID`
- `Label`
- `Assigned peripheral`
- `Report every seconds`

Rules:

- `Assigned peripheral` is a dropdown built from detected picos
- preserve the currently assigned serial in the dropdown even if the device is not currently detected
- `Report every seconds` edits the controller-level `report_every`
- controller `type` is not shown as an editable field in this UI because this section is only for Pico scheduler controllers

#### Device table

Below the controller fields, render a table containing only devices assigned to that controller.

Recommended columns:

- `ID`
- `Label`
- `Pin`
- `Type`
- `Editor`

Behavior:

- device rows stay editable
- adding a device inside a controller block creates a device assigned to that controller
- devices are grouped only under their controller

### Empty Controllers

Do not render scheduler blocks for controllers that have no devices.

Reason:

- unassigned hardware is already visible in `System status / Peripherals`
- empty scheduler blocks add noise and duplicate information

### Cameras

Leave the camera section unchanged in this slice.

## Data and Save Model

Keep the existing persisted config shape:

- `controllers`
- `devices`
- `cameras`

No backend schema change is required.

The UI is a presentation change over the existing config model:

- controller-level fields still write to `config.controllers[controller_id]`
- device rows still write to `config.devices[device_id]`
- device `controller` values still reference controller ids

### Save Behavior

Keep the existing combined save behavior through `PUT /api/config`.

This redesign should not introduce per-controller persistence endpoints.

Implications:

- the `Pico schedulers` editor submits one combined config payload
- controller renames must continue to rewrite device `controller` references in the submitted payload
- camera rows continue to save through the same combined config request as today

## Rendering Rules

When building the page:

1. read configured controllers
2. filter to Pico scheduler controllers
3. group configured devices by controller id
4. render only controllers that have at least one grouped device
5. compute peripheral assignment status for the read-only `System status / Peripherals` table from controller `pico_serial`

### Assignment Display Rules

For the `Assigned` column in `System status / Peripherals`:

- if one configured controller points at the detected serial, show that controller id
- if none point at it, show `Unassigned`
- if configured state is inconsistent and multiple controllers reference the same peripheral, show the assigned controller ids joined in a stable order

That last case should be visible rather than hidden, because it indicates conflicting config.

## Non-Goals

This slice does not:

- add inline editing to `System status / Peripherals`
- change camera configuration UX
- change controller validation rules
- change hardware detection behavior
- push firmware

## Risks and Edge Cases

### Controller Rename

Renaming a controller id is the riskiest part of this UI because device rows reference controller ids.

Requirement:

- preserve the current rename-safe behavior when building the combined config payload

### Undetected Assigned Peripheral

If a controller is assigned to a serial that is not currently detected:

- keep that serial visible/selectable in the controller dropdown
- do not silently clear the assignment

### Configured Controller With No Devices

This UI hides it intentionally.

That means:

- such controllers remain in config unless explicitly removed by the save logic
- implementation must decide whether the hidden controller is preserved or dropped

Recommended behavior:

- preserve hidden no-device scheduler controllers in the submitted config unless the user explicitly removes them through a supported path

This avoids destructive saves caused by a visibility rule.

## Testing

Update settings-page rendering tests to cover:

- `System status / Peripherals` includes the new `Assigned` column
- assigned controller ids appear for detected picos
- unassigned detected picos render `Unassigned`
- the old top-level `Controllers` section is not rendered
- the `Pico schedulers` section renders grouped controller blocks
- each controller block contains `ID`, `Label`, `Assigned peripheral`, and `Report every seconds`
- each controller block renders only that controller's device rows
- controllers with no devices do not render blocks
- existing camera section still renders
- combined save wiring still targets `PUT /api/config`

If implementation changes helper functions, add narrower tests around grouping and assignment labeling where useful.

## Implementation Outline

Expected code areas:

- `plamp_web/pages.py`
- `tests/test_pages.py`

Possible small supporting helpers may be added in `plamp_web/pages.py` if they reduce duplication around:

- peripheral assignment labeling
- scheduler controller grouping
- hidden controller preservation in submitted payload

## Recommendation

Proceed with the grouped-controller `Pico schedulers` layout while keeping save semantics and config shape stable.

This gives the page a better mental model without turning the backend into a new migration project.
