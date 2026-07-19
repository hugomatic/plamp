render_fn = 96;
render_text = true;
$fn = render_fn;

view = "assembly"; // [relay_footprint, psu_footprint, converter_footprint, floor, north_wall, south_wall, west_wall, east_wall, ledge_ring, top_panel, sub_panel, plate, ac_duplex_channel, dc_barrel_channel, usb_c_panel, c13_inlet, panel_corner_fastener_test, corner_coupon, wall_corner_fastener_assembly, assembly]

dc_connector_type = "xt60"; // [barrel, xt60]

/* [assembly view options] */

// show / hide enclosure parts
show_north_wall = true;
show_south_wall = true;
show_west_wall = true;
show_east_wall = true;
show_ledge_ring = true;
show_floor = true;
show_psu = true;
show_relay = true;
show_top_outline = false;
show_sub_panel = true;
show_top_panel = true;


/* [box features] */

//box features: floor anchors (tie wraps)
feature_psu_tie_wrap_anchors = false;
//box features: power module bottom screw mounts
feature_power_screw_mounts = true;
feature_ph_ledge_holes = true;


/* [dimensions] */

wall_z_height = 83;
outlet_plate_left = 46;
outlet_plate_right = 76;
plate_h = 120;
plate_t = 3;

hole_d = 34;        // source cylinder diameter
hole_h = 24;        // final vertical height after trimming
hole_depth = 10;    // taller than plate_t for clean boolean
cut_off_y = 2.5;
outlet_spacing = 39.65;
outlet_feature_x = -4;
outlet_toggle_x = 32;
outlet_group_x = 8;
outlet_group_w = 104;
outlet_group_h = 56;

screw_d = 4;
screw_spacing = 84;

// Modular box-builder dimensions. Keep these near the top for fit tuning.
toggle_hole_d = 12;

psu_screw_size = "M5";       // [M3, M4, M5]
converter_screw_size = "M5"; // [M3, M4, M5]
relay_screw_size = "M5";     // [M3, M4, M5]
floor_screw_size = "M3";     // [M3, M4, M5]
corner_screw_size = "M3";
panel_screw_size = "M3";
panel_screw_length = 20;
panel_screw_tip_protrusion = 1;
corner_screw_length = 30;

function screw_clearance_d(size) =
    size == "M5" ? 5.5 :
    size == "M4" ? 4.5 :
    3.4;

function screw_chamfer_d(size) =
    size == "M5" ? 10 :
    size == "M4" ? 8 :
    6.5;

function screw_nut_trap_d(size) =
    size == "M5" ? 9.4 :
    size == "M4" ? 8 :
    6.5;

function screw_nut_trap_h(size) =
    size == "M5" ? 4.4 :
    size == "M4" ? 3.4 :
    2.8;

panel_screw_d = screw_clearance_d(panel_screw_size);
panel_screw_countersink_d = screw_chamfer_d(panel_screw_size);
panel_screw_countersink_h = (panel_screw_countersink_d - panel_screw_d) / 2;
panel_screw_land_d = 9.5;
panel_nut_d = screw_nut_trap_d(panel_screw_size);
panel_nut_h = screw_nut_trap_h(panel_screw_size);
panel_nut_clearance = 0.3;
panel_nut_entry_l = 12;
panel_nut_entry_detent = 0.35;
panel_nut_entry_detent_l = 1.5;
panel_fastener_boss_d = 11;
corner_screw_d = screw_clearance_d(corner_screw_size);
corner_screw_head_d = screw_chamfer_d(corner_screw_size);
corner_nut_d = screw_nut_trap_d(corner_screw_size);
corner_nut_h = screw_nut_trap_h(corner_screw_size);
corner_nut_clearance = 0.3;


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
xt60_outside_w = 34.25;
dc_switch_outside_d = 21;
xt60_switch_clearance = 2;
xt60_switch_center_spacing = xt60_outside_w / 2 + dc_switch_outside_d / 2 + xt60_switch_clearance;
xt60_cutout_w = 19;
xt60_cutout_h = 12;
xt60_face_w = 35;
xt60_face_h = 16;
xt60_screw_spacing = 25;
xt60_screw_d = 3.2;
xt60_nut_clearance_d = 7;

usb_c_panel_w = 44;
usb_c_panel_h = 34;
usb_c_label_w = 32;
usb_c_label_h = 9;
usb_c_group_y = -4;
usb_c_group_w = 36;
usb_c_group_h = 28;
usb_c_cutout_w = 12;
usb_c_cutout_h = 10;
usb_c_cutout_r = 1.5;
usb_c_wire_cutout_w = 10;
usb_c_wire_cutout_h = 16;
usb_c_screw_d = 3.4;
usb_c_screw_head_d = 5.61;
usb_c_screw_spacing = 17;
usb_c_screw_surface_z = plate_t - 0.5;

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
c13_screw_spacing = 40;

// Calibrated from footprint test print: printed PSU diagonal was 138.00 mm
// against the original 134 x 36 mm footprint diagonal.
psu_w = 134.73;
psu_d = 36.2;
psu_h = 23;
psu_mount_hole_d = screw_clearance_d(psu_screw_size);
psu_mount_x_inset = 8.25;
psu_mount_y_inset = 2.5;
psu_mount_chamfer_d = screw_chamfer_d(psu_screw_size);
psu_view_w = psu_d;
psu_view_d = psu_w;
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

// Calibrated from footprint test print: printed 26.74 x 45.78 mm.
converter_w = 27.26;
converter_d = 46.22;
converter_h = 14;
converter_fit_clearance = 0.5;
converter_retaining_w = converter_w + 2 * converter_fit_clearance;
converter_retaining_d = converter_d + 2 * converter_fit_clearance;
converter_mount_spacing = 50;
converter_mount_hole_d = screw_clearance_d(converter_screw_size);
converter_mount_chamfer_d = screw_chamfer_d(converter_screw_size);

// Calibrated from footprint test print: +0.66 mm long side, +0.43 mm short side.
relay_w = 145.66;
relay_d = 90.43;
relay_h = 40;
relay_mount_hole_d = screw_clearance_d(relay_screw_size);
relay_mount_x = 135;
relay_mount_y = 70;
relay_countersink_d = screw_chamfer_d(relay_screw_size);

retaining_corner_l = 5;
retaining_corner_t = 4;
retaining_corner_h = 10;
psu_side_guide_l = 10;
psu_side_guide_t = retaining_corner_t;
psu_side_guide_h = retaining_corner_h;

