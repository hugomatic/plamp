# Unified Hex-Drop Nut Catcher Design

## Goal

Every Plamp8 nut catcher uses one geometry-producing module: a rectangular insertion tunnel united with a lower hexagonal nut pocket. The nut enters point-first, then gravity drops it into the hex seat so it cannot rotate while the screw is tightened.

## Geometry

`m3_nut_catcher_negative()` remains the single source of catcher geometry. It creates the hex-cylinder pocket, tunnel, mouth, and optional support-free roofs.

The drop is proportional to nominal nut thickness:

```scad
nut_drop = nut_thickness * nut_drop_fraction;
```

`nut_drop_fraction` is one globally adjustable parameter and defaults to `1 / 4`. For the 2.38 mm M3 nut profile, this produces a 0.595 mm drop that spans two complete shelf layers with a 0.20 mm slicer profile. Tunnel clearance does not affect the drop. The tunnel is positioned one `nut_drop` above the pocket floor in the module's local coordinates.

All production callers orient the module so the pocket is below the tunnel in the final assembled orientation. Corner, top-panel, and sub-panel catchers may retain different tunnel widths or thickness clearances, but they do not define separate pocket or drop geometry.

## Printable Roofs

The same module retains its roof-mode parameter. `roof_mode = "30deg"` adds the pointy support-free roofs over the hex pocket and tunnel where required by print orientation. `roof_mode = "flat"` leaves those additions out. Roof selection does not change the pocket, tunnel, or drop calculation.

## 45-Degree Test Coupon

The 45-degree diagnostic coupon must expose enough of the straight diagonal tunnel to make its shape visible in a slicer. Only this coupon grows: its width increases from 16 mm to 20 mm and its height from 10 mm to 14 mm. The hex pocket remains at its existing datum, while the test-only tunnel cutter extends by 2.5 mm so the longer enclosed tunnel still exits through the coupon top.

Normal orientation coupons and the clearance matrix retain their existing dimensions. The larger diagnostic coupon does not change any production catcher geometry.

## Cleanup

Remove the corner-only absolute drop and the public tunnel-Z-offset parameter. No production catcher may bypass the proportional drop. Orientation helpers may transform the shared module but must not construct alternate catcher geometry.

## Verification

Automated tests will confirm that the shared module computes the drop from nut thickness, every production catcher uses it, pointy-roof selection remains available, and only the 45-degree diagnostic coupon receives the larger envelope and longer test tunnel. OpenSCAD generation will verify the nut-catcher adjustment coupon and affected Plamp8 printable sets without warnings or invalid meshes.
