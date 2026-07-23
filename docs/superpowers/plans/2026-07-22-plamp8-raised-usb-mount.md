# Plamp8 Raised USB Mount Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the recessed top-panel USB mount with a 5.5 mm raised sub-panel mount whose connector ears protrude through a 27.5 × 10.5 mm capsule.

**Architecture:** Keep the canonical USB center and paired coupon. The top panel receives only the capsule cutter; the sub-panel subtracts its east-ledge notch before adding two ear risers, then applies the revised connector opening, M3 clearance holes, and flush underside countersinks through the complete mount.

**Tech Stack:** OpenSCAD and Python `unittest` source-contract tests.

## Global Constraints

- Target connector protrusion is 2.5 mm above the 3 mm top panel, requiring 5.5 mm risers.
- The top capsule is the hull of two 10.5 mm circles on 17 mm centers, totaling 27.5 × 10.5 mm.
- The top panel has no USB screw holes, countersinks, or cable recess.
- The sub-panel opening is 12.5 × 10.5 mm with 17 mm-spaced, 3.4 mm M3 holes.
- Remove 5 mm in X from the inner east ledge over 10 mm in Y, preserving its outer 5 mm.
- Use two M3 × 16 mm flat-head screws in 6.5 mm underside countersinks 1.55 mm deep.
- Preserve all other service-pocket, panel, connector, and enclosure geometry.
- Do not commit generated STL or CSG artifacts.

---

### Task 1: Implement the raised USB mount

**Files:**
- Modify: `tests/test_things_cad_scripts.py`
- Modify: `things/plamp8/plamp8.scad`

**Interfaces:**
- Consumes: `plate_t`, `sub_panel_base_h`, `sub_panel_wall`, `layout_offset_x`, `usb_c_panel_x/y`, `screw_clearance_d()`, and `screw_chamfer_d()`.
- Produces: `usb_c_capsule_negative()`, `sub_panel_usb_risers_positive()`, `sub_panel_usb_east_ledge_relief_negative()`, and `sub_panel_usb_screw_negative()`.

- [ ] **Step 1: Replace the recess regression test with a failing raised-mount contract**

Replace `test_plamp8_usb_cable_relief_thins_only_the_connector_mount` in
`tests/test_things_cad_scripts.py` with a test that checks these compact SCAD
contracts:

```python
def test_plamp8_usb_connector_uses_raised_sub_panel_mount(self):
    source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
    compact = compact_scad(source)
    top = compact_scad(scad_module_body(source, "usb_c_connector_negative"))
    capsule = compact_scad(scad_module_body(source, "usb_c_capsule_negative"))
    risers = compact_scad(scad_module_body(source, "sub_panel_usb_risers_positive"))
    ledge = compact_scad(
        scad_module_body(source, "sub_panel_usb_east_ledge_relief_negative")
    )
    screw = compact_scad(scad_module_body(source, "sub_panel_usb_screw_negative"))
    sub_negative = compact_scad(scad_module_body(source, "sub_panel_usb_c_negative"))

    for definition in (
        "usb_c_capsule_d=10.5;",
        "usb_c_capsule_w=usb_c_screw_spacing+usb_c_capsule_d;",
        "usb_c_target_protrusion=2.5;",
        "usb_c_riser_h=plate_t+usb_c_target_protrusion;",
        "usb_c_mount_screw_length=16;",
        "usb_c_countersink_d=screw_chamfer_d(\"M3\");",
        "usb_c_countersink_h=(usb_c_countersink_d-usb_c_screw_d)/2;",
        "sub_panel_usb_c_cutout_w=12.5;",
        "sub_panel_usb_c_cutout_h=10.5;",
        "sub_panel_usb_ledge_relief_x=5;",
        "sub_panel_usb_ledge_relief_y=10;",
    ):
        self.assertIn(definition, compact)

    self.assertEqual(top, "usb_c_capsule_negative();")
    self.assertIn("hull()", capsule)
    self.assertIn("x=[-usb_c_screw_spacing/2,usb_c_screw_spacing/2]", capsule)
    self.assertIn("d=usb_c_capsule_d", capsule)
    self.assertIn("h=usb_c_riser_h", risers)
    self.assertIn("d=usb_c_capsule_d", risers)
    self.assertIn("sub_panel_usb_ledge_relief_x", ledge)
    self.assertIn("sub_panel_usb_ledge_relief_y", ledge)
    self.assertIn("d1=usb_c_countersink_d", screw)
    self.assertIn("d2=usb_c_screw_d", screw)
    self.assertIn("sub_panel_usb_screw_negative();", sub_negative)
    self.assertNotIn("usb_c_cable_recess", source)
    self.assertNotIn("topside_countersunk_screw_hole", source)
```

Update `test_plamp8_usb_com_fit_dimensions_and_panel_cutouts` to expect the
12.5 × 10.5 mm sub-panel opening, capsule-only top negative, M3 × 16 declaration,
and underside countersink module. Remove its old 12 × 10 top opening and
topside countersink expectations.

- [ ] **Step 2: Run the focused tests and verify RED**

```bash
UV_CACHE_DIR=/tmp/uv-cache /home/hugo/.local/bin/uv run --locked \
  python -m unittest \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_usb_connector_uses_raised_sub_panel_mount \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_usb_com_fit_dimensions_and_panel_cutouts \
  -v
```

Expected: FAIL because the capsule, risers, ledge notch, underside countersinks,
and new dimensions do not exist.

- [ ] **Step 3: Add dimensions and invariant assertions**

Replace the recess-only USB dimensions with:

