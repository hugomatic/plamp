# Plamp8 top-to-sub-panel bonding

## Goal

Make the top panel feel straighter and more solid by adding interior contact
between it and the sub-panel, then use the existing XT60 and C13 screw axes to
clamp the two printed panels together. Preserve all connector locations,
rectangular openings, service pockets, and the raised USB mount.

## Structural approach

Use two complementary structures:

1. Add one continuous AC rib between the left and right socket groups.
2. Add one full-height captive-nut tower at every XT60 and C13 screw axis.

The rib and towers rise from the 5 mm sub-panel base to the underside of the
top panel. They are part of the production sub-panel, touch the assembled top
panel, and prevent the top from bowing into the internal 5 mm space.

Individual towers are preferred over continuous connector bridges because
they preserve connector and wiring access. The existing connector screw axes
are preferred over new panel holes because they add clamping without changing
the visible top-panel layout.

## AC rib

Add a 4 mm-wide rib running in Y at the X midpoint between the two AC socket
cutout centers. Derive its position from `left_ac_x`, `right_ac_x`, and
`outlet_feature_x`; do not freeze a duplicate coordinate.

The rib runs continuously from the inner face of the south perimeter ledge to
the south boundary of the DC section. It starts at `sub_panel_base_h`, ends at
`sub_panel_h`, and bonds to the perimeter ledge at one end and the existing DC
separator structure at the other. It must not enter either AC socket cutout,
switch cutout, screw bore, or the DC connector regions.

## Captive-nut towers

Add ten towers above the sub-panel:

- two towers at each of the four XT60 connectors;
- two towers at the C13 connector.

Every tower is centered on an existing vertical connector screw axis. Use an
11 mm nominal outer diameter, trimmed only by the existing connector opening
and surrounding production negatives. Each tower begins at
`sub_panel_base_h` and ends at `sub_panel_h`, making contact with the top-panel
underside in the assembled stack.

The XT60 towers follow `dc_channel_x()`, `dc_channel_y()`,
`dc_connector_x()`, and `xt60_screw_spacing`. The C13 towers follow
`c13_hardware_x`, `c13_hardware_y`, and `c13_screw_spacing`. Do not introduce
independent copies of those locations.

## Nut retention and loading

Use ordinary M3 hex nuts in roofed, side-loaded pockets. Reuse the repository's
calibrated M3 pocket and clearance dimensions rather than adding a second fit
standard. The nut cavity starts at the top of the sub-panel base. Its roof
tapers from the nut envelope to the vertical M3 screw bore within the remaining
tower height, avoiding an unsupported flat ceiling.

Each nut loads horizontally along X from its connector's rectangular opening:

- the left nut of a connector loads toward negative X;
- the right nut loads toward positive X;
- both loading mouths face inward toward the rectangular opening.

The entry slot joins the near side of the nut pocket and terminates there. It
must not continue through the screw axis or open through the tower's far wall.
The vertical screw bore remains distinct from the rectangular connector
opening, preserving the existing material bridge between them.

The roof retains each nut when the top panel and screws are removed. With the
screws installed, the nuts carry clamp load into the sub-panel towers and bond
the top panel to the sub-panel.

## Screw clearance

Do not make one screw length part of the CAD contract. Available M3 lengths are
8, 12, 16, and 20 mm. Continue the vertical screw bore below the nut as a blind
tip-clearance hole in the sub-panel base, stopping at least 1 mm above the
printed underside. After the geometry is generated, select the available screw
length that gives full nut engagement without bottoming in the blind bore.

The top-panel XT60 and C13 holes remain at their existing diameters and axes.
Do not add countersinks or new visible fastener holes.

## Production and coupon behavior

The production `sub_panel` contains the complete AC rib and all ten towers.
The `dc_connector_panel` and `c13_panel` paired views continue to use exact
crops of the production sub-panel, so they expose the real towers, loading
mouths, nut pockets, roofs, screw bores, and blind tip clearances. The top
coupon halves remain exact crops of the production top panel.

Do not modify the USB mount, other connector cutouts, labels, perimeter ledge,
or unrelated enclosure geometry. Do not commit generated STL or CSG files.

## Ready-made panel recipe

Add a `panels` preset for normal users. It expands, in order, to
`view:top_panel` and `view:sub_panel` and has the description "Printable top
and internal sub-panels". Keep `split-box` as the default preset.

The intended human workflow is:

```bash
plamp cad plan plamp8 --preset panels
plamp cad generate plamp8 --preset panels
```

Direct repeated `--view` selection remains available for advanced use, but it
is not the documented default for this test-print scenario.

## Verification

Add source-contract tests for the derived AC rib placement and full Y span,
the ten production tower axes, inward X loading directions, terminated entry
slots, roofed M3 pockets, and blind bores with at least 1 mm underside material.
Verify that existing XT60/C13 openings and screw axes are unchanged.

Validate Plamp8 metadata and verify that the `panels` preset expands to exactly
`top_panel` then `sub_panel`. Plan the `sub_panel`, `dc_connector_panel`, and
`c13_panel` views. Compile those views to CSG and inspect their logs for
warnings, errors, and assertions. Run the full Python suite. Final STL slicing,
nut insertion, screw selection, and physical rigidity checks occur on the
user's workstation.
