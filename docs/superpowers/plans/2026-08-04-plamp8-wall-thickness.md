# Plamp8 Wall Thickness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 2 mm to the exterior of each Plamp8 enclosure wall without changing floor or panel geometry.

**Architecture:** Preserve the existing 3 mm interior wall face and add a dedicated 2 mm exterior wall layer. Extend the wall bodies, 45° mitres, and vent cutters through that exterior layer while leaving floor and panel geometry untouched.

**Tech Stack:** OpenSCAD and Plamp CAD generation.

## Global Constraints

- Floor and panel dimensions remain unchanged.
- The 2 mm addition is on the exterior/build-plate side of flat wall prints.
- The interior width and depth remain unchanged.
- The 30 mm corner-screw support above the 3 mm floor is split equally: 13.5 mm per adjacent wall boss.

---

### Task 1: Parameterize the wall-only thickness

**Files:**
- Modify: `things/plamp8/plamp8.scad`
- Test: Plamp CAD planned wall, floor, panel, and assembly views.

- [ ] **Step 1: Inspect every `wall_t` use and classify it as wall, floor, or panel-interface geometry.**
- [ ] **Step 2: Add a dedicated 2 mm exterior wall thickness while retaining the existing 3 mm interior wall interface.**
- [ ] **Step 3: Change wall solids, 45° mitres, and wall-local cutouts to extend through the exterior layer without moving the interior face.**
- [ ] **Step 4: Run `plamp cad validate plamp8 --json` and `plamp cad plan plamp8 --preset enclosure-parts --json`; confirm floor and panel jobs remain present.**
- [ ] **Step 5: Generate the wall and assembly views, inspect the log for errors, and verify the artifacts are non-empty.**
