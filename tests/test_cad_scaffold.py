import json
import errno
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from plamp.cad_model import CadDiagnostic, CadMetadataError, load_model
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
        for name, create in (
            ("directory", lambda path: path.mkdir()),
            ("file", lambda path: path.write_text("keep")),
            ("linked", lambda path: path.symlink_to(self.templates)),
        ):
            destination = self.root / "things" / name
            create(destination)
            with self.subTest(kind=name), self.assertRaises(CadDestinationExistsError):
                create_model(self.root, self.system, name, "cad")

    def test_rejects_normalized_identifier_collision(self):
        (self.root / "things" / "pump_bracket").mkdir()
        with self.assertRaisesRegex(CadSelectionError, "shared OpenSCAD stem"):
            create_model(self.root, self.system, "pump-bracket", "cad")

    def test_staging_failures_leave_no_model_or_stage(self):
        for target, failure in (
            ("_read_template", OSError("read failed")),
            ("_make_staging", OSError("mkdir failed")),
            ("_write_exclusive", OSError("write failed")),
        ):
            with self.subTest(target=target), mock.patch(
                f"plamp.cad_scaffold.{target}", side_effect=failure
            ):
                with self.assertRaises(OSError):
                    create_model(self.root, self.system, "pump", "cad")
            self.assertFalse((self.root / "things" / "pump").exists())
            self.assertEqual(list((self.root / "things").glob(".pump.staging-*")), [])

    def test_generated_modes_follow_umask(self):
        previous = os.umask(0o027)
        try:
            created = create_model(self.root, self.system, "pump", "cad")
        finally:
            os.umask(previous)
        self.assertEqual(created.directory.stat().st_mode & 0o777, 0o750)
        self.assertEqual(created.scad_path.stat().st_mode & 0o777, 0o640)
        self.assertEqual(created.sidecar_path.stat().st_mode & 0o777, 0o640)

    def test_canonical_invalid_sidecar_metadata_never_publishes(self):
        sidecar_path = self.templates / "cad.cad.json"
        value = json.loads(sidecar_path.read_text())
        value["sets"]["missing"] = {"description": "not declared"}
        sidecar_path.write_text(json.dumps(value))
        with self.assertRaises(CadSelectionError):
            create_model(self.root, self.system, "pump", "cad")
        self.assertFalse((self.root / "things" / "pump").exists())

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

    def test_discovery_rejects_sidecar_inode_replacement_before_description_read(self):
        sidecar_path = self.templates / "cad.cad.json"
        replacement = self.root / "replacement.json"
        replacement.write_text(json.dumps(sidecar("attacker description")))
        from plamp import cad_scaffold
        real_identity = cad_scaffold._regular_identity
        replaced = False
        def race(path):
            nonlocal replaced
            identity = real_identity(path)
            if path == sidecar_path and not replaced:
                replaced = True
                sidecar_path.unlink()
                replacement.rename(sidecar_path)
            return identity
        with mock.patch("plamp.cad_scaffold._regular_identity", side_effect=race):
            with self.assertRaises(OSError):
                discover_templates(self.root)

    def test_manifest_replace_failure_rolls_back_published_model(self):
        original = self.system_path.read_bytes()
        with mock.patch("plamp.cad_scaffold._replace_system_manifest", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                create_model(self.root, self.system, "pump", "cad")
        self.assertFalse((self.root / "things" / "pump").exists())
        self.assertEqual(self.system_path.read_bytes(), original)

    def test_rollback_does_not_delete_concurrent_destination_replacement(self):
        original = self.system_path.read_bytes()
        destination = self.root / "things" / "pump"
        moved = self.root / "things" / "published-elsewhere"
        def replace_then_fail(_path, _data):
            destination.rename(moved)
            destination.mkdir()
            (destination / "sentinel").write_text("unrelated")
            raise OSError("manifest failed")
        with mock.patch("plamp.cad_scaffold._replace_system_manifest", side_effect=replace_then_fail):
            with self.assertRaises(OSError):
                create_model(self.root, self.system, "pump", "cad")
        self.assertEqual((destination / "sentinel").read_text(), "unrelated")
        self.assertFalse(moved.exists())
        self.assertEqual(list((self.root / "things").glob(".*.rollback-*")), [])
        self.assertEqual(self.system_path.read_bytes(), original)

    def test_atomic_rollback_claim_restores_swap_at_claim_boundary(self):
        original = self.system_path.read_bytes()
        destination = self.root / "things" / "pump"
        moved = self.root / "things" / "owned-moved"
        from plamp import cad_scaffold
        real_rename = os.rename
        real_exchange = cad_scaffold._exchange_paths
        swapped = False
        def race(source, target):
            nonlocal swapped
            if not swapped and Path(source) == destination:
                swapped = True
                real_rename(destination, moved)
                destination.mkdir()
                (destination / "sentinel").write_text("unrelated")
            return real_exchange(source, target)
        with mock.patch("plamp.cad_scaffold._replace_system_manifest", side_effect=OSError("fail")), \
             mock.patch("plamp.cad_scaffold._exchange_paths", side_effect=race):
            with self.assertRaises(OSError):
                create_model(self.root, self.system, "pump", "cad")
        self.assertEqual((destination / "sentinel").read_text(), "unrelated")
        self.assertFalse(moved.exists())
        self.assertEqual(list((self.root / "things").glob(".*.rollback-*")), [])
        self.assertEqual(self.system_path.read_bytes(), original)

    def test_claimed_cleanup_verifies_open_descriptor_before_unlink(self):
        from plamp import cad_scaffold
        owned = self.root / "things" / "owned"
        moved = self.root / "things" / "owned-moved"
        replacement = self.root / "things" / "replacement"
        owned.mkdir(); (owned / "owned-file").write_text("owned")
        replacement.mkdir(); (replacement / "sentinel").write_text("unrelated")
        identity = cad_scaffold._directory_identity(owned)
        real_open = os.open
        swapped = False
        def race(path, flags, *args, **kwargs):
            nonlocal swapped
            if not swapped and Path(path) == owned:
                swapped = True
                owned.rename(moved)
                replacement.rename(owned)
            return real_open(path, flags, *args, **kwargs)
        with mock.patch("plamp.cad_scaffold.os.open", side_effect=race):
            with self.assertRaises(OSError):
                cad_scaffold._clear_claimed_directory(owned, identity)
        self.assertEqual((owned / "sentinel").read_text(), "unrelated")
        self.assertEqual((moved / "owned-file").read_text(), "owned")

    def test_final_removal_exchange_survives_post_cleanup_swap(self):
        original = self.system_path.read_bytes()
        destination = self.root / "things" / "pump"
        moved = self.root / "things" / "owned-after-clean"
        from plamp import cad_scaffold
        real_finalize = cad_scaffold._clear_claimed_directory
        swapped = False
        def clean_then_swap(path, identity):
            nonlocal swapped
            result = real_finalize(path, identity)
            if not swapped:
                swapped = True
                path.rename(moved)
                path.mkdir()
            return result
        with mock.patch("plamp.cad_scaffold._replace_system_manifest", side_effect=OSError("fail")), \
             mock.patch("plamp.cad_scaffold._clear_claimed_directory", side_effect=clean_then_swap):
            with self.assertRaises(OSError):
                create_model(self.root, self.system, "pump", "cad")
        self.assertTrue(destination.is_dir())
        self.assertFalse(moved.exists())
        self.assertEqual(list((self.root / "things").glob(".*.rollback-*")), [])
        self.assertEqual(self.system_path.read_bytes(), original)

    def test_recursive_descriptor_cleanup_never_follows_symlinks(self):
        from plamp import cad_scaffold
        owned = self.root / "things" / "owned"
        nested = owned / "nested"
        outside = self.root / "outside"
        nested.mkdir(parents=True); outside.mkdir()
        (nested / "file").write_text("owned")
        (outside / "sentinel").write_text("keep")
        (nested / "outside-link").symlink_to(outside)
        identity = cad_scaffold._directory_identity(owned)
        self.assertTrue(cad_scaffold._remove_owned_directory(owned, identity))
        self.assertFalse(owned.exists())
        self.assertEqual((outside / "sentinel").read_text(), "keep")

    def test_unsupported_atomic_exchange_does_not_mask_manifest_failure(self):
        from plamp import cad_scaffold
        original = self.system_path.read_bytes()
        with mock.patch(
            "plamp.cad_scaffold._replace_system_manifest",
            side_effect=OSError(errno.EIO, "manifest failure"),
        ), mock.patch(
            "plamp.cad_scaffold._exchange_paths",
            side_effect=cad_scaffold._AtomicExchangeUnsupported("unsupported"),
        ):
            with self.assertRaisesRegex(OSError, "manifest failure"):
                create_model(self.root, self.system, "pump", "cad")
        self.assertEqual(self.system_path.read_bytes(), original)

    def test_prospective_manifest_failure_prevents_publication(self):
        from plamp import cad_scaffold
        real_load = cad_scaffold.load_system
        calls = 0
        def reject_second(path, root):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise CadMetadataError((CadDiagnostic(
                    "CAD120", "invalid_system_metadata", "prospective invalid",
                    str(path),
                ),))
            return real_load(path, root)
        published = []
        with mock.patch("plamp.cad_scaffold.load_system", side_effect=reject_second), \
             mock.patch("plamp.cad_scaffold._publish_noreplace", side_effect=lambda *args: published.append(args)):
            with self.assertRaises(CadMetadataError):
                create_model(self.root, self.system, "pump", "cad")
        self.assertEqual(published, [])

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
