# Plamp8 Ledge-Ring Removal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the redundant ledge ring, clamp the sub-panel directly to equal-thickness wall tabs with flush M3x25 engagement at both ends, retain enclosed M3x30 compatibility, and move the east-wall center rib into a clear vent-grid gap.

**Architecture:** Preserve the top/sub-panel datum and make the sub-panel the top structural plane. Shift the complete top wall-tab stack upward by the removed 3 mm ring thickness, express both fastener paths with explicit stack equations, and remove every ring-specific source/view/control. Compute the east center rib from the vent grid instead of the wall midpoint.

**Tech Stack:** OpenSCAD, Python 3.11 `unittest`, Bash `things/plamp8/generate.bash`, Git

## Global Constraints

- Keep the top surface at Z=0, top panel at Z=-3..0, and sub-panel at Z=-13..-3 mm.
- Remove the ledge ring as a part, view, Customizer control, feature control, geometry dependency, coupon surrogate, and assembly step.
- Move only the top wall tabs upward 3 mm; do not move bottom tabs, floor geometry, panel holes, wall height, or component geometry.
- Keep `corner_tab_t = 6` for both intersecting walls at every top and bottom screw.
- Use M3x25 as the named screw at all eight corners, ending flush with the far face of each nut.
- Keep M3x30 usable with its additional 5 mm enclosed inside existing corner material.
- Preserve the side-loaded nut pockets, two retention detents, full bores, 16 mm extensions, and continuous north/south spine.
- Keep the existing no-new-test exception limited to the already-pushed component-fit parameter changes; update CAD contract tests for ring removal and rib non-interference.
- Move the east-wall center rib to the vent-grid gap at X=105 mm without moving vents or other ribs.
- Commit and push every source checkpoint before invoking OpenSCAD.
- Do not start the long assembly render automatically; let the user inspect pushed source first.
- Do not commit generated STL artifacts.

---

### Task 1: Remove the ledge ring and make both M3x25 paths flush

**Files:**
- Modify: `tests/test_things_cad_scripts.py`
- Modify: `things/plamp8/plamp8.scad`

**Interfaces:**
- Consumes: existing top/sub-panel geometry, `corner_tab_t`, `corner_nut_tab_extension`, `corner_nut_retainer_t`, top/bottom tab functions, coupon modules, and assembly view.
- Produces: `sub_panel_bottom_z`, `corner_long_screw_length`, direct-bearing top tabs, explicit 25 mm top/bottom stack equations, and a ring-free view/assembly contract.

- [ ] **Step 1: Replace the obsolete ring contract with a failing direct-bearing contract**

In `tests/test_things_cad_scripts.py`, replace `test_plamp8_ledge_ring_is_separate_and_preserves_panel_stack` with:

```python
    def test_plamp8_sub_panel_replaces_ledge_ring_and_corner_screws_fill_nuts(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
        view_line = next(
            line for line in source.splitlines() if line.startswith("view =")
        )

        self.assertNotIn("ledge_ring", source)
        self.assertNotIn("ledge_top_z", source)
        self.assertNotIn("ph_ledge", source)
        self.assertNotIn("top_ledge", source)
        self.assertNotIn("ledge_ring", view_line)
        self.assertIn("sub_panel_bottom_z = -(plate_t + sub_panel_h);", source)
        self.assertIn("corner_screw_length = 25;", source)
        self.assertIn("corner_long_screw_length = 30;", source)
        self.assertIn(
            "top_stack_h = plate_t + sub_panel_h + 2 * corner_tab_t;",
            source,
        )
        self.assertIn(
            "bottom_stack_h = wall_t + 2 * corner_tab_t;",
            source,
        )
        self.assertIn(
            "bottom_corner_nut_offset = corner_screw_length - bottom_stack_h;",
            source,
        )
        self.assertIn("assert(top_stack_h == corner_screw_length", source)
        self.assertIn(
            "assert(bottom_stack_h + bottom_corner_nut_offset == corner_screw_length",
            source,
        )
        self.assertIn("assert(corner_long_screw_length <= top_long_screw_enclosure_h", source)
        self.assertIn("assert(corner_long_screw_length <= bottom_long_screw_enclosure_h", source)
        self.assertNotIn("corner_screw_tip_allowance", source)
        self.assertIn(
            "h + sub_panel_bottom_z - corner_tab_t / 2;",
            source,
        )

        coupon = source.split("module corner_coupon()", 1)[1].split(
            "module panel_corner_fastener_test", 1
        )[0]
        self.assertIn("corner_coupon_plate(plate_t, 1);", coupon)
        self.assertIn("corner_coupon_plate(sub_panel_h);", coupon)
        self.assertIn("corner_coupon_plate(wall_t, -1);", coupon)
```

