# Plamp8 Support-Free Wall Details Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 45-degree center-facing nut entries, support-free box fasteners and ribs, permanent floor and sub-panel-back placement labels, and a preview-only panel separation.

**Architecture:** Existing wall, corner-tab, rib-placement, and floor modules remain authoritative. An explicit `print_orientation` parameter selects box-only fastener/rib geometry; standalone fasteners retain current defaults except for the 45-degree entry, while standalone ribs become smooth semicylinders. `box()` passes the box orientation and does not duplicate geometry loops.

**Tech Stack:** OpenSCAD, Python `unittest` source-contract tests, Bash CAD generator, Git.

## Global Constraints

- Standalone wall print-up is wall-local +Z; box print-up is wall-local +Y/global +Z.
- Roof facets must rise at least 30 degrees above horizontal.
- All eight nut entries point 45 degrees toward the assembled box center.
- Standalone nut pockets and screw bores retain their existing support-free geometry.
- Standalone ribs are smooth semicylinders; box ribs reuse a clipped `$fn = 6` cylinder as a true regular half-hex profile.
- Box screw bores are round and vertical.
- Push every checkpoint before running OpenSCAD.
- Never render the full assembly or commit generated artifacts.
- Defer the fifth top-panel-to-sub-panel screw near Pump/Fan/Nutrients.

---

### Task 1: Print-Aware Corner Fasteners

**Files:**
- Modify: `things/plamp8/plamp8.scad:1510-1690,1850-1975,2250-2275`
- Test: `tests/test_things_cad_scripts.py:52-150,244-335`

**Interfaces:**
- Consumes: existing `support_free_horizontal_bore()`, nut-pocket/detent modules, `wall_end_feature()` mirroring, and wall/context modules.
- Produces: named flat/box orientations, `corner_screw_bore()`, a separated 45-degree nut-entry cutter, and box roof helpers.

- [ ] **Step 1: Write a failing contract test**

Add:

~~~python
def test_plamp8_corner_fasteners_follow_print_orientation(self):
    source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
    self.assertIn('flat_wall_print_orientation = "flat_wall";', source)
    self.assertIn('box_print_orientation = "box";', source)
    self.assertIn("corner_nut_entry_angle = 45;", source)
    self.assertIn("module corner_screw_bore(", source)
    self.assertIn("module corner_nut_entry_negative(", source)
    self.assertIn("rotate([0, corner_nut_entry_angle, 0])", source)
    self.assertIn("print_orientation == box_print_orientation", source)

    box_module = source.split("module box()", 1)[1].split(
        "module assembly()", 1
    )[0]
    self.assertEqual(
        box_module.count("print_orientation = box_print_orientation"), 4
    )
~~~

Update exact wall signature assertions to include `print_orientation = flat_wall_print_orientation`.

- [ ] **Step 2: Run the single test and verify red**

Run:

~~~bash
/home/hugo/.openclaw/workspace/code/plamp/.venv/bin/python -m unittest tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_corner_fasteners_follow_print_orientation -v
~~~

Expected: FAIL because the constants and modules do not exist.

- [ ] **Step 3: Add constants and a print-aware bore**

Add near wall dimensions:

~~~scad
flat_wall_print_orientation = "flat_wall";
box_print_orientation = "box";
corner_nut_entry_angle = 45;
support_free_roof_angle = 30;
boolean_shim = 0.01;
~~~

Keep the existing bore as the flat default and add:

~~~scad
module round_horizontal_bore(length, d, axis_z) {
    translate([0, 0, axis_z])
        rotate([90, 0, 0])
            cylinder(h = length, d = d, center = true);
}

module corner_screw_bore(
    length,
    d,
    print_orientation = flat_wall_print_orientation,
    axis_z = wall_t + panel_screw_inset
) {
    if (print_orientation == box_print_orientation)
        round_horizontal_bore(length, d, axis_z);
    else
        support_free_horizontal_bore(length, d, axis_z);
}
~~~

Replace direct corner-tab bore calls with `corner_screw_bore()` and pass orientation through clearance tabs, nut negatives, nut spines, wall corner tabs, flat walls, walls, and contexts.

- [ ] **Step 4: Separate the entry from the unchanged standalone pocket**

Extract the rectangular entry and retention throat/detents into `corner_nut_entry_negative()`. Rotate that entry around wall-local Y:

~~~scad
rotate([0, corner_nut_entry_angle, 0])
    corner_nut_entry_negative(
        bearing_side,
        pocket_center_y,
        print_orientation
    );
~~~

Do not rotate or reshape the existing standalone point-up hex nut pocket. The existing left/right mirror reverses the X component so both ends point inward after assembly.

- [ ] **Step 5: Add the box pocket and entry roofs**

For box orientation only, replace the pocket cutter with a rectangular M3 nut envelope plus a gable roof in local +Y. Use two facets rising 30 degrees above horizontal. Add the same local-Y roof to the horizontal 45-degree entry tunnel. Keep pocket centers, bearing-side offsets, nut clearances, and detents unchanged.

