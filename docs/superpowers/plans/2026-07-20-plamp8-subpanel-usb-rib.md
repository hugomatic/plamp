# Plamp8 Sub-Panel USB Rib Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a full-width 10 × 5 mm sub-panel brace below USB and make `revision` the default revision text.

**Architecture:** Keep the existing sub-panel base and perimeter authoritative. Add one named positive rib module spanning between the side walls, derive its Z height from the existing base/top datums, and relocate only the sub-panel revision engraving below it.

**Tech Stack:** OpenSCAD, Python `unittest`, Git

## Global Constraints

- The brace is 10 mm wide and 5 mm high.
- It spans the full interior width between the existing side walls.
- Its top is coplanar with the 10 mm sub-panel top datum.
- It clears the USB cutout by 1 mm.
- No fifth screw, top-panel hole, or nut trap is added.
- Push source before running OpenSCAD.
- Do not run a full assembly render.

---

### Task 1: Add the USB support rib and revision default

**Files:**
- Modify: `tests/test_things_cad_scripts.py`
- Modify: `things/plamp8/plamp8.scad`

**Interfaces:**
- Consumes: existing `sub_panel_base_h`, `sub_panel_h`, `sub_panel_wall`, `top_panel_w`, `layout_offset_y`, `usb_c_panel_y`, and `sub_panel_usb_c_cutout_h` dimensions.
- Produces: `sub_panel_usb_support_rib_positive()` and the `sub_panel_usb_support_rib_*` dimension contract.

- [ ] **Step 1: Write failing source-contract tests**

Add tests that require the 10 mm rib width, derived 5 mm height, 1 mm USB clearance, full interior span, base-to-top placement, relocated sub-panel revision text, and `revision_string = "revision"`.

```python
def test_plamp8_sub_panel_has_full_width_usb_support_rib(self):
    source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
    rib = source.split("module sub_panel_usb_support_rib_positive", 1)[1].split(
        "module ", 1
    )[0]

    self.assertIn("sub_panel_usb_support_rib_w = 10;", source)
    self.assertIn(
        "sub_panel_usb_support_rib_h = sub_panel_h - sub_panel_base_h;", source
    )
    self.assertIn("sub_panel_usb_support_rib_gap = 1;", source)
    self.assertIn(
        "usb_c_panel_y - sub_panel_usb_c_cutout_h / 2"
        " - sub_panel_usb_support_rib_gap"
        " - sub_panel_usb_support_rib_w / 2;",
        source,
    )
    self.assertIn("sub_panel_wall,", rib)
    self.assertIn("top_panel_w - 2 * sub_panel_wall,", rib)
    self.assertIn("sub_panel_base_h", rib)
    self.assertIn("sub_panel_usb_support_rib_h", rib)
    self.assertIn("sub_panel_usb_support_rib_positive();", source)

def test_plamp8_revision_default_and_sub_panel_rib_clearance(self):
    source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()

    self.assertIn('revision_string = "revision";', source)
    self.assertIn("sub_panel_revision_clearance = 1;", source)
    self.assertIn("translate([revision_x, sub_panel_revision_y, sub_panel_base_h])", source)
```

- [ ] **Step 2: Run the two tests and verify RED**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_sub_panel_has_full_width_usb_support_rib \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_revision_default_and_sub_panel_rib_clearance -v
```

Expected: both tests fail because the rib variables/module and `revision` default do not exist.

- [ ] **Step 3: Implement the minimal OpenSCAD geometry**

Add these dimensions near the existing sub-panel dimensions and layout coordinates:

```scad
sub_panel_usb_support_rib_w = 10;
sub_panel_usb_support_rib_h = sub_panel_h - sub_panel_base_h;
sub_panel_usb_support_rib_gap = 1;
sub_panel_revision_clearance = 1;
sub_panel_revision_font = 4;

sub_panel_usb_support_rib_y =
    usb_c_panel_y - sub_panel_usb_c_cutout_h / 2
    - sub_panel_usb_support_rib_gap
    - sub_panel_usb_support_rib_w / 2;
sub_panel_revision_y =
    sub_panel_usb_support_rib_y - sub_panel_usb_support_rib_w / 2
    - sub_panel_revision_clearance - sub_panel_revision_font / 2;
```

Change the default and add/call the positive module:

```scad
revision_string = "revision";

module sub_panel_usb_support_rib_positive() {
    translate([
        sub_panel_wall,
        layout_offset_y + sub_panel_usb_support_rib_y
            - sub_panel_usb_support_rib_w / 2,
        sub_panel_base_h
    ])
        cube([
            top_panel_w - 2 * sub_panel_wall,
            sub_panel_usb_support_rib_w,
            sub_panel_usb_support_rib_h
        ]);
}
```

Call `sub_panel_usb_support_rib_positive();` inside `sub_panel_8ch_positive()` and use `sub_panel_revision_y` plus `sub_panel_revision_font` for the sub-panel engraving only.

- [ ] **Step 4: Run the focused tests and full CAD script suite**

Run the Step 2 command, then:

```bash
.venv/bin/python -m unittest tests.test_things_cad_scripts -v
git diff --check
```

Expected: focused tests and the full CAD script suite pass; `git diff --check` prints nothing.

- [ ] **Step 5: Commit and push before OpenSCAD**

```bash
git add things/plamp8/plamp8.scad tests/test_things_cad_scripts.py \
  docs/superpowers/plans/2026-07-20-plamp8-subpanel-usb-rib.md
git commit -m "Add full-width sub-panel USB support rib"
git push
```

- [ ] **Step 6: Quick OpenSCAD compile**

```bash
openscad -o /tmp/plamp8-subpanel-rib.csg \
  -D 'view="sub_panel"' -D 'render_text=false' \
  things/plamp8/plamp8.scad
```

Expected: exit status 0 with no geometry errors. Keep the generated CSG outside the repository.