wall_t = 3;
panel_screw_inset = 4;
corner_axis_inset = wall_t + panel_screw_inset;
corner_fit_clearance = 0.25;
corner_tab_t = 6;
corner_tab_w = 12;
corner_tab_h = 11;
corner_tab_outer_x = wall_t + corner_fit_clearance - corner_axis_inset;
corner_tab_inner_x = corner_tab_w / 2;
corner_tab_effective_w = corner_tab_inner_x - corner_tab_outer_x;
bore_tangent_a = corner_screw_d / 2 / sqrt(2);
corner_nut_slot_l = corner_nut_h + corner_nut_clearance;
corner_nut_shoulder_t = corner_tab_t - corner_nut_slot_l;
corner_nut_retainer_t = 0.8;
corner_nut_tab_extension = 16;
corner_nut_detent_angle = 30;
corner_nut_detent_ramp_h = panel_nut_entry_detent * tan(corner_nut_detent_angle);
corner_coupon_wall_l = 36;
corner_coupon_wall_h = 32;
coupon_assembly_clearance = 0.05;
coupon_plate_column_x = 100;
wall_rib_w = 3;
wall_rib_h = 2;
wall_vent_joint_clearance = 1;
floor_locator_l = 16;
floor_locator_depth = 2;
floor_locator_h = 2;
floor_locator_end_offset = 20;
floor_locator_clearance = 0.25;
ledge_ring_t = 3;
ledge_ring_north_rail_w = 3;
ledge_ring_north_clearance_min = 0.75;
relay_countersink_h = wall_t;
component_raise_h = 5;
component_airflow_post_d = 5;
component_airflow_post_spacing = 14;
component_airflow_post_hole_clearance = 8;
floor_fastener_hole_d = screw_clearance_d(floor_screw_size);
floor_fastener_chamfer_d = screw_chamfer_d(floor_screw_size);
box_h = wall_z_height;
panel_margin = 5;
top_outline_w = 2;
top_outline_h = 1;
ledge_w = 10;
ledge_r = ledge_w;
internal_psu_y = 20;
internal_psu_rot_z = 90;
internal_converter_x = 65;
internal_converter_y = -85;
internal_converter_rot_z = 90;
internal_relay_x = -35;
internal_relay_y = 5;
internal_relay_rot_z = 90;
vent_hole_d = 5;
vent_hole_spacing = 10;
vent_wall_margin = 10;
vent_top_margin = ledge_r + vent_hole_d;
vent_floor_clearance = vent_wall_margin + vent_hole_spacing;
vent_ledge_clearance = vent_hole_spacing;
service_row_y = 58;
ac_row_y = -63;
dc_row_y = -106;
left_ac_x = -66;
right_ac_x = 40;

plate_w = outlet_plate_left + outlet_plate_right;

psu_stop_between_x_anchors_l = psu_w - 2 * psu_anchor_inset - psu_anchor_l - 2 * psu_stop_anchor_clearance;
psu_stop_between_y_anchors_l = psu_d - 2 * psu_anchor_inset - psu_anchor_l - 2 * psu_stop_anchor_clearance;

c13_face_w = c13_face_w_inch * inch;
c13_face_h = c13_face_h_inch * inch;

toggle_label_x_offset = 15;
toggle_label_step = 8.5;
toggle_label_font = 4.2;
sub_panel_switch_w = 20;
sub_panel_switch_h = 32.5;
sub_panel_socket_w = 35;
sub_panel_socket_h = 70;
sub_panel_socket_screw_spacing = 82;
sub_panel_usb_c_cutout_w = 13;
sub_panel_usb_c_cutout_h = 10.5;
sub_panel_wall = 10;
sub_panel_socket_rim_relief_w = sub_panel_socket_w;
sub_panel_socket_rim_relief_d = sub_panel_wall / 2;
sub_panel_base_h = 5;
sub_panel_h = 10;
sub_panel_revision_depth = 0.6;
ph_ledge_gap_clearance = 0.5;
ph_ledge_gap_w = sub_panel_switch_w + 2 * ph_ledge_gap_clearance;

top_stack_h = plate_t + sub_panel_h + ledge_ring_t + 2 * corner_tab_t + corner_nut_retainer_t;
bottom_stack_h = wall_t + 2 * corner_tab_t + corner_nut_retainer_t;
corner_screw_tip_allowance = 1;
bottom_corner_nut_offset = corner_screw_length
    - corner_screw_tip_allowance
    - (bottom_stack_h - corner_nut_retainer_t);
assert(corner_screw_length - top_stack_h >= 0, "top corner screw is shorter than its stack");
assert(bottom_corner_nut_offset >= 0, "bottom corner nut offset must not be negative");
assert(bottom_corner_nut_offset + corner_screw_tip_allowance <= corner_nut_tab_extension,
    "bottom corner nut must remain inside the extended beam");
assert(wall_z_height >= 2 * corner_tab_h + 10,
    "wall_z_height is too short for separated top and bottom joint zones");
assert(corner_nut_shoulder_t >= 0.8, "corner nut needs at least 0.8 mm axial bearing shoulder");
assert(2 * bore_tangent_a > corner_screw_d / 2, "teardrop roof must clear the round screw envelope");
echo(str("top M3 protrusion: ", corner_screw_length - top_stack_h, " mm"));
echo(str("bottom M3 nut offset: ", bottom_corner_nut_offset, " mm"));


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
panel_nut_trap_z = -panel_screw_length + panel_screw_tip_protrusion;
panel_fastener_boss_bottom_z = panel_nut_trap_z - 0.5;
panel_fastener_boss_h = ledge_top_z - panel_fastener_boss_bottom_z;

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
internal_psu_x = 60;

alignment_wall_h = 8;
alignment_wall_t = 2;
label_pocket_h = 3;
label_pocket_r = 3;
revision_label_w = 26;
revision_label_h = 9;
top_panel_brand_text = "plamp";
top_panel_brand_font = 4;
top_panel_brand_y_offset = 19;
box_revision_font = 6;
letter_size = 6;
write_t = 0.75;
revision_string = "dev";

dc_devices = ["PH Up", "PH Down", "Agitator", "Nutrients"];
dc_details = ["CH1 GP21 12V DC", "CH2 GP20 12V DC", "CH3 GP19 12V DC", "CH4 GP18 12V DC"];

ac_devices = ["Pump", "Lights", "Fan", "Aux"];
ac_details = ["CH5 GP17 110V AC", "CH7 GP15 110V AC", "CH6 GP16 110V AC", "CH8 GP14 110V AC"];




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
    bfont = 8;
    sfont = 5;
    x1 = outlet_feature_x;
    y1 = 50;

    x2 = x1;
    y2 = -y1 + 8;

    y_line = -bfont - 2;

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

module sub_panel_socket_bottom_rim_relief_negative() {
    bottom_rim_inner_y = -layout_offset_y + sub_panel_wall - sub_panel_socket_rim_relief_d;
    lip_h = sub_panel_h - sub_panel_base_h;

    for (x = [left_ac_x, right_ac_x])
        translate([
            x + outlet_feature_x - sub_panel_socket_rim_relief_w / 2,
            bottom_rim_inner_y,
            sub_panel_base_h - 0.1
        ])
            cube([
                sub_panel_socket_rim_relief_w,
                sub_panel_socket_rim_relief_d + 0.1,
                lip_h + 0.2
            ]);
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

module sub_panel_left_xt60_nut_clearances_negative() {
    for (i = [0, 2])
        translate([
            dc_channel_x(i) + dc_connector_x() - xt60_screw_spacing / 2,
            dc_channel_y(i),
            sub_panel_base_h
        ])
            cylinder(
                h = sub_panel_h - sub_panel_base_h + 0.1,
                d = xt60_nut_clearance_d
            );
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
    sub_panel_socket_bottom_rim_relief_negative();

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

