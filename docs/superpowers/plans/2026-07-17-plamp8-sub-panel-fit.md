# Plamp8 Sub-Panel Fit Correction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clear the two obstructed left XT60 nuts and make the sub-panel Git revision survive slicing.

**Architecture:** Keep the correction inside `plamp8.scad`: named fit parameters define the nut diameter and engraving depth, one negative module cuts only the PH Up and Agitator outboard lip positions, and the existing revision cutter uses a meaningful overlap. A source-contract test protects the exact dimensions and target positions; real OpenSCAD renders verify the final meshes.

**Tech Stack:** OpenSCAD, Python `unittest`, and the direct `plamp cad` CLI.

## Global Constraints

- Nut clearance diameter is exactly 7 mm.
- Sub-panel revision engraving depth is exactly 0.6 mm.
- Nut clearance cuts only the raised lip at DC channel indices 0 and 2; it preserves the 5 mm base.
- No other connector, wall, label, or panel dimension changes.
- Generated STL and print artifacts remain outside Git.

---

### Task 1: Correct and verify the sub-panel geometry

**Files:**
- Modify: `things/plamp8/plamp8.scad`
- Test: `tests/test_things_cad_scripts.py`

**Interfaces:**
- Consumes: `dc_channel_x(i)`, `dc_channel_y(i)`, `dc_connector_x()`, `xt60_screw_spacing`, `sub_panel_base_h`, and `sub_panel_h` from `things/plamp8/plamp8.scad`.
- Produces: `xt60_nut_clearance_d`, `sub_panel_revision_depth`, and `sub_panel_left_xt60_nut_clearances_negative()`.

- [ ] **Step 1: Add the failing source-contract test**

Add this method to `ThingsCadScriptsTest` in `tests/test_things_cad_scripts.py`:

```python
def test_plamp8_sub_panel_xt60_nut_clearance_and_revision_depth(self):
    source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()

    self.assertIn("xt60_nut_clearance_d = 7;", source)
    self.assertIn("sub_panel_revision_depth = 0.6;", source)
    self.assertRegex(
        source,
        r"module sub_panel_left_xt60_nut_clearances_negative\(\) \{[\s\S]*?for \(i = \[0, 2\]\)[\s\S]*?dc_channel_x\(i\) \+ dc_connector_x\(\) - xt60_screw_spacing / 2[\s\S]*?sub_panel_base_h[\s\S]*?cylinder\([\s\S]*?h = sub_panel_h - sub_panel_base_h \+ 0\.1,[\s\S]*?d = xt60_nut_clearance_d",
    )
    self.assertIn("sub_panel_left_xt60_nut_clearances_negative();", source)
    self.assertIn(
        "write_text(revision_string, 4, -sub_panel_revision_depth);",
        source,
    )
```

- [ ] **Step 2: Run the test and confirm it fails**

Run:

```bash
.venv/bin/python -m unittest tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_sub_panel_xt60_nut_clearance_and_revision_depth -v
```

Expected: `FAIL` because `xt60_nut_clearance_d = 7;` is absent.

- [ ] **Step 3: Add the named dimensions and targeted negative geometry**

Add these dimensions beside the existing XT60 and sub-panel dimensions in `things/plamp8/plamp8.scad`:

```scad
xt60_nut_clearance_d = 7;
sub_panel_revision_depth = 0.6;
```

Add this negative module after `sub_panel_barrel_channel_negative()`:

```scad
module sub_panel_left_xt60_nut_clearances_negative() {
    for (i = [0, 2])
        translate([
            dc_channel_x(i) + dc_connector_x() - xt60_screw_spacing / 2,
            dc_channel_y(i),
            sub_panel_base_h
        ])
            cylinder(
                h = sub_panel_h - sub_panel_base_h + 0.1,
                d = xt60_nut_clearance_d
            );
}
```

Call `sub_panel_left_xt60_nut_clearances_negative();` in `sub_panel_8ch_negative()` immediately after the four DC channel negatives. Replace the revision call with:

```scad
write_text(revision_string, 4, -sub_panel_revision_depth);
```

- [ ] **Step 4: Run the focused and CAD-script tests**

Run:

```bash
.venv/bin/python -m unittest tests.test_things_cad_scripts -v
```

Expected: all tests pass.

- [ ] **Step 5: Render the affected mesh and regression view**

Run from clean `/tmp` targets:

```bash
plamp cad generate plamp8 --revision nut-clearance-1 --view sub_panel --output /tmp/plamp8_sub_panel_fit
plamp cad generate plamp8 --revision nut-clearance-1 --preview --view top_panel --output /tmp/plamp8_top_panel_regression
```

Expected: both STL files are non-empty; neither log reports an empty top-level object. The sub-panel log reports a simple 3D object. The top-panel preview verifies aligned holes without paying the final text and `$fn=96` render cost.

- [ ] **Step 6: Verify and commit**

Run:

```bash
git diff --check
git status --short
```

Expected: only `things/plamp8/plamp8.scad`, `tests/test_things_cad_scripts.py`, and this plan are changed after the already-committed design document; no STL is tracked.

Commit:

```bash
git add things/plamp8/plamp8.scad tests/test_things_cad_scripts.py docs/superpowers/plans/2026-07-17-plamp8-sub-panel-fit.md
git commit -m "Clear Plamp8 sub-panel XT60 nuts"
```
