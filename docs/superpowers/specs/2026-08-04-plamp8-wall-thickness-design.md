# Plamp8 wall-thickness design

## Goal

Set the separate Plamp8 enclosure wall thickness with one adjustable 5 mm default without changing the floor or either panel.

## Approach

`wall_thickness` is the single adjustable wall value, with a 5 mm default. Floor thickness, floor fastener geometry, locator interfaces, panel thickness, panel dimensions, and panel fasteners retain their current values. The wall bodies, 45° mitres, and vent cutouts expand outward as `wall_thickness` increases.

## Verification

Validate the part metadata, plan the affected floor/wall/panel views, and generate the wall and assembly views. Confirm that the floor and panel plan variables remain unchanged and that the rendered wall solids are 4 mm thick.
