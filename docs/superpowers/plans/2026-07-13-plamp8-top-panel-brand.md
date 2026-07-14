# Plamp8 Top-Panel Brand Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an understated lowercase `plamp` inlay above the top-panel revision string.

**Architecture:** Reuse the existing shallow `label_pocket()` and `flush_label()` construction. Keep all brand dimensions parametric beside the revision-label dimensions, and derive the vertical position from `revision_y` so the relationship remains explicit.

**Tech Stack:** OpenSCAD and source-level shell verification.

## Global Constraints

- Do not run OpenSCAD locally.
- Brand text is lowercase `plamp` in DejaVu Sans at 4 mm.
- Brand pocket reuses the revision pocket's 28 mm by 9 mm dimensions.
- Brand center is `revision_y + 19`, top-aligning its pocket with `COM`, and is horizontally aligned to `revision_x`.
- Existing revision text and pocket remain unchanged.

---

### Task 1: Add the Top-Panel Brand Inlay

**Files:**
- Modify: `things/plamp8/plamp8.scad:311-314`
- Modify: `things/plamp8/plamp8.scad:806-852`

**Interfaces:**
- Consumes: `revision_x`, `revision_y`, `revision_label_h`, `label_pocket()`, and `flush_label()`.
- Produces: `top_panel_brand_text`, `top_panel_brand_font`, `top_panel_brand_y_offset`, and matching top-panel pocket/text geometry.

- [ ] **Step 1: Verify the brand source contract is absent**

Run:

```bash
rg -n 'top_panel_brand_text = "plamp"|top_panel_brand_y_offset = 12' things/plamp8/plamp8.scad
```

Expected: exit status 1 because the brand has not been implemented.

- [ ] **Step 2: Add the named brand dimensions**

Add beside the revision-label parameters:

```scad
top_panel_brand_text = "plamp";
top_panel_brand_font = 4;
top_panel_brand_y_offset = 19;
```

- [ ] **Step 3: Add matching pocket and flush text geometry**

Inside each `if (include_revision)` block in `top_panel_8ch()`, retain the existing revision operation and add a second operation at `[revision_x, revision_y + top_panel_brand_y_offset, 0]`. The negative block calls:

```scad
label_pocket(top_panel_revision_label_w, revision_label_h);
```

The positive text block calls:

```scad
flush_label(top_panel_brand_text, top_panel_brand_font);
```

- [ ] **Step 4: Verify the source geometry contract**

Run `rg` to confirm all three brand parameters and both geometry uses, then use `awk` to calculate the brand and `COM` pocket top edges as y = 24 mm. Expected: matching top edges, matching 28 mm brand/revision pocket widths, font 4 mm, and unchanged revision coordinates.

- [ ] **Step 5: Review, commit, and push**

Run:

```bash
git diff --check -- things/plamp8/plamp8.scad
git diff -- things/plamp8/plamp8.scad
git add things/plamp8/plamp8.scad
git commit -m "Add plamp8 top panel branding"
git push origin main
```

Expected: only the named brand parameters and top-panel pocket/text operations change in production code; `origin/main` advances to the implementation commit.
