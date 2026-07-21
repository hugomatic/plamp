render_fn = 64;
$fn = render_fn;
view = "assembly"; // [assembly, plate]

/* generate.json
{
  "default_preset": "all-views-default",
  "presets": {
    "all-views-default": {
      "description": "Generate every declared positive-negative part view",
      "items": ["view:assembly", "view:plate"]
    }
  }
}
*/

letter_size = 6;
revision_string = "dev";

part_dx = 70;
part_dy = 130;
part_dz = 12;
corner_r = 20;

module write_text(string) {
    translate([0, 0, -0.25])
        linear_extrude(0.5)
            text(
                string,
                size = letter_size,
                font = "DejaVu Sans",
                halign = "center",
                valign = "center"
            );
}

module rounded_box(x, y, z, r) {
    dx = x - 2 * r;
    dy = y - 2 * r;
    translate([-dx / 2, -dy / 2, -z / 2])
        hull() {
            translate([0, 0, 0]) cylinder(h = z, r = r);
            translate([dx, 0, 0]) cylinder(h = z, r = r);
            translate([dx, dy, 0]) cylinder(h = z, r = r);
            translate([0, dy, 0]) cylinder(h = z, r = r);
        }
}

module part_positive() {
    translate([0, 0, -part_dz / 2])
        rounded_box(part_dx, part_dy, part_dz, corner_r);
}

module part_negative() {
    translate([0, 0, -part_dz])
        rotate([0, 180, 0])
            write_text(revision_string);
}

module part() {
    difference() {
        part_positive();
        part_negative();
    }
}

module plate() {
    rotate([180, 0, 0])
        part();
}

module assembly() {
    part();
}

if (view == "plate") {
    plate();
} else if (view == "assembly") {
    assembly();
} else {
    assembly();
}
