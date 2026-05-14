$fn = 80;

view = "assembly"; // [assembly, plate, ac_duplex_channel, dc_barrel_channel, usb_c_panel, c13_inlet, top_panel]
revision_string = "dev";

// ---------------- global print parameters ----------------
plate_t = 3;
wall_t = 3;
alignment_wall_h = 8;
alignment_wall_t = 2;
corner_r = 6;

label_base_t = 0.45;
label_text_t = 0.45;
label_drop = 0.45;
label_font = "DejaVu Sans";
revision_font_size = 4;

fit_coupon_margin = 8;
part_gap = 18;

// ---------------- channel dimensions ----------------
ac_channel_w = 78;
ac_channel_h = 128;
dc_channel_w = 44;
dc_channel_h = 58;
service_panel_w = 44;
service_panel_h = 34;
c13_panel_w = 72;
c13_panel_h = 68;

// Outlet shape inherited from the plamp8 test plate.
outlet_hole_d = 34;
outlet_hole_h = 24;
outlet_cut_off_y = 2.5;
outlet_spacing = 40;

duplex_center_screw_d = 4;
duplex_hidden_screw_d = 3.5; // Tune after measuring the two faceplate-covered screws.
duplex_hidden_screw_spacing = 84;

toggle_hole_d = 12;
toggle_body_w = 18; // keepout placeholder
toggle_body_d = 24; // keepout placeholder

barrel_jack_hole_d = 12;
barrel_jack_body_d = 18; // nut/body keepout placeholder

usb_c_cutout_w = 14;
usb_c_cutout_h = 8;
usb_c_screw_d = 3.2;
usb_c_screw_spacing = 20;

inch = 25.4;
c13_cutout_w = 1.9 * inch;
c13_cutout_h = 2.0 * inch;
c13_screw_d = 3.5; // placeholder
c13_screw_inset = 1.5;
c13_screw_spacing = c13_cutout_w - 2 * c13_screw_inset;

// Internal keepouts.
psu_w = 160;
psu_d = 98;
psu_h = 38;

relay_w = 145;
relay_d = 90;
relay_h = 40;
relay_mount_hole_d = 5;
relay_mount_x = 135;
relay_mount_y = 70;

// Rough enclosure envelope.
box_w = 235;
box_d = 190;
box_h = 70;
top_panel_w = box_w;
top_panel_h = box_d;

// ---------------- helpers ----------------

module rounded_rect_2d(w, h, r) {
    hull() {
        for (x = [-1, 1], y = [-1, 1])
            translate([x * (w / 2 - r), y * (h / 2 - r)])
                circle(r = r);
    }
}

module rounded_plate(w, h, t = plate_t, r = corner_r) {
    linear_extrude(height = t)
        rounded_rect_2d(w, h, r);
}

module rounded_box(w, h, z, r = corner_r) {
    linear_extrude(height = z)
        rounded_rect_2d(w, h, r);
}

module screw_hole(d, depth = 30) {
    translate([0, 0, -depth / 2])
        cylinder(h = depth, d = d);
}

module rect_cutout(w, h, depth = 30) {
    translate([0, 0, -depth / 2])
        cube([w, h, depth], center = true);
}

module label_text(label, size = 5) {
    linear_extrude(height = label_text_t)
        text(label, size = size, font = label_font, halign = "center", valign = "center");
}

module flush_label(label, w, h, size = 5) {
    // Base sits below the top surface; text rises back to flush with the panel.
    translate([0, 0, plate_t - label_drop])
        rounded_box(w, h, label_base_t, 2);

    translate([0, 0, plate_t - label_drop])
        label_text(label, size);
}

module revision_mark() {
    flush_label(revision_string, 32, 9, revision_font_size);
}

module alignment_walls(w, h) {
    z = -alignment_wall_h;
    translate([0, h / 2 - alignment_wall_t / 2, z + alignment_wall_h / 2])
        cube([w, alignment_wall_t, alignment_wall_h], center = true);
    translate([0, -h / 2 + alignment_wall_t / 2, z + alignment_wall_h / 2])
        cube([w, alignment_wall_t, alignment_wall_h], center = true);
    translate([w / 2 - alignment_wall_t / 2, 0, z + alignment_wall_h / 2])
        cube([alignment_wall_t, h, alignment_wall_h], center = true);
    translate([-w / 2 + alignment_wall_t / 2, 0, z + alignment_wall_h / 2])
        cube([alignment_wall_t, h, alignment_wall_h], center = true);
}

