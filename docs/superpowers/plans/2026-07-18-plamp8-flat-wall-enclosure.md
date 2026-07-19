# Plamp8 Flat-Wall Enclosure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the support-dependent Plamp8 wall shell with four flat-printed walls, a separate ledge ring, and shared support-free M3 corner joints while preserving the existing top panel and sub-panel.

**Architecture:** Keep the implementation in `things/plamp8/plamp8.scad`, following its existing parameter and view conventions. Build reusable corner-joint and wall-body modules once, then transform those same modules for the four printable wall views and the assembly. Use source-contract tests for stable interfaces, targeted OpenSCAD renders for geometry, a physical corner coupon for fit, and a bounded intersection diagnostic for unintended overlap.

**Tech Stack:** OpenSCAD, Bash `things/plamp8/generate.bash`, Python `unittest`, Git directory-specific revision labels.

## Global Constraints

- North is `y = box_d`, south is `y = 0`, west is `x = 0`, and east is `x = box_w`.
- Every wall prints with its plain exterior face on Z=0; all interior features grow upward from supported material.
- All exterior vertical seams use 45-degree mitres.
- North/south own the captured-nut tabs; west/east own the clearance tabs.
- Keep `sub_panel_base_h = 5` and `sub_panel_h = 10` with existing panel corner-hole coordinates.
- Use M3x25 for the initial top coupon; M3x30 is the fallback only if the physical stack needs it.
- Use four bottom-up corner M3 floor screws; remove the four midpoint M5 enclosure fasteners.
- Do not add a bottom ring, full-height groove, bonnet wall, wiring-specific view, or generated STL to Git.
- `wall_z_height = 83` preserves the full bottom-edge-to-top-edge wall height; the top edge stays at Z=0 and the bottom edge is `-wall_z_height`.
- The wall shell, ring, floor, top panel, and sub-panel must have no unintended volumetric overlap in assembly.
- Keep collision computation bounded to corner/contact regions and stop a diagnostic that takes more than a few minutes.

## File Structure

- Modify `things/plamp8/plamp8.scad`: parameters, joint primitives, ring, four walls, floor joints, views, assembly, and bounded collision diagnostic.
- Modify `tests/test_things_cad_scripts.py`: source-contract tests for named views, dimensions, ownership, print orientation, M3 floor conversion, and assembly toggles.
- Preserve `things/plamp8/generate.bash`: no generator behavior change is required.

---

### Task 1: Corner-Stack Contract And Printable Coupon

**Files:**
- Modify: `tests/test_things_cad_scripts.py`
- Modify: `things/plamp8/plamp8.scad`

**Interfaces:**
- Produces parameters `wall_z_height`, `corner_tab_t`, `ledge_ring_t`, `top_corner_screw_length`, `bottom_corner_screw_length`, `corner_fit_clearance`, and `locator_clearance`.
- Produces modules `support_free_horizontal_bore()`, `corner_clearance_tab()`, `corner_nut_tab()`, `corner_tab_gusset()`, `support_free_m3_nut_trap()`, and `wall_corner_fastener_test()` for later wall and ring tasks.

- [ ] **Step 1: Write the failing source-contract test**

Add this method to `ThingsCadScriptsTest`:

```python
def test_plamp8_flat_wall_corner_stack_contract(self):
    source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()

    self.assertIn("wall_z_height = 83;", source)
    self.assertIn("corner_tab_t = 4;", source)
    self.assertIn("ledge_ring_t = 3;", source)
    self.assertIn("top_corner_screw_length = 25;", source)
    self.assertIn('floor_screw_size = "M3";', source)
    self.assertIn("module support_free_horizontal_bore", source)
    self.assertIn("module corner_clearance_tab", source)
    self.assertIn("module corner_nut_tab", source)
    self.assertIn("module corner_tab_gusset", source)
    self.assertIn("module support_free_m3_nut_trap", source)
    self.assertIn("module wall_corner_fastener_test", source)
    self.assertIn('view == "wall_corner_fastener_test"', source)
    self.assertIn("sub_panel_base_h = 5;", source)
    self.assertIn("sub_panel_h = 10;", source)
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_flat_wall_corner_stack_contract -v
```

