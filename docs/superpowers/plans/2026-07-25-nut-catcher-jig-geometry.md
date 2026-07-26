# Nut Catcher Jig Geometry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct the shared nut retention position and make the adjustment jig compact, self-supporting, consistently loadable, connected by row, and self-documenting.

**Architecture:** Keep `m3_nut_catcher_negative()` authoritative for production and test parts, but locate its nibs from the seated nut/screw axis instead of the remote opening. Keep coupon-only print-orientation details—45-degree roof suppression, sideways teardrop screw holes, negative-Y loading transforms, row joining, labels, and echo legend—in the jig modules.

**Tech Stack:** OpenSCAD, Python `unittest` source-contract tests, managed `plamp cad` rendering, ASCII STL connectivity verification.

## Global Constraints

- The seated nut center remains coincident with the screw axis.
- The nut passes the nib pair immediately before reaching the seated position.
- A 45-degree catcher always uses the flat/open roof; a 30-degree 45-degree candidate is never generated.
- Every exported insertion opening faces negative Y.
- Every declarative row is one connected print piece, while different rows remain disconnected.
- Labels remain complete and readable after reducing unused plastic.
- Managed generation emits one abbreviation legend and requires support-free slicing.

---

### Task 1: Seated Retention and Printable Hole Contracts

**Files:**
- Modify: `tests/test_things_cad_scripts.py`
- Modify: `things/plamp8/plamp8.scad`

**Interfaces:**
- Consumes: `m3_nut_catcher_negative(...)`, `m3_nut_catcher_floor_nibs_positive(...)`, and `nut_catcher_test_coupon(...)`.
- Produces: `nib_seat_offset`, `nut_catcher_effective_roof_mode(orientation, requested)`, and `nut_catcher_test_screw_negative(orientation, roof_mode, height)`.

- [ ] **Step 1: Write failing source-contract tests**

Add tests asserting that the canonical catcher derives nib X coordinates from the nut pocket/screw axis rather than `opening_edge_distance`, that `nut_catcher_effective_roof_mode("45", "30deg")` returns `"flat"`, and that the sideways flat-roof branch calls a teardrop screw-negative module.

- [ ] **Step 2: Verify the focused tests fail**

Run: `python3 -m unittest tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_nut_catcher_nibs_retain_at_seated_screw_axis tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_jig_45_roof_is_always_flat tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_sideways_flat_roof_uses_teardrop_screw_hole -v`

Expected: three assertion failures because the seated anchor, effective-roof function, and teardrop branch do not exist.

- [ ] **Step 3: Implement seated nib geometry and roof selection**

Change the nib module to accept a seated-axis anchor and derive a short ramp immediately entrance-side of X=0. Add:

```scad
function nut_catcher_effective_roof_mode(orientation, requested) =
    orientation == "45" ? "flat" : requested;
```

Use the effective value for geometry and marking, so no 45-degree pointed roof is rendered.

- [ ] **Step 4: Implement the sideways teardrop screw negative**

Add a centered self-supporting teardrop profile extrusion and select it only when `orientation == "sideways" && roof_mode == "flat"`; use the canonical cylindrical screw hole otherwise.

- [ ] **Step 5: Verify focused and existing nut-catcher tests pass**

Run: `python3 -m unittest tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_nut_catcher_nibs_retain_at_seated_screw_axis tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_jig_45_roof_is_always_flat tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_sideways_flat_roof_uses_teardrop_screw_hole tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_side_loaded_nuts_share_floor_nibs_and_30_degree_roof tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_uses_one_parametric_m3_nut_catcher -v`

Expected: five tests pass.

- [ ] **Step 6: Commit**

```bash
git add tests/test_things_cad_scripts.py things/plamp8/plamp8.scad
git commit -m "Fix seated nut catcher retention geometry"
```

### Task 2: Compact Connected Row Layout and Legend

**Files:**
- Modify: `tests/test_things_cad_scripts.py`
- Modify: `things/plamp8/plamp8.scad`

