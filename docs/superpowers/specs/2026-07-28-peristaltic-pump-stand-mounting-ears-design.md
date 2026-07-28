# Peristaltic Pump Stand Mounting Ears

## Goal

Move the provisional M5 table-mounting holes from the plate interior to two
external mounting ears, one beyond each end-panel leg.

## Geometry

- Each M5 clearance hole stays on the plate centreline (`y = 0`).
- Each hole sits just outboard of its corresponding leg.
- A circular positive boss around each hole merges with the rectangular plate,
  creating a half-cylindrical ear beyond the plate end.
- The existing central tab slot for each leg remains in the rectangular plate
  material, surrounded on all sides.

## Verification

- The CAD source keeps the M5-hole cutter and uses a named ear radius derived
  from the M5 hole diameter and material margin.
- The plate renders as a simple, non-empty solid.
- The assembly still renders with both end-panel legs seated in their slots.