Expected: FAIL because `wall_z_height`, the new joint modules, and the renamed coupon view do not exist.

- [ ] **Step 3: Add named joint parameters and support-free primitives**

Near the existing wall and fastener parameters, add:

```scad
wall_z_height = 83;
corner_tab_t = 4;
corner_tab_d = panel_fastener_boss_d;
corner_fit_clearance = 0.25;
locator_key_l = 16;
locator_key_w = 2;
locator_key_h = 2;
locator_clearance = 0.25;
ledge_ring_t = 3;
top_corner_screw_length = 25;
bottom_corner_screw_length = 12; // candidate; confirm against physical coupon and available hardware

box_h = wall_z_height;
floor_screw_size = "M3";

top_stack_h = plate_t + sub_panel_h + ledge_ring_t + 2 * corner_tab_t;
bottom_stack_h = wall_t + 2 * corner_tab_t;
assert(top_corner_screw_length - top_stack_h >= 0);
echo(str("top M3 protrusion: ", top_corner_screw_length - top_stack_h, " mm"));
echo(str("bottom candidate M3 protrusion: ", bottom_corner_screw_length - bottom_stack_h, " mm"));
```

Define all production wall geometry in wall-local print coordinates: wall length is X, wall height is Y, exterior-to-interior thickness is Z, and the exterior face is Z=0. The assembled vertical M3 axis therefore runs along local Y and cannot use an ordinary round horizontal bore.

Use a circular lower half plus two 45-degree roof slopes for both tab bores:

```scad
module support_free_bore_profile(d) {
    r = d / 2;
    union() {
        intersection() {
            circle(d = d);
            translate([-r, -r])
                square([d, r]);
        }
        polygon([[-r, 0], [0, r], [r, 0]]);
    }
}

module support_free_horizontal_bore(length, d) {
    rotate([90, 0, 0])
        linear_extrude(height = length, center = true)
            support_free_bore_profile(d);
}
```

Build `corner_clearance_tab()` and `corner_nut_tab()` around this bore in the same wall-local coordinates. Give each tab a broad root into the wall plus `corner_tab_gusset()` with a 45-degree printable slope. Define the side-open nut entry and roof directly in these print coordinates; do not wrap or rotate the old upright-shell nut trap.

Adapt the existing `panel_corner_fastener_test()` into `wall_corner_fastener_test()`. Lay out separate printable top and bottom coupon pieces on Z=0, preserving a 3 mm top-panel surrogate, 10 mm sub-panel surrogate, 3 mm ring segment, two 4 mm wall tabs, and 3 mm floor segment. Echo the 25 mm top screw and the candidate bottom screw stack; keep every coupon exterior surface on the build plane. Slice the coupon after rendering to confirm that neither the tab bodies nor their horizontal bores require support.

- [ ] **Step 4: Run the contract test and render the coupon**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_flat_wall_corner_stack_contract -v
things/plamp8/generate.bash --revision corner-fit-1 --view wall_corner_fastener_test \
  prints/plamp8_corner_fit_1
