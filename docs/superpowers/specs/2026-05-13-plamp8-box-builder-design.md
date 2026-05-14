# plamp8 Modular Box Builder Design

## Goal

Create a modular OpenSCAD CAD builder for the `plamp8` relay enclosure. The first implementation should produce useful fit-test prints and establish reusable CAD modules for the final enclosure, without trying to finish the entire box in one pass.

The current `things/plamp8` part remains a work-in-progress double-wall outlet plate with inscriptions. The new builder should live separately so the existing fit-tested part is not broken.

## New CAD Part

Add a new part directory:

```text
things/plamp8_box/
  generate.bash
  plamp8_box.scad
```

Use the existing `things/template.bash` and `things/3d_template/generate.bash` conventions.

The SCAD file must expose ordered views:

```scad
view = "assembly"; // [assembly, plate, ac_duplex_channel, dc_barrel_channel, usb_c_panel, c13_inlet, top_panel]
```

The generator will export views in this order, so keep the most useful visualization first and fit-test parts after.

## Product Model

The box controls eight relay channels:

- Four 120V outlet channels, physically represented as two duplex outlet channel units.
- Four 12V channels, physically represented as four barrel-jack channel units.
- One USB-C panel connector for service/control access.
- One C13 mains input with switch for 120V input, likely on a side/back wall rather than the top.
- Internal space for a 12V/5V PSU, 8-channel relay board, and diode wiring. These internals are represented as keepout placeholders in the first pass, not detailed mounts.

All connectors should be on the top panel except the 120V input, which may move to a side/back wall.

## CAD Architecture

Model reusable channel units as CAD modules, not separate final inserts.

The first pass creates a single printable top-panel concept plus separate fit-test coupons for each module. The final enclosure can later reuse the same modules in a full box body.

Core modules:

- `ac_duplex_channel_unit(label_a, label_b)`: One double-wall outlet plate area with two outlet cutouts, two toggle holes, labels, and underside alignment walls/ribs.
- `dc_barrel_channel_unit(label)`: One 2.1 mm barrel jack cutout, one toggle hole, label, and underside alignment walls/ribs.
- `usb_c_panel_unit()`: Placeholder rectangular cutout for a USB-C panel connector, with tunable width/height.
- `c13_inlet_unit()`: Placeholder C13 inlet and switch cutout, with tunable dimensions. This may be placed on a side wall in the final assembly.
- `top_panel_8ch()`: Places two AC duplex channel units and four DC barrel channel units on one top panel.
- `assembly()`: Shows the rough full box/top layout assembled in place.
- `plate()`: Lays out all printable/testable pieces separated for export.

## Dimensions And Parameters

Known values:

- Toggle switch mounting hole: `toggle_hole_d = 12`.
- Final top/channel plate thickness: `plate_t = 3`.
- The existing `plamp8` outlet plate geometry is a useful starting reference.

Unknown values should be explicit parameters with conservative defaults:

- Toggle switch body keepout rectangle width/depth.
- 2.1 mm barrel jack panel hole diameter and nut keepout.
- USB-C panel connector rectangular cutout dimensions.
- C13 inlet and switch cutout dimensions.
- Final enclosure width/depth/height and wall thickness.
- Internal keepout sizes for PSU, relay board, and wire paths.

Do not hide unknown hardware dimensions in magic numbers. Name them so they can be tuned after caliper measurements or fit-test prints.

## Views

`assembly`:

Show the rough assembled top panel and early enclosure context. This can be visually approximate in the first pass. It should make placement and spacing understandable.

`plate`:

Lay out all printable fit-test pieces separated on the build plane. This should include at least the AC duplex channel coupon, DC barrel channel coupon, USB-C panel coupon, C13 inlet coupon, and rough top panel if printable at current size.

Individual fit-test views:

- `ac_duplex_channel`: Render only the AC duplex channel test piece.
- `dc_barrel_channel`: Render only the DC barrel channel test piece.
- `usb_c_panel`: Render only the USB-C panel connector test piece.
- `c13_inlet`: Render only the C13 inlet/switch test piece.
- `top_panel`: Render only the rough top panel.

## Mechanical Intent

Underside alignment walls/ribs should be part of each channel module. They are not separate inserts; they are reusable CAD geometry that helps locate hardware and stiffen the panel.

The first pass should prefer printable, easy-to-measure coupons over a highly detailed final enclosure. Each coupon should make one hardware fit question answerable.

Labels should be parameterized and readable. Revision branding should use `revision_string` so generated STLs can be tied to the commit hash or explicit dirty revision text.

## Non-Goals For First Pass

- No detailed relay-board mount.
- No detailed PSU mount.
- No screw bosses for the final box unless they fall out naturally from the top-panel prototype.
- No separate removable cartridge inserts.
- No automatic layout solver. Placement is parametric but manually defined.
- No assumption that unknown connector dimensions are final.

## Testing And Verification

Use the CAD generator rather than direct OpenSCAD calls:

```bash
things/plamp8_box/generate.bash --revision fit-test-1 /tmp/plamp8_box_fit HEAD
```

Expected verification:

- `bash -n things/plamp8_box/generate.bash`
- Render all declared views using the generator.
- Confirm STL files are created and non-empty.
- Treat OpenSCAD non-manifold warnings as informational for early fit-test coupons unless the geometry is visibly empty or broken.

## Open Questions For Implementation

- Exact 2.1 mm barrel jack panel cutout diameter and body keepout.
- Exact toggle switch rectangular body keepout size under the 12 mm mounting hole.
- USB-C panel connector cutout dimensions.
- C13 inlet and switch dimensions.
- Final enclosure footprint and whether the C13 inlet goes on the back or side.
