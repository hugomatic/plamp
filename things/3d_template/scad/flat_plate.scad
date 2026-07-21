render_fn = 96;
$fn = render_fn;
view = "assembly"; // [assembly, plate]

/* generate.json
{
  "default_preset": "all-views-default",
  "presets": {
    "all-views-default": {
      "description": "Generate every declared flat-plate view",
      "items": ["view:assembly", "view:plate"]
    }
  }
}
*/

revision_string = "dev";

plate_w = 100;
plate_d = 60;
plate_h = 4;
corner_r = 5;
letter_size = 5;

module rounded_rect_2d(w, d, r) {
    hull() {
        for (x = [-1, 1], y = [-1, 1])
            translate([x * (w / 2 - r), y * (d / 2 - r)])
                circle(r = r);
    }
}

module plate_positive() {
    linear_extrude(height = plate_h)
        rounded_rect_2d(plate_w, plate_d, corner_r);
}

module plate_negative() {
    translate([0, 0, plate_h - 0.35])
        linear_extrude(height = 0.45)
            text(
                revision_string,
                size = letter_size,
                font = "DejaVu Sans",
                halign = "center",
                valign = "center"
            );
}

module part() {
    difference() {
        plate_positive();
        plate_negative();
    }
}

module plate() {
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
