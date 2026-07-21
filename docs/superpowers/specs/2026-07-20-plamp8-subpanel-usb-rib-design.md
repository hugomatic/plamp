# Plamp8 Sub-Panel USB Rib Design

## Goal

Support the top panel near the USB connector and stiffen the sub-panel without adding a fifth fastener or another assembly step.

## Geometry

Add one straight cross-rib to the positive sub-panel geometry:

- run across the full interior width between the existing left and right perimeter walls;
- use a 10 mm-wide by 5 mm-high rectangular section;
- rise from the 5 mm sub-panel base to the existing 10 mm top datum;
- place the rib immediately below the USB connector cutout; and
- keep the USB opening, USB screw holes, other connector cutouts, and wiring paths clear.

The rib top is coplanar with the perimeter lip so the top panel rests directly on both. The rib joins the two side walls, but does not extend into or duplicate them.

The existing revision engraving stays in place when it clears the rib. If the 10 mm rib overlaps it, move the engraving only far enough downward to restore readable clearance.

## Revision default

Change the public default from `revision_string = "dev"` to `revision_string = "revision"`. Callers may continue overriding the value through OpenSCAD customizer or `-D` arguments.

## Scope

This rib replaces the previously deferred fifth central top-panel screw. No top-panel holes, sub-panel nut traps, corner fasteners, exterior dimensions, or production plate layouts change.

## Verification and delivery

Add a lightweight source-contract test for the rib dimensions, span, top datum, and new revision default. Commit and push the source before running OpenSCAD. Then use only a quick sub-panel CSG compile; no full assembly render is required.