```

Expected: test PASS; one non-empty `wall_corner_fastener_test` STL; no empty-object or missing-include warning.

- [ ] **Step 5: Commit the coupon foundation**

```bash
git add tests/test_things_cad_scripts.py things/plamp8/plamp8.scad
git commit -m "Add Plamp8 stacked corner fit coupon"
```

---

### Task 2: Separate Flat-Printed Ledge Ring

**Files:**
- Modify: `tests/test_things_cad_scripts.py`
- Modify: `things/plamp8/plamp8.scad`

**Interfaces:**
- Consumes existing panel dimensions, `panel_corner_screw_holes_in_box()`, PH switch gap functions, and `ledge_ring_t`.
- Produces `ledge_ring_context()` for assembly and `ledge_ring()` for its printable Z=0 orientation.

- [ ] **Step 1: Write the failing ring test**

```python
def test_plamp8_ledge_ring_is_separate_and_preserves_panel_stack(self):
    source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()

    self.assertIn("module ledge_ring_context", source)
    self.assertIn("module ledge_ring()", source)
    self.assertIn('view == "ledge_ring"', source)
    self.assertIn("feature_ph_ledge_holes", source)
    self.assertIn("top_ledge_gap_start(0)", source)
    self.assertIn("top_ledge_gap_start(1)", source)
    self.assertNotIn("quarter_round(", source)
    self.assertIn("sub_panel_base_h = 5;", source)
    self.assertIn("sub_panel_h = 10;", source)
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_ledge_ring_is_separate_and_preserves_panel_stack -v
```

Expected: FAIL because `ledge_ring` does not exist and `quarter_round()` is still used.

- [ ] **Step 3: Implement the rectangular ring**

Replace `top_panel_ledge()`, `top_ledge_segment()`, and `quarter_round()` with a flat rectangular frame built by subtracting the inner opening from the outer footprint. Subtract four M3 clearance holes and the two existing PH switch clearance regions from the north rail. Engrave `revision_string` on the hidden underside away from holes and switch gaps.

Use one context module in box coordinates and one printable wrapper:

```scad
module ledge_ring_context() {
    translate([wall_t, wall_t, ledge_top_z - ledge_ring_t])
        difference() {
            cube([box_inner_w, box_inner_d, ledge_ring_t]);
            translate([ledge_w, ledge_w, -0.1])
                cube([
                    box_inner_w - 2 * ledge_w,
                    box_inner_d - 2 * ledge_w,
                    ledge_ring_t + 0.2
                ]);
            ledge_ring_corner_holes();
            if (feature_ph_ledge_holes)
                ledge_ring_ph_switch_clearances();
            ledge_ring_revision_negative();
        }
}

module ledge_ring() {
    translate([-wall_t, -wall_t, -(ledge_top_z - ledge_ring_t)])
        ledge_ring_context();
}
```

Keep `mounted_sub_panel()` at the existing `ledge_top_z` and `mounted_top_panel()` at the existing `-plate_t`. The ring occupies the 3 mm immediately below the current sub-panel base, preserving the established top surface at Z=0.

- [ ] **Step 4: Verify tests and targeted renders**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_ledge_ring_is_separate_and_preserves_panel_stack \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_sub_panel_xt60_nut_clearance_and_revision_depth -v
things/plamp8/generate.bash --revision ring-fit-1 --preview --view ledge_ring \
  prints/plamp8_ledge_ring_preview
things/plamp8/generate.bash --revision ring-fit-1 --preview --view sub_panel \
  prints/plamp8_sub_panel_preview
things/plamp8/generate.bash --revision ring-fit-1 --preview --view top_panel \
  prints/plamp8_top_panel_preview
```

Expected: tests PASS; all three outputs non-empty; no quarter-circle geometry remains; PH switch clearances remain visible.

- [ ] **Step 5: Commit**

```bash
git add tests/test_things_cad_scripts.py things/plamp8/plamp8.scad
git commit -m "Split the Plamp8 ledge into a printable ring"
```

---

### Task 3: Four Flat-Printed Mitred Walls

**Files:**
- Modify: `tests/test_things_cad_scripts.py`
- Modify: `things/plamp8/plamp8.scad`

**Interfaces:**
- Consumes corner-tab primitives, wall dimensions, vents, revision text, and panel corner coordinates.
- Produces `north_wall_context()`, `south_wall_context()`, `west_wall_context()`, and `east_wall_context()` plus matching printable wrappers.

- [ ] **Step 1: Write the failing wall/view test**

```python
def test_plamp8_has_four_flat_printed_mitred_wall_views(self):
    source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
    view_line = next(line for line in source.splitlines() if line.startswith("view ="))

    for name in ("north_wall", "south_wall", "west_wall", "east_wall"):
        self.assertIn(name, view_line)
        self.assertIn(f"module {name}_context", source)
        self.assertIn(f"module {name}()", source)
        self.assertIn(f'view == "{name}"', source)
    self.assertNotIn(" walls,", view_line)
    self.assertNotIn('view == "walls"', source)
    self.assertIn("module wall_mitre_negative", source)
    self.assertIn("module wall_revision_negative", source)
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_has_four_flat_printed_mitred_wall_views -v
```

Expected: FAIL because only the monolithic `walls` view exists.

- [ ] **Step 3: Implement shared wall bodies and handed corner ownership**

