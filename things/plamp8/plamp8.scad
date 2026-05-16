render_fn = 96;
render_text = true;
$fn = render_fn;

view = "internal"; // [internal, assembly, plate, ac_duplex_channel, dc_barrel_channel, usb_c_panel, c13_inlet, top_panel]

show_internal_box = true;
show_internal_psu = false;
show_internal_relay = false;
show_internal_top_outline = false;

// ---------------- dimensions ----------------
outlet_plate_left = 46;
outlet_plate_right = 76;
plate_w = outlet_plate_left + outlet_plate_right;
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
outlet_group_h = 54;

screw_d = 4;
panel_nut_d = 7.4;
panel_nut_h = 3.4;
screw_spacing = 84;

// Modular box-builder dimensions. Keep these near the top for fit tuning.
toggle_hole_d = 12;

barrel_jack_hole_d = 12;
barrel_channel_w = 70;
barrel_channel_h = 58;
barrel_label_w = 34;
barrel_label_h = 10;
barrel_label_x = 7;
barrel_group_y = -8;
barrel_group_x = 5;
barrel_group_w = 66;
barrel_group_h = 42;
barrel_jack_x = -13;
barrel_toggle_x = 8;

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

inch = 25.4;
c13_panel_w = 72;
c13_panel_h = 68;
c13_label_w = 48;
c13_label_h = 10;
c13_group_w = 66;
c13_group_h = 64;
c13_face_w = 1.9 * inch;
c13_face_h = 2.0 * inch;
c13_cutout_w = 28;
c13_cutout_h = 48;
c13_wire_cutout_w = c13_cutout_w;
c13_wire_cutout_h = c13_cutout_h;
c13_screw_d = 3.5;
c13_screw_inset = 1.5;
c13_screw_spacing = c13_face_w - 2 * c13_screw_inset;

psu_w = 160;
psu_d = 98;
psu_h = 38;
psu_anchor_r = 5;
psu_anchor_l = 14;
psu_anchor_slot_w = 5;
psu_anchor_slot_h = 2.5;
psu_anchor_slot_z = 1;
psu_anchor_gap = 4;
psu_anchor_inset = 20;

relay_w = 145;
relay_d = 90;
relay_h = 40;
relay_mount_hole_d = 5;
relay_mount_x = 135;
relay_mount_y = 70;
relay_countersink_d = 9;

wall_t = 3;
relay_countersink_h = wall_t;
internal_clearance_h = 50;
box_h = internal_clearance_h + wall_t;
panel_margin = 5;
top_outline_w = 2;
top_outline_h = 1;
ledge_w = 20;
ledge_r = ledge_w;
ledge_top_z = -plate_t;
panel_screw_inset = wall_t + ledge_r / 2;
internal_psu_x = 55;
internal_psu_y = 10;
internal_psu_rot_z = 90;
internal_relay_x = -50;
internal_relay_y = 0;
internal_relay_rot_z = 90;
vent_hole_d = 5;
vent_hole_spacing = 10;
wall_vent_cols = 14;
wall_vent_rows = 3;
service_row_y = 58;
ac_row_y = -62;
dc_row_y = -106;
left_ac_x = -66;
right_ac_x = 40;
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
revision_y = nutrients_recess_bottom_y + 9 / 2;
toggle_label_x_offset = 15;
toggle_label_step = 7;
toggle_label_font = 3.2;

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

alignment_wall_h = 8;
alignment_wall_t = 2;
label_pocket_h = 3;
label_pocket_r = 3;
revision_label_w = 26;
revision_label_h = 9;

letter_size = 6;
write_t = 0.75;
revision_string = "dev";

ac_devices = ["Pump", "Lights", "Fan", "Aux"];
ac_details = ["CH1 GP21", "CH2 GP20", "CH3 GP19", "CH4 GP18"];
dc_labels = ["PH Up CH5 GP17", "PH Down CH6 GP16", "Agitator CH7 GP15", "Nutrients CH8 GP14"];


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
    translate([barrel_jack_x, 0, 0])
        screw_hole(barrel_jack_hole_d);
    translate([barrel_toggle_x, 0, 0])
        screw_hole(toggle_hole_d);

    translate([barrel_group_x, barrel_group_y, 0])
        label_pocket(barrel_group_w, barrel_group_h);
}

module barrel_revision_negative() {
    translate([0, barrel_channel_h / 2 - 9, 0])
        label_pocket(revision_label_w, revision_label_h);
}

module dc_barrel_channel_unit(label = "PH Up CH5 GP17", include_revision = true) {
    difference() {
        union() {
            fit_plate(barrel_channel_w, barrel_channel_h);
            alignment_walls(barrel_channel_w - 8, barrel_channel_h - 8);
        }
        barrel_channel_negative();
        if (include_revision)
            barrel_revision_negative();
    }

