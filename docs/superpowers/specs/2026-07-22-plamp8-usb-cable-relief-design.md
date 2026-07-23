# Plamp8 USB cable relief

## Goal

Allow a molded USB-C cable plug to reach the underside-mounted COM receptacle's
retention position without changing the receptacle alignment or the sub-panel.

## Geometry

Add a centered 24 × 14 mm rounded-rectangle recess around the existing USB-C
opening and its two screw holes. The recess leaves 1.5 mm of top-panel material.
The existing 12 × 10 mm rounded through-opening remains the connector-locating
opening.

The 24 mm recess width covers the 22.61 mm screw-head envelope formed by the
17 mm screw spacing and 5.61 mm head diameter. The 14 mm height leaves 2 mm
above and below the through-opening. Use a 2 mm corner radius and keep all new
dimensions parameterized.

Reference both USB screw countersinks to the 1.5 mm recess floor. With the
existing 3.4 mm hole and 5.61 mm head diameters, the 1.105 mm countersink fits
within that local thickness while retaining material below its cone.

## Scope

The hardware negative shared by the production top panel and `usb_c_panel`
coupon receives the recess, so the printed coupon tests production geometry.
The matching production sub-panel crop remains unchanged. No other connector
panels, service-pocket layout, labels, or enclosure geometry change.

## Verification

Add source-contract coverage for the recess dimensions, remaining thickness,
corner radius, recess cutter, countersink datum, and unchanged sub-panel USB
opening. Validate Plamp8 metadata, plan the `usb_c_panel` view, compile that view
to CSG without warnings or assertions, and run the full Python test suite.