Create a canonical flat wall body in the Task 1 print-local coordinates with exterior face Z=0. Cut both ends with `wall_mitre_negative()` at 45 degrees through `wall_t`. Add interior ribs, downward-insertion locator notches, broad tab roots/gussets, and revision engraving only on the Z-positive interior side. Context modules rotate this production geometry into assembly; do not define an assembly-oriented wall and rotate its old support roofs afterward.

Build north and south with nut tabs at both top and bottom ends; build west and east with clearance tabs. In assembly transforms:

- Top: west/east clearance tabs sit above north/south nut tabs.
- Bottom: west/east clearance tabs sit below north/south nut tabs.
- All tab bores share existing panel corner X/Y axes.

Use the same print-local production modules in each printable view and rotate them once in each context wrapper for assembly. West and east must insert along assembly -Z after the ring and panels are lifted; their key lead-ins, mitres, and both end-tab stacks must not require a sideways or upward motion.

- [ ] **Step 4: Verify source tests and preview every wall**

Run the new wall test, then render each view individually:

```bash
/home/hugo/.local/bin/uv run python -m unittest \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_has_four_flat_printed_mitred_wall_views -v
for wall in north_wall south_wall west_wall east_wall; do
  things/plamp8/generate.bash --revision flat-wall-1 --preview --view "$wall" \
    "prints/plamp8_${wall}_preview"
done
```

Expected: four non-empty STLs; every exterior face lies on the build plane; no tab, rib, or nut-trap roof starts in mid-air.

- [ ] **Step 5: Commit**

```bash
git add tests/test_things_cad_scripts.py things/plamp8/plamp8.scad
git commit -m "Split Plamp8 enclosure into four flat walls"
```

---

### Task 4: Mirrored M3 Floor Joints And Short Locators

**Files:**
- Modify: `tests/test_things_cad_scripts.py`
- Modify: `things/plamp8/plamp8.scad`

**Interfaces:**
- Consumes existing panel corner coordinates and bottom wall tabs.
- Produces four floor corner holes, short floor locator keys, and final bottom joint geometry.

- [ ] **Step 1: Write the failing floor-joint test**

```python
def test_plamp8_floor_uses_corner_m3_wall_fasteners(self):
    source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()

    self.assertIn('floor_screw_size = "M3";', source)
    self.assertIn("function enclosure_corner_points()", source)
    self.assertIn("module floor_corner_fastener_holes", source)
    self.assertIn("module floor_corner_lands", source)
    self.assertIn("module floor_locator_keys", source)
    self.assertNotIn("function floor_fastener_points()", source)
    self.assertNotIn("function floor_wall_tab_points()", source)
    self.assertNotIn("module floor_wall_tabs()", source)
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_floor_uses_corner_m3_wall_fasteners -v
```

Expected: FAIL while midpoint M5-era functions remain.

- [ ] **Step 3: Replace midpoint tabs with mirrored corner joints**

Define one `enclosure_corner_points()` function from the existing panel screw axes. Use it for the top stack, bottom stack, floor bores, wall tabs, and locator keys. Add `floor_corner_lands()` extending the inner-only floor beneath each wall joint so a 6.5 mm M3 countersink retains at least 2 mm of material to the nearest floor edge. Subtract the four M3 holes from `floor_context()` regardless of `feature_power_screw_mounts`; enclosure assembly holes are not component-mount features.

Place short 16 mm locator keys near, but not across, each corner screw land. Apply `locator_clearance = 0.25` only to receiving wall notches so modeled parts have positive clearance and no volumetric overlap. Give west/east keys downward lead-ins and confirm those walls can be lowered along -Z while north/south remain assembled.

- [ ] **Step 4: Verify floor and coupon renders**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_floor_uses_corner_m3_wall_fasteners \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_flat_wall_corner_stack_contract -v
things/plamp8/generate.bash --revision floor-fit-1 --preview --view floor \
  prints/plamp8_floor_preview
things/plamp8/generate.bash --revision floor-fit-1 --preview --view wall_corner_fastener_test \
  prints/plamp8_corner_floor_preview
