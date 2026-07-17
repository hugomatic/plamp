# Plamp8 USB COM Fit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a standalone USB COM panel source suitable for testing the measured connector fit.

**Architecture:** Keep shared screw alignment but separate the top- and sub-panel openings. Add one reusable rounded-rectangle negative module and use it only for the top USB opening.

**Tech Stack:** OpenSCAD and Python `unittest` source-contract tests.

## Global Constraints

- Do not run OpenSCAD on Tower.
- Do not generate or commit STL files.
- Preserve the standalone `usb_c_panel` view.

---

### Task 1: Correct the USB COM mount geometry

**Files:**
- Modify: `things/plamp8/plamp8.scad`
- Modify: `tests/test_things_cad_scripts.py`

**Interfaces:**
- Produces top opening parameters `usb_c_cutout_w = 12`, `usb_c_cutout_h = 10`, and `usb_c_cutout_r = 1.5`.
- Produces independent sub-panel opening parameters `sub_panel_usb_c_cutout_w = 13` and `sub_panel_usb_c_cutout_h = 10.5`.
- Produces shared `usb_c_screw_spacing = 17`.

- [ ] Add a failing source-contract test for all measured dimensions and top-only rounded-cutout use.
- [ ] Run `UV_CACHE_DIR=/tmp/uv-cache /home/hugo/.local/bin/uv run python -m unittest tests.test_things_cad_scripts -v` and confirm failure.
- [ ] Add `rounded_rect_cutout(w, h, r, depth = 30)`, update the parameters, and call it from `usb_c_panel_negative()` while retaining `rect_cutout()` in `sub_panel_usb_c_negative()`.
- [ ] Run the focused test and the full Python test suite; inspect `git diff --check`.
- [ ] Commit and push `feature/plamp8-usb-com-fit`. Do not render locally.

### Task 2: Add captive M3 top-panel fasteners and COM countersinks

**Files:**
- Modify: `things/plamp8/plamp8.scad`
- Modify: `tests/test_things_cad_scripts.py`

**Interfaces:**
- Top-panel fasteners use M3 dimensions: 3.4 mm clearance, 6.5 mm countersink, and 9.5 mm circular land.
- Inward side-loading M3 nut pockets retain nuts with an entrance detent and place the full nut within reach of a 20 mm screw with 1 mm tip protrusion.
- COM fasteners use 2.4 mm clearance holes and 4 mm underside countersinks without circular lands.
- A standalone `panel_corner_fastener_test` view prints the complete screw-and-nut corner interface.

- [ ] Add failing source-contract tests for the M2 and M3 dimensions, underside COM countersinks, circular top-panel lands, captive side-entry nut channels and detents, 20 mm screw reach, and the fit-test view.
- [ ] Run the focused CAD test and confirm failure.
- [ ] Implement the parameters and positive/negative modules, keeping the screw axis and nut pocket derived from the same corner positions.
- [ ] Run all Git-tracked Python tests and `git diff --check`; do not run OpenSCAD.
- [ ] Commit and push the branch for the user's local fit-test render.
