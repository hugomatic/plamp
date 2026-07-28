# Peristaltic pump stand

## Goal

Create a new Plamp CAD model for a table-standing holder for one or more
peristaltic pumps. The first print targets two pumps.

## Form

- A horizontal top plate carries the pumps.
- Pump motors hang below the plate through circular motor openings.
- Two full-height end panels form a U-stand and keep the motors clear of the
  table.
- The default clearance below the top plate is 55 mm for approximately
  50 mm-long motors.

## Parametric interface

| Variable | Initial value | Meaning |
| --- | ---: | --- |
| `pump_count` | 2 | Number of repeated pump stations. |
| `pump_spacing` | 62 mm | Centre-to-centre spacing of stations. |
| `motor_hole_d` | 29 mm | Circular motor opening diameter. |
| `motor_screw_spacing` | 48.5 mm | M3 mounting-hole centre spacing. |
| `motor_clearance_h` | 55 mm | Plate-to-table clearance. |
| `mount_hole_d` | M5 clearance | Two provisional table-mount holes. |

Each station is aligned on one axis: M3 screw hole, motor opening, M3 screw
hole. The two provisional M5 table-mount holes are placed near the plate ends.

## CAD sets

- `plate`: printable top plate with all pump and table-mount holes.
- `legs`: printable pair of end panels.
- `assembly`: plate plus legs for fit and table-clearance inspection.

## Print and fit intent

- Plate and legs remain separate printable pieces.
- The first version prioritizes stiffness and fit verification over material
  minimization; end panels are full height rather than narrow rails.
- Motor opening and pump fastener dimensions are exposed for later measured
  adjustment.

## Verification

- CAD tests assert the parametric values, repeated station count, and named
  output sets.
- Render `plate`, `legs`, and `assembly`; verify motor openings, M3-hole
  alignment, M5 holes, and 55 mm table clearance.
