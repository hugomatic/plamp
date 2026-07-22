# Plamp8 Simplified Corners Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove unnecessary angled wall-tab geometry and the top locator collision while retaining rectangular corner tabs, captured nuts, straight bottom locators, and the existing M3 stack.

**Architecture:** Keep the existing shared `flat_wall()` model and its four assembly transforms. Simplify the shared corner primitives so every printable and assembly view receives the same change: tabs become rectangular columns, wall-to-wall locating exists only at the bottom, and the remaining key/notch pair is straight and clearance-controlled.

**Tech Stack:** OpenSCAD 2021.01, Python `unittest`, and the direct `plamp cad` CLI.

## Global Constraints

- Each wall exterior remains flat on the FDM build plate at Z=0.
- Keep the M3 screw axis, 4 mm stack layer, 0.8 mm axial retention, captured-nut pocket, and 30-degree nut-entry detents unchanged.
- Integrate the 0.8 mm retaining wall into one asymmetric 4.8 mm nut-tab block; remove the separate face-touching `corner_nut_axial_retainer()` solid.
- Remove `corner_tab_gusset()` and `clearance_tab_inward_gusset()`; do not replace them with another angled feature.
- Remove the top wall-to-wall locator key and matching notch because their former assembled Z=-19 through -3 mm interval intersects the ledge ring and sub-panel.
- Keep a straight bottom wall-to-wall locator key and clearance notch without an angled lead-in.
- Keep floor locator keys and lands unchanged; they are separate from the wall-to-wall locator.
- Remove the circular `floor_corner_lands()` that extend into the wall skins; keep the inner rectangular floor and its corner fastener holes.
- Preserve all ordered manufacturing view names and directory-specific Git revision behavior.

---

### Task 1: Rectangular Corner Tabs

**Files:**
- Modify: `tests/test_things_cad_scripts.py`
- Modify: `things/plamp8/plamp8.scad`

**Interfaces:**
- Consumes: `corner_tab_outer_x`, `corner_tab_effective_w`, `corner_tab_t`, `corner_tab_h`, `corner_nut_retainer_t`, `support_free_horizontal_bore()`, and `support_free_m3_nut_trap()`.
- Produces: `corner_tab_positive()`, `corner_nut_tab_positive()`, and `corner_clearance_tab()` containing rectangular tab bodies with no gusset or face-touching retainer modules.

- [ ] **Step 1: Write the failing rectangular-tab contract**

Add these assertions to `test_plamp8_flat_wall_corner_stack_contract()`:

```python
self.assertNotIn("module corner_tab_gusset", source)
self.assertNotIn("module clearance_tab_inward_gusset", source)
self.assertNotIn("module corner_nut_axial_retainer", source)
self.assertNotIn("corner_tab_root_l", source)
self.assertIn("module corner_tab_positive", source)
self.assertIn("module corner_nut_tab_positive", source)
self.assertIn("module corner_clearance_tab", source)
self.assertIn("corner_tab_t + corner_nut_retainer_t", source)
```

Remove assertions that require `corner_tab_gusset`, `clearance_tab_inward_gusset`, `bottom_wall_joint_inner_y`, or `top_wall_joint_inner_y` if present; those joint-bound helpers exist only to bound the removed gussets.

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
UV_CACHE_DIR=/tmp/uv-cache /home/hugo/.local/bin/uv run python -m unittest \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_flat_wall_corner_stack_contract -v
```

Expected: FAIL because the two gusset modules, separate axial-retainer module, and `corner_tab_root_l` still exist.

- [ ] **Step 3: Remove the angled tab geometry**

Delete `corner_tab_root_l`, `corner_tab_gusset()`, and `clearance_tab_inward_gusset()`. Reduce the two positive tab modules to rectangular bodies:

```scad
module corner_tab_positive() {
    translate([corner_tab_outer_x, -corner_tab_t / 2, 0])
        cube([corner_tab_effective_w, corner_tab_t, corner_tab_h]);
}

