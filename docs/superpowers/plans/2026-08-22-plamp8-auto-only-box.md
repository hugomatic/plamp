# Plamp8 Auto-Only Box Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add short auto-only split and fused Plamp8 enclosure products while preserving the existing toggle-equipped layout and adding the approved AC-socket relief to both modes.

**Architecture:** Add one OpenSCAD `auto_only` control-style parameter and derive wall height, connector centers, labels, and switch geometry from it. Reuse the existing printable sets for four product combinations; product metadata supplies the mode rather than duplicating CAD modules.

**Tech Stack:** OpenSCAD, Plamp CAD system JSON, Python `unittest`, managed `plamp cad` validation/planning/generation.

**Spec:** `docs/superpowers/specs/2026-08-22-plamp8-auto-only-box-design.md`

## Global Constraints

- Existing `split-box` and `fuse-box` products remain 128 mm high with unchanged connector, toggle, pocket, and label placement; the upper AC-socket relief is the only shared geometry change.
- New `split-box-auto` and `fuse-box-auto` products are 75 mm high and contain no toggle holes, switch pockets, or `Auto`/`Off`/`On` labels.
- Auto-only AC outlets, XT60 connectors, and their existing-size channel labels are centered within their own channel regions.
- The sub-panel USB support rib is relieved above each AC socket in both control styles, aligned with the existing lower socket-rim relief and the selected connector center.
- The Pico-Relay-B is modeled at its observed 18 mm height, mounted directly on the 3 mm floor.
- The AC fork-connector and wire-bend envelope extends 48 mm below the top, leaving 6 mm nominal vertical separation at 75 mm enclosure height.
- A 1N5408 remains soldered to and removable with each XT60 assembly; no diode holes, clips, sockets, or pockets are added.
- XT60-plus-diode wiring envelopes must pass through both top-panel and sub-panel XT60 openings.
- No pH electronics, pump mounting, dosing software, relay reassignment, or direction-reversal work is included.

## File Map

- `things/plamp8/plamp8.scad`: owns the mode parameter, derived dimensions and centers, conditional geometry, physical envelopes, and clearance assertions.
- `cad/plamp.system.cad.json`: owns the four enclosure product recipes and passes `auto_only=true` only for the two new products.
- `tests/test_things_cad_scripts.py`: owns repository-specific product and Plamp8 source contracts.

---

### Task 1: Four-Product Catalog Contract

**Files:**
- Modify: `tests/test_things_cad_scripts.py`
- Modify: `cad/plamp.system.cad.json`

**Interfaces:**
- Consumes: existing Plamp8 sets `floor`, `north_south_walls`, `east_west_walls`, `box`, `top_panel`, and `sub_panel`.
- Produces: products `split-box-auto` and `fuse-box-auto`; each auto product job exposes typed variable `auto_only == True`.

- [ ] **Step 1: Write the failing catalog test**

Add a focused test beside `test_plamp8_has_ready_made_panels_product`:

```python
def test_plamp8_has_four_independent_enclosure_products(self):
    system = load_system(REPO_ROOT / "cad" / "plamp.system.cad.json", REPO_ROOT)
    expected_sets = {
        "split-box": (
            "floor", "north_south_walls", "east_west_walls",
            "top_panel", "sub_panel",
        ),
        "fuse-box": ("box", "top_panel", "sub_panel"),
        "split-box-auto": (
            "floor", "north_south_walls", "east_west_walls",
            "top_panel", "sub_panel",
        ),
        "fuse-box-auto": ("box", "top_panel", "sub_panel"),
    }
    for name, set_names in expected_sets.items():
        product = system.products[name]
        self.assertEqual(tuple(item.set_name for item in product.items), set_names)
        expected_mode = name.endswith("-auto")
        self.assertTrue(all(item.variables.get("auto_only", False) is expected_mode
                            for item in product.items))
    self.assertEqual(system.default_product, "split-box")
```