```scad
usb_c_capsule_d = 10.5;
usb_c_screw_d = screw_clearance_d("M3");
usb_c_screw_spacing = 17;
usb_c_capsule_w = usb_c_screw_spacing + usb_c_capsule_d;
usb_c_target_protrusion = 2.5;
usb_c_riser_h = plate_t + usb_c_target_protrusion;
usb_c_supplied_screw_length = 10;
usb_c_mount_screw_length = 16;
usb_c_countersink_d = screw_chamfer_d("M3");
usb_c_countersink_h = (usb_c_countersink_d - usb_c_screw_d) / 2;
```

Set `sub_panel_usb_c_cutout_w = 12.5`, retain its 10.5 mm height, and add:

```scad
sub_panel_usb_ledge_relief_x = 5;
sub_panel_usb_ledge_relief_y = 10;
sub_panel_usb_hole_bridge =
    (usb_c_screw_spacing - sub_panel_usb_c_cutout_w - usb_c_screw_d) / 2;
```

Add these invariant assertions:

```scad
assert(usb_c_capsule_w == 27.5 && usb_c_capsule_d == 10.5,
    "USB top capsule must remain 27.5 x 10.5 mm");
assert(usb_c_riser_h == 5.5,
    "USB risers must place the connector 2.5 mm above the top panel");
assert(usb_c_mount_screw_length - usb_c_supplied_screw_length
        >= usb_c_riser_h
        && usb_c_mount_screw_length - usb_c_supplied_screw_length
        <= usb_c_riser_h + 0.5,
    "USB mount screws must preserve the supplied screw engagement");
assert(abs(sub_panel_usb_hole_bridge - 0.55) < 0.000001,
    "USB sub-panel opening must retain a 0.55 mm screw-hole bridge");
assert(sub_panel_wall - sub_panel_usb_ledge_relief_x == 5,
    "USB ledge relief must preserve the outer 5 mm east ledge");
```

- [ ] **Step 4: Implement the top capsule and sub-panel geometry**

Use this top cutter and retain `usb_c_connector_negative()` as the shared
production/coupon interface:

```scad
module usb_c_capsule_negative() {
    hull()
        for (x = [-usb_c_screw_spacing / 2, usb_c_screw_spacing / 2])
            translate([x, 0, plate_t / 2])
                cylinder(h = 30, d = usb_c_capsule_d, center = true);
}

module usb_c_connector_negative() {
    usb_c_capsule_negative();
}
```

Add the two positive risers in centered sub-panel coordinates:

```scad
module sub_panel_usb_risers_positive() {
    for (x = [-usb_c_screw_spacing / 2, usb_c_screw_spacing / 2])
        translate([
            usb_c_panel_x + x,
            usb_c_panel_y,
            sub_panel_base_h
        ])
            cylinder(h = usb_c_riser_h, d = usb_c_capsule_d);
}
```

Add the inner-half east-ledge notch:

```scad
module sub_panel_usb_east_ledge_relief_negative() {
    translate([
        top_panel_w - sub_panel_wall - layout_offset_x - boolean_shim,
        usb_c_panel_y - sub_panel_usb_ledge_relief_y / 2,
        sub_panel_base_h
    ])
        cube([
            sub_panel_usb_ledge_relief_x + boolean_shim,
            sub_panel_usb_ledge_relief_y,
            sub_panel_h - sub_panel_base_h + boolean_shim
        ]);
}
```

Change the geometry wrapper at the start of `sub_panel_8ch()` to subtract the
ledge notch before unioning the risers, then apply the complete production
negative set:

```scad
module sub_panel_8ch() {
    translate([layout_offset_x, layout_offset_y, 0]) {
        difference() {
            union() {
                difference() {
                    translate([-layout_offset_x, -layout_offset_y, 0])
                        sub_panel_8ch_positive();
                    sub_panel_usb_east_ledge_relief_negative();
                }
                sub_panel_usb_risers_positive();
            }

            sub_panel_8ch_negative();
        }
    }

    // Preserve the existing back-label body after this geometry block.
}
```

Add an underside countersink per screw:

```scad
module sub_panel_usb_screw_negative() {
    screw_hole(usb_c_screw_d);
    translate([0, 0, -boolean_shim])
        cylinder(
            h = usb_c_countersink_h + boolean_shim,
            d1 = usb_c_countersink_d,
            d2 = usb_c_screw_d
        );
}
```

Call it at both 17 mm-spaced positions from the revised connector negative:

```scad
module sub_panel_usb_c_negative() {
    rect_cutout(sub_panel_usb_c_cutout_w, sub_panel_usb_c_cutout_h);

    for (x = [-usb_c_screw_spacing / 2, usb_c_screw_spacing / 2])
        translate([x, 0, 0])
            sub_panel_usb_screw_negative();
}
```

Remove the obsolete top cable-recess and topside countersink modules and
dimensions.

- [ ] **Step 5: Verify GREEN and compile the coupon**

Run the focused tests from Step 2, then:

```bash
./bin/plamp cad validate plamp8 --json
./bin/plamp cad plan plamp8 --view usb_c_panel --revision usb-raised --json
openscad -o /tmp/plamp8-usb-raised.csg \
  -D 'view="usb_c_panel"' -D 'revision_string="usb-raised"' \
  things/plamp8/plamp8.scad
UV_CACHE_DIR=/tmp/uv-cache /home/hugo/.local/bin/uv run --locked \
  python -m unittest discover -s tests -q
git diff --check
```

Expected: metadata valid; one `usb_c_panel` job; non-empty CSG with no warning,
error, assertion, or empty-object output; all Python tests pass; diff check is
silent.

- [ ] **Step 6: Commit and push**

```bash
git add things/plamp8/plamp8.scad tests/test_things_cad_scripts.py
git commit -m "Raise Plamp8 USB connector mount"
git push origin fix/plamp8-usb-cable-relief
```