    sub_panel_left_xt60_nut_clearances_negative();

    translate([usb_c_panel_x, usb_c_panel_y, 0])
        sub_panel_usb_c_negative();

    translate([c13_panel_x, service_row_y, 0])
        sub_panel_c13_negative();

    panel_corner_screw_holes();

    translate([revision_x, revision_y, sub_panel_base_h])
        write_text(revision_string, 4, -sub_panel_revision_depth);
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

module topside_countersunk_screw_hole(hole_d, head_d, surface_z = plate_t, depth = 30) {
    countersink_h = (head_d - hole_d) / 2;
    screw_hole(hole_d, depth);
    translate([0, 0, surface_z - countersink_h])
        cylinder(h = countersink_h + 0.1, d1 = hole_d, d2 = head_d);
}

module rect_cutout(w, h, depth = 30) {
    translate([0, 0, plate_t / 2])
        cube([w, h, depth], center = true);
}

module rounded_rect_cutout(w, h, r, depth = 30) {
    translate([0, 0, plate_t / 2])
        hull()
            for (
                x = [-w / 2 + r, w / 2 - r],
                y = [-h / 2 + r, h / 2 - r]
            )
                translate([x, y, 0])
                    cylinder(h = depth, r = r, center = true);
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

module echo_hardware(include_psu = false, include_converter = false, include_relay = false, include_floor = false) {
    if (include_psu)
        echo(str("hardware: PSU mount: 2x ", psu_screw_size, " clearance/chamfer"));
    if (include_converter)
        echo(str("hardware: converter mount: 2x ", converter_screw_size, " clearance/chamfer"));
    if (include_relay)
        echo(str("hardware: relay mount: 4x ", relay_screw_size, " clearance/chamfer"));
    if (include_floor)
        echo(str("hardware: floor-to-wall: 4x ", floor_screw_size, " bottom-up, chamfered floor, wall nut traps"));
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
        flush_two_line_label(device, detail, 5.3, 4.1, 6);
    translate([dc_toggle_x() + toggle_label_x_offset, 0, 0])
        toggle_state_labels();

    if (include_revision)
        translate([0, barrel_channel_h / 2 - 9, 0])
            flush_revision_label();
}

module usb_c_panel_negative() {
    rounded_rect_cutout(usb_c_cutout_w, usb_c_cutout_h, usb_c_cutout_r);

    for (x = [-usb_c_screw_spacing / 2, usb_c_screw_spacing / 2])
        translate([x, 0, 0])
            topside_countersunk_screw_hole(usb_c_screw_d, usb_c_screw_head_d, usb_c_screw_surface_z);

    translate([0, usb_c_group_y, 0])
        label_pocket(usb_c_group_w, usb_c_group_h);
}

module usb_c_revision_negative() {
    translate([0, usb_c_panel_h / 2 - 8, 0])
        label_pocket(revision_label_w, revision_label_h);
}

module usb_c_panel_unit(include_revision = true) {
    difference() {
        // Flat coupon: the connector mounts directly under the 3 mm panel.
        fit_plate(usb_c_panel_w, usb_c_panel_h);
        usb_c_panel_negative();
        if (include_revision)
            usb_c_revision_negative();
    }

    translate([0, -usb_c_panel_h / 2 + 4, 0])
        flush_label("COM", 5);

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
function dc_toggle_x() = barrel_toggle_x + dc_toggle_x_extra;
function dc_connector_x() = dc_connector_type == "xt60"
    ? dc_toggle_x() - xt60_switch_center_spacing
    : barrel_jack_x;

assert(
    dc_connector_type != "xt60"
        || abs((dc_toggle_x() - dc_connector_x()) - xt60_switch_center_spacing) < 0.001,
    "XT60-to-switch clearance does not match the measured hardware envelopes"
);

function top_ledge_gap_center_for_dc_toggle(i) = layout_offset_x + dc_channel_x(i) + dc_toggle_x();
function top_ledge_gap_start(i) = max(0, top_ledge_gap_center_for_dc_toggle(i) - ph_ledge_gap_w / 2);
function top_ledge_gap_end(i, length) = min(length, top_ledge_gap_center_for_dc_toggle(i) + ph_ledge_gap_w / 2);
ledge_ring_north_clearance =
    box_inner_d - ledge_ring_north_rail_w
    - (layout_offset_y + dc_channel_y(0) + sub_panel_switch_h / 2);
assert(ledge_ring_north_clearance >= ledge_ring_north_clearance_min,
    "north ring rail collides with the PH switch-body envelope");
echo(str("north ring-to-switch clearance: ", ledge_ring_north_clearance, " mm"));

module top_panel_8ch(include_revision = true) {
    translate([layout_offset_x, layout_offset_y, 0]) {
        difference() {
            union() {
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

                    if (include_revision) {
                        translate([revision_x, revision_y, 0])
                            label_pocket(top_panel_revision_label_w, revision_label_h);
                        translate([revision_x, revision_y + top_panel_brand_y_offset, 0])
                            label_pocket(top_panel_revision_label_w, revision_label_h);
                    }
                }

                panel_corner_screw_lands();
            }

            panel_corner_screw_holes(include_countersink = true);
        }

        translate([left_ac_x, ac_row_y, 0])
            positive_plate_writings(ac_devices[0], ac_details[0], ac_devices[1], ac_details[1]);
        translate([right_ac_x, ac_row_y, 0])
            positive_plate_writings(ac_devices[2], ac_details[2], ac_devices[3], ac_details[3]);

        for (i = [0:3])
            translate([dc_channel_x(i) + barrel_label_x, dc_channel_y(i) - barrel_channel_h / 2 + 10, 0])
                flush_two_line_label(dc_devices[i], dc_details[i], 5.3, 4.1, 6);

        for (i = [0:3])
            translate([dc_channel_x(i) + dc_toggle_x() + toggle_label_x_offset, dc_channel_y(i), 0])
                toggle_state_labels();

        translate([usb_c_panel_x, usb_c_panel_y - usb_c_panel_h / 2 + 4, 0])
            flush_label("COM", 5);

