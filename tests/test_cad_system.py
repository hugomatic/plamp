import json
from pathlib import Path
import tempfile
import unittest

from plamp.cad_model import CadMetadataError
from plamp.cad_system import discover_systems, load_system, select_system


class CadSystemTests(unittest.TestCase):
    def test_repository_plamp_system_has_exact_models_and_products(self):
        repo_root = Path(__file__).resolve().parents[1]
        system = load_system(repo_root / "cad" / "plamp.system.cad.json", repo_root)
        self.assertEqual(tuple(system.models), ("plamp8", "iharvest_cover", "plamp_stand"))
        self.assertEqual(
            tuple(system.products),
            (
                "split-box", "fuse-box", "panels", "assembly",
                "component-floorplans", "top-panel-fit", "corner-coupons",
                "fit-and-function",
            ),
        )
        self.assertEqual(system.default_product, "split-box")
        self.assertTrue(all(product.description.strip() for product in system.products.values()))

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def write(self, relative, value):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8")
        return path

    def model(self, name="widget", sets=("one", "two")):
        choices = ", ".join(sets)
        self.write(f"things/{name}/{name}.scad", f'set = "{sets[0]}"; // [{choices}]\n')
        return self.write(
            f"things/{name}/{name}.cad.json",
            json.dumps({
                "schema": "plamp-cad-model/1", "name": name,
                "source": f"{name}.scad",
                "sets": {item: {"description": item} for item in sets},
            }),
        )

    def system(self, relative="cad/plamp.system.cad.json", **updates):
        model_path = self.model()
        value = {
            "schema": "plamp-cad-system/1", "name": "plamp",
            "description": "test system",
            "models": {"widget": str(model_path.relative_to(self.root))},
            "libraries": {}, "profiles": {}, "default_product": "complete",
            "products": {"complete": {"items": [{"model": "widget", "set": "one"}]}},
        }
        value.update(updates)
        return self.write(relative, json.dumps(value))

    def assert_invalid(self, **updates):
        path = self.system(**updates)
        with self.assertRaises(CadMetadataError) as caught:
            load_system(path, self.root)
        return caught.exception

    def test_discovers_all_sibling_system_files_and_keeps_invalid_rows(self):
        self.system("cad/plamp.system.cad.json", name="plamp")
        self.system("cad/jigs.system.cad.json", name="jigs")
        self.write("cad/broken.system.cad.json", "{")
        self.system("cad/nested/ignored.system.cad.json", name="ignored")
        rows = discover_systems(self.root)
        self.assertEqual(tuple(row.path.name for row in rows), (
            "broken.system.cad.json", "jigs.system.cad.json", "plamp.system.cad.json"))
        self.assertEqual(rows[0].status, "invalid")
        self.assertTrue(rows[0].diagnostics)

    def test_selects_by_unique_name_or_explicit_path(self):
        self.system("cad/plamp.system.cad.json", name="plamp")
        jigs_path = self.system("cad/jigs.system.cad.json", name="jigs")
        candidates = discover_systems(self.root)
        self.assertEqual(select_system(candidates, "plamp").name, "plamp")
        self.assertEqual(select_system(candidates, str(jigs_path)).name, "jigs")

    def test_selects_valid_explicit_manifest_outside_discovery_directory(self):
        self.system("cad/plamp.system.cad.json", name="plamp")
        external_path = self.system("catalogs/private.system.cad.json", name="private")
        candidates = discover_systems(self.root)
        selected = select_system(candidates, str(external_path))
        self.assertEqual(selected.name, "private")
        self.assertEqual(selected.path, external_path)
        self.assertEqual(selected.status, "valid")
        self.assertEqual(load_system(selected.path, self.root).name, "private")
        self.assertEqual(tuple(row.name for row in candidates), ("plamp",))

    def test_explicit_manifest_must_be_valid_and_inside_repository(self):
        self.system("cad/plamp.system.cad.json", name="plamp")
        candidates = discover_systems(self.root)
        invalid_path = self.write("catalogs/broken.system.cad.json", "{")
        with self.assertRaises(CadMetadataError):
            select_system(candidates, str(invalid_path))
        outside = self.root.parent / "outside.system.cad.json"
        with self.assertRaises(CadMetadataError) as caught:
            select_system(candidates, str(outside))
        self.assertEqual(caught.exception.diagnostics[0].kind, "unsafe_path")

    def test_selection_rejects_duplicate_names_and_lists_choices(self):
        self.system("cad/a.system.cad.json", name="same")
        self.system("cad/b.system.cad.json", name="same")
        candidates = discover_systems(self.root)
        with self.assertRaises(CadMetadataError) as caught:
            select_system(candidates, "same")
        self.assertIn("a.system.cad.json", str(caught.exception))
        self.assertIn("b.system.cad.json", str(caught.exception))

    def test_discovery_marks_every_duplicate_declared_name_invalid(self):
        self.system("cad/a.system.cad.json", name="same")
        self.system("cad/b.system.cad.json", name="same")
        self.system("cad/unique.system.cad.json", name="unique")
        candidates = discover_systems(self.root)
        duplicates = tuple(row for row in candidates if row.name == "same")
        self.assertEqual(tuple(row.status for row in duplicates), ("invalid", "invalid"))
        self.assertTrue(all(row.diagnostics for row in duplicates))
        self.assertEqual(
            tuple(row.diagnostics[-1].kind for row in duplicates),
            ("duplicate_system_name", "duplicate_system_name"),
        )
        self.assertEqual(candidates[-1].status, "valid")

    def test_rejects_unknown_schema_keys(self):
        error = self.assert_invalid(surprise=True)
        self.assertIn("$.surprise", str(error))

    def test_rejects_unknown_nested_keys_and_profile_references(self):
        cases = (
            {"products": {"complete": {"items": [], "surprise": True}}},
            {"products": {"complete": {"items": [{"model": "widget", "set": "one", "surprise": True}]}}},
            {"products": {"complete": {"profiles": ["missing"], "items": []}}},
            {"products": {"complete": {"items": [{"model": "widget", "set": "one", "profiles": ["missing"]}]}}},
        )
        for updates in cases:
            with self.subTest(updates=updates):
                with self.assertRaises(CadMetadataError):
                    load_system(self.system(**updates), self.root)

    def test_rejects_missing_model_profile_and_library_paths(self):
        cases = (
            {"models": {"widget": "missing.cad.json"}},
            {"profiles": {"draft": "cad/profiles/missing.json"}},
            {"libraries": {"BOSL2": {"path": "vendor/missing"}}},
        )
        for updates in cases:
            with self.subTest(updates=updates):
                with self.assertRaises(CadMetadataError):
                    load_system(self.system(**updates), self.root)

    def test_rejects_unknown_default_product(self):
        error = self.assert_invalid(default_product="missing")
        self.assertIn("missing", str(error))

    def test_product_item_requires_exactly_one_reference(self):
        for item in ({}, {"model": "widget", "product": "complete", "set": "one"}):
            with self.subTest(item=item):
                error = self.assert_invalid(products={"complete": {"items": [item]}})
                self.assertIn("exactly one", str(error))

    def test_rejects_unknown_model_set_and_product_references(self):
        items = (
            {"model": "missing", "set": "one"},
            {"model": "widget", "set": "missing"},
            {"product": "missing"},
        )
        for item in items:
            with self.subTest(item=item):
                with self.assertRaises(CadMetadataError):
                    load_system(self.system(products={"complete": {"items": [item]}}), self.root)

    def test_sibling_assignments_require_distinct_variants(self):
        repeated = [
            {"model": "widget", "set": "one", "variables": {"width": 1}},
            {"model": "widget", "set": "one", "variables": {"width": 2}},
        ]
        with self.assertRaises(CadMetadataError):
            load_system(self.system(products={"complete": {"items": repeated}}), self.root)
        repeated[0]["variant"] = "narrow"
        repeated[1]["variant"] = "wide"
        system = load_system(self.system(products={"complete": {"items": repeated}}), self.root)
        self.assertEqual(tuple(item.variant for item in system.products["complete"].items), ("narrow", "wide"))

    def test_identical_sibling_assignments_allow_deduplication_without_variants(self):
        repeated = [
            {"model": "widget", "set": "one", "description": "first label"},
            {"model": "widget", "set": "one", "description": "second label"},
        ]
        system = load_system(
            self.system(products={"complete": {"items": repeated}}), self.root
        )
        self.assertEqual(
            tuple(item.variant for item in system.products["complete"].items),
            (None, None),
        )

    def test_different_sibling_profiles_or_slicing_require_variants(self):
        self.write("cad/profiles/draft.json", "{}")
        for assignment in (
            ("profiles", ["draft"], []),
            ("slicing", {"wall": 1}, {"wall": 2}),
        ):
            field, first, second = assignment
            items = [
                {"model": "widget", "set": "one", field: first},
                {"model": "widget", "set": "one", field: second},
            ]
            with self.subTest(field=field), self.assertRaises(CadMetadataError):
                load_system(
                    self.system(
                        profiles={"draft": "cad/profiles/draft.json"},
                        products={"complete": {"items": items}},
                    ),
                    self.root,
                )

    def test_rejects_duplicate_or_unsafe_variants(self):
        for variants in (("same", "same"), ("good", "not safe")):
            items = [
                {"model": "widget", "set": "one", "variant": variants[0]},
                {"model": "widget", "set": "one", "variant": variants[1]},
            ]
            with self.subTest(variants=variants):
                with self.assertRaises(CadMetadataError):
                    load_system(self.system(products={"complete": {"items": items}}), self.root)

    def test_cycle_diagnostic_contains_full_path(self):
        products = {
            "alpha": {"items": [{"product": "beta"}]},
            "beta": {"items": [{"product": "gamma"}]},
            "gamma": {"items": [{"product": "alpha"}]},
        }
        with self.assertRaises(CadMetadataError) as caught:
            load_system(self.system(default_product="alpha", products=products), self.root)
        self.assertIn("alpha -> beta -> gamma -> alpha", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
