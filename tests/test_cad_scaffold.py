import os
import re
import shutil
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from plamp.cad_metadata import parse_cad_document
from plamp.cad_scaffold import _validate_contract, create_part, discover_templates


VALID_SOURCE = b'''view = "__PLAMP_PART__"; // [__PLAMP_PART__, assembly]
/* generate.json
{"default_preset":"both","views":{"__PLAMP_PART__":{"description":"Part"},"assembly":{"description":"Assembly"}},"presets":{"both":{"items":["view:__PLAMP_PART__","view:assembly"]}}}
*/
part_h = 4;
boolean_overlap = 0.1;
module __PLAMP_PART___positive() { cube([10, 10, part_h], center = true); }
module __PLAMP_PART___negative() {
  echo("BOM", "M3x16 screw", 1);
  cylinder(d = 3.4, h = part_h + 2 * boolean_overlap, center = true);
}
module __PLAMP_PART__() {
  difference() { __PLAMP_PART___positive(); __PLAMP_PART___negative(); }
}
if (view == "__PLAMP_PART__") { __PLAMP_PART__(); }
else if (view == "assembly") { __PLAMP_PART__(); }
'''


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

    def test_generates_named_document_for_underscore_and_hyphen_spelling(self):
        content = VALID_SOURCE + b'// preserve exact trailing bytes: "quoted"   \n'
        self.write_template("scad/fixture_any_name.scad", content)
        for requested in ("pump_bracket", "pump-bracket"):
            with self.subTest(requested=requested):
                created = create_part(self.root, requested, "fixture_any_name")
                expected = self.root / "things" / requested / f"{requested}.scad"
                self.assertEqual(created.scad_path, expected)
                document = parse_cad_document(expected)
                self.assertEqual(document.default_view, "pump_bracket")
                self.assertEqual(document.views, ("pump_bracket", "assembly"))
                self.assertEqual(
                    document.presets[document.default_preset].items,
                    ("view:pump_bracket", "view:assembly"),
                )
                self.assertEqual(set(document.view_metadata), {"pump_bracket", "assembly"})
                self.assertTrue(document.presets)
                source = expected.read_text(encoding="utf-8")
                self.assertEqual(
                    expected.read_bytes(),
                    content.replace(b"__PLAMP_PART__", b"pump_bracket"),
                )
                for declaration in (
                    "module pump_bracket_positive()",
                    "module pump_bracket_negative()",
                    "module pump_bracket()",
                ):
                    self.assertIn(declaration, source)
                for generic in ("module part(", "module part_positive(", "module part_negative("):
                    self.assertNotIn(generic, source)
                self.assertEqual(len(re.findall(r'view == "(?:pump_bracket|assembly)"[^}]*pump_bracket\(\)', source)), 2)
                shutil.rmtree(created.directory)

    def test_generated_contract_rejects_leftover_reserved_token(self):
        generated = VALID_SOURCE.decode("utf-8").replace(
            "__PLAMP_PART__", "pump_bracket"
        )

        with self.assertRaisesRegex(ValueError, "retains reserved token"):
            _validate_contract(
                generated + "\n// __PLAMP_PART__\n",
                "pump_bracket",
                "generated fixture",
            )

    def test_repository_templates_follow_named_geometry_and_bom_contract(self):
        repository = Path(__file__).resolve().parents[1]
        for template in discover_templates(repository):
            with self.subTest(template=template.name):
                raw = template.path.read_text(encoding="utf-8")
                self.assertGreaterEqual(raw.count("__PLAMP_PART__"), 10)
                with tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    target = root / "things" / "3d_template"
                    (target / "scad").mkdir(parents=True)
                    relative = "cad.scad" if template.name == "cad" else f"scad/{template.name}.scad"
                    (target / relative).write_text(raw, encoding="utf-8")
                    generated = create_part(root, "pump-bracket", template.name).scad_path.read_text(encoding="utf-8")
                positive = re.search(r"module pump_bracket_positive\(\)\s*\{(?P<body>.*?)\n\}", generated, re.S).group("body")
                negative = re.search(r"module pump_bracket_negative\(\)\s*\{(?P<body>.*?)\n\}", generated, re.S).group("body")
                composed = re.search(r"module pump_bracket\(\)\s*\{(?P<body>.*?)\n\}", generated, re.S).group("body")
                self.assertIn("cube", positive)
                self.assertIn('echo("BOM", "M3x16 screw", 1);', negative)
                self.assertRegex(negative, r"cylinder\s*\(d\s*=\s*3\.4,\s*h\s*=\s*part_h\s*\+\s*2\s*\*\s*boolean_overlap,\s*center\s*=\s*true\)")
                self.assertIn("difference()", composed)
                self.assertIn("pump_bracket_positive();", composed)
                self.assertIn("pump_bracket_negative();", composed)

    def test_rejects_invalid_identifier_and_normalized_sibling_collision(self):
        self.write_template("cad.scad")
        with self.assertRaisesRegex(ValueError, "identifier"):
            create_part(self.root, "3d_part", "cad")
        self.assertFalse((self.root / "things" / "3d_part").exists())

        for existing, requested in (("pump_bracket", "pump-bracket"), ("pump-bracket", "pump_bracket")):
            with self.subTest(existing=existing):
                existing_path = self.root / "things" / existing
                existing_path.mkdir()
                try:
                    with self.assertRaisesRegex(ValueError, rf"{requested}.*{existing}.*pump_bracket"):
                        create_part(self.root, requested, "cad")
                finally:
                    existing_path.rmdir()

        create_part(self.root, "Pump-bracket", "cad")
        create_part(self.root, "pump-bracket", "cad")

    def test_rejects_template_contract_errors_before_staging(self):
        mutations = {
            "invalid_utf8": b"\xff" + VALID_SOURCE,
            "no_token": VALID_SOURCE.replace(b"__PLAMP_PART__", b"fixed"),
            "missing_module": VALID_SOURCE.replace(b"module __PLAMP_PART___negative()", b"module absent()"),
            "generic_alias": VALID_SOURCE + b"\nmodule part() {}\n",
            "wrong_default": VALID_SOURCE.replace(b'view = "__PLAMP_PART__"', b'view = "assembly"'),
            "wrong_views": VALID_SOURCE.replace(b"[__PLAMP_PART__, assembly]", b"[assembly, __PLAMP_PART__]"),
            "missing_view_metadata": VALID_SOURCE.replace(b',"assembly":{"description":"Assembly"}', b""),
            "no_preset": VALID_SOURCE.replace(b',"presets":{"both":{"items":["view:__PLAMP_PART__","view:assembly"]}}', b""),
            "missing_default_preset": VALID_SOURCE.replace(b'"default_preset":"both",', b""),
            "wrong_items": VALID_SOURCE.replace(b'"view:__PLAMP_PART__","view:assembly"', b'"view:assembly","view:__PLAMP_PART__"'),
            "unknown_view": VALID_SOURCE.replace(b'"view:assembly"]', b'"view:missing"]'),
        }
        for name, content in mutations.items():
            with self.subTest(name=name):
                self.write_template(f"scad/{name}.scad", content)
                with self.assertRaises(ValueError):
                    create_part(self.root, f"from_{name}", name)
                self.assertFalse((self.root / "things" / f"from_{name}").exists())
                self.assertEqual(list((self.root / "things").glob(f".from_{name}.staging-*")), [])

    def test_contract_ignores_module_and_dispatch_decoys_in_comments_and_strings(self):
        mutations = {
            "commented_declaration": VALID_SOURCE.replace(
                b"module __PLAMP_PART___positive()",
                b"/* module __PLAMP_PART___positive() */ module absent_positive()",
            ),
            "string_declaration": VALID_SOURCE.replace(
                b"module __PLAMP_PART___negative()",
                b'echo("module __PLAMP_PART___negative()"); module absent_negative()',
            ),
            "commented_dispatch": VALID_SOURCE.replace(
                b'{ __PLAMP_PART__(); }\nelse if (view == "assembly")',
                b'{ /* __PLAMP_PART__(); */ }\nelse if (view == "assembly")',
                1,
            ),
            "string_dispatch": VALID_SOURCE.replace(
                b'{ __PLAMP_PART__(); }\nelse if (view == "assembly")',
                b'{ echo("__PLAMP_PART__();"); }\nelse if (view == "assembly")',
                1,
            ),
            "truncated_dispatch": VALID_SOURCE.replace(
                b'if (view == "__PLAMP_PART__") { __PLAMP_PART__(); }\n'
                b'else if (view == "assembly") { __PLAMP_PART__(); }',
                b'if (view == "__PLAMP_PART__")',
            ),
        }
        for name, content in mutations.items():
            with self.subTest(name=name):
                self.write_template(f"scad/{name}.scad", content)
                with mock.patch(
                    "plamp.cad_scaffold._make_staging",
                    side_effect=AssertionError("contract reached staging"),
                ):
                    with self.assertRaises(ValueError):
                        create_part(self.root, f"decoy_{name}", name)

    def test_canonical_metadata_errors_are_rejected_before_staging(self):
        mutations = {
            "non_finite_nested": VALID_SOURCE.replace(
                b'"description":"Part"',
                b'"description":"Part","variables":{"size":NaN}',
            ),
            "positive_infinity_nested": VALID_SOURCE.replace(
                b'"description":"Part"',
                b'"description":"Part","variables":{"size":Infinity}',
            ),
            "negative_infinity_nested": VALID_SOURCE.replace(
                b'"description":"Part"',
                b'"description":"Part","variables":{"size":-Infinity}',
            ),
            "invalid_nested_description": VALID_SOURCE.replace(
                b'"description":"Part"', b'"description":42'
            ),
            "invalid_nested_preset_item": VALID_SOURCE.replace(
                b'"view:assembly"]', b'"view:assembly",42]'
            ),
        }
        for name, content in mutations.items():
            with self.subTest(name=name):
                self.write_template(f"scad/{name}.scad", content)
                with mock.patch(
                    "plamp.cad_scaffold._make_staging",
                    side_effect=AssertionError("metadata reached staging"),
                ):
                    with self.assertRaises(ValueError):
                        create_part(self.root, f"metadata_{name}", name)
                self.assertFalse((self.root / "things" / f"metadata_{name}").exists())

    def test_generated_modes_follow_umask_and_ignore_source_executable_bits(self):
        source = self.write_template("cad.scad")
        source.chmod(0o755)
        previous = os.umask(0o027)
        try:
            created = create_part(self.root, "mode_part", "cad")
        finally:
            os.umask(previous)
        self.assertEqual(stat.S_IMODE(created.directory.stat().st_mode), 0o750)
        self.assertEqual(stat.S_IMODE(created.scad_path.stat().st_mode), 0o640)

    def test_atomic_publication_never_clobbers_commit_time_destination(self):
        self.write_template("cad.scad")
        from plamp import cad_scaffold
        real_publish = cad_scaffold._publish_noreplace
        destination = self.root / "things" / "raced"

        def race(staging, target):
            target.mkdir()
            (target / "sentinel").write_bytes(b"competitor")
            return real_publish(staging, target)

        with mock.patch("plamp.cad_scaffold._publish_noreplace", side_effect=race):
            with self.assertRaises(FileExistsError):
                create_part(self.root, "raced", "cad")
        self.assertEqual((destination / "sentinel").read_bytes(), b"competitor")
        self.assertEqual(tuple(destination.iterdir()), (destination / "sentinel",))
        self.assertEqual(list((self.root / "things").glob(".raced.staging-*")), [])

    def test_template_identity_change_to_outside_symlink_is_rejected(self):
        source = self.write_template("cad.scad")
        outside = self.root / "outside.scad"
        outside.write_bytes(VALID_SOURCE.replace(b"cube", b"sphere"))
        discovered = discover_templates(self.root)

        def raced(_root):
            source.unlink()
            source.symlink_to(outside)
            return discovered

        with mock.patch("plamp.cad_scaffold.discover_templates", side_effect=raced):
            with self.assertRaises(OSError):
                create_part(self.root, "symlink_race", "cad")
        self.assertFalse((self.root / "things" / "symlink_race").exists())
        self.assertEqual(list((self.root / "things").glob(".symlink_race.staging-*")), [])


if __name__ == "__main__":
    unittest.main()
