# PSU and DC/DC Mount Standoff Design

## Goal

Guide the PSU and DC/DC M5 screws through the existing 5 mm component raise
while providing load-bearing support at every mounting hole.

## Geometry

A shared mount-standoff module creates 9 mm outside-diameter cylinders at the
existing PSU and converter mount-point coordinates. Each cylinder starts on the
floor's interior surface, rises by `component_raise_h`, and terminates flush
with the existing airflow-support surface.

The existing PSU and converter M5 clearance-hole negatives remain
authoritative. They pass through the floor and the new positive cylinders,
forming coaxial hollow shafts without a second hole-diameter definition. The
PCB or component mounting flange rests on each annular top face; an M5 screw
passes through the shaft and a nut clamps the part against the standoff.

## Consumers

- The assembled/printable box floor includes PSU and converter standoffs when
  `feature_power_screw_mounts` is enabled.
- `psu_footprint` includes the same PSU standoffs.
- `converter_footprint` includes the same converter standoffs.
- Relay mounting geometry is unchanged.

## Verification

- Source tests require one shared 9 mm standoff module and reuse of the
  existing mount-point functions.
- Source tests require the existing M5 negatives to remain the bore source.
- PSU footprint, converter footprint, and floor render as non-empty valid
  solids without OpenSCAD warnings or errors.
- Physical fit and clamping strength remain subject to the next printed
  footprint/floor test.
