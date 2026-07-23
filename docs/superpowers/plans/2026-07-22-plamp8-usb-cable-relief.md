# Plamp8 USB Cable Relief Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a 24 × 14 mm stepped USB-C cable relief that leaves 1.5 mm of top-panel material so a molded plug can fully engage the underside-mounted receptacle.

**Architecture:** Keep the existing 12 × 10 mm through-opening as the receptacle locator. Add one parameterized local recess to the shared USB hardware negative and move the countersink datum to its floor, automatically updating both the production top panel and its paired fit coupon while leaving the sub-panel unchanged.

**Tech Stack:** OpenSCAD and Python `unittest` source-contract tests.

## Global Constraints

- The cable recess is a centered 24 × 14 mm rounded rectangle with 2 mm corner radius.
- The recess leaves exactly 1.5 mm of top-panel material.
- Preserve the 12 × 10 mm rounded through-opening and 13 × 10.5 mm sub-panel opening.
- Preserve connector and screw centers, labels, service-pocket layout, and all non-USB connector geometry.
- Do not commit generated CSG or STL artifacts.

---

### Task 1: Add the USB cable relief

**Files:**
- Modify: `tests/test_things_cad_scripts.py`
- Modify: `things/plamp8/plamp8.scad`

**Interfaces:**
- Consumes: `plate_t`, `boolean_shim`, `round_hull(x, y, r, h)`, and the existing `usb_c_connector_negative()` shared by production and coupon geometry.
- Produces: `usb_c_cable_recess_w`, `usb_c_cable_recess_h`, `usb_c_cable_recess_r`, `usb_c_mount_thickness`, and `usb_c_cable_recess_negative()`.

- [ ] **Step 1: Write the failing source-contract test**

Add this method to `ThingsCadScriptsTest` in `tests/test_things_cad_scripts.py`:

```python
def test_plamp8_usb_cable_relief_thins_only_the_connector_mount(self):
    source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
    compact = compact_scad(source)
    connector = compact_scad(scad_module_body(source, "usb_c_connector_negative"))
    relief = compact_scad(scad_module_body(source, "usb_c_cable_recess_negative"))
    sub_panel = compact_scad(scad_module_body(source, "sub_panel_usb_c_negative"))

    for definition in (
        "usb_c_cable_recess_w=24;",
        "usb_c_cable_recess_h=14;",
        "usb_c_cable_recess_r=2;",
        "usb_c_mount_thickness=1.5;",
        "usb_c_screw_surface_z=usb_c_mount_thickness;",
    ):
        self.assertIn(definition, compact)

    self.assertIn("usb_c_cable_recess_negative();", connector)
    self.assertIn(
        "recess_h=plate_t-usb_c_mount_thickness+boolean_shim;", relief
    )
    self.assertIn(
        "translate([0,0,usb_c_mount_thickness+recess_h/2])"
        "round_hull(usb_c_cable_recess_w,usb_c_cable_recess_h,"
        "usb_c_cable_recess_r,recess_h);",
        relief,
    )
    self.assertIn(
        "topside_countersunk_screw_hole(usb_c_screw_d,"
        "usb_c_screw_head_d,usb_c_screw_surface_z);",
        connector,
    )
    self.assertIn(
        "rect_cutout(sub_panel_usb_c_cutout_w,sub_panel_usb_c_cutout_h);",
        sub_panel,
    )
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
UV_CACHE_DIR=/tmp/uv-cache /home/hugo/.local/bin/uv run --locked \
  python -m unittest \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_usb_cable_relief_thins_only_the_connector_mount \
  -v
```

Expected: ERROR or FAIL because `usb_c_cable_recess_negative` and its dimensions do not exist.

- [ ] **Step 3: Implement the minimal OpenSCAD geometry**

Add the USB parameters beside the existing USB dimensions:

```scad
usb_c_cable_recess_w = 24;
usb_c_cable_recess_h = 14;
usb_c_cable_recess_r = 2;
usb_c_mount_thickness = 1.5;
usb_c_screw_surface_z = usb_c_mount_thickness;
```

Replace the old `usb_c_screw_surface_z = plate_t - 0.5;`. Add this module immediately before `usb_c_connector_negative()`:

```scad
module usb_c_cable_recess_negative() {
    recess_h = plate_t - usb_c_mount_thickness + boolean_shim;

    translate([0, 0, usb_c_mount_thickness + recess_h / 2])
        round_hull(
            usb_c_cable_recess_w,
            usb_c_cable_recess_h,
            usb_c_cable_recess_r,
            recess_h
        );
}
```

Call it once at the start of the shared connector cutter:

```scad
module usb_c_connector_negative() {
    usb_c_cable_recess_negative();
    rounded_rect_cutout(usb_c_cutout_w, usb_c_cutout_h, usb_c_cutout_r);

    for (x = [-usb_c_screw_spacing / 2, usb_c_screw_spacing / 2])
        translate([x, 0, 0])
            topside_countersunk_screw_hole(
                usb_c_screw_d,
                usb_c_screw_head_d,
                usb_c_screw_surface_z
            );
}
```

- [ ] **Step 4: Run focused and full verification**

Run the focused test from Step 2 and expect `OK`. Then run:

```bash
./bin/plamp cad validate plamp8 --json
./bin/plamp cad plan plamp8 --view usb_c_panel --revision usb-cable-relief --json
openscad -o /tmp/plamp8-usb-cable-relief.csg \
  -D 'view="usb_c_panel"' -D 'revision_string="usb-cable-relief"' \
  things/plamp8/plamp8.scad
UV_CACHE_DIR=/tmp/uv-cache /home/hugo/.local/bin/uv run --locked \
  python -m unittest discover -s tests -q
git diff --check
```

Expected: metadata is valid; the plan has one `usb_c_panel` job; OpenSCAD creates a non-empty CSG without warnings, errors, or assertions; all Python tests pass; and `git diff --check` is silent.

- [ ] **Step 5: Commit and push**

```bash
git add things/plamp8/plamp8.scad tests/test_things_cad_scripts.py
git commit -m "Add Plamp8 USB cable relief"
git push -u origin fix/plamp8-usb-cable-relief
```
