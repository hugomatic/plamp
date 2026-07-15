# Plamp8 USB COM fit

Update the USB COM mount for an underside-mounted connector:

- use 17 mm screw-hole center spacing on both panels;
- use 3.2 mm screw-clearance holes, producing a 20.2 mm outside span matching the measured 20.19 mm connector span;
- make the top-panel opening a 12 × 10 mm rounded rectangle with 1.5 mm corner radius;
- retain the sub-panel's larger 14 × 10.25 mm opening;
- keep top- and sub-panel opening dimensions independently parameterized.

The standalone `usb_c_panel` view is the fit-test print. Do not generate STL files or run OpenSCAD on Tower; the user will render and print it separately.

## Countersinks and top-panel fasteners

- Add underside countersinks for flat-head M2 COM screws, using 2.4 mm clearance holes and 4 mm head clearance.
- Change all four top-panel fasteners from M4 to M3: 3.4 mm clearance holes and 6.5 mm countersinks.
- Restore a 9.5 mm diameter flat circular land around each top-panel countersink where recessed-area borders interfere.
- Design the top-panel joint around the available 20 mm screw length. Each screw must traverse the full captive nut and extend approximately 1 mm beyond it.

## Captive nuts

Each top-panel corner uses an inward-facing, side-loaded M3 hex nut pocket inside the ledge. The outside end is closed, hex walls prevent rotation, and a small entrance detent prevents an inserted nut from sliding out while the enclosure is handled or inverted. Nuts are inserted before the top panel is installed; no hand access is required while tightening.

Add a small standalone corner/nut-trap fit-test view so nut insertion, retention, screw reach, and countersink fit can be checked without printing the enclosure.