        if (include_revision) {
            translate([revision_x, revision_y, 0])
                flush_revision_label();
            translate([revision_x, revision_y + top_panel_brand_y_offset, 0])
                flush_label(top_panel_brand_text, top_panel_brand_font);
        }
    }
}

module sub_panel_8ch() {
    translate([layout_offset_x, layout_offset_y, 0]) {
        difference() {
            union() {
                translate([-layout_offset_x, -layout_offset_y, 0])
                    sub_panel_8ch_positive();
            }

            sub_panel_8ch_negative();
        }
    }
}



module floor_context() {
    color([0.68, 0.68, 0.62, 1])
        difference() {
            union() {
                translate([wall_t, wall_t, -box_h])
                    cube([box_inner_w, box_inner_d, wall_t]);
                floor_locator_lands();
                floor_locator_keys();
                if (feature_power_screw_mounts) {
                    component_airflow_posts_in_box();
                    psu_retaining_corners_in_box();
                    relay_retaining_corners_in_box();
                    converter_retaining_corners_in_box();
                }
                if (feature_psu_tie_wrap_anchors)
                    psu_floor_tie_wrap_anchors_in_box();
                if (feature_psu_tie_wrap_anchors)
                    psu_floor_stops_in_box();
            }
            relay_bottom_mount_holes();
            if (feature_power_screw_mounts) {
                psu_bottom_mount_holes();
                converter_bottom_mount_holes();
            }
            floor_corner_fastener_holes();
            box_bottom_revision_negative();
        }
}

module ledge_ring_corner_holes() {
    for (
        x = [panel_screw_inset, box_inner_w - panel_screw_inset],
        y = [panel_screw_inset, box_inner_d - panel_screw_inset]
    )
        translate([x, y, -0.1])
            cylinder(h = ledge_ring_t + 0.2, d = panel_screw_d);
}

module ledge_ring_ph_switch_clearances() {
    for (i = [0, 1]) {
        gap_start = top_ledge_gap_start(i);
        gap_end = top_ledge_gap_end(i, box_inner_w);

        if (gap_end > gap_start)
            translate([gap_start, box_inner_d - ledge_w - 0.1, -0.1])
                cube([
                    gap_end - gap_start,
                    ledge_w - ledge_ring_north_rail_w + 0.1,
                    ledge_ring_t + 0.2
                ]);
    }
}

module ledge_ring_revision_negative() {
    translate([box_inner_w / 2, ledge_w / 2, 0])
        mirror([1, 0, 0])
            write_text(revision_string, 4, -0.01);
}

module ledge_ring_frame() {
    difference() {
        cube([box_inner_w, box_inner_d, ledge_ring_t]);
        translate([ledge_w, ledge_w, -0.1])
            cube([
                box_inner_w - 2 * ledge_w,
                box_inner_d - 2 * ledge_w,
                ledge_ring_t + 0.2
            ]);
    }
}

module ledge_ring_local() {
    difference() {
        ledge_ring_frame();
        ledge_ring_corner_holes();
        if (feature_ph_ledge_holes)
            ledge_ring_ph_switch_clearances();
        ledge_ring_revision_negative();
    }
}

module ledge_ring_context() {
    color([0.95, 0.45, 0.1, 1])
        translate([wall_t, wall_t, ledge_top_z - ledge_ring_t])
            ledge_ring_local();
}

module ledge_ring() {
    ledge_ring_local();
}

module relay_bottom_mount_holes() {
    translate([
        box_inner_x + top_panel_w / 2 + internal_relay_x,
        box_inner_y + top_panel_h / 2 + internal_relay_y,
        0
    ])
        rotate([0, 0, internal_relay_rot_z])
            relay_mount_holes();
}

module relay_mount_holes(z0 = -box_h) {
    for (
        x = [-relay_mount_x / 2, relay_mount_x / 2],
        y = [-relay_mount_y / 2, relay_mount_y / 2]
    )
        translate([x, y, 0])
            bottom_chamfered_mount_hole(relay_mount_hole_d, relay_countersink_d, z0, relay_countersink_h);
}

module bottom_chamfered_mount_hole(d, chamfer_d, z0 = -box_h, t = wall_t) {
    translate([0, 0, z0 - 1])
        cylinder(h = t + 2, d = d);
    translate([0, 0, z0 - 0.1])
        cylinder(h = t + 0.1, d1 = chamfer_d, d2 = d);
}

module bottom_m3_flat_head_recess(surface_z = 0) {
    translate([0, 0, surface_z - 0.1])
        cylinder(
            h = panel_screw_countersink_h + 0.1,
            d1 = corner_screw_head_d,
            d2 = corner_screw_d
        );
}

function enclosure_corner_points() = [
    [corner_axis_inset, corner_axis_inset],
    [box_w - corner_axis_inset, corner_axis_inset],
    [corner_axis_inset, box_d - corner_axis_inset],
    [box_w - corner_axis_inset, box_d - corner_axis_inset]
];

module floor_corner_fastener_holes() {
    for (p = enclosure_corner_points())
        translate([p[0], p[1], 0]) {
            translate([0, 0, -box_h - 0.1])
                cylinder(h = wall_t + 0.2, d = corner_screw_d);
            bottom_m3_flat_head_recess(-box_h);
        }
}

module floor_locator_key_shape() {
    cube([floor_locator_l, floor_locator_depth, floor_locator_h]);
}

module floor_locator_lands() {
    x_locator_starts = [
        floor_locator_end_offset,
        box_w - floor_locator_end_offset - floor_locator_l
    ];
    y_locator_starts = [
        floor_locator_end_offset,
        box_d - floor_locator_end_offset - floor_locator_l
    ];

    for (x = x_locator_starts) {
        translate([x, wall_t - floor_locator_depth, -box_h])
            cube([floor_locator_l, floor_locator_depth, wall_t]);
        translate([x, box_d - wall_t, -box_h])
            cube([floor_locator_l, floor_locator_depth, wall_t]);
    }

    for (y = y_locator_starts) {
        translate([wall_t - floor_locator_depth, y, -box_h])
            cube([floor_locator_depth, floor_locator_l, wall_t]);
        translate([box_w - wall_t, y, -box_h])
            cube([floor_locator_depth, floor_locator_l, wall_t]);
    }
}

module floor_locator_keys() {
    x_locator_starts = [
        floor_locator_end_offset,
        box_w - floor_locator_end_offset - floor_locator_l
    ];
    y_locator_starts = [
        floor_locator_end_offset,
        box_d - floor_locator_end_offset - floor_locator_l
    ];
    z0 = -box_h + wall_t - 0.01;

    for (x = x_locator_starts) {
        translate([x, wall_t - floor_locator_depth, z0])
            floor_locator_key_shape();
        translate([x, box_d - wall_t, z0])
            floor_locator_key_shape();
    }

    for (y = y_locator_starts) {
        translate([wall_t, y, z0])
            rotate([0, 0, 90])
                floor_locator_key_shape();
        translate([box_w - wall_t, y + floor_locator_l, z0])
            rotate([0, 0, -90])
                floor_locator_key_shape();
    }
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

module psu_mount_holes(z0 = -box_h) {
    psu_mount_hole_from_view(psu_view_w - psu_mount_x_inset, psu_mount_y_inset, z0);
    psu_mount_hole_from_view(psu_mount_x_inset, psu_view_d - psu_mount_y_inset, z0);
}

module psu_mount_hole_from_view(x, y, z0 = -box_h) {
    translate([y - psu_view_d / 2, psu_view_w / 2 - x, 0])
        bottom_chamfered_mount_hole(psu_mount_hole_d, psu_mount_chamfer_d, z0, wall_t + component_raise_h);
}

module psu_mount_markers(z) {
    psu_mount_marker_from_view(psu_view_w - psu_mount_x_inset, psu_mount_y_inset, z);
    psu_mount_marker_from_view(psu_mount_x_inset, psu_view_d - psu_mount_y_inset, z);
}

module psu_mount_marker_from_view(x, y, z) {
    translate([y - psu_view_d / 2, psu_view_w / 2 - x, z])
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
            retaining_corners(converter_retaining_w, converter_retaining_d);
}

module component_airflow_posts_in_box() {
    translate([
        box_inner_x + top_panel_w / 2 + internal_psu_x,
        box_inner_y + top_panel_h / 2 + internal_psu_y,
        -box_h + wall_t
    ])
        rotate([0, 0, internal_psu_rot_z])
            psu_airflow_posts();

