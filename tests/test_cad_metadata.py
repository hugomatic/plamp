import json
import tempfile
import unittest
from pathlib import Path

from plamp.cad_metadata import (
    CadDiagnostic,
    CadMetadataError,
    diagnostics_json,
    parse_cad_document,
)


SCAD_WITH_NORTH_SOUTH_TYPO = '''
view = "floor"; // [floor, north_south_walls]
/* generate.json
{"presets":{"split-box":{"items":["view:north_south_wall"]}}}
*/
'''

REPO_ROOT = Path(__file__).resolve().parents[1]


class CadMetadataTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temporary_directory.cleanup()

    def write_scad(self, source):
        path = Path(self.temporary_directory.name) / "part.scad"
        path.write_text(source, encoding="utf-8")
        return path

    def test_real_scad_templates_have_valid_generation_metadata(self):
        template_paths = (
            REPO_ROOT / "things/3d_template/cad.scad",
            REPO_ROOT / "things/3d_template/scad/flat_plate.scad",
            REPO_ROOT / "things/3d_template/scad/positive_negative.scad",
        )

        for path in template_paths:
            with self.subTest(path=path):
                document = parse_cad_document(path)
                self.assertIsNotNone(document.default_preset)
                self.assertTrue(document.presets)

    def test_parse_document_keeps_customizer_order_and_metadata_overlay(self):
        path = self.write_scad('''
view = "assembly"; // [floor, box, assembly]
/* generate.json
{"default_preset":"split-box","global_variables":{"$fn":64},
 "views":{"box":{"description":"A box","variables":{"vents":true}}},
 "presets":{"split-box":{"items":["view:floor","view:box"]}}}
*/
''')

        document = parse_cad_document(path)

        self.assertEqual(document.path, path)
        self.assertEqual(document.default_view, "assembly")
        self.assertEqual(document.views, ("floor", "box", "assembly"))
        self.assertEqual(document.global_variables, {"$fn": 64})
        self.assertEqual(document.view_metadata["box"].description, "A box")
        self.assertEqual(document.view_metadata["box"].variables, {"vents": True})
        self.assertEqual(document.presets["split-box"].items, ("view:floor", "view:box"))
        self.assertEqual(document.default_preset, "split-box")
        self.assertEqual(document.metadata_snapshot["default_preset"], "split-box")

    def test_partial_view_metadata_uses_typed_defaults(self):
        document = parse_cad_document(self.write_scad('''
view = "floor"; // [floor]
/* generate.json
{"views":{"floor":{"variables":{"quality":2}}}}
*/
'''))

        self.assertEqual(document.view_metadata["floor"].description, "")
        self.assertEqual(document.view_metadata["floor"].variables, {"quality": 2})

    def test_document_without_metadata_keeps_declared_views(self):
        document = parse_cad_document(
            self.write_scad('view = "assembly"; // [floor, assembly]\n')
        )

        self.assertEqual(document.default_view, "assembly")
        self.assertEqual(document.views, ("floor", "assembly"))
        self.assertEqual(document.global_variables, {})
        self.assertEqual(document.view_metadata, {})
        self.assertEqual(document.presets, {})
        self.assertIsNone(document.default_preset)
        self.assertEqual(document.metadata_snapshot, {})

    def test_default_view_without_customizer_list_is_implicit_default(self):
        document = parse_cad_document(self.write_scad('view = "assembly";\n'))

        self.assertEqual(document.default_view, "assembly")
        self.assertEqual(document.views, ())

    def test_invalid_json_reports_json_relative_location(self):
        path = self.write_scad('''
/* generate.json
{
  "views": }
*/
''')

        with self.assertRaises(CadMetadataError) as caught:
            parse_cad_document(path)

        diagnostic = caught.exception.diagnostics[0]
        self.assertEqual(diagnostic.code, "CAD100")
        self.assertEqual(diagnostic.kind, "invalid_json")
        self.assertEqual(diagnostic.source, str(path))
        self.assertEqual((diagnostic.line, diagnostic.column), (3, 12))

    def test_unknown_view_has_stable_code_path_and_suggestion(self):
        with self.assertRaises(CadMetadataError) as caught:
            parse_cad_document(self.write_scad(SCAD_WITH_NORTH_SOUTH_TYPO))

        diagnostic = caught.exception.diagnostics[0]
        self.assertEqual(diagnostic.code, "CAD101")
        self.assertEqual(diagnostic.json_path, "$.presets.split-box.items[0]")
        self.assertEqual(diagnostic.value, "north_south_wall")
        self.assertEqual(diagnostic.choices, ("floor", "north_south_walls"))
        self.assertEqual(diagnostic.suggestion, "north_south_walls")

    def test_unknown_preset_item_reports_reference_path(self):
        with self.assertRaises(CadMetadataError) as caught:
            parse_cad_document(self.write_scad('''
view = "floor"; // [floor]
/* generate.json
{"presets":{"all":{"items":["preset:missing"]}}}
*/
'''))

        diagnostic = caught.exception.diagnostics[0]
        self.assertEqual(diagnostic.code, "CAD102")
        self.assertEqual(diagnostic.json_path, "$.presets.all.items[0]")
        self.assertEqual(diagnostic.value, "missing")
        self.assertEqual(diagnostic.choices, ("all",))

    def test_self_referencing_preset_reports_cycle_and_offending_item(self):
        with self.assertRaises(CadMetadataError) as caught:
            parse_cad_document(self.write_scad('''
view = "floor"; // [floor]
/* generate.json
{"presets":{"loop":{"items":["preset:loop"]}}}
*/
'''))

        diagnostic = caught.exception.diagnostics[0]
        self.assertEqual(diagnostic.code, "CAD106")
        self.assertEqual(diagnostic.kind, "preset_cycle")
        self.assertEqual(diagnostic.json_path, "$.presets.loop.items[0]")
        self.assertEqual(diagnostic.value, ("loop", "loop"))
        self.assertIn("loop -> loop", diagnostic.message)

    def test_indirect_preset_cycle_reports_closing_edge_deterministically(self):
        with self.assertRaises(CadMetadataError) as caught:
            parse_cad_document(self.write_scad('''
view = "floor"; // [floor]
/* generate.json
{"presets":{
  "all":{"items":["preset:tests"]},
  "tests":{"items":["preset:coupons"]},
  "coupons":{"items":["preset:all"]}}}
*/
'''))

        diagnostic = caught.exception.diagnostics[0]
        self.assertEqual(diagnostic.code, "CAD106")
        self.assertEqual(diagnostic.json_path, "$.presets.coupons.items[0]")
        self.assertEqual(
            diagnostic.value, ("all", "tests", "coupons", "all")
        )
        self.assertIn("all -> tests -> coupons -> all", diagnostic.message)

    def test_all_views_is_reserved_as_a_synthetic_selector(self):
        with self.assertRaises(CadMetadataError) as caught:
            parse_cad_document(self.write_scad('''
view = "floor"; // [floor]
/* generate.json
{"presets":{"all-views":{}}}
*/
'''))

        diagnostic = caught.exception.diagnostics[0]
        self.assertEqual(diagnostic.code, "CAD107")
        self.assertEqual(diagnostic.kind, "reserved_preset")
        self.assertEqual(diagnostic.json_path, "$.presets.all-views")
        self.assertEqual(diagnostic.value, "all-views")

    def test_all_presets_is_reserved_as_a_synthetic_selector(self):
        with self.assertRaises(CadMetadataError) as caught:
            parse_cad_document(self.write_scad('''
view = "floor"; // [floor]
/* generate.json
{"presets":{"all-presets":{}}}
*/
'''))

        diagnostic = caught.exception.diagnostics[0]
        self.assertEqual(diagnostic.code, "CAD107")
        self.assertEqual(diagnostic.kind, "reserved_preset")
        self.assertEqual(diagnostic.json_path, "$.presets.all-presets")
        self.assertEqual(diagnostic.value, "all-presets")

    def test_invalid_item_prefix_reports_allowed_namespaces(self):
        with self.assertRaises(CadMetadataError) as caught:
            parse_cad_document(self.write_scad('''
view = "floor"; // [floor]
/* generate.json
{"presets":{"all":{"items":["part:floor"]}}}
*/
'''))

        diagnostic = caught.exception.diagnostics[0]
        self.assertEqual(diagnostic.code, "CAD103")
        self.assertEqual(diagnostic.json_path, "$.presets.all.items[0]")
        self.assertEqual(diagnostic.choices, ("view", "preset"))
        self.assertEqual(diagnostic.fix, "Use view:floor or preset:floor")

    def test_invalid_view_variables_reports_nested_mapping_requirement(self):
        with self.assertRaises(CadMetadataError) as caught:
            parse_cad_document(self.write_scad('''
view = "floor"; // [floor]
/* generate.json
{"presets":{"all":{"view_variables":{"floor":3}}}}
*/
'''))

        diagnostic = caught.exception.diagnostics[0]
        self.assertEqual(diagnostic.code, "CAD104")
        self.assertEqual(
            diagnostic.json_path, "$.presets.all.view_variables.floor"
        )
        self.assertIn("JSON object", diagnostic.message)

    def test_default_preset_and_metadata_keys_are_validated_after_parsing(self):
        with self.assertRaises(CadMetadataError) as caught:
            parse_cad_document(self.write_scad('''
view = "floor"; // [floor]
/* generate.json
{"default_preset":"missing","views":{"flor":{}},
 "presets":{"all":{"view_variables":{"flor":{}}}}}
*/
'''))

        diagnostics = caught.exception.diagnostics
        self.assertEqual(
            [diagnostic.json_path for diagnostic in diagnostics],
            ["$.views.flor", "$.presets.all.view_variables.flor", "$.default_preset"],
        )
        self.assertTrue(all(diagnostic.suggestion for diagnostic in diagnostics[:2]))

    def test_assigned_default_view_must_be_in_nonempty_customizer_list(self):
        with self.assertRaises(CadMetadataError) as caught:
            parse_cad_document(
                self.write_scad('view = "flor"; // [floor, assembly]\n')
            )

        diagnostic = caught.exception.diagnostics[0]
        self.assertEqual(diagnostic.code, "CAD101")
        self.assertEqual(diagnostic.kind, "unknown_view")
        self.assertIsNone(diagnostic.json_path)
        self.assertEqual(diagnostic.value, "flor")
        self.assertEqual(diagnostic.choices, ("floor", "assembly"))
        self.assertEqual(diagnostic.suggestion, "floor")

    def test_diagnostics_have_human_and_json_formats(self):
        diagnostic = CadDiagnostic(
            code="CAD101",
            kind="unknown_view",
            message="Unknown view 'flor'",
            source="part.scad",
            json_path="$.views.flor",
            value="flor",
            choices=("floor",),
            suggestion="floor",
            fix="Use 'floor'",
        )
        error = CadMetadataError((diagnostic,))

        self.assertEqual(error.diagnostics, (diagnostic,))
        self.assertIn("part.scad: $.views.flor: CAD101: Unknown view 'flor'", str(error))
        payload = json.loads(diagnostics_json(error.diagnostics))
        self.assertEqual(payload[0]["code"], "CAD101")
        self.assertEqual(payload[0]["choices"], ["floor"])
        self.assertIsNone(payload[0]["line"])


if __name__ == "__main__":
    unittest.main()
