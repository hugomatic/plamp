# Peristaltic Pump Stand Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a parametric, table-standing peristaltic-pump holder to Plamp CAD.

**Architecture:** Create one self-contained OpenSCAD model with `plate`, `legs`, and `assembly` sets. The plate repeats a complete pump station from `pump_count` and `pump_spacing`; the two end panels give a fixed 55 mm motor clearance. Register the model in the Plamp CAD system and assert its public parameters and set catalog from the existing CAD script tests.

**Tech Stack:** OpenSCAD, Plamp CAD sidecar metadata, Python `unittest`.

## Global Constraints

- Default to two pumps at 62 mm centre-to-centre spacing.
- Every station is collinear: M3 hole, 29 mm motor opening, M3 hole; the M3-hole centres are 48.5 mm apart.
- Expose `pump_count`, `pump_spacing`, `motor_hole_d`, `motor_screw_spacing`, `motor_clearance_h`, and `mount_hole_d` as SCAD variables.
- Motors hang below a horizontal plate; two full-height end panels create a U-stand with 55 mm default clearance.
- Provide two provisional M5 clearance holes near the plate ends.
- Keep printable `plate` and `legs` separate; `assembly` is non-printable.

---

### Task 1: Register the new CAD model and its public contract

**Files:**
- Create: `things/peristaltic_pump_stand/peristaltic_pump_stand.scad`
- Create: `things/peristaltic_pump_stand/peristaltic_pump_stand.cad.json`
- Modify: `cad/plamp.system.cad.json`
- Modify: `tests/test_things_cad_scripts.py`

**Interfaces:**
- Produces SCAD sets `plate`, `legs`, and `assembly`.
- Produces model id `peristaltic_pump_stand` for `plamp cad` discovery.

- [ ] **Step 1: Write failing catalog and parameter tests**

```python
def test_peristaltic_pump_stand_catalog_and_parameters(self):
    source = (REPO_ROOT / "things" / "peristaltic_pump_stand" /
              "peristaltic_pump_stand.scad").read_text()
    compact = compact_scad(source)
    for value in (
        "pump_count=2;", "pump_spacing=62;", "motor_hole_d=29;",
        "motor_screw_spacing=48.5;", "motor_clearance_h=55;",
    ):
        self.assertIn(value, compact)
    for set_name in ("plate", "legs", "assembly"):
        self.assertIn(f'set=="{set_name}"', compact)
```

Extend the system-catalog expectations with `peristaltic_pump_stand`, and load
its sidecar to assert that `plate` and `legs` are printable while `assembly`
is not.

- [ ] **Step 2: Run the test and verify it fails**

Run: `PYTHONPATH=. python3 -m unittest tests.test_things_cad_scripts -q`

Expected: failure because the model directory and system entry do not exist.

- [ ] **Step 3: Create the minimal SCAD shell and sidecar**

Create the variables and dispatch shell:

```scad
set = "plate"; // [plate, legs, assembly]
pump_count = 2;
pump_spacing = 62;
motor_hole_d = 29;
motor_screw_spacing = 48.5;
motor_clearance_h = 55;
mount_hole_d = 5.5;

if (set == "plate") plate();
else if (set == "legs") legs();
else if (set == "assembly") assembly();
```

Register the same three sets in the sidecar. Mark `plate` and `legs` as
printable with `as-exported` orientation, and `assembly` non-printable.

- [ ] **Step 4: Run the test and validate model discovery**

Run:

```bash
PYTHONPATH=. python3 -m unittest tests.test_things_cad_scripts -q
.venv/bin/plamp cad validate peristaltic_pump_stand --json
```

Expected: tests pass and validation reports no diagnostics.

- [ ] **Step 5: Commit**

```bash
git add things/peristaltic_pump_stand cad/plamp.system.cad.json tests/test_things_cad_scripts.py
git commit -m "Register peristaltic pump stand CAD model"
```

### Task 2: Build the parametric U-stand geometry

**Files:**
- Modify: `things/peristaltic_pump_stand/peristaltic_pump_stand.scad`
- Modify: `tests/test_things_cad_scripts.py`

**Interfaces:**
- Consumes the public variables from Task 1.
- Produces `pump_station_negative(index)`, `plate()`, `leg_pair()`, `legs()`, and `assembly()`.

- [ ] **Step 1: Write failing geometry-contract tests**