    translate([
        box_inner_x + top_panel_w / 2 + internal_converter_x,
        box_inner_y + top_panel_h / 2 + internal_converter_y,
        -box_h + wall_t
    ])
        rotate([0, 0, internal_converter_rot_z])
            converter_airflow_posts();
}

module component_airflow_posts_except(w, d, excludes) {
    xs = support_positions(w);
    ys = support_positions(d);
    for (x = xs, y = ys)
        if (!point_near_any([x, y], excludes, component_airflow_post_hole_clearance))
            translate([x, y, 0])
                cylinder(h = component_raise_h, d = component_airflow_post_d);
}

function support_position_count(length) = max(3, floor(length / component_airflow_post_spacing) + 1);
function support_position_span(length) = length - component_airflow_post_spacing;
function support_positions(length) =
    let(n = support_position_count(length), span = support_position_span(length))
        [for (i = [0:n - 1]) n == 1 ? 0 : -span / 2 + i * span / (n - 1)];

function point_near_any(p, points, clearance, i = 0) =
    i >= len(points) ? false :
    norm([p[0] - points[i][0], p[1] - points[i][1]]) < clearance ? true :
    point_near_any(p, points, clearance, i + 1);

function psu_mount_points() = [
    [psu_mount_y_inset - psu_view_d / 2, psu_view_w / 2 - (psu_view_w - psu_mount_x_inset)],
    [psu_view_d - psu_mount_y_inset - psu_view_d / 2, psu_view_w / 2 - psu_mount_x_inset]
];

function converter_mount_points() = [
    [0, -converter_mount_spacing / 2],
    [0, converter_mount_spacing / 2]
];

module psu_airflow_posts() {
    component_airflow_posts_except(psu_w, psu_d, psu_mount_points());
}

module converter_airflow_posts() {
    xs = support_positions(converter_w);
    ys = support_positions(converter_d);
    for (x = xs, y = ys)
        if (!point_near_any([x, y], converter_mount_points(), component_airflow_post_hole_clearance))
            translate([x, y, 0])
                cylinder(h = component_raise_h, d = component_airflow_post_d);
}

module retaining_corners(w, d) {
    for (sx = [-1, 1], sy = [-1, 1])
        retaining_corner(w, d, sx, sy);
}

module psu_retaining_corners() {
    retaining_corner(psu_w, psu_d, -1, 1);
    retaining_corner(psu_w, psu_d, 1, -1);
    psu_side_guides();
}

module psu_side_guides() {
    for (y = [-psu_d / 2 - psu_side_guide_t, psu_d / 2])
        translate([-psu_side_guide_l / 2, y, 0])
            cube([psu_side_guide_l, psu_side_guide_t, psu_side_guide_h]);
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
            converter_mount_holes();
}

module converter_mount_holes(z0 = -box_h) {
    for (y = [-converter_mount_spacing / 2, converter_mount_spacing / 2])
        translate([0, y, 0])
            bottom_chamfered_mount_hole(converter_mount_hole_d, converter_mount_chamfer_d, z0, wall_t + component_raise_h);
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

module panel_corner_screw_hole(include_countersink = false) {
    screw_hole(panel_screw_d);

    if (include_countersink)
        translate([0, 0, plate_t - panel_screw_countersink_h])
            cylinder(
                h = panel_screw_countersink_h + 0.1,
                d1 = panel_screw_d,
                d2 = panel_screw_countersink_d
            );
}

module panel_corner_screw_lands() {
    intersection() {
        union()
            for (
                x = [panel_screw_inset, top_panel_w - panel_screw_inset],
                y = [panel_screw_inset, top_panel_h - panel_screw_inset]
            )
                translate([x - layout_offset_x, y - layout_offset_y, plate_t - 0.5])
                    cylinder(h = 0.5, d = panel_screw_land_d);

        translate([-layout_offset_x, -layout_offset_y, plate_t - 0.5])
            cube([top_panel_w, top_panel_h, 0.5]);
    }
}

module panel_corner_screw_holes(include_countersink = false) {
    for (
        x = [panel_screw_inset, top_panel_w - panel_screw_inset],
        y = [panel_screw_inset, top_panel_h - panel_screw_inset]
    )
        translate([x - layout_offset_x, y - layout_offset_y, 0])
            panel_corner_screw_hole(include_countersink);
}

module panel_corner_fastener_boss(direction = 1) {
    union() {
        translate([0, 0, panel_fastener_boss_bottom_z])
            cylinder(h = panel_fastener_boss_h, d = panel_fastener_boss_d);
        translate([
            direction < 0 ? -panel_nut_entry_l : 0,
            -panel_fastener_boss_d / 2,
            panel_fastener_boss_bottom_z
        ])
            cube([panel_nut_entry_l, panel_fastener_boss_d, panel_fastener_boss_h]);
    }
}

module self_supporting_nut_trap_roof(x0, length, width, z0, tip_w = 1) {
    roof_h = (width - tip_w) / 2;

    hull() {
        translate([x0, -width / 2, z0 - 0.01])
            cube([length, width, 0.02]);
        translate([x0, -tip_w / 2, z0 + roof_h])
            cube([length, tip_w, 0.02]);
    }
}

module side_loaded_panel_nut_trap(direction = 1) {
    slot_w = panel_nut_d + panel_nut_clearance;
    slot_h = panel_nut_h + panel_nut_clearance;
    main_l = panel_nut_entry_l - panel_nut_entry_detent_l;
    throat_w = slot_w - 2 * panel_nut_entry_detent;
    roof_l = panel_nut_entry_l + panel_nut_d / 2;
    roof_x = direction < 0 ? -panel_nut_entry_l : -panel_nut_d / 2;

    rotate([0, 0, 30])
        cylinder(h = slot_h, d = panel_nut_d + panel_nut_clearance, $fn = 6);

    translate([direction < 0 ? -main_l : 0, -slot_w / 2, 0])
        cube([main_l, slot_w, slot_h]);
    translate([
        direction < 0 ? -panel_nut_entry_l : main_l,
        -throat_w / 2,
        0
    ])
        cube([panel_nut_entry_detent_l, throat_w, slot_h]);

    self_supporting_nut_trap_roof(roof_x, roof_l, slot_w, slot_h);
}

// Wall-local printable coordinates:
// X runs along the wall, Y runs along enclosure Z / the screw axis,
// and Z runs from the exterior build-plate face toward the box interior.
module support_free_bore_profile(d) {
    r = d / 2;
    a = r / sqrt(2);

