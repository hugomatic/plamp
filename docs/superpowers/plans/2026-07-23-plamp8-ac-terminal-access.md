# Plamp8 AC Terminal Access Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose all five terminal screws on each Plamp8 AC socket through three edge-relative extensions to the existing sub-panel socket opening.

**Architecture:** Keep the top-panel socket geometry and existing 35 x 70 mm sub-panel opening unchanged. Encapsulate the main sub-panel opening and its three access extensions in one parametric `sub_panel_socket_negative()` module, then reuse it at the two existing AC socket centers so the complete sub-panel and production-crop coupon remain identical.

**Tech Stack:** OpenSCAD, Python `unittest` source-contract tests, and the Plamp CAD CLI.

## Global Constraints

- Preserve both AC socket centers and the existing centered 35 x 70 mm main sub-panel openings.
- Add one 5 x 10 mm outward extension at the top-right corner, spanning the top 10 mm of the opening.
- Add one 5 x 25 mm outward extension on each side, with each top edge 27 mm below the main opening's top edge and extending downward.
- Extend only in X; do not move or enlarge the opening in Y.
- Preserve all top-panel AC geometry and the 4 mm AC bonding rib.
- Make the complete sub-panel and `ac_duplex_panel` coupon consume the same production geometry.
- Do not commit generated CSG or STL artifacts.

---

### Task 1: Add the parametric AC terminal-access cutter

**Files:**
- Modify: `things/plamp8/plamp8.scad`
- Test: `tests/test_things_cad_scripts.py`

**Interfaces:**
- Consumes: `sub_panel_socket_w`, `sub_panel_socket_h`, `boolean_shim`, `left_ac_x`, `right_ac_x`, `outlet_feature_x`, and `ac_row_y`.
- Produces: dimensions `sub_panel_socket_ground_access_w`, `sub_panel_socket_ground_access_h`, `sub_panel_socket_side_access_w`, `sub_panel_socket_side_access_h`, `sub_panel_socket_side_access_top_offset`; module `sub_panel_socket_negative()`.

- [ ] **Step 1: Write the failing source-contract test**

Add this test beside the existing Plamp8 sub-panel geometry tests in `tests/test_things_cad_scripts.py`:

```python
def test_plamp8_sub_panel_ac_socket_exposes_all_terminal_screws(self):
    source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
    compact = compact_scad(source)
    cutter = (
        compact_scad(scad_module_body(source, "sub_panel_socket_negative"))
        if "module sub_panel_socket_negative" in source
        else ""
    )
    sub_panel = compact_scad(scad_module_body(source, "sub_panel_8ch_negative"))
    top_panel = compact_scad(scad_module_body(source, "top_panel_8ch"))

    for definition in (
        "sub_panel_socket_ground_access_w=5;",
        "sub_panel_socket_ground_access_h=10;",
        "sub_panel_socket_side_access_w=5;",
        "sub_panel_socket_side_access_h=25;",
        "sub_panel_socket_side_access_top_offset=27;",
    ):
        self.assertIn(definition, compact)

    self.assertIn("rect_cutout(sub_panel_socket_w,sub_panel_socket_h);", cutter)
    self.assertIn(
        "sub_panel_socket_w/2+sub_panel_socket_ground_access_w/2-boolean_shim/2",
        cutter,
    )
    self.assertIn(
        "sub_panel_socket_h/2-sub_panel_socket_ground_access_h/2", cutter
    )
    self.assertIn(
        "rect_cutout(sub_panel_socket_ground_access_w+boolean_shim,"
        "sub_panel_socket_ground_access_h);",
        cutter,
    )
    self.assertIn("for(side=[-1,1])", cutter)
    self.assertIn(
        "side*(sub_panel_socket_w/2+sub_panel_socket_side_access_w/2-"
        "boolean_shim/2)",
        cutter,
    )
    self.assertIn(
        "sub_panel_socket_h/2-sub_panel_socket_side_access_top_offset-"
        "sub_panel_socket_side_access_h/2",
        cutter,
    )
    self.assertIn(
        "rect_cutout(sub_panel_socket_side_access_w+boolean_shim,"
        "sub_panel_socket_side_access_h);",
        cutter,
    )
    self.assertIn(
        "translate([x+outlet_feature_x,ac_row_y,plate_t/2])"
        "sub_panel_socket_negative();",
        sub_panel,
    )
    self.assertNotIn("sub_panel_socket_negative();", top_panel)
    self.assertEqual(top_panel.count("outlet_cover_negative(false);"), 2)
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_sub_panel_ac_socket_exposes_all_terminal_screws \
  -v
```

