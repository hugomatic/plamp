render_fn = 96;
$fn = render_fn;
set = "hook_core"; // [hook_core, bar_fit_coupon, insert_fit_coupon, assembly]
revision_string = "dev";

/* [bar and hook] */
bar_d = 26;
saddle_d = 29;
hook_width_y = 24;
core_radial_t = 8;
loaded_leg_h = 22;
open_nose_h = 7;
profile_blend_r = 5;

/* [CamJam attachment] */
insert_od = 10.5;
insert_length = 12;
insert_pilot_d = 9.5;
insert_pilot_clearance = 0.3;
m5_clearance_d = 5.5;
neck_od = 15;
boss_flare_od = 24;
boss_h = 18;
camjam_clearance_h = 8;
camjam_ring_id = 8;
camjam_ring_wire_d = 5;
camjam_sweep_radius = 42;
camjam_sweep_body_r = 8;
camjam_sweep_h = 12;

/* [fit coupons] */
bar_coupon_width_y = 10;
insert_coupon_pilot_ds = [9.2, 9.5, 9.8];
insert_coupon_spacing = 24;
insert_coupon_w = 68;
insert_coupon_d = 24;
insert_coupon_h = 16;

/* [rendering] */
boolean_shim = 0.1;
revision_depth = 0.5;
revision_font = 3.5;

saddle_r = saddle_d / 2;
hook_outer_r = saddle_r + core_radial_t;
boss_bottom_z = saddle_r + loaded_leg_h;
boss_top_z = boss_bottom_z + boss_h;
boss_flare_h = boss_h - camjam_clearance_h;
throat_w = saddle_d;

assert(saddle_d > bar_d, "saddle must clear the 26 mm bar");
assert(throat_w > bar_d, "open throat must admit the bar from above");
assert(neck_od > insert_od, "neck must retain material around the insert");
assert(boss_h >= insert_length + 2,
    "boss must retain material beyond the insert length");
assert(boss_flare_h > 0,
    "CamJam clearance must leave room for the lower boss flare");

module extrude_profile_y(width = hook_width_y) {
    rotate([90, 0, 0])
        linear_extrude(height = width, center = true)
            children();
}

module lower_saddle_profile() {
    intersection() {
        difference() {
            circle(r = hook_outer_r);
            circle(r = saddle_r);
        }
        translate([-hook_outer_r - boolean_shim, -hook_outer_r - boolean_shim])
            square([
                2 * hook_outer_r + 2 * boolean_shim,
                hook_outer_r + boolean_shim
            ]);
    }
}

module loaded_leg_profile() {
    hull() {
        translate([-hook_outer_r + core_radial_t / 2, -profile_blend_r])
            circle(r = core_radial_t / 2);
        translate([-hook_outer_r + core_radial_t / 2, boss_bottom_z - profile_blend_r])
            circle(r = core_radial_t / 2);
        translate([-boss_flare_od / 2 + profile_blend_r, boss_bottom_z])
            circle(r = profile_blend_r);
    }
}

module open_nose_profile() {
    hull() {
        translate([hook_outer_r - core_radial_t / 2, -profile_blend_r])
            circle(r = core_radial_t / 2);
        translate([hook_outer_r - core_radial_t / 2, open_nose_h])
            circle(r = core_radial_t / 2);
    }
}

module hook_body_positive() {
    extrude_profile_y()
        union() {
            lower_saddle_profile();
            loaded_leg_profile();
            open_nose_profile();
        }
}

module attachment_boss_positive() {
    union() {
        translate([0, 0, boss_bottom_z])
            cylinder(h = boss_flare_h, d1 = boss_flare_od, d2 = neck_od);
        translate([0, 0, boss_bottom_z + boss_flare_h - boolean_shim])
            cylinder(h = camjam_clearance_h + boolean_shim, d = neck_od);
    }
}

module hook_core_positive() {
    union() {
        hook_body_positive();
        attachment_boss_positive();
    }
}

module insert_pocket_negative(pilot_d = insert_pilot_d) {
    translate([0, 0, boss_bottom_z - boolean_shim])
        cylinder(
            h = insert_length + insert_pilot_clearance + boolean_shim,
            d = pilot_d
        );
}

module m5_bore_negative() {
    translate([0, 0, boss_bottom_z + insert_length - boolean_shim])
        cylinder(
            h = boss_h - insert_length + 2 * boolean_shim,
            d = m5_clearance_d
        );
}

