# Plamp8 Service Pocket Separation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single Plamp8 service recess with separate `plamp`, revision, and combined `COM + USB` rounded rectangles while keeping the top-panel and sub-panel USB holes aligned.

**Architecture:** Derive a two-row, three-pocket layout from the existing 58 mm by 28 mm service region and 2 mm panel gap. Explicit pocket modules compose the recess, while shared content datums place labels and provide the canonical USB center used by the coupon, top panel, and sub-panel.

**Tech Stack:** OpenSCAD 2021.01, Python 3.11 `unittest`, Plamp direct CAD CLI

## Global Constraints

- Keep the service region at 58 mm by 28 mm.
- Use 2 mm between rows and between the two top pockets.
- Use 28 mm by 13 mm top pockets and one 58 mm by 13 mm bottom pocket.
- Center `plamp` and revision in their top pockets.
- Center `COM` in the left half and USB hardware in the right half of the bottom pocket.
- Use the same derived USB center for top-panel and sub-panel cutouts.
- Do not move or resize C13, enlarge the service region, or change USB clearances.
- Do not commit generated CAD artifacts, manifests, logs, or archived source.

---

### Task 1: Separate and align the service pockets

**Files:**
- Modify: `tests/test_things_cad_scripts.py:967-1082`
- Modify: `things/plamp8/plamp8.scad:427-447,530-615,1114-1152,1237-1295`

**Interfaces:**
- Consumes: `service_group_w/h`, `service_group_x/y`, `panel_region_gap`, `label_pocket(w, h)`, and `usb_c_connector_negative()`.
- Produces: derived pocket dimensions and content centers, canonical `usb_c_panel_x/y`, three explicit pocket modules, and `service_group_negative()`.

- [ ] **Step 1: Write the failing three-pocket source contract**

Replace `test_plamp8_service_region_is_one_equal_cell_grid` with a test that reads and compacts `plamp8.scad`, then requires these exact equations:

```python
for equation in (
    "service_pocket_gap = panel_region_gap;",
    "service_pocket_h = (service_group_h - service_pocket_gap) / 2;",
    "service_top_pocket_w = (service_group_w - service_pocket_gap) / 2;",
    "service_top_pocket_x_offset = (service_top_pocket_w + service_pocket_gap) / 2;",
    "service_row_y_offset = (service_pocket_h + service_pocket_gap) / 2;",
    "service_bottom_content_x_offset = service_group_w / 4;",
    "service_brand_x = service_group_x - service_top_pocket_x_offset;",
    "service_revision_x = service_group_x + service_top_pocket_x_offset;",
    "service_com_x = service_group_x - service_bottom_content_x_offset;",
    "usb_c_panel_x = service_group_x + service_bottom_content_x_offset;",
    "service_top_y = service_group_y + service_row_y_offset;",
    "service_bottom_y = service_group_y - service_row_y_offset;",
    "usb_c_panel_y = service_bottom_y;",
):
    with self.subTest(equation=equation):
        self.assertIn(equation, source)
```

Require `service_group_negative()` to call each pocket once:

```python
pockets = compact_scad(scad_module_body(source, "service_group_negative"))
for call in (
    "service_brand_pocket_negative();",
    "service_revision_pocket_negative();",
    "service_com_usb_pocket_negative();",
):
    self.assertIn(call, pockets)
self.assertNotIn("label_pocket(service_group_w,service_group_h);", compact)
```

Require exact pocket geometry:

```python
self.assertIn(
    "translate([-service_top_pocket_x_offset,service_row_y_offset,0])"
    "label_pocket(service_top_pocket_w,service_pocket_h);",
    compact_scad(scad_module_body(source, "service_brand_pocket_negative")),
)
self.assertIn(
    "translate([service_top_pocket_x_offset,service_row_y_offset,0])"
    "label_pocket(service_top_pocket_w,service_pocket_h);",
    compact_scad(scad_module_body(source, "service_revision_pocket_negative")),
)
self.assertIn(
    "translate([0,-service_row_y_offset,0])"
    "label_pocket(service_group_w,service_pocket_h);",
    compact_scad(scad_module_body(source, "service_com_usb_pocket_negative")),
)
```

Require the coupon's local USB center and the panels' shared global center:

```python
coupon = compact_scad(scad_module_body(source, "usb_c_panel_negative"))
self.assertIn("service_group_negative();", coupon)
self.assertIn(
    "translate([service_bottom_content_x_offset,-service_row_y_offset,0])"
    "usb_c_connector_negative();",
    coupon,
)
top_panel = compact_scad(scad_module_body(source, "top_panel_8ch"))
sub_panel = compact_scad(scad_module_body(source, "sub_panel_8ch_negative"))
self.assertIn(
    "translate([usb_c_panel_x,usb_c_panel_y,0])usb_c_connector_negative();",
    top_panel,
)
self.assertIn(
    "translate([usb_c_panel_x,usb_c_panel_y,0])sub_panel_usb_c_negative();",
    sub_panel,
)
self.assertIn(
    "assert(usb_top_sub_panel_aligned,"
    '"USBtopandsub-panelcutoutsmustshareonecenter");',
    compact,
)
```

Require the centered top-panel labels:

```python
for label_call in (
    "translate([service_brand_x,service_top_y,0])"
    "flush_label(top_panel_brand_text,top_panel_brand_font);",
    "translate([service_revision_x,service_top_y,0])flush_revision_label();",
    'translate([service_com_x,service_bottom_y,0])flush_label("COM",5);',
):
    self.assertIn(label_call, top_panel)
```

Update the frozen-center contract to require brand `(56, 17.5)`, revision `(86, 17.5)`, COM `(56.5, 2.5)`, and USB `(85.5, 2.5)` with these source fragments:

```python
"assert(service_brand_x == 56 && service_revision_x == 86",
" && service_top_y == 17.5 && service_com_x == 56.5",
" && usb_c_panel_x == 85.5 && service_bottom_y == 2.5,",
```

In the separator-bound test, replace:

```python
"c13_region_bottom_y&&service_bottom_y+max(usb_c_cutout_h/2,"
```

with:

```python
"c13_region_bottom_y&&usb_c_panel_y+max(usb_c_cutout_h/2,"
```

- [ ] **Step 2: Run the focused contract to verify RED**

```bash
UV_CACHE_DIR=/tmp/uv-cache /home/hugo/.local/bin/uv run --locked \
  python -m unittest \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_service_region_has_three_separate_pockets \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_plamp8_c13_hardware_and_service_centers_are_frozen -v
```

Expected: FAIL because the source still uses equal cells, one full-region pocket, and different top-panel USB placement text.

- [ ] **Step 3: Add the derived pocket and content datums**

Replace the `service_cell_*` and `service_left/right_*` block with:

```scad
service_pocket_gap = panel_region_gap;
service_pocket_h = (service_group_h - service_pocket_gap) / 2;
service_top_pocket_w = (service_group_w - service_pocket_gap) / 2;
service_top_pocket_x_offset =
    (service_top_pocket_w + service_pocket_gap) / 2;
service_row_y_offset = (service_pocket_h + service_pocket_gap) / 2;
service_bottom_content_x_offset = service_group_w / 4;
service_brand_x = service_group_x - service_top_pocket_x_offset;
service_revision_x = service_group_x + service_top_pocket_x_offset;
service_com_x = service_group_x - service_bottom_content_x_offset;
usb_c_panel_x = service_group_x + service_bottom_content_x_offset;
service_top_y = service_group_y + service_row_y_offset;
service_bottom_y = service_group_y - service_row_y_offset;
usb_c_panel_y = service_bottom_y;
```

Set `revision_x = service_com_x;`. In `usb_hardware_inside_region`, use `usb_c_panel_x` for both X bounds and `usb_c_panel_y` for both Y bounds. In `c13_service_cutters_clear_separator`, replace `service_bottom_y` with `usb_c_panel_y`. Remove `usb_coupon_connector_matches_service_offset`; the shared-datum assertion below replaces that equal-cell-era contract. Add:

```scad
usb_top_sub_panel_aligned =
    usb_c_panel_x == service_group_x + service_group_w / 4
    && usb_c_panel_y == service_group_y - service_row_y_offset;

assert(service_top_pocket_w * 2 + service_pocket_gap == service_group_w,
    "top service pockets and gap must exactly span the region");
assert(service_pocket_h * 2 + service_pocket_gap == service_group_h,
    "service pocket rows and gap must exactly span the region");
assert(service_brand_x == 56 && service_revision_x == 86
        && service_top_y == 17.5 && service_com_x == 56.5
        && usb_c_panel_x == 85.5 && service_bottom_y == 2.5,
    "service pocket content centers must remain fixed");
assert(usb_top_sub_panel_aligned,
    "USB top and sub-panel cutouts must share one center");
```