In `test_plamp8_flat_wall_corner_stack_contract`, replace the old screw/stack assertions with:

```python
        self.assertIn("corner_screw_length = 25;", source)
        self.assertIn("corner_long_screw_length = 30;", source)
        self.assertIn(
            "top_stack_h = plate_t + sub_panel_h + 2 * corner_tab_t;",
            source,
        )
        self.assertIn("bottom_stack_h = wall_t + 2 * corner_tab_t;", source)
        self.assertIn("bottom_corner_nut_offset", source)
```

Remove its assertions for `ledge_ring_t = 3`, `corner_screw_length = 30`, the retainer-inclusive `top_stack_h`, and the retainer-inclusive `bottom_stack_h`.

In `test_plamp8_assembly_has_individual_wall_controls_and_height`, remove `"show_ledge_ring"` from the expected control tuple and replace its `ledge_top_z` assertion with:

```python
        self.assertIn(
            "assert(sub_panel_bottom_z == -(plate_t + sub_panel_h)", source
        )
```

- [ ] **Step 2: Run the focused contract and confirm the intended failure**

Run:

```bash
.venv/bin/python -m unittest tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_sub_panel_replaces_ledge_ring_and_corner_screws_fill_nuts -v
```

Expected: `FAIL` because `ledge_ring` still exists in the SCAD source.

- [ ] **Step 3: Replace ring-derived dimensions with direct panel and screw contracts**

In `things/plamp8/plamp8.scad`:

1. Remove `ledge_ring` from the ordered `view` comment.
2. Delete `show_ledge_ring`, `feature_ph_ledge_holes`, `ledge_ring_t`, `ledge_ring_north_rail_w`, `ledge_ring_north_clearance_min`, `ledge_w`, `ledge_r`, `ph_ledge_gap_clearance`, and `ph_ledge_gap_w`.
3. Change the screw declarations to:

```scad
corner_screw_length = 25;
corner_long_screw_length = 30;
```

4. Preserve the current vent position with:

```scad
vent_top_margin = 15;
```

5. Replace the stack calculations and assertions with:

```scad
top_stack_h = plate_t + sub_panel_h + 2 * corner_tab_t;
bottom_stack_h = wall_t + 2 * corner_tab_t;
bottom_corner_nut_offset = corner_screw_length - bottom_stack_h;
top_long_screw_enclosure_h =
    top_stack_h + corner_nut_retainer_t + corner_nut_tab_extension;
bottom_long_screw_enclosure_h =
    bottom_stack_h + corner_nut_retainer_t + corner_nut_tab_extension;

assert(top_stack_h == corner_screw_length,
    "top M3x25 must end flush with the captured nut");
assert(bottom_stack_h + bottom_corner_nut_offset == corner_screw_length,
    "bottom M3x25 must end flush with the captured nut");
assert(bottom_corner_nut_offset >= 0,
    "bottom corner nut offset must not be negative");
assert(corner_long_screw_length <= top_long_screw_enclosure_h,
    "top corner must enclose an M3x30 substitute");
assert(corner_long_screw_length <= bottom_long_screw_enclosure_h,
    "bottom corner must enclose an M3x30 substitute");
```

Delete `corner_screw_tip_allowance` and its old bottom-offset assertion.

6. Replace the hardware echoes with:

```scad
echo(str("top M3x25 nut-face offset: ", corner_screw_length - top_stack_h, " mm"));
echo(str("bottom M3x25 nut-face offset: ",
    corner_screw_length - bottom_stack_h - bottom_corner_nut_offset, " mm"));
echo(str("M3x30 extra enclosed travel: ",
    corner_long_screw_length - corner_screw_length, " mm"));
```

