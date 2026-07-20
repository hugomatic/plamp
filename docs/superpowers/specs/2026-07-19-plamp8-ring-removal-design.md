# Plamp8 Ledge-Ring Removal Design

## Status And Scope

This design supersedes the separate ledge-ring requirements in `2026-07-18-plamp8-flat-wall-enclosure-design.md`. It preserves the four-wall enclosure, floor, top panel, existing 10 mm sub-panel, corner spine, captured nuts, and panel datums while removing the redundant printed ledge ring.

The sub-panel is the top structural plane, matching the floor's role at the bottom. During open-wall wiring the connected panel assembly may be supported temporarily; it no longer needs to rest unaided on only the north and south walls.

## Removed Part And Controls

Remove the ledge ring completely:

- Remove `ledge_ring` from the ordered view list and top-level dispatcher.
- Remove `show_ledge_ring` and its assembly branch.
- Remove `feature_ph_ledge_holes`.
- Remove all `ledge_ring_*`, `ph_ledge_*`, and `top_ledge_*` parameters, functions, assertions, echoes, and modules.
- Remove the ring surrogate from the corner coupon and corner-fastener assembly.
- Remove the ring from hardware summaries, source-contract tests, rendering lists, and assembly instructions.

Preserve the current ventilation clearance numerically after removing the ring-derived names. Set `vent_top_margin = 15` directly; do not move the existing top vent row as an incidental consequence of this cleanup.

## Panel Datum And Direct Bearing

Keep the existing top panel and sub-panel positions:

- Top surface: Z = 0.
- Top panel: Z = -3 through 0 mm.
- Sub-panel: Z = -13 through -3 mm.
- Sub-panel bottom: Z = -13 mm.

Rename `ledge_top_z` to `sub_panel_bottom_z` and retain:

```scad
sub_panel_bottom_z = -(plate_t + sub_panel_h);
```

Move only the top wall-tab stack upward by the removed ring thickness of 3 mm. The upper east/west clearance tab must contact the sub-panel bottom directly:

```scad
function top_clearance_tab_center_y(h) =
    h + sub_panel_bottom_z - corner_tab_t / 2;
```

The north/south nut tab remains immediately below the clearance tab. The continuous north/south spine follows the revised top nut-tab position. Bottom tabs, floor, floor locators, wall height, panel hole coordinates, and all component positions remain unchanged.

## Equal Wall Thickness And M3x25 Fasteners

Use one named screw length for all eight enclosure corners:

```scad
corner_screw_length = 25;
```

At both top and bottom, each intersecting wall contributes the same `corner_tab_t = 6` mm thickness along the screw axis.

The top M3x25 path is:

1. 3 mm top panel.
2. 10 mm sub-panel.
3. 6 mm east/west clearance tab.
4. 6 mm north/south nut tab, including the nut's complete axial thickness.

The resulting 25 mm path ends flush with the far face of the captured nut.

The bottom M3x25 path begins with the 3 mm floor, then crosses the same two 6 mm wall contributions. Place the bottom nut 10 mm farther along the existing extended north/south spine so its far face also lands exactly 25 mm from the screw-head bearing surface:

```scad
top_stack_h = plate_t + sub_panel_h + 2 * corner_tab_t;
bottom_stack_h = wall_t + 2 * corner_tab_t;
bottom_corner_nut_offset = corner_screw_length - bottom_stack_h;
```

At the approved dimensions, `top_stack_h = 25`, `bottom_stack_h = 15`, and `bottom_corner_nut_offset = 10`. Remove `corner_screw_tip_allowance`; neither M3x25 screw intentionally protrudes beyond its nut.

Assertions and hardware echoes must verify both flush relationships rather than comparing the screw against sacrificial retainer material beyond the nut.

## M3x30 Compatibility

Retain the 16 mm nut-tab extensions, full-length support-free bores, captured-nut pockets, retention detents, and continuous north/south spine. Define 30 mm as the supported long substitute length and assert that its extra 5 mm remains inside positive corner material at both ends.

An M3x30 may extend 5 mm beyond the far face of either nut, but its tip must remain enclosed inside the corner boss or spine rather than entering the wiring space or bottom exterior. No user-accessible trimming is required.

## Corner Coupon

Keep the compact corner coupon because it tests the real current nut pocket and equal-thickness wall stack. It must contain:

- One top north/south nut-tab snippet.
- One top east/west clearance-tab snippet.
- One bottom north/south nut-tab snippet.
- One bottom east/west clearance-tab snippet.
- A 3 mm top-panel surrogate.
- A 10 mm sub-panel surrogate.
- A 3 mm floor surrogate.

Remove only the 3 mm ring surrogate. The coupon continues to use the current side-loaded M3 nut pocket with two small retention detents; it must not reintroduce the obsolete broad axial nut catcher. Verify both M3x25 flush engagement and enclosed M3x30 substitution against the coupon geometry.

## Assembly Sequence

The revised sequence is:

1. Assemble the top panel and sub-panel.
2. Mount the PSU, DC/DC converter, and relay board on the floor.
3. Install north and south walls while leaving east and west open.
4. Temporarily support the connected panel assembly above the enclosure during wiring.
5. Complete wiring with east and west absent.
6. Install east and west, engaging their bottom locators and corner tabs.
7. Place the panel assembly directly on the upper clearance tabs.
8. Install four top and four bottom M3x25 screws.

Later service removes the panel assembly and whichever individual wall provides access. There is no separate ring to remove, align, store, or reinstall.

## East-Wall Center Rib Alignment

Correct the existing east-wall center-rib interference while updating the enclosure. At the current 226 mm east-wall length, `length / 2` places the 3 mm center rib at X=113 mm. The adjacent 5 mm vent at X=110 mm extends through X=112.5 mm, overlapping the rib that begins at X=111.5 mm.

Move the center rib to X=105 mm, exactly midway between the X=100 and X=110 vent columns. This leaves 1 mm between each hole edge and the 3 mm rib, matching the established outer ribs at X=15 and X=205 mm. Derive the position from the vent grid so it remains centered in a left-of-center vent gap rather than encoding an unexplained 8 mm offset.

Do not move any vent, outer rib, transverse rib, floor-bearing rib, wall hole, revision engraving, or corner feature.

## Source And Test Changes

Update the existing CAD source-contract tests to require:

- No ledge-ring view, Customizer control, feature control, module, parameter, or dispatcher branch.
- `corner_screw_length = 25`.
- Equal 6 mm wall-tab contributions at top and bottom.
- `sub_panel_bottom_z` and the direct-bearing top-tab formula.
- Flush M3x25 engagement at both captured nuts.
- A 10 mm bottom nut offset.
- Enclosed M3x30 compatibility at both ends.
- No ring surrogate in the corner coupon.
- Preservation of the existing top/sub-panel datums and bottom geometry.
- The east-wall center rib occupies the vent-grid gap centered at X=105 mm and does not overlap either neighboring 5 mm vent.

The user's earlier no-new-test request applies only to the three component-fit parameter adjustments. Ring removal deliberately changes the ordered view contract, screw-stack math, coupon, and assembly behavior, so the existing CAD contract tests must be updated.

## Verification

Push each source checkpoint before starting OpenSCAD. Do not commit generated STLs.

After source tests and `git diff --check` pass:

1. Render the corner coupon from the pushed commit and inspect both M3x25 and M3x30 paths.
2. Render all four walls and confirm only the top joint positions moved by 3 mm.
3. Render the floor and confirm its tabs, holes, labels, and component mounts did not move.
4. Render the top panel and sub-panel and confirm their geometry and datums did not change.
5. Render the complete assembly without a ledge ring.
6. Confirm every STL is non-empty and logs contain no warning, error, missing geometry, or empty top-level object.
7. Visually confirm direct sub-panel bearing, aligned corner bores, full nut engagement, enclosed long-screw travel, and no new component or wall interference.

## Acceptance Criteria

- The ledge ring no longer exists as a printed part, view, assembly option, or geometry dependency.
- The sub-panel directly forms the top structural plane and retains its existing dimensions and Z datum.
- Only the top wall tabs move upward 3 mm; bottom geometry remains fixed.
- All eight primary fasteners are M3x25.
- Every wall contributes exactly 6 mm along every corner screw path.
- Each M3x25 fully engages and ends flush with the far face of its captured nut at both top and bottom.
- M3x30 substitutes remain enclosed at both top and bottom.
- The corner coupon contains no ring surrogate and no obsolete axial nut catcher.
- The east-wall center rib is centered between vent columns at X=105 mm with 1 mm edge clearance to both neighboring holes.
- The enclosure retains four independently printable walls and the existing service access sequence with temporary panel support.
