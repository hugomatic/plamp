$fn = 96;

view = "assembly"; // [assembly, plate, ac_duplex_channel, dc_barrel_channel, usb_c_panel, c13_inlet, top_panel]

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
outlet_toggle_x = 25;
outlet_group_x = 3;
outlet_group_w = 66;
outlet_group_h = 54;

screw_d = 4;
screw_spacing = 84;

// Modular box-builder dimensions. Keep these near the top for fit tuning.
toggle_hole_d = 12;

barrel_jack_hole_d = 12;
barrel_channel_w = 44;
barrel_channel_h = 58;
barrel_label_w = 34;
barrel_label_h = 10;
barrel_group_y = -8;
barrel_group_w = 40;
barrel_group_h = 42;

usb_c_panel_w = 44;
usb_c_panel_h = 34;
usb_c_label_w = 32;
usb_c_label_h = 9;
usb_c_group_y = -4;
usb_c_group_w = 36;
usb_c_group_h = 28;
usb_c_cutout_w = 14;
usb_c_cutout_h = 8;
usb_c_screw_d = 3.2;
usb_c_screw_spacing = 20;

inch = 25.4;
c13_panel_w = 72;
c13_panel_h = 68;
c13_label_w = 48;
c13_label_h = 10;
c13_group_w = 66;
c13_group_h = 64;
c13_cutout_w = 1.9 * inch;
c13_cutout_h = 2.0 * inch;
c13_screw_d = 3.5;
c13_screw_inset = 1.5;
c13_screw_spacing = c13_cutout_w - 2 * c13_screw_inset;

psu_w = 160;
psu_d = 98;
psu_h = 38;

relay_w = 145;
relay_d = 90;
relay_h = 40;
relay_mount_hole_d = 5;
relay_mount_x = 135;
relay_mount_y = 70;

box_w = 235;
box_d = 190;
box_h = 70;
wall_t = 3;
top_panel_w = box_w;
top_panel_h = box_d;