Expected: FAIL because the five access dimensions and `sub_panel_socket_negative()` do not exist.

- [ ] **Step 3: Add the five access dimensions**

Immediately after the existing `sub_panel_socket_w` and `sub_panel_socket_h` declarations in `things/plamp8/plamp8.scad`, add:

```scad
sub_panel_socket_ground_access_w = 5;
sub_panel_socket_ground_access_h = 10;
sub_panel_socket_side_access_w = 5;
sub_panel_socket_side_access_h = 25;
sub_panel_socket_side_access_top_offset = 27;
```

- [ ] **Step 4: Add the shared socket cutter**

Before `sub_panel_socket_bottom_rim_relief_negative()`, add:

```scad
module sub_panel_socket_negative() {
    rect_cutout(sub_panel_socket_w, sub_panel_socket_h);

    translate([
        sub_panel_socket_w / 2
            + sub_panel_socket_ground_access_w / 2
            - boolean_shim / 2,
        sub_panel_socket_h / 2
            - sub_panel_socket_ground_access_h / 2,
        0
    ])
        rect_cutout(
            sub_panel_socket_ground_access_w + boolean_shim,
            sub_panel_socket_ground_access_h
        );

    for (side = [-1, 1])
        translate([
            side * (
                sub_panel_socket_w / 2
                    + sub_panel_socket_side_access_w / 2
                    - boolean_shim / 2
            ),
            sub_panel_socket_h / 2
                - sub_panel_socket_side_access_top_offset
                - sub_panel_socket_side_access_h / 2,
            0
        ])
            rect_cutout(
                sub_panel_socket_side_access_w + boolean_shim,
                sub_panel_socket_side_access_h
            );
}
```

The `boolean_shim / 2` offset plus `+ boolean_shim` width makes each extension overlap the main opening by `boolean_shim` while keeping its nominal outside edge exactly 5 mm beyond the original opening.

- [ ] **Step 5: Reuse the cutter at both production socket centers**

Inside the existing `for (x = [left_ac_x, right_ac_x])` loop in `sub_panel_8ch_negative()`, replace:

```scad
translate([x + outlet_feature_x, ac_row_y, plate_t / 2])
    rect_cutout(sub_panel_socket_w, sub_panel_socket_h);
```

with:

```scad
translate([x + outlet_feature_x, ac_row_y, plate_t / 2])
    sub_panel_socket_negative();
```

Do not change `top_panel_8ch()`, `outlet_cover_negative()`, the AC socket centers, or the AC bonding rib.

- [ ] **Step 6: Run focused tests and verify GREEN**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_sub_panel_ac_socket_exposes_all_terminal_screws \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_sub_panel_has_full_y_ac_bonding_rib \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_connector_panel_views_pair_top_and_production_sub_panel_coupons \
  -v
```

Expected: all three tests pass; the new contract confirms the top panel is unchanged and the existing coupon contract confirms the AC view still crops production geometry.

- [ ] **Step 7: Compile the affected production views**

Run:

```bash
openscad -o /tmp/plamp8-ac-terminal-access-sub.csg \
  -D 'view="sub_panel"' \
  -D 'revision_string="ac-terminal-access"' \
  things/plamp8/plamp8.scad
openscad -o /tmp/plamp8-ac-terminal-access-coupon.csg \
  -D 'view="ac_duplex_panel"' \
  -D 'revision_string="ac-terminal-access"' \
  things/plamp8/plamp8.scad
test -s /tmp/plamp8-ac-terminal-access-sub.csg
test -s /tmp/plamp8-ac-terminal-access-coupon.csg
```

Expected: both OpenSCAD commands exit zero without warnings, errors, or assertions, and both CSG files are non-empty.

- [ ] **Step 8: Run repository-wide verification**

Run:

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m plamp cad validate plamp8 --json
.venv/bin/python -m plamp cad plan plamp8 --preset panels --revision ac-terminal-access --json
git diff --check
```

Expected: all tests pass, CAD metadata reports `"valid": true`, the `panels` preset still expands to ordered jobs `top_panel` and `sub_panel`, and `git diff --check` prints nothing.

- [ ] **Step 9: Commit and push**

```bash
git add things/plamp8/plamp8.scad tests/test_things_cad_scripts.py
git commit -m "Expose Plamp8 AC terminal screws"
git push origin feature/plamp8-panel-bonding
```

Retain the worktree and provide the existing pull-request comparison link for print review.