- [ ] **Step 4: Implement the pocket composition and centered content**

```scad
module service_brand_pocket_negative() {
    translate([-service_top_pocket_x_offset, service_row_y_offset, 0])
        label_pocket(service_top_pocket_w, service_pocket_h);
}

module service_revision_pocket_negative() {
    translate([service_top_pocket_x_offset, service_row_y_offset, 0])
        label_pocket(service_top_pocket_w, service_pocket_h);
}

module service_com_usb_pocket_negative() {
    translate([0, -service_row_y_offset, 0])
        label_pocket(service_group_w, service_pocket_h);
}

module service_group_negative() {
    service_brand_pocket_negative();
    service_revision_pocket_negative();
    service_com_usb_pocket_negative();
}

module usb_c_panel_negative() {
    service_group_negative();
    translate([service_bottom_content_x_offset, -service_row_y_offset, 0])
        usb_c_connector_negative();
}
```

Remove the redundant `usb_c_revision_negative()` cutter. In `usb_c_panel_unit()`, center the three labels with local offsets:

```scad
translate([-service_top_pocket_x_offset, service_row_y_offset, 0])
    flush_label(top_panel_brand_text, top_panel_brand_font);
translate([-service_bottom_content_x_offset, -service_row_y_offset, 0])
    flush_label("COM", 5);
if (include_revision)
    translate([service_top_pocket_x_offset, service_row_y_offset, 0])
        flush_revision_label();
```

In `top_panel_8ch()`, use:

```scad
translate([usb_c_panel_x, usb_c_panel_y, 0])
    usb_c_connector_negative();

translate([service_com_x, service_bottom_y, 0])
    flush_label("COM", 5);

if (include_revision) {
    translate([service_brand_x, service_top_y, 0])
        flush_label(top_panel_brand_text, top_panel_brand_font);
    translate([service_revision_x, service_top_y, 0])
        flush_revision_label();
}
```

Keep `sub_panel_8ch_negative()` using:

```scad
translate([usb_c_panel_x, usb_c_panel_y, 0])
    sub_panel_usb_c_negative();
```

- [ ] **Step 5: Run focused tests to verify GREEN**

```bash
UV_CACHE_DIR=/tmp/uv-cache /home/hugo/.local/bin/uv run --locked \
  python -m unittest tests.test_things_cad_scripts -v
```

Expected: all Plamp8 CAD source-contract tests pass.

- [ ] **Step 6: Commit**

```bash
git add things/plamp8/plamp8.scad tests/test_things_cad_scripts.py
git commit -m "Separate Plamp8 service pockets"
```

### Task 2: Validate and publish the CAD change

**Files:**
- Verify: `things/plamp8/plamp8.scad`
- Verify: `tests/test_things_cad_scripts.py`

**Interfaces:**
- Consumes: the three-pocket composition and canonical `usb_c_panel_x/y` from Task 1.
- Produces: a pushed branch passing metadata, assertion, CSG, and repository test gates.

- [ ] **Step 1: Validate and plan**

```bash
./bin/plamp cad validate plamp8 --json
./bin/plamp cad plan plamp8 --revision service-pocket-separation --view assembly --json
```

Expected: `"valid": true` and one planned `assembly` job.

- [ ] **Step 2: Run the fast OpenSCAD assertion/CSG gate**

```bash
/usr/bin/openscad \
  -o /tmp/plamp8-service-pocket-separation.csg \
  -D 'revision_string="service-pocket-separation"' \
  -D 'view="assembly"' \
  things/plamp8/plamp8.scad
test -s /tmp/plamp8-service-pocket-separation.csg
```

Expected: exit 0, non-empty CSG, and no `WARNING`, `ERROR`, or failed assertion.

- [ ] **Step 3: Run full verification**

```bash
UV_CACHE_DIR=/tmp/uv-cache /home/hugo/.local/bin/uv run --locked \
  python -m unittest discover -s tests -q
git diff --check origin/main...HEAD
```

Expected: all tests pass and the diff check prints nothing.

- [ ] **Step 4: Push for user rendering**

```bash
git push -u origin fix/plamp8-scad-definition-order
```

Expected: the remote branch advances. Report the exact commit and GitHub branch URL; the user will perform the final STL render locally.
