# Parametric Nut Catcher Jig Design

The M3 nut catcher is defined from `nut_across_flats`, `nut_thickness`,
`width_clearance`, `thick_clearance`, and `nib_height`. One canonical local
geometry owns the hex pocket, insertion channel, retention nibs, and optional
roof. Production panel catchers (including C13 and XT60) and wall-corner
catchers call that geometry through coordinate-system wrappers rather than
maintaining independent fit dimensions or nibs.

The canonical catcher uses local X for insertion, local Y across flats, and
local Z for nut thickness/screw axis. `roof_mode` is either `"flat"` (bridge
the small rectangular gap) or `"30deg"` (cut a support-free peaked roof).
Orientation is a fixture concern: `up`, `down`, `sideways`, and `45` rotate the
same catcher relative to the build plate.

The printable `nut_catcher_adjustment_test` set consumes declarative rows of
`[orientation, parameter, mode, candidates]`. `orientation` is one orientation
or `"all"`; `parameter` is `width_clearance`, `thick_clearance`, or
`roof_mode`; `mode` is `offsets` for numeric deltas from the initial value and
`values` for literal candidates. Rows are independent sweeps, never a Cartesian
product. Every coupon is engraved with orientation, varied parameter/value,
and the revision. Defaults exercise five width offsets and five thickness
offsets on `up`, plus both roof modes in every orientation.

The production defaults remain the measured 5.46 mm across-flats, 2.38 mm
thickness, 0.14 mm width clearance, 0.14 mm thickness clearance, and 0.20 mm
nib height established by revision `83e9554`.
