import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from plamp.cad_model import load_model
from plamp.cad_scaffold import (
    CadDestinationExistsError,
    CadSelectionError,
    create_model,
    discover_templates,
)
from plamp.cad_system import load_system


SCAD = '''set = "__PLAMP_PART__"; // [__PLAMP_PART__, assembly]
module __PLAMP_PART___positive() { cube(1); }
module __PLAMP_PART___negative() {}
module __PLAMP_PART__() { difference() { __PLAMP_PART___positive(); __PLAMP_PART___negative(); } }
if (set == "__PLAMP_PART__") { __PLAMP_PART__(); }
else if (set == "assembly") { __PLAMP_PART__(); }
'''


def sidecar(description="General model"):
    return {
        "schema": "plamp-cad-model/1", "name": "__PLAMP_PART__",
        "source": "__PLAMP_PART__.scad", "description": description,
        "sets": {
            "__PLAMP_PART__": {"description": "Printable model"},
            "assembly": {"description": "Assembly", "printable": False},
        },
    }


class CadScaffoldTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.templates = self.root / "things" / "3d_template"
        (self.templates / "scad").mkdir(parents=True)
        self.write_template("cad", root=True)
        self.system_path = self.root / "cad" / "test.system.cad.json"
        self.system_path.parent.mkdir()
        self.system_path.write_text(json.dumps({
            "schema": "plamp-cad-system/1", "name": "test",
            "description": "Test system", "models": {}, "libraries": {},
            "profiles": {}, "products": {},
        }), encoding="utf-8")
        self.system = load_system(self.system_path, self.root)

    def write_template(self, name, *, root=False, description=None):
        directory = self.templates if root else self.templates / "scad"
        scad_path = directory / f"{name}.scad"
        scad_path.write_text(SCAD, encoding="utf-8")
        scad_path.with_suffix(".cad.json").write_text(
            json.dumps(sidecar(description or f"{name} description")), encoding="utf-8"
        )
        return scad_path

    def test_discovers_sorted_paired_templates_with_descriptions(self):
        self.write_template("zeta")
        alpha = self.write_template("alpha", description="Flat plate")
        rows = discover_templates(self.root)
        self.assertEqual(tuple(item.name for item in rows), ("alpha", "cad", "zeta"))
        self.assertEqual(rows[0].description, "Flat plate")
        self.assertEqual(rows[0].sidecar_path, alpha.with_suffix(".cad.json"))

    def test_discovery_rejects_missing_sidecar_description_and_symlink(self):
        lonely = self.templates / "scad" / "lonely.scad"
        lonely.write_text(SCAD)
        with self.assertRaisesRegex(ValueError, "sidecar"):
            discover_templates(self.root)
        lonely.unlink()
        bad = self.write_template("bad")
        value = sidecar("")
        bad.with_suffix(".cad.json").write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, "description"):
            discover_templates(self.root)
        bad.unlink(); bad.with_suffix(".cad.json").unlink()
        outside = self.root / "outside.scad"; outside.write_text(SCAD)
        (self.templates / "scad" / "linked.scad").symlink_to(outside)
        self.assertNotIn("linked", tuple(item.name for item in discover_templates(self.root)))

    def test_generates_two_clean_files_and_registers_model(self):
        created = create_model(self.root, self.system, "pump-bracket", "cad")
        self.assertTrue(created.scad_path.is_file())
        self.assertTrue(created.sidecar_path.is_file())
        self.assertNotIn("generate.json", created.scad_path.read_text())
        metadata = json.loads(created.sidecar_path.read_text())
        self.assertEqual(metadata["name"], "pump-bracket")
        self.assertEqual(metadata["source"], "pump-bracket.scad")
        model = load_model("pump-bracket", created.sidecar_path, self.root)
        self.assertEqual(tuple(model.sets), ("pump_bracket", "assembly"))
        manifest = json.loads(self.system_path.read_text())
        self.assertEqual(
            manifest["models"]["pump-bracket"],
            "things/pump-bracket/pump-bracket.cad.json",
        )

    def test_unknown_template_and_duplicate_model_are_non_mutating(self):
        original = self.system_path.read_bytes()
        with self.assertRaisesRegex(ValueError, "available: cad"):
            create_model(self.root, self.system, "pump", "missing")
        self.assertEqual(self.system_path.read_bytes(), original)
        create_model(self.root, self.system, "pump", "cad")
        refreshed = load_system(self.system_path, self.root)
        with self.assertRaises(CadDestinationExistsError):
            create_model(self.root, refreshed, "pump", "cad")

    def test_rejects_unsafe_names_and_existing_destination_kinds(self):
        for unsafe in ("../pump", "pump/name", "pump name", "$(owned)"):
            with self.subTest(unsafe=unsafe), self.assertRaises(CadSelectionError):
                create_model(self.root, self.system, unsafe, "cad")
        destination = self.root / "things" / "linked"
        destination.symlink_to(self.templates)
        with self.assertRaises(CadDestinationExistsError):
            create_model(self.root, self.system, "linked", "cad")

    def test_template_replacement_symlink_race_is_rejected(self):
        source = self.templates / "cad.scad"
        outside = self.root / "outside.scad"; outside.write_text(SCAD.replace("cube", "sphere"))
        discovered = discover_templates(self.root)
        def raced(_root):
            source.unlink(); source.symlink_to(outside)
            return discovered
        with mock.patch("plamp.cad_scaffold.discover_templates", side_effect=raced):
            with self.assertRaises(OSError):
                create_model(self.root, self.system, "pump", "cad")
        self.assertFalse((self.root / "things" / "pump").exists())

    def test_manifest_replace_failure_rolls_back_published_model(self):
        original = self.system_path.read_bytes()
        with mock.patch("plamp.cad_scaffold._replace_system_manifest", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                create_model(self.root, self.system, "pump", "cad")
        self.assertFalse((self.root / "things" / "pump").exists())
        self.assertEqual(self.system_path.read_bytes(), original)

    def test_publish_race_preserves_competing_directory_and_manifest(self):
        original = self.system_path.read_bytes()
        destination = self.root / "things" / "pump"
        def race(staging, target):
            target.mkdir(); (target / "sentinel").write_text("keep")
            raise FileExistsError("won elsewhere")
        with mock.patch("plamp.cad_scaffold._publish_noreplace", side_effect=race):
            with self.assertRaises(FileExistsError):
                create_model(self.root, self.system, "pump", "cad")
        self.assertEqual((destination / "sentinel").read_text(), "keep")
        self.assertEqual(self.system_path.read_bytes(), original)

    def test_repository_templates_are_complete_and_generate_navigable_models(self):
        repository = Path(__file__).resolve().parents[1]
        for template in discover_templates(repository):
            with self.subTest(template=template.name), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                shutil.copytree(repository / "things" / "3d_template", root / "things" / "3d_template")
                manifest = root / "cad" / "test.system.cad.json"; manifest.parent.mkdir()
                manifest.write_text(json.dumps({
                    "schema": "plamp-cad-system/1", "name": "test", "models": {},
                    "products": {}, "profiles": {}, "libraries": {},
                }))
                system = load_system(manifest, root)
                created = create_model(root, system, f"from-{template.name}", template.name)
                loaded = load_system(manifest, root)
                self.assertIn(created.model_id, loaded.models)
                self.assertEqual(tuple(loaded.models[created.model_id].sets)[-1], "assembly")


if __name__ == "__main__":
    unittest.main()
