# Plamp8 Corner Spine And Assembly Labels Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Join each north/south wall's two nut bosses into one continuous rounded corner spine and add raised, readable names to the three transparent assembly keepouts.

**Architecture:** Keep all geometry in the established `things/plamp8/plamp8.scad` model. Refactor the existing nut-tab subtraction into a reusable negative module, use it twice inside one full-height positive spine on nut-owner walls, and leave clearance-owner walls unchanged. Add one reusable illustration-label module called only by the transparent keepout modules.

**Tech Stack:** OpenSCAD, Python `unittest`, Bash CAD generator

## Global Constraints

- Preserve the 5 mm boss radius and shared M3 axis.
- Preserve both existing side-loaded nut traps, their offsets, shoulders, and retention detents.
- Keep the two M3x30 screw paths separate; the bore negatives must not join.
- Keep east/west clearance tabs as separate 6 mm-thick bosses.
- Use exact assembly label text: `RELAYS`, `DC/DC`, and `12V PSU`.
- Extrude labels from the component top faces in positive Z and render them opaque dark over the existing transparent keepouts.
- Keep labels out of all printable enclosure and component-footprint parts.
- Do not commit generated STL, PNG, or print artifacts.

---

### Task 1: Continuous North/South Corner Spine

**Files:**
- Modify: `tests/test_things_cad_scripts.py`
- Modify: `things/plamp8/plamp8.scad`

**Interfaces:**
- Consumes: `corner_tab_boss_positive(length, center_y)`, `top_nut_tab_center_y(h)`, `bottom_nut_tab_center_y()`, `corner_nut_tab(bearing_side)`.
- Produces: `corner_nut_tab_negatives(bearing_side)`, `corner_nut_spine(h)`, `corner_spine_y0()`, and `corner_spine_y1(h)`.

- [ ] **Step 1: Write the failing spine contract test**

Extend `test_plamp8_flat_wall_corner_stack_contract` with:

```python
self.assertIn("function corner_spine_y0()", source)
self.assertIn("function corner_spine_y1(h)", source)
self.assertIn("module corner_nut_tab_negatives", source)
self.assertIn("module corner_nut_spine(h)", source)
self.assertIn("corner_tab_boss_positive(spine_l, spine_y0 + spine_l / 2);", source)
self.assertEqual(source.count("corner_nut_tab_negatives("), 4)
self.assertIn("corner_nut_spine(h);", source)
```

Extract the `wall_corner_tabs` module and assert nut owners use the spine while clearance owners retain both separate tabs:

```python
wall_tabs = source.split("module wall_corner_tabs", 1)[1].split(
    "module flat_wall", 1
)[0]
self.assertIn("if (nut_owner)", wall_tabs)
self.assertIn("corner_nut_spine(h);", wall_tabs)
self.assertEqual(wall_tabs.count("corner_clearance_tab();"), 2)
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
python3 -m unittest tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_flat_wall_corner_stack_contract -v
```

Expected: FAIL because `corner_nut_spine` and its boundary functions do not exist.

- [ ] **Step 3: Extract reusable nut-tab negatives**

In `things/plamp8/plamp8.scad`, preserve `corner_nut_tab()` for the existing coupon but move its subtractive geometry into:

```scad
module corner_nut_tab_negatives(bearing_side = 1) {
    corner_nut_tab_length = corner_tab_t
        + corner_nut_retainer_t
        + corner_nut_tab_extension;
    corner_nut_tab_bore_center_y = -bearing_side
        * (corner_nut_retainer_t + corner_nut_tab_extension) / 2;
    nut_offset_y = bearing_side < 0 ? bottom_corner_nut_offset : 0;

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

module corner_nut_tab(bearing_side = 1) {
    difference() {
        corner_nut_tab_positive(bearing_side);
        corner_nut_tab_negatives(bearing_side);
    }
}
```

- [ ] **Step 4: Implement the continuous positive and apply both independent negatives**

Add the spine boundaries after the existing corner-center functions:

```scad
function corner_spine_y0() = bottom_nut_tab_center_y() - corner_tab_t / 2;
function corner_spine_y1(h) = top_nut_tab_center_y(h) + corner_tab_t / 2;
```

Add the full spine module:

```scad
module corner_nut_spine(h) {
    spine_y0 = corner_spine_y0();
    spine_l = corner_spine_y1(h) - spine_y0;

    difference() {
        corner_tab_boss_positive(spine_l, spine_y0 + spine_l / 2);
        translate([0, top_nut_tab_center_y(h), 0])
            corner_nut_tab_negatives(bearing_side = 1);
        translate([0, bottom_nut_tab_center_y(), 0])
            corner_nut_tab_negatives(bearing_side = -1);
    }
}
```

Refactor each end of `wall_corner_tabs()` so nut owners receive one spine and clearance owners retain two tabs:

```scad
if (nut_owner)
    translate([corner_axis_inset, 0, 0])
        corner_nut_spine(h);
else {
    translate([corner_axis_inset, top_clearance_tab_center_y(h), 0])
        corner_clearance_tab();
    translate([corner_axis_inset, bottom_clearance_tab_center_y(), 0])
        corner_clearance_tab();
}
```

