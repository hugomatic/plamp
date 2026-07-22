# Plamp8 Flat Connector Panels Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the four Plamp8 connector fit views consistently as panels and make each coupon a flat, support-free plate that retains at least 3 mm around every recessed rounded pocket.

**Architecture:** Keep the change inside the existing Plamp8 SCAD document and its source-contract tests. First make the public view rename as an intentional breaking change, then derive standalone coupon bounds from their pocket envelopes, remove underside alignment walls, and protect the confirmed XT60 fit with frozen assertions and tests. Production enclosure geometry continues to reuse its existing negative modules and is not resized.

**Tech Stack:** OpenSCAD, embedded `generate.json` CAD metadata, Python `unittest`, Plamp CAD CLI.

## Global Constraints

- Canonical connector views are `ac_duplex_panel`, `dc_connector_panel`, `usb_c_panel`, and `c13_panel`.
- Do not retain compatibility aliases for `ac_duplex_channel`, `dc_barrel_channel`, or `c13_inlet`.
- Every connector coupon is a flat `plate_t`-thick solid beginning at Z=0 with no underside alignment walls.
- Every complete recessed rounded pocket, including revision pockets, retains at least 3 mm of plate on all four sides.
- Preserve the confirmed XT60 19 by 12 mm cutout, 25 mm screw spacing, 3.2 mm screw holes, and current connector-to-toggle spacing and position.
- Do not change production top-panel, sub-panel, box, wall, or assembly geometry.
- Generated STL, CSG, manifests, logs, and archives remain untracked instance data.

---

## File map

- Modify `things/plamp8/plamp8.scad`: public view names, preset metadata, flat coupon geometry, derived pocket bounds, rim assertions, and final dispatch.
- Modify `tests/test_cad_recipes.py`: exact Plamp8 preset expansion contract for the breaking view rename.
- Modify `tests/test_things_cad_scripts.py`: source contracts for canonical view names, flat coupon positives, 3 mm rims, and frozen XT60 dimensions.

### Task 1: Rename connector fit views and preset entries

**Files:**
- Modify: `things/plamp8/plamp8.scad:5-53,2742-2755,2947-2955`
- Modify: `tests/test_cad_recipes.py:100-175`
- Modify: `tests/test_things_cad_scripts.py`

**Interfaces:**
- Consumes: the canonical Customizer view list and embedded `generate.json` metadata in `plamp8.scad`.
- Produces: public views `ac_duplex_panel`, `dc_connector_panel`, `usb_c_panel`, and `c13_panel`; a `top-panel-fit` preset ordered exactly the same way.

- [ ] **Step 1: Update recipe expectations before production code**

Change the `top-panel-fit` and nested `test-fit` tuples in `test_plamp8_recipe_catalog_matches_print_workflows`:

```python
"top-panel-fit": (
    "ac_duplex_panel", "dc_connector_panel", "usb_c_panel", "c13_panel",
),
"test-fit": (
    "relay_footprint", "psu_footprint", "converter_footprint",
    "ac_duplex_panel", "dc_connector_panel", "usb_c_panel", "c13_panel",
    "panel_corner_fastener_test", "corner_coupon",
    "wall_corner_fastener_assembly",
),
```

Add this source-contract test to `ThingsCadScriptsTest`:

```python
def test_plamp8_connector_fit_views_use_panel_names(self):
    source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()

    for name in (
        "ac_duplex_panel", "dc_connector_panel", "usb_c_panel", "c13_panel",
    ):
        with self.subTest(name=name):
            self.assertIn(f'view == "{name}"', source)
            self.assertIn(f'module {name}()', source)

    for retired in ("ac_duplex_channel", "dc_barrel_channel", "c13_inlet"):
        with self.subTest(retired=retired):
            self.assertNotIn(f'view == "{retired}"', source)
            self.assertNotIn(f'module {retired}()', source)

    self.assertIn(
        '"items": ["view:ac_duplex_panel", "view:dc_connector_panel", '
        '"view:usb_c_panel", "view:c13_panel"]',
        source,
    )
```

