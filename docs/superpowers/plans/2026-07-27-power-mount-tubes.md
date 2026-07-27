# Power Mount Tubes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add four hollow 9 mm OD, 5 mm high screw-guide tubes at the existing PSU and DC/DC M5 mount points.

**Architecture:** One shared positive tube helper consumes the existing mount-point arrays. Existing PSU/DC-DC hole cutters create the coaxial bores after union, so no bore geometry is duplicated.

**Tech Stack:** OpenSCAD 2021.01, Python `unittest`, Plamp CAD CLI.

## Global Constraints

- Tube OD is 9 mm and height is `component_raise_h`.
- PSU and DC/DC coordinates remain authoritative through their existing mount-point functions.
- Existing M5 negatives remain authoritative for bore diameter and chamfer.
- Relay geometry is unchanged.

---

### Task 1: Add and verify shared mount tubes

**Files:**
- Modify: `things/plamp8/plamp8.scad`
- Modify: `tests/test_things_cad_scripts.py`

**Interfaces:**
- Produces: `component_mount_tubes(points)` with no duplicated hole cutter.
- Consumed by: floor, `psu_footprint`, and `converter_footprint` positive unions.

- [ ] Add a failing source test requiring `component_mount_tube_d = 9`, one shared tube module, reuse of `psu_mount_points()` and `converter_mount_points()`, and calls from all three positive consumers.
- [ ] Run the focused test and confirm RED.
- [ ] Implement `component_mount_tubes(points)` as `cylinder(h = component_raise_h, d = component_mount_tube_d)` for every supplied point; add calls before the existing M5 negatives are subtracted.
- [ ] Run the focused test, all `tests.test_things_cad_scripts`, and `git diff --check`.
- [ ] Render `psu_footprint`, `converter_footprint`, and `floor`; require non-empty complete artifacts and clean logs.
- [ ] Commit source/tests with `Add PSU and converter screw guide tubes`, then push `main`.