```python
plate = compact_scad(scad_module_body(source, "plate"))
station = compact_scad(scad_module_body(source, "pump_station_negative"))
legs = compact_scad(scad_module_body(source, "leg_pair"))
self.assertIn("for(index=[0:pump_count-1])", plate)
self.assertIn("cylinder(d=motor_hole_d", station)
self.assertIn("motor_screw_spacing/2", station)
self.assertIn("cylinder(d=mount_hole_d", plate)
self.assertIn("motor_clearance_h", legs)
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `PYTHONPATH=. python3 -m unittest tests.test_things_cad_scripts -q`

Expected: failure because the station and leg modules do not exist.

- [ ] **Step 3: Implement the plate, stations, and legs**

Implement these derived dimensions and modules:

```scad
plate_t = 4;
plate_end_margin = 12;
plate_w = (pump_count - 1) * pump_spacing + motor_screw_spacing
    + 2 * plate_end_margin;

module pump_station_negative(index) {
    x = (index - (pump_count - 1) / 2) * pump_spacing;
    translate([x, 0, -boolean_overlap]) {
        cylinder(d = motor_hole_d, h = plate_t + 2 * boolean_overlap);
        for (dx = [-motor_screw_spacing / 2, motor_screw_spacing / 2])
            translate([dx, 0, 0])
                cylinder(d = 3.4, h = plate_t + 2 * boolean_overlap);
    }
}
```

Build a rectangular plate around these stations, subtract two M5 clearance
holes near its ends, and create two full-height end panels under the plate.
Use a printed leg thickness of 4 mm and a plate-to-table height derived from
`motor_clearance_h + plate_t`. `legs()` prints the pair separated on the bed;
`assembly()` places each leg at a plate end under the mounted plate.

- [ ] **Step 4: Run tests and render every set**

Run:

```bash
PYTHONPATH=. python3 -m unittest tests.test_things_cad_scripts -q
.venv/bin/plamp cad plan peristaltic_pump_stand --all-sets --json
.venv/bin/plamp cad generate peristaltic_pump_stand --all-sets --revision pump-stand-v1 --json
```

Expected: tests pass; the plan expands `plate`, `legs`, and `assembly`; each
printable artifact is non-empty and the assembly is archived as non-printable.

- [ ] **Step 5: Commit**

```bash
git add things/peristaltic_pump_stand tests/test_things_cad_scripts.py
git commit -m "Add parametric peristaltic pump stand"
```

### Task 3: Verify print-facing details and document generation

**Files:**
- Create: `things/peristaltic_pump_stand/README.md`
- Modify: `things/peristaltic_pump_stand/peristaltic_pump_stand.scad`

**Interfaces:**
- Documents `plamp cad` generation for `plate`, `legs`, and `assembly`.

- [ ] **Step 1: Add a failing documentation assertion**

```python
readme = (REPO_ROOT / "things" / "peristaltic_pump_stand" / "README.md").read_text()
self.assertIn("plamp cad generate peristaltic_pump_stand --set plate", readme)
self.assertIn("pump_spacing", readme)
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `PYTHONPATH=. python3 -m unittest tests.test_things_cad_scripts -q`

Expected: failure because the README is absent.

- [ ] **Step 3: Write the concise generation guide**

Document the normal plate and legs commands plus a two-pump spacing override:

```bash
plamp cad generate peristaltic_pump_stand --set plate
plamp cad generate peristaltic_pump_stand --set legs
plamp cad generate peristaltic_pump_stand --set plate \
  --define 'pump_count=2' --define 'pump_spacing=62'
```

State that 29 mm and 48.5 mm are initial measured values to verify with a
short plate print before committing to a long production run.

- [ ] **Step 4: Run final verification**

Run:

```bash
PYTHONPATH=. python3 -m unittest tests.test_things_cad_scripts -q
.venv/bin/plamp cad validate peristaltic_pump_stand --json
.venv/bin/plamp cad plan peristaltic_pump_stand --all-sets --json
git diff --check
```

Expected: all tests pass, validation returns no errors, the plan lists the
three sets, and Git reports no whitespace errors.

- [ ] **Step 5: Commit**

```bash
git add things/peristaltic_pump_stand/README.md tests/test_things_cad_scripts.py
git commit -m "Document peristaltic pump stand generation"
```

## Self-review

- Spec coverage: Tasks 1–2 implement every required parameter, repeated
  station, U-stand component, M5 holes, and output set; Task 3 documents use.
- Placeholder scan: no unresolved dimensions or deferred implementation steps.
- Interface consistency: all tasks use `peristaltic_pump_stand`, `plate`,
  `legs`, and `assembly` consistently.