- [ ] **Step 4: Rename the datum and move only the top tabs upward**

Replace:

```scad
ledge_top_z = -(plate_t + sub_panel_h);
```

with:

```scad
sub_panel_bottom_z = -(plate_t + sub_panel_h);
```

Replace every non-ring use of `ledge_top_z` with `sub_panel_bottom_z`, including panel-fastener bosses, coupon plate placement, panel-fastener test geometry, and `mounted_sub_panel`.

Replace the top-tab function with:

```scad
function top_clearance_tab_center_y(h) =
    h + sub_panel_bottom_z - corner_tab_t / 2;
```

Replace the datum assertion with:

```scad
assert(sub_panel_bottom_z == -(plate_t + sub_panel_h),
    "sub-panel bottom datum must stay fixed below the top panel");
```

Do not change `bottom_clearance_tab_center_y`, `bottom_nut_tab_center_y`, floor translations, or `wall_z_height`.

- [ ] **Step 5: Delete all ring-only functions and modules**

Delete these complete definitions from `things/plamp8/plamp8.scad`:

```text
top_ledge_gap_center_for_dc_toggle
top_ledge_gap_start
top_ledge_gap_end
ledge_ring_north_clearance
ledge_ring_corner_holes
ledge_ring_ph_switch_clearances
ledge_ring_revision_negative
ledge_ring_frame
ledge_ring_local
ledge_ring_context
ledge_ring
```

Also delete the ring-clearance assertion and echo beside the `top_ledge_*` functions.

From `assembly()`, delete:

```scad
    if (show_ledge_ring)
        ledge_ring_context();
```

From the top-level view dispatcher, delete:

```scad
} else if (view == "ledge_ring") {
    ledge_ring();
```

- [ ] **Step 6: Remove the ring surrogate from both coupon presentations**

In `wall_corner_fastener_assembly`, retain the top-panel and sub-panel surrogates:

```scad
        translate(top_origin + [0, 0, -plate_t])
            corner_coupon_plate(plate_t, 1);
        translate(top_origin + [0, 0, sub_panel_bottom_z])
            corner_coupon_plate(sub_panel_h);
```

Delete the translated `corner_coupon_plate(ledge_ring_t)` call.

In `corner_coupon`, retain:

```scad
    translate([coupon_plate_column_x, 12, 0])
        corner_coupon_plate(plate_t, 1);
    translate([coupon_plate_column_x, 34, 0])
        corner_coupon_plate(sub_panel_h);
    translate([coupon_plate_column_x + 22, 12, 0])
        corner_coupon_plate(wall_t, -1);
```

Delete the `corner_coupon_plate(ledge_ring_t)` surrogate.

- [ ] **Step 7: Run focused and complete CAD contracts**

Run:

```bash
.venv/bin/python -m unittest tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_sub_panel_replaces_ledge_ring_and_corner_screws_fill_nuts -v
.venv/bin/python -m unittest tests.test_things_cad_scripts -v
git diff --check
```

Expected: the focused test passes, all CAD-script tests pass, and `git diff --check` is silent.

- [ ] **Step 8: Commit and push the ring-removal checkpoint before OpenSCAD**

```bash
git add tests/test_things_cad_scripts.py things/plamp8/plamp8.scad
git commit -m "Remove Plamp8 ledge ring"
git push origin feature/plamp8-flat-walls
```

Expected: the remote feature branch advances. Do not run OpenSCAD yet.

---

### Task 2: Align the east center rib to the vent grid

**Files:**
- Modify: `tests/test_things_cad_scripts.py`
- Modify: `things/plamp8/plamp8.scad`

**Interfaces:**
- Consumes: `vent_wall_margin = 10`, `vent_hole_spacing = 10`, `vent_hole_d = 5`, `wall_rib_w = 3`, and the full-vent `rib_xs` branch.
- Produces: `vent_gap_center_left_of(x)`, `full_vent_center_rib_x(length)`, and a 105 mm east center-rib position with 1 mm clearance from both neighboring holes.

- [ ] **Step 1: Add the failing vent-grid rib contract**

