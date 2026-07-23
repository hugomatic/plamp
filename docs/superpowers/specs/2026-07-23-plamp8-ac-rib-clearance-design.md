# Plamp8 AC Rib Clearance Design

## Goal

Move the existing full-height AC bonding rib away from the left socket's switch
openings while preserving its structural connection between the top panel and
sub-panel.

## Root Cause

The current rib is centered between the two AC socket holes. That calculation
ignores the two switch openings located to the right of the left socket. In
socket-relative coordinates, the left switch envelope ends at X = -24 mm while
the 4 mm rib begins at X = -19 mm, leaving only 5 mm clearance. The right edge
of the rib has 28.5 mm clearance to the right socket's expanded access opening.

## Placement

Derive the usable horizontal corridor from production cutter envelopes:

- The corridor's left edge is the right edge of the left socket's switch
  opening: `left_ac_x + outlet_toggle_x + sub_panel_switch_w / 2`.
- The corridor's right edge is the left edge of the right socket's complete
  sub-panel opening, including its 5 mm terminal-access extension:
  `right_ac_x + outlet_feature_x - sub_panel_socket_w / 2
  - sub_panel_socket_side_access_w`.
- The rib center is the midpoint of those two edges, with `layout_offset_x`
  applied for the production sub-panel coordinate system.

With the current dimensions, the corridor spans X = -24 through 13.5 mm. The
4 mm rib moves from X = -19..-15 to X = -7.25..-3.25, leaving 16.75 mm on each
side.

## Preserved Geometry

Keep the rib width at 4 mm. Preserve its full Y span from the inner south ledge
to the DC section, its Z span from `sub_panel_base_h` to `sub_panel_h`, both AC
socket centers, all socket/switch/access openings, and all top-panel geometry.
The production `ac_duplex_panel` coupon continues to crop the exact sub-panel
geometry and therefore shows the corrected rib placement.

## Verification

Add a source-contract regression test that freezes the two corridor edges,
midpoint-derived rib center, and equal 16.75 mm clearances. Keep the existing
rib dimension and production-coupon contracts passing. Compile `sub_panel` and
`ac_duplex_panel` to non-empty CSG files without warnings, errors, or failed
assertions, then run the complete repository test suite and CAD metadata
validation. Do not commit generated artifacts.
