# Plamp8 XT60-to-Switch Clearance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give each 12 V XT60 connector 2 mm of clearance from its adjacent 21 mm switch without reducing space for the switch state text.

**Architecture:** Keep the switch and label positions unchanged. Model the measured XT60 width, switch diameter, and requested clearance as named OpenSCAD parameters, then derive the XT60 x-position from the switch position and required center spacing. A top-level assertion protects the fit relationship for every rendered view.

**Tech Stack:** OpenSCAD, Bash, the existing `things/plamp8/generate.bash` renderer.

## Global Constraints

- XT60 outside width is 34.25 mm.
- Switch outside diameter is 21 mm.
- Required edge-to-edge clearance is 2 mm.
- Switch center remains x = 16 mm in XT60 mode.
- Switch state labels remain centered at x = 31 mm.
- Barrel-connector mode retains its existing positions.
- Generated STL and preview artifacts are written under `/tmp` and are not committed.

---

## File Structure

- Modify `things/plamp8/plamp8.scad`: define the hardware envelopes and clearance, derive the XT60 position, and assert the resulting fit.
- No production files are created. Rendered verification artifacts remain in `/tmp/plamp8_xt60_clearance`.

### Task 1: Derive and Verify XT60 Placement

**Files:**
- Modify: `things/plamp8/plamp8.scad:95-113`
- Modify: `things/plamp8/plamp8.scad:786-790`

**Interfaces:**
- Consumes: `barrel_jack_x`, `barrel_toggle_x`, `dc_connector_type`, and `dc_toggle_x()` from `things/plamp8/plamp8.scad`.
- Produces: `xt60_outside_w`, `dc_switch_outside_d`, `xt60_switch_clearance`, `xt60_switch_center_spacing`, and an XT60-specific `dc_connector_x()` result of -13.625 mm.

- [ ] **Step 1: Add a failing geometric assertion**

After `dc_toggle_x()` in `things/plamp8/plamp8.scad`, add the measured parameters and assertion while leaving the existing connector offset unchanged:

```scad
xt60_outside_w = 34.25;
dc_switch_outside_d = 21;
xt60_switch_clearance = 2;
xt60_switch_center_spacing = xt60_outside_w / 2 + dc_switch_outside_d / 2 + xt60_switch_clearance;

assert(
    dc_connector_type != "xt60"
        || abs((dc_toggle_x() - dc_connector_x()) - xt60_switch_center_spacing) < 0.001,
    "XT60-to-switch clearance does not match the measured hardware envelopes"
);
```

- [ ] **Step 2: Run OpenSCAD to verify the assertion fails**

Run:

```bash
openscad -D 'view="dc_barrel_channel"' -o /tmp/plamp8_xt60_clearance_red.stl things/plamp8/plamp8.scad
```

Expected: OpenSCAD reports `Assertion ... failed: "XT60-to-switch clearance does not match the measured hardware envelopes"` because the existing center spacing is 26 mm rather than 29.625 mm.

- [ ] **Step 3: Derive the connector position from the fit constraint**

Move the four measured-fit parameters next to the existing XT60 dimensions and replace the fixed `xt60_x_extra` offset with an XT60 connector position derived by `dc_connector_x()`:

```scad
dc_toggle_x_extra = dc_connector_type == "xt60" ? 8 : 0;
xt60_outside_w = 34.25;
dc_switch_outside_d = 21;
xt60_switch_clearance = 2;
xt60_switch_center_spacing = xt60_outside_w / 2 + dc_switch_outside_d / 2 + xt60_switch_clearance;
xt60_cutout_w = 19;
```

Use these function definitions:

```scad
function dc_connector_x() = dc_connector_type == "xt60"
    ? dc_toggle_x() - xt60_switch_center_spacing
    : barrel_jack_x;
function dc_toggle_x() = barrel_toggle_x + dc_toggle_x_extra;
```

Keep the assertion after both functions. This evaluates to XT60 x = -13.625 mm and retains barrel x = -13 mm.

- [ ] **Step 4: Run OpenSCAD to verify the assertion passes**

Run:

```bash
openscad -D 'view="dc_barrel_channel"' -o /tmp/plamp8_xt60_clearance_green.stl things/plamp8/plamp8.scad
```

Expected: exit status 0, a non-empty `/tmp/plamp8_xt60_clearance_green.stl`, and no assertion, empty-object, or missing-include errors.

- [ ] **Step 5: Verify barrel mode is unchanged**

Run:

```bash
openscad -D 'dc_connector_type="barrel"' -D 'view="dc_barrel_channel"' -o /tmp/plamp8_barrel_regression.stl things/plamp8/plamp8.scad
```

Expected: exit status 0 and a non-empty `/tmp/plamp8_barrel_regression.stl`. The derived functions evaluate to connector x = -13 mm, switch x = 8 mm, and label x = 23 mm, matching the previous barrel layout.

- [ ] **Step 6: Render all affected XT60 views with the repository generator**

Run:

```bash
rm -rf /tmp/plamp8_xt60_clearance
things/plamp8/generate.bash --revision xt60-clearance --preview --view dc_barrel_channel /tmp/plamp8_xt60_clearance/dc HEAD
things/plamp8/generate.bash --revision xt60-clearance --preview --view top_panel /tmp/plamp8_xt60_clearance/top HEAD
things/plamp8/generate.bash --revision xt60-clearance --preview --view sub_panel /tmp/plamp8_xt60_clearance/sub HEAD
```

Expected: each command exits 0; each output directory contains a non-empty STL; logs contain no assertion, empty-top-level-object, or missing-include warnings.

- [ ] **Step 7: Review the source diff and commit**

Run:

```bash
git diff --check -- things/plamp8/plamp8.scad
git diff -- things/plamp8/plamp8.scad
git add things/plamp8/plamp8.scad
git commit -m "Increase plamp8 XT60 switch clearance"
```

Expected: the diff changes only the XT60 fit parameters, connector-position function, and geometric assertion; the commit succeeds.

- [ ] **Step 8: Push the commits to GitHub**

Run:

```bash
git push origin main
```

Expected: GitHub advances `origin/main` to include the design, plan, and CAD implementation commits.
