# Plamp8 AC Terminal Access Design

## Goal

Expose all five AC socket terminal screws through the internal sub-panel while
preserving the existing top panel, socket centers, main socket openings, and AC
panel-bonding rib.

## Geometry

Each of the two AC socket locations keeps its existing centered 35 x 70 mm
sub-panel opening. A dedicated `sub_panel_socket_negative()` cutter unions that
opening with three outward extensions:

- One 5 x 10 mm ground-terminal notch extends from the opening's top-right
  corner: 5 mm farther in positive X and 10 mm downward from the top edge.
- One 5 x 25 mm left terminal notch extends 5 mm farther in negative X. Its top
  edge is 27 mm below the main opening's top edge and it extends downward.
- One matching 5 x 25 mm right terminal notch extends 5 mm farther in positive
  X at the same Y range.

The dimensions and edge-relative offsets are named parameters. Boolean overlap
uses the existing `boolean_shim` so the extensions form one clean opening
without changing their nominal external dimensions.

## Integration

`sub_panel_8ch_negative()` calls the new cutter at the existing socket center
for both `left_ac_x` and `right_ac_x`. The top-panel `outlet_cover_negative()`
geometry remains unchanged. Because `ac_duplex_panel` crops the production
sub-panel, its paired sub-panel coupon receives the same access notches without
separate coupon geometry.

The existing 4 mm AC bonding rib remains centered between the two socket
groups. The new outward notches remain local to each socket opening and do not
move or trim that rib.

## Verification

Add a source-contract regression test that freezes:

- the 5 x 10 mm ground notch;
- the two 5 x 25 mm side notches;
- the 27 mm top-edge offset;
- outward X placement and downward Y placement;
- exactly two production calls to `sub_panel_socket_negative()`; and
- continued use of the unchanged top-panel socket cutter.

Run the focused Plamp8 tests, compile `sub_panel` and `ac_duplex_panel` to
non-empty CSG files without warnings or assertions, validate the CAD metadata,
and run the complete repository test suite. Do not commit generated artifacts.