module outlet_load_ribs() {
    // Local ribs transfer plug/unplug force into the panel instead of only the thin cutout edge.
    rib_w = ac_channel_w - 12;
    rib_h = 4;
    rib_z = -alignment_wall_h / 2;

    for (y = [-duplex_hidden_screw_spacing / 2, 0, duplex_hidden_screw_spacing / 2])
        translate([0, y, rib_z])
            cube([rib_w, rib_h, alignment_wall_h], center = true);
}

module outlet_roundish_cutout() {
    cut_y = outlet_hole_h / 2 + outlet_cut_off_y;

    difference() {
        screw_hole(outlet_hole_d);

        translate([-outlet_hole_d, cut_y, -20])
            cube([2 * outlet_hole_d, outlet_hole_d, 40]);

        translate([-outlet_hole_d, -cut_y - outlet_hole_d, -20])
            cube([2 * outlet_hole_d, outlet_hole_d, 40]);
    }
}

module duplex_channel_negative() {
    for (y = [-outlet_spacing / 2, outlet_spacing / 2])
        translate([0, y, plate_t / 2])
            outlet_roundish_cutout();

    screw_hole(duplex_center_screw_d);

    for (y = [-duplex_hidden_screw_spacing / 2, duplex_hidden_screw_spacing / 2])
        translate([0, y, 0])
            screw_hole(duplex_hidden_screw_d);

    for (y = [-outlet_spacing / 2, outlet_spacing / 2])
        translate([25, y, 0])
            screw_hole(toggle_hole_d);
}

module dc_channel_negative() {
    translate([-9, 0, 0])
        screw_hole(barrel_jack_hole_d);
    translate([12, 0, 0])
        screw_hole(toggle_hole_d);
}

module usb_c_panel_negative() {
    rect_cutout(usb_c_cutout_w, usb_c_cutout_h);
    for (x = [-usb_c_screw_spacing / 2, usb_c_screw_spacing / 2])
        translate([x, 0, 0])
            screw_hole(usb_c_screw_d);
}

module c13_inlet_negative() {
    rect_cutout(c13_cutout_w, c13_cutout_h);
    for (x = [-c13_screw_spacing / 2, c13_screw_spacing / 2])
        translate([x, 0, 0])
            screw_hole(c13_screw_d);
}

// ---------------- channel units ----------------

module ac_duplex_channel_unit(label_a = "AC 1", label_b = "AC 2", include_revision = true) {
    difference() {
        union() {
            rounded_plate(ac_channel_w, ac_channel_h);
            alignment_walls(ac_channel_w - 10, ac_channel_h - 10);
        }
        duplex_channel_negative();
    }

    translate([-22, outlet_spacing / 2 + 8, 0])
        flush_label(label_a, 28, 10, 5);
    translate([-22, -outlet_spacing / 2 - 8, 0])
        flush_label(label_b, 28, 10, 5);

    if (include_revision)
        translate([20, -ac_channel_h / 2 + 12, 0])
            revision_mark();
}

module dc_barrel_channel_unit(label = "12V", include_revision = true) {
    difference() {
        union() {
            rounded_plate(dc_channel_w, dc_channel_h);
            alignment_walls(dc_channel_w - 8, dc_channel_h - 8);
        }
        dc_channel_negative();
    }

    translate([0, -dc_channel_h / 2 + 10, 0])
        flush_label(label, 28, 9, 4.5);

    if (include_revision)
        translate([0, dc_channel_h / 2 - 9, 0])
            revision_mark();
}

module usb_c_panel_unit(include_revision = true) {
    difference() {
        union() {
            rounded_plate(service_panel_w, service_panel_h);
            alignment_walls(service_panel_w - 8, service_panel_h - 8);
        }
        usb_c_panel_negative();
    }

    translate([0, -service_panel_h / 2 + 8, 0])
        flush_label("USB-C", 30, 8, 4);

