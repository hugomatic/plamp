# Plamp8 Fused Box View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a floor-down `box` manufacturing view that fuses the existing Plamp8 walls and floor while using optional point-up hexagonal vents.

**Architecture:** Thread one `coarse_vents` boolean through the existing wall context, wall, and vent-negative modules; all defaults preserve the standalone walls. Add `box()` as an explicit union of the existing four wall contexts and `floor_context()`, passing only `box_coarse_vents` and leaving every fastener, locator, rib, label, and floor feature unchanged.

**Tech Stack:** OpenSCAD, Python `unittest` source-contract tests, Bash CAD generator, Git

## Global Constraints

- `box` is a deterministic, floor-down manufacturing view containing only the four walls and floor.
- `box_coarse_vents = true` by default; true means regular `$fn = 6` openings with one vertex pointing upward, and false means the current round openings.
- Standalone wall views always remain round.
- Keep the complete top and bottom corner fastener stacks, M3x25/M3x30 behavior, floor screw holes, locator lands, locator keys, and wall notches unchanged.
- Do not duplicate a wall module, floor module, vent loop, or structural geometry path.
- Push each source checkpoint before running OpenSCAD.
- Render only `box`; do not render the full assembly.
- Do not commit generated STL or render-log artifacts.

---

## File Structure

- Modify `things/plamp8/plamp8.scad`: add the Customizer checkbox, shared vent-profile parameter, and `box` view.
- Modify `tests/test_things_cad_scripts.py`: enforce the point-up hex profile, parameter routing, unchanged standalone defaults, and structural reuse in `box`.
- No production file is created; the existing single-file Plamp8 CAD structure remains authoritative.

### Task 1: Add the Shared Point-Up Hex Vent Path

**Files:**
- Modify: `tests/test_things_cad_scripts.py:167-265`
- Modify: `things/plamp8/plamp8.scad:9-24, 1731-1944`

**Interfaces:**
- Consumes: existing `render_fn`, `vent_hole_d`, `wall_t`, `wall_rib_h`, `wall_vent_negatives()`, `flat_wall()`, wall modules, and wall context modules.
- Produces: `box_coarse_vents: bool`, `wall_vent_negative(x, y, coarse_vents = false)`, and a `coarse_vents = false` parameter threaded through every wall layer.

- [ ] **Step 1: Write the failing vent-profile contract and update signature expectations**

Add this test to `ThingsCadScriptsTest`:

```python
def test_plamp8_box_coarse_vents_are_point_up_hexagons(self):
    source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()

    self.assertIn("box_coarse_vents = true;", source)
    vent_negative = source.split("module wall_vent_negative", 1)[1].split(
        "module ", 1
    )[0]
    self.assertIn("rotate([0, 0, coarse_vents ? 30 : 0])", vent_negative)
    self.assertIn("$fn = coarse_vents ? 6 : render_fn", vent_negative)

    vent_grid = source.split("module wall_vent_negatives", 1)[1].split(
        "module ", 1
    )[0]
    self.assertIn("coarse_vents = false", vent_grid)
    self.assertIn("wall_vent_negative(x, y, coarse_vents);", vent_grid)
    self.assertEqual(source.count("for (x = vent_xs, y = vent_ys)"), 1)

    for wall in ("north", "south", "west", "east"):
        self.assertIn(f"module {wall}_wall(coarse_vents = false)", source)
        self.assertIn(
            f"module {wall}_wall_context(coarse_vents = false)", source
        )
```

In `test_plamp8_has_four_flat_printed_mitred_wall_views`, replace the two no-argument module assertions with:

```python
self.assertIn(f"module {name}_context(coarse_vents = false)", source)
self.assertIn(f"module {name}(coarse_vents = false)", source)
```

In `test_plamp8_walls_have_full_compass_name_engravings`, replace the wall and context extraction/call assertions with:

```python
wall_module = source.split(
    f"module {wall}_wall(coarse_vents = false)", 1
)[1].split("module ", 1)[0]
self.assertIn(f'wall_name = "{wall.upper()}"', wall_module)

context_module = source.split(
    f"module {wall}_wall_context(coarse_vents = false)", 1
)[1].split("module ", 1)[0]
self.assertIn(
    f"{wall}_wall(coarse_vents = coarse_vents);", context_module
)
```

- [ ] **Step 2: Run the focused tests and verify they fail for missing coarse vents**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_box_coarse_vents_are_point_up_hexagons \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_has_four_flat_printed_mitred_wall_views \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_walls_have_full_compass_name_engravings \
  -v
```

Expected: FAIL because `box_coarse_vents`, `wall_vent_negative`, and the parameterized wall signatures do not exist.

- [ ] **Step 3: Add the checkbox and shared vent negative**

After the assembly view options in `things/plamp8/plamp8.scad`, add:

```scad
/* [box view options] */

// Use point-up hexagonal vents when printing the fused box floor-down.
box_coarse_vents = true;
```

Replace `wall_vent_negatives()` with these two modules, preserving the existing grid limits and joint-clearance checks exactly:

```scad
module wall_vent_negative(x, y, coarse_vents = false) {
    translate([x, y, -0.1])
        rotate([0, 0, coarse_vents ? 30 : 0])
            cylinder(
                h = wall_t + wall_rib_h + 0.2,
                d = vent_hole_d,
                $fn = coarse_vents ? 6 : render_fn
            );
}