Add this method immediately after the four-wall view contract in `tests/test_things_cad_scripts.py`:

```python
    def test_plamp8_east_center_rib_sits_between_vent_columns(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()

        self.assertIn("function vent_gap_center_left_of(x)", source)
        self.assertIn("function full_vent_center_rib_x(length)", source)
        self.assertIn("full_vent_center_rib_x(length)", source)
        self.assertIn("east_center_rib_x = full_vent_center_rib_x(box_d);", source)
        self.assertIn("assert(east_center_rib_x == 105", source)
        self.assertIn("vent_rib_edge_clearance =", source)
        self.assertIn("assert(vent_rib_edge_clearance >= 1", source)
```

In `test_plamp8_has_four_flat_printed_mitred_wall_views`, replace the old full-vent rib-list assertion containing `length / 2` with:

```python
        self.assertIn(
            "? [vent_wall_margin + vent_hole_spacing / 2, full_vent_center_rib_x(length), length - 21]",
            source,
        )
```

- [ ] **Step 2: Run the focused test and confirm the intended failure**

Run:

```bash
.venv/bin/python -m unittest tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_east_center_rib_sits_between_vent_columns -v
```

Expected: `FAIL` because `vent_gap_center_left_of` is absent.

- [ ] **Step 3: Derive the center rib from the vent grid**

Immediately before `wall_stiffening_ribs`, add:

```scad
function vent_gap_center_left_of(x) =
    vent_wall_margin
    + (floor((x - vent_wall_margin) / vent_hole_spacing) - 0.5)
        * vent_hole_spacing;

function full_vent_center_rib_x(length) =
    vent_gap_center_left_of(length / 2);

east_center_rib_x = full_vent_center_rib_x(box_d);
vent_rib_edge_clearance =
    vent_hole_spacing / 2 - vent_hole_d / 2 - wall_rib_w / 2;
assert(east_center_rib_x == 105,
    "east center rib must remain in the approved vent-grid gap");
assert(vent_rib_edge_clearance >= 1,
    "east wall ribs need at least 1 mm edge clearance from vents");
```

Change only the full-vent `rib_xs` entry:

```scad
    rib_xs = vent_mode == "half"
        ? [length / 4, length / 2 + vent_hole_spacing / 2]
        : (vent_mode == "full"
            ? [vent_wall_margin + vent_hole_spacing / 2, full_vent_center_rib_x(length), length - 21]
            : [length / 3, 2 * length / 3]);
```

- [ ] **Step 4: Run focused and complete CAD contracts**

Run:

```bash
.venv/bin/python -m unittest tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_east_center_rib_sits_between_vent_columns -v
.venv/bin/python -m unittest tests.test_things_cad_scripts -v
git diff --check
```

Expected: the focused test passes, all CAD-script tests pass, and `git diff --check` is silent.

- [ ] **Step 5: Commit and push the rib checkpoint before OpenSCAD**

```bash
git add tests/test_things_cad_scripts.py things/plamp8/plamp8.scad
git commit -m "Align Plamp8 east wall rib"
git push origin feature/plamp8-flat-walls
```

Expected: the remote feature branch advances. Both implementation checkpoints are now available for user inspection before rendering.

- [ ] **Step 6: Render only the focused views after the push**

Run from `things/plamp8`:

```bash
ringless_preview_root="$(mktemp -d)"
ringless_revision="$(git rev-parse --short HEAD)"
./generate.bash --view corner_coupon "$ringless_preview_root/corner"
./generate.bash --view east_wall "$ringless_preview_root/east"
test -s "$ringless_preview_root/corner/plamp8_corner_coupon_${ringless_revision}.stl"
test -s "$ringless_preview_root/east/plamp8_east_wall_${ringless_revision}.stl"
! rg -n "WARNING|ERROR|empty top level object" "$ringless_preview_root"/*/readme.md
```

Expected: both focused STLs are non-empty and logs contain no warning, error, or empty-object match. Do not start the full assembly render unless the user requests it.

- [ ] **Step 7: Report the pushed source for visual approval**

```bash
git status --short
git log -2 --oneline
```

Expected: the worktree is clean. Report both source commits and wait for visual approval before proposing a `main` fast-forward.