- [ ] **Step 2: Run the test and verify the missing auto products fail**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_has_four_independent_enclosure_products -v
```

Expected: error or failure because `split-box-auto` is absent.

- [ ] **Step 3: Add the auto product recipes**

In `cad/plamp.system.cad.json`, leave `split-box` and `fuse-box` untouched and add:

```json
"split-box-auto": {
  "description": "Auto-only enclosure printed as separate floor, short walls, and panels",
  "items": [
    {"model": "plamp8", "set": "floor", "variables": {"auto_only": true}},
    {"model": "plamp8", "set": "north_south_walls", "variables": {"auto_only": true}},
    {"model": "plamp8", "set": "east_west_walls", "variables": {"auto_only": true}},
    {"model": "plamp8", "set": "top_panel", "variables": {"auto_only": true}},
    {"model": "plamp8", "set": "sub_panel", "variables": {"auto_only": true}}
  ]
},
"fuse-box-auto": {
  "description": "Auto-only enclosure printed as a fused short box with separate panels",
  "items": [
    {"model": "plamp8", "set": "box", "variables": {"auto_only": true}},
    {"model": "plamp8", "set": "top_panel", "variables": {"auto_only": true}},
    {"model": "plamp8", "set": "sub_panel", "variables": {"auto_only": true}}
  ]
}
```

- [ ] **Step 4: Run catalog and metadata tests**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_has_four_independent_enclosure_products tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp_system_catalog_has_migrated_products tests.test_cad_system -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit the catalog contract**

```bash
git add cad/plamp.system.cad.json tests/test_things_cad_scripts.py
git commit -m "Add Plamp8 auto-only enclosure products"
```

---

### Task 2: Auto-Only Panel Layout And Short Enclosure

**Files:**
- Modify: `tests/test_things_cad_scripts.py`
- Modify: `things/plamp8/plamp8.scad`

**Interfaces:**
- Consumes: product variable `auto_only` and existing channel-region dimensions.
- Produces: functions `ac_connector_x()`, `dc_connector_x()`, and `dc_label_x()` plus derived `wall_z_height`; manual mode returns all legacy coordinates exactly.

- [ ] **Step 1: Write failing source-contract tests**

Add a new Plamp8 test:

```python
def test_plamp8_auto_only_mode_controls_height_switches_and_centers(self):
    source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
    compact = compact_scad(source)
    self.assertIn("auto_only=false;", compact)
    self.assertIn("wall_z_height=auto_only?auto_wall_z_height:manual_wall_z_height;", compact)
    self.assertIn("functionac_connector_x()=auto_only?", compact)
    self.assertIn("functiondc_connector_x()=auto_only?", compact)
    self.assertIn("functiondc_label_x()=auto_only?dc_connector_x():manual_dc_label_x;", compact)
    self.assertIn("manual_wall_z_height=128;", compact)
    self.assertIn("auto_wall_z_height=75;", compact)
    self.assertIn("manual_ac_connector_x=outlet_feature_x;", compact)
    self.assertIn("manual_dc_label_x=barrel_label_x;", compact)

    outlet_negative = compact_scad(scad_module_body(source, "outlet_cover_negative"))
    barrel_negative = compact_scad(scad_module_body(source, "barrel_channel_negative"))
    sub_panel = compact_scad(scad_module_body(source, "sub_panel_8ch_negative"))
    top_panel = compact_scad(scad_module_body(source, "top_panel_8ch"))
    writings = compact_scad(scad_module_body(source, "positive_plate_writings"))
    self.assertIn("if(!auto_only)", outlet_negative)
    self.assertIn("if(!auto_only)", barrel_negative)
    self.assertIn("if(!auto_only)", sub_panel)
    self.assertIn("if(!auto_only)", top_panel)
    self.assertIn("if(!auto_only)", writings)
```

- [ ] **Step 2: Run the source-contract test and verify it fails**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_auto_only_mode_controls_height_switches_and_centers -v
```

Expected: failure because `auto_only` and the derived placement helpers do not exist.