- [ ] **Step 2: Run the renamed-view tests and observe the expected failures**

Run:

```bash
UV_CACHE_DIR=/tmp/uv-cache /home/hugo/.local/bin/uv run --locked python -m unittest \
  tests.test_cad_recipes.CadRecipeTests.test_plamp8_recipe_catalog_matches_print_workflows \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_connector_fit_views_use_panel_names -v
```

Expected: both tests fail because `plamp8.scad` still declares and dispatches the retired view names.

- [ ] **Step 3: Rename the public views, wrappers, metadata, and preset**

In the Customizer view list and embedded metadata, replace the retired names with:

```scad
ac_duplex_panel
dc_connector_panel
c13_panel
```

Keep `usb_c_panel` unchanged. Change the `top-panel-fit` preset to:

```json
"top-panel-fit": {
  "description": "Top-panel connector fit tests",
  "items": ["view:ac_duplex_panel", "view:dc_connector_panel", "view:usb_c_panel", "view:c13_panel"]
}
```

Rename only the standalone coupon unit/wrapper symbols:

```scad
module dc_connector_panel_unit(device = "PH Up", detail = "CH5 GP17 12V DC", include_revision = true) {
    // Existing body; Task 2 changes its positive geometry.
}

module ac_duplex_panel() {
    outlet_cover(true, ac_devices[0], ac_details[0], ac_devices[1], ac_details[1]);
}

module dc_connector_panel() {
    dc_connector_panel_unit(dc_devices[0], dc_details[0], true);
}

module c13_panel() {
    c13_inlet_unit(true);
}
```

Update final dispatch:

```scad
} else if (view == "ac_duplex_panel") {
    ac_duplex_panel();
} else if (view == "dc_connector_panel") {
    dc_connector_panel();
} else if (view == "usb_c_panel") {
    usb_c_panel();
} else if (view == "c13_panel") {
    c13_panel();
```

Do not rename `barrel_channel_negative`, `dc_channel_x`, or other production channel-layout symbols.

- [ ] **Step 4: Run the focused rename tests**

Run the command from Step 2 again.

Expected: both tests pass; the recipe test still reports 17 jobs for `all-presets`.

- [ ] **Step 5: Commit the breaking view rename**

```bash
git add things/plamp8/plamp8.scad tests/test_cad_recipes.py tests/test_things_cad_scripts.py
git diff --cached --check
git commit -m "Rename Plamp8 connector fit views"
```

### Task 2: Make every connector coupon flat with a 3 mm pocket rim

**Files:**
- Modify: `things/plamp8/plamp8.scad:100-235,640-655,747-810,981-1215`
- Modify: `tests/test_things_cad_scripts.py:900-950,1165-1220`

**Interfaces:**
- Consumes: renamed coupon wrapper `dc_connector_panel_unit(...)` from Task 1 and existing `fit_plate(w, h)`, `label_pocket(w, h)`, and connector-negative modules.
- Produces: `connector_panel_rim = 3`, derived DC coupon bounds, flat DC/C13 positives, rim assertions for AC/DC/USB-C/C13, and unchanged production cutter modules.

- [ ] **Step 1: Add failing flatness, rim, and XT60 fit contracts**

Add this test to `ThingsCadScriptsTest`:

```python
def test_plamp8_connector_panels_are_flat_and_retain_three_mm_rims(self):
    source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
    compact = compact_scad(source)
    dc_unit = compact_scad(scad_module_body(source, "dc_connector_panel_unit"))
    c13_unit = compact_scad(scad_module_body(source, "c13_inlet_unit"))

    self.assertIn("connector_panel_rim = 3;", source)
    self.assertNotIn("module alignment_walls", source)
    self.assertNotIn("alignment_walls(", dc_unit)
    self.assertNotIn("alignment_walls(", c13_unit)
    self.assertIn(
        "translate([dc_connector_panel_center_x,dc_connector_panel_center_y,0])"
        "fit_plate(dc_connector_panel_w,dc_connector_panel_h);",
        dc_unit,
    )
    self.assertIn("fit_plate(c13_panel_w,c13_panel_h);", c13_unit)

    for assertion in (
        'assert(ac_connector_panel_rim_ok,"ACconnectorpanelmustretain3mmaroundeveryroundedpocket");',
        'assert(dc_connector_panel_rim_ok,"DCconnectorpanelmustretain3mmaroundeveryroundedpocket");',
        'assert(usb_coupon_pocket_inside_plate,"USBcouponmustretain3mmaroundeveryroundedpocket");',
        'assert(c13_connector_panel_rim_ok,"C13connectorpanelmustretain3mmaroundeveryroundedpocket");',
    ):
        self.assertIn(assertion, compact)

    for frozen in (
        "xt60_cutout_w = 19;", "xt60_cutout_h = 12;",
        "xt60_screw_spacing = 25;", "xt60_screw_d = 3.2;",
    ):
        self.assertIn(frozen, source)
    self.assertIn(
        "xt60_switch_center_spacing = xt60_outside_w / 2 + "
        "dc_switch_outside_d / 2 + xt60_switch_clearance;",
        source,
    )
```

Update `test_plamp8_panel_regions_have_two_mm_gaps_and_xt60_margin` to stop requiring `barrel_channel_w = dc_region_w;` if that coupon-only declaration is removed or renamed.

- [ ] **Step 2: Run the new geometry contract and observe failure**

Run:

```bash
UV_CACHE_DIR=/tmp/uv-cache /home/hugo/.local/bin/uv run --locked python -m unittest \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_connector_panels_are_flat_and_retain_three_mm_rims \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_panel_regions_have_two_mm_gaps_and_xt60_margin \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_usb_com_fit_dimensions_and_panel_cutouts -v
```

Expected: the new test fails because the shared rim and derived panel assertions do not exist and DC/C13 still call `alignment_walls()`.

- [ ] **Step 3: Define the shared rim and pocket-derived panel bounds**

Place the shared rim immediately after `plate_t` so every later coupon declaration can use it:

```scad
plate_t = 3;
connector_panel_rim = 3;
```

Move the AC coupon-bound declarations below `outlet_group_x`, `outlet_group_w`, `outlet_group_h`, and `screw_spacing`, then derive the left extent while retaining its existing extra right-side material. This ordering is required so OpenSCAD does not evaluate a forward reference as `undef`:

```scad
outlet_plate_left = outlet_group_w / 2 - outlet_group_x + connector_panel_rim;
outlet_plate_right = 76;
plate_h = 120;
outlet_pocket_y = screw_spacing / 2 - 13;
```

Replace `usb_c_panel_rim` uses with `connector_panel_rim`:

```scad
usb_c_panel_w = service_group_w + 2 * connector_panel_rim;
usb_c_panel_h = service_group_h + 2 * connector_panel_rim;
```

After `revision_label_w` and `revision_label_h` are defined, derive the offset DC plate from the union of its main and revision rounded-pocket envelopes:

```scad
dc_connector_panel_revision_y = barrel_channel_h / 2 - 9;
dc_connector_panel_left_x = barrel_group_x - barrel_group_w / 2 - connector_panel_rim;
dc_connector_panel_right_x = barrel_group_x + barrel_group_w / 2 + connector_panel_rim;
dc_connector_panel_bottom_y = barrel_group_y - barrel_group_h / 2 - connector_panel_rim;
dc_connector_panel_top_y = max(
    barrel_group_y + barrel_group_h / 2,
    dc_connector_panel_revision_y + revision_label_h / 2
) + connector_panel_rim;
dc_connector_panel_w = dc_connector_panel_right_x - dc_connector_panel_left_x;
dc_connector_panel_h = dc_connector_panel_top_y - dc_connector_panel_bottom_y;
dc_connector_panel_center_x = (dc_connector_panel_left_x + dc_connector_panel_right_x) / 2;
dc_connector_panel_center_y = (dc_connector_panel_bottom_y + dc_connector_panel_top_y) / 2;
```

