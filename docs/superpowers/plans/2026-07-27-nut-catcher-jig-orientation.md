# Nut Catcher Jig Orientation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align the 45-degree jig coupon to the north wall and make sideways roof coupons load from `-Y`.

**Architecture:** Keep shared catcher geometry unchanged. Change only adjustment-jig transforms and protect them with source-level tests.

**Tech Stack:** OpenSCAD, Python unittest, Plamp CAD generation.

## Global Constraints

- Preserve nut dimensions, clearances, nibs, labels, and wall geometry.
- `45` follows the north-wall catcher transform.
- `S RF` and `S R30` expose insertion shafts at coupon `-Y`.

---

### Task 1: Correct adjustment-jig transforms

**Files:**
- Modify: `tests/test_things_cad_scripts.py`
- Modify: `things/plamp8/plamp8.scad`

**Interfaces:**
- Consumes: `nut_catcher_orientation_transform()` and `support_free_m3_nut_trap()`.
- Produces: printable `nut_catcher_adjustment_test` coupons with canonical orientations.

- [ ] **Step 1: Write failing test**

Assert the 45-degree jig branch uses the north-wall `rotate([0, -corner_nut_entry_angle, 0])` transform and sideways points its shaft at `-Y`.

- [ ] **Step 2: Verify red**

Run `PYTHONPATH=. python3 -m unittest tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_nut_catcher_jig_orientations -v`; it must fail before source changes.

- [ ] **Step 3: Implement**

Modify only `nut_catcher_orientation_transform()` and directly necessary caller arguments.

- [ ] **Step 4: Verify green and render**

Run the targeted test, full CAD-script test module, Plamp validation, plan, and a managed adjustment-jig render.

- [ ] **Step 5: Commit**

Commit the SCAD and regression test as `Align nut catcher adjustment jig orientations`.
