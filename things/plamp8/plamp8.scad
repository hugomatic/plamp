render_fn = 96;
render_text = true;
$fn = render_fn;

view = "assembly"; // [assembly, box, top_panel, sub_panel, plate, ac_duplex_channel, dc_barrel_channel, usb_c_panel, c13_inlet]

dc_connector_type = "xt60"; // [barrel, xt60]

/* [assembly view options] */

// show / hide box
show_box = true;
show_psu = false;
show_relay = false;
show_top_outline = false;
show_sub_panel = false;
show_top_panel = false;


/* [box features] */

//box features: ledge
feature_ledge = true;
//box features: floor anchors (tie wraps)
feature_psu_tie_wrap_anchors = false;
//box features: wall anchors (tie wraps)
feature_psu_tie_wrap_anchors_wall = false;
//box features: power module bottom screw mounts
feature_power_screw_mounts = true;
feature_ph_ledge_holes = true;


/* [dimensions] */

// height between the floor and the ledge
internal_clearance_h = 80;
outlet_plate_left = 46;
outlet_plate_right = 76;
plate_h = 120;
plate_t = 3;

corner_r = 6;

hole_d = 34;        // source cylinder diameter
hole_h = 24;        // final vertical height after trimming
hole_depth = 10;    // taller than plate_t for clean boolean
cut_off_y = 2.5;
outlet_spacing = 41;
outlet_feature_x = -4;
outlet_toggle_x = 32;
outlet_group_x = 8;
outlet_group_w = 104;
outlet_group_h = 56;

screw_d = 4;
panel_nut_d = 7.4;
panel_nut_h = 3.4;
screw_spacing = 84;

// Modular box-builder dimensions. Keep these near the top for fit tuning.
toggle_hole_d = 12;


/* [components dimensions] */

barrel_jack_hole_d = 12;
barrel_channel_w = 70;
barrel_channel_h = 58;
barrel_label_w = 34;
barrel_label_h = 10;
barrel_label_x = 7;
barrel_group_y = -8;
barrel_group_x = 5;
barrel_group_w = 70;
barrel_group_h = 46;
barrel_jack_x = -13;
barrel_toggle_x = 8;
dc_toggle_x_extra = dc_connector_type == "xt60" ? 8 : 0;
xt60_x_extra = dc_connector_type == "xt60" ? 3 : 0;
xt60_cutout_w = 19;
xt60_cutout_h = 12;
xt60_face_w = 35;
xt60_face_h = 16;
xt60_screw_spacing = 25;
xt60_screw_d = 3.2;

usb_c_panel_w = 44;
usb_c_panel_h = 34;
usb_c_label_w = 32;
usb_c_label_h = 9;
usb_c_group_y = -4;
usb_c_group_w = 36;
usb_c_group_h = 28;
usb_c_cutout_w = 14;
usb_c_cutout_h = 8;
usb_c_wire_cutout_w = 10;
usb_c_wire_cutout_h = 16;
usb_c_screw_d = 3.2;
usb_c_screw_spacing = 20;

c13_panel_w = 72;
c13_panel_h = 68;
c13_label_w = 48;
c13_label_h = 10;
c13_group_w = 66;
c13_group_h = 64;
inch = 24.5;
c13_face_w_inch = 1.9;
c13_face_h_inch = 2.0;

c13_cutout_w = 28;
c13_cutout_h = 48;
c13_wire_cutout_w = c13_cutout_w;
c13_wire_cutout_h = c13_cutout_h;
c13_screw_d = 3.5;
c13_screw_inset = 1.5;

psu_w = 134;
psu_d = 36;
psu_h = 23;
psu_mount_hole_d = 4.5;
psu_mount_x_inset = 8.25;
psu_mount_chamfer_d = 9;
psu_wall_clearance = 1;
psu_anchor_r = 5;
psu_anchor_l = 14;
psu_anchor_slot_w = 5;
psu_anchor_slot_h = 2.5;
psu_anchor_slot_z = 1;
psu_anchor_gap = 5;
psu_anchor_inset = 20;
psu_stop_l = 10;
psu_stop_t = 4;
psu_stop_h = 4;
psu_stop_anchor_clearance = 1;

converter_w = 27;
converter_d = 46;
converter_h = 14;
converter_mount_spacing = 50;
converter_mount_hole_d = 4.5;
converter_mount_chamfer_d = 9;

relay_w = 145;
relay_d = 90;
relay_h = 40;
relay_mount_hole_d = 5;
relay_mount_x = 135;
relay_mount_y = 70;
relay_countersink_d = 9;

retaining_corner_l = 5;
retaining_corner_t = 2;
retaining_corner_h = 5;