module corner_nut_tab_positive(bearing_side = 1) {
    y0 = -corner_tab_t / 2
        - (bearing_side > 0 ? corner_nut_retainer_t : 0);

    translate([corner_tab_outer_x, y0, 0])
        cube([
            corner_tab_effective_w,
            corner_tab_t + corner_nut_retainer_t,
            corner_tab_h
        ]);
}

module corner_clearance_tab() {
    difference() {
        corner_tab_positive();
        support_free_horizontal_bore(corner_tab_t + 0.2, corner_screw_d);
    }
}
```

Change `corner_nut_tab()` to call `corner_nut_tab_positive(bearing_side)` and delete `corner_nut_axial_retainer()`. Remove `root_direction` from `corner_nut_tab()`, `wall_corner_tabs()`, and `corner_wall_coupon()`. Delete `bottom_wall_joint_inner_y()` and `top_wall_joint_inner_y()`, then bound wall vents directly outside the tab bands:

```scad
joint_min_y = bottom_nut_tab_center_y() + corner_tab_t / 2;
joint_max_y = top_nut_tab_center_y(h) - corner_tab_t / 2;
```

Use the same `joint_min_y` and `joint_max_y` expressions in `wall_stiffening_ribs()`.

- [ ] **Step 4: Run the focused test and verify GREEN**

Run the command from Step 2.

Expected: one test PASS.

- [ ] **Step 5: Commit the rectangular-tab change**

```bash
git add tests/test_things_cad_scripts.py things/plamp8/plamp8.scad
git commit -m "Simplify Plamp8 corner tabs"
```

---

### Task 2: Bottom-Only Straight Wall Locators

**Files:**
- Modify: `tests/test_things_cad_scripts.py`
- Modify: `things/plamp8/plamp8.scad`

**Interfaces:**
- Consumes: `locator_key_w`, `locator_key_l`, `locator_key_h`, `locator_clearance`, and `wall_end_feature()`.
- Produces: `bottom_corner_locator_key()`, `bottom_corner_locator_notch()`, `wall_bottom_locator_keys()`, and `wall_bottom_locator_notches()`.

- [ ] **Step 1: Write the failing bottom-locator contract**

Add these assertions to `test_plamp8_has_four_flat_printed_mitred_wall_views()`:

```python
self.assertIn("module bottom_corner_locator_key", source)
self.assertIn("module bottom_corner_locator_notch", source)
self.assertIn("module wall_bottom_locator_keys", source)
self.assertIn("module wall_bottom_locator_notches", source)
self.assertNotIn("module corner_locator_key", source)
self.assertNotIn("module corner_locator_notch", source)
self.assertNotIn("module wall_locator_keys", source)
self.assertNotIn("module wall_locator_notches", source)

notch = source.split("module bottom_corner_locator_notch", 1)[1].split(
    "module ", 1
)[0]
self.assertNotIn("hull()", notch)

coupon = source.split("module corner_wall_coupon", 1)[1].split(
    "module ", 1
)[0]
self.assertIn("if (!nut_owner && !top)", coupon)
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
UV_CACHE_DIR=/tmp/uv-cache /home/hugo/.local/bin/uv run python -m unittest \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_has_four_flat_printed_mitred_wall_views -v
```

Expected: FAIL because the old top-and-bottom locator modules and angled notch lead-in still exist.

- [ ] **Step 3: Implement the straight bottom locator primitives**

Replace `corner_locator_key()` and `corner_locator_notch()` with:

```scad
module bottom_corner_locator_key() {
    translate([wall_t, wall_t, wall_t])
        cube([locator_key_w, locator_key_l, locator_key_h]);
}

module bottom_corner_locator_notch() {
    shim = 0.01;

    translate([
        wall_t - locator_clearance,
        wall_t - locator_clearance,
        wall_t - shim
    ])
        cube([
            locator_key_w + 2 * locator_clearance,
            locator_key_l + 2 * locator_clearance,
            locator_key_h + locator_clearance + 2 * shim
        ]);
}
```

Replace the wall locator wrappers with bottom-only versions:

```scad
module wall_bottom_locator_keys(length) {
    for (right = [false, true])
        wall_end_feature(right = right, length = length)
            bottom_corner_locator_key();
}

