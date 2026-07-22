import tempfile
import unittest
from pathlib import Path

from plamp.cad_scaffold import create_part, discover_templates


VALID_SOURCE = b'''view = "assembly"; // [assembly]\n/* generate.json\n{"views":{"assembly":{"description":"Complete part"}}}\n*/\ncube(1);\n'''


class CadScaffoldTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.templates = self.root / "things" / "3d_template"
        (self.templates / "scad").mkdir(parents=True)

    def tearDown(self):
        self.temp.cleanup()

    def write_template(self, relative: str, content: bytes = VALID_SOURCE) -> Path:
        path = self.templates / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def test_discovers_root_cad_and_arbitrary_named_templates_in_sorted_order(self):
        cad = self.write_template("cad.scad")
        zeta = self.write_template("scad/zeta_fixture.scad")
        alpha = self.write_template("scad/alpha_plate.scad")
        self.write_template("scad/readme.txt")
        (self.templates / "scad" / "not_a_file.scad").mkdir()

        templates = discover_templates(self.root)

        self.assertEqual(
            tuple((item.name, item.path) for item in templates),
            (("alpha_plate", alpha), ("cad", cad), ("zeta_fixture", zeta)),
        )

    def test_discovery_rejects_missing_template_root(self):
        (self.templates / "scad").rmdir()
        self.templates.rmdir()
        with self.assertRaisesRegex(FileNotFoundError, "3d_template"):
            discover_templates(self.root)

    def test_unknown_template_reports_sorted_available_choices(self):
        self.write_template("cad.scad")
        self.write_template("scad/flat_plate.scad")

        with self.assertRaisesRegex(ValueError, "cad, flat_plate"):
            create_part(self.root, "pump_bracket", "missing")

        self.assertFalse((self.root / "things" / "pump_bracket").exists())

    def test_rejects_unsafe_part_and_template_names_without_mutation(self):
        self.write_template("cad.scad")
        unsafe_names = (
            "nested/part",
            r"nested\\part",
            "../part",
            " part",
            "part ",
            "part name",
            "$(touch-owned)",
            "part;false",
        )
        for unsafe in unsafe_names:
            with self.subTest(part=unsafe):
                with self.assertRaisesRegex(ValueError, "name"):
                    create_part(self.root, unsafe, "cad")
            with self.subTest(template=unsafe):
                with self.assertRaisesRegex(ValueError, "name"):
                    create_part(self.root, "safe_part", unsafe)
            self.assertFalse((self.root / "things" / "safe_part").exists())

    def test_refuses_every_preexisting_destination_kind(self):
        self.write_template("cad.scad")
        things = self.root / "things"
        for part, make_destination in (
            ("existing_dir", lambda path: path.mkdir()),
            ("existing_file", lambda path: path.write_text("keep", encoding="utf-8")),
            ("existing_link", lambda path: path.symlink_to(self.templates)),
        ):
            destination = things / part
            make_destination(destination)
            with self.subTest(part=part):
                with self.assertRaisesRegex(FileExistsError, part):
                    create_part(self.root, part, "cad")
            self.assertTrue(destination.exists())

    def test_invalid_or_missing_metadata_leaves_no_destination_or_staging(self):
        self.write_template("scad/invalid.scad", b"/* generate.json\n{\n*/\n")
        self.write_template("scad/missing.scad", b"cube(1);\n")

        for template in ("invalid", "missing"):
            part = f"from_{template}"
            with self.subTest(template=template):
                with self.assertRaises(ValueError):
                    create_part(self.root, part, template)
                self.assertFalse((self.root / "things" / part).exists())
                self.assertEqual(list((self.root / "things").glob(f".{part}.staging-*")), [])

    def test_success_copies_exact_bytes_to_exact_part_scad_path(self):
        content = VALID_SOURCE + b"// exact trailing bytes and spacing   \n"
        self.write_template("scad/fixture_any_name.scad", content)

        created = create_part(self.root, "pump_bracket", "fixture_any_name")

        expected_dir = self.root / "things" / "pump_bracket"
        expected_scad = expected_dir / "pump_bracket.scad"
        self.assertEqual(created.part, "pump_bracket")
        self.assertEqual(created.template, "fixture_any_name")
        self.assertEqual(created.directory, expected_dir)
        self.assertEqual(created.scad_path, expected_scad)
        self.assertEqual(expected_scad.read_bytes(), content)
        self.assertEqual(tuple(expected_dir.iterdir()), (expected_scad,))


if __name__ == "__main__":
    unittest.main()