    union() {
        intersection() {
            circle(d = d);
            translate([-r, -r])
                square([d, r + a]);
        }
        polygon([[-a, a], [0, 2 * a], [a, a]]);
    }
}

module support_free_horizontal_bore(length, d, axis_z = wall_t + panel_screw_inset) {
    translate([0, 0, axis_z])
        rotate([90, 0, 0])
            linear_extrude(height = length, center = true)
                support_free_bore_profile(d);
}

module corner_tab_positive() {
    translate([corner_tab_outer_x, -corner_tab_t / 2, 0])
        cube([corner_tab_effective_w, corner_tab_t, corner_tab_h]);
}

module corner_nut_tab_positive(bearing_side = 1) {
    y0 = -corner_tab_t / 2
        - (bearing_side > 0
            ? corner_nut_retainer_t + corner_nut_tab_extension
            : 0);
    corner_nut_tab_length = corner_tab_t
        + corner_nut_retainer_t
        + corner_nut_tab_extension;

    translate([corner_tab_outer_x, y0, 0])
        cube([
            corner_tab_effective_w,
            corner_nut_tab_length,
            corner_tab_h
        ]);
}

// Subtractive entry transition that leaves two small positive detents.
// Their 30-degree faces guide the nut past the narrow retaining throat.
module corner_nut_retention_detents(
    nut_flat_w,
    throat_w,
    pocket_center_y,
    detent_bottom_z
) {
    shim = 0.01;
    entry_y = pocket_center_y - corner_nut_slot_l / 2;
    ramp_start_z = detent_bottom_z - corner_nut_detent_ramp_h;

    hull() {
        translate([-nut_flat_w / 2, entry_y, ramp_start_z - shim])
            cube([nut_flat_w, corner_nut_slot_l, shim]);
        translate([-throat_w / 2, entry_y, detent_bottom_z])
            cube([throat_w, corner_nut_slot_l, shim]);
    }

    translate([-throat_w / 2, entry_y, detent_bottom_z])
        cube([
            throat_w,
            corner_nut_slot_l,
            corner_tab_h - detent_bottom_z + 1
        ]);
}

module support_free_m3_nut_trap(
    bearing_side = 1,
    pocket_offset_y = 0,
    axis_z = wall_t + panel_screw_inset
) {
    nut_d = corner_nut_d + corner_nut_clearance;
    nut_flat_w = nut_d * cos(30);
    throat_w = nut_flat_w - 2 * panel_nut_entry_detent;
    pocket_center_y = -bearing_side * corner_nut_shoulder_t / 2
        + pocket_offset_y;
    detent_bottom_z = corner_tab_h - panel_nut_entry_detent_l;

    translate([0, pocket_center_y, axis_z])
        rotate([0, 30, 0])
            rotate([90, 0, 0])
                cylinder(h = corner_nut_slot_l, d = nut_d, center = true, $fn = 6);

    // The main entry is open toward the wall's Z-positive interior face.
    translate([
        -nut_flat_w / 2,
        pocket_center_y - corner_nut_slot_l / 2,
        axis_z
    ])
        cube([
            nut_flat_w,
            corner_nut_slot_l,
            detent_bottom_z - corner_nut_detent_ramp_h - axis_z
        ]);

    corner_nut_retention_detents(
        nut_flat_w,
        throat_w,
        pocket_center_y,
        detent_bottom_z
    );
}

module corner_clearance_tab() {
    difference() {
        corner_tab_positive();
        support_free_horizontal_bore(corner_tab_t + 0.2, corner_screw_d);
    }
}

module corner_nut_tab(bearing_side = 1) {
    corner_nut_tab_length = corner_tab_t
        + corner_nut_retainer_t
        + corner_nut_tab_extension;
    corner_nut_tab_bore_center_y = -bearing_side
        * (corner_nut_retainer_t + corner_nut_tab_extension) / 2;
    nut_offset_y = bearing_side < 0 ? bottom_corner_nut_offset : 0;

    difference() {
        corner_nut_tab_positive(bearing_side);
        translate([0, corner_nut_tab_bore_center_y, 0])
            support_free_horizontal_bore(
                corner_nut_tab_length + 0.2,
                corner_screw_d
            );
        support_free_m3_nut_trap(
            bearing_side,
            pocket_offset_y = nut_offset_y
        );
    }
}

function top_clearance_tab_center_y(h) = h + ledge_top_z - ledge_ring_t - corner_tab_t / 2;
function top_nut_tab_center_y(h) = top_clearance_tab_center_y(h) - corner_tab_t;
function bottom_clearance_tab_center_y() = wall_t + corner_tab_t / 2;
function bottom_nut_tab_center_y() = bottom_clearance_tab_center_y() + corner_tab_t;
assert(ledge_top_z == -(plate_t + sub_panel_h),
    "sub-panel top datum must stay fixed below the top panel");
assert(top_nut_tab_center_y(box_h) < top_clearance_tab_center_y(box_h),
    "top nut tab must remain below the clearance tab");
assert(bottom_clearance_tab_center_y() < bottom_nut_tab_center_y(),
    "bottom clearance tab must remain below the nut tab");

module mitred_wall_segment(l = corner_coupon_wall_l, h = corner_coupon_wall_h) {
    polyhedron(
        points = [
            [0, 0, 0], [l, 0, 0], [l, h, 0], [0, h, 0],
            [wall_t, 0, wall_t], [l, 0, wall_t], [l, h, wall_t], [wall_t, h, wall_t]
        ],
        faces = [
            [0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4],
            [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]
        ]
    );
}

module wall_mitre_negative(length, h = wall_z_height) {
    translate([0, h + 0.1, 0])
        rotate([90, 0, 0])
            linear_extrude(height = h + 0.2)
                polygon([
                    [-0.1, -0.1],
                    [wall_t + 0.1, wall_t + 0.1],
                    [-0.1, wall_t + 0.1]
                ]);

    translate([0, h + 0.1, 0])
        rotate([90, 0, 0])
            linear_extrude(height = h + 0.2)
                polygon([
                    [length + 0.1, -0.1],
                    [length + 0.1, wall_t + 0.1],
                    [length - wall_t - 0.1, wall_t + 0.1]
                ]);
}

module wall_body_positive(length, h = wall_z_height) {
    difference() {
        cube([length, h, wall_t]);
        wall_mitre_negative(length, h);
    }
}

module wall_revision_negative(length, h = wall_z_height, vent_mode = "none") {
    revision_x = vent_mode == "half" ? length / 3 : length / 2;

    translate([revision_x, h / 2, wall_t])
        write_text(revision_string, box_revision_font, -0.6);
}

module wall_vent_negatives(length, vent_mode = "none", h = wall_z_height) {
    vent_ys = [
        vent_floor_clearance:
        vent_hole_spacing:
        h - vent_top_margin - vent_ledge_clearance
    ];
    vent_start_x = vent_mode == "half" ? length / 2 : vent_wall_margin;
    vent_xs = [vent_start_x:vent_hole_spacing:length - vent_wall_margin];
    joint_min_x = corner_axis_inset + corner_tab_w / 2;
    joint_max_x = length - joint_min_x;
    joint_min_y = bottom_nut_tab_center_y() + corner_tab_t / 2;
    joint_max_y = top_nut_tab_center_y(h) - corner_tab_t / 2;

