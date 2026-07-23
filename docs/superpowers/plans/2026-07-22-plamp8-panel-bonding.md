# Plamp8 Panel Bonding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a full AC support rib and ten roofed, side-loaded M3 nut towers that clamp the Plamp8 top panel to its sub-panel, plus a ready-made `panels` generation preset.

**Architecture:** Keep the existing top-panel connector geometry and canonical screw axes unchanged. Add all structural positives to `sub_panel_8ch_positive()`, apply specialized blind screw bores and captive-nut cutters through `sub_panel_8ch_negative()`, and rely on the existing production-crop coupon views for exact fit tests. Add one metadata-only preset for the normal-user two-panel workflow.

**Tech Stack:** OpenSCAD, embedded `generate.json` metadata, Python `unittest` source-contract tests, and the Plamp CAD CLI.

## Global Constraints

- Preserve all connector centers, rectangular openings, screw spacing, labels, service pockets, perimeter ledge, and the raised USB mount.
- The AC rib is 4 mm wide, runs in Y, and spans from the inner south ledge to the DC section.
- Add two towers for each of four XT60 connectors and two towers for C13: ten towers total when `dc_connector_type == "xt60"`.
- Each tower is 11 mm nominal diameter and spans `sub_panel_base_h` through `sub_panel_h`.
- Nut loading mouths face inward toward their connector rectangle; left nuts slide toward negative X and right nuts slide toward positive X.
- Entry slots sweep the nut from the rectangular opening into its pocket, stop at the screw axis, and never continue into the far half of the tower.
- Use the existing calibrated M3 nut dimensions and retain every nut under a tapered, support-free roof.
- Blind screw-tip bores stop at least 1 mm above the sub-panel underside.
- Do not hardcode a screw length; available M3 lengths are 8, 12, 16, and 20 mm.
- Add `panels` with ordered items `view:top_panel`, `view:sub_panel`; keep `split-box` as the default.
- Do not commit generated CSG or STL artifacts.

---

### Task 1: Add the ready-made panels preset

**Files:**
- Modify: `things/plamp8/plamp8.scad`
- Test: `tests/test_things_cad_scripts.py`

**Interfaces:**
- Consumes: embedded `generate.json` metadata and existing `top_panel` / `sub_panel` views.
- Produces: preset `panels`, ordered as top panel then sub-panel.

- [ ] **Step 1: Write the failing preset contract**

Add this test beside the existing Plamp8 view/preset tests:

```python
def test_plamp8_has_ready_made_panels_preset(self):
    source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()

    self.assertIn('"panels": {', source)
    self.assertIn(
        '"description": "Printable top and internal sub-panels",', source
    )
    self.assertIn(
        '"items": ["view:top_panel", "view:sub_panel"]', source
    )
    self.assertIn('"default_preset": "split-box"', source)
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_has_ready_made_panels_preset \
  -v
```

Expected: FAIL because `"panels": {` is absent.

- [ ] **Step 3: Add the preset metadata**

Add this object to the embedded `presets` map after `fuse-box`:

```json
"panels": {
  "description": "Printable top and internal sub-panels",
  "items": ["view:top_panel", "view:sub_panel"]
},
```

Do not change `default_preset`.

- [ ] **Step 4: Verify the test and real recipe expansion**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_has_ready_made_panels_preset \
  -v
