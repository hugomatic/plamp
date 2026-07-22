# Plamp8 Flat Connector Panels Design

Date: 2026-07-22
Status: Approved for implementation planning

## Purpose

Make the four Plamp8 top-panel connector fit tests easy to discover, name, and print. The public view names will consistently describe panels, and every connector fit-test STL will contain a flat top-panel coupon plus a matching crop of the production sub-panel.

This work is independent of the proposed human-readable CAD run IDs and duplicate-render handling.

## Current behavior

Plamp8 currently exposes these connector fit views:

- `ac_duplex_channel`
- `dc_barrel_channel`
- `usb_c_panel`
- `c13_inlet`

The names mix `channel`, `panel`, and component-specific nouns. `dc_barrel_channel` is especially misleading because the default connector is XT60 and the view follows `dc_connector_type` rather than always rendering a barrel jack.

The DC and C13 coupons also add 8 mm alignment walls below the 3 mm face plate. Those walls make the coupons non-flat and introduce support or orientation problems. The AC and USB-C coupons are already flat.

## Public view names

Replace the connector fit views with this canonical set:

| Old view | New view | Description |
|---|---|---|
| `ac_duplex_channel` | `ac_duplex_panel` | AC duplex top-panel fit test |
| `dc_barrel_channel` | `dc_connector_panel` | DC connector top-panel fit test |
| `usb_c_panel` | `usb_c_panel` | USB-C top-panel fit test |
| `c13_inlet` | `c13_panel` | C13 inlet top-panel fit test |

This is an intentional breaking rename. Do not retain hidden or visible aliases. Old view names must disappear from the OpenSCAD Customizer list, embedded metadata, presets, dispatch, current workflow documentation, and source-contract expectations. Historical design and plan records remain unchanged. A caller using an old name receives the existing unknown-view error and can discover the replacements with `plamp cad views plamp8`.

The `top-panel-fit` preset must expand, in order, to:

1. `ac_duplex_panel`
2. `dc_connector_panel`
3. `usb_c_panel`
4. `c13_panel`

## Geometry

All four connector fit views must produce a flat plate whose solid extent begins at Z=0 and whose base thickness is `plate_t`, currently 3 mm. Existing cutouts, countersinks, recessed label pockets, flush text, and revision engraving remain unchanged unless a name must change to follow the public view rename.

Introduce one shared `connector_panel_rim` of 3 mm. Size and position each coupon plate from the complete XY envelope of all of its recessed rounded pockets, including revision pockets. Every pocket edge must remain inside the plate by at least `connector_panel_rim` on every side. Do not assume a pocket and its plate share a center: the DC rounded pocket is intentionally offset, and its coupon boundary must account for that offset instead of clipping the pocket. AC must account for both rounded outlet pockets; USB-C must account for all three service pockets; C13 must account for its connector and revision pockets.

The panel may retain additional material where connector hardware, labels, or existing layout needs more than the minimum rim. The 3 mm value is a minimum, not a requirement to crop every side to exactly 3 mm. Add derived-bound assertions so a future pocket or panel dimension change fails clearly if any rim becomes smaller than 3 mm.

Remove `alignment_walls()` from both the DC connector coupon and the C13 coupon. Do not remove alignment or support geometry from production `top_panel`, `sub_panel`, assembly, box, or wall paths. The fit coupons remain representative of the production top-panel face and connector holes; they no longer model an underside locating border.

The AC duplex and USB-C coupons already satisfy the flat-plate requirement and need no underside-geometry redesign. Their outer plate bounds may still change where required to satisfy the shared 3 mm rim contract.

The user's physical XT60 fit is confirmed. Freeze the existing XT60 fit dimensions and relative layout: the 19 by 12 mm cutout, 25 mm screw spacing, 3.2 mm screw holes, and current XT60-to-toggle spacing and position must not change. Expanding or repositioning the surrounding coupon plate must not move those features relative to one another.

## Paired top-panel and sub-panel coupons

Every connector-panel view produces two disconnected printable parts in one STL:

1. The flat top-panel coupon.
2. A matching XY-sized crop of the production `sub_panel_8ch()` geometry directly beneath that connector region.

Place the top-panel coupon on the left and the sub-panel crop on the right with `connector_panel_pair_gap = 10` mm between their outer bounds. Both parts begin at Z=0 and retain their normal print orientations. Their XY outlines and dimensions are identical within each view.

Define one authoritative left, right, bottom, and top bound set for each connector-panel view. Use the same bounds to size the top coupon and to crop the sub-panel. Normalize both parts into the standalone fit-view coordinate system before arranging them side by side. Do not duplicate sub-panel holes, ribs, labels, reliefs, nut clearances, or support geometry in coupon-specific modules.