- [ ] **Step 5: Run the focused and full CAD-script tests**

Run:

```bash
python3 -m unittest tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_flat_wall_corner_stack_contract -v
python3 -m unittest tests.test_things_cad_scripts -v
```

Expected: both commands report `OK` with zero failures.

- [ ] **Step 6: Commit the spine**

```bash
git add tests/test_things_cad_scripts.py things/plamp8/plamp8.scad
git commit -m "Join Plamp8 corner nut bosses"
```

---

### Task 2: Raised Assembly Illustration Labels

**Files:**
- Modify: `tests/test_things_cad_scripts.py`
- Modify: `things/plamp8/plamp8.scad`

**Interfaces:**
- Consumes: `psu_h`, `converter_h`, `relay_h`, and the three existing `*_keepout()` modules.
- Produces: `component_label_t`, `component_label_color`, and `raised_component_label(label, font_size, top_z, counter_rotation_z)`.

- [ ] **Step 1: Write the failing assembly-label contract test**

Add a separate test:

```python
def test_plamp8_transparent_components_have_raised_assembly_labels(self):
    source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()

    self.assertIn("component_label_t = 0.8;", source)
    self.assertIn("module raised_component_label", source)
    self.assertIn('raised_component_label("12V PSU"', source)
    self.assertIn('raised_component_label("DC/DC"', source)
    self.assertIn('raised_component_label("RELAYS"', source)
    self.assertIn("linear_extrude(height = component_label_t)", source)

    for module_name in ("psu_keepout", "converter_keepout", "relay_board_keepout"):
        keepout = source.split(f"module {module_name}", 1)[1].split("module ", 1)[0]
        self.assertIn("raised_component_label(", keepout)

    for module_name in ("psu_footprint", "converter_footprint", "relay_footprint"):
        footprint = source.split(f"module {module_name}", 1)[1].split("module ", 1)[0]
        self.assertNotIn("raised_component_label(", footprint)
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
python3 -m unittest tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_transparent_components_have_raised_assembly_labels -v
```

Expected: FAIL because `raised_component_label` does not exist.

- [ ] **Step 3: Add named illustration parameters and the reusable label module**

Place these parameters with the component dimensions:

```scad
component_label_t = 0.8;
component_label_color = [0.05, 0.05, 0.05, 1];
psu_label_font = 9;
converter_label_font = 5;
relay_label_font = 14;
```

Add this module immediately before the keepout modules:

```scad
module raised_component_label(label, font_size, top_z, counter_rotation_z) {
    color(component_label_color)
        translate([0, 0, top_z])
            rotate([0, 0, counter_rotation_z])
                linear_extrude(height = component_label_t)
                    text(label, size = font_size, halign = "center", valign = "center");
}
```

- [ ] **Step 4: Add labels only to contextual keepouts**

At the end of each keepout module, add:

```scad
// psu_keepout()
raised_component_label("12V PSU", psu_label_font, psu_h, -internal_psu_rot_z);

// converter_keepout()
raised_component_label("DC/DC", converter_label_font, converter_h, -internal_converter_rot_z);

// relay_board_keepout()
raised_component_label("RELAYS", relay_label_font, relay_h, -internal_relay_rot_z);
```

The counter-rotations cancel the component placement rotations so all three labels are horizontal in the assembly's top view.

- [ ] **Step 5: Run the focused and full CAD-script tests**

Run:

```bash
python3 -m unittest tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_transparent_components_have_raised_assembly_labels -v
python3 -m unittest tests.test_things_cad_scripts -v
```

Expected: both commands report `OK` with zero failures.

- [ ] **Step 6: Commit the labels**

```bash
git add tests/test_things_cad_scripts.py things/plamp8/plamp8.scad
git commit -m "Label Plamp8 assembly components"
```

---

### Task 3: Render And Inspect Affected Views

**Files:**
- Verify: `things/plamp8/plamp8.scad`
- Verify: the `plamp cad` interface and Plamp8 metadata
- Verify: `tests/test_things_cad_scripts.py`

**Interfaces:**
- Consumes: committed `north_wall`, `wall_corner_fastener_assembly`, and `assembly` views.
- Produces: disposable render evidence under `/tmp`; no repository artifacts.

- [ ] **Step 1: Run syntax and complete regression checks**

Run:

```bash
plamp cad validate plamp8 --json
plamp cad plan plamp8 --preset split-box --json
python3 -m unittest tests.test_things_cad_scripts -v
git diff --check
```

Expected: validation and planning exit 0, all tests report `OK`, and `git diff --check` prints nothing.

- [ ] **Step 2: Render the nut-owner wall**

Run from the repository root:

```bash
plamp cad generate plamp8 --view north_wall --revision HEAD --output /tmp/plamp8-north-spine
```

Expected: one non-empty `plamp8_north_wall_<revision>.stl`; the log has no empty top-level object, missing include, or manifold warning.

- [ ] **Step 3: Render the corner fastener assembly**

Run from the repository root:

