import json
import tempfile
import unittest
from pathlib import Path

from plamp.cad_model import (
    CadMetadataError,
    load_model,
    parse_set_declaration,
)


class CadModelTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def write(self, relative_path, contents):
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")
        return path

    def write_json(self, relative_path, value):
        return self.write(relative_path, json.dumps(value))

    def sidecar(self, **overrides):
        self.write(
            "things/fixture/fixture.scad",
            'set = ""; // [floor, assembly]\n',
        )
        value = {
            "schema": "plamp-cad-model/1",
            "name": "fixture",
            "source": "fixture.scad",
            "description": "Fixture",
            "sets": {},
        }
        value.update(overrides)
        return self.write_json("things/fixture/fixture.cad.json", value)

    def test_clean_scad_and_sidecar_produce_ordered_sets(self):
        self.write("things/fixture/fixture.scad", '''
set = ""; // [floor, top_panel, assembly]
if (set == "floor") floor_set();
''')
        sidecar = self.write_json("things/fixture/fixture.cad.json", {
            "schema": "plamp-cad-model/1", "name": "fixture",
            "source": "fixture.scad", "description": "Fixture",
            "variables": {"quality": 2},
            "sets": {
                "": {"description": "Normal output"},
                "floor": {
                    "description": "Printable floor",
                    "variables": {"vents": True},
                    "slicing": {"supports": "forbidden"},
                },
                "assembly": {"description": "Assembly", "printable": False},
            },
        })

        model = load_model("fixture", sidecar, self.root)

        self.assertEqual(tuple(model.sets), ("", "floor", "top_panel", "assembly"))
        self.assertEqual(model.default_set, "")
        self.assertEqual(model.name, "fixture")
        self.assertEqual(model.description, "Fixture")
        self.assertEqual(model.variables, {"quality": 2})
        self.assertEqual(model.sets["floor"].description, "Printable floor")
        self.assertEqual(model.sets["floor"].variables, {"vents": True})
        self.assertEqual(model.sets["floor"].slicing, {"supports": "forbidden"})
        self.assertFalse(model.sets["assembly"].printable)
        self.assertEqual(model.sets["top_panel"].description, "")
        self.assertEqual(model.advisories[0].code, "CAD112")

    def test_set_declaration_decodes_default_and_preserves_choice_order(self):
        default, choices = parse_set_declaration(
            'set = "top\\u005fpanel"; // [floor, top_panel, assembly]\n',
            Path("fixture.scad"),
        )
        self.assertEqual(default, "top_panel")
        self.assertEqual(choices, ("floor", "top_panel", "assembly"))

    def test_missing_set_declaration_is_rejected_for_sidecar_model(self):
        sidecar = self.sidecar()
        (sidecar.parent / "fixture.scad").write_text("cube(1);\n", encoding="utf-8")
        with self.assertRaises(CadMetadataError) as caught:
            load_model("fixture", sidecar, self.root)
        self.assertIn("set declaration", caught.exception.diagnostics[0].message)

    def test_empty_default_with_no_choices_is_authoritative_empty_set(self):
        sidecar = self.sidecar(
            sets={"": {"description": "Normal model output"}}
        )
        (sidecar.parent / "fixture.scad").write_text(
            'set = ""; // []\n', encoding="utf-8"
        )

        model = load_model("fixture", sidecar, self.root)

        self.assertEqual(tuple(model.sets), ("",))
        self.assertEqual(model.default_set, "")
        self.assertEqual(model.sets[""].description, "Normal model output")
        self.assertEqual(model.advisories, ())

    def test_nonempty_default_with_no_choices_is_rejected(self):
        sidecar = self.sidecar()
        (sidecar.parent / "fixture.scad").write_text(
            'set = "floor"; // []\n', encoding="utf-8"
        )

        with self.assertRaises(CadMetadataError) as caught:
            load_model("fixture", sidecar, self.root)

        diagnostic = caught.exception.diagnostics[0]
        self.assertEqual(diagnostic.code, "CAD111")
        self.assertEqual(diagnostic.value, "floor")
        self.assertEqual(diagnostic.choices, ())

    def test_direct_scad_model_has_implicit_empty_set_and_advisory(self):
        scad = self.write("things/plain/plain.scad", "cube(1);\n")
        model = load_model("plain", scad, self.root)
        self.assertEqual(tuple(model.sets), ("",))
        self.assertEqual(model.sets[""].description, "")
        self.assertIsNone(model.sidecar_path)
        self.assertEqual(model.metadata_snapshot, {})
        self.assertEqual(model.advisories[0].code, "CAD112")

    def test_sidecar_cannot_invent_a_set(self):
        with self.assertRaises(CadMetadataError) as caught:
            load_model("fixture", self.sidecar(sets={"missing": {}}), self.root)
        self.assertEqual(caught.exception.diagnostics[0].code, "CAD111")
        self.assertEqual(caught.exception.diagnostics[0].json_path, "$.sets.missing")

    def test_assigned_nonempty_default_must_occur_in_choices(self):
        sidecar = self.sidecar()
        (sidecar.parent / "fixture.scad").write_text(
            'set = "missing"; // [floor, assembly]\n', encoding="utf-8"
        )
        with self.assertRaises(CadMetadataError) as caught:
            load_model("fixture", sidecar, self.root)
        self.assertEqual(caught.exception.diagnostics[0].value, "missing")
        self.assertEqual(caught.exception.diagnostics[0].choices, ("floor", "assembly"))

    def test_unknown_top_level_and_set_keys_are_rejected(self):
        cases = (
            ({"extra": True}, "$.extra"),
            ({"sets": {"floor": {"extra": True}}}, "$.sets.floor.extra"),
        )
        for overrides, expected_path in cases:
            with self.subTest(expected_path=expected_path):
                with self.assertRaises(CadMetadataError) as caught:
                    load_model("fixture", self.sidecar(**overrides), self.root)
                self.assertEqual(caught.exception.diagnostics[0].json_path, expected_path)

    def test_schema_and_field_types_are_strict(self):
        cases = (
            ({"schema": "wrong"}, "$.schema"),
            ({"name": 3}, "$.name"),
            ({"description": 3}, "$.description"),
            ({"variables": []}, "$.variables"),
            ({"sets": []}, "$.sets"),
            ({"sets": {"floor": {"printable": "yes"}}}, "$.sets.floor.printable"),
        )
        for overrides, expected_path in cases:
            with self.subTest(expected_path=expected_path):
                with self.assertRaises(CadMetadataError) as caught:
                    load_model("fixture", self.sidecar(**overrides), self.root)
                self.assertEqual(caught.exception.diagnostics[0].json_path, expected_path)

    def test_non_finite_numbers_are_rejected(self):
        sidecar = self.write(
            "things/fixture/fixture.cad.json",
            '{"schema":"plamp-cad-model/1","name":"fixture",'
            '"source":"fixture.scad","variables":{"size":NaN}}',
        )
        self.write("things/fixture/fixture.scad", 'set = ""; // [floor]\n')
        with self.assertRaises(CadMetadataError) as caught:
            load_model("fixture", sidecar, self.root)
        self.assertIn("finite", caught.exception.diagnostics[0].message)

    def test_unsafe_names_are_rejected(self):
        for model_id, name in (("../fixture", "fixture"), ("fixture", "../fixture")):
            with self.subTest(model_id=model_id, name=name):
                with self.assertRaises(CadMetadataError):
                    load_model(model_id, self.sidecar(name=name), self.root)

    def test_source_must_remain_in_sidecar_folder(self):
        self.write("things/outside.scad", 'set = ""; // [floor]\n')
        with self.assertRaises(CadMetadataError) as caught:
            load_model("fixture", self.sidecar(source="../outside.scad"), self.root)
        self.assertEqual(caught.exception.diagnostics[0].json_path, "$.source")

    def test_reference_must_remain_in_repository(self):
        outside = Path(self.temporary_directory.name).parent / "outside.scad"
        outside.write_text("cube(1);\n", encoding="utf-8")
        self.addCleanup(outside.unlink, missing_ok=True)
        with self.assertRaises(CadMetadataError):
            load_model("outside", outside, self.root)

    def test_direct_scad_declaration_exposes_declared_sets(self):
        scad = self.write("things/plain/plain.scad", 'set = "floor"; // [floor, assembly]\n')
        model = load_model("plain", scad, self.root)
        self.assertEqual(tuple(model.sets), ("floor", "assembly"))
        self.assertEqual(model.default_set, "floor")
        self.assertEqual(len(model.advisories), 2)

    def test_public_mappings_are_immutable(self):
        model = load_model("fixture", self.sidecar(sets={"floor": {}}), self.root)
        with self.assertRaises(TypeError):
            model.sets["new"] = model.sets["floor"]
        with self.assertRaises(TypeError):
            model.sets["floor"].variables["new"] = 1


if __name__ == "__main__":
    unittest.main()