wall_t = 3;
relay_countersink_h = wall_t;
box_h = internal_clearance_h + wall_t;
panel_margin = 5;
top_outline_w = 2;
top_outline_h = 1;
ledge_w = 10;
ledge_r = ledge_w;
panel_screw_inset = 4;
internal_psu_y = 10;
internal_psu_rot_z = 90;
internal_converter_x = 45;
internal_converter_y = -70;
internal_converter_rot_z = 0;
internal_relay_x = -50;
internal_relay_y = 0;
internal_relay_rot_z = 90;
vent_hole_d = 5;
vent_hole_spacing = 10;
vent_wall_margin = 10;
vent_top_margin = ledge_r + vent_hole_d;
service_row_y = 58;
ac_row_y = -63;
dc_row_y = -106;
left_ac_x = -66;
right_ac_x = 40;

plate_w = outlet_plate_left + outlet_plate_right;

psu_wall_anchor_z = psu_h + psu_anchor_gap;
psu_stop_between_x_anchors_l = psu_w - 2 * psu_anchor_inset - psu_anchor_l - 2 * psu_stop_anchor_clearance;
psu_stop_between_y_anchors_l = psu_d - 2 * psu_anchor_inset - psu_anchor_l - 2 * psu_stop_anchor_clearance;

c13_face_w = c13_face_w_inch * inch;
c13_face_h = c13_face_h_inch * inch;
c13_screw_spacing = c13_face_w - 2 * c13_screw_inset;

toggle_label_x_offset = 15;
toggle_label_step = 7;
toggle_label_font = 3.2;
sub_panel_switch_w = 20;
sub_panel_switch_h = 32.5;
sub_panel_socket_w = 35;
sub_panel_socket_h = 70;
sub_panel_socket_screw_spacing = 82;
sub_panel_socket_screw_boss_d = 12;
sub_panel_socket_raise_h = 2.5;
sub_panel_usb_c_cutout_w = 12.5;
sub_panel_usb_c_cutout_h = 10.5;
sub_panel_wall = 10;
sub_panel_base_h = 5;
sub_panel_h = 10;
ph_ledge_gap_clearance = 5;
ph_ledge_gap_w = sub_panel_switch_w + 2 * ph_ledge_gap_clearance;


outlet_right_x = right_ac_x + outlet_group_x + outlet_group_w / 2;
usb_c_panel_x = outlet_right_x - usb_c_group_w / 2;
usb_c_panel_y = 14;
c13_panel_x = outlet_right_x - c13_group_w / 2;
dc_grid_x = left_ac_x + outlet_group_x - outlet_group_w / 2 - barrel_group_x + barrel_group_w / 2;
dc_grid_y = service_row_y + c13_group_h / 2 - barrel_group_y - barrel_group_h / 2;
dc_channel_gap = (
    outlet_right_x - c13_group_w
    - dc_grid_x - barrel_group_w - barrel_group_x - barrel_group_w / 2
) / 2;
dc_col_spacing = barrel_group_w + dc_channel_gap;
dc_row_spacing = barrel_group_h + dc_channel_gap;
nutrients_recess_right_x = dc_grid_x + dc_col_spacing + barrel_group_x + barrel_group_w / 2;
nutrients_recess_bottom_y = dc_grid_y - dc_row_spacing + barrel_group_y - barrel_group_h / 2;
revision_x = (nutrients_recess_right_x + usb_c_panel_x - usb_c_group_w / 2) / 2;
revision_y = usb_c_panel_y + usb_c_group_y - usb_c_group_h / 2 + 9 / 2;
top_panel_revision_label_w = 2 * (revision_x - (c13_panel_x - c13_group_w / 2));
ledge_top_z = -(plate_t + sub_panel_h);

content_left_x = left_ac_x + outlet_group_x - outlet_group_w / 2;
content_right_x = outlet_right_x;
content_bottom_y = ac_row_y - (screw_spacing / 2 - 13) - outlet_group_h / 2;
content_top_y = service_row_y + c13_group_h / 2;
top_panel_w = content_right_x - content_left_x + 2 * panel_margin;
top_panel_h = content_top_y - content_bottom_y + 2 * panel_margin;
box_inner_w = top_panel_w;
box_inner_d = top_panel_h;
box_w = box_inner_w + 2 * wall_t;
box_d = box_inner_d + 2 * wall_t;
layout_offset_x = panel_margin - content_left_x;
layout_offset_y = panel_margin - content_bottom_y;
box_inner_x = wall_t;
box_inner_y = wall_t;
internal_psu_x = top_panel_w / 2 - psu_d / 2 - retaining_corner_l - psu_wall_clearance;

alignment_wall_h = 8;
alignment_wall_t = 2;
label_pocket_h = 3;
label_pocket_r = 3;
revision_label_w = 26;
revision_label_h = 9;
box_revision_font = 6;