```

Expected: four corner M3 holes with heads underneath; no midpoint enclosure holes; coupon bottom stack is floor, west/east clearance tab, north/south nut tab.

- [ ] **Step 5: Commit**

```bash
git add tests/test_things_cad_scripts.py things/plamp8/plamp8.scad
git commit -m "Move Plamp8 floor fasteners to M3 corners"
```

---

### Task 5: Parametric Height And Selectable Assembly Walls

**Files:**
- Modify: `tests/test_things_cad_scripts.py`
- Modify: `things/plamp8/plamp8.scad`

**Interfaces:**
- Consumes all completed printable part modules.
- Produces the final `assembly()` controls and wall-height behavior.

- [ ] **Step 1: Write the failing assembly test**

```python
def test_plamp8_assembly_has_individual_wall_controls_and_height(self):
    source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()

    for control in (
        "show_north_wall",
        "show_south_wall",
        "show_west_wall",
        "show_east_wall",
        "show_ledge_ring",
    ):
        self.assertIn(f"{control} = true;", source)
        self.assertIn(f"if ({control})", source)
    self.assertNotIn("show_walls = true;", source)
    self.assertIn("box_h = wall_z_height;", source)
    self.assertIn("assert(wall_z_height", source)
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_assembly_has_individual_wall_controls_and_height -v
```

Expected: FAIL because assembly still uses `show_walls` and the monolithic shell.

- [ ] **Step 3: Assemble the real parts and update height-dependent geometry**

Replace `show_walls` with five Customizer booleans. Call the four context modules and `ledge_ring_context()` independently from `assembly()`.

Use `wall_z_height` through the existing `box_h` alias for floor Z, component Z, vent rows, wall revision placement, and the bottom joints. Keep the top edge at Z=0, the existing panel datums at -3 and -13 mm, the ring at -16..-13 mm, and the top tabs immediately below the ring. Add assertions for these planes, both stack equations, shared screw axes, and enough wall height for the two joint zones plus vent safety margins.

Regenerate vent Z positions from fixed bottom and top margins. Do not move PSU, relay, or converter XY coordinates.

Render the assembly once more with `--define 'wall_z_height=100'` and verify that only the floor end moves while the panel/ring top datum remains fixed.

- [ ] **Step 4: Verify assembly configurations**

Run the assembly test, then render:

```bash
/home/hugo/.local/bin/uv run python -m unittest \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_assembly_has_individual_wall_controls_and_height -v
things/plamp8/generate.bash --revision assembly-all --preview --view assembly \
  --define 'show_north_wall=true' --define 'show_south_wall=true' \
  --define 'show_west_wall=true' --define 'show_east_wall=true' \
  prints/plamp8_assembly_all

things/plamp8/generate.bash --revision assembly-wiring --preview --view assembly \
  --define 'show_north_wall=true' --define 'show_south_wall=true' \
  --define 'show_west_wall=false' --define 'show_east_wall=false' \
  prints/plamp8_assembly_wiring