    if (vent_mode != "none")
        for (x = vent_xs, y = vent_ys)
            if (
                x - vent_hole_d / 2 >= joint_min_x + wall_vent_joint_clearance
                && x + vent_hole_d / 2 <= joint_max_x - wall_vent_joint_clearance
                && y - vent_hole_d / 2 >= joint_min_y + wall_vent_joint_clearance
                && y + vent_hole_d / 2 <= joint_max_y - wall_vent_joint_clearance
            )
                translate([x, y, -0.1])
                    cylinder(h = wall_t + wall_rib_h + 0.2, d = vent_hole_d);
}

module wall_stiffening_ribs(length, h, vent_mode = "none") {
    rib_xs = vent_mode == "half"
        ? [length / 4, length / 2 + vent_hole_spacing / 2]
        : (vent_mode == "full"
            ? [vent_wall_margin + vent_hole_spacing / 2, length - 21]
            : [length / 3, 2 * length / 3]);
    rib_y0 = bottom_nut_tab_center_y() + corner_tab_t / 2 + wall_vent_joint_clearance;
    rib_y1 = top_nut_tab_center_y(h) - corner_tab_t / 2 - wall_vent_joint_clearance;
    transverse_rib_y = top_nut_tab_center_y(h)
        - corner_nut_shoulder_t / 2;
    floor_rib_y0 = wall_t;
    transverse_rib_x0 = corner_axis_inset + corner_tab_w / 2;
    transverse_rib_x1 = length - transverse_rib_x0;
    floor_rib_x0 = floor_locator_end_offset
        + floor_locator_l
        + floor_locator_clearance;
    floor_rib_x1 = length - floor_rib_x0;

    for (x = rib_xs)
        translate([x - wall_rib_w / 2, rib_y0, wall_t])
            cube([wall_rib_w, rib_y1 - rib_y0, wall_rib_h]);

    translate([transverse_rib_x0, transverse_rib_y - wall_rib_w / 2, wall_t])
        cube([
            transverse_rib_x1 - transverse_rib_x0,
            wall_rib_w,
            wall_rib_h
        ]);

    translate([floor_rib_x0, floor_rib_y0, wall_t])
        cube([
            floor_rib_x1 - floor_rib_x0,
            wall_rib_w,
            wall_rib_h
        ]);
}

module floor_locator_notches(length) {
    for (x = [
        floor_locator_end_offset,
        length - floor_locator_end_offset - floor_locator_l
    ])
        translate([
            x - floor_locator_clearance,
            -0.1,
            wall_t - floor_locator_depth - floor_locator_clearance
        ])
            cube([
                floor_locator_l + 2 * floor_locator_clearance,
                wall_t + floor_locator_h + floor_locator_clearance + 0.1,
                floor_locator_depth + 2 * floor_locator_clearance
            ]);
}

module wall_end_feature(right = false, length = box_w) {
    if (right)
        translate([length, 0, 0])
            mirror([1, 0, 0])
                children();
    else
        children();
}

module wall_corner_tabs(length, h, nut_owner) {
    for (right = [false, true])
        wall_end_feature(right = right, length = length) {
            translate([corner_axis_inset, top_nut_tab_center_y(h), 0])
                if (nut_owner)
                    corner_nut_tab(bearing_side = 1);
            translate([corner_axis_inset, top_clearance_tab_center_y(h), 0])
                if (!nut_owner)
                    corner_clearance_tab();
            translate([corner_axis_inset, bottom_nut_tab_center_y(), 0])
                if (nut_owner)
                    corner_nut_tab(bearing_side = -1);
            translate([corner_axis_inset, bottom_clearance_tab_center_y(), 0])
                if (!nut_owner)
                    corner_clearance_tab();
        }
}

module flat_wall(length, nut_owner = false, vent_mode = "none", h = wall_z_height) {
    difference() {
        union() {
            wall_body_positive(length, h);
            wall_corner_tabs(length, h, nut_owner);
            wall_stiffening_ribs(length, h, vent_mode);
        }
        floor_locator_notches(length);
        wall_vent_negatives(length, vent_mode, h);
        wall_revision_negative(length, h, vent_mode);
    }
}

module south_wall_context() {
    color([0.15, 0.45, 0.9, 1])
        multmatrix([
            [1, 0, 0, 0],
            [0, 0, 1, 0],
            [0, 1, 0, -box_h],
            [0, 0, 0, 1]
        ])
            flat_wall(box_w, nut_owner = true, vent_mode = "half");
}

module north_wall_context() {
    color([0.15, 0.45, 0.9, 1])
        multmatrix([
            [1, 0, 0, 0],
            [0, 0, -1, box_d],
            [0, 1, 0, -box_h],
            [0, 0, 0, 1]
        ])
            flat_wall(box_w, nut_owner = true, vent_mode = "half");
}

module west_wall_context() {
    color([0.2, 0.75, 0.35, 1])
        multmatrix([
            [0, 0, 1, 0],
            [-1, 0, 0, box_d],
            [0, 1, 0, -box_h],
            [0, 0, 0, 1]
        ])
            flat_wall(box_d, nut_owner = false, vent_mode = "none");
}

module east_wall_context() {
    color([0.2, 0.75, 0.35, 1])
        multmatrix([
            [0, 0, -1, box_w],
            [1, 0, 0, 0],
            [0, 1, 0, -box_h],
            [0, 0, 0, 1]
        ])
            flat_wall(box_d, nut_owner = false, vent_mode = "full");
}

module north_wall() {
    flat_wall(box_w, nut_owner = true, vent_mode = "half");
}

module south_wall() {
    flat_wall(box_w, nut_owner = true, vent_mode = "half");
}

module west_wall() {
    flat_wall(box_d, nut_owner = false, vent_mode = "none");
}

module east_wall() {
    flat_wall(box_d, nut_owner = false, vent_mode = "full");
}

module corner_wall_coupon(nut_owner = false, top = true) {
    tab_y = top
        ? (nut_owner
            ? top_nut_tab_center_y(corner_coupon_wall_h)
            : top_clearance_tab_center_y(corner_coupon_wall_h))
        : (nut_owner
            ? bottom_nut_tab_center_y()
            : bottom_clearance_tab_center_y());
    bearing_side = top ? 1 : -1;

    difference() {
        union() {
            mitred_wall_segment();
            translate([corner_axis_inset, tab_y, 0])
                if (nut_owner)
                    corner_nut_tab(bearing_side);
                else
                    corner_clearance_tab();
        }
    }
}

module corner_coupon_plate(t, head_side = 0) {
    coupon_w = 16;
    outer_edge_offset = panel_screw_inset - coupon_assembly_clearance;