alignment_wall_h = 8;
alignment_wall_t = 2;
label_pocket_h = 3;
label_pocket_r = 3;
revision_label_w = 34;
revision_label_h = 9;

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
        write_text("Pump", bfont, -write_t);
        translate([0, y_line, 0])
            write_text("ch 1 pin 21", sfont, -write_t);
    }

    translate([x2, y2, plate_t]) {
        write_text("lights", bfont, -write_t);
        translate([0, y_line, 0])
            write_text("ch 2 pin 22", sfont, -write_t);
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

module outlet_cover_negative(include_revision = true) {
    // outlet openings
    for (y = [-outlet_spacing / 2, outlet_spacing / 2])
        translate([0, y, plate_t / 2])
            negative_roundish_outlet();

    for (y = [-outlet_spacing / 2, outlet_spacing / 2])
        translate([outlet_toggle_x, y, 0])
            screw_hole(toggle_hole_d);

    /*
    // screw openings
    for (y = [-screw_spacing / 2, screw_spacing / 2])
        translate([0, y, plate_t / 2])
            negative_screw_hole();
    */
    negative_screw_hole();

    if (include_revision)
        negative_plate_writings();

    hh = 3;
    hr = 3;
    h_y = screw_spacing / 2 - 13;
    h_z = plate_t + hh / 2 - 0.5;

    for (y = [-h_y, h_y])
        translate([outlet_group_x, y, h_z])
            round_hull(outlet_group_w, outlet_group_h, hr, hh);
}

// ---------------- final ----------------

module outlet_cover(include_revision = true) {
    union() {
        difference() {
            outlet_cover_positive();
            outlet_cover_negative(include_revision);
        }

        positive_plate_writings();
    }
}

// ---------------- modular fit-test units ----------------

module alignment_walls(w, h) {
    z = -alignment_wall_h / 2;

    translate([0, h / 2 - alignment_wall_t / 2, z])
        cube([w, alignment_wall_t, alignment_wall_h], center = true);
    translate([0, -h / 2 + alignment_wall_t / 2, z])
        cube([w, alignment_wall_t, alignment_wall_h], center = true);
    translate([w / 2 - alignment_wall_t / 2, 0, z])
        cube([alignment_wall_t, h, alignment_wall_h], center = true);
    translate([-w / 2 + alignment_wall_t / 2, 0, z])
        cube([alignment_wall_t, h, alignment_wall_h], center = true);
}

module screw_hole(d, depth = 30) {
    translate([0, 0, -depth / 2])
        cylinder(h = depth, d = d);
}

module rect_cutout(w, h, depth = 30) {
    translate([0, 0, -depth / 2])
        cube([w, h, depth], center = true);
}

module fit_plate(w, h) {
    translate([-w / 2, -h / 2, 0])
        cube([w, h, plate_t]);
}

module label_pocket(w, h) {
    translate([0, 0, plate_t + label_pocket_h / 2 - 0.5])
        round_hull(w, h, label_pocket_r, label_pocket_h);
}

module flush_label(label, font_size = 5) {
    translate([0, 0, plate_t])
        write_text(label, font_size, -write_t);
}

module flush_revision_label() {
    flush_label(revision_string, 4);
}

module barrel_channel_negative() {
    translate([-9, 0, 0])
        screw_hole(barrel_jack_hole_d);
    translate([12, 0, 0])
        screw_hole(toggle_hole_d);

    translate([0, barrel_group_y, 0])
        label_pocket(barrel_group_w, barrel_group_h);
}

module barrel_revision_negative() {
    translate([0, barrel_channel_h / 2 - 9, 0])
        label_pocket(revision_label_w, revision_label_h);
}

module dc_barrel_channel_unit(label = "12V 1", include_revision = true) {
    difference() {
        union() {
            fit_plate(barrel_channel_w, barrel_channel_h);
            alignment_walls(barrel_channel_w - 8, barrel_channel_h - 8);
        }
        barrel_channel_negative();
        if (include_revision)
            barrel_revision_negative();
    }

    translate([0, -barrel_channel_h / 2 + 10, 0])
        flush_label(label, 4.5);

    if (include_revision)
        translate([0, barrel_channel_h / 2 - 9, 0])
            flush_revision_label();
}

module usb_c_panel_negative() {
    rect_cutout(usb_c_cutout_w, usb_c_cutout_h);

    for (x = [-usb_c_screw_spacing / 2, usb_c_screw_spacing / 2])
        translate([x, 0, 0])
            screw_hole(usb_c_screw_d);

    translate([0, usb_c_group_y, 0])
        label_pocket(usb_c_group_w, usb_c_group_h);
}

module usb_c_revision_negative() {
    translate([0, usb_c_panel_h / 2 - 8, 0])
        label_pocket(revision_label_w, revision_label_h);
}

module usb_c_panel_unit(include_revision = true) {
    difference() {
        union() {
            fit_plate(usb_c_panel_w, usb_c_panel_h);
            alignment_walls(usb_c_panel_w - 8, usb_c_panel_h - 8);
        }
        usb_c_panel_negative();
        if (include_revision)
            usb_c_revision_negative();
    }

    translate([0, -usb_c_panel_h / 2 + 8, 0])
        flush_label("USB-C", 4);

    if (include_revision)
        translate([0, usb_c_panel_h / 2 - 8, 0])
            flush_revision_label();
}

module c13_inlet_negative() {
    rect_cutout(c13_cutout_w, c13_cutout_h);

    for (x = [-c13_screw_spacing / 2, c13_screw_spacing / 2])
        translate([x, 0, 0])
            screw_hole(c13_screw_d);

    label_pocket(c13_group_w, c13_group_h);
}

module c13_revision_negative() {
    translate([0, c13_panel_h / 2 - 8, 0])
        label_pocket(revision_label_w, revision_label_h);
}

module c13_inlet_unit(include_revision = true) {
    difference() {
        union() {
            fit_plate(c13_panel_w, c13_panel_h);
            alignment_walls(c13_panel_w - 8, c13_panel_h - 8);
        }
        c13_inlet_negative();
        if (include_revision)
            c13_revision_negative();
    }

    translate([0, -c13_panel_h / 2 + 8, 0])
        flush_label("120V IN", 4.5);

    if (include_revision)
        translate([0, c13_panel_h / 2 - 8, 0])
            flush_revision_label();
}

module psu_keepout() {
    color([1, 0.6, 0.1, 0.25])
        translate([0, 0, psu_h / 2])
            cube([psu_w, psu_d, psu_h], center = true);
}

module relay_board_keepout() {
    color([0.1, 0.7, 0.2, 0.25])
        translate([0, 0, relay_h / 2])
            cube([relay_w, relay_d, relay_h], center = true);

    color([0, 0, 0, 1])
        for (x = [-relay_mount_x / 2, relay_mount_x / 2], y = [-relay_mount_y / 2, relay_mount_y / 2])
            translate([x, y, relay_h + 1])
                cylinder(h = 2, d = relay_mount_hole_d);
}

module top_panel_8ch(include_revision = true) {
    difference() {
        fit_plate(top_panel_w, top_panel_h);

        translate([-58, 34, 0])
            outlet_cover_negative(false);
        translate([58, 34, 0])
            outlet_cover_negative(false);

        for (i = [0:3])
            translate([-72 + i * 48, -58, 0])
                barrel_channel_negative();

        translate([88, -5, 0])
            usb_c_panel_negative();

        if (include_revision)
            translate([top_panel_w / 2 - 28, -top_panel_h / 2 + 12, 0])
                label_pocket(revision_label_w, revision_label_h);
    }

    translate([-58, 34, 0])
        positive_plate_writings();
    translate([58, 34, 0])
        positive_plate_writings();

    for (i = [0:3])
        translate([-72 + i * 48, -58 - barrel_channel_h / 2 + 10, 0])
            flush_label(str("12V ", i + 1), 4.5);

    translate([88, -5 - usb_c_panel_h / 2 + 8, 0])
        flush_label("USB-C", 4);

    if (include_revision)
        translate([top_panel_w / 2 - 28, -top_panel_h / 2 + 12, 0])
            flush_revision_label();
}

module box_context() {
    color([0.7, 0.72, 0.68, 0.35])
        difference() {
            translate([-box_w / 2, -box_d / 2, -box_h])
                cube([box_w, box_d, box_h]);
            translate([-box_w / 2 + wall_t, -box_d / 2 + wall_t, -box_h + wall_t])
                cube([box_w - 2 * wall_t, box_d - 2 * wall_t, box_h + 2]);
        }
}

// ---------------- views ----------------

module ac_duplex_channel() {
    outlet_cover(true);
}

module dc_barrel_channel() {
    dc_barrel_channel_unit("12V 1", true);
}

module usb_c_panel() {
    usb_c_panel_unit(true);
}

module c13_inlet() {
    c13_inlet_unit(true);
}

module top_panel() {
    top_panel_8ch(true);
}

module plate() {
    translate([-126, 46, 0])
        outlet_cover(true);
    translate([-48, 62, 0])
        dc_barrel_channel_unit("12V 1", true);
    translate([16, 62, 0])
        usb_c_panel_unit(true);
    translate([88, 46, 0])
        c13_inlet_unit(true);

    translate([0, -112, 0])
        top_panel_8ch(true);
}

module assembly() {
    box_context();
    top_panel_8ch(true);

    translate([0, -box_d / 2 - 0.1, -box_h / 2])
        rotate([90, 0, 0])
            c13_inlet_unit(false);

    translate([-34, 20, -box_h + wall_t])
        psu_keepout();
    translate([42, -38, -box_h + wall_t])
        relay_board_keepout();
}

if (view == "plate") {
    plate();
} else if (view == "ac_duplex_channel") {
    ac_duplex_channel();
} else if (view == "dc_barrel_channel") {
    dc_barrel_channel();
} else if (view == "usb_c_panel") {
    usb_c_panel();
} else if (view == "c13_inlet") {
    c13_inlet();
} else if (view == "top_panel") {
    top_panel();
} else if (view == "assembly") {
    assembly();
} else {
    assembly();
}
