# plamp8 Box Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evolve the existing OpenSCAD `plamp8` part with reusable channel modules, fit-test views, and a rough assembly/top-panel layout.

**Architecture:** Evolve the existing `things/plamp8` part through the direct `plamp cad` interface. Keep geometry correctness primarily human/print-verified; automated checks focus on CAD validation/planning and SCAD view/module structure. Use top-level parameters for all known and unknown hardware dimensions.

**Tech Stack:** OpenSCAD and the direct `plamp cad` CLI.

---

### Task 1: Evolve `plamp8`

**Files:**
- Modify: `things/plamp8/plamp8.scad`

- [ ] Replace the existing `plamp8.scad` with a modular SCAD file exposing `view = "assembly"; // [assembly, plate, ac_duplex_channel, dc_barrel_channel, usb_c_panel, c13_inlet, top_panel]`.
- [ ] Keep `revision_string = "dev"` and do not add generated STL files.

### Task 2: Implement reusable CAD modules

**Files:**
- Modify: `things/plamp8/plamp8.scad`

- [ ] Add top-level dimensions for plate thickness, outlet geometry, toggle holes, barrel jack holes, USB-C, C13, PSU keepout, relay keepout, relay mounting pattern, labels, and layout spacing.
- [ ] Add helper modules: rounded rectangles, rounded boxes, screw holes, label plaque/text, revision text, and alignment walls.
- [ ] Add channel modules: `ac_duplex_channel_unit(label_a, label_b, include_revision)`, `dc_barrel_channel_unit(label, include_revision)`, `usb_c_panel_unit(include_revision)`, `c13_inlet_unit(include_revision)`.
- [ ] Add internal context modules: `psu_keepout()` and `relay_board_keepout()` for assembly view only.

### Task 3: Implement views

**Files:**
- Modify: `things/plamp8/plamp8.scad`

- [ ] Add individual views for AC duplex, DC barrel, USB-C, C13, and top panel.
- [ ] Add `plate()` with separated printable coupons and the rough top panel laid out on the build plane.
- [ ] Add `assembly()` with rough box floor/walls, top panel, side/back C13 placement, and translucent/internal keepout placeholders.
- [ ] Ensure the full top panel has one revision string total; repeated modules must not duplicate revision strings in the full panel.

### Task 4: Lightweight verification

**Files:**
- Verify: `things/plamp8/plamp8.scad`

- [ ] Run `plamp cad validate plamp8 --json` and `plamp cad plan plamp8 --preset all-views --json`.
- [ ] Run `plamp cad generate plamp8 --preset all-views --revision plamp8-wip --output /tmp/plamp8_wip` only if OpenSCAD is available and time is reasonable. If rendering is slow, generate a single coupon with `plamp cad generate plamp8 --view VIEW --output DIR` or report that full rendering was skipped.
- [ ] Confirm no generated STL files were added to git.

### Task 5: Commit and push branch

**Files:**
- Add: `docs/superpowers/plans/2026-05-13-plamp8-box-builder.md`
- Modify: `things/plamp8/plamp8.scad`

- [ ] Commit with `git commit -m "Add plamp8 modular box builder"`.
- [ ] Push branch `plamp8-box-builder` to origin.