    if (include_revision)
        translate([0, service_panel_h / 2 - 8, 0])
            revision_mark();
}

module c13_inlet_unit(include_revision = true) {
    difference() {
        union() {
            rounded_plate(c13_panel_w, c13_panel_h);
            alignment_walls(c13_panel_w - 8, c13_panel_h - 8);
        }
        c13_inlet_negative();
    }

    translate([0, -c13_panel_h / 2 + 8, 0])
        flush_label("120V IN", 42, 9, 4.5);

    if (include_revision)
        translate([0, c13_panel_h / 2 - 8, 0])
            revision_mark();
}

// ---------------- internal context ----------------

module keepout_box(w, d, h, label) {
    color([1, 0.6, 0.1, 0.28])
        translate([0, 0, h / 2])
            cube([w, d, h], center = true);
    color([0.15, 0.15, 0.15, 1])
        translate([0, 0, h + 1])
            label_text(label, 6);
}

module psu_keepout() {
    keepout_box(psu_w, psu_d, psu_h, "PSU");
}

module relay_board_keepout() {
    keepout_box(relay_w, relay_d, relay_h, "Relay");
    color([0.1, 0.1, 0.1, 1])
        for (x = [-relay_mount_x / 2, relay_mount_x / 2], y = [-relay_mount_y / 2, relay_mount_y / 2])
            translate([x, y, relay_h + 2])
                cylinder(h = 2, d = relay_mount_hole_d);
}

// ---------------- composed parts ----------------

module top_panel_8ch(include_revision = true) {
    difference() {
        union() {
            rounded_plate(top_panel_w, top_panel_h, plate_t, 8);

            translate([-58, 34, 0])
                outlet_load_ribs();
            translate([58, 34, 0])
                outlet_load_ribs();
        }

        translate([-58, 34, 0])
            duplex_channel_negative();
        translate([58, 34, 0])
            duplex_channel_negative();

        for (i = [0:3])
            translate([-72 + i * 48, -58, 0])
                dc_channel_negative();

        translate([88, -5, 0])
            usb_c_panel_negative();
    }

    translate([-58, 34, 0])
        ac_channel_labels("AC 1", "AC 2");
    translate([58, 34, 0])
        ac_channel_labels("AC 3", "AC 4");

    for (i = [0:3])
        translate([-72 + i * 48, -58, 0])
            dc_channel_label(str("12V ", i + 1));

    translate([88, -5, 0])
        usb_c_label();

    if (include_revision)
        translate([top_panel_w / 2 - 28, -top_panel_h / 2 + 12, 0])
            revision_mark();
}

module ac_channel_labels(label_a, label_b) {
    translate([-22, outlet_spacing / 2 + 8, 0])
        flush_label(label_a, 28, 10, 5);
    translate([-22, -outlet_spacing / 2 - 8, 0])
        flush_label(label_b, 28, 10, 5);
}

module dc_channel_label(label) {
    translate([0, -dc_channel_h / 2 + 10, 0])
        flush_label(label, 28, 9, 4.5);
}

module usb_c_label() {
    translate([0, -service_panel_h / 2 + 8, 0])
        flush_label("USB-C", 30, 8, 4);
}

module box_context() {
    color([0.7, 0.72, 0.68, 0.35])
        difference() {
            translate([0, 0, -box_h])
                rounded_box(box_w, box_d, box_h, 8);
            translate([0, 0, -box_h + wall_t])
                rounded_box(box_w - 2 * wall_t, box_d - 2 * wall_t, box_h + 2, 6);
        }
}

// ---------------- views ----------------

module ac_duplex_channel() {
    ac_duplex_channel_unit("AC 1", "AC 2", true);
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
    translate([-130, 48, 0])
        ac_duplex_channel_unit("AC 1", "AC 2", true);
    translate([-48, 64, 0])
        dc_barrel_channel_unit("12V 1", true);
    translate([16, 64, 0])
        usb_c_panel_unit(true);
    translate([86, 48, 0])
        c13_inlet_unit(true);

    translate([0, -110, 0])
        top_panel_8ch(true);
}

module assembly() {
    box_context();

    translate([0, 0, 0])
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
} else {
    assembly();
}
