# Plamp8 Service Pocket Separation Design

## Goal

Separate the Plamp8 service area into three visually distinct rounded-rectangle pockets without combining the `plamp`, revision, and `COM + USB` concepts or expanding the established service region.

## Layout

Keep the existing 58 mm by 28 mm service region and the existing 2 mm panel-region gap.

- Split the service region into two 13 mm-high rows separated by 2 mm.
- Split the top row into two 28 mm-wide pockets separated by 2 mm.
- Center `plamp` in the top-left pocket.
- Center the revision string in the top-right pocket.
- Use one 58 mm-wide pocket for the bottom row.
- Center `COM` in the left half of the bottom pocket.
- Center the USB connector and its fasteners in the right half of the bottom pocket.

The three pocket centers and sizes will be derived from the service-region width, height, and gap rather than duplicated as independent coordinates.

## Geometry Reuse and Alignment

The top panel and USB fit coupon will use the same three-pocket negative composition. The top panel and sub-panel will use one shared derived USB center. An OpenSCAD assertion and a source-contract test will require the top-panel USB cutout and sub-panel USB cutout to remain coincident.

The service-region outer bounds, C13 hardware center, C13/service separator, USB connector dimensions, and fastener dimensions remain unchanged. Only the internal pocket layout and the content centers derived from it change.

## Verification

- Add source-contract tests for the three pocket sizes, 2 mm gaps, centered labels, shared USB datum, and top/sub-panel alignment assertion.
- Run the new test red before changing the SCAD source, then green afterward.
- Run all Plamp8 CAD source-contract tests and the complete Python test suite.
- Run Plamp CAD metadata validation and an assembly plan.
- Run a fast OpenSCAD CSG export to exercise evaluation and assertions without waiting for final STL tessellation.
- Push the verified branch so the final assembly render can be checked on the user's OpenSCAD machine.

## Out of Scope

- Moving or resizing the C13 region.
- Changing USB connector or screw clearances.
- Enlarging the service region or top panel.
- Changing unrelated panel labels, ribs, or hardware.