    translate([barrel_label_x, -barrel_channel_h / 2 + 10, 0])
        flush_label(label, 4.3);
    translate([barrel_toggle_x + toggle_label_x_offset, 0, 0])
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
                    label_pocket(revision_label_w, revision_label_h);
        }

        translate([left_ac_x, ac_row_y, 0])
            positive_plate_writings(ac_devices[0], ac_details[0], ac_devices[1], ac_details[1]);
        translate([right_ac_x, ac_row_y, 0])
            positive_plate_writings(ac_devices[2], ac_details[2], ac_devices[3], ac_details[3]);

        for (i = [0:3])
            translate([dc_channel_x(i) + barrel_label_x, dc_channel_y(i) - barrel_channel_h / 2 + 10, 0])
                flush_label(dc_labels[i], 4.3);

        for (i = [0:3])
            translate([dc_channel_x(i) + barrel_toggle_x + toggle_label_x_offset, dc_channel_y(i), 0])
                toggle_state_labels();

        translate([usb_c_panel_x, usb_c_panel_y - usb_c_panel_h / 2 + 8, 0])
            flush_label("COM", 4);

        if (include_revision)
            translate([revision_x, revision_y, 0])
                flush_revision_label();
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
                }
                top_panel_ledge();
                psu_floor_tie_wrap_anchors_in_box();
                psu_right_wall_tie_wrap_anchors_in_box();
            }
            panel_corner_screw_holes_in_box();
            panel_corner_nut_traps_in_box();
        }
}

module top_panel_ledge() {
    // Four self-supporting lips: flat on top, flat against the wall.
    translate([wall_t, wall_t, ledge_top_z])
        rotate([0, 90, 0])
            quarter_round(length = box_w - 2 * wall_t, r = ledge_r);
    translate([wall_t, box_d - wall_t, ledge_top_z])
        mirror([0, 1, 0])
            rotate([0, 90, 0])
                quarter_round(length = box_w - 2 * wall_t, r = ledge_r);
    translate([wall_t, wall_t, ledge_top_z])
        rotate([-90, 0, 0])
            quarter_round(length = box_d - 2 * wall_t, r = ledge_r);
    translate([box_w - wall_t, wall_t, ledge_top_z])
        mirror([1, 0, 0])
            rotate([-90, 0, 0])
                quarter_round(length = box_d - 2 * wall_t, r = ledge_r);

}

module quarter_round(length, r) {
    linear_extrude(height = length)
        intersection() {
            circle(r = r);
            square([r, r]);
        }
}

module side_wall_psu_vents() {
    vent_y = box_inner_y + top_panel_h / 2 + internal_psu_y;
    vent_z = -box_h / 2;

    for (
        y = [-(wall_vent_cols - 1) / 2:(wall_vent_cols - 1) / 2],
        z = [-(wall_vent_rows - 1) / 2:(wall_vent_rows - 1) / 2]
    )
        translate([
            box_w + 1,
            vent_y + y * vent_hole_spacing,
            vent_z + z * vent_hole_spacing
        ])
            rotate([0, 90, 0])
                cylinder(h = wall_t + 2, d = vent_hole_d);
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
    for (y = [-psu_d / 2 - psu_anchor_gap, psu_d / 2 + psu_anchor_gap])
        for (x = [-psu_w / 2 + psu_anchor_inset, psu_w / 2 - psu_anchor_inset])
            translate([x, y, 0])
                tie_wrap_anchor_x();

    for (x = [-psu_w / 2 - psu_anchor_gap, psu_w / 2 + psu_anchor_gap])
        for (y = [-psu_d / 2 + psu_anchor_inset, psu_d / 2 - psu_anchor_inset])
            translate([x, y, 0])
                tie_wrap_anchor_y();

}

module psu_right_wall_tie_wrap_anchors_in_box() {
    psu_center_y = box_inner_y + top_panel_h / 2 + internal_psu_y;

    // Wall anchors are modeled in box coordinates so "right wall" stays literal.
    for (y = [psu_center_y - psu_w / 2 + psu_anchor_inset, psu_center_y + psu_w / 2 - psu_anchor_inset])
        translate([box_w - wall_t, y, -box_h + wall_t])
            rotate([0, -90, 0])
                tie_wrap_anchor_x();
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
    dc_barrel_channel_unit(dc_labels[0], true);
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
        dc_barrel_channel_unit(dc_labels[0], true);
    translate([6, 66, 0])
        usb_c_panel_unit(true);
    translate([78, 56, 0])
        c13_inlet_unit(true);

    translate([0, -140, 0])
        top_panel_8ch(true);
}

module assembly() {
    box_context();
    translate([box_inner_x, box_inner_y, 0])
        mounted_top_panel();
    internal_components();
}

module internal() {
    if (show_internal_box)
        box_context();

    if (show_internal_top_outline)
        translate([box_inner_x, box_inner_y, 0])
            top_panel_outline();

    internal_components(show_internal_psu, show_internal_relay);
}

if (view == "internal") {
    internal();
} else if (view == "plate") {
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
