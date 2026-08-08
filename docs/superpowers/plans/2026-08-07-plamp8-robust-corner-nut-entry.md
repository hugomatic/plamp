# Plamp8 Robust Corner Nut Entry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Plamp8 north/south wall nuts slide through a material-tolerant 45-degree tunnel and stop in the existing snug anti-rotation pocket.

**Architecture:** Extend the shared negative catcher with optional tunnel dimensions whose defaults preserve all existing callers. The corner wall adapter and its exact 45-degree coupon opt into a 6.10 mm wide by 2.52 mm high tunnel; the final hex pocket remains 5.65 mm across flats by 2.42 mm high.

**Tech Stack:** OpenSCAD, Python `unittest`, `plamp cad generate`

## Global Constraints

- Keep the calibrated M3 hex pocket at 5.46 + 0.19 mm across flats and 2.38 + 0.04 mm high.
- Make only the complete corner entry tunnel 6.10 mm wide with 0.14 mm thickness clearance (2.52 mm high).
- Keep the retention nibs and snug hex pocket.
- Do not change side-loaded panel nut-catcher geometry.
- The 45-degree test coupon must invoke the same corner dimensions as the production north/south walls.

---

### Task 1: Separate Corner Tunnel Fit From Pocket Fit

**Files:**
- Modify: `tests/test_things_cad_scripts.py`
- Modify: `things/plamp8/plamp8.scad`

**Interfaces:**
- Consumes: `m3_nut_catcher_negative()`, `support_free_m3_nut_trap()`, and `nut_catcher_test_coupon()`.
- Produces: optional `entry_tunnel_w` and `entry_tunnel_h` parameters, plus `corner_nut_tunnel_w` and `corner_nut_tunnel_h` corner-fit constants.

- [ ] **Step 1: Write the failing source-contract test**

Add a test that checks the independent dimensions, both corner callers, and the unchanged ordinary caller:

```python
def test_plamp8_corner_nut_entry_uses_roomy_tunnel_and_snug_pocket(self):
    source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
    compact = compact_scad(source)
    catcher = compact_scad(scad_module_body(source, "m3_nut_catcher_negative"))
    corner = compact_scad(scad_module_body(source, "support_free_m3_nut_trap"))
    coupon = compact_scad(scad_module_body(source, "nut_catcher_test_coupon"))
    panel = compact_scad(scad_module_body(source, "side_loaded_panel_nut_trap_negative"))

    self.assertIn("corner_nut_tunnel_w=corner_nut_entry_mouth_w;", compact)
    self.assertIn("corner_nut_tunnel_h=m3_nut_thickness+0.14;", compact)
    self.assertIn("entry_tunnel_w=undef", catcher)
    self.assertIn("entry_tunnel_h=undef", catcher)
    self.assertIn("effective_tunnel_w=is_undef(entry_tunnel_w)?slot_w:entry_tunnel_w", catcher)
    self.assertIn("effective_tunnel_h=is_undef(entry_tunnel_h)?slot_h:entry_tunnel_h", catcher)
    self.assertIn("entry_tunnel_w=corner_nut_tunnel_w", corner)
    self.assertIn("entry_tunnel_h=corner_nut_tunnel_h", corner)
    self.assertIn('entry_tunnel_w=orientation=="45"?corner_nut_tunnel_w:undef', coupon)
    self.assertIn('entry_tunnel_h=orientation=="45"?corner_nut_tunnel_h:undef', coupon)
    self.assertNotIn("entry_tunnel_w=corner_nut_tunnel_w", panel)
    self.assertNotIn("entry_tunnel_h=corner_nut_tunnel_h", panel)
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
python -m unittest tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_corner_nut_entry_uses_roomy_tunnel_and_snug_pocket -v
```

Expected: `FAIL` because `corner_nut_tunnel_w` and the independent tunnel parameters do not exist.

- [ ] **Step 3: Implement independent tunnel dimensions**

In `things/plamp8/plamp8.scad`, define:

```scad
corner_nut_entry_mouth_w = 6.1;
corner_nut_tunnel_w = corner_nut_entry_mouth_w;
corner_nut_tunnel_h = m3_nut_thickness + 0.14;
```

Add optional `entry_tunnel_w` and `entry_tunnel_h` arguments to `m3_nut_catcher_negative()`. Derive effective values that default to `slot_w` and `slot_h`. Use them for both rectangular tunnel segments. Keep the hex cylinder on `slot_w`, `slot_h`, and `pocket_d`.

For `roof_mode == "30deg"`, preserve the snug pocket roof over the hex seat and add a second tunnel roof based on the effective tunnel dimensions. The two roof negatives overlap at the pocket/tunnel boundary so no printable shelf separates them.

Pass both corner constants from `support_free_m3_nut_trap()`. Pass them conditionally from `nut_catcher_test_coupon()` only when `orientation == "45"`.

- [ ] **Step 4: Run the focused test and verify GREEN**

Run the Step 2 command again.

Expected: one test passes.

- [ ] **Step 5: Run the Plamp CAD source suite**

Run:

```bash
python -m unittest tests.test_things_cad_scripts -v
```

Expected: all tests pass with no errors.

- [ ] **Step 6: Generate the exact printable test set**

Run:

```bash
bin/plamp cad generate plamp8 --set nut_catcher_adjustment_test --revision robust-corner-entry --output /tmp/plamp8-robust-corner-entry
```

Expected: OpenSCAD exits successfully and writes the `nut_catcher_adjustment_test` STL under `/tmp/plamp8-robust-corner-entry`.

- [ ] **Step 7: Inspect and commit the implementation**

Run:

```bash
git diff --check
git status --short
git add tests/test_things_cad_scripts.py things/plamp8/plamp8.scad docs/superpowers/plans/2026-08-07-plamp8-robust-corner-nut-entry.md
git commit -m "Make Plamp8 corner nut entry tolerant"
```

Expected: clean diff check and one implementation commit containing only the plan, test, and CAD source.