**Interfaces:**
- Consumes: the Task 1 effective roof and screw-hole helpers.
- Produces: negative-Y coupon orientation transforms, `nut_catcher_test_row(...)`, compact coupon constants, and `nut_catcher_test_echo_legend()`.

- [ ] **Step 1: Write failing layout and legend tests**

Add source-contract tests requiring: per-orientation transforms that point the insertion axis toward negative Y; a row module that places candidates at exactly one coupon width so adjacent solids join; row-to-row spacing; reduced coupon width/depth/height and closer text Y offsets; and these exact echo meanings: `U=up`, `D=down`, `S=sideways`, `45=diagonal`, `W=width clearance`, `T=thickness clearance`, `RF=flat roof`, `R30=30-degree roof`.

- [ ] **Step 2: Verify the focused tests fail**

Run: `python3 -m unittest tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_nut_jig_loads_every_coupon_from_negative_y tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_nut_jig_connects_each_row_and_compacts_coupons tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_nut_jig_echoes_label_legend -v`

Expected: three assertion failures against the old global grid and absent legend.

- [ ] **Step 3: Reorient and compact coupons**

Replace the global item grid with row-local X placement. Rotate/translate each catcher so its entry ray exits the negative-Y coupon face. Reduce coupon bounds only to the measured geometry envelope plus representative wall and label margins; move label/revision lines inward without clipping.

- [ ] **Step 4: Join candidates within each row**

Implement `nut_catcher_test_row(row, row_i)` as a union of touching coupons, then place each row at its cumulative compact row height plus a positive inter-row gap. Filter the invalid 45/30-degree combination rather than creating a duplicate or pointed coupon.

- [ ] **Step 5: Emit the generation legend once**

Call `echo()` once from `nut_catcher_adjustment_test()` with the exact abbreviation mapping. Ensure roof labels use `RF` and `R30` after effective roof selection.

- [ ] **Step 6: Verify focused tests and all source contracts pass**

Run: `python3 -m unittest tests.test_things_cad_scripts -v`

Expected: all tests pass with no failures.

- [ ] **Step 7: Commit**

```bash
git add tests/test_things_cad_scripts.py things/plamp8/plamp8.scad
git commit -m "Compact and document nut catcher adjustment rows"
```

### Task 3: Render and Production Regression Verification

**Files:**
- Modify only if verification exposes a defect: `things/plamp8/plamp8.scad`, `tests/test_things_cad_scripts.py`

**Interfaces:**
- Consumes: complete jig geometry from Tasks 1 and 2.
- Produces: verified managed STL and evidence that production consumers still compile.

- [ ] **Step 1: Validate and plan the exact jig**

Run: `bin/plamp cad validate plamp8 --json`

Run: `bin/plamp cad plan plamp8 --set nut_catcher_adjustment_test --revision jig-geometry-test --json`

Expected: validation succeeds and the plan contains exactly one support-forbidden job.

- [ ] **Step 2: Render the jig headlessly**

Run: `xvfb-run -a bin/plamp cad generate plamp8 --set nut_catcher_adjustment_test --revision jig-geometry-test --json`

Expected: job status `complete`, `geometry.simple` true, no warnings, and no errors.

- [ ] **Step 3: Verify mesh connectivity by declarative row**

Run the repository STL connectivity checker or a read-only ASCII STL adjacency script against the generated artifact.

Expected: connected-component count equals `len(nut_catcher_test_rows)`—three for the default jig.

- [ ] **Step 4: Compile production consumers**

Plan/render `c13_panel`, `dc_connector_panel` with `dc_connector_type="xt60"`, and `panel_corner_fastener_test` using preview-quality geometry where a full render is unnecessary.

Expected: every command exits zero without OpenSCAD warnings or errors.

- [ ] **Step 5: Run the full repository test suite and formatting checks**

Run: `python3 -m unittest discover -s tests -v`

Run: `git diff --check`

Expected: all tests pass and diff check emits no output.

- [ ] **Step 6: Commit any verification-driven correction, otherwise record no new commit**

```bash
git add things/plamp8/plamp8.scad tests/test_things_cad_scripts.py
git commit -m "Verify nut catcher jig print geometry"
```

Skip this commit when verification requires no source correction.