module revision_negative() {
    translate([
        -hook_outer_r + core_radial_t / 2,
        -hook_width_y / 2 + revision_depth,
        -hook_outer_r + core_radial_t / 2
    ])
        rotate([90, 0, 0])
            linear_extrude(height = revision_depth + boolean_shim)
                text(
                    revision_string,
                    size = revision_font,
                    halign = "center",
                    valign = "center"
                );
}

module hook_core_negative() {
    insert_pocket_negative();
    m5_bore_negative();
    revision_negative();
}

module hook_core() {
    difference() {
        hook_core_positive();
        hook_core_negative();
    }
}

module printable_hook_core() {
    translate([0, 0, hook_width_y / 2])
        rotate([90, 0, 0])
            hook_core();
}

module bar_fit_coupon_raw() {
    extrude_profile_y(bar_coupon_width_y)
        union() {
            lower_saddle_profile();
            open_nose_profile();
            intersection() {
                loaded_leg_profile();
                translate([-hook_outer_r, -hook_outer_r])
                    square([2 * hook_outer_r, hook_outer_r + 12]);
            }
        }
}

module bar_fit_coupon() {
    translate([0, 0, bar_coupon_width_y / 2])
        rotate([90, 0, 0])
            bar_fit_coupon_raw();
}

module insert_coupon_label(label) {
    translate([0, -insert_coupon_d / 2 + 3.2, insert_coupon_h - revision_depth])
        linear_extrude(height = revision_depth + boolean_shim)
            text(label, size = 3, halign = "center", valign = "center");
}

module insert_fit_coupon() {
    difference() {
        translate([-insert_coupon_w / 2, -insert_coupon_d / 2, 0])
            cube([insert_coupon_w, insert_coupon_d, insert_coupon_h]);

        for (i = [0:2]) {
            x = (i - 1) * insert_coupon_spacing;
            translate([x, 0, insert_coupon_h - insert_length])
                cylinder(
                    h = insert_length + boolean_shim,
                    d = insert_coupon_pilot_ds[i]
                );
            translate([x, 0, -boolean_shim])
                cylinder(
                    h = insert_coupon_h - insert_length + 2 * boolean_shim,
                    d = m5_clearance_d
                );
            translate([x, 0, 0])
                insert_coupon_label(str(insert_coupon_pilot_ds[i]));
        }
    }
}

module bar_preview() {
    color([0.12, 0.12, 0.14, 0.65])
        rotate([90, 0, 0])
            cylinder(h = hook_width_y + 30, d = bar_d, center = true);
}

module insert_preview() {
    color([0.75, 0.62, 0.18, 0.85])
        translate([0, 0, boss_bottom_z])
            cylinder(h = insert_length, d = insert_od);
}

module camjam_ring_preview() {
    color([0.55, 0.58, 0.62, 0.9])
        translate([0, 0, boss_top_z + camjam_ring_wire_d / 2])
            rotate_extrude()
                translate([
                    camjam_ring_id / 2 + camjam_ring_wire_d / 2,
                    0
                ])
                    circle(d = camjam_ring_wire_d);
}

module camjam_sweep_keepout() {
    color([1, 0.35, 0.1, 0.18])
        translate([0, 0, boss_top_z])
            intersection() {
                difference() {
                    cylinder(
                        h = camjam_sweep_h,
                        r = camjam_sweep_radius + camjam_sweep_body_r
                    );
                    translate([0, 0, -boolean_shim])
                        cylinder(
                            h = camjam_sweep_h + 2 * boolean_shim,
                            r = camjam_sweep_radius - camjam_sweep_body_r
                        );
                }
                translate([
                    -camjam_sweep_radius - camjam_sweep_body_r,
                    0,
                    -boolean_shim
                ])
                    cube([
                        2 * (camjam_sweep_radius + camjam_sweep_body_r),
                        camjam_sweep_radius + camjam_sweep_body_r,
                        camjam_sweep_h + 2 * boolean_shim
                    ]);
            }
}

module assembly() {
    color([0.2, 0.45, 0.75, 0.9]) hook_core();
    bar_preview();
    insert_preview();
    camjam_ring_preview();
    camjam_sweep_keepout();
}

if (set == "hook_core") {
    printable_hook_core();
} else if (set == "bar_fit_coupon") {
    bar_fit_coupon();
} else if (set == "insert_fit_coupon") {
    insert_fit_coupon();
} else if (set == "assembly") {
    assembly();
} else {
    assembly();
}
