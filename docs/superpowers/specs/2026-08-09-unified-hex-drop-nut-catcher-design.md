# Unified Hex-Drop Nut Catcher Design

## Goal

Every Plamp8 nut catcher uses one geometry-producing module: a rectangular insertion tunnel joined to a raised hexagonal entry pocket above a lower hexagonal nut pocket. The nut enters point-first, reaches the raised hex without meeting a flat rear wall, then gravity drops it into the lower hex seat so it cannot rotate while the screw is tightened.

## Geometry

`m3_nut_catcher_negative()` remains the single source of catcher geometry. It creates the hex-cylinder pocket, tunnel, mouth, and optional support-free roofs.

The rectangular insertion tunnel runs from the exterior mouth to the screw axis, where it joins a raised point-first hexagonal entry pocket at the tunnel elevation. The raised hex provides clearance for the complete nut while preserving the pointy rear wall of the catcher. A second hex pocket below it provides the drop and anti-rotation seat. The rectangular tunnel must not extend through the rear half of the hex, because that cuts away the pointy wall and leaves a flat tunnel end.

The drop is proportional to nominal nut thickness:

```scad
nut_drop = nut_thickness * nut_drop_fraction;
```

`nut_drop_fraction` is one globally adjustable parameter and defaults to `1 / 2`. For the 2.38 mm M3 nut profile, this produces a 1.19 mm drop that is clearly visible and spans five complete shelf layers with a 0.20 mm slicer profile. Tunnel clearance does not affect the drop. The tunnel is positioned one `nut_drop` above the pocket floor in the module's local coordinates.

All production callers orient the module so the pocket is below the tunnel in the final assembled orientation. Corner, top-panel, and sub-panel catchers may retain different tunnel widths or thickness clearances, but they do not define separate pocket or drop geometry.

## Printable Roofs

The same module retains its roof-mode parameter. `roof_mode = "30deg"` adds the pointy support-free roofs over the hex pocket and tunnel where required by print orientation. `roof_mode = "flat"` leaves those additions out. Roof selection does not change the pocket, tunnel, or drop calculation.

The sideways diagnostic coupon uses a test-only gable because its printable roof faces a different direction after rotation. That gable must share the tunnel's local floor elevation, `nut_thickness * nut_drop_fraction`; otherwise changing the drop displaces the roof along the sideways tunnel. Its cross-section and 30-degree slopes remain unchanged.

## 45-Degree Test Coupon

The 45-degree diagnostic coupon must expose the complete cross-section of its straight diagonal tunnel through the top, not merely let one corner of the cutter graze the surface. Only this coupon grows: its width increases from 16 mm to 28 mm and its height from 10 mm to 14 mm. The hex pocket remains at its existing datum.

Its label and revision engraving use the effective 14 mm coupon height. They must remain shallow cuts in the actual top face; using the original 10 mm height buries the text inside the coupon and can produce an STL that slicers cannot process.

The tunnel length is derived from the actual coupon top, the unchanged 45-degree catcher origin, and half the 6.1 mm tunnel width:

```scad
opening_edge_distance =
    (effective_coupon_h - origin_45_z) * sqrt(2)
    + corner_nut_tunnel_w / 2
    + boolean_shim;
```

This replaces the guessed 2.5 mm extension, which produced only a minuscule slit. In the all-orientations row, the wider 45-degree coupon shifts by half its added width so it retains the normal gap from its neighbor.

Normal orientation coupons and the clearance matrix retain their existing dimensions. The larger diagnostic coupon does not change any production catcher geometry.

The clearance matrix defaults to three width values and three thickness values: `[-0.1, 0, 0.1]` mm. This produces a compact 3×3 matrix at 0.1 mm intervals while keeping both dimensions independently adjustable from the command line.

## Cleanup

Remove the corner-only absolute drop and the public tunnel-Z-offset parameter. No production catcher may bypass the proportional drop. Orientation helpers may transform the shared module but must not construct alternate catcher geometry.

## Verification

Automated tests will confirm that the shared module computes the half-thickness drop, every production catcher uses it, pointy-roof selection remains available, and only the 45-degree diagnostic coupon receives the larger envelope and geometry-derived straight tunnel. OpenSCAD generation and visual inspection will verify that the complete tunnel cross-section exits the coupon top without warnings or invalid meshes.
