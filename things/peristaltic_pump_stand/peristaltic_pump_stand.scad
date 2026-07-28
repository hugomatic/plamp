// Peristaltic pump stand: a separate mounting plate and two end-panel legs.

set = "plate"; // [plate, legs, assembly]
revision_string = "dev";

// Measured pump dimensions and fit controls.
pump_count = 2;
pump_spacing = 62;
motor_hole_d = 29;
motor_screw_spacing = 48.5;
motor_clearance_h = 55;
mount_hole_d = 5.5;

module plate() {
    cube([1, 1, 1]);
}

module legs() {
    cube([1, 1, 1]);
}

module assembly() {
    plate();
    translate([2, 0, 0]) legs();
}

if (set == "plate") plate();
else if (set == "legs") legs();
else if (set == "assembly") assembly();
