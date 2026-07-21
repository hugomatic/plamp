import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def run(cmd, cwd, **kwargs):
    return subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        **kwargs,
    )


def init_git_repo(path: Path):
    run(["git", "init"], path, check=True)
    run(["git", "config", "user.email", "test@example.invalid"], path, check=True)
    run(["git", "config", "user.name", "Test User"], path, check=True)


def make_fake_openscad(path: Path):
    path.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
out=""
view=""
input="${@: -1}"
while [[ "$#" -gt 0 ]]; do
  case "$1" in
    -o) shift; out="$1" ;;
    view=*) view="${1#view=}" ;;
  esac
  shift || true
done
printf 'view=%s input=%s\\n' "$view" "$input" >> "$OPENSCAD_LOG"
printf 'solid %s\\nendsolid %s\\n' "$view" "$view" > "$out"
""",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


class ThingsCadScriptsTest(unittest.TestCase):
    def test_plamp8_flat_wall_corner_stack_contract(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()

        self.assertIn("wall_z_height = 83;", source)
        self.assertIn("corner_tab_t = 6;", source)
        self.assertIn("corner_screw_length = 25;", source)
        self.assertIn("corner_long_screw_length = 30;", source)
        self.assertNotIn("top_corner_screw_length", source)
        self.assertNotIn("bottom_corner_screw_length", source)
        self.assertIn("bottom_corner_nut_offset", source)
        self.assertIn('corner_screw_size = "M3";', source)
        self.assertIn('floor_screw_size = "M3";', source)
        self.assertIn(
            "corner_axis_inset = wall_t + panel_screw_inset;", source
        )
        self.assertIn(
            "corner_tab_outer_x = wall_t + corner_fit_clearance - corner_axis_inset;",
            source,
        )
        self.assertIn("corner_tab_inner_x = corner_tab_w / 2;", source)
        self.assertIn("bore_tangent_a = corner_screw_d / 2 / sqrt(2);", source)
        self.assertIn("corner_nut_shoulder_t = corner_tab_t - corner_nut_slot_l;", source)
        self.assertIn("corner_nut_retainer_t = 0.8;", source)
        self.assertIn("corner_nut_tab_extension = 16;", source)
        self.assertIn("corner_nut_detent_angle = 30;", source)
        self.assertIn(
            "corner_nut_detent_ramp_h = panel_nut_entry_detent * tan(corner_nut_detent_angle);",
            source,
        )
        self.assertIn(
            "top_stack_h = plate_t + sub_panel_h + 2 * corner_tab_t;",
            source,
        )
        self.assertIn(
            "bottom_stack_h = wall_t + 2 * corner_tab_t;",
            source,
        )
        self.assertIn(
            "bottom_corner_nut_offset = corner_screw_length - bottom_stack_h;",
            source,
        )
        self.assertIn("module support_free_horizontal_bore", source)
        self.assertNotIn("module corner_tab_gusset", source)
        self.assertNotIn("module clearance_tab_inward_gusset", source)
        self.assertNotIn("module corner_nut_axial_retainer", source)
        self.assertNotIn("corner_tab_root_l", source)
        self.assertIn("module corner_tab_positive", source)
        self.assertIn("module corner_nut_tab_positive", source)
        self.assertIn("module corner_tab_boss_positive", source)
        self.assertIn("corner_tab_boss_r = 5;", source)
        self.assertIn("module corner_clearance_tab", source)
        self.assertIn(
            "corner_nut_tab_length = corner_tab_t\n"
            "        + corner_nut_retainer_t\n"
            "        + corner_nut_tab_extension;",
            source,
        )
        self.assertIn("corner_nut_tab_length", source)
        self.assertIn("corner_nut_tab_bore_center_y", source)
        self.assertIn("module corner_nut_tab", source)
        self.assertIn("function corner_spine_y0()", source)
        self.assertIn("function corner_spine_y1(h)", source)
        self.assertIn("module corner_nut_tab_negatives", source)
        self.assertIn("module corner_nut_spine(h, print_orientation", source)
        self.assertIn(
            "corner_tab_boss_positive(spine_l, spine_y0 + spine_l / 2);",
            source,
        )
        self.assertEqual(source.count("corner_nut_tab_negatives("), 4)
        self.assertIn("corner_nut_spine(h, print_orientation);", source)
        wall_tabs = source.split("module wall_corner_tabs", 1)[1].split(
            "module flat_wall", 1
        )[0]
        self.assertIn("if (nut_owner)", wall_tabs)
        self.assertIn("corner_nut_spine(h, print_orientation);", wall_tabs)
        self.assertEqual(
            wall_tabs.count("corner_clearance_tab(print_orientation);"), 2
        )
        self.assertIn("module support_free_m3_nut_trap", source)
        self.assertIn("module corner_nut_retention_detents", source)
        nut_entry = source.split("module corner_nut_entry_negative", 1)[1].split(
            "module ", 1
        )[0]
        self.assertIn("corner_nut_retention_detents(", nut_entry)
        self.assertIn("module corner_wall_coupon", source)
        self.assertIn("module corner_coupon", source)
        self.assertIn("module wall_corner_fastener_assembly", source)
        self.assertIn(
            "outer_edge_offset = panel_screw_inset - coupon_assembly_clearance;",
            source,
        )
        self.assertIn("coupon_plate_column_x = 100;", source)
        self.assertIn('view == "corner_coupon"', source)
        self.assertIn('view == "wall_corner_fastener_test"', source)
        view_line = next(
            line for line in source.splitlines() if line.startswith("view =")
        )
        self.assertIn("corner_coupon", view_line)
        self.assertNotIn("wall_corner_fastener_test", view_line)
        self.assertIn('view == "wall_corner_fastener_assembly"', source)
        self.assertIn("sub_panel_base_h = 5;", source)
        self.assertIn("sub_panel_h = 10;", source)

    def test_plamp8_sub_panel_replaces_ledge_ring_and_corner_screws_fill_nuts(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()

        for obsolete in ("ledge_ring", "ledge_top_z", "ph_ledge", "top_ledge"):
            self.assertNotIn(obsolete, source)
        self.assertIn("sub_panel_bottom_z = -(plate_t + sub_panel_h);", source)
        self.assertIn("sub_panel_base_h = 5;", source)
        self.assertIn("sub_panel_h = 10;", source)
        self.assertIn("corner_screw_length = 25;", source)
        self.assertIn("corner_long_screw_length = 30;", source)
        self.assertIn(
            "top_stack_h = plate_t + sub_panel_h + 2 * corner_tab_t;", source
        )
        self.assertIn("bottom_stack_h = wall_t + 2 * corner_tab_t;", source)
        self.assertIn(
            "bottom_corner_nut_offset = corner_screw_length - bottom_stack_h;",
            source,
        )
        self.assertNotIn("corner_screw_tip_allowance", source)
        self.assertIn("assert(top_stack_h == corner_screw_length", source)
        self.assertIn(
            "assert(bottom_stack_h + bottom_corner_nut_offset == corner_screw_length",
            source,
        )
        self.assertIn("assert(corner_long_screw_length <= top_long_screw_enclosure_h", source)
        self.assertIn("assert(corner_long_screw_length <= bottom_long_screw_enclosure_h", source)
        self.assertIn(
            "h + sub_panel_bottom_z - corner_tab_t / 2;", source
        )
        fastener_assembly = source.split(
            "module wall_corner_fastener_assembly", 1
        )[1].split("module corner_coupon", 1)[0]
        self.assertEqual(fastener_assembly.count("corner_coupon_plate("), 3)
        coupon = source.split("module corner_coupon()", 1)[1].split(
            "module panel_corner_fastener_test", 1
        )[0]
        self.assertEqual(coupon.count("corner_coupon_plate("), 3)

    def test_plamp8_has_four_flat_printed_mitred_wall_views(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
        view_line = next(
            line for line in source.splitlines() if line.startswith("view =")
        )

        for name in ("north_wall", "south_wall", "west_wall", "east_wall"):
            self.assertIn(name, view_line)
            self.assertIn(
                f"module {name}_context(",
                source,
            )
            self.assertIn(
                f"module {name}(",
                source,
            )
            self.assertIn(f'view == "{name}"', source)
        self.assertNotIn(" walls,", view_line)
        self.assertNotIn('view == "walls"', source)
        self.assertNotIn("module walls_context", source)
        self.assertNotIn("module walls()", source)
        self.assertNotIn("feature_ledge", source)
        self.assertNotIn("feature_psu_tie_wrap_anchors_wall", source)
        self.assertNotIn("module psu_right_wall_tie_wrap_anchors_in_box", source)
        self.assertNotIn("psu_wall_anchor_z", source)
        self.assertNotIn("module side_wall_psu_vents", source)
        self.assertNotIn("module legacy_wall_revision_negative", source)
        self.assertNotIn("module panel_corner_fastener_bosses", source)
        self.assertNotIn("module panel_corner_screw_holes_in_box", source)
        self.assertNotIn("module side_loaded_panel_nut_traps", source)
        self.assertNotIn("internal_clearance_h", source)
        self.assertNotIn("psu_wall_clearance", source)
        self.assertNotIn("corner_r", source)
        self.assertIn("module wall_mitre_negative", source)
        self.assertIn("module wall_revision_negative", source)
        self.assertIn("wall_revision_top_margin = 10;", source)
        revision_module = source.split("module wall_revision_negative", 1)[1].split(
            "module ", 1
        )[0]
        self.assertNotIn("mirror(", revision_module)
        self.assertIn(
            'revision_y = vent_mode == "full" ? h - wall_revision_top_margin : h / 2;',
            revision_module,
        )
        self.assertIn("module wall_stiffening_ribs", source)
        self.assertIn(
            "? [vent_wall_margin + vent_hole_spacing / 2, "
            "full_vent_center_rib_x(length), length - 21]",
            source,
        )
        self.assertIn("transverse_rib_y = top_nut_tab_center_y(h)", source)
        self.assertIn("corner_nut_shoulder_t / 2;", source)
        self.assertIn("floor_rib_y0 = wall_t;", source)
        self.assertIn("floor_rib_x0 = floor_locator_end_offset", source)
        self.assertIn("floor_rib_x1 = length - floor_rib_x0;", source)
        self.assertIn("transverse_rib_x0", source)
        self.assertIn('vent_mode == "half" ? length / 2', source)
        self.assertNotIn("module bottom_corner_locator_key", source)

    def test_plamp8_box_coarse_vents_are_point_up_hexagons(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()

        self.assertIn("box_coarse_vents = true;", source)
        vent_negative = source.split("module wall_vent_negative", 1)[1].split(
            "module ", 1
        )[0]
        self.assertIn("rotate([0, 0, coarse_vents ? 30 : 0])", vent_negative)
        self.assertIn("$fn = coarse_vents ? 6 : render_fn", vent_negative)

        vent_grid = source.split("module wall_vent_negatives", 1)[1].split(
            "module ", 1
        )[0]
        self.assertIn("coarse_vents = false", vent_grid)
        self.assertIn("wall_vent_negative(x, y, coarse_vents);", vent_grid)
        self.assertEqual(source.count("for (x = vent_xs, y = vent_ys)"), 1)

        for wall in ("north", "south", "west", "east"):
            self.assertIn(
                f"module {wall}_wall(",
                source,
            )
            self.assertIn(
                f"module {wall}_wall_context(",
                source,
            )

    def test_plamp8_box_view_reuses_complete_wall_and_floor_geometry(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
        view_line = next(
            line for line in source.splitlines() if line.startswith("view =")
        )

        self.assertIn("box", view_line)
        self.assertIn('view == "box"', source)
        box_module = source.split("module box()", 1)[1].split(
            "module assembly()", 1
        )[0]

        for wall in ("north", "south", "west", "east"):
            self.assertIn(
                f"{wall}_wall_context(",
                box_module,
            )
            self.assertIn(
                "mitre_overlap = box_wall_mitre_overlap",
                box_module,
            )
        self.assertIn("floor_context();", box_module)
        self.assertIn("union()", box_module)
        self.assertNotIn("flat_wall(", box_module)
        self.assertNotIn("wall_corner_tabs(", box_module)
        self.assertNotIn("floor_locator_", box_module)
        self.assertNotIn("floor_corner_fastener_holes", box_module)

        self.assertIn("corner_nut_spine(h, print_orientation);", source)
        self.assertIn("floor_corner_fastener_holes();", source)
        self.assertIn("floor_locator_lands();", source)
        self.assertIn("floor_locator_keys();", source)
        self.assertIn("floor_locator_notches(length);", source)

    def test_plamp8_box_uses_box_only_mitre_overlap(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()

        self.assertIn("box_wall_mitre_overlap = 0.02;", source)
        mitre_module = source.split("module wall_mitre_negative", 1)[1].split(
            "module ", 1
        )[0]
        self.assertIn("mitre_overlap = 0", mitre_module)
        self.assertIn("- mitre_overlap", mitre_module)
        self.assertIn("+ mitre_overlap", mitre_module)

        for wall in ("north", "south", "west", "east"):
            self.assertIn(
                f"module {wall}_wall_context(",
                source,
            )
            self.assertIn(
                f"module {wall}_wall(",
                source,
            )

    def test_plamp8_corner_fasteners_follow_print_orientation(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()

        self.assertIn('flat_wall_print_orientation = "flat_wall";', source)
        self.assertIn('box_print_orientation = "box";', source)
        self.assertIn("corner_nut_entry_angle = 45;", source)
        self.assertIn("module corner_screw_bore(", source)
        self.assertIn("module corner_nut_entry_negative(", source)
        self.assertIn("rotate([0, corner_nut_entry_angle, 0])", source)
        self.assertIn("print_orientation == box_print_orientation", source)

        box_module = source.split("module box()", 1)[1].split(
            "module assembly()", 1
        )[0]
        self.assertEqual(
            box_module.count("print_orientation = box_print_orientation"), 4
        )

    def test_plamp8_preview_separates_panels_only_in_preview(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()

        self.assertIn("assembly_preview_gap = $preview ? 0.01 : 0;", source)
        mounted = source.split("module mounted_top_panel", 1)[1].split(
            "module ", 1
        )[0]
        self.assertIn("-plate_t + assembly_preview_gap", mounted)

    def test_plamp8_east_center_rib_sits_between_vent_columns(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()

        self.assertIn("function vent_gap_center_left_of(x)", source)
        self.assertIn("function full_vent_center_rib_x(length)", source)
        self.assertIn("east_center_rib_x = full_vent_center_rib_x(box_d);", source)
        self.assertIn("vent_rib_edge_clearance =", source)
        self.assertIn("assert(east_center_rib_x == 105", source)
        self.assertIn("assert(vent_rib_edge_clearance >= 1", source)
        self.assertLess(
            source.index("box_d = box_inner_d + 2 * wall_t;"),
            source.index("east_center_rib_x = full_vent_center_rib_x(box_d);"),
        )
        self.assertNotIn("module bottom_corner_locator_notch", source)
        self.assertNotIn("module wall_bottom_locator_keys", source)
        self.assertNotIn("module wall_bottom_locator_notches", source)
        self.assertNotIn("module corner_locator_key", source)
        self.assertNotIn("module corner_locator_notch", source)
        self.assertNotIn("module wall_locator_keys", source)
        self.assertNotIn("module wall_locator_notches", source)

    def test_plamp8_walls_have_full_compass_name_engravings(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()

        self.assertIn("assembly_name_depth = 0.6;", source)
        self.assertIn("assembly_name_font = 7;", source)
        self.assertIn("wall_assembly_name_y =", source)
        self.assertIn("module wall_assembly_name_negative", source)

        flat_wall = source.split("module flat_wall", 1)[1].split("module ", 1)[0]
        self.assertIn('wall_name = ""', flat_wall)
        self.assertIn("wall_assembly_name_negative(length, wall_name);", flat_wall)

        for wall in ("north", "south", "east", "west"):
            wall_signature = f"module {wall}_wall("
            context_signature = f"module {wall}_wall_context("
            self.assertIn(wall_signature, source)
            self.assertIn(context_signature, source)
            wall_module = source.split(
                wall_signature, 1
            )[1].split("module ", 1)[0]
            self.assertIn(f'wall_name = "{wall.upper()}"', wall_module)

            context_module = source.split(context_signature, 1)[1].split(
                "module ", 1
            )[0]
            self.assertIn("coarse_vents = coarse_vents", context_module)
            self.assertIn("mitre_overlap = mitre_overlap", context_module)

    def test_plamp8_floor_has_matching_oriented_compass_names(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()

        self.assertIn("floor_assembly_name_inset = 14;", source)
        self.assertIn("module floor_assembly_name_negative", source)
        self.assertIn("module floor_assembly_name_negatives", source)

        floor_names = source.split(
            "module floor_assembly_name_negatives", 1
        )[1].split("module ", 1)[0]
        expected = (
            '("NORTH", box_w / 2, box_d - wall_t - floor_assembly_name_inset, 0)',
            '("EAST", box_w - wall_t - floor_assembly_name_inset, box_d / 2, -90)',
            '("SOUTH", box_w / 2, wall_t + floor_assembly_name_inset, 180)',
            '("WEST", wall_t + floor_assembly_name_inset, box_d / 2, 90)',
        )
        for call in expected:
            self.assertIn(f"floor_assembly_name_negative{call};", floor_names)

        floor_context = source.split("module floor_context()", 1)[1].split(
            "module ", 1
        )[0]
        self.assertIn("floor_assembly_name_negatives();", floor_context)

    def test_plamp8_floor_uses_corner_m3_wall_fasteners(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()

        self.assertIn('floor_screw_size = "M3";', source)
        self.assertIn("function enclosure_corner_points()", source)
        self.assertIn("module floor_corner_fastener_holes", source)
        self.assertNotIn("module floor_corner_lands", source)
        self.assertNotIn("floor_corner_land_radial_ligament", source)
        self.assertIn("module floor_locator_keys", source)
        self.assertIn("module floor_locator_lands", source)
        self.assertIn("module floor_locator_key_shape", source)
        floor_key = source.split("module floor_locator_key_shape", 1)[1].split(
            "module ", 1
        )[0]
        self.assertNotIn("hull()", floor_key)
        self.assertNotIn("lead_in", floor_key)
        self.assertIn("floor_locator_depth = 2;", source)
        self.assertIn("floor_locator_clearance = 0.25;", source)
        self.assertIn("x_locator_starts", source)
        self.assertIn("y_locator_starts", source)
        self.assertIn("module bottom_m3_flat_head_recess", source)
        self.assertGreaterEqual(source.count("bottom_m3_flat_head_recess("), 3)
        self.assertNotIn("function floor_fastener_points()", source)
        self.assertNotIn("function floor_wall_tab_points()", source)
        self.assertNotIn("module floor_wall_tabs()", source)
        for obsolete in (
            "floor_perimeter_rib",
            "floor_rib_corner",
            "floor_rib_t",
            "floor_rib_h",
            "floor_rib_corner_l",
            "floor_nut_trap_d",
            "floor_nut_trap_h",
        ):
            self.assertNotIn(obsolete, source)

    def test_plamp8_assembly_has_individual_wall_controls_and_height(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()

        for control in (
            "show_north_wall",
            "show_south_wall",
            "show_west_wall",
            "show_east_wall",
        ):
            self.assertIn(f"{control} = true;", source)
            self.assertIn(f"if ({control})", source)
        self.assertNotIn("show_walls = true;", source)
        self.assertIn("show_dc_dc = true;", source)
        self.assertIn("if (show_dc_dc)", source)
        self.assertIn("internal_components(show_psu, show_dc_dc, show_relay);", source)
        self.assertIn("box_h = wall_z_height;", source)
        self.assertIn("assert(wall_z_height", source)
        self.assertNotIn("show_ledge_ring", source)
        self.assertIn("assert(sub_panel_bottom_z == -(plate_t + sub_panel_h)", source)
        self.assertIn("assert(top_nut_tab_center_y(box_h) < top_clearance_tab_center_y(box_h)", source)
        self.assertIn("assert(bottom_clearance_tab_center_y() < bottom_nut_tab_center_y()", source)

    def test_plamp8_transparent_components_have_raised_assembly_labels(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()

        self.assertIn("component_label_t = 0.8;", source)
        self.assertNotIn("component_label_color", source)
        self.assertIn("module raised_component_label", source)
        self.assertIn('raised_component_label("12V PSU"', source)
        self.assertIn('raised_component_label("DC/DC"', source)
        self.assertIn('raised_component_label("RELAYS"', source)
        self.assertIn("linear_extrude(height = component_label_t)", source)
        label_module = source.split("module raised_component_label", 1)[1].split(
            "module ", 1
        )[0]
        self.assertNotIn("color(", label_module)

        for module_name in (
            "psu_keepout",
            "converter_keepout",
            "relay_board_keepout",
        ):
            keepout = source.split(f"module {module_name}", 1)[1].split(
                "module ", 1
            )[0]
            self.assertIn("raised_component_label(", keepout)

        self.assertRegex(
            source,
            r"color\(\[1, 0\.6, 0\.1, 0\.25\]\)\s*\{[\s\S]*?"
            r'raised_component_label\("12V PSU", psu_label_font, psu_h, 0\);\s*\}',
        )
        self.assertRegex(
            source,
            r"color\(\[0\.8, 0\.25, 0\.95, 0\.25\]\)\s*\{[\s\S]*?"
            r'raised_component_label\("DC/DC", converter_label_font, converter_h, '
            r"-internal_converter_rot_z\);\s*\}",
        )
        self.assertRegex(
            source,
            r"color\(\[0\.1, 0\.7, 0\.2, 0\.25\]\)\s*\{[\s\S]*?"
            r'raised_component_label\("RELAYS", relay_label_font, relay_h, '
            r"-internal_relay_rot_z\);\s*\}",
        )

        for module_name in (
            "psu_footprint",
            "converter_footprint",
            "relay_footprint",
        ):
            footprint = source.split(f"module {module_name}", 1)[1].split(
                "module ", 1
            )[0]
            self.assertNotIn("raised_component_label(", footprint)

    def test_plamp8_sub_panel_xt60_nut_clearance_and_revision_depth(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()

        self.assertIn("xt60_nut_clearance_d = 7;", source)
        self.assertIn("sub_panel_revision_depth = 0.6;", source)
        self.assertRegex(
            source,
            r"module sub_panel_left_xt60_nut_clearances_negative\(\) \{[\s\S]*?for \(i = \[0, 2\]\)[\s\S]*?dc_channel_x\(i\) \+ dc_connector_x\(\) - xt60_screw_spacing / 2[\s\S]*?sub_panel_base_h[\s\S]*?cylinder\([\s\S]*?h = sub_panel_h - sub_panel_base_h \+ 0\.1,[\s\S]*?d = xt60_nut_clearance_d",
        )
        self.assertIn("sub_panel_left_xt60_nut_clearances_negative();", source)
        self.assertIn(
            "write_text(revision_string, 4, -sub_panel_revision_depth);",
            source,
        )

    def test_plamp8_usb_com_fit_dimensions_and_panel_cutouts(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
        usb_unit = source.split("module usb_c_panel_unit", 1)[1].split("module c13_inlet_negative", 1)[0]

        self.assertIn("usb_c_cutout_w = 12;", source)
        self.assertIn("usb_c_cutout_h = 10;", source)
        self.assertIn("usb_c_cutout_r = 1.5;", source)
        self.assertIn("usb_c_screw_spacing = 17;", source)
        self.assertIn("sub_panel_usb_c_cutout_w = 13;", source)
        self.assertIn("sub_panel_usb_c_cutout_h = 10.5;", source)
        self.assertRegex(
            source,
            r"module usb_c_panel_negative\(\) \{\s*rounded_rect_cutout\(usb_c_cutout_w, usb_c_cutout_h, usb_c_cutout_r\);",
        )
        self.assertRegex(
            source,
            r"module sub_panel_usb_c_negative\(\) \{\s*rect_cutout\(sub_panel_usb_c_cutout_w, sub_panel_usb_c_cutout_h\);",
        )
        self.assertIn('panel_screw_size = "M3";', source)
        self.assertIn("panel_screw_length = 20;", source)
        self.assertIn("panel_screw_tip_protrusion = 1;", source)
        self.assertIn("panel_screw_land_d = 9.5;", source)
        self.assertIn("usb_c_screw_d = 3.4;", source)
        self.assertIn("usb_c_screw_head_d = 5.61;", source)
        self.assertIn("usb_c_screw_surface_z = plate_t - 0.5;", source)
        self.assertIn(
            "topside_countersunk_screw_hole(usb_c_screw_d, usb_c_screw_head_d, usb_c_screw_surface_z)",
            source,
        )
        self.assertIn("module topside_countersunk_screw_hole", source)
        self.assertNotIn("module underside_countersunk_screw_hole", source)
        self.assertIn("fit_plate(usb_c_panel_w, usb_c_panel_h);", usb_unit)
        self.assertNotIn("alignment_walls", usb_unit)
        self.assertIn("module panel_corner_screw_lands", source)
        self.assertIn("module panel_corner_fastener_boss", source)
        self.assertIn("module side_loaded_panel_nut_trap", source)
        self.assertIn("panel_nut_entry_detent", source)
        self.assertIn("module self_supporting_nut_trap_roof", source)
        self.assertRegex(
            source,
            r"module side_loaded_panel_nut_trap\(direction = 1\)[\s\S]*?self_supporting_nut_trap_roof",
        )
        self.assertIn("module panel_corner_fastener_test", source)
        self.assertIn('view == "panel_corner_fastener_test"', source)

    def test_template_bash_can_select_scad_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            things = tmp_path / "things"
            shutil.copytree(REPO_ROOT / "things" / "3d_template", things / "3d_template")
            shutil.copy2(REPO_ROOT / "things" / "template.bash", things / "template.bash")
            templates = things / "3d_template" / "scad"
            templates.mkdir(exist_ok=True)
            (templates / "cover.scad").write_text('view = "plate"; // [plate]\n// cover template\n')

            result = run(["bash", "template.bash", "new_cover", "--template", "cover"], things)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((things / "new_cover" / "generate.bash").exists())
            self.assertEqual(
                (things / "new_cover" / "new_cover.scad").read_text(),
                'view = "plate"; // [plate]\n// cover template\n',
            )
            self.assertIn('cad="new_cover"', (things / "new_cover" / "generate.bash").read_text())

    def test_template_bash_lists_available_templates_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            things = tmp_path / "things"
            shutil.copytree(REPO_ROOT / "things" / "3d_template", things / "3d_template")
            shutil.copy2(REPO_ROOT / "things" / "template.bash", things / "template.bash")
            templates = things / "3d_template" / "scad"
            templates.mkdir(exist_ok=True)
            (templates / "basic.scad").write_text("// basic\n")

            result = run(["bash", "template.bash", "new_part", "--template", "missing"], things)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Available templates:", result.stderr)
            self.assertIn("basic", result.stderr)

    def test_generate_bash_defaults_to_latest_part_commit_and_uses_ordered_views(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo = tmp_path / "repo"
            part = repo / "things" / "multi_part"
            part.mkdir(parents=True)
            init_git_repo(repo)
            generate = (REPO_ROOT / "things" / "3d_template" / "generate.bash").read_text()
            (part / "generate.bash").write_text(generate.replace("__cad__name__", "multi_part"))
            (part / "generate.bash").chmod(0o755)
            (part / "lib.scad").write_text("module helper() { cube([1, 1, 1]); }\n")
            (part / "multi_part.scad").write_text(
                'include <lib.scad>\nview = "assembly"; // [assembly, camera_clip, plate]\n'
                'revision_string = "dev";\nhelper();\n'
            )
            run(["git", "add", "."], repo, check=True)
            source_commit_env = {
                **os.environ,
                "GIT_AUTHOR_DATE": "2020-09-02T03:04:05+00:00",
                "GIT_COMMITTER_DATE": "2020-09-02T03:04:05+00:00",
            }
            run(
                ["git", "commit", "-m", "add cad part"],
                repo,
                check=True,
                env=source_commit_env,
            )
            part_commit = run(
                ["git", "rev-parse", "--short", "HEAD"], repo, check=True
            ).stdout.strip()
            (repo / "README.md").write_text("unrelated change\n")
            run(["git", "add", "README.md"], repo, check=True)
            run(["git", "commit", "-m", "change unrelated file"], repo, check=True)

            help_result = run(["./generate.bash", "--help"], part)
            self.assertEqual(help_result.returncode, 0, help_result.stderr)
            self.assertIn("prints/multi_part_september02", help_result.stdout)
            self.assertIn(
                f"prints/multi_part_september02_replacement {part_commit}",
                help_result.stdout,
            )
            self.assertIn("not for printing", help_result.stdout)
            self.assertNotIn(" HEAD", help_result.stdout)

            fake_openscad = tmp_path / "openscad"
            make_fake_openscad(fake_openscad)
            log = tmp_path / "openscad.log"
            target = tmp_path / "rendered"

            env = {**os.environ, "OPENSCAD_BIN": str(fake_openscad), "OPENSCAD_LOG": str(log)}
            result = run(["./generate.bash", str(target)], part, env=env)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                [p.name for p in sorted(target.glob("*.stl"))],
                [
                    f"multi_part_assembly_{part_commit}.stl",
                    f"multi_part_camera_clip_{part_commit}.stl",
                    f"multi_part_plate_{part_commit}.stl",
                ],
            )
            rendered_views = [
                line.split()[0].removeprefix("view=").strip('"')
                for line in log.read_text().splitlines()
            ]
            self.assertEqual(rendered_views, ["assembly", "camera_clip", "plate"])

    def test_generate_bash_preview_uses_render_fn_without_ball_quality(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo = tmp_path / "repo"
            part = repo / "things" / "preview_part"
            part.mkdir(parents=True)
            init_git_repo(repo)
            generate = (REPO_ROOT / "things" / "3d_template" / "generate.bash").read_text()
            (part / "generate.bash").write_text(generate.replace("__cad__name__", "preview_part"))
            (part / "generate.bash").chmod(0o755)
            (part / "preview_part.scad").write_text('view = "plate"; // [plate]\ncube([1,1,1]);\n')
            run(["git", "add", "."], repo, check=True)
            run(["git", "commit", "-m", "add cad part"], repo, check=True)
            fake_openscad = tmp_path / "openscad"
            make_fake_openscad(fake_openscad)
            log = tmp_path / "openscad.log"
            target = tmp_path / "rendered"

            env = {**os.environ, "OPENSCAD_BIN": str(fake_openscad), "OPENSCAD_LOG": str(log)}
            result = run(["./generate.bash", "--preview", str(target), "HEAD"], part, env=env)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("render_fn=24", result.stdout)
            self.assertNotIn("ball_quality=", result.stdout)

    def test_generate_bash_refuses_dirty_part_without_revision_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo = tmp_path / "repo"
            part = repo / "things" / "dirty_part"
            other = repo / "app"
            part.mkdir(parents=True)
            other.mkdir()
            init_git_repo(repo)
            generate = (REPO_ROOT / "things" / "3d_template" / "generate.bash").read_text()
            (part / "generate.bash").write_text(generate.replace("__cad__name__", "dirty_part"))
            (part / "generate.bash").chmod(0o755)
            (part / "dirty_part.scad").write_text('view = "plate"; // [plate]\ncube([1,1,1]);\n')
            (other / "unrelated.py").write_text("print('clean enough')\n")
            run(["git", "add", "."], repo, check=True)
            run(["git", "commit", "-m", "add files"], repo, check=True)
            (other / "unrelated.py").write_text("print('ignored dirty')\n")
            result_with_unrelated_dirty = run(["./generate.bash", str(tmp_path / "ok"), "HEAD"], part)
            (part / "dirty_part.scad").write_text('view = "plate"; // [plate]\nsphere(1);\n')

            result = run(["./generate.bash", str(tmp_path / "blocked"), "HEAD"], part)

            self.assertNotIn("part directory has uncommitted changes", result_with_unrelated_dirty.stderr)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("part directory has uncommitted changes", result.stderr)
            self.assertIn("git status --porcelain -- things/dirty_part", result.stderr)


if __name__ == "__main__":
    unittest.main()