letter_size = 6;
write_t = 0.75;
revision_string = "dev";

ac_devices = ["Pump", "Lights", "Fan", "Aux"];
ac_details = ["CH1 GP21 110V AC", "CH2 GP20 110V AC", "CH3 GP19 110V AC", "CH4 GP18 110V AC"];
dc_devices = ["PH Up", "PH Down", "Agitator", "Nutrients"];
dc_details = ["CH5 GP17 12V DC", "CH6 GP16 12V DC", "CH7 GP15 12V DC", "CH8 GP14 12V DC"];


module write_text(string, font_size = letter_size, z0 = -0.25) {
    if (render_text)
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

module flush_two_line_label(device, detail, big_font = 5, small_font = 3.2, line_gap = 6) {
    translate([0, line_gap / 2, plate_t])
        write_text(device, big_font, -write_t);
    translate([0, -line_gap / 2, plate_t])
        write_text(detail, small_font, -write_t);
}

module positive_plate_writings(
    device_a = "Pump",
    detail_a = "ch 1 pin ?",
    device_b = "Lights",
    detail_b = "ch 2 pin ?"
) {
    bfont = 7;
    sfont = 4;
    x1 = 0;
    y1 = 47;

    x2 = x1;
    y2 = -y1 + 5;

    y_line = -bfont - 1;

    translate([x1, y1, plate_t]) {
        write_text(device_a, bfont, -write_t);
        translate([0, y_line, 0])
            write_text(detail_a, sfont, -write_t);
    }
    translate([outlet_toggle_x + toggle_label_x_offset, outlet_spacing / 2, 0])
        toggle_state_labels();

    translate([x2, y2, plate_t]) {
        write_text(device_b, bfont, -write_t);
        translate([0, y_line, 0])
            write_text(detail_b, sfont, -write_t);
    }
    translate([outlet_toggle_x + toggle_label_x_offset, -outlet_spacing / 2, 0])
        toggle_state_labels();
}

module outlet_cover_positive() {
    translate([-outlet_plate_left, -plate_h / 2, 0])
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
        translate([outlet_feature_x, y, plate_t / 2])
            negative_roundish_outlet();

    for (y = [-outlet_spacing / 2, outlet_spacing / 2])
        translate([outlet_toggle_x, y, 0])
            screw_hole(toggle_hole_d);

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

module sub_panel_8ch_positive() {
    base_h = sub_panel_base_h;
    lip_h = sub_panel_h - base_h;

    union() {
        cube([top_panel_w, top_panel_h, base_h]);

        translate([0, 0, base_h]) {
            cube([top_panel_w, sub_panel_wall, lip_h]);
            translate([0, top_panel_h - sub_panel_wall, 0])
                cube([top_panel_w, sub_panel_wall, lip_h]);
            translate([0, sub_panel_wall, 0])
                cube([sub_panel_wall, top_panel_h - 2 * sub_panel_wall, lip_h]);
            translate([top_panel_w - sub_panel_wall, sub_panel_wall, 0])
                cube([sub_panel_wall, top_panel_h - 2 * sub_panel_wall, lip_h]);
        }
    }
}

module sub_panel_socket_screw_bosses() {
    for (x = [left_ac_x, right_ac_x])
        for (y = [-sub_panel_socket_screw_spacing / 2, sub_panel_socket_screw_spacing / 2])
            translate([x + outlet_feature_x, ac_row_y + y, sub_panel_base_h])
                cylinder(h = sub_panel_socket_raise_h, d = sub_panel_socket_screw_boss_d);
}

module sub_panel_barrel_channel_negative() {
    translate([dc_connector_x(), 0, 0]) {
        if (dc_connector_type == "xt60")
            xt60_connector_negative();
        else
            screw_hole(barrel_jack_hole_d);
    }
    translate([dc_toggle_x(), 0, 0])
        rect_cutout(sub_panel_switch_w, sub_panel_switch_h);
}

module sub_panel_usb_c_negative() {
    rect_cutout(sub_panel_usb_c_cutout_w, sub_panel_usb_c_cutout_h);

    for (x = [-usb_c_screw_spacing / 2, usb_c_screw_spacing / 2])
        translate([x, 0, 0])
            screw_hole(usb_c_screw_d);
}

module sub_panel_c13_negative() {
    rect_cutout(c13_cutout_w, c13_cutout_h);