```bash
plamp cad generate plamp8 --view wall_corner_fastener_assembly --revision HEAD --output /tmp/plamp8-corner-spine
```

Expected: one non-empty `plamp8_wall_corner_fastener_assembly_<revision>.stl` and no empty-object or missing-include warnings. This compatibility view verifies the preserved individual joint negatives and captured nuts.

- [ ] **Step 4: Render the labeled assembly**

Run from the repository root:

```bash
plamp cad generate plamp8 --view assembly --revision HEAD --output /tmp/plamp8-labeled-assembly
```

Expected: one non-empty `plamp8_assembly_<revision>.stl` and no empty-object or missing-include warnings.

- [ ] **Step 5: Inspect rendered geometry**

Open or snapshot the north-wall and assembly outputs. Confirm:

- The north/south nut-owner corner is a continuous rounded solid from the bottom joint zone through the former 6.4 mm gap to the top joint zone.
- The central section between the opposed bores remains solid.
- Both nut entries remain open toward the enclosure interior.
- East/west clearance tabs remain two distinct bosses in the assembly.
- `RELAYS`, `DC/DC`, and `12V PSU` are centered, raised above their keepout top faces, and horizontal/readable from above.

- [ ] **Step 6: Record final repository state**

Run:

```bash
git status --short --branch
git log --oneline -4
```

Expected: the branch is clean, generated files exist only under `/tmp`, and the log includes the design, spine, and label commits.

---

### Task 4: Apply Assembly-Illustration Review Feedback

**Files:**
- Modify: `tests/test_things_cad_scripts.py`
- Modify: `things/plamp8/plamp8.scad`

**Interfaces:**
- Consumes: the three component keepout modules and `internal_components(...)`.
- Produces: independent `show_dc_dc` visibility, inherited keepout color/transparency for all raised labels, and a 90-degree counter-clockwise assembled orientation for `12V PSU`.

- [ ] **Step 1: Write failing source-contract assertions**

Extend the assembly-controls test with `show_dc_dc = true;`, `if (show_dc_dc)`, and `internal_components(show_psu, show_dc_dc, show_relay);`. Update the label test to reject `component_label_color`, verify the label module contains no `color(` call, verify each label call is inside its keepout's transparent `color()` block, and require the PSU call to use a local rotation of `0` while converter and relay retain their negative placement counter-rotations.

- [ ] **Step 2: Run the two focused tests and verify RED**

```bash
python3 -m unittest \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_assembly_has_individual_wall_controls_and_height \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_transparent_components_have_raised_assembly_labels -v
```

Expected: FAIL because `show_dc_dc` is absent and labels still apply an independent color.

- [ ] **Step 3: Implement the visibility and illustration refinements**

Add `show_dc_dc = true;`, change `internal_components` to accept three booleans, guard the converter with `show_dc_dc`, and pass all three controls from `assembly()`. Remove `component_label_color` and the `color()` wrapper from `raised_component_label`. Expand each keepout's existing transparent color into a block containing both its cube and label. Call the PSU label with local rotation `0`; keep converter and relay calls counter-rotated by their placement angles.

- [ ] **Step 4: Run focused and full tests, then commit and push**

```bash
python3 -m unittest \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_assembly_has_individual_wall_controls_and_height \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_transparent_components_have_raised_assembly_labels -v
python3 -m unittest tests.test_things_cad_scripts -v
git diff --check
git add tests/test_things_cad_scripts.py things/plamp8/plamp8.scad \
  docs/superpowers/specs/2026-07-18-plamp8-flat-wall-enclosure-design.md \
  docs/superpowers/plans/2026-07-19-plamp8-corner-spine-labels.md
git commit -m "Refine Plamp8 assembly labels"
git push origin feature/plamp8-flat-walls
```

Expected: all tests pass, the commit succeeds, and the remote branch advances.

---

### Task 5: Refine East-Wall Revision And Stiffening

**Files:**
- Modify: `tests/test_things_cad_scripts.py`
- Modify: `things/plamp8/plamp8.scad`

**Interfaces:**
- Consumes: `wall_revision_negative(...)`, `wall_stiffening_ribs(...)`, and the existing full-vent safety margins.
- Produces: an east-wall revision position above the vent field and a centerline vertical rib for `vent_mode == "full"`.

- [ ] **Step 1: Write failing assertions**

Require a named `wall_revision_top_margin = 10;`, a full-vent `revision_y` of `h - wall_revision_top_margin`, and `length / 2` in the full-vent `rib_xs` array.

- [ ] **Step 2: Run the east-wall contract test and verify RED**

```bash
python3 -m unittest tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_has_four_flat_printed_mitred_wall_views -v
```

Expected: FAIL because the top-margin parameter and center rib are absent.

- [ ] **Step 3: Implement, verify, commit, and push**

Add the named margin with the wall parameters. Derive `revision_y` from `vent_mode`, use it in `wall_revision_negative`, and add `length / 2` to the `full` rib positions. Run the focused and full CAD tests plus `git diff --check`, then commit as `Refine Plamp8 east wall` and push the feature branch.