Create each sub-panel coupon by intersecting the actual `sub_panel_8ch()` result with a vertical prism covering the shared XY bounds and the complete sub-panel Z extent. The crop must preserve full production height and all intersecting production features. It is not a flattened alignment plate.

Use these production regions:

- AC: the left AC section, including its production socket opening, switches, reliefs, and any intersecting structure.
- DC: channel 1, including the confirmed XT60 opening, switch opening, screw features, and left-channel XT60 nut clearance.
- USB-C: the USB-C service region, including the production sub-panel opening and USB support rib.
- C13: the C13 inlet region, including its production opening and any intersecting separator structure.

Add explicit assertions that each top/sub pair has identical XY dimensions and that the relevant connector centers map to identical local XY coordinates. A future production-layout change must fail clearly rather than silently misaligning a coupon pair.

## Internal naming

Rename coupon-specific modules and dimensions where their current names encode the obsolete public view:

- `dc_barrel_channel_unit` becomes `dc_connector_panel_unit`.
- The view wrapper becomes `dc_connector_panel`.
- The AC view wrapper becomes `ac_duplex_panel`.
- The C13 view wrapper becomes `c13_panel`.
- Coupon-only width and height names based on `barrel_channel_*` become `dc_connector_panel_*` when they do not describe production channel layout.

Production modules and variables may retain `channel` or `barrel` when those terms describe an actual output channel, barrel-jack compatibility, or shared production geometry. Avoid unrelated renaming.

`alignment_walls()` may be removed entirely only if no remaining source path uses it after the coupon changes. Otherwise leave the generic module in place.

## Metadata and data flow

The OpenSCAD Customizer declaration remains the canonical ordered view list. Embedded `generate.json` metadata must use only the new names, and `top-panel-fit` must reference those same names. The final view dispatch must call the renamed wrappers.

`plamp cad validate plamp8` must accept the document. `plamp cad views plamp8` and `plamp cad plan plamp8 --preset top-panel-fit` must expose only the canonical connector-panel names. Planning a single `dc_connector_panel` job must still honor `dc_connector_type`; with the repository default it renders the XT60 cutout and mounting holes.

The standalone view wrappers compose the top coupon and production-derived sub-panel crop. Production top-panel and sub-panel modules remain independently printable and unchanged outside the crop operation.

## Error handling and compatibility

Because the rename is intentionally breaking, no alias layer or migration mechanism is added. The normal CLI unknown-view diagnostic is sufficient. Current workflow documentation and test fixtures must not advertise commands using the removed names.

Removing underside walls must not weaken or alter the production enclosure. The change is limited to standalone connector fit-test modules.

## Verification

Automated source-contract tests must verify:

- The canonical view list and metadata contain the four panel names.
- The three retired names are absent.
- `top-panel-fit` expands to the four canonical views in the specified order.
- The DC view still dispatches through connector-type-aware geometry.
- DC and C13 fit units contain a single flat `fit_plate(...)` positive and no `alignment_walls(...)` call.
- Every recessed rounded pocket has at least 3 mm of plate to each corresponding coupon edge.
- Derived rim assertions cover offset and multi-pocket panels rather than only comparing nominal widths and heights.
- The confirmed XT60 cutout, screw-hole, and toggle-spacing constants remain unchanged.
- Every connector-panel view contains one top coupon and one crop derived from `sub_panel_8ch()`.
- Each top/sub pair uses one shared XY bound set, has identical width and height, and retains a 10 mm inter-part gap.
- AC crops the left production section; DC crops channel 1; USB-C and C13 crop their canonical production centers.
- Top-panel and sub-panel connector centers normalize to the same local XY coordinates.
- Production top-panel connector cutouts retain their existing dimension and center contracts.

Run `plamp cad validate` and `plamp cad plan` before OpenSCAD. Compile all four connector-panel views through the fast CSG gate and inspect logs for warnings, errors, failed assertions, or empty geometry. Run the complete repository test suite. Full STL rendering may be performed on the user's workstation when local OpenSCAD rendering is too slow; the user will inspect the four coupons for flat build-plate contact and support-free slicing.

## Out of scope

- Human-readable CAD run IDs, duplicate-render detection, or artifact verification.
- Changes to connector cutout sizes, fit clearances, labels, or hardware positions.
- Changes to production enclosure geometry; the standalone views only intersect existing production sub-panel output.
- Compatibility aliases for retired view names.
- Redesigning component floorplan, corner, wall, or assembly test views.
