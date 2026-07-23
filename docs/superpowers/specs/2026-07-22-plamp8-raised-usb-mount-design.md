# Plamp8 raised USB mount

## Status

This design supersedes the recess-only USB cable relief on
`fix/plamp8-usb-cable-relief`. It incorporates measurements and assembly tests
from the printed top/sub-panel coupon.

## Goal

Mount the USB-C connector on the production sub-panel while allowing its front
ears to pass through the top panel and protrude 2.5 mm above the top surface.
The top panel must not carry USB mounting screws or obstruct large molded cable
plugs.

## Verified stack and rise

With the connector mounted directly to the sub-panel, its face is flush with
the bottom of the 3 mm top panel and the cable clicks with both panels in their
production positions. Moving the face to 2.5 mm above the top surface requires
a 5.5 mm rise:

```text
3.0 mm top-panel thickness + 2.5 mm protrusion = 5.5 mm rise
```

Add two 5.5 mm-high ear risers to the sub-panel, centered on the existing USB
screw axes.

## Top-panel opening

Remove the recess-only design's 24 × 14 mm cable relief, 12 × 10 mm rounded
through-opening, and top-panel USB screw holes/countersinks. Replace them with
one through-capsule formed by the hull of two 10.5 mm diameter circles centered
17 mm apart on the existing screw axis. The resulting opening is
27.5 × 10.5 mm and remains centered at the canonical USB location.

The capsule matches the connector's central rectangle and rounded mounting
ears. The ears are 5 mm high; at the target elevation half of that height is
above the top panel.

## Sub-panel mount

Keep the USB screw pattern at 17 mm with 3.4 mm M3 clearance holes. Change the
sub-panel connector opening from 13 × 10.5 mm to 12.5 × 10.5 mm. The connector
measures approximately 12.15 mm in X, so the revised opening retains 0.35 mm
nominal total clearance without requiring filing. It also increases the
nominal bridge between the opening and each screw hole from 0.30 to 0.55 mm.

Build each positive riser from the same 10.5 mm ear circle used by the top
capsule. Apply the production connector opening and screw negatives after the
risers are unioned with the sub-panel so the openings continue through the
complete mount.

The connector conflicts with the inner portion of the 10 mm east perimeter
ledge. Remove a local notch 5 mm deep in X from the ledge's inner face, spanning
10 mm in Y and centered on the connector. Preserve the outer 5 mm of the ledge.

## Fasteners

The supplied working screws are M3 × 10 mm. A 5.5 mm rise requires 15.5 mm,
so use standard M3 × 16 mm countersunk screws. This preserves the current
thread engagement within 0.5 mm; M3 × 18 mm would extend 2.5 mm farther and
could bottom out or protrude through the connector.

Cut underside countersinks through the sub-panel at the USB screw axes using
the repository's M3 dimensions: 3.4 mm clearance, 6.5 mm head diameter, and
1.55 mm countersink depth. The flat-head screw length includes its head and its
top surface finishes flush with the sub-panel underside.

## Coupon and scope

The `usb_c_panel` view continues to contain the production top-panel section
and the same-size crop of the full production sub-panel. The crop must include
the risers, underside countersinks, revised opening, and east-ledge notch.

Do not change the canonical USB center, service-pocket layout, other connector
panels, or non-USB enclosure geometry. Do not commit generated STL or CSG
artifacts.

## Verification

Use source-contract tests for the capsule dimensions and construction, absence
of top USB screw cutters, 5.5 mm risers, 12.5 × 10.5 mm sub-panel opening,
5 × 10 mm east-ledge notch, underside countersinks, and M3 × 16 mm hardware
declaration. Validate Plamp8 metadata, plan and compile `usb_c_panel` to CSG,
inspect the log for warnings/errors/assertions, and run the full Python suite.
The user will render, slice, and physically test the STL on their workstation.
