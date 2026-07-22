render_fn = 64;
$fn = render_fn;
view = "__PLAMP_PART__"; // [__PLAMP_PART__, assembly]

/* generate.json
{
  "default_preset": "all-views-default",
  "views": {
    "__PLAMP_PART__": {"description": "Printable part"},
    "assembly": {"description": "Initial complete assembly"}
  },
  "presets": {
    "all-views-default": {
      "description": "Generate the part and initial assembly",
      "items": ["view:__PLAMP_PART__", "view:assembly"]
    }
  }
}
*/

part_w = 40;
part_d = 30;
part_h = 4;
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

if (view == "__PLAMP_PART__") {
    __PLAMP_PART__();
} else if (view == "assembly") {
    __PLAMP_PART__();
}