module wall_vent_negatives(
    length,
    vent_mode = "none",
    h = wall_z_height,
    coarse_vents = false
) {
    vent_ys = [
        vent_floor_clearance:
        vent_hole_spacing:
        h - vent_top_margin - vent_top_clearance
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
                wall_vent_negative(x, y, coarse_vents);
}
```

The 30-degree rotation puts one of the six vertices at positive wall-local Y. Every assembly context maps positive wall-local Y upward, so the hexagon is point-up in the floor-down box.

- [ ] **Step 4: Thread the parameter through the shared wall modules**

Change `flat_wall()` to:

```scad
module flat_wall(
    length,
    wall_name = "",
    nut_owner = false,
    vent_mode = "none",
    h = wall_z_height,
    coarse_vents = false
) {
    difference() {
        union() {
            wall_body_positive(length, h);
            wall_corner_tabs(length, h, nut_owner);
            wall_stiffening_ribs(length, h, vent_mode);
        }
        floor_locator_notches(length);
        wall_vent_negatives(length, vent_mode, h, coarse_vents);
        wall_revision_negative(length, h, vent_mode);
        wall_assembly_name_negative(length, wall_name);
    }
}
```

Change all four context modules to accept and forward the defaulted parameter while leaving their matrices and colors unchanged:

```scad
module south_wall_context(coarse_vents = false) {
    color([0.15, 0.45, 0.9, 1])
        multmatrix([
            [1, 0, 0, 0],
            [0, 0, 1, 0],
            [0, 1, 0, -box_h],
            [0, 0, 0, 1]
        ])
            south_wall(coarse_vents = coarse_vents);
}

module north_wall_context(coarse_vents = false) {
    color([0.15, 0.45, 0.9, 1])
        multmatrix([
            [1, 0, 0, 0],
            [0, 0, -1, box_d],
            [0, 1, 0, -box_h],
            [0, 0, 0, 1]
        ])
            north_wall(coarse_vents = coarse_vents);
}

module west_wall_context(coarse_vents = false) {
    color([0.2, 0.75, 0.35, 1])
        multmatrix([
            [0, 0, 1, 0],
            [-1, 0, 0, box_d],
            [0, 1, 0, -box_h],
            [0, 0, 0, 1]
        ])
            west_wall(coarse_vents = coarse_vents);
}

module east_wall_context(coarse_vents = false) {
    color([0.2, 0.75, 0.35, 1])
        multmatrix([
            [0, 0, -1, box_w],
            [1, 0, 0, 0],
            [0, 1, 0, -box_h],
            [0, 0, 0, 1]
        ])
            east_wall(coarse_vents = coarse_vents);
}
```

Change the four wall modules to:

```scad
module north_wall(coarse_vents = false) {
    flat_wall(
        box_w,
        wall_name = "NORTH",
        nut_owner = true,
        vent_mode = "half",
        coarse_vents = coarse_vents
    );
}

module south_wall(coarse_vents = false) {
    flat_wall(
        box_w,
        wall_name = "SOUTH",
        nut_owner = true,
        vent_mode = "half",
        coarse_vents = coarse_vents
    );
}

module west_wall(coarse_vents = false) {
    flat_wall(
        box_d,
        wall_name = "WEST",
        nut_owner = false,
        vent_mode = "none",
        coarse_vents = coarse_vents
    );
}

module east_wall(coarse_vents = false) {
    flat_wall(
        box_d,
        wall_name = "EAST",
        nut_owner = false,
        vent_mode = "full",
        coarse_vents = coarse_vents
    );
}
```

- [ ] **Step 5: Run the focused and full CAD contract suites**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_box_coarse_vents_are_point_up_hexagons \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_has_four_flat_printed_mitred_wall_views \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_walls_have_full_compass_name_engravings \
  -v
.venv/bin/python -m unittest tests.test_things_cad_scripts -v
git diff --check
```

Expected: all 17 tests PASS and `git diff --check` exits 0.

- [ ] **Step 6: Commit and push the vent checkpoint**

```bash
git add tests/test_things_cad_scripts.py things/plamp8/plamp8.scad
git commit -m "Add support-free Plamp8 box vents"
git push
```

Expected: the feature branch advances on GitHub before any OpenSCAD render.

### Task 2: Add the Minimal Fused Box View

**Files:**
- Modify: `tests/test_things_cad_scripts.py:167-345`
- Modify: `things/plamp8/plamp8.scad:5, 2209-2270`

**Interfaces:**
- Consumes: `box_coarse_vents`, the four parameterized wall context modules from Task 1, unchanged `floor_context()`, and unchanged complete corner/locator geometry.
- Produces: `box()` and the `view == "box"` dispatch path.

- [ ] **Step 1: Write the failing box-reuse contract**

Add this test to `ThingsCadScriptsTest`:

```python
def test_plamp8_box_view_reuses_complete_wall_and_floor_geometry(self):
    source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
    view_line = next(
        line for line in source.splitlines() if line.startswith("view =")
    )

    self.assertIn("box", view_line)
    self.assertIn('view == "box"', source)
    box_module = source.split("module box()", 1)[1].split(
        "module assembly()", 1
    )[0]

    for wall in ("north", "south", "west", "east"):
        self.assertIn(
            f"{wall}_wall_context(coarse_vents = box_coarse_vents);",
            box_module,
        )
    self.assertIn("floor_context();", box_module)
    self.assertIn("union()", box_module)
    self.assertNotIn("flat_wall(", box_module)
    self.assertNotIn("wall_corner_tabs(", box_module)
    self.assertNotIn("floor_locator_", box_module)
    self.assertNotIn("floor_corner_fastener_holes", box_module)

    self.assertIn("corner_nut_spine(h);", source)
    self.assertIn("floor_corner_fastener_holes();", source)
    self.assertIn("floor_locator_lands();", source)
    self.assertIn("floor_locator_keys();", source)
    self.assertIn("floor_locator_notches(length);", source)
```

- [ ] **Step 2: Run the focused test and verify it fails for the missing view**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_box_view_reuses_complete_wall_and_floor_geometry \
  -v
```

Expected: FAIL because `box` is absent from the view list and dispatcher.

- [ ] **Step 3: Add `box` to the view contract and compose existing geometry**

Add `box` immediately after `east_wall` in the ordered view comment:

```scad
view = "assembly"; // [relay_footprint, psu_footprint, converter_footprint, floor, north_wall, south_wall, west_wall, east_wall, box, top_panel, sub_panel, plate, ac_duplex_channel, dc_barrel_channel, usb_c_panel, c13_inlet, panel_corner_fastener_test, corner_coupon, wall_corner_fastener_assembly, assembly]
```

Immediately before `assembly()`, add:

```scad
module box() {
    echo_hardware(true, true, true, true);
    union() {
        north_wall_context(coarse_vents = box_coarse_vents);
        south_wall_context(coarse_vents = box_coarse_vents);
        west_wall_context(coarse_vents = box_coarse_vents);
        east_wall_context(coarse_vents = box_coarse_vents);
        floor_context();
    }
}
```

Add the dispatcher branch immediately after `east_wall`:

```scad
} else if (view == "box") {
    box();
```

Do not add structural flags or alternate wall/floor modules. The exact existing floor fasteners, wall fasteners, nut catches, spines, locator keys, and locator notches remain in the union.

- [ ] **Step 4: Run focused and full verification**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_box_view_reuses_complete_wall_and_floor_geometry \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_box_coarse_vents_are_point_up_hexagons \
  -v
.venv/bin/python -m unittest tests.test_things_cad_scripts -v
git diff --check
```

Expected: all 18 tests PASS and `git diff --check` exits 0.

- [ ] **Step 5: Commit and push the box checkpoint before OpenSCAD**

```bash
git add tests/test_things_cad_scripts.py things/plamp8/plamp8.scad
git commit -m "Add fused Plamp8 box view"
git push
```

Expected: GitHub contains the exact source commit that will be rendered.

### Task 3: Verify the Committed Box Geometry

**Files:**
- Verify: `things/plamp8/plamp8.scad`
- Generated outside the repository: `/tmp/plamp8-box-${plamp8_box_commit}/plamp8_box_${plamp8_box_commit}.stl`

**Interfaces:**
- Consumes: the clean, pushed Task 2 commit and `things/plamp8/generate.bash`.
- Produces: verification evidence only; no tracked artifacts.

- [ ] **Step 1: Re-run tests and confirm the render source is clean and pushed**

Run:

```bash
.venv/bin/python -m unittest tests.test_things_cad_scripts -v
git diff --check
git status --short
git rev-parse --short HEAD
git rev-parse HEAD
git rev-parse origin/feature/plamp8-box
```

Expected: 19 tests PASS; diff/status output is empty; local and remote full hashes match.

- [ ] **Step 2: Render only the committed default coarse-vent box**

From `things/plamp8`, run with the literal hash from Step 1:

```bash
plamp8_box_commit=$(git rev-parse --short HEAD)
./generate.bash --view box "/tmp/plamp8-box-${plamp8_box_commit}" "${plamp8_box_commit}"
```

Expected: OpenSCAD exits 0 and reports a non-empty top-level 3D object. Do not run `assembly`.

- [ ] **Step 3: Verify the STL, warnings, simplicity, and connectivity**

Run:

```bash
plamp8_box_commit=$(git rev-parse --short HEAD)
test -s "/tmp/plamp8-box-${plamp8_box_commit}/plamp8_box_${plamp8_box_commit}.stl"
! rg -n "WARNING:|ERROR:|Current top level object is empty" \
  "/tmp/plamp8-box-${plamp8_box_commit}/readme.md"
rg -n "Simple:[[:space:]]+yes" "/tmp/plamp8-box-${plamp8_box_commit}/readme.md"
rg -n "Volumes:[[:space:]]+2" "/tmp/plamp8-box-${plamp8_box_commit}/readme.md"
```

Expected: the STL is non-empty; no warning/error match; the log reports `Simple: yes` and `Volumes: 2`. OpenSCAD's Nef-polyhedron report counts the exterior volume plus the single bounded solid, so `Volumes: 2` is the normal result for one connected printable part.

- [ ] **Step 4: Report the review checkpoint**

Report the pushed commit, 19/19 passing CAD tests, exact STL path, OpenSCAD simplicity/connectivity result, and that the full assembly was not rendered. If `Simple` is not `yes`, warnings appear, or `Volumes` is not 2, stop and diagnose the existing mating faces before proposing any geometry change.
