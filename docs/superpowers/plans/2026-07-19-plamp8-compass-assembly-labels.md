# Plamp8 Compass Assembly Labels Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Engrave matching full-word compass names into the interior faces of all four Plamp8 walls and their corresponding floor edges so wall placement is self-evident during assembly.

**Architecture:** Keep the existing single-file parametric OpenSCAD structure. Add one reusable wall-name negative and one reusable floor-name negative, pass each wall's identity explicitly at its standalone wall module, and reuse those modules in assembly context transforms. Source-contract tests lock down the names, dimensions, pairings, orientation, and positive/negative composition before OpenSCAD rendering verifies the printable geometry.

**Tech Stack:** OpenSCAD, Python 3.11 `unittest`, the direct `plamp cad` CLI, Git

## Global Constraints

- Use the full words `NORTH`, `SOUTH`, `EAST`, and `WEST`; do not substitute numbers or single letters.
- Use named `assembly_name_depth = 0.6` and `assembly_name_font = 7` parameters for both floor and wall engravings.
- Put all assembly names on printable interior faces; preserve the plain exterior build-plate faces.
- Do not replace or move any existing `revision_string` engraving.
- Wall names must remain below the first vent row and clear of the floor rib, stiffening ribs, vents, locator notches, corner hardware, and mating faces.
- Floor names must remain clear of component mounts, tie-wrap anchors, corner fasteners, locator lands, and wall seating faces.
- Orient floor names to read from the enclosure center while facing their matching wall: north `0°`, east `-90°`, south `180°`, west `90°` in the standard assembly top view.
- Render printable verification through `plamp cad generate`; keep generated STL and preview artifacts outside the repository.
- Commit and push after each task so geometry can receive early feedback.

---

### Task 1: Engrave compass names on all four walls

**Files:**
- Modify: `tests/test_things_cad_scripts.py`
- Modify: `things/plamp8/plamp8.scad`

**Interfaces:**
- Consumes: existing `write_text(string, font_size, z0)`, `flat_wall(...)`, four standalone wall modules, and four assembly context modules.
- Produces: `wall_assembly_name_negative(length, wall_name)`, the `wall_name` argument on `flat_wall`, and standalone wall modules that are the sole authority for each wall's compass identity.

- [ ] **Step 1: Add the failing wall-label source-contract test**

Add this method to `ThingsCadScriptsTest` in `tests/test_things_cad_scripts.py` immediately after `test_plamp8_has_four_flat_printed_mitred_wall_views`:

```python
    def test_plamp8_walls_have_full_compass_name_engravings(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()

        self.assertIn("assembly_name_depth = 0.6;", source)
        self.assertIn("assembly_name_font = 7;", source)
        self.assertIn("wall_assembly_name_y =", source)
        self.assertIn("module wall_assembly_name_negative", source)

        flat_wall = source.split("module flat_wall", 1)[1].split("module ", 1)[0]
        self.assertIn('wall_name = ""', flat_wall)
        self.assertIn("wall_assembly_name_negative(length, wall_name);", flat_wall)

        for wall in ("north", "south", "east", "west"):
            wall_module = source.split(f"module {wall}_wall()", 1)[1].split(
                "module ", 1
            )[0]
            self.assertIn(f'wall_name = "{wall.upper()}"', wall_module)

            context_module = source.split(
                f"module {wall}_wall_context()", 1
            )[1].split("module ", 1)[0]
            self.assertIn(f"{wall}_wall();", context_module)
```

- [ ] **Step 2: Run the focused test and confirm it fails**

Run:

```bash
.venv/bin/python -m unittest tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_walls_have_full_compass_name_engravings -v
```

Expected: `FAIL`; the first missing contract is `assembly_name_depth = 0.6;`.

- [ ] **Step 3: Add shared engraving dimensions and the wall-name negative**

In `things/plamp8/plamp8.scad`, add these parameters beside the existing wall rib and vent dimensions:

```scad
assembly_name_depth = 0.6;
assembly_name_font = 7;
wall_assembly_name_y =
    (wall_t + wall_rib_w + vent_floor_clearance - vent_hole_d / 2) / 2;
```

Place this module immediately before `wall_revision_negative`:

```scad
module wall_assembly_name_negative(length, wall_name) {
    if (wall_name != "")
        translate([length / 2, wall_assembly_name_y, wall_t])
            write_text(wall_name, assembly_name_font, -assembly_name_depth);
}
```

