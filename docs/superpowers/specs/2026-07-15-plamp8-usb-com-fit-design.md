# Plamp8 USB COM fit

Update the USB COM mount for an underside-mounted connector:

- use 17 mm screw-hole center spacing on both panels;
- use 3.2 mm screw-clearance holes, producing a 20.2 mm outside span matching the measured 20.19 mm connector span;
- make the top-panel opening a 12 × 10 mm rounded rectangle with 1.5 mm corner radius;
- use a 13 × 10.5 mm sub-panel opening;
- keep top- and sub-panel opening dimensions independently parameterized.

The standalone `usb_c_panel` view is a flat 3 mm fit-test plate without the 8 mm alignment-wall frame. Its M3 screw heads enter through countersinks on the top face and thread into the USB connector beneath the panel. Do not generate STL files or run OpenSCAD on Tower; the user will render and print it separately.

## Countersinks and top-panel fasteners

- Add top-face countersinks for flat-head M3 COM screws, using 3.4 mm clearance holes and 5.61 mm head clearance. Measure the countersink depth from the COM pocket's 0.5 mm recessed surface, not the nominal panel top. Do not add circular lands around the COM screws.
- Change all four top-panel fasteners from M4 to M3: 3.4 mm clearance holes and 6.5 mm countersinks.
- Restore a 9.5 mm diameter flat circular land around each top-panel countersink where recessed-area borders interfere.
- Design the top-panel joint around the available 20 mm screw length. Each screw must traverse the full captive nut and extend approximately 1 mm beyond it.

## Captive nuts

Each top-panel corner uses an inward-facing, side-loaded M3 hex nut pocket inside the ledge. The outside end is closed, hex walls prevent rotation, and a small entrance detent prevents an inserted nut from sliding out while the enclosure is handled or inverted. Nuts are inserted before the top panel is installed; no hand access is required while tightening.

The nut-height pocket remains rectangular for fit, then transitions to a 45-degree self-supporting roof with a narrow tip. The roof must not require support or leave a full-width horizontal bridge over the nut.

Add a small standalone corner/nut-trap fit-test view so nut insertion, retention, screw reach, and countersink fit can be checked without printing the enclosure.
