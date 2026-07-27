# Point-First Nut Catcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Key every shared M3 nut catcher for point-first insertion and make its retaining nibs printable insertion ramps.

**Architecture:** Keep `m3_nut_catcher_negative()` and `m3_nut_catcher_floor_nibs_positive()` as the only shared geometry path. Change only the hex phase and the two wedge profiles, so panels, corner walls, box mode, and the adjustment jig inherit identical behavior.

**Tech Stack:** OpenSCAD 2021.01, Python `unittest`, Plamp CAD CLI.

## Global Constraints

- The tunnel remains sized from `m3_nut_across_flats` plus `panel_nut_width_clearance`.
- A point-first nut fits; a flat-first nut presents its larger across-corners dimension and must not fit.
- Nib dimensions remain controlled by the existing height, length, width, and angle parameters.
- Printable artifacts must remain support-free and contain no OpenSCAD warnings or errors.
- Physical retention is not claimed until a new jig is printed.

---

### Task 1: Correct the shared pocket phase and nib ramp

**Files:**
- Modify: `things/plamp8/plamp8.scad`
- Test: `tests/test_things_cad_scripts.py`

**Interfaces:**
- Consumes: `m3_nut_across_flats`, `panel_nut_width_clearance`, and existing nib parameters.
- Produces: unchanged `m3_nut_catcher_negative(...)` and `m3_nut_catcher_floor_nibs_positive(...)` module signatures.

- [ ] **Step 1: Write the failing source regression test**

Add a test that extracts both shared module bodies, requires an unrotated six-sided pocket, rejects the old 30-degree pocket phase, and requires the high wedge vertex at `nib_outer_x`:

```python
def test_plamp8_shared_nut_catcher_is_point_first_and_ramped(self):
    source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
    catcher = compact_scad(scad_module_body(source, "m3_nut_catcher_negative"))
    nibs = compact_scad(
        scad_module_body(source, "m3_nut_catcher_floor_nibs_positive")
    )

    self.assertIn("cylinder(h=slot_h,d=pocket_d,$fn=6);", catcher)
    self.assertNotIn("rotate([0,0,30])cylinder(h=slot_h,d=pocket_d,$fn=6);", catcher)
    self.assertIn(
        "polygon([[nib_inner_x,-boolean_shim],[nib_outer_x,-boolean_shim],[nib_outer_x,nib_height]])",
        nibs,
    )
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
PYTHONPATH=. python3 -m unittest \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_shared_nut_catcher_is_point_first_and_ramped -v
```

Expected: `FAIL` because the pocket still has `rotate([0, 0, 30])` and the nib high vertex is still at `nib_inner_x`.

- [ ] **Step 3: Implement the minimal shared geometry correction**

In `m3_nut_catcher_negative()`, replace:

```scad
rotate([0, 0, 30])
    cylinder(h = slot_h, d = pocket_d, $fn = 6);
```

with:

```scad
cylinder(h = slot_h, d = pocket_d, $fn = 6);
```

In `m3_nut_catcher_floor_nibs_positive()`, replace the wedge polygon with:

```scad
polygon([
    [nib_inner_x, -boolean_shim],
    [nib_outer_x, -boolean_shim],
    [nib_outer_x, nib_height]
]);
```

This puts the floor-only end toward the entrance and the high retaining edge nearer the seated nut.

- [ ] **Step 4: Run the focused and complete source suites**

Run:

```bash
PYTHONPATH=. python3 -m unittest \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_shared_nut_catcher_is_point_first_and_ramped -v
PYTHONPATH=. python3 -m unittest tests.test_things_cad_scripts -q
git diff --check
```

Expected: focused test passes, all 66 source tests pass, and `git diff --check` emits no output.

- [ ] **Step 5: Commit the shared geometry correction**

```bash
git add things/plamp8/plamp8.scad tests/test_things_cad_scripts.py
git commit -m "Key shared nut catchers for point-first insertion"
```

### Task 2: Render the calibration and wall consumers

**Files:**
- Verify: `things/plamp8/plamp8.scad`
- Verify: `things/plamp8/plamp8.cad.json`

**Interfaces:**
- Consumes: corrected shared catcher modules from Task 1.
- Produces: non-versioned managed STL/log evidence for the adjustment jig and NORTH wall.

- [ ] **Step 1: Validate and plan both render jobs**

```bash
PYTHONPATH=. python3 -m plamp cad validate plamp8 --json
PYTHONPATH=. python3 -m plamp cad plan plamp8 \
  --set nut_catcher_adjustment_test --set north_wall \
  --revision point-first-nibs --json
```

Expected: validation succeeds and planning reports exactly two jobs.

- [ ] **Step 2: Generate both artifacts**

```bash
PYTHONPATH=. python3 -m plamp cad generate plamp8 \
  --set nut_catcher_adjustment_test --set north_wall \
  --revision point-first-nibs \
  --openscad /tmp/foil-claw-openscad-headless --json
```

Expected: both jobs report `complete`, with non-empty STL artifacts.

- [ ] **Step 3: Inspect every generated log**

Use the run and artifact identifiers returned by generation:

```bash
PYTHONPATH=. python3 -m plamp cad show RUN_ID --json
PYTHONPATH=. python3 -m plamp cad log RUN_ID ARTIFACT_ID --json
```

Expected: both logs contain 3D geometry statistics and no warning, error, empty-geometry, or non-manifold messages.

- [ ] **Step 4: Push the implementation after verification**

```bash
git push origin main
```

Expected: `origin/main` advances to the Task 1 implementation commit. Generated artifacts remain outside Git.