Declare `c13_group_w` and `c13_group_h` before the C13 panel dimensions, then preserve the C13 revision position while increasing the vertical rim from 2 to 3 mm:

```scad
c13_group_w = 58;
c13_group_h = 64;
c13_panel_w = 72;
c13_panel_h = c13_group_h + 2 * connector_panel_rim;
c13_revision_y = 26;
```

- [ ] **Step 4: Add explicit rim booleans and assertions**

Define booleans from actual plate and rounded-pocket edges. The comparisons must include every side:

```scad
ac_connector_panel_rim_ok =
    -outlet_plate_left <= outlet_group_x - outlet_group_w / 2 - connector_panel_rim
    && outlet_plate_right >= outlet_group_x + outlet_group_w / 2 + connector_panel_rim
    && -plate_h / 2 <= -outlet_pocket_y - outlet_group_h / 2 - connector_panel_rim
    && plate_h / 2 >= outlet_pocket_y + outlet_group_h / 2 + connector_panel_rim;
dc_connector_panel_rim_ok =
    dc_connector_panel_left_x <= barrel_group_x - barrel_group_w / 2 - connector_panel_rim
    && dc_connector_panel_right_x >= barrel_group_x + barrel_group_w / 2 + connector_panel_rim
    && dc_connector_panel_bottom_y <= barrel_group_y - barrel_group_h / 2 - connector_panel_rim
    && dc_connector_panel_top_y >= dc_connector_panel_revision_y + revision_label_h / 2 + connector_panel_rim;
usb_coupon_pocket_inside_plate =
    service_group_w + 2 * connector_panel_rim <= usb_c_panel_w
    && service_group_h + 2 * connector_panel_rim <= usb_c_panel_h;
c13_connector_panel_rim_ok =
    c13_group_w + 2 * connector_panel_rim <= c13_panel_w
    && c13_group_h + 2 * connector_panel_rim <= c13_panel_h
    && c13_revision_y + revision_label_h / 2 + connector_panel_rim <= c13_panel_h / 2;
```

Add the four exact assertion messages required by Step 1. Also freeze the measured DC panel values without replacing the production XT60 contracts:

```scad
assert(dc_connector_panel_left_x == -35 && dc_connector_panel_right_x == 45
        && dc_connector_panel_bottom_y == -32 && dc_connector_panel_top_y == 27.5,
    "DC connector panel bounds must follow the rounded-pocket envelope");
```

- [ ] **Step 5: Remove underside walls and use the derived flat plates**

Delete `alignment_wall_h`, `alignment_wall_t`, and `module alignment_walls(...)` after confirming no remaining call sites.

Make the DC positive a single translated plate while preserving all hole, label, toggle, and revision coordinates:

```scad
module dc_connector_panel_unit(device = "PH Up", detail = "CH5 GP17 12V DC", include_revision = true) {
    difference() {
        translate([dc_connector_panel_center_x, dc_connector_panel_center_y, 0])
            fit_plate(dc_connector_panel_w, dc_connector_panel_h);
        barrel_channel_negative();
        if (include_revision)
            barrel_revision_negative();
    }

    translate([barrel_label_x, -barrel_channel_h / 2 + 11, 0])
        flush_two_line_label(device, detail, 5.3, 4.1, 6);
    translate([dc_toggle_x() + toggle_label_x_offset, 0, 0])
        toggle_state_labels();
    if (include_revision)
        translate([0, dc_connector_panel_revision_y, 0])
            flush_revision_label();
}
```

Use `dc_connector_panel_revision_y` in `barrel_revision_negative()`.

Make C13 a single flat plate and preserve its revision center:

```scad
module c13_revision_negative() {
    translate([0, c13_revision_y, 0])
        label_pocket(revision_label_w, revision_label_h);
}

module c13_inlet_unit(include_revision = true) {
    difference() {
        fit_plate(c13_panel_w, c13_panel_h);
        c13_inlet_negative();
        if (include_revision)
            c13_revision_negative();
    }

    if (include_revision)
        translate([0, c13_revision_y, 0])
            flush_revision_label();
}
```

