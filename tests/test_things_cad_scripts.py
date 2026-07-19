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
        self.assertIn("corner_tab_t = 4;", source)
        self.assertIn("ledge_ring_t = 3;", source)
        self.assertIn("top_corner_screw_length = 25;", source)
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
            "top_stack_h = plate_t + sub_panel_h + ledge_ring_t + 2 * corner_tab_t + corner_nut_retainer_t;",
            source,
        )
        self.assertIn(
            "bottom_stack_h = wall_t + 2 * corner_tab_t + corner_nut_retainer_t;",
            source,
        )
        self.assertIn("module support_free_horizontal_bore", source)
        self.assertNotIn("module corner_tab_gusset", source)
        self.assertNotIn("module clearance_tab_inward_gusset", source)
        self.assertNotIn("module corner_nut_axial_retainer", source)
        self.assertNotIn("corner_tab_root_l", source)
        self.assertIn("module corner_tab_positive", source)
        self.assertIn("module corner_nut_tab_positive", source)
        self.assertIn("module corner_clearance_tab", source)
        self.assertIn("corner_tab_t + corner_nut_retainer_t", source)
        self.assertIn("corner_nut_tab_length", source)
        self.assertIn("corner_nut_tab_bore_center_y", source)
        self.assertIn("module corner_nut_tab", source)
        self.assertIn("module support_free_m3_nut_trap", source)
        self.assertIn("module corner_nut_retention_detents", source)
        nut_trap = source.split("module support_free_m3_nut_trap", 1)[1].split(
            "module ", 1
        )[0]
        self.assertIn("corner_nut_retention_detents(", nut_trap)
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

    def test_plamp8_ledge_ring_is_separate_and_preserves_panel_stack(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()

        self.assertIn("module ledge_ring_context", source)
        self.assertIn("module ledge_ring()", source)
        self.assertIn("ledge_ring_north_rail_w = 3;", source)
        self.assertIn("ledge_ring_north_clearance_min = 0.75;", source)
        self.assertIn("ph_ledge_gap_clearance = 0.5;", source)
        self.assertIn("module ledge_ring_ph_switch_clearances", source)
        self.assertIn('view == "ledge_ring"', source)
        self.assertIn("feature_ph_ledge_holes", source)
        self.assertIn("for (i = [0, 1])", source)
        self.assertIn("top_ledge_gap_start(i)", source)
        self.assertIn("top_ledge_gap_end(i, box_inner_w)", source)
        self.assertIn("ledge_w - ledge_ring_north_rail_w", source)
        self.assertIn(
            "assert(ledge_ring_north_clearance >= ledge_ring_north_clearance_min",
            source,
        )
        self.assertNotIn("quarter_round(", source)
        self.assertIn("sub_panel_base_h = 5;", source)
        self.assertIn("sub_panel_h = 10;", source)

    def test_plamp8_has_four_flat_printed_mitred_wall_views(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
        view_line = next(
            line for line in source.splitlines() if line.startswith("view =")
        )

        for name in ("north_wall", "south_wall", "west_wall", "east_wall"):
            self.assertIn(name, view_line)
            self.assertIn(f"module {name}_context", source)
            self.assertIn(f"module {name}()", source)
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
        revision_module = source.split("module wall_revision_negative", 1)[1].split(
            "module ", 1
        )[0]
        self.assertNotIn("mirror(", revision_module)
        self.assertIn("module wall_stiffening_ribs", source)
        self.assertIn('vent_mode == "half" ? length / 2', source)
        self.assertNotIn("module bottom_corner_locator_key", source)
        self.assertNotIn("module bottom_corner_locator_notch", source)
        self.assertNotIn("module wall_bottom_locator_keys", source)
        self.assertNotIn("module wall_bottom_locator_notches", source)
        self.assertNotIn("module corner_locator_key", source)
        self.assertNotIn("module corner_locator_notch", source)
        self.assertNotIn("module wall_locator_keys", source)
        self.assertNotIn("module wall_locator_notches", source)

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
            "show_ledge_ring",
        ):
            self.assertIn(f"{control} = true;", source)
            self.assertIn(f"if ({control})", source)
        self.assertNotIn("show_walls = true;", source)
        self.assertIn("box_h = wall_z_height;", source)
        self.assertIn("assert(wall_z_height", source)
        self.assertIn("assert(ledge_top_z == -(plate_t + sub_panel_h)", source)
        self.assertIn("assert(top_nut_tab_center_y(box_h) < top_clearance_tab_center_y(box_h)", source)
        self.assertIn("assert(bottom_clearance_tab_center_y() < bottom_nut_tab_center_y()", source)

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