- [ ] **Step 3: Add mode and derived dimensions**

Near the top-level Customizer parameters, add:

```scad
auto_only = false;
manual_wall_z_height = 128;
auto_wall_z_height = 75;
wall_z_height = auto_only ? auto_wall_z_height : manual_wall_z_height;
```

Replace the old literal `wall_z_height = 128`. Keep legacy coordinate constants and add helper functions near the existing DC placement helpers:

```scad
manual_ac_connector_x = outlet_feature_x;
manual_dc_label_x = barrel_label_x;

function ac_connector_x() = auto_only
    ? (outlet_feature_x + outlet_toggle_x) / 2
    : manual_ac_connector_x;
function dc_connector_x() = auto_only
    ? barrel_group_x
    : (dc_connector_type == "xt60"
        ? dc_toggle_x() - xt60_switch_center_spacing
        : barrel_jack_x);
function dc_label_x() = auto_only ? dc_connector_x() : manual_dc_label_x;
```

Use `ac_connector_x()` for outlet cutouts, outlet labels, sub-panel socket openings, socket screws, and socket relief. Use `dc_label_x()` for the four top-panel labels and DC coupon label. Preserve all label font sizes.

Add an upper relief cutter for the USB support rib. It must use
`ac_connector_x()` and `sub_panel_socket_rim_relief_w`, cross the complete
rib width, and cut only the rib height above `sub_panel_base_h`:

```scad
module sub_panel_socket_usb_rib_relief_negative() {
    lip_h = sub_panel_h - sub_panel_base_h;

    for (x = [left_ac_x, right_ac_x])
        translate([
            x + ac_connector_x() - sub_panel_socket_rim_relief_w / 2,
            layout_offset_y + sub_panel_usb_support_rib_y
                - sub_panel_usb_support_rib_w / 2 - boolean_shim,
            sub_panel_base_h - boolean_shim
        ])
            cube([
                sub_panel_socket_rim_relief_w,
                sub_panel_usb_support_rib_w + 2 * boolean_shim,
                lip_h + 2 * boolean_shim
            ]);
}
```

Call this cutter from `sub_panel_8ch_negative()` beside
`sub_panel_socket_bottom_rim_relief_negative()`. Update the lower cutter to
use `ac_connector_x()` as well, ensuring both reliefs follow manual and
auto-only connector placement.

- [ ] **Step 4: Guard every switch-only feature**

Wrap toggle holes, sub-panel switch rectangles, and state-label calls in the relevant modules:

```scad
if (!auto_only)
    for (y = [-outlet_spacing / 2, outlet_spacing / 2])
        translate([outlet_toggle_x, y, 0])
            screw_hole(toggle_hole_d);
```

Apply the same `if (!auto_only)` condition to:

- AC `toggle_state_labels()` calls in `positive_plate_writings()`;
- the DC toggle hole in `barrel_channel_negative()`;
- DC `toggle_state_labels()` calls in `dc_connector_panel_unit()` and `top_panel_8ch()`;
- AC switch pockets in `sub_panel_8ch_negative()`;
- the DC switch pocket in `sub_panel_barrel_channel_negative()`.

Extend the source-contract test with:

```python
self.assertIn("modulesub_panel_socket_usb_rib_relief_negative()", compact)
self.assertIn("x+ac_connector_x()-sub_panel_socket_rim_relief_w/2", compact)
self.assertIn("sub_panel_socket_usb_rib_relief_negative();", sub_panel)
self.assertIn("sub_panel_socket_bottom_rim_relief_negative();", sub_panel)
```

Update hardware-bound and separator calculations so auto-only mode excludes switch bodies from `dc_hardware_left_x`, `dc_hardware_right_x`, and related cutter envelopes. Assertions must evaluate the geometry present in the selected mode.

