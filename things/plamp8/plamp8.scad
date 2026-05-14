$fn = 96;

view = "assembly"; // [assembly, plate]

// ---------------- dimensions ----------------
plate_w = 70;
plate_h = 120;
plate_t = 3;

corner_r = 6;

hole_d = 34;        // source cylinder diameter
hole_h = 24;        // final vertical height after trimming
hole_depth = 10;    // taller than plate_t for clean boolean
cut_off_y = 2.5;
outlet_spacing = 40;

screw_d = 4;
screw_spacing = 84;

letter_size = 6;
write_t = 0.75;
revision_string = "dev";


module write_text(string, font_size = letter_size, z0 = -0.25) {
    translate([0, 0, z0])
        linear_extrude(write_t)
            text(
                string,
                size = font_size,
                font = "DejaVu Sans",
                halign = "center",
                valign = "center"
            );
}

module round_hull(x, y, r, h) {
    dx = x - 2 * r;
    dy = y - 2 * r;

    translate([-dx / 2, -dy / 2, -h / 2])
        hull() {
            translate([0, 0, 0]) cylinder(h = h, r = r);
            translate([dx, 0, 0]) cylinder(h = h, r = r);
            translate([dx, dy, 0]) cylinder(h = h, r = r);
            translate([0, dy, 0]) cylinder(h = h, r = r);
        }
}

// ---------------- positive modules ----------------

module positive_plate_writings() {
    bfont = 7;
    sfont = 4;
    x1 = 0;
    y1 = 47;

    x2 = x1;
    y2 = -y1 + 5;

    y_line = -bfont - 1;

    translate([x1, y1, plate_t]) {
        write_text("Pump", bfont);
        translate([0, y_line, 0])
            write_text("ch 1 pin 21", sfont);
    }

    translate([x2, y2, plate_t]) {
        write_text("lights", bfont);
        translate([0, y_line, 0])
            write_text("ch 2 pin 22", sfont);
    }
}

module outlet_cover_positive() {
    translate([-plate_w / 2, -plate_h / 2, 0])
        cube([plate_w, plate_h, plate_t]);
}

// ---------------- negative modules ----------------

module negative_roundish_outlet() {
    /*
      Start with a cylinder. Chop off top and bottom with cubes.
      Result: circular sides, straight-ish top/bottom, controlled in 3D.
    */
    cut_y = hole_h / 2 + cut_off_y;

    difference() {
        translate([0, 0, -hole_depth / 2])
            cylinder(h = hole_depth, d = hole_d);

        translate([-hole_d, cut_y, -hole_depth])
            cube([2 * hole_d, hole_d, 2 * hole_depth]);

        translate([-hole_d, -cut_y - hole_d, -hole_depth])
            cube([2 * hole_d, hole_d, 2 * hole_depth]);
    }
}

module negative_plate_writings() {
    rev_x = -30;
    rev_y = 40;
    rev_z = plate_t;

    translate([rev_x, rev_y, rev_z])
        rotate([0, 0, 90])
            write_text(revision_string, 4);
}

module negative_screw_hole() {
    translate([0, 0, -hole_depth / 2])
        cylinder(h = hole_depth, d = screw_d);
}

// ---------------- subtraction module ----------------

module outlet_cover_negative() {
    // outlet openings
    for (y = [-outlet_spacing / 2, outlet_spacing / 2])
        translate([0, y, plate_t / 2])
            negative_roundish_outlet();

    /*
    // screw openings
    for (y = [-screw_spacing / 2, screw_spacing / 2])
        translate([0, y, plate_t / 2])
            negative_screw_hole();
    */
    negative_screw_hole();

    negative_plate_writings();

    hh = 3;
    hr = 3;
    hx = 40;
    hy = 54;
    h_y = screw_spacing / 2 - 13;
    h_z = plate_t + hh / 2 - 0.5;

    for (y = [-h_y, h_y])
        translate([0, y, h_z])
            round_hull(hx, hy, hr, hh);
}

// ---------------- final ----------------

module outlet_cover() {
    union() {
        difference() {
            outlet_cover_positive();
            outlet_cover_negative();
        }

        positive_plate_writings();
    }
}

module plate() {
    outlet_cover();
}

module assembly() {
    outlet_cover();
}

if (view == "plate") {
    plate();
} else if (view == "assembly") {
    assembly();
} else {
    assembly();
}
