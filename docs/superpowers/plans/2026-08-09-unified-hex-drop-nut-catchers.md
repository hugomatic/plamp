# Unified Hex-Drop Nut Catchers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every Plamp8 nut catcher use one shared tunnel-and-hex geometry with an adjustable drop proportional to nominal nut thickness.

**Architecture:** `m3_nut_catcher_negative()` remains the only module that constructs catcher geometry. It derives a local tunnel elevation from `nut_thickness * drop_fraction`; production wrappers may orient that module but may not replace or bypass its pocket, tunnel, drop, or roof logic.

**Tech Stack:** OpenSCAD 2021.01, Python `unittest`, Plamp CAD CLI.

## Global Constraints

- Default `nut_drop_fraction` is `1 / 4`.
- Calculate drop from nominal nut thickness, never tunnel clearance.
- Apply the proportional drop to every production catcher.
- Retain `"flat"` and `"30deg"` roof modes in the shared module.
- Preserve family-specific tunnel width and thickness clearances.
- Preserve screw axes and hex-pocket locations.

---

### Task 1: Unify the proportional hex drop

**Files:**
- Modify: `tests/test_things_cad_scripts.py`
- Modify: `things/plamp8/plamp8.scad`

**Interfaces:**
- Consumes: `m3_nut_thickness`, caller-supplied `nut_thickness`, and the existing `roof_mode`, tunnel-width, tunnel-height, clearance, nib, direction, and opening-distance parameters.
- Produces: global `nut_drop_fraction = 1 / 4`; module parameter `drop_fraction = nut_drop_fraction`; local `nut_drop = nut_thickness * drop_fraction`; one shared catcher negative used by corner, panel, sub-panel, and coupon callers.

- [ ] **Step 1: Write the failing structural test**

Update the Plamp8 catcher test to require these source-level contracts:

```python
self.assertIn("nut_drop_fraction=1/4;", compact)
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
nut_drop_fraction = 1 / 4;
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
