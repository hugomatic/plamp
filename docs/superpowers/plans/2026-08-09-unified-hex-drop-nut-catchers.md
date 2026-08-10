# Unified Hex-Drop Nut Catchers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every Plamp8 nut catcher use one shared tunnel-and-hex geometry with an adjustable drop proportional to nominal nut thickness.

**Architecture:** `m3_nut_catcher_negative()` remains the only module that constructs catcher geometry. It derives a local tunnel elevation from `nut_thickness * drop_fraction`; production wrappers may orient that module but may not replace or bypass its pocket, tunnel, drop, or roof logic.

**Tech Stack:** OpenSCAD 2021.01, Python `unittest`, Plamp CAD CLI.

## Global Constraints

- Default `nut_drop_fraction` is `1 / 2`.
- Calculate drop from nominal nut thickness, never tunnel clearance.
- Apply the proportional drop to every production catcher.
- Retain `"flat"` and `"30deg"` roof modes in the shared module.
- Preserve family-specific tunnel width and thickness clearances.
- Preserve screw axes and hex-pocket locations.
- Default the clearance matrix to `[-0.1, 0, 0.1]` mm on each axis for a 3×3 test.

---

### Task 1: Unify the proportional hex drop

**Files:**
- Modify: `tests/test_things_cad_scripts.py`
- Modify: `things/plamp8/plamp8.scad`

**Interfaces:**
- Consumes: `m3_nut_thickness`, caller-supplied `nut_thickness`, and the existing `roof_mode`, tunnel-width, tunnel-height, clearance, nib, direction, and opening-distance parameters.
- Produces: global `nut_drop_fraction = 1 / 2`; module parameter `drop_fraction = nut_drop_fraction`; local `nut_drop = nut_thickness * drop_fraction`; one shared catcher negative used by corner, panel, sub-panel, and coupon callers.

- [ ] **Step 1: Write the failing structural test**

Update the Plamp8 catcher test to require these source-level contracts:

```python
self.assertIn("nut_drop_fraction=1/2;", compact)
self.assertNotIn("corner_nut_drop", compact)
self.assertIn("drop_fraction=nut_drop_fraction", catcher)
self.assertIn("nut_drop=nut_thickness*drop_fraction", catcher)
self.assertIn("-effective_tunnel_w/2,nut_drop])", catcher)
self.assertIn("-effective_entry_mouth_w/2,nut_drop])", catcher)
self.assertIn(
    "translate([tunnel_roof_x,0,nut_drop+effective_tunnel_h])",
    catcher,
)
self.assertNotIn("entry_tunnel_z_offset", compact)
self.assertNotIn("drop_fraction=", corner)
self.assertNotIn("drop_fraction=", panel)
self.assertNotIn("drop_fraction=", coupon)
```