```

Expected: full enclosure in the first view; both relay long sides open in the second; panels and ring remain correctly positioned.

- [ ] **Step 5: Commit**

```bash
git add tests/test_things_cad_scripts.py things/plamp8/plamp8.scad
git commit -m "Assemble selectable parametric Plamp8 walls"
```

---

### Task 6: Bounded Interference Diagnostic And Final Evidence

**Files:**
- Modify: `tests/test_things_cad_scripts.py`
- Modify: `things/plamp8/plamp8.scad`

**Interfaces:**
- Consumes final context modules.
- Produces `corner_interference_witnesses()` as a diagnostic module that is not part of the ordered manufacturing view list.

- [ ] **Step 1: Write the failing diagnostic contract test**

```python
def test_plamp8_has_bounded_corner_interference_diagnostic(self):
    source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()

    self.assertIn("module corner_interference_witnesses", source)
    self.assertIn("intersection()", source.split("module corner_interference_witnesses", 1)[1])
    view_line = next(line for line in source.splitlines() if line.startswith("view ="))
    self.assertNotIn("interference", view_line)
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_has_bounded_corner_interference_diagnostic -v
```

Expected: FAIL because no bounded diagnostic exists.

- [ ] **Step 3: Add cropped intersection witnesses**

Create a diagnostic module with these bounded regions:

- Four wall-to-wall corner boxes large enough to include mitres, both tab roots, gussets, and locator keys.
- Four narrow floor-to-wall strips spanning each complete floor edge.
- Four narrow ring-to-wall strips spanning each complete bearing rail.
- One thin full-perimeter sub-panel-to-ring strip.
- One thin full-perimeter top-to-sub-panel strip.
- Two small north-rail boxes around the PH Up and PH Down switch clearances.

For every pair, crop each operand first and then intersect the two cropped operands. Do not write `intersection() { part_a(); part_b(); crop_box(); }`, because that makes CGAL construct both complete parts before cropping. Set `render_text=false` and `render_fn=24` for the combined diagnostic.

Expose it only through a non-ordered developer selection:

```scad
} else if (view == "corner_interference") {
    corner_interference_witnesses();
```

The expected result is an empty top-level object. Any rendered solid is an exact collision witness. Do not add ray casting, voxelization, or a new Python mesh dependency unless this targeted result is ambiguous.

- [ ] **Step 4: Run bounded diagnostics and stop if slow**

Run one low-detail direct diagnostic with a 60-second hard stop and an inverted empty-result oracle:

```bash
rm -f /tmp/plamp8_corner_interference.stl /tmp/plamp8_corner_interference.log
set +e
timeout 60s openscad \
  -o /tmp/plamp8_corner_interference.stl \
  -D 'view="corner_interference"' \
  -D 'render_fn=24' \
  -D 'render_text=false' \
  things/plamp8/plamp8.scad \
  > /tmp/plamp8_corner_interference.log 2>&1
diagnostic_status=$?
set -e

if [[ "$diagnostic_status" -eq 1 ]] \
  && grep -q "Current top level object is empty" /tmp/plamp8_corner_interference.log \
  && [[ ! -s /tmp/plamp8_corner_interference.stl ]]; then
  echo "PASS: no interference witness"
elif [[ "$diagnostic_status" -eq 0 ]] \
  && [[ -s /tmp/plamp8_corner_interference.stl ]]; then
  echo "FAIL: interference witness rendered" >&2
  exit 1
elif [[ "$diagnostic_status" -eq 124 ]]; then
  echo "INCONCLUSIVE: time budget reached; inspect one region at a time" >&2
  exit 2
else
  cat /tmp/plamp8_corner_interference.log >&2
  echo "ERROR: diagnostic failed for a reason other than an empty result" >&2
  exit 3
fi
```

Expected: `PASS: no interference witness`. Exit status 2 means the calculation hit the time budget; switch to one-region section views instead of increasing the timeout.

Expected: empty collision result. Designed coincident seating surfaces may touch but must not share non-zero solid volume.

- [ ] **Step 5: Run complete verification**

```bash
/home/hugo/.local/bin/uv run python -m unittest tests.test_things_cad_scripts -v
bash -n things/plamp8/generate.bash
git diff --check
```

Before physical fit evidence, low-detail render the coupon, ledge ring, four walls, floor, full assembly, and north/south-only wiring assembly. Final-quality render only the coupon plus one revision-marked wall; inspect the marked wall in the slicer to verify the exterior is on the build plate, horizontal bores/roofs need no support, and the revision is readable. Do not regenerate unchanged top/sub-panel STLs.

After the physical coupon passes, generate final manufacturing-quality ledge ring, four walls, and floor from the committed directory-specific revision. Confirm every requested STL is non-empty and inspect logs for empty-object, missing-include, and manifold warnings.

- [ ] **Step 6: Commit the verified source**

```bash
git add tests/test_things_cad_scripts.py things/plamp8/plamp8.scad
git commit -m "Verify Plamp8 enclosure part clearances"
git push
```

- [ ] **Step 7: Print and evaluate the physical coupon before full walls**

Use the committed coupon STL with M3x25 first. Record whether the nut inserts from inside, tabs assemble without binding, the 45-degree seam closes, and the full panel/ring/tab stack clamps with full nut engagement and 0-2 mm screw protrusion. Try M3x30 only if M3x25 lacks engagement.

Do not start four full wall prints until the coupon supplies this physical evidence.
