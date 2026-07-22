# Plamp8 Assembly Fit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct Plamp8 wall handedness, interior revision placement, panel-region clearance/support, and measured corner-nut fit while preserving the enclosure stack.

**Architecture:** Keep `things/plamp8/plamp8.scad` as the single parametric source and extend `tests/test_things_cad_scripts.py` with focused source contracts. Each geometry increment is test-first, committed, and pushed before the next increment; final validation uses the installed `plamp cad` dry-planning interface and does not render.

**Tech Stack:** OpenSCAD source, Python 3.11 `unittest`, Plamp CAD CLI, Git

## Global Constraints

- Keep the NORTH wall context matrix byte-for-byte unchanged; SOUTH, WEST, and EAST must be proper rotations with determinant `+1`.
- Preserve wall-local axes, box planes, shared wall bodies, and the existing assembly/fused-box call paths; do not add locator keys or wall copies.
- Keep floor thickness, holes, chamfers, locators, component supports, compass labels, and component labels unchanged.
- Keep `sub_panel_base_h = 5`, `sub_panel_h = 10`, top-panel thickness, wall height, corner supports, M3x20 panel screws, and M3x25/M3x30 corner screws unchanged.
- Do not change `side_loaded_panel_nut_trap()` or any `panel_nut_*` dimension.
- Do not commit generated STL, log, archive, manifest, or archived-source files.
- Do not invoke OpenSCAD before Task 1's source commit is pushed; this plan requires no OpenSCAD invocation at all.

---

### Task 1: Wall rotations, half-vent handedness, and interior floor revision

**Files:**
- Modify: `tests/test_things_cad_scripts.py`
- Modify: `things/plamp8/plamp8.scad`

**Failing tests:**
- `ThingsCadScriptsTest.test_plamp8_wall_contexts_are_proper_rotations`
- `ThingsCadScriptsTest.test_plamp8_half_vents_are_explicitly_handed`
- `ThingsCadScriptsTest.test_plamp8_floor_revision_is_readable_from_inside`

- [ ] **Step 1: Write the focused source-contract tests**

Parse the four `multmatrix()` literals and assert the exact matrices from the design, determinant `+1`, and an unchanged NORTH block. Assert `vent_side = "right"` flows through `flat_wall()`, `wall_vent_negatives()`, `wall_revision_negative()`, and `wall_stiffening_ribs()`; valid half sides are asserted; NORTH passes `"right"`; SOUTH passes `"left"`; and half-wall vent ranges, rib positions, and revision X use the selected side. Assert `box_bottom_revision_negative()` and its call are absent and `floor_revision_negative()` uses center `[box_w / 2, box_d / 2]`, interior Z `-box_h + wall_t`, depth `floor_revision_depth = 0.6`, angle zero, and no `mirror()`.

