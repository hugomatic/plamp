# Plamp8 Assembly Truth and Fit Corrections Design

**Date:** 2026-07-21

## Goal

Correct four observed Plamp8 print/assembly problems without changing the
enclosure stack:

- make every wall placement in `assembly` and fused `box` a physically
  realizable rotation rather than a reflection;
- put the floor revision where it can be read from inside the open box;
- give all four XT60 faces usable clearance while organizing and supporting
  the top/sub-panel service area; and
- make the corner-wall M3 nut catches accept the measured nuts without their
  current axial looseness.

The fixes remain parametric in `things/plamp8/plamp8.scad`. Source-contract
tests in `tests/test_things_cad_scripts.py` protect the dimensions,
handedness, and unchanged stack. Asymmetric floor locator keys remain a
deferred stretch goal.

## Wall coordinate and handedness contract

Wall-local coordinates remain authoritative: X runs along the wall, Y runs
along enclosure height/the corner-screw axis, and Z runs from the exterior
face toward the assembled box interior. A wall context transform is valid
only when the determinant of its 3x3 orientation block is `+1`. A determinant
of `-1` is a reflection and cannot describe placement of the printed part.

The existing NORTH transform is already correct and stays byte-for-byte
unchanged:

```scad
[
    [1, 0, 0, 0],
    [0, 0, -1, box_d],
    [0, 1, 0, -box_h],
    [0, 0, 0, 1]
]
```

SOUTH, WEST, and EAST use these proper rotations:

```scad
// SOUTH
[
    [-1, 0, 0, box_w],
    [0, 0, 1, 0],
    [0, 1, 0, -box_h],
    [0, 0, 0, 1]
]

// WEST
[
    [0, 0, 1, 0],
    [1, 0, 0, 0],
    [0, 1, 0, -box_h],
    [0, 0, 0, 1]
]

// EAST
[
    [0, 0, -1, box_w],
    [-1, 0, 0, box_d],
    [0, 1, 0, -box_h],
    [0, 0, 0, 1]
]
```

All four orientation blocks are orthogonal signed-permutation matrices with
determinant `+1`. The translations retain the same north/south/east/west box
planes. Consequently `NORTH`, `SOUTH`, `EAST`, `WEST`, and each wall revision
read normally in assembly; the CAD no longer obtains apparently correct hole
placement by mirroring text and geometry.

Half-wall ventilation becomes explicit instead of being hidden inside
`vent_mode = "half"`. Add `vent_side = "right"` to `flat_wall()`,
`wall_vent_negatives()`, `wall_revision_negative()`, and
`wall_stiffening_ribs()`. Valid half sides are `"left"` and `"right"` and are
asserted. `north_wall()` explicitly selects `"right"`; `south_wall()`
explicitly selects `"left"`. The left/right selection controls the vent-grid
range, the mirrored half-wall rib X positions, and revision placement. A
half-vented wall always engraves its revision at the center of the non-vented
half (`length / 4` or `3 * length / 4`), never over its holes. SOUTH therefore
has left-side vents in its printable source and the required left-side holes
when its readable physical wall is installed.

No asymmetric locator key, duplicate wall body, or view-dependent wall copy
is introduced. Both `assembly` and fused `box` continue to call these same
wall context modules.

## Interior floor revision

Delete `box_bottom_revision_negative()`. Replace it with
`floor_revision_negative()` centered at `[box_w / 2, box_d / 2]` on the
interior floor face `z = -box_h + wall_t`. It uses
`floor_revision_depth = 0.6`, no `mirror()`, and angle zero, so it reads while
looking into the open box from above. The cutter enters only from the interior
face. There is no revision geometry on the exterior/build-plate face.

The existing compass and component labels keep their positions and 0.6 mm
depths. Floor thickness, holes, chamfers, locators, and component supports do
not change.

## Top-panel region layout

Introduce one authoritative `panel_region_gap = 2` and derive all neighboring
rounded-region spacing from it. Replace local width assumptions with:

```scad
dc_region_w = 74;
barrel_group_w = dc_region_w;
barrel_channel_w = dc_region_w;
c13_group_w = 58;
service_group_w = c13_group_w;
service_group_h = usb_c_group_h;  // 28 mm
```

The existing layout equations continue to derive `dc_grid_x`,
`dc_col_spacing`, and `dc_row_spacing`; explicit assertions require both DC
column and row gaps to equal `panel_region_gap`. The width exchange from the
C13 region to the DC regions keeps the enclosure width unchanged: every DC
rounded pocket grows from 70 to 74 mm while the C13 rounded pocket shrinks
from 66 to 58 mm. With the existing hardware centers, the XT60 face changes
from protruding 0.75 mm beyond the pocket's left edge to approximately
1.25 mm inside it.

`c13_cutout_w = 28` and `c13_screw_spacing = 40` are invariant and covered by
assertions. Narrowing applies only to the surrounding rounded rectangle; it
does not move or resize the C13 cutout or its screw holes.

The service region is one rounded rectangle directly below C13. Derive it
from shared region bounds, not independent nudges:

```scad
service_group_x = c13_panel_x;
service_group_y = service_row_y - c13_group_h / 2
    - panel_region_gap - service_group_h / 2;
service_cell_w = service_group_w / 2;
service_cell_h = service_group_h / 2;
```

Its four equal cells form this readable 2x2 grid:

```text
plamp       revision
COM         USB hole
```

Cell centers are derived as `service_group_x +/- service_cell_w / 2` and
`service_group_y +/- service_cell_h / 2`. `plamp` and `COM` occupy the left
column; the revision and USB connector occupy the right column. USB therefore
exits on the right for cable management. Split the existing USB negative into
a hardware-only `usb_c_connector_negative()` and the single
`service_group_negative()` rounded pocket so no second rounded rectangle is
hidden inside the service region. Both COM and USB belong to this one pocket.
The standalone USB fit coupon may compose those two modules to retain its
usefulness.

Assertions protect the complete layout: every XT60 face is inside its DC
rounded bounds with at least 1.2 mm X margin; DC row/column gaps and the
C13/service gap are exactly 2 mm; the service cells share identical dimensions
and bounds; and C13/USB cutout and screw envelopes stay within their assigned
regions.

## Sub-panel separator supports

Keep the existing full-width USB support rib. Add only separator supports
whose centerlines and extents derive from the rounded-region bounds:

- one vertical support under the 2 mm gap between the two DC columns;
- one horizontal support under the 2 mm gap between the two DC rows; and
- one horizontal support under the 2 mm gap between C13 and the service
  region.

Use one helper,
`sub_panel_separator_rib_positive(x0, y0, w, h)`, and one composing module,
`sub_panel_separator_ribs_positive()`. Each rib starts at
`sub_panel_base_h`, rises exactly
`sub_panel_h - sub_panel_base_h`, and stops at the existing `sub_panel_h`
datum flush with the top-panel underside. Its across-gap width is exactly
`panel_region_gap`; its long extent spans the matching neighboring region
bounds. Intersections between separator ribs are intentional unions.

The support modules use layout coordinates consistently with
`sub_panel_8ch_positive()`; they do not contain corrective numeric offsets.
Bounding-box assertions require every DC, C13, USB, switch, screw, and XT60
nut-clearance cutter either to remain wholly on its assigned side of a rib or
to be an intentional opening through the pre-existing full-width USB rib.
Separator supports must not be silently trimmed around a cutter.

`sub_panel_base_h = 5`, `sub_panel_h = 10`, top-panel thickness, wall height,
corner supports, 20 mm panel screws, and 25/30 mm corner screws remain
unchanged.

## Corner-wall nut fit

This correction applies only to the top and bottom corner-wall nut catches
made by `support_free_m3_nut_trap()`. The top-panel
`side_loaded_panel_nut_trap()` and its `panel_nut_*` dimensions do not change.

Decouple the corner values from the panel-detent controls and define:

```scad
corner_nut_slot_l = 2.7;
corner_nut_entry_w = 6.1;
corner_nut_throat_w = 5.8;
corner_nut_entry_detent =
    (corner_nut_entry_w - corner_nut_throat_w) / 2;  // 0.15 mm/side
corner_nut_entry_detent_l = 1.5;
corner_nut_pocket_d = corner_nut_entry_w / cos(30);
```

The 2.7 mm axial slot replaces the current 3.1 mm slot around the measured
approximately 2.41 mm nut. The entry width is 6.1 mm, the retaining throat is
5.8 mm, and each positive detent is 0.15 mm. Assert all four values and the
identity `entry width - 2 * detent = throat width`.

Flat-wall and fused-box paths share these finished dimensions. The flat path
uses the point-up six-sided pocket with `corner_nut_pocket_d`, whose
flat-to-flat width is exactly 6.1 mm. The box path uses the same 6.1 mm core
and 2.7 mm axial length; only its global-print-up support-free roof differs.
Entry angle, screw axis, bore diameter, nut bearing-face datum, top and bottom
nut offsets, tab/spine solids, and coupon modules remain authoritative and
unchanged. The existing zero-offset M3x25 nut-face stack assertions and M3x30
enclosed-travel assertions must still pass.

## Verification and delivery

Implementation follows red-green-refactor in four reviewable increments:

1. wall rotations/vent handedness and the interior floor revision;
2. DC/C13/service layout and sub-panel separator supports;
3. corner-wall nut fit; and
4. integrated source-contract and `plamp cad` validation (no empty commit).

Before each source edit, add and run the focused failing source-contract test.
Use `plamp cad views plamp8 --json`, `plamp cad validate plamp8 --json`, and
`plamp cad plan plamp8 --preset split-box --json` plus `--preset fuse-box` for
non-rendering validation. Commit and push each small source increment for
early feedback. Do not invoke OpenSCAD until the first source commit is
pushed. Subsequent rendering is optional and only on user request; a successful
render is never evidence that printed hardware fits.

No generated STL, log, archive, or source snapshot is committed.