The roof helper must extend cutters by `boolean_shim` at seams and compute:

~~~scad
roof_h = roof_half_span * tan(support_free_roof_angle);
~~~

- [ ] **Step 6: Propagate orientation and make box explicit**

Default every wall/context signature to `flat_wall_print_orientation`. In `box()`, pass:

~~~scad
print_orientation = box_print_orientation
~~~

to all four wall contexts. Standalone dispatch remains argument-free.

- [ ] **Step 7: Verify, commit, and push**

~~~bash
/home/hugo/.openclaw/workspace/code/plamp/.venv/bin/python -m unittest tests.test_things_cad_scripts -v
git diff --check
git add things/plamp8/plamp8.scad tests/test_things_cad_scripts.py
git commit -m "Make Plamp8 corner fasteners print-aware"
git push origin feature/plamp8-support-free
~~~

Expected: all tests PASS and GitHub advances before OpenSCAD runs.

---

### Task 2: Smooth Standalone Ribs and Faceted Box Ribs

**Files:**
- Modify: `things/plamp8/plamp8.scad:1765-1845`
- Test: `tests/test_things_cad_scripts.py:190-245,297-345`

**Interfaces:**
- Consumes: Task 1 orientation propagation and existing rib positions/ranges.
- Produces: smooth semicylinder and reusable low-`$fn` half-hex rib helpers.

- [ ] **Step 1: Add a failing rib profile test**

~~~python
def test_plamp8_ribs_select_profiles_by_print_orientation(self):
    source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
    self.assertIn("module smooth_half_rib_profile", source)
    self.assertIn("module low_fn_half_hex_rib", source)
    self.assertIn("$fn = 6", source)
    self.assertIn("module floor_supported_box_rib", source)
    ribs = source.split("module wall_stiffening_ribs", 1)[1].split(
        "module ", 1
    )[0]
    self.assertIn("print_orientation", ribs)
    self.assertEqual(source.count("for (x = rib_xs)"), 1)
~~~

Run the single test. Expected: FAIL.

- [ ] **Step 2: Implement the standalone smooth profile**

~~~scad
module smooth_half_rib_profile(width, projection) {
    intersection() {
        scale([width / 2, projection])
            circle(r = 1, $fn = render_fn);
        translate([-width / 2, 0])
            square([width, projection]);
    }
}
~~~

Extrude this profile along existing local-X/local-Y rib lengths with its flat diameter on the wall face.

- [ ] **Step 3: Implement the box low-facet profile**

Clip a six-sided cylinder at its diameter so OpenSCAD supplies the regular point-up half-hex proportions directly:

~~~scad
module low_fn_half_hex_rib(length, width = wall_rib_w) {
    intersection() {
        cylinder(h = length, r = width / 2, $fn = 6);
        translate([-width / 2, 0, 0])
            cube([width, width / 2 + boolean_shim, length]);
    }
}
~~~

Use this profile for both horizontal and vertical box ribs. Extend each vertical rib from the floor-supported horizontal rib, through the upper horizontal rib, to `h + sub_panel_bottom_z`. This eliminates the unsupported start and its ramp while adding direct support under the sub-panel perimeter.

- [ ] **Step 4: Reuse the existing placement loops**

Add orientation to `wall_stiffening_ribs()` and select only the primitive/profile inside the existing vertical loop and transverse/floor placements. Do not duplicate `rib_xs` or vent-clearance calculations.

- [ ] **Step 5: Verify, commit, and push**

~~~bash
/home/hugo/.openclaw/workspace/code/plamp/.venv/bin/python -m unittest tests.test_things_cad_scripts -v
git diff --check
git add things/plamp8/plamp8.scad tests/test_things_cad_scripts.py
git commit -m "Make Plamp8 wall ribs support-free"
git push origin feature/plamp8-support-free
~~~

---

### Task 3: Floor and Sub-Panel Placement Labels and Preview Polish

**Files:**
- Modify: `things/plamp8/plamp8.scad:210-225,870-930,1015-1065,2145-2165`
- Test: `tests/test_things_cad_scripts.py:345-455`

**Interfaces:**
- Consumes: component centers, compass engraving depth, transparent keepouts, `mounted_top_panel()`.
- Produces: engraved floor labels, mirrored sub-panel back wiring labels, and a 0.01 mm preview-only panel gap.

- [ ] **Step 1: Add failing label and preview tests**

~~~python
def test_plamp8_floor_marks_component_orientation(self):
    source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
    labels = source.split("module floor_component_label_negatives", 1)[1].split(
        "module ", 1
    )[0]
    self.assertIn('"Pico Relay-B"', labels)
    self.assertIn('"PSU"', labels)
    self.assertIn('"DC/DC"', labels)
    self.assertIn("floor_component_label_negatives();", source)
    self.assertNotIn('raised_component_label("RELAYS"', source)
    self.assertNotIn('raised_component_label("12V PSU"', source)