- [ ] **Step 2: Run RED**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_wall_contexts_are_proper_rotations \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_half_vents_are_explicitly_handed \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_floor_revision_is_readable_from_inside -v
```

Expected: FAIL because SOUTH/WEST/EAST still contain reflected orientation blocks, half vents have no `vent_side`, and the floor revision is mirrored on the exterior face.

- [ ] **Step 3: Implement the minimum source change**

Replace only the SOUTH, WEST, and EAST context matrices with the approved matrices. Add asserted `vent_side` plumbing and derive left/right half vent ranges, mirrored rib X positions, and non-vented-half revision centers (`length / 4` or `3 * length / 4`); select right for NORTH and left for SOUTH. Replace the exterior revision cutter with `floor_revision_negative()` at the exact interior center/depth and call it from the existing floor negative composition.

- [ ] **Step 4: Run GREEN, commit, and push**

Run:

```bash
.venv/bin/python -m unittest tests.test_things_cad_scripts -v
git diff --check
git add tests/test_things_cad_scripts.py things/plamp8/plamp8.scad
git commit -m "Correct Plamp8 wall and floor orientation"
git push origin fix/plamp8-assembly-fit
```

Expected: all CAD source-contract tests pass, diff check is clean, and the source commit is on the remote before any optional render.

---

### Task 2: Panel layout, service grid, and separator ribs

**Files:**
- Modify: `tests/test_things_cad_scripts.py`
- Modify: `things/plamp8/plamp8.scad`

**Failing tests:**
- `ThingsCadScriptsTest.test_plamp8_panel_regions_have_two_mm_gaps_and_xt60_margin`
- `ThingsCadScriptsTest.test_plamp8_service_region_is_one_equal_cell_grid`
- `ThingsCadScriptsTest.test_plamp8_sub_panel_separator_ribs_follow_region_bounds`

- [ ] **Step 1: Write the focused source-contract tests**

Assert the exact constants and derived equations: `panel_region_gap = 2`, `dc_region_w = barrel_group_w = barrel_channel_w = 74`, `c13_group_w = service_group_w = 58`, `service_group_h = usb_c_group_h = 28`, unchanged `c13_cutout_w = 28`, and unchanged `c13_screw_spacing = 40`. Cover explicit SCAD assertions for 2 mm DC row/column/C13-service gaps, at least 1.2 mm XT60 X margin on every face, equal service cells, region-contained hardware/screw envelopes, and cutter-vs-rib bounds. Assert one `service_group_negative()`, a hardware-only `usb_c_connector_negative()`, and the 2x2 labels/connector centers (`plamp`, revision, `COM`, USB). Assert `sub_panel_separator_rib_positive(x0, y0, w, h)` and `sub_panel_separator_ribs_positive()` create exactly the two DC gap ribs and one C13/service gap rib from region bounds, from Z 5 through Z 10, while retaining the full-width USB rib.

- [ ] **Step 2: Run RED**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_panel_regions_have_two_mm_gaps_and_xt60_margin \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_service_region_is_one_equal_cell_grid \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_sub_panel_separator_ribs_follow_region_bounds -v
```

Expected: FAIL on the current 70/66 mm regions, independently nudged USB region, nested USB pocket, and missing separator helpers.

- [ ] **Step 3: Implement the minimum source change**

Introduce the approved region constants and derive DC, C13, and service bounds from `panel_region_gap = 2`. Preserve the C13 cutout and screw locations. Split USB hardware cutting into `usb_c_connector_negative()` and the single service pocket; place the four equal service cells in the approved readable grid and keep the USB coupon by composing both cutters. Add only the vertical DC-column separator, horizontal DC-row separator, and horizontal C13/service separator at exactly 2 mm across-gap width and height `sub_panel_h - sub_panel_base_h`; union them with `sub_panel_8ch_positive()` without trimming around cutters. Add the exact layout, margin, envelope, and rib-side assertions required by the design.

- [ ] **Step 4: Run GREEN, commit, and push**

Run:

```bash
.venv/bin/python -m unittest tests.test_things_cad_scripts -v
git diff --check
git add tests/test_things_cad_scripts.py things/plamp8/plamp8.scad
git commit -m "Rework Plamp8 panel regions and supports"
git push origin fix/plamp8-assembly-fit
```

Expected: all CAD source-contract tests pass and the second source increment is pushed.

---

### Task 3: Measured corner-wall nut fit

**Files:**
- Modify: `tests/test_things_cad_scripts.py`
- Modify: `things/plamp8/plamp8.scad`

**Failing tests:**
- `ThingsCadScriptsTest.test_plamp8_corner_nut_fit_uses_measured_independent_dimensions`
- `ThingsCadScriptsTest.test_plamp8_corner_nut_fit_is_shared_by_flat_and_box_paths`

- [ ] **Step 1: Write the focused source-contract tests**

Assert `corner_nut_slot_l = 2.7`, `corner_nut_entry_w = 6.1`, `corner_nut_throat_w = 5.8`, `corner_nut_entry_detent = (corner_nut_entry_w - corner_nut_throat_w) / 2`, `corner_nut_entry_detent_l = 1.5`, and `corner_nut_pocket_d = corner_nut_entry_w / cos(30)`. Require assertions for all four measured values, 0.15 mm detent per side, and `entry - 2 * detent == throat`. Verify `support_free_m3_nut_trap()` uses these corner values in both flat point-up hex and box support-free paths, and does not use `panel_nut_entry_detent` or `panel_nut_entry_detent_l`. Retain existing M3x25 zero-offset and M3x30 enclosed-travel source contracts.

