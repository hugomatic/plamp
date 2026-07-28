// Peristaltic pump stand: a horizontal motor plate and two end-panel legs.

set = "plate"; // [plate, legs, assembly]
revision_string = "dev";

// Measured pump dimensions and fit controls.
pump_count = 2;
pump_spacing = 62;
motor_hole_d = 29;
motor_screw_spacing = 48.5;
motor_clearance_h = 55;
mount_hole_d = 5.5;

// Print and construction dimensions.
render_fn = 64;
$fn = render_fn;
boolean_overlap = 0.1;
plate_t = 4;
plate_d = 44;
plate_end_margin = 12;
pump_mount_hole_d = 3.4;
leg_t = 4;
leg_tab_d = 10;
leg_slot_clearance = 0.25;
leg_print_gap = 10;
// Keep the M5 bore clear of the leg tab slot while the ear bridges around it.
// 33 mm outside diameter: twice the preceding 16.5 mm fit-test ear.
mount_ear_wall = 13.75;
leg_inset = 4;

plate_w = (pump_count - 1) * pump_spacing + motor_screw_spacing
    + 2 * plate_end_margin;
leg_x = plate_w / 2 - leg_t / 2 - leg_inset;
mount_ear_r = mount_hole_d / 2 + mount_ear_wall;
// Centre on the plate end: the exterior profile is a true semicircular ear.
mount_ear_x = plate_w / 2;

// Each station is collinear along X: M3, motor opening, M3.
module pump_station_negative(index) {
    x = (index - (pump_count - 1) / 2) * pump_spacing;
    translate([x, 0, -boolean_overlap]) {
        cylinder(d = motor_hole_d, h = plate_t + 2 * boolean_overlap);
        for (dx = [-motor_screw_spacing / 2, motor_screw_spacing / 2])
            translate([dx, 0, 0])
                cylinder(d = pump_mount_hole_d,
                    h = plate_t + 2 * boolean_overlap);
    }
}

module leg_slot_negative(x) {
    translate([
        x - (leg_t + leg_slot_clearance) / 2,
        -leg_tab_d / 2,
        -boolean_overlap
    ])
        cube([
            leg_t + leg_slot_clearance,
            leg_tab_d + leg_slot_clearance,
            plate_t + 2 * boolean_overlap
        ]);
}

module plate_positive() {
    union() {
        translate([-plate_w / 2, -plate_d / 2, 0])
            cube([plate_w, plate_d, plate_t]);

        // These ears place the table-mounting holes outside the end legs.
        for (x = [-mount_ear_x, mount_ear_x])
            translate([x, 0, 0])
                cylinder(d = 2 * mount_ear_r, h = plate_t);
    }
}

module plate() {
    difference() {
        plate_positive();

        for (index = [0:pump_count - 1]) pump_station_negative(index);

        for (x = [-mount_ear_x, mount_ear_x])
            translate([x, 0, -boolean_overlap])
                cylinder(d = mount_hole_d, h = plate_t + 2 * boolean_overlap);

        for (x = [-leg_x, leg_x]) leg_slot_negative(x);
    }
}

module leg_panel(height = motor_clearance_h) {
    union() {
        translate([-leg_t / 2, -plate_d / 2, 0])
            cube([leg_t, plate_d, height]);
        translate([-leg_t / 2, -leg_tab_d / 2, height])
            cube([leg_t, leg_tab_d, plate_t]);
    }
}

module leg_pair() {
    for (x = [-leg_x, leg_x])
        translate([x, 0, 0]) leg_panel(motor_clearance_h);
}

// Lay both panels flat on the bed, retaining their tab geometry.
module legs() {
    for (x = [0, motor_clearance_h + leg_print_gap])
        translate([x, 0, leg_t])
            rotate([0, 90, 0]) leg_panel(motor_clearance_h);
}

module assembly() {
    leg_pair();
    translate([0, 0, motor_clearance_h]) plate();
}

if (set == "plate") plate();
else if (set == "legs") legs();
else if (set == "assembly") assembly();