Keep the existing assertions that the corner tunnel is wider, corner nibs are disabled, panel nibs remain enabled, and both roof modes remain present.

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
python -m unittest tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_corner_nut_entry_uses_roomy_tunnel_and_snug_pocket -v
```

Expected: `FAIL` because `nut_drop_fraction`, `drop_fraction`, and the derived `nut_drop` do not yet exist.

- [ ] **Step 3: Implement the shared proportional drop**

In `things/plamp8/plamp8.scad`, replace the corner-only absolute parameter with:

```scad
nut_drop_fraction = 1 / 2;
```

Change the shared module parameter and derived value to:

```scad
module m3_nut_catcher_negative(
    nut_across_flats = m3_nut_across_flats,
    nut_thickness = m3_nut_thickness,
    width_clearance = panel_nut_width_clearance,
    thick_clearance = panel_nut_thickness_clearance,
    nib_height = panel_nut_floor_nib_h,
    roof_mode = "30deg",
    direction = 1,
    opening_edge_distance = panel_nut_entry_l,
    entry_detent = panel_nut_entry_detent,
    entry_detent_l = panel_nut_entry_detent_l,
    entry_mouth_w = undef,
    entry_tunnel_w = undef,
    entry_tunnel_h = undef,
    drop_fraction = nut_drop_fraction
) {
    nut_drop = nut_thickness * drop_fraction;
```

Use `nut_drop` as the local Z origin of the main tunnel and mouth. Start the pointy tunnel roof at `nut_drop + effective_tunnel_h`. Keep the hex cylinder and pointy pocket roof at their existing position.

Remove `entry_tunnel_z_offset` from the module and all callers. Remove the corner-only `corner_nut_drop`. Because every caller reaches `m3_nut_catcher_negative()`, its default proportional drop then applies uniformly; orientation wrappers remain transform-only.

- [ ] **Step 4: Run focused and complete tests and verify GREEN**

Run:

```bash
python -m unittest tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_corner_nut_entry_uses_roomy_tunnel_and_snug_pocket -v
python -m unittest tests.test_things_cad_scripts -v
git diff --check
```

Expected: focused test passes, all Things CAD tests pass, and `git diff --check` prints nothing.

- [ ] **Step 5: Commit and push the source change**

```bash
git add tests/test_things_cad_scripts.py things/plamp8/plamp8.scad
git commit -m "Unify Plamp8 hex-drop nut catchers"
git push origin main
```

Expected: GitHub `main` advances to the new commit.

### Task 2: Verify printable catcher geometry

**Files:**
- Verify: `things/plamp8/plamp8.scad`
- Do not commit generated STL, manifests, logs, or archived source.

**Interfaces:**
- Consumes: committed Plamp8 source from Task 1 and sets `nut_catcher_adjustment_test`, `panel_corner_fastener_test`, `north_south_walls`, and `sub_panel`.
- Produces: reproducible preview STL evidence for the shared catcher, transformed panel catcher, 45-degree wall catcher, and sub-panel bonding catchers.

- [ ] **Step 1: Plan every affected render**

Run:

```bash
bin/plamp cad plan plamp8 --set nut_catcher_adjustment_test --revision "$(git rev-parse --short HEAD)" --json
bin/plamp cad plan plamp8 --set panel_corner_fastener_test --revision "$(git rev-parse --short HEAD)" --json
bin/plamp cad plan plamp8 --set north_south_walls --revision "$(git rev-parse --short HEAD)" --json
bin/plamp cad plan plamp8 --set sub_panel --revision "$(git rev-parse --short HEAD)" --json
```

Expected: each plan contains exactly one job for the requested set.

- [ ] **Step 2: Generate preview meshes**

Run:

```bash
xvfb-run -a bin/plamp cad generate plamp8 --set nut_catcher_adjustment_test --preview --revision "$(git rev-parse --short HEAD)" --output /tmp/plamp8-unified-drop-adjustment
xvfb-run -a bin/plamp cad generate plamp8 --set panel_corner_fastener_test --preview --revision "$(git rev-parse --short HEAD)" --output /tmp/plamp8-unified-drop-panel
xvfb-run -a bin/plamp cad generate plamp8 --set north_south_walls --preview --revision "$(git rev-parse --short HEAD)" --output /tmp/plamp8-unified-drop-walls
xvfb-run -a bin/plamp cad generate plamp8 --set sub_panel --preview --revision "$(git rev-parse --short HEAD)" --output /tmp/plamp8-unified-drop-sub-panel
```

Expected: all four jobs finish with status `complete`, non-empty STL artifacts, simple geometry, and no OpenSCAD warnings or errors.

- [ ] **Step 3: Verify repository consistency**

Run:

```bash
git status --short
git rev-parse HEAD
git rev-parse origin/main
```

Expected: status is clean and both revisions are identical.

### Task 3: Expose the complete straight tunnel in the 45-degree diagnostic coupon

**Files:**
- Modify: `tests/test_things_cad_scripts.py`
- Modify: `things/plamp8/plamp8.scad`

**Interfaces:**
- Consumes: `nut_catcher_test_coupon()`, its base `coupon_w` and `coupon_h`, and the existing 45-degree orientation transform.
- Produces: test-only parameters `nut_catcher_test_45_extra_w = 12` and `nut_catcher_test_45_extra_h = 4`; a 28 mm wide by 14 mm high 45-degree coupon with its pocket datum unchanged; a tunnel length derived from the coupon top and the complete 6.1 mm tunnel cross-section; and row spacing that keeps the wider coupon separate.

- [ ] **Step 1: Write the failing structural test**

Add this test to `tests/test_things_cad_scripts.py`:

```python
def test_plamp8_45_nut_coupon_has_extended_tunnel_envelope(self):
    source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
    compact = compact_scad(source)
    coupon = compact_scad(scad_module_body(source, "nut_catcher_test_coupon"))

    self.assertIn("nut_catcher_test_45_extra_w=12;", compact)
    self.assertIn("nut_catcher_test_45_extra_h=4;", compact)
    self.assertNotIn("nut_catcher_test_45_tunnel_extra_l", compact)
    self.assertIn(
        'effective_coupon_w=coupon_w+(orientation=="45"?nut_catcher_test_45_extra_w:0);',
        coupon,
    )
    self.assertIn(
        'effective_coupon_h=coupon_h+(orientation=="45"?nut_catcher_test_45_extra_h:0);',
        coupon,
    )
    self.assertIn(
        'opening_edge_distance=orientation=="45"?nut_catcher_test_45_opening_edge_distance(',
        coupon,
    )
    self.assertIn("-effective_coupon_w/2", coupon)
    self.assertIn("effective_coupon_w,effective_coupon_h", coupon)
    self.assertIn(
        "nut_catcher_orientation_transform(orientation,slot_w,slot_h,roof_mode,coupon_h)",
        coupon,
    )
    self.assertIn(
        "nut_catcher_test_screw_negative(orientation,roof_mode,effective_coupon_h)",
        coupon,
    )
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
python -m unittest tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_45_nut_coupon_has_extended_tunnel_envelope -v
```

Expected: `FAIL` because the 45-degree tunnel still uses a fixed, insufficient extension.

- [ ] **Step 3: Implement the test-only envelope extension**

Use these test-only envelope parameters:

```scad
nut_catcher_test_45_extra_w = 12;
nut_catcher_test_45_extra_h = 4;
```

Extract the existing 45-degree catcher origin calculation into a function shared by the transform and coupon. In `nut_catcher_test_coupon()`, derive the 45-degree opening distance from the complete tunnel cross-section:

```scad
effective_coupon_w = coupon_w
    + (orientation == "45" ? nut_catcher_test_45_extra_w : 0);
effective_coupon_h = coupon_h
    + (orientation == "45" ? nut_catcher_test_45_extra_h : 0);
opening_edge_distance = coupon_d / 2 + 1
    // For 45 degrees, replace this base value with:
    // (effective_coupon_h - origin_45_z) * sqrt(2)
    //     + corner_nut_tunnel_w / 2 + boolean_shim;
```

Build the coupon cube using `effective_coupon_w` and `effective_coupon_h`. Continue passing the base `coupon_h` to `nut_catcher_orientation_transform()` so the pocket datum does not move, and pass `effective_coupon_h` to `nut_catcher_test_screw_negative()` so its bore crosses the taller coupon. Shift only the 45-degree item in the all-orientations row by `nut_catcher_test_45_extra_w / 2`, preserving the standard gap from its neighbor.

- [ ] **Step 4: Run focused and complete tests and verify GREEN**

Run:

```bash
python -m unittest tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_45_nut_coupon_has_extended_tunnel_envelope -v
python -m unittest tests.test_things_cad_scripts -v
git diff --check
```

Expected: the focused test passes, all Things CAD tests pass, and `git diff --check` prints nothing.

- [ ] **Step 5: Commit and push before rendering**

```bash
git add tests/test_things_cad_scripts.py things/plamp8/plamp8.scad
git commit -m "Enlarge Plamp8 45-degree nut coupon"
git push origin main
```

Expected: GitHub `main` advances to the implementation commit.

- [ ] **Step 6: Plan and render a small diagnostic set**

Run:

```bash
bin/plamp cad plan plamp8 --set nut_catcher_adjustment_test --define 'nut_catcher_test_width_offsets=[0]' --define 'nut_catcher_test_thick_offsets=[0]' --revision "$(git rev-parse --short HEAD)" --json
xvfb-run -a bin/plamp cad generate plamp8 --set nut_catcher_adjustment_test --define 'nut_catcher_test_width_offsets=[0]' --define 'nut_catcher_test_thick_offsets=[0]' --preview --revision "$(git rev-parse --short HEAD)" --output /tmp/plamp8-large-45-coupon
```

Expected: one complete job, a non-empty simple STL, no OpenSCAD warnings or errors, and visual confirmation that a broad rectangular tunnel—not a slit—exits the 45-degree coupon top.

### Task 4: Reduce the default clearance matrix to 3×3

**Files:**
- Modify: `tests/test_things_cad_scripts.py`
- Modify: `things/plamp8/plamp8.scad`

- [ ] Require both default offset arrays to equal `[-0.1, 0, 0.1]`.
- [ ] Verify the test fails against the seven-value defaults.
- [ ] Change only the two default arrays; retain CLI adjustability and the existing matrix generator.
- [ ] Run the complete Things CAD suite, push source, then plan and render the committed diagnostic set.

### Task 5: Align the sideways 30-degree roof with its dropped tunnel

- [ ] Require `nut_catcher_sideways_print_roof_negative()` to receive the shared proportional tunnel-floor elevation.
- [ ] Verify the test fails while the roof remains at local Z zero.
- [ ] Offset the test-only gable by `m3_nut_thickness * nut_drop_fraction` and leave its angle and cross-section unchanged.
- [ ] Run the complete Things CAD suite, push source, and visually inspect a committed `S R30` render.

### Task 6: Carry the straight tunnel through the full hex pocket

- [ ] Require the shared tunnel to extend from the mouth to the far point of the hex pocket rather than stopping at the screw axis.
- [ ] Verify the test fails against the center-stopping tunnel.
- [ ] Extend only the main rectangular tunnel by `pocket_d / 2` behind the screw axis; preserve the mouth, detents, screw axis, and lower hex seat.
- [ ] Verify both `S RF` and `S R30` in the committed diagnostic render.

### Task 7: Keep the 45-degree engraving on its actual top face

- [ ] Require both coupon engravings to use `effective_coupon_h`.
- [ ] Verify the test fails while the enlarged coupon still engraves at the original 10 mm height.
- [ ] Move only the label and revision cutters to the effective top surface.
- [ ] Push source, generate with text enabled, and verify the complete STL is slicer-safe.
