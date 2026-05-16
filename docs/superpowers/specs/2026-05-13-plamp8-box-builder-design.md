# plamp8 Modular Box Builder Design

## Goal

Create a modular OpenSCAD CAD builder for the `plamp8` relay enclosure. The first implementation should produce useful fit-test prints and establish reusable CAD modules for the final enclosure, without trying to finish the entire box in one pass.

The current `things/plamp8` double-wall outlet plate is the starting point. The builder should evolve this part in place, preserving its outlet cutout approach and inscription style while adding modular channels and views.

## CAD Part

Use the existing part directory:

```text
things/plamp8/
  generate.bash
  plamp8.scad
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
- Internal space for a 12V/5V PSU, 8-channel relay board, and diode wiring. These internals are represented as keepout placeholders in the first pass. The relay board can show known mounting hole positions, but detailed standoffs are not part of the first pass.

All connectors should be on the top panel except the 120V input, which may move to a side/back wall.

## CAD Architecture

Model reusable channel units as CAD modules, not separate final inserts.

The first pass creates a single printable top-panel concept plus separate fit-test coupons for each module. The final enclosure can later reuse the same modules in a full box body.

Core modules:

- `ac_duplex_channel_unit(label_a, label_b)`: One double-wall outlet plate area with two outlet cutouts, two toggle holes, labels, and underside alignment walls/ribs.
- `dc_barrel_channel_unit(label)`: One 2.1 mm barrel jack cutout, one toggle hole, label, and underside alignment walls/ribs.
- `usb_c_panel_unit()`: USB-C panel connector cutout using the measured 14 mm by 8 mm rectangle and two M3 screw holes 20 mm apart.
- `c13_inlet_unit()`: C13 inlet and switch cutout using the measured 1.9 inch by 2.0 inch opening, with tunable screw holes. This may be placed on a side wall in the final assembly.
- `psu_keepout()`: Internal 12V/5V PSU keepout using the measured 160 mm by 98 mm by 38 mm envelope. Do not add screw mounts until hole positions are measured.
- `relay_board_keepout()`: Internal Waveshare Pico relay keepout using the measured 145 mm by 90 mm by 40 mm envelope. Show four 5 mm mounting hole positions on a 135 mm by 70 mm XY pattern for layout planning.
- `top_panel_8ch()`: Places two AC duplex channel units and four DC barrel channel units on one top panel.
- `assembly()`: Shows the rough full box/top layout assembled in place.
- `plate()`: Lays out all printable/testable pieces separated for export.

## Dimensions And Parameters

Known values:

- Toggle switch mounting hole: `toggle_hole_d = 12`.
- Duplex outlet mounting has one visible center screw hole plus two screws under the face plate. These should be treated as available load paths for outlet retention where practical.
- 2.1 mm barrel jack mounting hole: `barrel_jack_hole_d = 12`.
- USB-C panel connector cutout: `usb_c_cutout_w = 14`, `usb_c_cutout_h = 8`.
- USB-C panel connector screws: two M3 screws, `usb_c_screw_spacing = 20`, centered around the rectangular cutout.
- C13 mains inlet/switch module cutout: `c13_cutout_w = 1.9 * 25.4`, `c13_cutout_h = 2.0 * 25.4`.
- C13 screw holes: left and right, vertically centered on the inlet; screw diameter and exact spacing remain tunable. Initial spacing should be derived from the 1.9 inch width minus 1-2 mm inset per side.
- PSU keepout: `psu_w = 160`, `psu_d = 98`, `psu_h = 38`.
- Waveshare Pico relay keepout: `relay_w = 145`, `relay_d = 90`, `relay_h = 40`.
- Waveshare Pico relay mounting holes: `relay_mount_hole_d = 5`, `relay_mount_x = 135`, `relay_mount_y = 70`.
- Final top/channel plate thickness: `plate_t = 3`.
- The existing `plamp8` outlet plate geometry is a useful starting reference.

Unknown values should be explicit parameters with conservative defaults:

- Toggle switch body keepout rectangle width/depth.
- 2.1 mm barrel jack nut/body keepout.
- C13 inlet screw diameter and exact screw spacing.
- PSU screw mount positions.
- Final enclosure width/depth/height and wall thickness.
- Internal keepout sizes for wire paths and diode wiring.

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

AC outlet channels must resist both downward and upward forces from plugging and unplugging cords. The outlet should not rely only on thin panel material around the cutout. The CAD should provide local stiffness and retention around the duplex channel, using the center screw and the two screws hidden under the face plate as mounting/load-transfer points where practical.

The first pass should prefer printable, easy-to-measure coupons over a highly detailed final enclosure. Each coupon should make one hardware fit question answerable.

Labels should be parameterized and readable. Revision branding should use `revision_string` so generated STLs can be tied to the commit hash or explicit dirty revision text.

Channel labels should be two lines: a large device name on the first line and a smaller channel/Pico-pin line on the second line. The strings should be top-level parameters so relay channel numbers and Pico pins can be assigned later. Default AC outlet device names are `Pump`, `Lights`, `Fan`, and `Aux`. Default DC barrel channel device names are `PH up`, `PH down`, `Agitator`, and `Nutrients`.

Revision branding is per printable part, not per repeated module. The full top panel should have one revision string total even if it contains two duplex channel modules and four DC channel modules. The eventual box body should also have one revision string. Individual fit-test coupons may include their own revision string because each coupon is a standalone printable part.

Label construction should follow the successful `plamp8` approach: text is extruded from a rounded rectangle that sits lower than the top surface, leaving the text flush with the panel surface rather than raised above it.

## Non-Goals For First Pass

- No detailed relay-board standoffs or fastener design, beyond showing the known mounting hole pattern for layout planning.
- No detailed PSU mount.
- No screw bosses for the final box unless they fall out naturally from the top-panel prototype.
- No separate removable cartridge inserts.
- No automatic layout solver. Placement is parametric but manually defined.
- No assumption that unknown connector dimensions are final.

## Testing And Verification

Use the CAD generator rather than direct OpenSCAD calls:

```bash
things/plamp8/generate.bash --revision fit-test-1 /tmp/plamp8_fit HEAD
```

Expected verification:

- `bash -n things/plamp8/generate.bash`
- Render all declared views using the generator.
- Confirm STL files are created and non-empty.
- Treat OpenSCAD non-manifold warnings as informational for early fit-test coupons unless the geometry is visibly empty or broken.

## Open Questions For Implementation

- Exact 2.1 mm barrel jack nut/body keepout behind the known 12 mm panel hole.
- Exact toggle switch rectangular body keepout size under the 12 mm mounting hole.
- C13 inlet screw diameter and exact screw spacing.
- Exact duplex outlet hidden faceplate screw positions and screw diameter.
- PSU screw mount positions.
- Final enclosure footprint and whether the C13 inlet goes on the back or side.
