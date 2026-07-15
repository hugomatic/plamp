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
- Produces independent sub-panel opening parameters `sub_panel_usb_c_cutout_w = 14` and `sub_panel_usb_c_cutout_h = 10.25`.
- Produces shared `usb_c_screw_spacing = 17`.

- [ ] Add a failing source-contract test for all measured dimensions and top-only rounded-cutout use.
- [ ] Run `UV_CACHE_DIR=/tmp/uv-cache /home/hugo/.local/bin/uv run python -m unittest tests.test_things_cad_scripts -v` and confirm failure.
- [ ] Add `rounded_rect_cutout(w, h, r, depth = 30)`, update the parameters, and call it from `usb_c_panel_negative()` while retaining `rect_cutout()` in `sub_panel_usb_c_negative()`.
- [ ] Run the focused test and the full Python test suite; inspect `git diff --check`.
- [ ] Commit and push `feature/plamp8-usb-com-fit`. Do not render locally.