.venv/bin/python -m plamp cad validate plamp8 --json
.venv/bin/python -m plamp cad plan plamp8 --preset panels --revision panel-bonding --json
```

Expected: the test passes, validation reports `"valid": true`, and the plan has exactly two jobs ordered `top_panel`, `sub_panel`.

- [ ] **Step 5: Commit the preset**

```bash
git add things/plamp8/plamp8.scad tests/test_things_cad_scripts.py
git commit -m "Add Plamp8 panels preset"
```

---

### Task 2: Add the full AC support rib

**Files:**
- Modify: `things/plamp8/plamp8.scad`
- Test: `tests/test_things_cad_scripts.py`

**Interfaces:**
- Consumes: `left_ac_x`, `right_ac_x`, `outlet_feature_x`, `layout_offset_x`, `layout_offset_y`, `dc_region_bottom_y`, `sub_panel_wall`, `sub_panel_base_h`, and `sub_panel_h`.
- Produces: `sub_panel_ac_bonding_rib_positive()` and derived rib bounds.

- [ ] **Step 1: Write the failing rib contract**

Add this test beside `test_plamp8_sub_panel_separator_ribs_follow_region_bounds`:

```python
def test_plamp8_sub_panel_has_full_y_ac_bonding_rib(self):
    source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
    compact = compact_scad(source)
    rib = (
        compact_scad(scad_module_body(source, "sub_panel_ac_bonding_rib_positive"))
        if "module sub_panel_ac_bonding_rib_positive" in source
        else ""
    )
    positive = compact_scad(scad_module_body(source, "sub_panel_8ch_positive"))

    for definition in (
        "sub_panel_ac_bonding_rib_w=4;",
        "sub_panel_ac_bonding_rib_x=layout_offset_x+(left_ac_x+outlet_feature_x+right_ac_x+outlet_feature_x)/2;",
        "sub_panel_ac_bonding_rib_y0=sub_panel_wall;",
        "sub_panel_ac_bonding_rib_y1=layout_offset_y+dc_region_bottom_y;",
    ):
        self.assertIn(definition, compact)

    self.assertIn("sub_panel_base_h", rib)
    self.assertIn("sub_panel_h-sub_panel_base_h", rib)
    self.assertIn("sub_panel_ac_bonding_rib_y1-sub_panel_ac_bonding_rib_y0", rib)
    self.assertIn("sub_panel_ac_bonding_rib_positive();", positive)
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_sub_panel_has_full_y_ac_bonding_rib \
  -v
```

Expected: FAIL because the rib definitions and module are absent.

- [ ] **Step 3: Add derived dimensions and clearance assertions**

After the layout and region bounds are available, add:

```scad
sub_panel_ac_bonding_rib_w = 4;
sub_panel_ac_bonding_rib_x = layout_offset_x
    + (left_ac_x + outlet_feature_x + right_ac_x + outlet_feature_x) / 2;
sub_panel_ac_bonding_rib_y0 = sub_panel_wall;
sub_panel_ac_bonding_rib_y1 = layout_offset_y + dc_region_bottom_y;
sub_panel_ac_left_socket_right_x = layout_offset_x + left_ac_x
    + outlet_feature_x + sub_panel_socket_w / 2;
sub_panel_ac_right_socket_left_x = layout_offset_x + right_ac_x
    + outlet_feature_x - sub_panel_socket_w / 2;

assert(
    sub_panel_ac_bonding_rib_x - sub_panel_ac_bonding_rib_w / 2
        > sub_panel_ac_left_socket_right_x
    && sub_panel_ac_bonding_rib_x + sub_panel_ac_bonding_rib_w / 2
        < sub_panel_ac_right_socket_left_x,
    "AC bonding rib must remain between the socket openings"
);
assert(sub_panel_ac_bonding_rib_y1 > sub_panel_ac_bonding_rib_y0,
    "AC bonding rib must span from the south ledge to the DC section");
```

- [ ] **Step 4: Add the positive rib and union it into the production sub-panel**

Add:

```scad
module sub_panel_ac_bonding_rib_positive() {
    translate([
        sub_panel_ac_bonding_rib_x - sub_panel_ac_bonding_rib_w / 2,
        sub_panel_ac_bonding_rib_y0,
        sub_panel_base_h
    ])
        cube([
            sub_panel_ac_bonding_rib_w,
            sub_panel_ac_bonding_rib_y1 - sub_panel_ac_bonding_rib_y0,
            sub_panel_h - sub_panel_base_h
        ]);
}
```

Call `sub_panel_ac_bonding_rib_positive();` inside the union in `sub_panel_8ch_positive()` beside the existing USB and separator ribs. Existing production negatives then trim any accidental intersection, while the assertions protect the socket gap.

- [ ] **Step 5: Verify the rib contract and SCAD compilation**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_sub_panel_has_full_y_ac_bonding_rib \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_sub_panel_separator_ribs_follow_region_bounds \
  -v
openscad -o /tmp/plamp8-ac-bonding.csg \
  -D 'view="sub_panel"' \
  -D 'revision_string="panel-bonding"' \
  things/plamp8/plamp8.scad
```

Expected: both tests pass; OpenSCAD exits zero, produces a non-empty CSG, and emits no warning, error, or assertion failure.

- [ ] **Step 6: Commit the AC rib**

```bash
git add things/plamp8/plamp8.scad tests/test_things_cad_scripts.py
git commit -m "Add Plamp8 AC panel bonding rib"
```

