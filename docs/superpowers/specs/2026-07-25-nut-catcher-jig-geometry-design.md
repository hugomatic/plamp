# Nut Catcher Jig Geometry Refinement

## Goal

Make the calibration jig accurately exercise the shared production nut catcher while using less plastic and remaining easy to identify, handle, and load.

## Geometry

- Derive the retention nib position from the seated nut center and screw axis. The nut must pass the nib pair before its center reaches the screw axis, then remain retained beneath that axis.
- The 45-degree orientation always uses the flat/open self-supporting roof. Never generate a pointed/30-degree roof at 45 degrees, including when a roof row targets `all`.
- Keep flat and 30-degree roof candidates for the other requested orientations.
- Give the sideways flat-roof candidate a self-supporting teardrop screw passage. Other candidates retain the canonical round screw passage unless their print orientation already transforms it into the required printable geometry.
- Transform each coupon so its nut insertion opening faces negative Y in the exported jig.

## Layout and Material

- Arrange each declarative test row as one connected printable strip.
- Reduce unused material above, below, and beside the functional catcher geometry.
- Tighten label spacing while preserving complete, readable markings and representative wall thickness around the catcher.
- Keep separate rows disconnected so a failed or unwanted row can be discarded independently.

## Generation Legend

OpenSCAD generation output must explain the engraved abbreviations:

- `U`: up
- `D`: down
- `S`: sideways
- `45`: diagonal
- `W`: width clearance
- `T`: thickness clearance
- `RF`: flat roof
- `R30`: 30-degree roof

The legend is emitted once for the adjustment-test set and is recorded in the managed CAD log.

## Verification

- Automated source/geometry-contract tests cover seated nib placement, roof selection, teardrop selection, negative-Y insertion direction, connected row layout, compact dimensions, and legend text.
- A headless OpenSCAD render must complete without warnings or errors and produce simple geometry.
- Mesh connectivity must match the number of declarative rows: one connected component per row.
- Existing C13, XT60, and corner catcher generation must still compile because they share the canonical catcher.
