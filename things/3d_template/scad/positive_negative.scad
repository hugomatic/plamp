render_fn = 64;
$fn = render_fn;
set = "__PLAMP_PART__"; // [__PLAMP_PART__, assembly]

part_w = 70;
part_d = 130;
part_h = 12;
boolean_overlap = 0.1;

module __PLAMP_PART___positive() {
    cube([part_w, part_d, part_h], center = true);
}

module __PLAMP_PART___negative() {
    echo("BOM", "M3x16 screw", 1);
    cylinder(d = 3.4, h = part_h + 2 * boolean_overlap, center = true);
}

module __PLAMP_PART__() {
    difference() {
        __PLAMP_PART___positive();
        __PLAMP_PART___negative();
    }
}

if (set == "__PLAMP_PART__") {
    __PLAMP_PART__();
} else if (set == "assembly") {
    __PLAMP_PART__();
}
