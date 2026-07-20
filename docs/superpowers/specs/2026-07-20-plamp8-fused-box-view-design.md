# Plamp8 Fused Box View Design

## Purpose

Add a print-ready `box` view that fuses the Plamp8 floor and four walls into one floor-down part. This gives an alternative to printing and fastening five separate enclosure parts when the populated box can still be wired comfortably. The existing separate floor and wall views remain available and unchanged.

## Goals

- Export one fused STL containing the floor and all four walls in assembly position.
- Reuse the existing floor and wall geometry without copying box-specific versions of those modules.
- Keep the top corner supports that locate and carry the sub-panel.
- Remove bottom corner fasteners that are redundant in a fused print.
- Make wall vents printable in the floor-down orientation without support.
- Allow normal round vents in the box view through an OpenSCAD Customizer checkbox.
- Preserve all existing separate-part and full-assembly behavior by default.

## Non-goals

- Do not merge or otherwise change the standalone wall and floor STLs.
- Do not alter the sub-panel, top panel, component placement, component retainers, labels, ribs, or floor locator geometry.
- Do not add a second implementation of any wall or floor module.
- Do not render the full assembly as part of this change.

## View Contract

Add `box` to the ordered `view` list. The `box()` module explicitly unions:

- north wall in assembly position;
- south wall in assembly position;
- west wall in assembly position;
- east wall in assembly position; and
- the existing floor in assembly position.

The box is exported floor-down in its real assembly coordinates. It contains no sub-panel, top panel, transparent component models, or assembly-only outlines.

The existing `assembly` view and its show/hide controls do not affect `box`. The box is a deterministic manufacturing view rather than a preset assembled illustration.

## Shared Geometry Parameters

The box view passes explicit parameters through the existing context, wall, vent, corner-tab, and floor modules. Defaults reproduce the current standalone parts.

The shared parameters control only these differences:

- whether vents use the normal round profile or the coarse support-free profile;
- whether bottom corner wall fasteners are included; and
- whether floor corner screw holes and countersinks are subtracted.

For the box view, bottom wall fasteners and floor corner screw holes are disabled. The floor locator lands, keys, and wall notches remain. They provide alignment and positive overlap between the floor and walls in the union.

## Corner Supports

The current top tab datum remains authoritative:

```scad
top_clearance_tab_center_y(h) =
    h + sub_panel_bottom_z - corner_tab_t / 2;
```

Consequently, the top face of each support ends at `sub_panel_bottom_z`. The fused box retains:

- the two top clearance tabs on each clearance-owner wall; and
- the top nut-tab portion on each nut-owner wall.

The fused box omits the bottom clearance tabs, bottom nut pockets, and the continuous material whose only purpose is connecting top and bottom fasteners. Shared existing modules such as `corner_nut_tab()` are reused to create the top-only nut-owner support. Standalone walls retain their full continuous corner spines and both fastener zones.

## Coarse Vent Mode

Add this Customizer option, defaulting on:

```scad
box_coarse_vents = true;
```

When enabled, vents in the `box` view use a regular six-sided profile with one vertex pointing upward in assembled box coordinates. A point-up regular hexagon has two roof facets at 30 degrees from horizontal, so the opening has no horizontal ceiling and scales without introducing a fixed bridge span.

The profile remains inside the existing `vent_hole_d` envelope. This preserves the current clearances to ribs, joints, and adjacent vents. The box vent grid positions and spacing do not change.

When `box_coarse_vents` is false, the box uses the existing round vent profile. The standalone north, south, and east wall views always use round vents regardless of this checkbox.

The profile selection belongs in the shared vent-negative path. The box must not duplicate vent loops or wall modules.

## Manufacturing Considerations

- Intended process: FDM, printed floor-down as one part.
- The floor provides the build-plane base and the walls grow vertically.
- Point-up hexagonal vents eliminate unsupported circular ceilings on vertical walls.
- Existing top tabs continue to support the sub-panel.
- Existing internal floor posts and component retainers remain printable from the floor.
- The user must still confirm that the assembled box fits the printer's build volume and that wiring access is acceptable before choosing this alternative.

## Assertions and Tests

Source contract tests will verify:

- `box` is present in the ordered view contract and dispatcher;
- `box_coarse_vents` defaults to true;
- the coarse profile is a point-up regular hexagon;
- the box calls shared wall and floor context modules with explicit options;
- standalone wall and floor calls retain existing defaults;
- top supports remain enabled for the box;
- bottom wall fasteners and floor corner screw holes are disabled only for the box; and
- no box-specific duplicate wall or vent loop is introduced.

All existing CAD script tests must continue to pass.

After the source and tests are committed and pushed, render only the `box` view from that commit. The render must:

- finish without OpenSCAD warnings or errors;
- produce a non-empty simple 3D object;
- produce one connected volume; and
- emit a non-empty STL.

The full assembly will not be rendered unless requested separately.

## Delivery

Implementation will be split into reviewable checkpoints and pushed before OpenSCAD rendering, following the established Plamp8 workflow.
