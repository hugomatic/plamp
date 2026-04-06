view = "assembly"; // [assembly, tripod, camera_clip, plate]

letter_size = 7;
revision_string = "1234567";


//
// Frame where mounting holes are on the frame (not in the opening)
//

$fn = 64;

// ==========================
// PARAMETERS
// ==========================

// Inner opening (must be SMALLER than hole spacing)
inner_w = 70;   // < 75
inner_h = 120;  // < 126

// Frame thickness
frame_margin = 15;
frame_thickness = 6; // 6;
screw_thickness = 2; // 3;
corner_radius = 6;

// Hole pattern (official portrait)
hole_d = 3.5;
hole_x = 35.355; // 37.5;
hole_y = 70; // 63.0;

// position of the tripod mount
elevator_y = 30;

tripod_thick = 20;
tripod_screw_thick = 2;

// ==========================
// DERIVED
// ==========================

outer_w = inner_w + 2 * frame_margin;
outer_h = inner_h + 2 * frame_margin;

// ==========================
// HELPERS
// ==========================

module rounded_rect_2d(w, h, r) {
    hull() {
        for (x = [-1,1], y = [-1,1])
            translate([x*(w/2 - r), y*(h/2 - r)])
                circle(r);
    }
}

module rounded_rect(w, h, r, t) {
    linear_extrude(height = t)
        rounded_rect_2d(w, h, r);
}

// ==========================
// MODULES
// ==========================

module frame_positive() {
    rounded_rect(outer_w, outer_h, corner_radius, frame_thickness);
}

module frame_negative() {
    union() {
        // inner window
        translate([0,0,-0.1])
            rounded_rect(
                inner_w,
                inner_h,
                max(0.01, corner_radius - 2),
                frame_thickness + 0.2
            );

        // mounting holes
        for (x = [-hole_x, hole_x], y = [-hole_y, hole_y]) {
            translate([x, y, -0.1]) {
                cylinder(d = hole_d, h = frame_thickness + 0.2);
                translate([0,0, 0 + screw_thickness])
                    cylinder(d = hole_d * 2, h = frame_thickness + 0.2);
            }
        }
    }

    translate([0, 68, frame_thickness])
    write_text(revision_string);
    
    // connectors
    con_dx = frame_margin *2;
    con_dy = 60; 
    con_dz = frame_thickness * 2;
    con_x = -(inner_w + con_dx + frame_thickness ) /2 ;
    con_y = -10;
    con_z = 2;
    translate([con_x, con_y, con_z]) cube([con_dx, con_dy, con_dz]);

}

module frame() {
    difference() {
        frame_positive();
        frame_negative();
    }
}

// ==========================
// OUTPUT
// ==========================
module camera_clip(){
    
    echo("camera clip");
    
    clip_x = 0;
    clip_y = 0;
    clip_z = 0;
    
    clip_thick = 6;
    clip_gap_s = 1;
    clip_gap_c = 1;
    
    dz = 20; 
    dy = 20;
    
    // we can cover this much
    screen_z = 12;
    
    cable_w = 16;
    
    clip_base_dxyz = [clip_thick, dy, dz];
    clip_screen_dxyz = [clip_thick, dy, dz - screen_z];
    clip_cable_dxyz = [clip_thick, dy - cable_w, dz];
    
    translate([clip_x, clip_y, clip_z]) cube(clip_base_dxyz);
    translate([clip_x + clip_thick, clip_y, clip_z]) cube(clip_screen_dxyz); 
    
    translate([clip_x + clip_thick + clip_gap_s, clip_y, clip_z]) cube(clip_base_dxyz);
    translate([clip_x + clip_thick * 2 + clip_gap_s, clip_y, clip_z]) cube(clip_cable_dxyz);    
    
    translate([clip_x + clip_thick * 2 + clip_gap_s + clip_gap_c, clip_y, clip_z]) cube(clip_base_dxyz);
    
    translate([clip_thick/2 + clip_gap_s + clip_gap_c + clip_thick * 2 , dy +1, 0]) cylinder(d=  1.25 * clip_thick, h = dz);

}




module tripod() {
    cube_x = 40;
    translate([0,0,0]) {
        difference() {
            translate([-cube_x/2,-10, 0]) cube([cube_x, 25, tripod_thick]);
            translate([0, 0, -1]) cylinder(h = tripod_thick +1, d = 7);
            translate([0, 0, tripod_screw_thick]) cylinder(h = tripod_thick + 1, d = 14, $fn = 6);
        }
        translate([0, 0, elevator_y/2 -10])
        translate([(-cube_x )/2,  15 - frame_thickness, 10]) cube([cube_x , frame_thickness, elevator_y ]);
    }
    

    
}

module instrument_hook() {

    thick = 10;
   
    dy1 = 20;
   
    t2 = 1.25;
    gap = 3;
   
    // red
    dz1 = thick;
    dx1 = 5;
   
    // blue
    dx3 = t2;
    dy3 = 60.8;
   
    // orange
    dy4 = 1;
   
    // pink
    dx5 = t2;
    dy5 = 20;
   
    dx4 = dx3 + dx5 + gap;
   
     // mm per inch
    i = 25.4;
   
   
   
    x1 = 0;
    y1 = 0;
    z1 = 0;
    color("red") translate([x1, y1, z1]) cube([dx1, dy1, dz1]);
   
    thick2 = 5;
    x2 = x1;
    y2 = -thick2;
    z2 = z1;
    dx2 = dx1 + i +dx3;
    dy2 = 5;
    dz2 = dz1;
    color("green") translate([x2, y2, z2])cube([dx2, dy2, dz2]);
   
    x3 = dx2  - dx3;
    y3 = y1;
    z3 = z2;
    dz3 = dz2;
    color("blue") translate([x3, y3, z3])cube([dx3, dy3, dz3]);
   
    x4 = x3;
    y4 = dy3;
    z4 = z3;
    dz4 = dz3;
    color("orange") translate([x4, y4, z4])cube([dx4, dy4, dz4]);
   
    x5 = x4 + dx4 - dx5;
    y5 = dy3 - dy5;
    z5 = z1;
    dz5 = dz4;
    color("pink") translate([x5, y5, z5])cube([dx5, dy5, dz5]);
    echo("x", x5);
    echo("y", y5);
    echo("z", z5);
    echo("dx",dx5);
    echo("dy",dy5);
    echo("dz",dz5);    
   
}

module write_text(string) {
    z0 = - 0.25;
    dz= 0.5;
    translate([0, 0, z0]) {
        rotate([0,0,0]) {
            linear_extrude(dz) {
                font = "DejaVu Sans";
                text(string, size = letter_size, font = font,
                     halign = "center", valign = "center", $fn = 64);
            }
        }
    }
}

module rpi_holder () {
   translate([0, -85 -elevator_y, 15])rotate([-90,0,0]) tripod();
   frame();
    
}

echo(["view", view]); 


if (view == "tripod") {
  tripod();
}

if (view == "camera_clip") {
  // flat("part");
  camera_clip();  
}


if (view == "assembly" || view == "plate") {
   echo("assmenbly view"); 
   
   rpi_holder();
   camera_clip();
   translate([-5, -25, 0]) instrument_hook();
}


