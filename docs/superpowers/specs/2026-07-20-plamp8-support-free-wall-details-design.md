# Plamp8 Support-Free Wall Details Design

## Goal

Make the Plamp8 corner nut traps, screw bores, and wall ribs printable without generated support in both manufacturing arrangements:

- standalone walls printed exterior-face down; and
- the fused `box` printed floor-down.

The design keeps the assembled fastener axes and existing wall/floor dimensions unchanged.

## Print coordinate contract

Wall-local coordinates remain authoritative:

- X runs along the wall;
- Y runs along the enclosure height and corner-screw axis; and
- Z runs inward from the exterior wall face.

For a standalone wall, print-up is wall-local +Z. In `box`, print-up is assembled/global +Z, which is wall-local +Y for the north and south nut-owning walls.

Wall modules receive an explicit print-orientation parameter. They must not inspect the global `view` value. Standalone wall calls retain the default flat-wall orientation; `box` passes the box orientation explicitly.

The support-free threshold is a surface rising at least 30 degrees above horizontal. Point-up regular-hex roof facets satisfy this threshold.

## Corner nut access

All top and bottom nut entries point 45 degrees from inward toward the box center. Mirroring the existing left/right wall-end feature supplies the matching handedness at the two ends. North/south assembly transforms then point all eight entries toward the enclosure center.

This same geometry has a manufacturing benefit for standalone walls: the 45-degree center-facing path combines wall-local X and +Z, so its rectangular tunnel rises 45 degrees above the build plane and is support-free.

The nut clearance core is rectangular and sized from the existing M3 nut dimensions and clearances. Only the print-facing roof is added:

- flat-wall orientation uses a point-up roof in wall-local +Z;
- box orientation uses a point-up roof in wall-local +Y/global +Z.

The roof is the upper, support-relevant portion of a point-up regular hex: vertical clearance walls below and the two 30-degree rising facets meeting at the ridge. It does not add lower hexagonal facets to the nut clearance core.

In flat-wall orientation, the rising 45-degree entry does not need a second longitudinal roof. In box orientation, the entry is horizontal in assembled XY and receives the same global-up roof as the pocket. Existing nut-entry detents remain, transformed with the complete pocket and entry so their retention behavior follows the new access direction.

## Corner screw bores

Standalone wall screw bores are horizontal. They use a circular clearance region with a point-up support-free roof in wall-local +Z.

Box corner screw bores are vertical. They remain true round M3 clearance bores; no pointed roof is applied. The bore choice follows the explicit print-orientation parameter and does not change the screw axis or nominal clearance diameter.

## Wall ribs

Rectangular rib projections are replaced with support-aware profiles built by one shared rib helper. The helper selects a smooth or faceted profile from the explicit print orientation; it does not duplicate rib placement loops.

For standalone walls, every rib grows from the wall face toward wall-local +Z with a smooth semicylindrical cross-section. Its flat diameter lies on the wall face, so successive layers recede rather than creating an unsupported underside. Both vertical and horizontal assembled ribs lie in the build plane in this manufacturing view.

For `box`:

- assembled vertical ribs keep their existing width and projection, but their lower ends rise from the wall with a short 30-degree support-free ramp before reaching full projection;
- suspended horizontal ribs use a faceted point-up half-hex profile across their long run so their underside rises at least 30 degrees above horizontal; and
- the floor-touching horizontal rib uses the corresponding faceted quarter profile supported by both wall and floor, without an unnecessary suspended lower half.

Rib centerlines, endpoints, vent clearances, revision-text clearance, and nominal projection remain unchanged unless the support-free end transition requires shortening only the full-height portion of a rib.

## Vents, labels, and unchanged geometry

Standalone wall vents remain round because their axes are vertical while the wall is printed flat. Box vents retain their existing point-up regular hexagons because their 30-degree roof facets meet the support-free threshold.

Wall text, floor geometry, corner-tab stack heights, nut offsets, floor locators, screw lengths, and the 0.02 mm box-only miter overlap remain unchanged.

No box-specific copy of a wall, rib loop, nut trap, or bore loop is introduced. The existing modules remain authoritative and accept print-orientation/profile parameters.

## Verification and delivery

Source-contract tests will verify:

- both explicit print orientations;
- 45-degree mirrored center-facing nut entries;
- flat-wall roofed horizontal bores and box round vertical bores;
- print-up roofs on nut pockets and box entry tunnels;
- smooth standalone semicylindrical ribs, faceted box half-hex ribs, and floor-touching quarter-profile behavior; and
- continued reuse of complete wall modules by `box`.

Changes are committed and pushed before OpenSCAD runs. Verification renders only targeted standalone wall/corner geometry and `box`, never the full assembly. Generated STL and render logs stay outside the repository.

## Deferred follow-up

A separate next change will add the fifth central fastener through the top panel into a nut catch in the sub-panel near the Pump/Fan/Nutrients junction. It is intentionally outside this support-free wall-detail change.
