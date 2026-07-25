# Parametric Nut Catcher Jig Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace duplicate M3 nut-catcher fit geometry with one parametric implementation and add a marked multi-orientation adjustment jig.

**Architecture:** `plamp8.scad` keeps one canonical catcher in local coordinates; thin wrappers transform it into panel, wall-corner, and jig coordinates. A row-driven jig expands independent sweeps into printable labeled coupons. `plamp8.cad.json` exposes the jig as a managed printable set.

**Tech Stack:** OpenSCAD, Plamp CAD model metadata, Python `unittest` source-contract tests.

## Global Constraints

- Production defaults are 5.46 mm across flats, 2.38 mm thickness, 0.14 mm width clearance, 0.14 mm thickness clearance, and 0.20 mm nib height.
- Local catcher axes are X insertion, Y across flats, and Z nut thickness/screw axis.
- Roof modes are exactly `"flat"` and `"30deg"`.
- Jig rows are independent sweeps in `[orientation, parameter, mode, candidates]` form.
- Generated artifacts remain outside Git.

---

### Task 1: Canonical catcher and production consumers

**Files:**
- Modify: `things/plamp8/plamp8.scad`
- Test: `tests/test_things_cad_scripts.py`

**Interfaces:**
- Produces: `m3_nut_catcher_negative(...)` and coordinate wrappers used by panel and wall-corner production geometry.

- [x] Add a failing source-contract test requiring the five fit parameters, both roof modes, shared nib implementation, and production wrapper calls.
- [x] Run the focused test and confirm failure because the canonical module is absent.
- [x] Implement the canonical module and replace duplicated fit/nib dimensions with wrapper calls.
- [x] Run focused existing and new catcher tests and confirm they pass.

### Task 2: Declarative marked adjustment jig

**Files:**
- Modify: `things/plamp8/plamp8.scad`
- Test: `tests/test_things_cad_scripts.py`

**Interfaces:**
- Consumes: `m3_nut_catcher_negative(...)`.
- Produces: `nut_catcher_test_rows`, row expansion helpers, orientation transforms, marked coupons, and `nut_catcher_adjustment_test()`.

- [x] Add failing tests for all four orientations, independent `offsets`/`values` rows, five width candidates, five thickness candidates, two roof candidates, and derived labels.
- [x] Run the focused tests and confirm failure because the jig is absent.
- [x] Implement printable coupons, orientation transforms, row expansion, layout, and engraving.
- [x] Run focused tests and render the complete test set to STL.

### Task 3: Managed generation and regression verification

**Files:**
- Modify: `things/plamp8/plamp8.cad.json`
- Test: `tests/test_things_cad_scripts.py`

**Interfaces:**
- Produces: managed set `nut_catcher_adjustment_test`.

- [x] Add a failing test requiring the metadata set and SCAD dispatch.
- [x] Add the set to Customizer, dispatch, and CAD metadata.
- [x] Run `plamp cad validate`, then `plan`, then headless OpenSCAD rendering.
- [x] Run the complete test suite, `git diff --check`, independent review, and commit the verified implementation.
