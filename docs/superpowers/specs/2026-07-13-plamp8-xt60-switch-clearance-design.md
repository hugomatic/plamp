# Plamp8 XT60-to-Switch Clearance Design

## Goal

Prevent interference between each 12 V XT60 connector and its adjacent switch while preserving room for the switch state labels.

## Measured Hardware

- XT60 outside width: 34.25 mm.
- Switch outside diameter: 21 mm.
- Required edge-to-edge clearance: 2 mm.
- Required center-to-center spacing: `34.25 / 2 + 21 / 2 + 2 = 29.625 mm`.

The current XT60-mode layout places the XT60 at x = -10 mm and the switch at x = 16 mm, producing 26 mm center spacing. The hardware envelopes therefore overlap by 1.625 mm before clearance is added.

## Layout Change

Keep the switch at x = 16 mm and keep its `Auto`, `Off`, and `On` labels centered at x = 31 mm. Move the XT60 center 3.625 mm left, from x = -10 mm to x = -13.625 mm.

The resulting layout provides:

- 29.625 mm center-to-center spacing.
- 2 mm between the measured hardware envelopes.
- 4.25 mm between the XT60 envelope and the edge of the 70 mm channel plate.
- Unchanged space for the switch state labels on the right.

Only XT60 mode changes. Barrel-connector mode retains its existing connector, switch, and label positions.

## Implementation

Express the measured component envelopes and desired clearance as named parameters near the existing connector dimensions. Derive the XT60-specific connector offset from those parameters and the existing switch position so the physical constraint is visible and remains tunable.

The same derived connector position must continue to feed the modular DC channel, top panel, and sub-panel through `dc_connector_x()`.

## Verification

- Add a source-level geometry check for the 29.625 mm center spacing and 2 mm envelope clearance if the repository has an appropriate CAD test pattern; otherwise verify the equations directly from the named parameters.
- Render the `dc_barrel_channel`, `top_panel`, and `sub_panel` views with the part generator.
- Confirm every STL is non-empty and the OpenSCAD logs contain no empty-object or missing-include warnings.
- Confirm barrel mode retains its current positions.
