import json
import re
import subprocess
import unittest
from pathlib import Path

from plamp.cad_model import load_model
from plamp.cad_manufacturing import DirectiveSource, normalize_slicing
from plamp.cad_system import load_system


REPO_ROOT = Path(__file__).resolve().parents[1]


def scad_module_body(source, module_name):
    return source.split(f"module {module_name}(", 1)[1].split("module ", 1)[0]


def compact_scad(source):
    return re.sub(r"\s+", "", source)


def run(cmd, cwd, **kwargs):
    return subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        **kwargs,
    )


class ThingsCadScriptsTest(unittest.TestCase):
    def test_repository_assemblies_are_not_printable(self):
        assembly_sets = {
            "plamp8": ("", "assembly", "wall_corner_fastener_assembly"),
            "iharvest_cover": ("", "assembly"),
            "plamp_stand": ("", "assembly"),
            "peristaltic_pump_stand": ("assembly",),
        }
        for model_id, set_names in assembly_sets.items():
            with self.subTest(model=model_id):
                model = load_model(
                    model_id,
                    REPO_ROOT / "things" / model_id / f"{model_id}.cad.json",
                    REPO_ROOT,
                )
                for set_name in set_names:
                    with self.subTest(set=set_name):
                        self.assertFalse(model.sets[set_name].printable)
                        self.assertEqual(dict(model.sets[set_name].slicing), {})

    def test_plamp8_top_panel_recommends_ironing_without_supports(self):
        model = load_model(
            "plamp8", REPO_ROOT / "things" / "plamp8" / "plamp8.cad.json",
            REPO_ROOT,
        )
        policy, _notes = normalize_slicing(
            model.sets["top_panel"].slicing,
            DirectiveSource("set:plamp8/top_panel"),
        )
        self.assertEqual(policy["ironing"].value, "recommended")
        self.assertEqual(policy["supports"].value, "forbidden")

    def test_repository_printable_sets_preserve_exported_orientation(self):
        for model_id in (
            "plamp8", "iharvest_cover", "plamp_stand",
            "peristaltic_pump_stand",
        ):
            model = load_model(
                model_id,
                REPO_ROOT / "things" / model_id / f"{model_id}.cad.json",
                REPO_ROOT,
            )
            for set_name, cad_set in model.sets.items():
                if not cad_set.printable:
                    continue
                with self.subTest(model=model_id, set=set_name):
                    policy, _notes = normalize_slicing(
                        cad_set.slicing,
                        DirectiveSource(f"set:{model_id}/{set_name}"),
                    )
                    self.assertEqual(
                        policy["orientation"].value, "as-exported"
                    )

    def test_host_tools_documents_profiles_defaults_and_readme_advice(self):
        source = (REPO_ROOT / "docs" / "host-tools.md").read_text(encoding="utf-8")
        for text in (
            "plamp cad profiles",
            "--profile system:draft",
            "$PLAMP_DATA_DIR/cad/profiles",
            "$PLAMP_DATA_DIR/cad/preferences.json",
            "--no-default-profiles",
            "readme.md",
        ):
            with self.subTest(text=text):
                self.assertIn(text, source)

    def test_every_repository_scad_is_clean_or_a_library(self):
        roots = tuple(REPO_ROOT.glob("things/**/*.scad"))
        self.assertTrue(roots)
        for path in roots:
            source = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertNotIn("generate.json", source)
                self.assertNotRegex(source, r"(?m)^\s*view\s*=")

    def test_plamp_system_catalog_has_migrated_products(self):
        system = load_system(REPO_ROOT / "cad" / "plamp.system.cad.json", REPO_ROOT)
        self.assertEqual(
            tuple(system.models), (
                "plamp8", "iharvest_cover", "plamp_stand",
                "peristaltic_pump_stand",
            )
        )
        self.assertEqual(system.default_product, "split-box")
        self.assertIn("fit-and-function", system.products)
        self.assertNotIn("test-fit", system.products)

    def test_repository_models_have_exact_described_set_catalogs(self):
        expected = {
            "plamp8": (
                "", "floor", "north_south_walls", "east_west_walls", "box",
                "top_panel", "sub_panel", "north_wall", "south_wall",
                "west_wall", "east_wall", "relay_footprint", "psu_footprint",
                "converter_footprint", "ac_duplex_panel", "dc_connector_panel",
                "usb_c_panel", "c13_panel", "panel_corner_fastener_test",
                "nut_catcher_adjustment_test",
                "corner_coupon", "wall_corner_fastener_assembly", "assembly",
            ),
            "iharvest_cover": ("", "assembly", "plate"),
            "plamp_stand": ("", "assembly", "tripod", "camera_clip", "plate"),
            "peristaltic_pump_stand": ("plate", "legs", "assembly"),
        }
        for model_id, set_names in expected.items():
            with self.subTest(model=model_id):
                model = load_model(
                    model_id,
                    REPO_ROOT / "things" / model_id / f"{model_id}.cad.json",
                    REPO_ROOT,
                )
                self.assertEqual(tuple(model.sets), set_names)
                self.assertTrue(model.description.strip())
                self.assertTrue(all(item.description.strip() for item in model.sets.values()))

    def test_peristaltic_pump_stand_catalog_and_parameters(self):
        source = (
            REPO_ROOT / "things" / "peristaltic_pump_stand" /
            "peristaltic_pump_stand.scad"
        ).read_text()
        compact = compact_scad(source)

        for value in (
            "pump_count=2;", "pump_spacing=62;", "motor_hole_d=29;",
            "motor_screw_spacing=48.5;", "motor_clearance_h=55;",
            "mount_hole_d=5.5;",
        ):
            with self.subTest(value=value):
                self.assertIn(value, compact)

        for set_name in ("plate", "legs", "assembly"):
            with self.subTest(set_name=set_name):
                self.assertIn(f'set=="{set_name}"', compact)

        model = load_model(
            "peristaltic_pump_stand",
            REPO_ROOT / "things" / "peristaltic_pump_stand" /
            "peristaltic_pump_stand.cad.json",
            REPO_ROOT,
        )
        self.assertTrue(model.sets["plate"].printable)
        self.assertTrue(model.sets["legs"].printable)
        self.assertFalse(model.sets["assembly"].printable)

    def test_peristaltic_pump_stand_builds_repeated_motor_plate_and_legs(self):
        source = (
            REPO_ROOT / "things" / "peristaltic_pump_stand" /
            "peristaltic_pump_stand.scad"
        ).read_text()
        plate = compact_scad(scad_module_body(source, "plate"))
        station = compact_scad(scad_module_body(source, "pump_station_negative"))
        legs = compact_scad(scad_module_body(source, "leg_pair"))

        self.assertIn("for(index=[0:pump_count-1])", plate)
        self.assertIn("cylinder(d=motor_hole_d", station)
        self.assertIn("motor_screw_spacing/2", station)
        self.assertIn("cylinder(d=mount_hole_d", plate)
        self.assertIn("motor_clearance_h", legs)

    def test_peristaltic_pump_stand_mounting_holes_use_external_ears(self):
        source = (
            REPO_ROOT / "things" / "peristaltic_pump_stand" /
            "peristaltic_pump_stand.scad"
        ).read_text()
        compact = compact_scad(source)
        plate = compact_scad(scad_module_body(source, "plate"))
        positive = compact_scad(scad_module_body(source, "plate_positive"))

        self.assertIn("mount_ear_r=mount_hole_d/2+mount_ear_wall;", compact)
        self.assertIn("leg_inset=4;", compact)
        self.assertIn("leg_x=plate_w/2-leg_t/2-leg_inset;", compact)
        self.assertIn("mount_ear_x=plate_w/2;", compact)
        self.assertIn("mount_ear_wall=13.75;", compact)
        self.assertIn("plate_positive();", plate)
        self.assertIn("for(x=[-mount_ear_x,mount_ear_x])", plate)
        self.assertIn("translate([x,0,-boolean_overlap])", plate)
        self.assertIn("for(x=[-mount_ear_x,mount_ear_x])", positive)
        self.assertIn("cylinder(d=2*mount_ear_r", positive)

    def test_peristaltic_pump_stand_readme_documents_generation(self):
        readme = (
            REPO_ROOT / "things" / "peristaltic_pump_stand" / "README.md"
        ).read_text()
        self.assertIn(
            "plamp cad generate peristaltic_pump_stand --set plate", readme
        )
        self.assertIn("pump_spacing", readme)

    def test_plamp8_connector_fit_views_use_panel_names(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()

        for name in (
            "ac_duplex_panel", "dc_connector_panel", "usb_c_panel", "c13_panel",
        ):
            with self.subTest(name=name):
                self.assertIn(f'set == "{name}"', source)
                self.assertIn(f'module {name}()', source)

        for retired in ("ac_duplex_channel", "dc_barrel_channel", "c13_inlet"):
            with self.subTest(retired=retired):
                self.assertNotIn(f'set == "{retired}"', source)
                self.assertNotIn(f'module {retired}()', source)


    def test_plamp8_derived_dimensions_follow_their_dependencies(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()

        self.assertLess(
            source.index("service_group_w = c13_group_w;"),
            source.index("usb_c_panel_w = service_group_w + 2 * connector_panel_rim;"),
        )
        self.assertLess(
            source.index("service_group_h = usb_c_group_h;"),
            source.index("usb_c_panel_h = service_group_h + 2 * connector_panel_rim;"),
        )
        self.assertLess(
            source.index("layout_offset_y = panel_margin - content_bottom_y;"),
            source.index("sub_panel_socket_rim_relief_y0 ="),
        )

    def test_plamp8_corner_nut_fit_uses_shared_measured_dimensions(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
        compact = compact_scad(source)

        for definition in (
            'm3_nut_across_flats=nut_profile_across_flats("M3");',
            'm3_nut_thickness=nut_profile_thickness("M3");',
            "panel_nut_width_clearance=0.19;",
            "panel_nut_thickness_clearance=0.04;",
            "corner_nut_entry_mouth_w=6.1;",
        ):
            with self.subTest(definition=definition):
                self.assertIn(definition, compact)

        self.assertNotIn("corner_nut_entry_w=", compact)
        self.assertNotIn("corner_nut_pocket_d=", compact)

    def test_plamp8_psu_and_converter_mounts_use_shared_guide_tubes(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
        compact = compact_scad(source)
        self.assertIn("module component_mount_tubes(", source)
        tubes = compact_scad(scad_module_body(source, "component_mount_tubes"))

        self.assertIn("component_mount_tube_d=9;", compact)
        self.assertIn("for(p=points)", tubes)
        self.assertIn(
            "cylinder(h=component_raise_h,d=component_mount_tube_d);", tubes
        )

        in_box = compact_scad(scad_module_body(source, "component_airflow_posts_in_box"))
        self.assertIn("component_mount_tubes(psu_mount_points());", in_box)
        self.assertIn("component_mount_tubes(converter_mount_points());", in_box)

        psu = compact_scad(scad_module_body(source, "psu_footprint"))
        converter = compact_scad(scad_module_body(source, "converter_footprint"))
        self.assertIn("component_mount_tubes(psu_mount_points());", psu)
        self.assertIn("component_mount_tubes(converter_mount_points());", converter)
        self.assertIn("psu_mount_holes(0);", psu)
        self.assertIn("converter_mount_holes(0);", converter)

    def test_plamp8_nut_profiles_drive_the_current_m3_catcher(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
        compact = compact_scad(source)

        self.assertIn('nut_profiles=[["M3",5.46,2.38],["M5",8.00,4.00]];', compact)
        self.assertIn("functionnut_profile_index(", compact)
        self.assertIn("functionnut_profile_across_flats(", compact)
        self.assertIn("functionnut_profile_thickness(", compact)
        self.assertIn('m3_nut_across_flats=nut_profile_across_flats("M3");', compact)
        self.assertIn('m3_nut_thickness=nut_profile_thickness("M3");', compact)

    def test_plamp8_corner_nut_fit_is_shared_by_flat_and_box_paths(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
        nut_trap = compact_scad(scad_module_body(source, "support_free_m3_nut_trap"))

        self.assertIn(
            "opening_edge_distance=corner_tab_boss_r+boolean_shim;",
            nut_trap,
        )
        self.assertIn("m3_nut_catcher_negative(", nut_trap)
        self.assertIn("entry_mouth_w=corner_nut_entry_mouth_w", nut_trap)
        self.assertIn(
            'roof_mode=print_orientation==box_print_orientation?"30deg":"flat"',
            nut_trap,
        )

    def test_plamp8_corner_nut_entry_uses_roomy_tunnel_and_snug_pocket(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
        compact = compact_scad(source)
        catcher = compact_scad(
            scad_module_body(source, "m3_nut_catcher_negative")
        )
        corner = compact_scad(
            scad_module_body(source, "support_free_m3_nut_trap")
        )
        coupon = compact_scad(
            scad_module_body(source, "nut_catcher_test_coupon")
        )
        panel = compact_scad(
            scad_module_body(source, "side_loaded_panel_nut_trap_negative")
        )

        self.assertIn("corner_nut_tunnel_w=corner_nut_entry_mouth_w;", compact)
        self.assertIn("corner_nut_thickness_clearance=0.14;", compact)
        self.assertIn("nut_drop_fraction=1/2;", compact)
        self.assertNotIn("corner_nut_drop", compact)
        self.assertIn(
            "corner_nut_tunnel_h=m3_nut_thickness+corner_nut_thickness_clearance;",
            compact,
        )
        self.assertIn("entry_tunnel_w=undef", catcher)
        self.assertIn("entry_tunnel_h=undef", catcher)
        self.assertIn("drop_fraction=nut_drop_fraction", catcher)
        self.assertIn("nut_drop=nut_thickness*drop_fraction", catcher)
        self.assertIn(
            "effective_tunnel_w=is_undef(entry_tunnel_w)?slot_w:entry_tunnel_w",
            catcher,
        )
        self.assertIn(
            "effective_tunnel_h=is_undef(entry_tunnel_h)?slot_h:entry_tunnel_h",
            catcher,
        )
        self.assertIn("-effective_tunnel_w/2,nut_drop])", catcher)
        self.assertIn("-effective_entry_mouth_w/2,nut_drop])", catcher)
        self.assertIn(
            "translate([tunnel_roof_x,0,nut_drop+effective_tunnel_h])",
            catcher,
        )
        self.assertNotIn("entry_tunnel_z_offset", compact)
        self.assertIn("if(nib_height>0)m3_nut_catcher_floor_nibs_positive(", catcher)
        self.assertIn("entry_tunnel_w=corner_nut_tunnel_w", corner)
        self.assertIn("entry_tunnel_h=corner_nut_tunnel_h", corner)
        self.assertNotIn("drop_fraction=", corner)
        self.assertIn(
            "thick_clearance=corner_nut_thickness_clearance", corner
        )
        self.assertIn("nib_height=0", corner)
        self.assertIn(
            'effective_thick_clearance=orientation=="45"?corner_nut_thickness_clearance:thick_clearance',
            coupon,
        )
        self.assertIn("thick_clearance=effective_thick_clearance", coupon)
        self.assertIn(
            'nib_height=orientation=="45"?0:panel_nut_floor_nib_h', coupon
        )
        self.assertIn(
            'entry_tunnel_w=orientation=="45"?corner_nut_tunnel_w:undef',
            coupon,
        )
        self.assertIn(
            'entry_tunnel_h=orientation=="45"?corner_nut_tunnel_h:undef',
            coupon,
        )
        self.assertNotIn("drop_fraction=", coupon)
        self.assertNotIn("entry_tunnel_w=corner_nut_tunnel_w", panel)
        self.assertNotIn("entry_tunnel_h=corner_nut_tunnel_h", panel)
        self.assertNotIn("drop_fraction=", panel)
        self.assertNotIn("thick_clearance=corner_nut_thickness_clearance", panel)
        self.assertNotIn("nib_height=0", panel)

    def test_plamp8_shared_nut_catcher_is_point_first_and_ramped(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
        catcher = compact_scad(scad_module_body(source, "m3_nut_catcher_negative"))
        nibs = compact_scad(
            scad_module_body(source, "m3_nut_catcher_floor_nibs_positive")
        )

        self.assertIn("cylinder(h=slot_h,d=pocket_d,$fn=6);", catcher)
        self.assertNotIn(
            "rotate([0,0,30])cylinder(h=slot_h,d=pocket_d,$fn=6);",
            catcher,
        )
        self.assertIn(
            "polygon([[nib_inner_x,-boolean_shim],[nib_outer_x,-boolean_shim],[nib_outer_x,nib_height]])",
            nibs,
        )

    def test_plamp8_nut_catcher_jig_orientations(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
        transform = compact_scad(
            scad_module_body(source, "nut_catcher_orientation_transform")
        )
        origin = compact_scad(
            source.split("function nut_catcher_test_45_origin_z", 1)[1].split(
                "function nut_catcher_test_45_opening_edge_distance", 1
            )[0]
        )

        self.assertIn(
            "rotate([0,-corner_nut_entry_angle,0])rotate([-90,0,0])",
            transform,
        )
        sideways = transform.split('elseif(orientation=="sideways")', 1)[1].split(
            'elseif(orientation=="45")', 1
        )[0]
        self.assertIn("rotate([90,0,0])", sideways)
        self.assertIn("rotate([0,0,-90])", sideways)

        screw = compact_scad(
            scad_module_body(source, "nut_catcher_test_screw_negative")
        )
        self.assertIn('orientation=="sideways"&&roof_mode=="30deg"', screw)
        self.assertIn("else", screw)

        compact = compact_scad(source)
        self.assertIn("nut_catcher_test_mark_font=1.7;", compact)
        self.assertIn(
            'nut_catcher_test_orientations=["up","sideways","45"];',
            compact,
        )

        row = compact_scad(scad_module_body(source, "nut_catcher_test_row"))
        self.assertIn("row[0]==\"all\"", row)
        self.assertIn("item_i%3", row)
        self.assertIn("floor(item_i/3)", row)

        matrix = compact_scad(
            scad_module_body(source, "nut_catcher_adjustment_matrix")
        )
        self.assertIn("for(width_offset=nut_catcher_test_width_offsets)", matrix)
        self.assertIn("for(thick_offset=nut_catcher_test_thick_offsets)", matrix)
        self.assertIn("nut_catcher_test_coupon_matrix(", matrix)
        self.assertIn("nut_catcher_test_matrix_base(matrix_w,", matrix)
        self.assertIn("*nut_catcher_test_matrix_coupon_h", matrix)
        self.assertIn("*nut_catcher_test_matrix_coupon_w", matrix)

    def test_plamp8_45_nut_coupon_has_extended_tunnel_envelope(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
        compact = compact_scad(source)
        coupon = compact_scad(
            scad_module_body(source, "nut_catcher_test_coupon")
        )

        self.assertIn("nut_catcher_test_45_extra_w=12;", compact)
        self.assertIn("nut_catcher_test_45_extra_h=4;", compact)
        self.assertNotIn("nut_catcher_test_45_tunnel_extra_l", compact)
        self.assertIn(
            'effective_coupon_w=coupon_w+(orientation=="45"?'
            "nut_catcher_test_45_extra_w:0);",
            coupon,
        )
        self.assertIn(
            'effective_coupon_h=coupon_h+(orientation=="45"?'
            "nut_catcher_test_45_extra_h:0);",
            coupon,
        )
        self.assertIn(
            'opening_edge_distance=orientation=="45"?'
            "nut_catcher_test_45_opening_edge_distance(slot_w,slot_h,"
            "roof_mode,coupon_h,effective_coupon_h):coupon_d/2+1;",
            coupon,
        )
        self.assertIn(
            "functionnut_catcher_test_45_origin_z(slot_w,slot_h,roof_mode,"
            "coupon_h=nut_catcher_test_coupon_h)=",
            compact,
        )
        self.assertIn(
            "functionnut_catcher_test_45_opening_edge_distance(slot_w,slot_h,"
            "roof_mode,coupon_h,effective_coupon_h)=",
            compact,
        )
        self.assertIn(
            "(effective_coupon_h-nut_catcher_test_45_origin_z(slot_w,slot_h,"
            "roof_mode,coupon_h))*sqrt(2)+corner_nut_tunnel_w/2+boolean_shim;",
            compact,
        )
        self.assertIn(
            "translate([-effective_coupon_w/2,coupon_y-coupon_d/2,0])"
            "cube([effective_coupon_w,coupon_d,effective_coupon_h]);",
            coupon,
        )
        self.assertIn(
            "nut_catcher_orientation_transform(orientation,slot_w,slot_h,"
            "roof_mode,coupon_h)",
            coupon,
        )
        row = compact_scad(scad_module_body(source, "nut_catcher_test_row"))
        self.assertIn(
            '(items[item_i][0]=="45"?nut_catcher_test_45_extra_w/2:0)',
            row,
        )
        self.assertIn(
            "nut_catcher_test_screw_negative(orientation,roof_mode,"
            "effective_coupon_h)",
            coupon,
        )

        base = compact_scad(
            scad_module_body(source, "nut_catcher_test_matrix_base")
        )
        self.assertIn("revision_string", base)
        self.assertIn("nut_catcher_test_matrix_width_label", base)
        self.assertIn("nut_catcher_test_matrix_thick_label", base)
        self.assertIn("matrix_d+nut_catcher_test_matrix_header_d", base)

        coupon = compact_scad(scad_module_body(source, "nut_catcher_test_coupon"))
        self.assertIn("if(top_grid)", coupon)
        self.assertIn("coupon_h-nut_catcher_test_matrix_grid_depth", coupon)
        self.assertIn("module nut_catcher_sideways_print_roof_negative(", source)
        self.assertIn('orientation=="sideways"&&roof_mode=="30deg"', coupon)
        roof = compact_scad(
            scad_module_body(source, "nut_catcher_sideways_print_roof_negative")
        )
        self.assertIn("rotate([0,90,0])", roof)
        self.assertIn("roof_h=slot_h/2*tan(panel_nut_roof_angle)", roof)
        self.assertIn("throat_w=slot_w-2*entry_detent", roof)
        self.assertIn("translate([0,throat_w/2-boolean_shim,slot_h/2])", roof)
        self.assertIn("[-slot_h/2,0]", roof)
        self.assertIn("[slot_h/2,0]", roof)
        self.assertIn("[0,roof_h]", roof)

    def test_plamp8_wall_contexts_are_proper_rotations(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
        expected_matrices = {
            "north": [
                ["1", "0", "0", "0"],
                ["0", "0", "-1", "box_d"],
                ["0", "1", "0", "-box_h"],
                ["0", "0", "0", "1"],
            ],
            "south": [
                ["-1", "0", "0", "box_w"],
                ["0", "0", "1", "0"],
                ["0", "1", "0", "-box_h"],
                ["0", "0", "0", "1"],
            ],
            "west": [
                ["0", "0", "1", "0"],
                ["1", "0", "0", "0"],
                ["0", "1", "0", "-box_h"],
                ["0", "0", "0", "1"],
            ],
            "east": [
                ["0", "0", "-1", "box_w"],
                ["-1", "0", "0", "box_d"],
                ["0", "1", "0", "-box_h"],
                ["0", "0", "0", "1"],
            ],
        }

        for wall, expected in expected_matrices.items():
            with self.subTest(wall=wall):
                context = source.split(
                    f"module {wall}_wall_context(", 1
                )[1].split("module ", 1)[0]
                matrix_literal = re.search(
                    r"multmatrix\(\[\s*((?:\[[^\]]+\],?\s*){4})\]\)",
                    context,
                )
                self.assertIsNotNone(matrix_literal)
                rows = [
                    [value.strip() for value in row.split(",")]
                    for row in re.findall(r"\[([^\]]+)\]", matrix_literal.group(1))
                ]
                self.assertEqual(rows, expected)

                orientation = [[int(value) for value in row[:3]] for row in rows[:3]]
                determinant = (
                    orientation[0][0]
                    * (
                        orientation[1][1] * orientation[2][2]
                        - orientation[1][2] * orientation[2][1]
                    )
                    - orientation[0][1]
                    * (
                        orientation[1][0] * orientation[2][2]
                        - orientation[1][2] * orientation[2][0]
                    )
                    + orientation[0][2]
                    * (
                        orientation[1][0] * orientation[2][1]
                        - orientation[1][1] * orientation[2][0]
                    )
                )
                self.assertEqual(determinant, 1)

        north_context = source.split("module north_wall_context(", 1)[1].split(
            "module ", 1
        )[0]
        self.assertIn(
            """multmatrix([
            [1, 0, 0, 0],
            [0, 0, -1, box_d],
            [0, 1, 0, -box_h],
            [0, 0, 0, 1]
        ])""",
            north_context,
        )

    def test_plamp8_half_vents_are_explicitly_handed(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()

        for module_name in (
            "flat_wall",
            "wall_vent_negatives",
            "wall_revision_negative",
            "wall_stiffening_ribs",
        ):
            with self.subTest(module=module_name):
                module = scad_module_body(source, module_name)
                self.assertIn('vent_side = "right"', module)
                self.assertIn(
                    'vent_mode != "half" || vent_side == "left" || vent_side == "right"',
                    module,
                )

        flat_wall = compact_scad(scad_module_body(source, "flat_wall"))
        self.assertIn(
            "wall_stiffening_ribs(length,h,vent_mode,vent_side,print_orientation,middle_rib_x_adjust);",
            flat_wall,
        )
        self.assertIn(
            "wall_vent_negatives(length,vent_mode,vent_side,h,coarse_vents);",
            flat_wall,
        )
        self.assertIn(
            "wall_revision_negative(length,h,vent_mode,vent_side);", flat_wall
        )

        vent_grid = source.split("module wall_vent_negatives(", 1)[1].split(
            "module ", 1
        )[0]
        self.assertIn(
            'vent_mode == "half" && vent_side == "right" ? length / 2',
            vent_grid,
        )
        self.assertIn(
            'vent_mode == "half" && vent_side == "left" ? length / 2',
            vent_grid,
        )
        self.assertIn(
            "vent_xs = [vent_start_x:vent_hole_spacing:vent_end_x];", vent_grid
        )

        ribs = source.split("module wall_stiffening_ribs(", 1)[1].split(
            "module ", 1
        )[0]
        self.assertIn('vent_side == "left"', ribs)
        self.assertIn(
            "[length / 2 - vent_hole_spacing / 2 + middle_rib_x_adjust, 3 * length / 4]", ribs
        )
        self.assertIn(
            "[length / 4, length / 2 + vent_hole_spacing / 2 + middle_rib_x_adjust]", ribs
        )

        revision = source.split("module wall_revision_negative(", 1)[1].split(
            "module ", 1
        )[0]
        self.assertIn(
            'vent_side == "left" ? 3 * length / 4 : length / 4', revision
        )

        north = compact_scad(scad_module_body(source, "north_wall"))
        south = compact_scad(scad_module_body(source, "south_wall"))
        self.assertIn(
            'flat_wall(box_w,wall_name="NORTH",nut_owner=true,'
            'vent_mode="half",vent_side="right",',
            north,
        )
        self.assertIn(
            'flat_wall(box_w,wall_name="SOUTH",nut_owner=true,'
            'vent_mode="half",vent_side="left",',
            south,
        )

    def test_plamp8_floor_revision_is_readable_from_inside(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()

        self.assertIn("floor_revision_depth = 0.6;", source)
        self.assertNotIn("box_bottom_revision_negative", source)
        revision = source.split("module floor_revision_negative()", 1)[1].split(
            "module ", 1
        )[0]
        self.assertIn(
            "translate([box_w / 2, box_d / 2, -box_h + wall_t])", revision
        )
        self.assertIn("rotate([0, 0, 0])", revision)
        self.assertIn(
            "write_text(revision_string, box_revision_font, -floor_revision_depth);",
            revision,
        )
        self.assertNotIn("mirror(", revision)

        floor_context = source.split("module floor_context(", 1)[1].split(
            "module ", 1
        )[0]
        self.assertEqual(floor_context.count("floor_revision_negative();"), 1)

    def test_cad_documentation_uses_system_model_set_product_vocabulary(self):
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        host_tools = (REPO_ROOT / "docs" / "host-tools.md").read_text(
            encoding="utf-8"
        )
        readme_cad = readme.split("## Generate printable CAD", 1)[1].split(
            "\n## ", 1
        )[0]
        host_tools_cad = host_tools.split("## OpenSCAD on a Pi", 1)[1]
        documentation = f"{readme_cad}\n{host_tools_cad}"

        for command in (
            "plamp cad generate",
            "plamp cad systems",
            "plamp cad models",
            "plamp cad sets",
            "plamp cad products",
            "plamp cad templates",
            "plamp cad generate --system plamp --product fuse-box",
            "plamp cad generate --system plamp plamp8 --set top_panel",
            "plamp cad generate --system plamp plamp8 --all-sets",
            "plamp cad new pump_bracket --system plamp --template flat_plate",
            "plamp cad runs plamp8",
            "plamp cad show RUN_ID",
        ):
            with self.subTest(command=command):
                self.assertIn(command, documentation)
        self.assertIn("$PLAMP_DATA_DIR/cad/prints", documentation)
        self.assertIn(
            "2026-jul23-plamp8-top_panel-22h:19m-47e7d26",
            documentation,
        )
        self.assertIn(
            "plamp cad generate --system plamp plamp8 --set top_panel --regenerate",
            documentation,
        )
        self.assertIn(
            "explicit --output bypasses managed duplicate detection",
            " ".join(documentation.lower().replace("`", "").split()),
        )
        self.assertIn("generate directly", documentation.lower().replace("`", ""))
        self.assertIn(
            "SCAD defaults → model → set → deepest product outward → "
            "product item → parent product → CLI global → CLI per-set",
            " ".join(documentation.split()),
        )
        self.assertIn("noninteractive", documentation.lower())
        self.assertNotIn("plamp cad views", documentation)
        self.assertNotIn("--preset", documentation)
        self.assertNotIn("--view", documentation)
        self.assertNotIn("web", documentation.lower())
        self.assertNotIn("three.js", documentation.lower())

    def test_versioned_scad_sources_use_adjacent_model_sidecars(self):
        paths = (
            "things/plamp8/plamp8.scad",
            "things/plamp_stand/plamp_stand.scad",
            "things/iharvest_cover/iharvest_cover.scad",
        )

        for relative_path in paths:
            with self.subTest(path=relative_path):
                path = REPO_ROOT / relative_path
                source = path.read_text(encoding="utf-8")
                self.assertIn("set =", source)
                self.assertNotIn("generate.json", source)
                self.assertTrue(path.with_suffix(".cad.json").is_file())

    def test_scaffold_templates_keep_metadata_in_adjacent_sidecars(self):
        paths = (
            "things/3d_template/cad.scad",
            "things/3d_template/scad/flat_plate.scad",
            "things/3d_template/scad/positive_negative.scad",
        )
        for relative_path in paths:
            with self.subTest(path=relative_path):
                path = REPO_ROOT / relative_path
                source = path.read_text(encoding="utf-8")
                self.assertIn('set = "__PLAMP_PART__";', source)
                self.assertNotIn("generate.json", source)
                self.assertTrue(path.with_suffix(".cad.json").is_file())

    def test_plamp8_flat_wall_corner_stack_contract(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()

        self.assertIn("wall_z_height = 128;", source)
        self.assertIn("corner_tab_t = 6;", source)
        self.assertIn("corner_clearance_tab_l = corner_wall_boss_h;", source)
        self.assertIn(
            "top_clearance_tab_l = (corner_wall_boss_h + corner_tab_t) / 2;",
            source,
        )
        self.assertIn("corner_tab_positive(length);", source)
        self.assertIn("length + 0.2", source)
        self.assertIn("corner_screw_length = 25;", source)
        self.assertIn("corner_long_screw_length = 30;", source)
        self.assertNotIn("top_corner_screw_length", source)
        self.assertNotIn("bottom_corner_screw_length", source)
        self.assertIn("bottom_shared_nut_offset", source)
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
        bore_profile = source.split("module support_free_bore_profile", 1)[1].split(
            "module ", 1
        )[0]
        self.assertIn("roof_x = r * sin(support_free_roof_angle);", bore_profile)
        self.assertIn("roof_y = r * cos(support_free_roof_angle);", bore_profile)
        self.assertIn(
            "apex_y = roof_y + roof_x * tan(support_free_roof_angle);",
            bore_profile,
        )
        self.assertNotIn("sqrt(2)", bore_profile)
        self.assertIn("corner_nut_shoulder_t = corner_tab_t - panel_nut_slot_h;", source)
        self.assertIn("corner_nut_retainer_t = 0.8;", source)
        self.assertIn(
            "corner_nut_tab_extension = corner_wall_boss_h - corner_tab_t - corner_nut_retainer_t;",
            source,
        )
        self.assertNotIn("corner_nut_detent_angle", source)
        self.assertIn("top_nut_near_face_depth", source)
        self.assertIn("bottom_nut_near_face_depth", source)
        self.assertIn("module support_free_horizontal_bore", source)
        self.assertNotIn("module corner_tab_gusset", source)
        self.assertNotIn("module clearance_tab_inward_gusset", source)
        self.assertNotIn("module corner_nut_axial_retainer", source)
        self.assertNotIn("corner_tab_root_l", source)
        self.assertIn("module corner_tab_positive", source)
        self.assertIn("module corner_nut_tab_positive", source)
        self.assertIn("module corner_tab_boss_positive", source)
        self.assertIn("corner_tab_boss_r = 6;", source)
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
        self.assertIn(
            "corner_clearance_tab(top_clearance_tab_l, print_orientation);",
            wall_tabs,
        )
        self.assertIn(
            "corner_clearance_tab(corner_clearance_tab_l, print_orientation);",
            wall_tabs,
        )
        self.assertIn("module support_free_m3_nut_trap", source)
        self.assertIn("module m3_nut_catcher_floor_nibs_positive", source)
        self.assertNotIn("module corner_nut_retention_detents", source)
        self.assertIn("module corner_wall_coupon", source)
        self.assertIn("module corner_coupon", source)
        self.assertIn("module wall_corner_fastener_assembly", source)
        self.assertIn(
            "outer_edge_offset = panel_screw_inset - coupon_assembly_clearance;",
            source,
        )
        self.assertIn("coupon_plate_column_x = 100;", source)
        self.assertIn('set == "corner_coupon"', source)
        self.assertNotIn('set == "wall_corner_fastener_test"', source)
        set_line = next(
            line for line in source.splitlines() if line.startswith("set =")
        )
        self.assertIn("corner_coupon", set_line)
        self.assertNotIn("wall_corner_fastener_test", set_line)
        self.assertIn('set == "wall_corner_fastener_assembly"', source)
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
        self.assertIn("top_nut_near_face_depth", source)
        self.assertIn("bottom_nut_near_face_depth", source)
        self.assertNotIn("corner_screw_tip_allowance", source)
        self.assertIn(
            "assert(corner_long_screw_length >= top_nut_far_face_depth",
            source,
        )
        self.assertIn("assert(corner_long_screw_length >= bottom_nut_far_face_depth", source)
        self.assertIn(
            "h + sub_panel_bottom_z - top_clearance_tab_l / 2;", source
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
        set_line = next(
            line for line in source.splitlines() if line.startswith("set =")
        )

        for name in ("north_wall", "south_wall", "west_wall", "east_wall"):
            self.assertIn(name, set_line)
            self.assertIn(
                f"module {name}_context(",
                source,
            )
            self.assertIn(
                f"module {name}(",
                source,
            )
            self.assertIn(f'set == "{name}"', source)
        self.assertNotIn(" walls,", set_line)
        self.assertNotIn('set == "walls"', source)
        self.assertNotIn("module walls_context", source)
        self.assertNotIn("module walls()", source)
        self.assertNotIn("feature_ledge", source)
        self.assertNotIn("feature_psu_tie_wrap_anchors_wall", source)
        self.assertNotIn("module psu_right_wall_tie_wrap_anchors_in_box", source)
        self.assertNotIn("psu_wall_anchor_z", source)
        self.assertNotIn("feature_psu_tie_wrap_anchors", source)
        self.assertNotIn("module psu_floor_tie_wrap_anchors", source)
        self.assertNotIn("module psu_floor_stops", source)
        self.assertNotIn("module tie_wrap_anchor", source)
        self.assertNotIn("module half_round", source)
        self.assertNotIn("module side_wall_psu_vents", source)
        self.assertNotIn("module legacy_wall_revision_negative", source)
        self.assertNotIn("module panel_corner_fastener_bosses", source)

    def test_plamp8_has_five_flat_or_three_box_production_plates(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()

        self.assertIn("module north_south_walls()", source)
        self.assertIn("module east_west_walls()", source)
        north_south = source.split("module north_south_walls()", 1)[1].split(
            "module ", 1
        )[0]
        self.assertEqual(north_south.count("north_wall();"), 1)
        self.assertEqual(north_south.count("south_wall();"), 1)
        east_west = source.split("module east_west_walls()", 1)[1].split(
            "module ", 1
        )[0]
        self.assertEqual(east_west.count("east_wall();"), 1)
        self.assertEqual(east_west.count("west_wall();"), 1)
        self.assertNotIn("module plate()", source)
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
        self.assertIn(
            'vent_mode == "half" && vent_side == "right" ? length / 2', source
        )
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
        set_line = next(
            line for line in source.splitlines() if line.startswith("set =")
        )

        self.assertIn("box", set_line)
        self.assertIn('set == "box"', source)
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
        self.assertIn("floor_context(colorize = false);", box_module)
        self.assertIn("union()", box_module)
        self.assertNotIn("flat_wall(", box_module)
        self.assertNotIn("wall_corner_tabs(", box_module)
        self.assertNotIn("floor_locator_", box_module)
        self.assertNotIn("floor_corner_fastener_holes", box_module)
        self.assertIn("color(box_preview_color)", box_module)
        self.assertEqual(box_module.count("colorize = false"), 5)

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
        self.assertIn("module support_free_m3_nut_trap(", source)
        self.assertIn("rotate([0, -corner_nut_entry_angle, 0])", source)
        self.assertIn("m3_nut_catcher_negative(", source)
        self.assertIn("print_orientation == box_print_orientation", source)

        corner_adapter = source.split("module support_free_m3_nut_trap(", 1)[1].split(
            "module corner_clearance_tab", 1
        )[0]
        # The 45-degree entry must travel toward local +X: after the -45-degree
        # Y rotation that is also upward, so the shaft breaks through the top
        # edge of the corner spine instead of disappearing below the print face.
        self.assertIn("direction = 1", corner_adapter)
        self.assertIn(
            "opening_edge_distance=corner_tab_boss_r+boolean_shim;",
            compact_scad(corner_adapter),
        )

        box_module = source.split("module box()", 1)[1].split(
            "module assembly()", 1
        )[0]
        self.assertEqual(
            box_module.count("print_orientation = box_print_orientation"), 4
        )

    def test_plamp8_south_middle_rib_has_wall_specific_negative_x_adjustment(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
        compact = compact_scad(source)

        self.assertIn("south_middle_rib_x_adjust=-2.5;", compact)
        self.assertIn("middle_rib_x_adjust=0", compact)
        self.assertIn("length/2-vent_hole_spacing/2+middle_rib_x_adjust", compact)
        south = compact_scad(scad_module_body(source, "south_wall"))
        self.assertIn("middle_rib_x_adjust=south_middle_rib_x_adjust", south)

    def test_plamp8_preview_separates_panels_only_in_preview(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()

        self.assertIn("assembly_preview_gap = $preview ? 0.01 : 0;", source)
        mounted = source.split("module mounted_top_panel", 1)[1].split(
            "module ", 1
        )[0]
        self.assertIn("-plate_t + assembly_preview_gap", mounted)

    def test_plamp8_ribs_select_profiles_by_print_orientation(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()

        self.assertIn("module smooth_half_rib_profile", source)
        self.assertIn("module low_fn_half_hex_rib", source)
        self.assertIn("$fn = 6", source)
        self.assertNotIn("module box_half_hex_rib_profile", source)
        self.assertIn(
            "box_half_hex_rib_h = wall_rib_w * sqrt(3) / 4;",
            source,
        )
        self.assertIn("module floor_supported_box_rib", source)
        self.assertNotIn("module vertical_box_rib_ramp", source)
        ribs = source.split("module wall_stiffening_ribs", 1)[1].split(
            "module ", 1
        )[0]
        self.assertIn("print_orientation", ribs)
        self.assertIn("vertical_half_hex_rib(", ribs)
        self.assertIn("horizontal_half_hex_rib(", ribs)
        self.assertIn("rib_y0 = floor_rib_y0;", ribs)
        self.assertIn("rib_y1 = h + sub_panel_bottom_z;", ribs)
        self.assertEqual(source.count("for (x = rib_xs)"), 1)

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

        floor_context = source.split("module floor_context(", 1)[1].split(
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

    def test_plamp8_top_wall_bosses_meet_without_overlap(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()

        self.assertIn(
            "function top_nut_tab_center_y(h) =\n"
            "    top_clearance_tab_center_y(h)\n"
            "    - top_clearance_tab_l / 2\n"
            "    - corner_tab_t / 2;",
            source,
        )
        self.assertIn(
            "assert(abs(top_nut_tab_center_y(box_h) + corner_tab_t / 2\n"
            "    - (top_clearance_tab_center_y(box_h) - top_clearance_tab_l / 2))\n"
            "    <= boolean_shim,\n"
            '    "top wall bosses must meet without overlap");',
            source,
        )
        self.assertIn("top_nut_roof_t = corner_nut_shoulder_t;", source)
        self.assertIn("top_shared_nut_offset = 0;", source)
        self.assertIn(
            "nut_offset_y = bearing_side < 0\n"
            "        ? bottom_shared_nut_offset\n"
            "        : top_shared_nut_offset;",
            source,
        )
        self.assertIn(
            "top_nut_near_face_depth = plate_t + sub_panel_h\n"
            "    + top_clearance_tab_l + top_nut_roof_t;",
            source,
        )
        self.assertIn(
            "top_nut_far_face_depth = top_nut_near_face_depth + panel_nut_slot_h;",
            source,
        )
        self.assertIn(
            "assert(corner_long_screw_length >= top_nut_far_face_depth,\n"
            '    "M3x30 top screw must pass through the captured nut");',
            source,
        )
        self.assertIn(
            "assert(top_nut_roof_t >= 3,\n"
            '    "top nut catcher needs at least 3 mm structural roof");',
            source,
        )
        self.assertIn("corner_clearance_tab(top_clearance_tab_l", source)
        self.assertIn("corner_clearance_tab(corner_clearance_tab_l", source)

    def test_plamp8_floor_marks_component_orientation(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()

        labels = source.split("module floor_component_label_negatives", 1)[1].split(
            "module ", 1
        )[0]
        self.assertIn('"Pico Relay-B"', labels)
        self.assertIn('"PSU"', labels)
        self.assertIn('"DC/DC"', labels)
        self.assertIn("90,", labels)
        self.assertIn("180,", labels)
        self.assertIn("component_origin_y + internal_psu_y + 13.5", labels)
        self.assertIn("component_origin_y + internal_converter_y + 12", labels)
        self.assertIn("floor_component_label_negatives();", source)

    def test_plamp8_transparent_components_keep_colors_without_labels(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()

        self.assertIn("color([1, 0.6, 0.1, 0.25])", source)
        self.assertIn("color([0.8, 0.25, 0.95, 0.25])", source)
        self.assertIn("color([0.1, 0.7, 0.2, 0.25])", source)
        self.assertNotIn("raised_component_label", source)
        self.assertNotIn('"12V PSU"', source)
        self.assertNotIn('"RELAYS"', source)

        for module_name in (
            "psu_keepout",
            "converter_keepout",
            "relay_board_keepout",
        ):
            keepout = source.split(f"module {module_name}", 1)[1].split(
                "module ", 1
            )[0]
            self.assertNotIn("text(", keepout)

    def test_plamp8_sub_panel_back_labels_match_wiring_layout(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()

        labels = source.split("module sub_panel_back_labels_negative", 1)[1].split(
            "module ", 1
        )[0]
        for label in (
            "CH1",
            "CH2",
            "CH3",
            "CH4",
            "CH5",
            "CH6",
            "CH7",
            "CH8",
            "AC",
            "USB",
        ):
            self.assertIn(f'"{label}"', labels)
        self.assertIn("dc_label_x_offset = -3;", labels)
        self.assertIn("c13_hardware_y + c13_cutout_h / 2 + 4", labels)
        self.assertIn(
            "usb_c_panel_y + sub_panel_usb_c_cutout_h / 2 + 4", labels
        )
        self.assertIn("mirror([1, 0, 0])", source)
        self.assertIn("sub_panel_back_labels_negative();", source)

    def test_plamp8_sub_panel_has_full_width_usb_support_rib(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
        self.assertIn("module sub_panel_usb_support_rib_positive", source)
        rib = source.split("module sub_panel_usb_support_rib_positive", 1)[1].split(
            "module ", 1
        )[0]

        self.assertIn("sub_panel_usb_support_rib_w = 10;", source)
        self.assertIn(
            "sub_panel_usb_support_rib_h = sub_panel_h - sub_panel_base_h;", source
        )
        self.assertIn("sub_panel_usb_support_rib_gap = 1;", source)
        self.assertRegex(
            source,
            r"sub_panel_usb_support_rib_y\s*=\s*"
            r"usb_c_panel_y - sub_panel_usb_c_cutout_h / 2\s*"
            r"- sub_panel_usb_support_rib_gap\s*"
            r"- sub_panel_usb_support_rib_w / 2;",
        )
        self.assertIn("sub_panel_wall,", rib)
        self.assertIn("top_panel_w - 2 * sub_panel_wall,", rib)
        self.assertIn("sub_panel_base_h", rib)
        self.assertIn("sub_panel_usb_support_rib_h", rib)
        self.assertIn("sub_panel_usb_support_rib_positive();", source)

    def test_plamp8_panel_regions_have_two_mm_gaps_and_xt60_margin(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
        compact = compact_scad(source)

        for declaration in (
            "panel_region_gap = 2;",
            "dc_region_w = 74;",
            "barrel_group_w = dc_region_w;",
            "barrel_channel_w = dc_region_w;",
            "c13_group_w = 58;",
            "service_group_w = c13_group_w;",
            "service_group_h = usb_c_group_h;",
            "c13_cutout_w = 28;",
            "c13_screw_spacing = 40;",
        ):
            with self.subTest(declaration=declaration):
                self.assertIn(declaration, source)

        self.assertIn("dc_col_spacing=dc_region_w+panel_region_gap;", compact)
        self.assertIn("dc_row_spacing=barrel_group_h+panel_region_gap;", compact)
        self.assertIn(
            "assert(dc_column_gap==panel_region_gap,"
            '"DCcolumnregiongapmustbe2mm");',
            compact,
        )
        self.assertIn(
            "assert(dc_row_gap==panel_region_gap,"
            '"DCrowregiongapmustbe2mm");',
            compact,
        )
        self.assertIn(
            "assert(c13_service_gap==panel_region_gap,"
            '"C13/servicegapmustbe2mm");',
            compact,
        )
        self.assertIn(
            "assert(xt60_region_x_margin>=1.2,"
            '"everyXT60faceneedsatleast1.2mmXmargin");',
            compact,
        )
        self.assertIn(
            "assert(c13_cutout_w==28&&c13_screw_spacing==40,"
            '"C13hardwarelocationsmustremainunchanged");',
            compact,
        )

    def test_plamp8_connector_panels_are_flat_and_retain_three_mm_rims(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
        compact = compact_scad(source)
        dc_unit = compact_scad(scad_module_body(source, "dc_connector_panel_unit"))
        c13_unit = compact_scad(scad_module_body(source, "c13_inlet_unit"))

        self.assertIn("connector_panel_rim = 3;", source)
        self.assertNotIn("module alignment_walls", source)
        self.assertNotIn("alignment_walls(", dc_unit)
        self.assertNotIn("alignment_walls(", c13_unit)
        self.assertIn(
            "translate([dc_connector_panel_center_x,dc_connector_panel_center_y,0])"
            "fit_plate(dc_connector_panel_w,dc_connector_panel_h);",
            dc_unit,
        )
        self.assertIn("fit_plate(c13_panel_w,c13_panel_h);", c13_unit)

        for assertion in (
            'assert(ac_connector_panel_rim_ok,"ACconnectorpanelmustretain3mmaroundeveryroundedpocket");',
            'assert(dc_connector_panel_rim_ok,"DCconnectorpanelmustretain3mmaroundeveryroundedpocket");',
            'assert(usb_coupon_pocket_inside_plate,"USBcouponmustretain3mmaroundeveryroundedpocket");',
            'assert(c13_connector_panel_rim_ok,"C13connectorpanelmustretain3mmaroundeveryroundedpocket");',
        ):
            self.assertIn(assertion, compact)

        for frozen in (
            "xt60_cutout_w = 19;", "xt60_cutout_h = 12;",
            "xt60_screw_spacing = 25;", "xt60_screw_d = 3.2;",
        ):
            self.assertIn(frozen, source)
        self.assertIn(
            "xt60_switch_center_spacing = xt60_outside_w / 2 + "
            "dc_switch_outside_d / 2 + xt60_switch_clearance;",
            source,
        )

    def test_plamp8_connector_panel_views_pair_top_and_production_sub_panel_coupons(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
        crop = (
            compact_scad(scad_module_body(source, "production_sub_panel_crop"))
            if "module production_sub_panel_crop" in source
            else ""
        )

        self.assertIn("connector_panel_pair_gap = 10;", source)
        self.assertIn("sub_panel_8ch();", crop)
        self.assertIn("intersection()", crop)
        self.assertIn("sub_panel_print_h+2*boolean_shim", crop)
        self.assertIn(
            "c13_panel_hardware_x = c13_hardware_x - c13_region_x;",
            source,
        )
        c13_negative = compact_scad(scad_module_body(source, "c13_inlet_negative"))
        self.assertIn(
            "translate([c13_panel_hardware_x,0,0])c13_hardware_negative();",
            c13_negative,
        )

        expected = {
            "ac_duplex_panel": "left_ac_x,ac_row_y",
            "dc_connector_panel": "dc_channel_x(0),dc_channel_y(0)",
            "usb_c_panel": "service_group_x,service_group_y",
            "c13_panel": "c13_region_x,c13_hardware_y",
        }
        for view, origin in expected.items():
            body = compact_scad(scad_module_body(source, view))
            with self.subTest(view=view):
                self.assertEqual(body.count("connector_panel_pair("), 1)
                self.assertEqual(body.count("production_sub_panel_crop("), 1)
                self.assertIn(origin, body)

        compact = compact_scad(source)
        for assertion in (
            'assert(ac_connector_pair_aligned,"ACtopandsub-panelcouponcentersmustalign");',
            'assert(dc_connector_pair_aligned,"DCtopandsub-panelcouponcentersmustalign");',
            'assert(usb_connector_pair_aligned,"USBtopandsub-panelcouponcentersmustalign");',
            'assert(c13_connector_pair_aligned,"C13topandsub-panelcouponcentersmustalign");',
        ):
            self.assertIn(assertion, compact)

    def test_plamp8_c13_hardware_and_service_centers_are_frozen(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
        compact = compact_scad(source)

        for contract in (
            "c13_hardware_x = 67;",
            "c13_hardware_y = 58;",
            "c13_region_x = outlet_right_x - c13_group_w / 2;",
            "service_group_x = c13_region_x;",
            "assert(c13_hardware_x == 67 && c13_hardware_y == 58,",
            "assert(service_brand_x == 56 && service_revision_x == 86",
            " && service_top_y == 17.5 && service_com_x == 56.5",
            " && usb_c_panel_x == 85.5 && service_bottom_y == 2.5,",
            "assert(service_region_left_x == c13_region_left_x",
            " && service_region_right_x == c13_region_right_x,",
            "assert(service_region_left_x - dc_region_right_x == panel_region_gap,",
        ):
            with self.subTest(contract=contract):
                self.assertIn(contract, source)
        top_panel = compact_scad(scad_module_body(source, "top_panel_8ch"))
        self.assertIn(
            "translate([c13_region_x,c13_hardware_y,0])c13_group_negative();",
            top_panel,
        )
        self.assertIn(
            "translate([c13_hardware_x,c13_hardware_y,0])c13_hardware_negative();",
            top_panel,
        )

    def test_plamp8_service_region_has_three_separate_pockets(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
        compact = compact_scad(source)

        for equation in (
            "service_pocket_gap = panel_region_gap;",
            "service_pocket_h = (service_group_h - service_pocket_gap) / 2;",
            "service_top_pocket_w = (service_group_w - service_pocket_gap) / 2;",
            "service_top_pocket_x_offset =\n    (service_top_pocket_w + service_pocket_gap) / 2;",
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

        pockets = compact_scad(scad_module_body(source, "service_group_negative"))
        for call in (
            "service_brand_pocket_negative();",
            "service_revision_pocket_negative();",
            "service_com_usb_pocket_negative();",
        ):
            self.assertIn(call, pockets)
        self.assertNotIn("label_pocket(service_group_w,service_group_h);", compact)
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

        top_panel = compact_scad(scad_module_body(source, "top_panel_8ch"))
        sub_panel = compact_scad(scad_module_body(source, "sub_panel_8ch_negative"))
        coupon = compact_scad(scad_module_body(source, "usb_c_panel_negative"))
        self.assertIn("service_group_negative();", coupon)
        self.assertIn(
            "translate([service_bottom_content_x_offset,-service_row_y_offset,0])"
            "usb_c_connector_negative();",
            coupon,
        )
        self.assertIn(
            "translate([usb_c_panel_x,usb_c_panel_y,0])"
            "usb_c_connector_negative();",
            top_panel,
        )
        self.assertIn(
            "translate([usb_c_panel_x,usb_c_panel_y,0])"
            "sub_panel_usb_c_negative();",
            sub_panel,
        )
        self.assertIn(
            "assert(usb_top_sub_panel_aligned,"
            '"USBtopandsub-panelcutoutsmustshareonecenter");',
            compact,
        )
        for label_call in (
            "translate([service_brand_x,service_top_y,0])"
            "flush_label(top_panel_brand_text,top_panel_brand_font);",
            "translate([service_revision_x,service_top_y,0])"
            "flush_revision_label();",
            'translate([service_com_x,service_bottom_y,0])flush_label("COM",5);',
        ):
            self.assertIn(label_call, top_panel)

    def test_plamp8_has_ready_made_panels_product(self):
        system = load_system(REPO_ROOT / "cad" / "plamp.system.cad.json", REPO_ROOT)
        panels = system.products["panels"]
        self.assertEqual(panels.description, "Printable top and internal sub-panels")
        self.assertEqual(
            tuple((item.model, item.set_name) for item in panels.items),
            (("plamp8", "top_panel"), ("plamp8", "sub_panel")),
        )
        self.assertEqual(system.default_product, "split-box")

    def test_plamp8_sub_panel_separator_ribs_follow_region_bounds(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
        compact = compact_scad(source)
        self.assertIn("module sub_panel_separator_rib_positive(x0, y0, w, h)", source)
        self.assertIn("module sub_panel_separator_ribs_positive()", source)
        helper = (
            compact_scad(scad_module_body(source, "sub_panel_separator_rib_positive"))
            if "module sub_panel_separator_rib_positive(" in source
            else ""
        )
        ribs = (
            compact_scad(scad_module_body(source, "sub_panel_separator_ribs_positive"))
            if "module sub_panel_separator_ribs_positive(" in source
            else ""
        )
        positive = compact_scad(scad_module_body(source, "sub_panel_8ch_positive"))

        self.assertIn("translate([x0,y0,sub_panel_base_h])", helper)
        self.assertIn(
            "cube([w,h,sub_panel_h-sub_panel_base_h]);", helper
        )
        expected_calls = (
            "sub_panel_separator_rib_positive(layout_offset_x+dc_column_gap_left_x,"
            "layout_offset_y+dc_region_bottom_y,panel_region_gap,"
            "dc_region_top_y-dc_region_bottom_y);",
            "sub_panel_separator_rib_positive(layout_offset_x+dc_region_left_x,"
            "layout_offset_y+dc_row_gap_bottom_y,"
            "dc_region_right_x-dc_region_left_x,panel_region_gap);",
            "sub_panel_separator_rib_positive(layout_offset_x+c13_region_left_x,"
            "layout_offset_y+service_region_top_y,c13_group_w,panel_region_gap);",
        )
        for call in expected_calls:
            with self.subTest(call=call):
                self.assertIn(call, ribs)
        self.assertEqual(ribs.count("sub_panel_separator_rib_positive("), 3)
        self.assertIn("sub_panel_separator_ribs_positive();", positive)
        self.assertIn("sub_panel_usb_support_rib_positive();", positive)
        self.assertIn(
            "assert(separator_cutters_respect_rib_bounds,"
            '"separatorribsmustfollowregionboundswithoutcuttertrimming");',
            compact,
        )
        for contract in (
            "assert(xt60_screw_nut_envelope_inside_region,"
            '"XT60screwandnutenvelopemustremaininsideeachDCregion");',
            "assert(dc_column_cutters_clear_separator,"
            '"DCcuttersmustclearthefinitecolumnseparator");',
            "assert(dc_row_cutters_clear_separator,"
            '"DCcuttersmustclearthefiniterowseparator");',
            "assert(ac_socket_screw_cutters_below_separators,"
            '"ACsocket,switch,andscrewcuttersmustremainbelowseparatorribextents");',
            "assert(socket_rim_relief_below_separators,"
            '"ACsocketrimreliefmustremainbelowseparatorribextents");',
            "assert(c13_service_cutters_clear_separator,"
            '"C13andUSBcuttersmustcleartheirfiniteseparator");',
        ):
            with self.subTest(contract=contract):
                self.assertIn(contract, compact)
        for bounds in (
            "xt60_screw_nut_envelope_inside_region=xt60_screw_nut_left_x>="
            "barrel_group_x-dc_region_w/2&&xt60_screw_nut_right_x<="
            "barrel_group_x+dc_region_w/2",
            "dc_column_cutters_clear_separator=dc_grid_x+"
            "dc_separator_cutter_right_x<=dc_column_gap_left_x&&dc_grid_x+"
            "dc_col_spacing+dc_separator_cutter_left_x>=dc_column_gap_right_x;",
            "dc_row_cutters_clear_separator=dc_grid_y-dc_separator_cutter_half_h>="
            "dc_row_gap_top_y&&dc_grid_y-dc_row_spacing+dc_separator_cutter_half_h"
            "<=dc_row_gap_bottom_y;",
            "ac_socket_screw_cutters_below_separators=ac_socket_screw_cutter_top_y"
            "<=dc_region_bottom_y;",
            "socket_rim_relief_below_separators=socket_rim_relief_top_y"
            "<=dc_region_bottom_y;",
            "c13_service_cutters_clear_separator=c13_hardware_y-c13_cutout_h/2>="
            "c13_region_bottom_y&&usb_c_panel_y+usb_c_capsule_d/2"
            "<=service_region_top_y;",
        ):
            with self.subTest(bounds=bounds):
                self.assertIn(bounds, compact)

    def test_plamp8_sub_panel_has_full_y_ac_bonding_rib(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
        compact = compact_scad(source)
        rib = (
            compact_scad(
                scad_module_body(source, "sub_panel_ac_bonding_rib_positive")
            )
            if "module sub_panel_ac_bonding_rib_positive" in source
            else ""
        )
        positive = compact_scad(scad_module_body(source, "sub_panel_8ch_positive"))

        for definition in (
            "sub_panel_ac_bonding_rib_w=4;",
            "sub_panel_ac_bonding_rib_x_adjust=15;",
            "sub_panel_ac_bonding_rib_x=layout_offset_x+(left_ac_x+outlet_feature_x+right_ac_x+outlet_feature_x)/2+sub_panel_ac_bonding_rib_x_adjust;",
            "sub_panel_ac_bonding_rib_y0=sub_panel_wall;",
            "sub_panel_ac_bonding_rib_y1=layout_offset_y+dc_region_bottom_y;",
        ):
            self.assertIn(definition, compact)

        self.assertIn("sub_panel_base_h", rib)
        self.assertIn("sub_panel_h-sub_panel_base_h", rib)
        self.assertIn(
            "sub_panel_ac_bonding_rib_y1-sub_panel_ac_bonding_rib_y0", rib
        )
        self.assertIn("sub_panel_ac_bonding_rib_positive();", positive)

    def test_plamp8_sub_panel_ac_socket_exposes_all_terminal_screws(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
        compact = compact_scad(source)
        cutter = (
            compact_scad(scad_module_body(source, "sub_panel_socket_negative"))
            if "module sub_panel_socket_negative" in source
            else ""
        )
        sub_panel = compact_scad(scad_module_body(source, "sub_panel_8ch_negative"))
        top_panel = compact_scad(scad_module_body(source, "top_panel_8ch"))

        for definition in (
            "sub_panel_socket_ground_access_w=5;",
            "sub_panel_socket_ground_access_h=10;",
            "sub_panel_socket_side_access_w=5;",
            "sub_panel_socket_side_access_h=25;",
            "sub_panel_socket_side_access_top_offset=27;",
        ):
            self.assertIn(definition, compact)

        self.assertIn("rect_cutout(sub_panel_socket_w,sub_panel_socket_h);", cutter)
        self.assertIn(
            "sub_panel_socket_w/2+sub_panel_socket_ground_access_w/2-boolean_shim/2",
            cutter,
        )
        self.assertIn(
            "sub_panel_socket_h/2-sub_panel_socket_ground_access_h/2", cutter
        )
        self.assertIn(
            "rect_cutout(sub_panel_socket_ground_access_w+boolean_shim,"
            "sub_panel_socket_ground_access_h);",
            cutter,
        )
        self.assertIn("for(side=[-1,1])", cutter)
        self.assertIn(
            "side*(sub_panel_socket_w/2+sub_panel_socket_side_access_w/2-"
            "boolean_shim/2)",
            cutter,
        )
        self.assertIn(
            "sub_panel_socket_h/2-sub_panel_socket_side_access_top_offset-"
            "sub_panel_socket_side_access_h/2",
            cutter,
        )
        self.assertIn(
            "rect_cutout(sub_panel_socket_side_access_w+boolean_shim,"
            "sub_panel_socket_side_access_h);",
            cutter,
        )
        self.assertIn(
            "translate([x+outlet_feature_x,ac_row_y,plate_t/2])"
            "sub_panel_socket_negative();",
            sub_panel,
        )
        self.assertNotIn("sub_panel_socket_negative();", top_panel)
        self.assertEqual(top_panel.count("outlet_cover_negative(false);"), 2)

    def test_plamp8_revision_default_and_sub_panel_rib_clearance(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()

        self.assertIn('revision_string = "revision";', source)
        self.assertIn("sub_panel_revision_clearance = 1;", source)
        self.assertIn(
            "translate([revision_x, sub_panel_revision_y, sub_panel_base_h])",
            source,
        )

    def test_plamp8_sub_panel_revision_depth(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()

        self.assertIn("sub_panel_revision_depth = 0.6;", source)
        self.assertRegex(
            source,
            r"write_text\(\s*revision_string,\s*sub_panel_revision_font,\s*"
            r"-sub_panel_revision_depth\s*\);",
        )

    def test_plamp8_xt60_and_c13_towers_bond_top_to_sub_panel(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
        compact = compact_scad(source)
        tower = (
            compact_scad(scad_module_body(source, "sub_panel_bonding_tower_positive"))
            if "module sub_panel_bonding_tower_positive" in source
            else ""
        )
        nut = (
            compact_scad(scad_module_body(source, "sub_panel_bonding_nut_negative"))
            if "module sub_panel_bonding_nut_negative" in source
            else ""
        )
        screw = (
            compact_scad(scad_module_body(source, "sub_panel_bonding_screw_negative"))
            if "module sub_panel_bonding_screw_negative" in source
            else ""
        )
        xt60_positive = (
            compact_scad(scad_module_body(source, "sub_panel_xt60_bonding_positive"))
            if "module sub_panel_xt60_bonding_positive" in source
            else ""
        )
        c13_positive = (
            compact_scad(scad_module_body(source, "sub_panel_c13_bonding_positive"))
            if "module sub_panel_c13_bonding_positive" in source
            else ""
        )

        for definition in (
            "sub_panel_bonding_tower_d=11;",
            "sub_panel_bonding_nut_w=panel_nut_entry_w;",
            "sub_panel_bonding_nut_h=panel_nut_slot_h;",
        ):
            self.assertIn(definition, compact)

        self.assertIn("d=sub_panel_bonding_tower_d", tower)
        self.assertIn("side_loaded_panel_nut_trap_negative(", nut)
        self.assertNotIn("cylinder(", nut)
        self.assertIn("translate([0,0,-boolean_shim])", screw)
        self.assertIn("h=sub_panel_h+2*boolean_shim", screw)
        self.assertNotIn("sub_panel_bonding_blind_floor", compact)
        self.assertIn("for(i=[0:3],side=[-1,1])", xt60_positive)
        self.assertEqual(
            xt60_positive.count("sub_panel_bonding_tower_positive();"), 1
        )
        self.assertEqual(
            c13_positive.count("sub_panel_bonding_tower_positive();"), 1
        )
        self.assertIn("mouth_direction=-side", compact)
        self.assertIn(
            "sub_panel_xt60_bonding_positive();",
            compact_scad(scad_module_body(source, "sub_panel_8ch_positive")),
        )
        self.assertIn(
            "sub_panel_c13_bonding_positive();",
            compact_scad(scad_module_body(source, "sub_panel_8ch_positive")),
        )

    def test_plamp8_side_loaded_nuts_share_floor_nibs_and_30_degree_roof(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
        compact = compact_scad(source)
        self.assertNotIn("module side_loaded_panel_nut_pocket_negative", source)
        self.assertNotIn("module side_loaded_panel_nut_floor_nibs_positive", source)
        self.assertNotIn("module side_loaded_panel_nut_roof_negative", source)
        self.assertIn("module side_loaded_panel_nut_trap_negative", source)
        canonical = compact_scad(scad_module_body(source, "m3_nut_catcher_negative"))
        bonding_nut = compact_scad(
            scad_module_body(source, "sub_panel_bonding_nut_negative")
        )
        floor_nibs = compact_scad(
            scad_module_body(source, "m3_nut_catcher_floor_nibs_positive")
        )
        shared_trap = compact_scad(
            scad_module_body(source, "side_loaded_panel_nut_trap_negative")
        )
        corner_nut = compact_scad(
            scad_module_body(source, "side_loaded_panel_nut_trap")
        )

        for definition in (
            "panel_nut_entry_w=m3_nut_across_flats+panel_nut_width_clearance;",
            "panel_nut_slot_h=m3_nut_thickness+panel_nut_thickness_clearance;",
            "panel_nut_floor_nib_h=0.2;",
            "panel_nut_floor_nib_l=1.2;",
            "panel_nut_floor_nib_w=1;",
            "panel_nut_floor_nib_angle=30;",
            "panel_nut_roof_angle=30;",
        ):
            self.assertIn(definition, compact)

        self.assertIn("difference(){", canonical)
        self.assertIn("m3_nut_catcher_floor_nibs_positive(", canonical)
        self.assertIn("for(side=[-1,1])", floor_nibs)
        self.assertIn("linear_extrude(", floor_nibs)
        self.assertIn("polygon(", floor_nibs)
        self.assertIn("rotate([0,0,side*nib_angle])", floor_nibs)
        self.assertIn(
            "pocket_roof_h=slot_w/2*tan(panel_nut_roof_angle)", canonical
        )
        self.assertIn(
            "tunnel_roof_h=effective_tunnel_w/2*tan(panel_nut_roof_angle)",
            canonical,
        )
        self.assertIn("linear_extrude(", canonical)
        self.assertIn("polygon(", canonical)
        self.assertIn("[-pocket_roof_h,0]", canonical)
        self.assertIn("[-tunnel_roof_h,0]", canonical)
        self.assertIn("m3_nut_catcher_negative(", shared_trap)
        self.assertIn("side_loaded_panel_nut_trap_negative(", bonding_nut)
        self.assertIn("side_loaded_panel_nut_trap_negative(", corner_nut)

    def test_plamp8_side_loaded_nut_fit_derives_from_measured_m3_nut(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
        compact = compact_scad(source)
        canonical = compact_scad(scad_module_body(source, "m3_nut_catcher_negative"))
        flipped = compact_scad(
            scad_module_body(source, "side_loaded_panel_nut_trap_flipped_z")
        )

        for definition in (
            'm3_nut_across_flats=nut_profile_across_flats("M3");',
            'm3_nut_thickness=nut_profile_thickness("M3");',
            "panel_nut_width_clearance=0.19;",
            "panel_nut_thickness_clearance=0.04;",
            "corner_nut_entry_mouth_w=6.1;",
            "panel_nut_entry_w=m3_nut_across_flats+panel_nut_width_clearance;",
            "panel_nut_pocket_d=panel_nut_entry_w/cos(30);",
            "panel_nut_slot_h=m3_nut_thickness+panel_nut_thickness_clearance;",
        ):
            self.assertIn(definition, compact)

        self.assertIn("slot_w=nut_across_flats+width_clearance", canonical)
        self.assertIn("pocket_d=slot_w/cos(30)", canonical)
        self.assertIn("slot_h=nut_thickness+thick_clearance", canonical)
        self.assertIn("entry_mouth_w=undef", canonical)
        self.assertIn(
            "effective_entry_mouth_w=is_undef(entry_mouth_w)?slot_w-2*entry_detent:entry_mouth_w",
            canonical,
        )
        self.assertIn(
            "cube([detent_l+boolean_shim,effective_entry_mouth_w,effective_tunnel_h])",
            canonical,
        )
        self.assertIn("slot_h=panel_nut_slot_h", flipped)

    def test_plamp8_uses_one_parametric_m3_nut_catcher(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
        self.assertIn("module m3_nut_catcher_negative(", source)
        canonical = compact_scad(
            scad_module_body(source, "m3_nut_catcher_negative")
        )
        panel = compact_scad(
            scad_module_body(source, "side_loaded_panel_nut_trap_negative")
        )
        wall = compact_scad(
            scad_module_body(source, "support_free_m3_nut_trap")
        )

        for parameter in (
            "nut_across_flats=m3_nut_across_flats",
            "nut_thickness=m3_nut_thickness",
            "width_clearance=panel_nut_width_clearance",
            "thick_clearance=panel_nut_thickness_clearance",
            "nib_height=panel_nut_floor_nib_h",
            'roof_mode="30deg"',
        ):
            self.assertIn(parameter, canonical)
        self.assertIn('assert(roof_mode=="flat"||roof_mode=="30deg"', canonical)
        self.assertIn("m3_nut_catcher_floor_nibs_positive(", canonical)
        self.assertIn("m3_nut_catcher_negative(", panel)
        self.assertIn("m3_nut_catcher_negative(", wall)

    def test_plamp8_nut_catcher_nibs_retain_at_seated_screw_axis(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
        nibs = compact_scad(
            scad_module_body(source, "m3_nut_catcher_floor_nibs_positive")
        )

        self.assertIn("seated_nut_center_x=0", nibs)
        self.assertIn(
            "nib_outer_x=seated_nut_center_x+slot_w/2", nibs
        )
        self.assertIn("nib_inner_x=nib_outer_x+nib_length", nibs)
        self.assertNotIn("main_l-nib_length", nibs)

    def test_plamp8_jig_45_roof_is_always_flat(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
        compact = compact_scad(source)
        coupon = compact_scad(scad_module_body(source, "nut_catcher_test_coupon"))

        self.assertIn(
            'functionnut_catcher_effective_roof_mode(orientation,requested)='
            'orientation=="45"?"flat":requested;',
            compact,
        )
        self.assertIn(
            "roof_mode=nut_catcher_effective_roof_mode(orientation,requested_roof_mode)",
            coupon,
        )

    def test_plamp8_sideways_roofs_use_teardrop_screw_holes(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
        self.assertIn("module nut_catcher_test_screw_negative(", source)
        screw = compact_scad(
            scad_module_body(source, "nut_catcher_test_screw_negative")
        )

        self.assertIn('orientation=="sideways"', screw)
        self.assertNotIn('roof_mode=="flat"', screw)
        self.assertIn("teardrop_hole_3d(", screw)
        self.assertIn("d=panel_screw_d", screw)

    def test_plamp8_panel_corner_fastener_test_exports_two_flat_pieces(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
        compact = compact_scad(source)
        self.assertIn("module panel_corner_fastener_top_coupon", source)
        self.assertIn("module panel_corner_fastener_sub_panel_coupon", source)
        test = compact_scad(scad_module_body(source, "panel_corner_fastener_test"))
        top = compact_scad(
            scad_module_body(source, "panel_corner_fastener_top_coupon")
        )
        sub_panel = compact_scad(
            scad_module_body(source, "panel_corner_fastener_sub_panel_coupon")
        )

        self.assertIn("panel_corner_fastener_test_gap=5;", compact)
        self.assertIn("panel_corner_coupon_roof_cover_t=0.5;", compact)
        self.assertIn(
            "panel_corner_coupon_boss_bottom_z=panel_nut_trap_z-panel_nut_roof_h-panel_corner_coupon_roof_cover_t;",
            compact,
        )
        self.assertIn("panel_corner_fastener_top_coupon(test_w);", test)
        self.assertIn("panel_corner_fastener_sub_panel_coupon(test_w);", test)
        self.assertIn("test_w+panel_corner_fastener_test_gap", test)
        self.assertNotIn("union(){", test)
        self.assertIn("cube([test_w,test_w,plate_t])", top)
        self.assertIn("rotate([180,0,0])", sub_panel)
        self.assertIn(
            "panel_corner_fastener_boss(1,panel_corner_coupon_boss_bottom_z);",
            sub_panel,
        )
        self.assertIn("panel_corner_coupon_boss_bottom_z-1", sub_panel)
        self.assertIn(
            "side_loaded_panel_nut_trap_flipped_z(1)",
            sub_panel,
        )
        flipped = compact_scad(
            scad_module_body(source, "side_loaded_panel_nut_trap_flipped_z")
        )
        self.assertIn("translate([0,0,slot_h])", flipped)
        self.assertIn("mirror([0,0,1])", flipped)
        self.assertIn("side_loaded_panel_nut_trap(direction);", flipped)

    def test_plamp8_panel_corner_fastener_test_marks_fit_and_revision(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
        compact = compact_scad(source)
        top = compact_scad(
            scad_module_body(source, "panel_corner_fastener_top_coupon")
        )
        sub_panel = compact_scad(
            scad_module_body(source, "panel_corner_fastener_sub_panel_coupon")
        )

        self.assertIn(
            'panel_corner_fastener_fit_label=str("W",fixed_2(panel_nut_entry_w),"T",fixed_2(panel_nut_slot_h));',
            compact,
        )
        self.assertIn("scaled=round(value*100)", compact)
        self.assertIn("write_text(panel_corner_fastener_fit_label", top)
        self.assertIn("write_text(revision_string", sub_panel)

    def test_plamp8_nut_catcher_adjustment_jig_expands_independent_rows(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
        compact = compact_scad(source)
        self.assertIn("module nut_catcher_adjustment_test(", source)
        jig = compact_scad(
            scad_module_body(source, "nut_catcher_adjustment_test")
        )
        coupon = compact_scad(scad_module_body(source, "nut_catcher_test_coupon"))
        transform = compact_scad(
            scad_module_body(source, "nut_catcher_orientation_transform")
        )
        origin = compact_scad(
            source.split("function nut_catcher_test_45_origin_z", 1)[1].split(
                "function nut_catcher_test_45_opening_edge_distance", 1
            )[0]
        )

        for orientation in ('"up"', '"down"', '"sideways"', '"45"'):
            self.assertIn(orientation, compact)
        self.assertIn(
            "nut_catcher_test_width_offsets=[-0.1,0,0.1];",
            compact,
        )
        self.assertIn(
            "nut_catcher_test_thick_offsets=[-0.1,0,0.1];",
            compact,
        )
        self.assertIn("nut_catcher_test_matrix_coupon_w=9;", compact)
        self.assertIn(
            '["all","roof_mode","values",["flat","30deg"]]',
            compact,
        )
        self.assertIn("nut_catcher_test_row(rows[row_i],row_i)", jig)
        self.assertIn("nut_catcher_adjustment_matrix();", jig)
        self.assertIn("m3_nut_catcher_negative(", coupon)
        self.assertIn(
            'entry_mouth_w=orientation=="45"?corner_nut_entry_mouth_w:undef',
            coupon,
        )
        self.assertIn("nut_catcher_orientation_transform(orientation", coupon)
        self.assertIn("write_text(label", coupon)
        self.assertIn("write_text(revision_string", coupon)
        self.assertIn("m3_nut_across_flats+width_clearance>0", coupon)
        self.assertIn("m3_nut_thickness+thick_clearance>0", coupon)
        self.assertNotIn("width_clearance>=0", coupon)
        self.assertNotIn("thick_clearance>=0", coupon)
        self.assertIn("roof_top_extent", origin)
        self.assertIn("nut_catcher_test_roof_cover_t", origin)
        self.assertIn("nut_catcher_test_45_origin_z", transform)
        self.assertIn("is_num(candidate)", coupon)
        self.assertIn('candidate=="flat"||candidate=="30deg"', coupon)
        self.assertIn('orientation=="up"', transform)
        self.assertIn('orientation=="down"', transform)
        self.assertIn('orientation=="sideways"', transform)
        self.assertIn('orientation=="45"', transform)

    def test_plamp8_nut_catcher_jig_marks_the_real_diagonal_entry_mouth(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
        label = compact_scad(
            source.split("function nut_catcher_candidate_label", 1)[1].split(
                "module nut_catcher_orientation_transform", 1
            )[0]
        )

        self.assertIn('orientation=="45"', label)
        self.assertIn('str("45M",fixed_2(corner_nut_entry_mouth_w))', label)

    def test_plamp8_nut_jig_loads_every_coupon_from_negative_y(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
        transform = compact_scad(
            scad_module_body(source, "nut_catcher_orientation_transform")
        )
        coupon = compact_scad(scad_module_body(source, "nut_catcher_test_coupon"))

        self.assertIn("rotate([0,0,-90])", transform)
        self.assertIn(":coupon_d/2+1", coupon)

    def test_plamp8_nut_jig_keeps_roof_coupons_independent(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
        compact = compact_scad(source)
        self.assertIn("module nut_catcher_test_row(", source)
        row = compact_scad(scad_module_body(source, "nut_catcher_test_row"))
        jig = compact_scad(
            scad_module_body(source, "nut_catcher_adjustment_test")
        )

        for definition in (
            "nut_catcher_test_coupon_w=16;",
            "nut_catcher_test_coupon_d=12;",
            "nut_catcher_test_coupon_h=10;",
            "nut_catcher_test_gap=3;",
            "nut_catcher_test_row_gap=20;",
            "nut_catcher_test_mark_y=3.8;",
        ):
            self.assertIn(definition, compact)
        self.assertIn("items=nut_catcher_row_items(row)", row)
        self.assertIn("item_i*nut_catcher_test_coupon_w", row)
        self.assertIn('row[0]=="all"?', row)
        self.assertIn("(item_i%3)*(nut_catcher_test_coupon_w+nut_catcher_test_gap)", row)
        self.assertIn("floor(item_i/3)*(nut_catcher_test_coupon_d+nut_catcher_test_row_gap)", row)
        self.assertIn("nut_catcher_test_row(rows[row_i],row_i)", jig)
        self.assertIn(
            "row_i*(nut_catcher_test_coupon_d+nut_catcher_test_row_gap)", jig
        )
        self.assertIn(
            'nut_catcher_test_orientations=["up","sideways","45"];',
            compact,
        )

    def test_plamp8_nut_jig_echoes_label_legend(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
        jig = compact_scad(
            scad_module_body(source, "nut_catcher_adjustment_test")
        )
        label = compact_scad(
            source.split("function nut_catcher_candidate_label", 1)[1].split(
                "module ", 1
            )[0]
        )

        self.assertIn(
            'echo("Nutcatcherfeatures:screwbore;nutpocket;insertiontunnel;'
            'tunnelmouth;entrythroat(narrowedbyretentionnibs);tunnelfloor;'
            'tunnelroof;printroof;countersinkabsent")',
            jig,
        )
        self.assertIn(
            'echo("Nutcatcherlegend:U=boreup,S=sidebore,45=north-walldiagonal,'
            'W=widthclearance,T=thicknessclearance,RF=flatprintroof,'
            'R30=30-degreeprintroof")',
            jig,
        )
        self.assertIn(
            'echo(str("Nutcatcherdrop:",fixed_3('
            'm3_nut_thickness*nut_drop_fraction),"mm(",'
            'nut_drop_fraction,"xnutthickness)"));',
            jig,
        )
        self.assertIn(
            'parameter=="roof_mode"?str(nut_catcher_orientation_short(orientation),'
            '"",candidate=="flat"?"RF":"R30")',
            label,
        )
        self.assertIn("functionsigned_fixed_2(value)", compact_scad(source))
        self.assertIn("signed_fixed_2(candidate)", label)

    def test_plamp8_exposes_nut_catcher_adjustment_test_set(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
        metadata = json.loads(
            (REPO_ROOT / "things" / "plamp8" / "plamp8.cad.json").read_text()
        )

        self.assertIn("nut_catcher_adjustment_test", metadata["sets"])
        self.assertEqual(
            metadata["sets"]["nut_catcher_adjustment_test"]["slicing"],
            {"orientation": "as-exported", "supports": "forbidden"},
        )
        self.assertIn("nut_catcher_adjustment_test", source.splitlines()[4])
        self.assertIn(
            'else if (set == "nut_catcher_adjustment_test")',
            source,
        )

    def test_plamp8_usb_com_fit_dimensions_and_panel_cutouts(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
        usb_unit = source.split("module usb_c_panel_unit", 1)[1].split("module c13_inlet_negative", 1)[0]

        self.assertIn("usb_c_capsule_d = 10.5;", source)
        self.assertIn("usb_c_screw_spacing = 17;", source)
        self.assertIn("usb_c_capsule_w = usb_c_screw_spacing + usb_c_capsule_d;", source)
        self.assertIn("sub_panel_usb_c_cutout_w = 12.5;", source)
        self.assertIn("sub_panel_usb_c_cutout_h = 10.5;", source)
        self.assertRegex(
            source,
            r"module usb_c_connector_negative\(\) \{\s*usb_c_capsule_negative\(\);",
        )
        self.assertRegex(
            source,
            r"module sub_panel_usb_c_negative\(\) \{\s*rect_cutout\(sub_panel_usb_c_cutout_w, sub_panel_usb_c_cutout_h\);",
        )
        self.assertIn('panel_screw_size = "M3";', source)
        self.assertIn("panel_screw_length = 20;", source)
        self.assertIn("panel_screw_tip_protrusion = 1;", source)
        self.assertIn("panel_screw_land_d = 9.5;", source)
        self.assertIn('usb_c_screw_d = screw_clearance_d("M3");', source)
        self.assertIn("usb_c_mount_screw_length = 16;", source)
        self.assertIn("usb_c_countersink_d = screw_chamfer_d(\"M3\");", source)
        self.assertIn("module sub_panel_usb_screw_negative", source)
        self.assertNotIn("module topside_countersunk_screw_hole", source)
        self.assertIn("fit_plate(usb_c_panel_w, usb_c_panel_h);", usb_unit)
        self.assertNotIn("alignment_walls", usb_unit)
        self.assertIn("module panel_corner_screw_lands", source)
        self.assertIn("module panel_corner_fastener_boss", source)
        self.assertIn("module side_loaded_panel_nut_trap", source)
        self.assertIn("module m3_nut_catcher_negative", source)
        self.assertIn("panel_nut_entry_detent", source)
        self.assertRegex(
            source,
            r"module side_loaded_panel_nut_trap\(direction = 1\)[\s\S]*?side_loaded_panel_nut_trap_negative",
        )
        self.assertIn("module panel_corner_fastener_test", source)
        self.assertIn('set == "panel_corner_fastener_test"', source)

    def test_plamp8_usb_connector_uses_raised_sub_panel_mount(self):
        source = (REPO_ROOT / "things" / "plamp8" / "plamp8.scad").read_text()
        compact = compact_scad(source)
        top = compact_scad(scad_module_body(source, "usb_c_connector_negative"))
        capsule = compact_scad(scad_module_body(source, "usb_c_capsule_negative"))
        risers = compact_scad(
            scad_module_body(source, "sub_panel_usb_risers_positive")
        )
        screw = compact_scad(
            scad_module_body(source, "sub_panel_usb_screw_negative")
        )
        sub_negative = compact_scad(
            scad_module_body(source, "sub_panel_usb_c_negative")
        )
        crop = compact_scad(scad_module_body(source, "production_sub_panel_crop"))

        for definition in (
            "usb_c_capsule_d=10.5;",
            "usb_c_capsule_w=usb_c_screw_spacing+usb_c_capsule_d;",
            "usb_c_target_protrusion=2.5;",
            "usb_c_riser_h=plate_t+usb_c_target_protrusion;",
            "sub_panel_print_h=max(sub_panel_h,sub_panel_base_h+usb_c_riser_h);",
            "usb_c_mount_screw_length=16;",
            'usb_c_countersink_d=screw_chamfer_d("M3");',
            "usb_c_countersink_h=(usb_c_countersink_d-usb_c_screw_d)/2;",
            "sub_panel_usb_c_cutout_w=12.5;",
            "sub_panel_usb_c_cutout_h=10.5;",
        ):
            self.assertIn(definition, compact)

        self.assertIn("usb_c_capsule_negative();", top)
        self.assertNotIn("screw_hole", top)
        self.assertNotIn("countersink", top)
        self.assertIn("hull()", capsule)
        self.assertIn(
            "x=[-usb_c_screw_spacing/2,usb_c_screw_spacing/2]", capsule
        )
        self.assertIn("d=usb_c_capsule_d", capsule)
        self.assertIn("h=usb_c_riser_h", risers)
        self.assertIn("d=usb_c_capsule_d", risers)
        self.assertNotIn("sub_panel_usb_ledge_relief", source)
        self.assertIn("d1=usb_c_countersink_d", screw)
        self.assertIn("d2=usb_c_screw_d", screw)
        self.assertIn("sub_panel_usb_screw_negative();", sub_negative)
        self.assertIn("sub_panel_print_h+2*boolean_shim", crop)
        self.assertNotIn("usb_c_cable_recess", source)
        self.assertNotIn("topside_countersunk_screw_hole", source)

    def test_retired_cad_shell_files_are_untracked(self):
        tracked = run(["git", "ls-files", "-z"], REPO_ROOT, check=True).stdout.split("\0")
        removed_names = {"generate" + ".bash", "template" + ".bash"}
        self.assertTrue(removed_names.isdisjoint(Path(path).name for path in tracked if path))


if __name__ == "__main__":
    unittest.main()