    difference() {
        translate([-coupon_w + outer_edge_offset, -coupon_w + outer_edge_offset, 0])
            cube([coupon_w, coupon_w, t]);
        translate([0, 0, -0.1])
            cylinder(h = t + 0.2, d = corner_screw_d);
        if (head_side > 0)
            translate([0, 0, t - panel_screw_countersink_h])
                cylinder(
                    h = panel_screw_countersink_h + 0.1,
                    d1 = corner_screw_d,
                    d2 = corner_screw_head_d
                );
        if (head_side < 0)
            bottom_m3_flat_head_recess();
    }
}

module corner_coupon_north_context(top = true, origin = [0, 0, 0]) {
    z_offset = top ? -corner_coupon_wall_h : 0;
    translate(origin)
        multmatrix([
            [-1, 0, 0, corner_axis_inset],
            [0, 0, -1, wall_t + panel_screw_inset],
            [0, 1, 0, z_offset],
            [0, 0, 0, 1]
        ])
            corner_wall_coupon(nut_owner = true, top = top);
}

module corner_coupon_east_context(top = true, origin = [0, 0, 0]) {
    z_offset = top ? -corner_coupon_wall_h : 0;
    translate(origin)
        multmatrix([
            [0, 0, -1, wall_t + panel_screw_inset],
            [-1, 0, 0, corner_axis_inset],
            [0, 1, 0, z_offset],
            [0, 0, 0, 1]
        ])
            corner_wall_coupon(nut_owner = false, top = top);
}

module wall_corner_fastener_assembly() {
    top_origin = [-28, 0, 0];
    bottom_origin = [28, 0, 0];

    color([0.15, 0.45, 0.9, 1]) {
        corner_coupon_north_context(true, top_origin);
        corner_coupon_north_context(false, bottom_origin);
    }
    color([0.2, 0.75, 0.35, 1]) {
        corner_coupon_east_context(true, top_origin);
        corner_coupon_east_context(false, bottom_origin);
    }

    color([0.85, 0.72, 0.15, 1]) {
        translate(top_origin + [0, 0, -plate_t])
            corner_coupon_plate(plate_t, 1);
        translate(top_origin + [0, 0, ledge_top_z])
            corner_coupon_plate(sub_panel_h);
        translate(top_origin + [0, 0, ledge_top_z - ledge_ring_t])
            corner_coupon_plate(ledge_ring_t);
        translate(bottom_origin + [0, 0, 0])
            corner_coupon_plate(wall_t, -1);
    }
}

module corner_coupon() {
    echo(str("corner screws: 8x M3x", corner_screw_length));
    echo(str("top stack: ", top_stack_h, " mm"));
    echo(str("bottom stack: ", bottom_stack_h, " mm"));
    echo(str("nut bearing shoulder: ", corner_nut_shoulder_t, " mm"));

    // Four actual wall snippets in their exterior-face-down print orientation.
    translate([0, 0, 0])
        corner_wall_coupon(nut_owner = true, top = true);
    translate([44, 0, 0])
        corner_wall_coupon(nut_owner = false, top = true);
    translate([0, 40, 0])
        corner_wall_coupon(nut_owner = true, top = false);
    translate([44, 40, 0])
        corner_wall_coupon(nut_owner = false, top = false);

    // Exact head recess and stack-thickness surrogates.
    translate([coupon_plate_column_x, 12, 0])
        corner_coupon_plate(plate_t, 1);
    translate([coupon_plate_column_x, 34, 0])
        corner_coupon_plate(sub_panel_h);
    translate([coupon_plate_column_x, 56, 0])
        corner_coupon_plate(ledge_ring_t);
    translate([coupon_plate_column_x + 22, 12, 0])
        corner_coupon_plate(wall_t, -1);
}

module panel_corner_fastener_test() {
    test_w = 18;

    translate([0, 0, -panel_fastener_boss_bottom_z])
        difference() {
            union() {
                translate([-test_w / 2, -test_w / 2, -plate_t])
                    cube([test_w, test_w, plate_t]);
                translate([-test_w / 2, -test_w / 2, ledge_top_z])
                    cube([test_w, test_w, sub_panel_h]);
                panel_corner_fastener_boss(1);
            }

            translate([0, 0, -plate_t])
                panel_corner_screw_hole(include_countersink = true);
            translate([0, 0, panel_fastener_boss_bottom_z - 1])
                cylinder(h = -panel_fastener_boss_bottom_z + 2, d = panel_screw_d);
            translate([0, 0, panel_nut_trap_z])
                side_loaded_panel_nut_trap(1);
        }
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
            translate([internal_psu_x, internal_psu_y, -box_h + wall_t + component_raise_h])
                rotate([0, 0, internal_psu_rot_z])
                    psu_keepout();
        if (show_psu)
            translate([internal_converter_x, internal_converter_y, -box_h + wall_t + component_raise_h])
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

module floor_part() {
    echo_hardware(true, true, true, true);
    translate([0, 0, box_h])
        floor_context();
}

module footprint_base(w, d, margin = 12) {
    translate([-w / 2 - margin, -d / 2 - margin, 0])
        cube([w + 2 * margin, d + 2 * margin, wall_t]);
}

module psu_footprint() {
    echo_hardware(include_psu = true);
    difference() {
        union() {
            footprint_base(psu_view_w, psu_view_d);
            translate([0, 0, wall_t])
                rotate([0, 0, internal_psu_rot_z])
                    psu_airflow_posts();
            translate([0, 0, wall_t])
                rotate([0, 0, internal_psu_rot_z])
                    psu_retaining_corners();
        }
        rotate([0, 0, internal_psu_rot_z])
            psu_mount_holes(0);
    }
}

module converter_footprint() {
    echo_hardware(include_converter = true);
    difference() {
        union() {
            footprint_base(converter_w, converter_d);
            translate([0, 0, wall_t])
                rotate([0, 0, internal_converter_rot_z])
                    converter_airflow_posts();
            translate([0, 0, wall_t])
                rotate([0, 0, internal_converter_rot_z])
                    retaining_corners(converter_retaining_w, converter_retaining_d);
        }
        rotate([0, 0, internal_converter_rot_z])
            converter_mount_holes(0);
    }
}

module relay_footprint() {
    echo_hardware(include_relay = true);
    difference() {
        union() {
            footprint_base(relay_d, relay_w);
            translate([0, 0, wall_t])
                rotate([0, 0, internal_relay_rot_z])
                    retaining_corners(relay_w, relay_d);
        }
        rotate([0, 0, internal_relay_rot_z])
            relay_mount_holes(0);
    }
}

module assembly() {
    echo_hardware(true, true, true, true);
    if (show_north_wall)
        north_wall_context();
    if (show_south_wall)
        south_wall_context();
    if (show_west_wall)
        west_wall_context();
    if (show_east_wall)
        east_wall_context();

    if (show_ledge_ring)
        ledge_ring_context();

    if (show_floor)
        floor_context();

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

if (view == "relay_footprint") {
    relay_footprint();
} else if (view == "psu_footprint") {
    psu_footprint();
} else if (view == "converter_footprint") {
    converter_footprint();
} else if (view == "floor") {
    floor_part();
} else if (view == "north_wall") {
    north_wall();
} else if (view == "south_wall") {
    south_wall();
} else if (view == "west_wall") {
    west_wall();
} else if (view == "east_wall") {
    east_wall();
} else if (view == "ledge_ring") {
    ledge_ring();
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
} else if (view == "panel_corner_fastener_test") {
    panel_corner_fastener_test();
} else if (view == "corner_coupon") {
    corner_coupon();
} else if (view == "wall_corner_fastener_test") {
    corner_coupon();
} else if (view == "wall_corner_fastener_assembly") {
    wall_corner_fastener_assembly();
} else if (view == "top_panel") {
    top_panel();
} else if (view == "sub_panel") {
    sub_panel();
} else if (view == "assembly") {
    assembly();
} else {
    assembly();
}