---

### Task 3: Add XT60 and C13 captive-nut towers

**Files:**
- Modify: `things/plamp8/plamp8.scad`
- Test: `tests/test_things_cad_scripts.py`

**Interfaces:**
- Consumes: `panel_nut_d`, `panel_nut_h`, `panel_nut_clearance`, `panel_nut_entry_detent`, `sub_panel_base_h`, `sub_panel_h`, `dc_channel_x()`, `dc_channel_y()`, `dc_connector_x()`, `xt60_screw_spacing`, `xt60_cutout_w`, `c13_hardware_x/y`, `c13_screw_spacing`, and `c13_cutout_w`.
- Produces: `sub_panel_bonding_tower_positive()`, `sub_panel_bonding_nut_negative()`, `sub_panel_bonding_screw_negative()`, `sub_panel_xt60_bonding_positive()`, `sub_panel_c13_bonding_positive()`, and matching negative placement modules.

- [ ] **Step 1: Write the failing tower and placement contract**

Replace `test_plamp8_sub_panel_xt60_nut_clearance_and_revision_depth` with the
revision-only contract below because the clearance-only cylinders are being
superseded:

```python
def test_plamp8_sub_panel_revision_depth(self):
    source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()

    self.assertIn("sub_panel_revision_depth = 0.6;", source)
    self.assertRegex(
        source,
        r"write_text\(\s*revision_string,\s*sub_panel_revision_font,\s*"
        r"-sub_panel_revision_depth\s*\);",
    )
```

Then add this new test:

```python
def test_plamp8_xt60_and_c13_towers_bond_top_to_sub_panel(self):
    source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
    compact = compact_scad(source)
    tower = compact_scad(scad_module_body(source, "sub_panel_bonding_tower_positive")) if "module sub_panel_bonding_tower_positive" in source else ""
    nut = compact_scad(scad_module_body(source, "sub_panel_bonding_nut_negative")) if "module sub_panel_bonding_nut_negative" in source else ""
    screw = compact_scad(scad_module_body(source, "sub_panel_bonding_screw_negative")) if "module sub_panel_bonding_screw_negative" in source else ""
    xt60_positive = compact_scad(scad_module_body(source, "sub_panel_xt60_bonding_positive")) if "module sub_panel_xt60_bonding_positive" in source else ""
    c13_positive = compact_scad(scad_module_body(source, "sub_panel_c13_bonding_positive")) if "module sub_panel_c13_bonding_positive" in source else ""

    for definition in (
        "sub_panel_bonding_tower_d=11;",
        "sub_panel_bonding_nut_w=panel_nut_d+panel_nut_clearance;",
        "sub_panel_bonding_nut_h=panel_nut_h+panel_nut_clearance;",
        "sub_panel_bonding_roof_h=sub_panel_h-sub_panel_base_h-sub_panel_bonding_nut_h;",
        "sub_panel_bonding_blind_floor=1;",
    ):
        self.assertIn(definition, compact)

    self.assertIn("d=sub_panel_bonding_tower_d", tower)
    self.assertIn("d1=sub_panel_bonding_nut_w", nut)
    self.assertIn("d2=panel_screw_d", nut)
    self.assertIn("sub_panel_bonding_blind_floor", screw)
    self.assertIn("for(i=[0:3])", xt60_positive)
    self.assertEqual(xt60_positive.count("sub_panel_bonding_tower_positive();"), 1)
    self.assertEqual(c13_positive.count("sub_panel_bonding_tower_positive();"), 1)
    self.assertIn("mouth_direction=-side", compact)
    self.assertIn("sub_panel_xt60_bonding_positive();", compact_scad(scad_module_body(source, "sub_panel_8ch_positive")))
    self.assertIn("sub_panel_c13_bonding_positive();", compact_scad(scad_module_body(source, "sub_panel_8ch_positive")))
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_xt60_and_c13_towers_bond_top_to_sub_panel \
  -v
```

Expected: FAIL because the tower dimensions and modules are absent.

- [ ] **Step 3: Add shared dimensions and invariants**

Add near the other sub-panel dimensions:

```scad
sub_panel_bonding_tower_d = 11;
sub_panel_bonding_nut_w = panel_nut_d + panel_nut_clearance;
sub_panel_bonding_nut_h = panel_nut_h + panel_nut_clearance;
sub_panel_bonding_roof_h = sub_panel_h - sub_panel_base_h
    - sub_panel_bonding_nut_h;
sub_panel_bonding_throat_w = sub_panel_bonding_nut_w
    - 2 * panel_nut_entry_detent;
sub_panel_bonding_blind_floor = 1;
sub_panel_bonding_blind_depth = sub_panel_base_h
    - sub_panel_bonding_blind_floor;

assert(sub_panel_bonding_roof_h > 0,
    "panel bonding nut catcher needs a positive roof height");
assert(sub_panel_bonding_blind_floor >= 1,
    "panel bonding screw bores need 1 mm underside material");
assert(sub_panel_bonding_throat_w > panel_nut_d * cos(30),
    "panel bonding nut entry must admit the calibrated M3 nut");
assert(c13_screw_spacing / 2 + sub_panel_bonding_tower_d / 2
        <= c13_group_w / 2,
    "C13 bonding towers must remain inside the connector region");
```

- [ ] **Step 4: Add the shared tower and negative cutters**

Add these modules before the placement modules:

```scad
module sub_panel_bonding_tower_positive() {
    translate([0, 0, sub_panel_base_h])
        cylinder(
            h = sub_panel_h - sub_panel_base_h,
            d = sub_panel_bonding_tower_d
        );
}

module sub_panel_bonding_nut_negative(mouth_direction, opening_edge_distance) {
    detent_l = min(panel_nut_entry_detent_l, opening_edge_distance);
    main_l = opening_edge_distance - detent_l;

    translate([0, 0, sub_panel_base_h]) {
        cylinder(
            h = sub_panel_bonding_nut_h,
            d = sub_panel_bonding_nut_w,
            $fn = 6
        );

        if (main_l > 0)
            translate([
                mouth_direction > 0
                    ? 0
                    : -main_l,
                -sub_panel_bonding_nut_w / 2,
                0
            ])
                cube([
                    main_l + boolean_shim,
                    sub_panel_bonding_nut_w,
                    sub_panel_bonding_nut_h
                ]);

        translate([
            mouth_direction > 0 ? main_l : -opening_edge_distance,
            -sub_panel_bonding_throat_w / 2,
            0
        ])
            cube([
                detent_l + boolean_shim,
                sub_panel_bonding_throat_w,
                sub_panel_bonding_nut_h
            ]);

        translate([0, 0, sub_panel_bonding_nut_h - boolean_shim])
            cylinder(
                h = sub_panel_bonding_roof_h + 2 * boolean_shim,
                d1 = sub_panel_bonding_nut_w,
                d2 = panel_screw_d
            );
    }
}

module sub_panel_bonding_screw_negative(d) {
    translate([0, 0, sub_panel_bonding_blind_floor])
        cylinder(
            h = sub_panel_h - sub_panel_bonding_blind_floor + boolean_shim,
            d = d
        );
}
```

The hex pocket and tapered transition retain the nut while avoiding an
unsupported flat roof. The main entry tunnel sweeps the full nut width from
the pocket center toward the rectangular opening, then narrows for the final
calibrated detent segment. It stops at the screw axis and never enters the far
half of the tower. The roof preserves the surface bridge between the visible
rectangular opening and vertical screw hole.

- [ ] **Step 5: Add derived XT60 and C13 placements**

Add positive placement modules:

```scad
module sub_panel_xt60_bonding_positive() {
    if (dc_connector_type == "xt60")
        for (i = [0:3], side = [-1, 1])
            translate([
                layout_offset_x + dc_channel_x(i) + dc_connector_x()
                    + side * xt60_screw_spacing / 2,
                layout_offset_y + dc_channel_y(i),
                0
            ])
                sub_panel_bonding_tower_positive();
}

module sub_panel_c13_bonding_positive() {
    for (side = [-1, 1])
        translate([
            layout_offset_x + c13_hardware_x + side * c13_screw_spacing / 2,
            layout_offset_y + c13_hardware_y,
            0
        ])
            sub_panel_bonding_tower_positive();
}
```

Call both modules in `sub_panel_8ch_positive()`.

Add matching negative placement modules. Here `side` is the screw's side of the connector and `mouth_direction = -side` always points toward the rectangular opening:

```scad
module sub_panel_xt60_bonding_negative() {
    if (dc_connector_type == "xt60")
        for (i = [0:3], side = [-1, 1])
            translate([
                dc_channel_x(i) + dc_connector_x()
                    + side * xt60_screw_spacing / 2,
                dc_channel_y(i),
                0
            ]) {
                sub_panel_bonding_nut_negative(
                    mouth_direction = -side,
                    opening_edge_distance = xt60_screw_spacing / 2
                        - xt60_cutout_w / 2
                );
                sub_panel_bonding_screw_negative(xt60_screw_d);
            }
}

module sub_panel_c13_bonding_negative() {
    for (side = [-1, 1])
        translate([
            c13_hardware_x + side * c13_screw_spacing / 2,
            c13_hardware_y,
            0
        ]) {
            sub_panel_bonding_nut_negative(
                mouth_direction = -side,
                opening_edge_distance = c13_screw_spacing / 2
                    - c13_cutout_w / 2
            );
            sub_panel_bonding_screw_negative(c13_screw_d);
        }
}
```

- [ ] **Step 6: Separate sub-panel connector openings from their new screw cutters**

The top panel continues to use `xt60_connector_negative()` and `c13_hardware_negative()` unchanged. In `sub_panel_barrel_channel_negative()`, replace the XT60 call with only its rectangular opening:

```scad
if (dc_connector_type == "xt60")
    rect_cutout(xt60_cutout_w, xt60_cutout_h);
else
    screw_hole(barrel_jack_hole_d);
```

In `sub_panel_c13_negative()`, keep only the rectangular C13 opening. Remove its old loop of through screw holes:

```scad
module sub_panel_c13_negative() {
    rect_cutout(c13_cutout_w, c13_cutout_h);
}
```

Call `sub_panel_xt60_bonding_negative();` and `sub_panel_c13_bonding_negative();` from `sub_panel_8ch_negative()` after the connector openings. Remove `sub_panel_left_xt60_nut_clearances_negative()` and its call because the new towers and captive pockets replace those clearance-only cylinders.

Also remove the obsolete `xt60_nut_clearance_d` declaration and update the
existing region-envelope calculation so it protects the complete tower:

```scad
xt60_screw_nut_radius = max(xt60_screw_d, sub_panel_bonding_tower_d) / 2;
```

- [ ] **Step 7: Verify focused contracts and exact coupon preservation**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_xt60_and_c13_towers_bond_top_to_sub_panel \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_connector_panel_views_pair_top_and_production_sub_panel_coupons \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_panel_regions_have_two_mm_gaps_and_xt60_margin \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_c13_hardware_and_service_centers_are_frozen \
  -v
```

Expected: all focused tests pass and the frozen connector axes remain unchanged.

- [ ] **Step 8: Compile all affected views to CSG**

Run each command separately:

```bash
openscad -o /tmp/plamp8-panel-bonding-sub.csg \
  -D 'view="sub_panel"' \
  -D 'revision_string="panel-bonding"' \
  things/plamp8/plamp8.scad
openscad -o /tmp/plamp8-panel-bonding-dc.csg \
  -D 'view="dc_connector_panel"' \
  -D 'revision_string="panel-bonding"' \
  things/plamp8/plamp8.scad
openscad -o /tmp/plamp8-panel-bonding-c13.csg \
  -D 'view="c13_panel"' \
  -D 'revision_string="panel-bonding"' \
  things/plamp8/plamp8.scad
```

Expected: each command exits zero, creates a non-empty CSG, and emits no warning, error, or assertion failure.

- [ ] **Step 9: Run repository-wide verification**

Run:

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m plamp cad validate plamp8 --json
.venv/bin/python -m plamp cad plan plamp8 --preset panels --revision panel-bonding --json
git diff --check
```

Expected: all tests pass, metadata is valid, the preset plans exactly two ordered jobs, and `git diff --check` prints nothing.

- [ ] **Step 10: Commit the captive tower system**

```bash
git add things/plamp8/plamp8.scad tests/test_things_cad_scripts.py
git commit -m "Bond Plamp8 top and sub-panels"
```

---

## Final handoff

Push the feature branch and retain its worktree for print feedback. On the user's workstation, generate the complete test panels with:

```bash
plamp cad plan plamp8 --preset panels --revision panel-bonding
plamp cad generate plamp8 --preset panels --revision panel-bonding
```

Use the exact `dc_connector_panel` and `c13_panel` paired coupons first if nut insertion or connector clearance needs a shorter physical check before printing both complete panels.