In `outlet_cover_negative`, replace local `h_y` with `outlet_pocket_y` so the assertion and geometry share one source of truth.

- [ ] **Step 6: Run the focused geometry tests**

Run the command from Step 2 again.

Expected: all three tests pass, including the pre-existing USB-C fit and production-region contracts.

- [ ] **Step 7: Run all Plamp8 source-contract tests**

```bash
UV_CACHE_DIR=/tmp/uv-cache /home/hugo/.local/bin/uv run --locked python -m unittest tests.test_things_cad_scripts -v
```

Expected: all Plamp8 and general `things/` CAD source-contract tests pass.

- [ ] **Step 8: Commit the flat coupon geometry**

```bash
git add things/plamp8/plamp8.scad tests/test_things_cad_scripts.py
git diff --cached --check
git commit -m "Flatten Plamp8 connector fit panels"
```

### Task 3: Validate, compile, and publish the connector panels

**Files:**
- Verify: `things/plamp8/plamp8.scad`
- Verify: `tests/test_cad_recipes.py`
- Verify: `tests/test_things_cad_scripts.py`

**Interfaces:**
- Consumes: the four canonical flat panel views from Tasks 1 and 2.
- Produces: validated metadata, a four-job `top-panel-fit` plan, non-empty CSG output for every panel, passing repository tests, and a pushed review branch.

- [ ] **Step 1: Validate metadata and plan the renamed preset**

```bash
./bin/plamp cad validate plamp8 --json
./bin/plamp cad plan plamp8 --preset top-panel-fit --revision flat-connector-panels --json
```

Expected: validation returns `"valid": true`; the plan returns four jobs ordered `ac_duplex_panel`, `dc_connector_panel`, `usb_c_panel`, `c13_panel`.

- [ ] **Step 2: Compile each panel through the fast OpenSCAD CSG gate**

```bash
/usr/bin/openscad -o /tmp/plamp8-ac-duplex-panel.csg -D 'revision_string="flat-connector-panels"' -D 'view="ac_duplex_panel"' things/plamp8/plamp8.scad
/usr/bin/openscad -o /tmp/plamp8-dc-connector-panel.csg -D 'revision_string="flat-connector-panels"' -D 'view="dc_connector_panel"' things/plamp8/plamp8.scad
/usr/bin/openscad -o /tmp/plamp8-usb-c-panel.csg -D 'revision_string="flat-connector-panels"' -D 'view="usb_c_panel"' things/plamp8/plamp8.scad
/usr/bin/openscad -o /tmp/plamp8-c13-panel.csg -D 'revision_string="flat-connector-panels"' -D 'view="c13_panel"' things/plamp8/plamp8.scad
test -s /tmp/plamp8-ac-duplex-panel.csg
test -s /tmp/plamp8-dc-connector-panel.csg
test -s /tmp/plamp8-usb-c-panel.csg
test -s /tmp/plamp8-c13-panel.csg
```

Expected: every command exits 0, every CSG is non-empty, and output contains no warning, error, or failed assertion.

- [ ] **Step 3: Run the complete repository test suite and diff checks**

```bash
UV_CACHE_DIR=/tmp/uv-cache /home/hugo/.local/bin/uv run --locked python -m unittest discover -s tests -q
git diff --check origin/main...HEAD
```

Expected: all tests pass and the diff check prints nothing.

- [ ] **Step 4: Push the branch for user rendering and review**

```bash
git push -u origin feature/plamp8-flat-connector-panels
```

Expected: GitHub accepts the branch. Report the branch link, exact commit, validation/test counts, and these workstation render commands:

```bash
plamp cad plan plamp8 --preset top-panel-fit
plamp cad generate plamp8 --preset top-panel-fit
```

The user verifies the generated STLs lie flat, slice without support, retain visible 3 mm pocket rims, and preserve the confirmed XT60 fit.
