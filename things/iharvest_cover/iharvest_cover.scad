$fn = 128;
view = "assembly"; // [assembly, plate]

/* generate.json
{
  "default_preset": "all-views-default",
  "presets": {
    "all-views-default": {
      "description": "Generate every declared iHarvest cover view",
      "items": ["view:assembly", "view:plate"]
    }
  }
}
*/

revision_string = "dev";

// -------- dimensions --------
W = 196.85; // 7.75 * 25.4
D = 165.10; // 6.50 * 25.4

plate_thick = 4;

// Sagitta: how much the arc middle drops below its endpoints.
top_sag = 10;
bottom_sag = 6.35;

corner_r = 6;

// holes
air_hole_d = 10;
wire_hole_d = 12;

N = 96;

// engraving
engrave_size = 5;
engrave_depth = 0.6;


// -------- arc math --------
function arc_radius(w, sag) =
    sag == 0 ? 1e9 : (w * w) / (8 * sag) + sag / 2;

function arc_y_center_below(x, y_edge, w, sag) =
    let(
        R = arc_radius(w, sag),
        yc = y_edge - R + sag
    )
    yc + sqrt(R * R - x * x);

function y_top(x) = arc_y_center_below(x, D / 2, W, top_sag);
function y_bottom(x) = arc_y_center_below(x, -D / 2, W, bottom_sag);


module cover_outline_raw_2d() {
    polygon(
        points = concat(
            [
                for (i = [0:N])
                let(x = -W / 2 + i * W / N)
                [x, y_top(x)]
            ],
            [
                [W / 2, y_bottom(W / 2)]
            ],
            [
                for (i = [N:-1:0])
                let(x = -W / 2 + i * W / N)
                [x, y_bottom(x)]
            ],
            [
                [-W / 2, y_top(-W / 2)]
            ]
        )
    );
}

module cover_outline_2d() {
    if (corner_r > 0) {
        offset(r = corner_r)
            offset(delta = -corner_r)
                cover_outline_raw_2d();
    } else {
        cover_outline_raw_2d();
    }
}

module top_plate() {
    linear_extrude(height = plate_thick)
        cover_outline_2d();
}

module holes() {
    translate([-30, 70, -20])
        cylinder(d = air_hole_d, h = 60);

    // translate([0, 70, -20]) cylinder(d = wire_hole_d, h = 60);

    translate([30, 70, -20])
        cylinder(d = air_hole_d, h = 60);
}

module engrave_revision_string() {
    translate([0, -D / 2 + 12, plate_thick - engrave_depth])
        linear_extrude(height = engrave_depth + 0.05)
            text(
                revision_string,
                size = engrave_size,
                font = "DejaVu Sans",
                halign = "center",
                valign = "center"
            );
}

module access_cover_flat() {
    difference() {
        top_plate();
        holes();
        engrave_revision_string();
    }
}

module handle() {
    h = 100;
    x = -h / 2;
    y = 0;
    d = 20;
    z = d / 2 + 3;

    translate([x, y, z])
        rotate([0, 90, 0])
            cylinder(d = d, h = h);
}

module assembly() {
    access_cover_flat();
    handle();
}

if (view == "plate") {
    access_cover_flat();
}

if (view == "assembly") {
    assembly();
}