Change `flat_wall` to accept and subtract the name:

```scad
module flat_wall(
    length,
    wall_name = "",
    nut_owner = false,
    vent_mode = "none",
    h = wall_z_height
) {
    difference() {
        union() {
            wall_body_positive(length, h);
            wall_corner_tabs(length, h, nut_owner);
            wall_stiffening_ribs(length, h, vent_mode);
        }
        floor_locator_notches(length);
        wall_vent_negatives(length, vent_mode, h);
        wall_revision_negative(length, h, vent_mode);
        wall_assembly_name_negative(length, wall_name);
    }
}
```

- [ ] **Step 4: Make standalone wall modules authoritative for identity**

Replace the four standalone wall bodies with:

```scad
module north_wall() {
    flat_wall(
        box_w,
        wall_name = "NORTH",
        nut_owner = true,
        vent_mode = "half"
    );
}

module south_wall() {
    flat_wall(
        box_w,
        wall_name = "SOUTH",
        nut_owner = true,
        vent_mode = "half"
    );
}

module west_wall() {
    flat_wall(
        box_d,
        wall_name = "WEST",
        nut_owner = false,
        vent_mode = "none"
    );
}

module east_wall() {
    flat_wall(
        box_d,
        wall_name = "EAST",
        nut_owner = false,
        vent_mode = "full"
    );
}
```

Inside each existing colored context transform, replace its direct `flat_wall(...)` call with the matching `north_wall();`, `south_wall();`, `west_wall();`, or `east_wall();` call. Preserve every color and transformation matrix exactly.

- [ ] **Step 5: Run focused and complete CAD source tests**

Run:

```bash
.venv/bin/python -m unittest tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_walls_have_full_compass_name_engravings -v
.venv/bin/python -m unittest tests.test_things_cad_scripts -v
git diff --check
```

Expected: the focused test passes, all `tests.test_things_cad_scripts` tests pass, and `git diff --check` produces no output.

- [ ] **Step 6: Render all four labeled walls**

Run from `things/plamp8` with a fresh temporary parent:

```bash
label_preview_root="$(mktemp -d)"
plamp cad generate plamp8 --revision compass-walls-1 --view north_wall --output "$label_preview_root/north"
plamp cad generate plamp8 --revision compass-walls-1 --view south_wall --output "$label_preview_root/south"
plamp cad generate plamp8 --revision compass-walls-1 --view east_wall --output "$label_preview_root/east"
plamp cad generate plamp8 --revision compass-walls-1 --view west_wall --output "$label_preview_root/west"
test -s "$label_preview_root/north/plamp8_north_wall_compass-walls-1.stl"
test -s "$label_preview_root/south/plamp8_south_wall_compass-walls-1.stl"
test -s "$label_preview_root/east/plamp8_east_wall_compass-walls-1.stl"
test -s "$label_preview_root/west/plamp8_west_wall_compass-walls-1.stl"
! rg -n "WARNING|ERROR|empty top level object" "$label_preview_root"/*/readme.md
```

Expected: four non-empty STL files and no warning, error, or empty-object matches. Inspect each interior face and confirm the complete word is recessed, centered, below the first vent row, and separated from the lower horizontal rib.

- [ ] **Step 7: Commit and push the wall checkpoint**

```bash
git add tests/test_things_cad_scripts.py things/plamp8/plamp8.scad
git commit -m "Engrave compass names on Plamp8 walls"
git push origin feature/plamp8-flat-walls
```

Expected: one new commit appears on `feature/plamp8-flat-walls` and the push succeeds.

---

### Task 2: Engrave matching names on the floor and verify the assembly

**Files:**
- Modify: `tests/test_things_cad_scripts.py`
- Modify: `things/plamp8/plamp8.scad`

**Interfaces:**
- Consumes: Task 1's `assembly_name_depth`, `assembly_name_font`, and existing floor `difference()` composition.
- Produces: `floor_assembly_name_inset`, `floor_assembly_name_negative(label, x, y, angle)`, and `floor_assembly_name_negatives()` with one correctly oriented entry for every wall.

- [ ] **Step 1: Add the failing floor-label source-contract test**

Add this method immediately after the wall-label test:

```python
    def test_plamp8_floor_has_matching_oriented_compass_names(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()

        self.assertIn("floor_assembly_name_inset = 14;", source)
        self.assertIn("module floor_assembly_name_negative", source)
        self.assertIn("module floor_assembly_name_negatives", source)

        floor_names = source.split(
            "module floor_assembly_name_negatives", 1
        )[1].split("module ", 1)[0]
        expected = (
            '("NORTH", box_w / 2, box_d - wall_t - floor_assembly_name_inset, 0)',
            '("EAST", box_w - wall_t - floor_assembly_name_inset, box_d / 2, -90)',
            '("SOUTH", box_w / 2, wall_t + floor_assembly_name_inset, 180)',
            '("WEST", wall_t + floor_assembly_name_inset, box_d / 2, 90)',
        )
        for call in expected:
            self.assertIn(f"floor_assembly_name_negative{call};", floor_names)

        floor_context = source.split("module floor_context()", 1)[1].split(
            "module ", 1
        )[0]
        self.assertIn("floor_assembly_name_negatives();", floor_context)
```

- [ ] **Step 2: Run the focused test and confirm it fails**

Run:

```bash
.venv/bin/python -m unittest tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_floor_has_matching_oriented_compass_names -v
```

Expected: `FAIL`; `floor_assembly_name_inset = 14;` is absent.

- [ ] **Step 3: Add the four parametric floor engravings**

Add this parameter beside the assembly-name dimensions:

```scad
floor_assembly_name_inset = 14;
```

Place these modules immediately before `floor_context`:

```scad
module floor_assembly_name_negative(label, x, y, angle) {
    translate([x, y, -box_h + wall_t])
        rotate([0, 0, angle])
            write_text(label, assembly_name_font, -assembly_name_depth);
}

module floor_assembly_name_negatives() {
    floor_assembly_name_negative("NORTH", box_w / 2, box_d - wall_t - floor_assembly_name_inset, 0);
    floor_assembly_name_negative("EAST", box_w - wall_t - floor_assembly_name_inset, box_d / 2, -90);
    floor_assembly_name_negative("SOUTH", box_w / 2, wall_t + floor_assembly_name_inset, 180);
    floor_assembly_name_negative("WEST", wall_t + floor_assembly_name_inset, box_d / 2, 90);
}
```

In the negative section of `floor_context`, add the floor assembly names after the existing revision negative:

```scad
            floor_corner_fastener_holes();
            box_bottom_revision_negative();
            floor_assembly_name_negatives();
```

- [ ] **Step 4: Run focused and complete CAD source tests**

Run:

```bash
.venv/bin/python -m unittest tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_floor_has_matching_oriented_compass_names -v
.venv/bin/python -m unittest tests.test_things_cad_scripts -v
git diff --check
```

Expected: the focused test passes, all CAD script tests pass, and `git diff --check` produces no output.

- [ ] **Step 5: Render the floor and complete assembly with text enabled**

Run from `things/plamp8`:

```bash
label_preview_root="$(mktemp -d)"
plamp cad generate plamp8 --revision compass-floor-1 --view floor --output "$label_preview_root/floor"
plamp cad generate plamp8 --revision compass-floor-1 --view assembly --output "$label_preview_root/assembly"
test -s "$label_preview_root/floor/plamp8_floor_compass-floor-1.stl"
test -s "$label_preview_root/assembly/plamp8_assembly_compass-floor-1.stl"
! rg -n "WARNING|ERROR|empty top level object" "$label_preview_root"/*/readme.md
```

Expected: both STL files are non-empty and logs contain no warning, error, or empty-object matches. Inspect the floor interior to confirm all four words are readable from the center while facing their matching walls, remain inside the floor skin, and do not intersect mounts, anchors, locators, fasteners, or wall seats. Inspect the assembly to confirm the floor-to-wall pairings are correct.

- [ ] **Step 6: Run final verification**

```bash
.venv/bin/python -m unittest tests.test_things_cad_scripts -v
git diff --check
git status --short
```

Expected: all CAD script tests pass, the diff check is silent, and only `tests/test_things_cad_scripts.py` plus `things/plamp8/plamp8.scad` are modified.

- [ ] **Step 7: Commit and push the completed compass-label feature**

```bash
git add tests/test_things_cad_scripts.py things/plamp8/plamp8.scad
git commit -m "Pair Plamp8 walls with floor labels"
git push origin feature/plamp8-flat-walls
```

Expected: the second implementation commit appears on `feature/plamp8-flat-walls` and the push succeeds.