    for (x = [-c13_screw_spacing / 2, c13_screw_spacing / 2])
        translate([x, 0, 0])
            screw_hole(c13_screw_d);
}

module sub_panel_8ch_negative() {
    for (x = [left_ac_x, right_ac_x]) {
        translate([x + outlet_feature_x, ac_row_y, plate_t / 2])
            rect_cutout(sub_panel_socket_w, sub_panel_socket_h);
        for (y = [-sub_panel_socket_screw_spacing / 2, sub_panel_socket_screw_spacing / 2])
            translate([x + outlet_feature_x, ac_row_y + y, 0])
                screw_hole(screw_d);

        for (y = [-outlet_spacing / 2, outlet_spacing / 2])
            translate([x + outlet_toggle_x, ac_row_y + y, 0])
                rect_cutout(sub_panel_switch_w, sub_panel_switch_h);
    }

    for (i = [0:3])
        translate([dc_channel_x(i), dc_channel_y(i), 0])
            sub_panel_barrel_channel_negative();

    translate([usb_c_panel_x, usb_c_panel_y, 0])
        sub_panel_usb_c_negative();

    translate([c13_panel_x, service_row_y, 0])
        sub_panel_c13_negative();

    panel_corner_screw_holes();

    translate([revision_x, revision_y, sub_panel_base_h])
        write_text(revision_string, 4, -0.01);
}

// ---------------- final ----------------

module outlet_cover(
    include_revision = true,
    device_a = "Pump",
    detail_a = "ch 1 pin ?",
    device_b = "Lights",
    detail_b = "ch 2 pin ?"
) {
    union() {
        difference() {
            outlet_cover_positive();
            outlet_cover_negative(include_revision);
        }

        positive_plate_writings(device_a, detail_a, device_b, detail_b);
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
    translate([0, 0, plate_t / 2])
        cube([w, h, depth], center = true);
}

module fit_plate(w, h) {
    translate([-w / 2, -h / 2, 0])
        cube([w, h, plate_t]);
}

module fit_plate_from_origin(w, h) {
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

module toggle_state_labels() {
    translate([0, toggle_label_step, 0])
        flush_label("Auto", toggle_label_font);
    flush_label("Off", toggle_label_font);
    translate([0, -toggle_label_step, 0])
        flush_label("On", toggle_label_font);
}

module flush_revision_label() {
    flush_label(revision_string, 4);
}

module barrel_channel_negative() {
    translate([dc_connector_x(), 0, 0]) {
        if (dc_connector_type == "xt60")
            xt60_connector_negative();
        else
            screw_hole(barrel_jack_hole_d);
    }
    translate([dc_toggle_x(), 0, 0])
        screw_hole(toggle_hole_d);

    translate([barrel_group_x, barrel_group_y, 0])
        label_pocket(barrel_group_w, barrel_group_h);
}

module xt60_connector_negative() {
    rect_cutout(xt60_cutout_w, xt60_cutout_h);

    for (x = [-xt60_screw_spacing / 2, xt60_screw_spacing / 2])
        translate([x, 0, 0])
            screw_hole(xt60_screw_d);
}

module barrel_revision_negative() {
    translate([0, barrel_channel_h / 2 - 9, 0])
        label_pocket(revision_label_w, revision_label_h);
}

module dc_barrel_channel_unit(device = "PH Up", detail = "CH5 GP17 12V DC", include_revision = true) {
    difference() {
        union() {
            fit_plate(barrel_channel_w, barrel_channel_h);
            alignment_walls(barrel_channel_w - 8, barrel_channel_h - 8);
        }
        barrel_channel_negative();
        if (include_revision)
            barrel_revision_negative();
    }

    translate([barrel_label_x, -barrel_channel_h / 2 + 11, 0])
        flush_two_line_label(device, detail, 4.3, 3.1, 5);
    translate([dc_toggle_x() + toggle_label_x_offset, 0, 0])
        toggle_state_labels();

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
        flush_label("COM", 4);

    if (include_revision)
        translate([0, usb_c_panel_h / 2 - 8, 0])
            flush_revision_label();
}

module c13_inlet_negative() {
    rect_cutout(c13_cutout_w, c13_cutout_h);
    rect_cutout(c13_wire_cutout_w, c13_wire_cutout_h);

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

    if (include_revision)
        translate([0, c13_panel_h / 2 - 8, 0])
            flush_revision_label();
}

module psu_keepout() {
    color([1, 0.6, 0.1, 0.25])
        translate([0, 0, psu_h / 2])
            cube([psu_w, psu_d, psu_h], center = true);

    color([0, 0, 0, 1])
        psu_mount_markers(psu_h + 1);
}

module converter_keepout() {
    color([0.8, 0.25, 0.95, 0.25])
        translate([0, 0, converter_h / 2])
            cube([converter_w, converter_d, converter_h], center = true);

    color([0, 0, 0, 1])
        for (y = [-converter_mount_spacing / 2, converter_mount_spacing / 2])
            translate([0, y, converter_h + 1])
                cylinder(h = 2, d = converter_mount_hole_d);
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

function dc_channel_x(i) = dc_grid_x + (i % 2) * dc_col_spacing;
function dc_channel_y(i) = dc_grid_y - floor(i / 2) * dc_row_spacing;
function dc_connector_x() = barrel_jack_x + xt60_x_extra;
function dc_toggle_x() = barrel_toggle_x + dc_toggle_x_extra;
function top_ledge_gap_center_for_dc_toggle(i) = layout_offset_x + dc_channel_x(i) + dc_toggle_x();
function top_ledge_gap_start(i) = max(0, top_ledge_gap_center_for_dc_toggle(i) - ph_ledge_gap_w / 2);
function top_ledge_gap_end(i, length) = min(length, top_ledge_gap_center_for_dc_toggle(i) + ph_ledge_gap_w / 2);

module top_panel_8ch(include_revision = true) {
    translate([layout_offset_x, layout_offset_y, 0]) {
        difference() {
            translate([-layout_offset_x, -layout_offset_y, 0])
                fit_plate_from_origin(top_panel_w, top_panel_h);

            translate([left_ac_x, ac_row_y, 0])
                outlet_cover_negative(false);
            translate([right_ac_x, ac_row_y, 0])
                outlet_cover_negative(false);

            for (i = [0:3])
                translate([dc_channel_x(i), dc_channel_y(i), 0])
                    barrel_channel_negative();

            translate([usb_c_panel_x, usb_c_panel_y, 0])
                usb_c_panel_negative();

            translate([c13_panel_x, service_row_y, 0])
                c13_inlet_negative();

            panel_corner_screw_holes();

            if (include_revision)
                translate([revision_x, revision_y, 0])
                    label_pocket(top_panel_revision_label_w, revision_label_h);
        }

        translate([left_ac_x, ac_row_y, 0])
            positive_plate_writings(ac_devices[0], ac_details[0], ac_devices[1], ac_details[1]);
        translate([right_ac_x, ac_row_y, 0])
            positive_plate_writings(ac_devices[2], ac_details[2], ac_devices[3], ac_details[3]);

        for (i = [0:3])
            translate([dc_channel_x(i) + barrel_label_x, dc_channel_y(i) - barrel_channel_h / 2 + 10, 0])
                flush_two_line_label(dc_devices[i], dc_details[i], 4.3, 3.1, 5);

        for (i = [0:3])
            translate([dc_channel_x(i) + dc_toggle_x() + toggle_label_x_offset, dc_channel_y(i), 0])
                toggle_state_labels();

        translate([usb_c_panel_x, usb_c_panel_y - usb_c_panel_h / 2 + 8, 0])
            flush_label("COM", 4);

        if (include_revision)
            translate([revision_x, revision_y, 0])
                flush_revision_label();
    }
}

module sub_panel_8ch() {
    translate([layout_offset_x, layout_offset_y, 0]) {
        difference() {
            union() {
                translate([-layout_offset_x, -layout_offset_y, 0])
                    sub_panel_8ch_positive();
                sub_panel_socket_screw_bosses();
            }

            sub_panel_8ch_negative();
        }
    }
}



module box_context() {
    color([0.7, 0.72, 0.68, 0.35])
        difference() {
            union() {
                difference() {
                    translate([0, 0, -box_h])
                        cube([box_w, box_d, box_h]);
                    translate([wall_t, wall_t, -box_h + wall_t])
                        cube([box_w - 2 * wall_t, box_d - 2 * wall_t, box_h + 2]);
                    side_wall_psu_vents();
                    relay_bottom_mount_holes();
                    if (feature_power_screw_mounts) {
                        psu_bottom_mount_holes();
                        converter_bottom_mount_holes();
                    }
                    box_bottom_revision_negative();
                }
                if (feature_ledge) top_panel_ledge();
                if (feature_power_screw_mounts) {
                    psu_retaining_corners_in_box();
                    relay_retaining_corners_in_box();
                    converter_retaining_corners_in_box();
                }
                if (feature_psu_tie_wrap_anchors)
                    psu_floor_tie_wrap_anchors_in_box();
                if (feature_psu_tie_wrap_anchors)
                    psu_floor_stops_in_box();
                if (feature_psu_tie_wrap_anchors_wall)
                    psu_right_wall_tie_wrap_anchors_in_box();
            }
            panel_corner_screw_holes_in_box();
            panel_corner_nut_traps_in_box();
        }
}

module top_panel_ledge() {
    // Four self-supporting lips: flat on top, flat against the wall.
    // bottom
    translate([wall_t, wall_t, ledge_top_z])
        rotate([0, 90, 0])
            quarter_round(length = box_w - 2 * wall_t, r = ledge_r);

    // top
    translate([wall_t, box_d - wall_t, ledge_top_z])
        mirror([0, 1, 0])
            rotate([0, 90, 0]) {
                r = ledge_r;
                length = box_w - 2 * wall_t;
                if (!feature_ph_ledge_holes)
                    quarter_round(length, r);
                else {
                    gap0_start = top_ledge_gap_start(0);
                    gap0_end = top_ledge_gap_end(0, length);
                    gap1_start = top_ledge_gap_start(1);
                    gap1_end = top_ledge_gap_end(1, length);

                    top_ledge_segment(0, gap0_start, r);
                    top_ledge_segment(gap0_end, gap1_start, r);
                    top_ledge_segment(gap1_end, length, r);
                }

            }

    translate([wall_t, wall_t, ledge_top_z])
        rotate([-90, 0, 0])
            quarter_round(length = box_d - 2 * wall_t, r = ledge_r);
    translate([box_w - wall_t, wall_t, ledge_top_z])
        mirror([1, 0, 0])
            rotate([-90, 0, 0])
                quarter_round(length = box_d - 2 * wall_t, r = ledge_r);

}

module top_ledge_segment(start, end, r) {
    if (end > start)
        translate([0, 0, start])
            quarter_round(end - start, r);
}

module quarter_round(length, r) {
    linear_extrude(height = length)
        intersection() {
            circle(r = r);
            square([r, r]);
        }
}

module side_wall_psu_vents() {
    vent_zs = [-box_h + vent_wall_margin:vent_hole_spacing:-vent_top_margin];
    right_wall_ys = [vent_wall_margin:vent_hole_spacing:box_d - vent_wall_margin];
    side_wall_xs = [box_w / 2:vent_hole_spacing:box_w - vent_wall_margin];

    for (y = right_wall_ys, z = vent_zs)
        translate([box_w + 1, y, z])
            rotate([0, -90, 0])
                cylinder(h = wall_t + 2, d = vent_hole_d);

    for (x = side_wall_xs, z = vent_zs) {
        translate([x, -1, z])
            rotate([-90, 0, 0])
                cylinder(h = wall_t + 2, d = vent_hole_d);
        translate([x, box_d + 1, z])
            rotate([90, 0, 0])
                cylinder(h = wall_t + 2, d = vent_hole_d);
    }
}

module relay_bottom_mount_holes() {
    translate([
        box_inner_x + top_panel_w / 2 + internal_relay_x,
        box_inner_y + top_panel_h / 2 + internal_relay_y,
        0
    ])
        rotate([0, 0, internal_relay_rot_z])
            for (
                x = [-relay_mount_x / 2, relay_mount_x / 2],
                y = [-relay_mount_y / 2, relay_mount_y / 2]
            ) {
                translate([x, y, -box_h - 1])
                    cylinder(h = wall_t + 2, d = relay_mount_hole_d);
                translate([x, y, -box_h - 0.1])
                    cylinder(h = relay_countersink_h + 0.1, d1 = relay_countersink_d, d2 = relay_mount_hole_d);
            }
}

module bottom_chamfered_mount_hole(d, chamfer_d) {
    translate([0, 0, -box_h - 1])
        cylinder(h = wall_t + 2, d = d);
    translate([0, 0, -box_h - 0.1])
        cylinder(h = wall_t + 0.1, d1 = chamfer_d, d2 = d);
}

module psu_bottom_mount_holes() {
    translate([
        box_inner_x + top_panel_w / 2 + internal_psu_x,
        box_inner_y + top_panel_h / 2 + internal_psu_y,
        0
    ])
        rotate([0, 0, internal_psu_rot_z])
            psu_mount_holes();
}

module psu_mount_holes() {
    translate([psu_w / 2 - psu_mount_x_inset, -psu_d / 2, 0])
        bottom_chamfered_mount_hole(psu_mount_hole_d, psu_mount_chamfer_d);
    translate([-psu_w / 2 + psu_mount_x_inset, psu_d / 2, 0])
        bottom_chamfered_mount_hole(psu_mount_hole_d, psu_mount_chamfer_d);
}

module psu_mount_markers(z) {
    translate([psu_w / 2 - psu_mount_x_inset, -psu_d / 2, z])
        cylinder(h = 2, d = psu_mount_hole_d);
    translate([-psu_w / 2 + psu_mount_x_inset, psu_d / 2, z])
        cylinder(h = 2, d = psu_mount_hole_d);
}

module psu_retaining_corners_in_box() {
    translate([
        box_inner_x + top_panel_w / 2 + internal_psu_x,
        box_inner_y + top_panel_h / 2 + internal_psu_y,
        -box_h + wall_t
    ])
        rotate([0, 0, internal_psu_rot_z])
            psu_retaining_corners();
}

module relay_retaining_corners_in_box() {
    translate([
        box_inner_x + top_panel_w / 2 + internal_relay_x,
        box_inner_y + top_panel_h / 2 + internal_relay_y,
        -box_h + wall_t
    ])
        rotate([0, 0, internal_relay_rot_z])
            retaining_corners(relay_w, relay_d);
}

module converter_retaining_corners_in_box() {
    translate([
        box_inner_x + top_panel_w / 2 + internal_converter_x,
        box_inner_y + top_panel_h / 2 + internal_converter_y,
        -box_h + wall_t
    ])
        rotate([0, 0, internal_converter_rot_z])
            retaining_corners(converter_w, converter_d);
}

module retaining_corners(w, d) {
    for (sx = [-1, 1], sy = [-1, 1])
        retaining_corner(w, d, sx, sy);
}

module psu_retaining_corners() {
    retaining_corner(psu_w, psu_d, -1, 1);
    retaining_corner(psu_w, psu_d, 1, -1);
}

module retaining_corner(w, d, sx, sy) {
    l = retaining_corner_l;
    t = retaining_corner_t;
    h = retaining_corner_h;

    translate([sx * (w / 2 + (t - l) / 2), sy * (d / 2 + t / 2), h / 2])
        cube([l + t, t, h], center = true);
    translate([sx * (w / 2 + t / 2), sy * (d / 2 + (t - l) / 2), h / 2])
        cube([t, l + t, h], center = true);
}

module converter_bottom_mount_holes() {
    translate([
        box_inner_x + top_panel_w / 2 + internal_converter_x,
        box_inner_y + top_panel_h / 2 + internal_converter_y,
        0
    ])
        rotate([0, 0, internal_converter_rot_z])
            for (y = [-converter_mount_spacing / 2, converter_mount_spacing / 2])
                translate([0, y, 0])
                    bottom_chamfered_mount_hole(converter_mount_hole_d, converter_mount_chamfer_d);
}

module box_bottom_revision_negative() {
    translate([box_w / 2, box_d / 2, -box_h])
        mirror([1, 0, 0])
            write_text(revision_string, box_revision_font, -0.01);
}

module psu_floor_tie_wrap_anchors_in_box() {
    translate([
        box_inner_x + top_panel_w / 2 + internal_psu_x,
        box_inner_y + top_panel_h / 2 + internal_psu_y,
        -box_h + wall_t
    ])
        rotate([0, 0, internal_psu_rot_z])
            psu_floor_tie_wrap_anchors();
}

module psu_floor_tie_wrap_anchors() {
    // Floor anchors route straps in both directions across the PSU footprint.
    for (y = [psu_d / 2 + psu_anchor_r + psu_anchor_gap])
        for (x = [-psu_w / 2 + psu_anchor_inset, psu_w / 2 - psu_anchor_inset])
            translate([x, y, 0])
                tie_wrap_anchor_x();

    for (x = [-psu_w / 2 - psu_anchor_r - psu_anchor_gap])
        for (y = [-psu_d / 2 + psu_anchor_inset, psu_d / 2 - psu_anchor_inset])
            translate([x, y, 0])
                tie_wrap_anchor_y();

}

module psu_floor_stops_in_box() {
    translate([
        box_inner_x + top_panel_w / 2 + internal_psu_x,
        box_inner_y + top_panel_h / 2 + internal_psu_y,
        -box_h + wall_t
    ])
        rotate([0, 0, internal_psu_rot_z])
            psu_floor_stops();
}

module psu_floor_stops() {
    for (y = [psu_d / 2])
        translate([-psu_stop_between_x_anchors_l / 2, y, 0])
            cube([psu_stop_between_x_anchors_l, psu_stop_t, psu_stop_h]);

    translate([-psu_w / 2 - psu_stop_t, -psu_stop_between_y_anchors_l / 2, 0])
        cube([psu_stop_t, psu_stop_between_y_anchors_l, psu_stop_h]);

    for (x = [psu_w / 2])
        translate([x, -psu_stop_l / 2, 0])
            cube([psu_stop_t, psu_stop_l, psu_stop_h]);
}

module psu_right_wall_tie_wrap_anchors_in_box() {
    psu_center_y = box_inner_y + top_panel_h / 2 + internal_psu_y;

    // Wall anchors are modeled in box coordinates so "right wall" stays literal.
    for (y = [psu_center_y - psu_w / 2 + psu_anchor_inset, psu_center_y + psu_w / 2 - psu_anchor_inset])
        translate([box_w - wall_t, y, -box_h + wall_t + psu_wall_anchor_z])
            rotate([0, -90, 0])
                tie_wrap_anchor_y();
}

module tie_wrap_anchor_x() {
    difference() {
        rotate([0, 90, 0])
            half_round(length = psu_anchor_l, r = psu_anchor_r);
        // The tie passes across the anchor, under the curved roof.
        translate([-psu_anchor_slot_w / 2, -psu_anchor_r - 1, psu_anchor_slot_z])
            cube([psu_anchor_slot_w, 2 * psu_anchor_r + 2, psu_anchor_slot_h]);
    }
}

module tie_wrap_anchor_y() {
    rotate([0, 0, 90])
        tie_wrap_anchor_x();
}

module half_round(length, r) {
    translate([0, 0, -length / 2])
        linear_extrude(height = length)
            intersection() {
                circle(r = r);
                translate([-r, -r])
                    square([r, 2 * r]);
            }
}

module top_panel_outline() {
    color([0.85, 0.72, 0.15, 0.8])
        linear_extrude(height = top_outline_h)
            difference() {
                square([top_panel_w, top_panel_h]);
                translate([top_outline_w, top_outline_w])
                    square([
                        top_panel_w - 2 * top_outline_w,
                        top_panel_h - 2 * top_outline_w
                    ]);
            }
}

module panel_corner_screw_holes() {
    for (
        x = [panel_screw_inset, top_panel_w - panel_screw_inset],
        y = [panel_screw_inset, top_panel_h - panel_screw_inset]
    )
        translate([x - layout_offset_x, y - layout_offset_y, 0])
            screw_hole(screw_d);
}

module panel_corner_screw_holes_in_box() {
    for (
        x = [box_inner_x + panel_screw_inset, box_inner_x + top_panel_w - panel_screw_inset],
        y = [box_inner_y + panel_screw_inset, box_inner_y + top_panel_h - panel_screw_inset]
    )
        translate([x, y, ledge_top_z - ledge_r - 1])
            cylinder(h = ledge_r + plate_t + 2, d = screw_d);
}

module panel_corner_nut_traps_in_box() {
    for (
        x = [box_inner_x + panel_screw_inset, box_inner_x + top_panel_w - panel_screw_inset],
        y = [box_inner_y + panel_screw_inset, box_inner_y + top_panel_h - panel_screw_inset]
    )
        translate([x, y, ledge_top_z - ledge_r - 0.1])
            cylinder(h = panel_nut_h + 0.1, d = panel_nut_d, $fn = 6);
}

// ---------------- views ----------------

module ac_duplex_channel() {
    outlet_cover(true, ac_devices[0], ac_details[0], ac_devices[1], ac_details[1]);
}

module dc_barrel_channel() {
    dc_barrel_channel_unit(dc_devices[0], dc_details[0], true);
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

module sub_panel() {
    sub_panel_8ch();
}

module mounted_sub_panel() {
    translate([0, 0, ledge_top_z])
        sub_panel_8ch();
}

module mounted_top_panel() {
    translate([0, 0, -plate_t])
        top_panel_8ch(true);
}

module internal_components(show_psu = true, show_relay = true) {
    translate([box_inner_x + top_panel_w / 2, box_inner_y + top_panel_h / 2, 0]) {
        if (show_psu)
            translate([internal_psu_x, internal_psu_y, -box_h + wall_t])
                rotate([0, 0, internal_psu_rot_z])
                    psu_keepout();
        if (show_psu)
            translate([internal_converter_x, internal_converter_y, -box_h + wall_t])
                rotate([0, 0, internal_converter_rot_z])
                    converter_keepout();
        if (show_relay)
            translate([internal_relay_x, internal_relay_y, -box_h + wall_t])
                rotate([0, 0, internal_relay_rot_z])
                    relay_board_keepout();
    }
}

module plate() {
    translate([-176, 56, 0])
        outlet_cover(true, ac_devices[0], ac_details[0], ac_devices[1], ac_details[1]);
    translate([-62, 66, 0])
        dc_barrel_channel_unit(dc_devices[0], dc_details[0], true);
    translate([6, 66, 0])
        usb_c_panel_unit(true);
    translate([78, 56, 0])
        c13_inlet_unit(true);

    translate([0, -140, 0])
        top_panel_8ch(true);
}

module assembly() {
    if (show_box)
        box_context();

    if (show_top_outline)
        translate([box_inner_x, box_inner_y, 0])
            top_panel_outline();

    if (show_sub_panel)
        translate([box_inner_x, box_inner_y, 0])
            mounted_sub_panel();

    if (show_top_panel)
        translate([box_inner_x, box_inner_y, 0])
            mounted_top_panel();

    internal_components(show_psu, show_relay);
}

module box() {
    box_context();
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
} else if (view == "sub_panel") {
    sub_panel();
} else if (view == "assembly") {
    assembly();
} else if (view == "box") {
    box();
} else {
    assembly();
}
