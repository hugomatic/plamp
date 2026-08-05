# Plamp8 wall-thickness design

## Goal

Set the separate Plamp8 enclosure wall thickness with one adjustable 5 mm default without changing the floor or either panel.

## Approach

`wall_thickness` is the single adjustable wall value, with a 5 mm default. Floor thickness, floor fastener geometry, locator interfaces, panel thickness, panel dimensions, and panel fasteners retain their current values. The wall bodies, 45° mitres, and vent cutouts expand outward as `wall_thickness` increases.

For the 30 mm corner screw, the 3 mm floor leaves 27 mm of vertical support. The north/south nut-owner boss and east/west clearance boss each use half: 13.5 mm. Their common boss radius is 6 mm, up from 5 mm, while the screw axis remains fixed.

The nut-entry and retention tunnel height derives from the boss radius, retaining the same 1 mm crown thickness as the boss radius changes.

At the lower corner, the east/west boss starts at the top of the 3 mm floor and ends at 16.5 mm; the north/south boss then runs from 16.5 mm to 30 mm. Neither boss enters the floor.

The shared 30 mm screw uses its own lower nut-catcher offset so the catcher stays fully inside the upper end of the north/south 13.5 mm boss; the existing 25 mm floor-stack offset remains unchanged.

## Verification

Validate the part metadata, plan the affected floor/wall/panel views, and generate the wall and assembly views. Confirm that the floor and panel plan variables remain unchanged and that the rendered wall solids are 4 mm thick.