def test_plamp8_preview_separates_panels_only_in_preview(self):
    source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
    self.assertIn("assembly_preview_gap = $preview ? 0.01 : 0;", source)
    mounted = source.split("module mounted_top_panel", 1)[1].split(
        "module ", 1
    )[0]
    self.assertIn("-plate_t + assembly_preview_gap", mounted)

def test_plamp8_sub_panel_back_labels_match_wiring_layout(self):
    source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
    labels = source.split("module sub_panel_back_labels_negative", 1)[1].split(
        "module ", 1
    )[0]
    for label in ("CH1", "CH2", "CH3", "CH4", "CH5", "CH6", "CH7", "CH8", "AC", "USB"):
        self.assertIn(f'"{label}"', labels)
    self.assertIn("mirror([1, 0, 0])", source)
    self.assertIn("sub_panel_back_labels_negative();", source)
~~~

Run both tests. Expected: FAIL.

- [ ] **Step 2: Add floor engravings**

Add a shared negative label module using `assembly_name_depth`. Place labels at existing component centers, offset only if needed to avoid posts/holes:

~~~scad
floor_component_label_negative("Pico Relay-B", relay_center, 90, 9);
floor_component_label_negative("PSU", psu_center, 0, 9);
floor_component_label_negative("DC/DC", converter_center, 180, 5);
~~~

Call `floor_component_label_negatives()` in `floor_context()`'s subtraction beside compass names. Remove the raised label calls from transparent keepouts without changing colors or solids.

- [ ] **Step 3: Add mirrored sub-panel back wiring labels**

Add a negative underside-text helper that starts just below local Z = 0, cuts to the existing 0.6 mm marking depth, and mirrors X so it reads normally from below. Place labels in back-view order:

~~~text
DC: CH1 CH2    (CH2 nearest AC input)
    CH3 CH4    (CH4 nearest AC input)

AC: CH5 CH6    (CH6 below USB)
    CH7 CH8    (CH8 below USB)
~~~

Add `AC` at the C13 input and `USB` at the USB connector. Use existing `dc_channel_x/y()`, `left_ac_x`, `right_ac_x`, outlet spacing, `c13_panel_x`, `service_row_y`, and `usb_c_panel_x/y`; do not duplicate layout dimensions. Call `sub_panel_back_labels_negative()` inside `sub_panel_8ch_negative()`.

- [ ] **Step 4: Add the low-priority preview-only gap**

~~~scad
assembly_preview_gap = $preview ? 0.01 : 0;

module mounted_top_panel() {
    translate([0, 0, -plate_t + assembly_preview_gap])
        top_panel_8ch(true);
}
~~~

Do not change `label_pocket()`; its cutter already penetrates the panel by 0.5 mm.

- [ ] **Step 5: Verify, commit, and push**

~~~bash
/home/hugo/.openclaw/workspace/code/plamp/.venv/bin/python -m unittest tests.test_things_cad_scripts -v
git diff --check
git add things/plamp8/plamp8.scad tests/test_things_cad_scripts.py
git commit -m "Add Plamp8 placement markings"
git push origin feature/plamp8-support-free
~~~

---

### Task 4: Render and Verify Pushed Geometry

**Files:**
- Verify: `things/plamp8/plamp8.scad`
- Generate outside repository under `/tmp/` using the pushed short commit in each directory name.

**Interfaces:**
- Consumes: clean, pushed Tasks 1-3 and `things/plamp8/generate.bash`.
- Produces: verification evidence only.

- [ ] **Step 1: Verify clean pushed source**

~~~bash
/home/hugo/.openclaw/workspace/code/plamp/.venv/bin/python -m unittest tests.test_things_cad_scripts -v
git diff --check
git status --short
git rev-parse HEAD
git rev-parse origin/feature/plamp8-support-free
~~~

Expected: tests PASS, status is empty, and hashes match.

- [ ] **Step 2: Render committed previews**

From `things/plamp8`:

~~~bash
support_commit=$(git rev-parse --short HEAD)
./generate.bash --preview --view north_wall "/tmp/plamp8-wall-${support_commit}" "${support_commit}"
./generate.bash --preview --view floor "/tmp/plamp8-floor-${support_commit}" "${support_commit}"
./generate.bash --preview --view box "/tmp/plamp8-box-preview-${support_commit}" "${support_commit}"
~~~

Expected: non-empty simple objects and no warnings. Stop and diagnose before production rendering on any failure.

- [ ] **Step 3: Render production wall and box only**

~~~bash
support_commit=$(git rev-parse --short HEAD)
./generate.bash --view north_wall "/tmp/plamp8-wall-final-${support_commit}" "${support_commit}"
./generate.bash --view box "/tmp/plamp8-box-final-${support_commit}" "${support_commit}"
~~~

Do not render `assembly`.

- [ ] **Step 4: Verify logs and meshes**

Require non-empty STLs, no warning/error lines, `Simple: yes`, and `Volumes: 2`. Run the existing ASCII-STL edge-incidence check and require zero bad edges and one connected component.

- [ ] **Step 5: Report**

Report the pushed commit/link, passing test count, output paths, OpenSCAD results, topology results, and confirmation that the full assembly was not rendered.