- [ ] **Step 5: Run focused and full source tests**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_auto_only_mode_controls_height_switches_and_centers -v
/home/hugo/.local/bin/uv run python -m unittest tests.test_things_cad_scripts -v
```

Expected: all tests pass; legacy Plamp8 source-contract tests remain green.

- [ ] **Step 6: Commit panel and enclosure geometry**

```bash
git add things/plamp8/plamp8.scad tests/test_things_cad_scripts.py
git commit -m "Add Plamp8 auto-only enclosure geometry"
```

---

### Task 3: Relay, AC Harness, And XT60 Service Envelopes

**Files:**
- Modify: `tests/test_things_cad_scripts.py`
- Modify: `things/plamp8/plamp8.scad`

**Interfaces:**
- Consumes: `auto_only`, `wall_z_height`, `plate_t`, and centered connector functions from Task 2.
- Produces: measured `relay_h = 18`, `ac_harness_depth = 48`, `auto_vertical_clearance = 6`, an XT60 removable-assembly envelope, and assembly assertions/preview geometry.

- [ ] **Step 1: Write failing measured-clearance tests**

Add a new test:

```python
def test_plamp8_auto_only_has_measured_service_envelopes(self):
    source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
    compact = compact_scad(source)
    for declaration in (
        "relay_h=18;",
        "ac_harness_depth=48;",
        "auto_vertical_clearance=auto_wall_z_height-plate_t-relay_h-ac_harness_depth;",
        "assert(auto_vertical_clearance>=6",
        "moduleac_harness_keepout()",
        "modulext60_removable_assembly_keepout()",
    ):
        self.assertIn(declaration, compact)

    assembly = compact_scad(scad_module_body(source, "internal_components"))
    self.assertIn("ac_harness_keepout();", assembly)
    self.assertIn("xt60_removable_assembly_keepout();", assembly)
```

- [ ] **Step 2: Run the measured-clearance test and verify it fails**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_auto_only_has_measured_service_envelopes -v
```

Expected: failure because the relay still uses the old 40 mm planning envelope and the service envelopes are absent.

- [ ] **Step 3: Encode the measured vertical clearance**

Replace `relay_h = 40` with `relay_h = 18` and add:

```scad
ac_harness_depth = 48;
auto_vertical_clearance =
    auto_wall_z_height - plate_t - relay_h - ac_harness_depth;
assert(
    auto_vertical_clearance >= 6,
    "auto-only relay-to-AC-harness clearance fell below 6 mm"
);
```

Keep the relay on the floor using the existing `-box_h + wall_t` assembly translation. Do not add a component lift.

- [ ] **Step 4: Add preview-only service envelopes**

Create translucent keepout modules sized from existing socket and XT60 dimensions:

```scad
module ac_harness_keepout() {
    color([0.85, 0.35, 0.1, 0.25])
        translate([0, 0, -ac_harness_depth / 2])
            cube([sub_panel_socket_w, sub_panel_socket_h,
                  ac_harness_depth], center = true);
}

module xt60_removable_assembly_keepout() {
    xt60_service_depth = 24;
    color([0.95, 0.75, 0.1, 0.25])
        translate([0, 0, -xt60_service_depth / 2])
            cube([xt60_cutout_w, xt60_cutout_h,
                  xt60_service_depth], center = true);
}
```

In `internal_components()`, show AC keepouts at all four `ac_connector_x()` locations and XT60 keepouts at all four `dc_connector_x()` locations when `auto_only && $preview`. The XT60 envelope must be no wider or taller than the shared top/sub-panel pass-through opening; it represents the insulated diode tucked behind the removable connector, not a fixed enclosure feature.

- [ ] **Step 5: Run source and repository tests**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_auto_only_has_measured_service_envelopes -v
/home/hugo/.local/bin/uv run python -m unittest discover -s tests -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit service-envelope geometry**

```bash
git add things/plamp8/plamp8.scad tests/test_things_cad_scripts.py
git commit -m "Model Plamp8 auto-only service clearances"
```

---

### Task 4: CAD Planning, Rendering, And Visual Verification

