# Plamp8 Sub-Panel Fit Correction

## Problem

The outboard XT60 mounting screws for PH Up and Agitator intersect the
sub-panel's raised left perimeter lip, leaving no room for their M3 nuts.
The sub-panel revision cutter overlaps its surface by only 0.01 mm, so the
hash appears in OpenSCAD but is effectively absent after slicing and printing.

## Design

- Add 7 mm cylindrical clearances centered on only the two obstructed outboard
  XT60 screw holes: PH Up and Agitator.
- Subtract each clearance through the raised lip, from the top of the 5 mm base
  through the 10 mm sub-panel height. Preserve the base and existing screw holes.
- Engrave `revision_string` 0.6 mm into the existing sub-panel revision location.
- Leave every other connector, wall section, label, and panel dimension unchanged.

## Verification

Render the sub-panel with a known revision and verify that the STL is non-empty,
the revision changes the final mesh, and the two 7 mm clearances intersect the
left lip without cutting through the base. Render the top panel as a regression
check because its holes align with the sub-panel.