- [ ] **Step 2: Run RED**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_corner_nut_fit_uses_measured_independent_dimensions \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_corner_nut_fit_is_shared_by_flat_and_box_paths -v
```

Expected: FAIL because the corner slot is derived from generic nut clearance and corner retention still depends on panel-detent controls.

- [ ] **Step 3: Implement the minimum source change**

Define the six approved corner-only dimensions and their exact assertions. Feed `corner_nut_entry_w`, `corner_nut_throat_w`, `corner_nut_entry_detent_l`, and `corner_nut_pocket_d` through the existing entry, detent, flat-pocket, and box-pocket modules. Preserve entry angle, screw axis/bore, nut bearing datum and offsets, tab/spine solids, coupon modules, and all panel-nut definitions.

- [ ] **Step 4: Run GREEN, commit, and push**

Run:

```bash
.venv/bin/python -m unittest tests.test_things_cad_scripts -v
git diff --check
git add tests/test_things_cad_scripts.py things/plamp8/plamp8.scad
git commit -m "Calibrate Plamp8 corner nut fit"
git push origin fix/plamp8-assembly-fit
```

Expected: all CAD source-contract tests pass and the third source increment is pushed.

---

### Task 4: Integrated CLI validation and review

**Files:**
- Modify only if review finds a missing cross-contract assertion: `tests/test_things_cad_scripts.py`
- Do not modify during this task: `things/plamp8/plamp8.scad`

**Failing tests / integration gates:**
- `tests.test_things_cad_scripts.ThingsCadScriptsTest` (all focused and legacy Plamp8 contracts)
- `tests.test_cad_cli.CadCliTests`
- `tests.test_cad_metadata.CadMetadataTests`
- `tests.test_cad_recipes.CadRecipeTests`

- [ ] **Step 1: Run the integration preflight**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_things_cad_scripts \
  tests.test_cad_cli \
  tests.test_cad_metadata \
  tests.test_cad_recipes -v
```

Expected: GREEN. Treat any failure as the integration RED signal: add one narrowly named source-contract assertion in `tests/test_things_cad_scripts.py` only when it exposes a missing approved-spec contract, then return the source correction to its owning Task 1, 2, or 3 commit instead of changing CAD here.

- [ ] **Step 2: Run non-rendering Plamp8 validation**

Run:

```bash
.venv/bin/plamp cad views plamp8 --json
.venv/bin/plamp cad validate plamp8 --json
.venv/bin/plamp cad plan plamp8 --preset split-box --json
.venv/bin/plamp cad plan plamp8 --preset fuse-box --json
```

Expected: each command exits 0 with valid JSON; `split-box` expands `floor`, `north_south_walls`, `east_west_walls`, `top_panel`, and `sub_panel`; `fuse-box` includes the fused `box` path plus the panel jobs declared by metadata. No command invokes OpenSCAD.

- [ ] **Step 3: Review invariants and repository cleanliness**

Confirm the NORTH matrix remained byte-identical, every context determinant is `+1`, no locator key or copied wall body appeared, panel and corner screw/stack values remain unchanged, panel-nut controls remain independent, and no generated artifact is tracked. Run:

```bash
git diff --check
git status --short
```

Expected: diff check is clean; status contains only an intentional final test-only review correction, or is clean.

- [ ] **Step 4: Commit any non-empty review correction and push the final checkpoint**

If Step 1 required a test-only correction, run:

```bash
git add tests/test_things_cad_scripts.py
git commit -m "Strengthen Plamp8 assembly fit contracts"
git push origin fix/plamp8-assembly-fit
```

Otherwise run only:

```bash
git push origin fix/plamp8-assembly-fit
```

Expected: the remote contains all three source increments and any genuine test-only integration correction; no empty commit is created.