**Files:**
- Modify only if verification exposes a defect: `things/plamp8/plamp8.scad`, `cad/plamp.system.cad.json`, `tests/test_things_cad_scripts.py`
- Do not commit generated STL files, manifests, logs, or archived sources.

**Interfaces:**
- Consumes: all four enclosure products and the complete CAD source contract.
- Produces: validated plans and managed render evidence for both auto-only construction styles, plus regression evidence for manual products.

- [ ] **Step 1: Validate metadata**

Run:

```bash
/home/hugo/.local/bin/uv run plamp cad validate plamp8 --json
```

Expected: valid model metadata with no unknown sets or variables.

- [ ] **Step 2: Plan all four products**

Run each command and inspect `jobs[].set_name` and `jobs[].variables.auto_only`:

```bash
/home/hugo/.local/bin/uv run plamp cad plan --system plamp --product split-box --json
/home/hugo/.local/bin/uv run plamp cad plan --system plamp --product fuse-box --json
/home/hugo/.local/bin/uv run plamp cad plan --system plamp --product split-box-auto --json
/home/hugo/.local/bin/uv run plamp cad plan --system plamp --product fuse-box-auto --json
```

Expected: manual jobs omit or set `auto_only` false; every auto job sets it true. Split products contain five jobs and fused products contain three.

- [ ] **Step 3: Generate the two auto-only products**

Use an honest revision label if the Plamp8 source is dirty:

```bash
/home/hugo/.local/bin/uv run plamp cad generate --system plamp --product split-box-auto --revision auto-only-fit-1 --json
/home/hugo/.local/bin/uv run plamp cad generate --system plamp --product fuse-box-auto --revision auto-only-fit-1 --json
```

Expected: all eight total jobs complete and produce non-empty STLs in managed run archives.

- [ ] **Step 4: Inspect every render log and artifact**

For each returned run ID, use:

```bash
/home/hugo/.local/bin/uv run plamp cad show RUN_ID --json
/home/hugo/.local/bin/uv run plamp cad log RUN_ID ARTIFACT_ID --json
```

Substitute identifiers from the generation output. Expected: no missing includes, OpenSCAD errors, empty geometry, or failed jobs. Confirm the archived source snapshot exists.

- [ ] **Step 5: Inspect rendered geometry**

Export preview images or inspect the STLs and confirm:

- both auto enclosures are 75 mm high;
- every AC and XT60 connector and its label is centered in its channel;
- no toggle holes, switch pockets, or state labels remain;
- lower socket-rim and upper USB-support-rib reliefs align with every AC socket in both modes;
- mounting holes, connector retention, corner fasteners, and panel access remain intact;
- AC and XT60 service envelopes do not intersect the 18 mm relay envelope;
- the XT60 keepout passes through both panel openings and does not trap the connector assembly.

- [ ] **Step 6: Plan or render manual regression products**

At minimum, repeat the plan commands for `split-box` and `fuse-box`. Render `top_panel`, `sub_panel`, and one wall or fused box with `auto_only=false` if source inspection cannot prove legacy placement. Expected: 128 mm height and unchanged toggle-equipped geometry.

- [ ] **Step 7: Run final verification**

```bash
git diff --check
/home/hugo/.local/bin/uv run python -m unittest discover -s tests -v
git status --short
```

Expected: no whitespace errors, all tests pass, and only intentional source changes remain.

- [ ] **Step 8: Commit any verification fixes**

If verification required source corrections:

```bash
git add things/plamp8/plamp8.scad cad/plamp.system.cad.json tests/test_things_cad_scripts.py
git commit -m "Verify Plamp8 auto-only enclosure output"
```

If no correction was required, do not create an empty commit.

- [ ] **Step 9: Record the physical-fit gate in the handoff**

Report that a full production print remains gated on a dry fit using one AC socket harness, the floor-mounted Pico-Relay-B, and one XT60 with an insulated 1N5408 soldered across its terminals. Confirm that the connector-plus-diode assembly can be removed through both panel openings.