module wall_bottom_locator_notches(length) {
    for (right = [false, true])
        wall_end_feature(right = right, length = length)
            bottom_corner_locator_notch();
}
```

Update `flat_wall()` to call these new wrappers. In `corner_wall_coupon()`, include the locator only for the bottom clearance-wall coupon:

```scad
if (!nut_owner && !top)
    bottom_corner_locator_key();
if (nut_owner && !top)
    bottom_corner_locator_notch();
```

- [ ] **Step 4: Run the focused test and verify GREEN**

Run the command from Step 2.

Expected: one test PASS.

- [ ] **Step 5: Commit the bottom-only locator change**

```bash
git add tests/test_things_cad_scripts.py things/plamp8/plamp8.scad
git commit -m "Remove Plamp8 top wall locators"
```

---

### Task 3: CAD Verification And Branch Push

**Files:**
- Verify: `things/plamp8/plamp8.scad`
- Verify: the `plamp cad` interface and Plamp8 metadata
- Verify: `tests/test_things_cad_scripts.py`

**Interfaces:**
- Consumes: the simplified shared wall and locator modules from Tasks 1 and 2.
- Produces: reproducible source commits on `feature/plamp8-flat-walls`; generated artifacts remain ignored.

- [ ] **Step 1: Run the complete CAD-script suite and static checks**

```bash
UV_CACHE_DIR=/tmp/uv-cache /home/hugo/.local/bin/uv run python -m unittest tests.test_things_cad_scripts -v
plamp cad validate plamp8 --json
plamp cad plan plamp8 --preset split-box --json
git diff --check
```

Expected: 12 tests PASS; CAD validation, planning, and diff checks exit zero.

- [ ] **Step 2: Render the affected dirty-worktree views through the generator**

From the repository root, use separate new target directories:

```bash
plamp cad generate plamp8 --revision simplified-corners --preview --view north_wall \
  --output prints/plamp8_north_wall_simplified
plamp cad generate plamp8 --revision simplified-corners --preview --view east_wall \
  --output prints/plamp8_east_wall_simplified
plamp cad generate plamp8 --revision simplified-corners --preview --view corner_coupon \
  --output prints/plamp8_corner_coupon_simplified
plamp cad generate plamp8 --revision simplified-corners --preview --view assembly \
  --output prints/plamp8_assembly_simplified
```

Expected: each requested STL exists and is non-empty; wall and coupon logs report `Simple: yes`; no empty-object or missing-geometry warning occurs. The assembly is a multi-part visualization and is not required to report one manifold volume.

- [ ] **Step 3: Inspect the simplified geometry**

Confirm in OpenSCAD or the generated meshes:

- no angled tab gusset remains;
- east and west have no wall-to-wall locator above assembled Z=-19 mm;
- the ring interval Z=-16 through -13 mm and sub-panel interval Z=-13 through -3 mm contain no wall locator solid;
- each bottom clearance wall retains two straight locator keys;
- each bottom nut-owner wall retains two matching straight notches;
- the captured nut pocket, integrated 0.8 mm axial retaining wall, and detents remain present.
- the floor has no circular corner lands extending beyond its inner rectangular outline.

- [ ] **Step 4: Run final verification from the committed source**

```bash
UV_CACHE_DIR=/tmp/uv-cache /home/hugo/.local/bin/uv run python -m unittest discover -s tests -v
plamp cad validate plamp8 --json
plamp cad plan plamp8 --preset split-box --json
git diff --check
git status --short
```

Expected: all repository tests PASS; checks exit zero; only intentionally ignored generated print directories are absent from `git status`.

- [ ] **Step 5: Push the branch**

```bash
git push origin feature/plamp8-flat-walls
```

Expected: Git reports the latest Task 2 commit on the remote feature branch.
