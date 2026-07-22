# Plamp8 Component Fit and Cable Corridor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Loosen the DC/DC converter retaining pocket by 0.5 mm overall in each axis and create a wider relay-to-PSU corridor for the USB connector and upward cable bend.

**Architecture:** Change only the three existing parametric inputs that already drive the relevant geometry. The converter's calibrated body and mount definitions remain fixed, while the shared PSU and relay X offsets move their complete floor and illustration feature groups together.

**Tech Stack:** OpenSCAD, the direct `plamp cad` CLI, Git

## Global Constraints

- Set `converter_fit_clearance = 0.75`; do not change `converter_w`, `converter_d`, mount spacing, mount holes, airflow-post layout, or transparent converter keepout.
- Set `internal_psu_x = 70`, moving the complete PSU group 10 mm east.
- Set `internal_relay_x = -39`, moving the complete relay group 4 mm west.
- Do not change any component Y offset or move the DC/DC converter.
- Add no automated test for these user-directed fit changes.
- Push the source commit before running OpenSCAD.
- Render only through `plamp cad generate` and leave generated files outside the repository.
- Do not push this checkpoint to `main` until the user approves the rendered geometry.

---

### Task 1: Adjust component fit and placement

**Files:**
- Modify: `things/plamp8/plamp8.scad`

**Interfaces:**
- Consumes: `converter_retaining_w`, `converter_retaining_d`, and every existing floor/illustration transform based on `internal_psu_x` or `internal_relay_x`.
- Produces: a converter retaining envelope 0.5 mm larger overall in X and Y, plus a relay-to-PSU body corridor approximately 46 mm wide.

- [ ] **Step 1: Confirm the worktree contains only the committed design**

Run:

```bash
git status --short
git branch --show-current
```

Expected: no status output and branch `feature/plamp8-flat-walls`.

- [ ] **Step 2: Change only the three approved parameters**

In `things/plamp8/plamp8.scad`, make these exact replacements:

```scad
converter_fit_clearance = 0.75;
```

```scad
internal_psu_x = 70;
```

```scad
internal_relay_x = -39;
```

Do not edit `converter_w`, `converter_d`, `internal_converter_x`, `internal_psu_y`, `internal_relay_y`, or any geometry module.

- [ ] **Step 3: Verify the source diff is limited to those values**

Run:

```bash
git diff --check
git diff -- things/plamp8/plamp8.scad
```

Expected: `git diff --check` is silent, and the SCAD diff contains exactly three changed assignment lines: `0.5 → 0.75`, `60 → 70`, and `-35 → -39`.

- [ ] **Step 4: Commit and push before OpenSCAD**

```bash
git add things/plamp8/plamp8.scad
git commit -m "Loosen Plamp8 component fit"
git push origin feature/plamp8-flat-walls
```

Expected: the commit succeeds and the remote feature branch advances. Do not invoke OpenSCAD before this step completes.

- [ ] **Step 5: Render the converter footprint from the pushed clean commit**

Run from `things/plamp8`:

```bash
fit_preview_root="$(mktemp -d)"
plamp cad generate plamp8 --view converter_footprint --output "$fit_preview_root/converter"
converter_revision="$(git rev-parse --short HEAD)"
test -s "$fit_preview_root/converter/plamp8_converter_footprint_${converter_revision}.stl"
! rg -n "WARNING|ERROR|empty top level object" "$fit_preview_root/converter/readme.md"
```

Expected: the converter STL is non-empty and the log contains no warning, error, or empty-object match. The body and two mount holes remain fixed while all four retaining corners move 0.25 mm outward per side in both axes.

- [ ] **Step 6: Render the complete assembly from the same pushed commit**

Using the same `fit_preview_root` and `converter_revision` values:

```bash
plamp cad generate plamp8 --view assembly --output "$fit_preview_root/assembly"
test -s "$fit_preview_root/assembly/plamp8_assembly_${converter_revision}.stl"
! rg -n "WARNING|ERROR|empty top level object" "$fit_preview_root/assembly/readme.md"
```

Expected: the assembly STL is non-empty and the log contains no warning, error, or empty-object match. Visual inspection confirms the PSU group moved 10 mm east, the relay group moved 4 mm west, their associated mounts/retainers/keepouts remain aligned, and the new corridor is clear for the USB connector and upward cable bend.

- [ ] **Step 7: Report the pushed commit for visual approval**

Run:

```bash
git status --short
git log -1 --oneline
```

Expected: the worktree is clean. Report the feature commit and wait for user approval before fast-forwarding `main`.
