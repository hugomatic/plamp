import json
import math
from pathlib import Path
import tempfile
import unittest

from plamp.cad_profiles import (
    CadProfileError,
    discover_local_profiles,
    load_preferences,
    load_system_profiles,
    profile_content_hash,
    resolve_profile_ids,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class CadProfileTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def write_json(self, relative, value):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def profile_value(self, name="draft", kind="quality", **updates):
        value = {
            "schema": "plamp-cad-profile/1",
            "name": name,
            "kind": kind,
            "cad": {"render_fn": 24},
            "slicing": {"supports": "optional"},
            "machine": {},
        }
        value.update(updates)
        return value

    def load_profile(self, name="draft", kind="quality", *, local=False, **updates):
        relative = f"data/cad/profiles/{name}.json" if local else f"cad/profiles/{name}.json"
        path = self.write_json(relative, self.profile_value(name, kind, **updates))
        if local:
            return discover_local_profiles(self.root / "data")[name]
        return load_system_profiles({name: path})[name]

    def test_loads_strict_typed_immutable_system_profile(self):
        path = self.write_json(
            "cad/profiles/draft.json",
            self.profile_value(cad={"flag": True, "offset": [1, 2.5, None], "label": "x"}),
        )
        profile = load_system_profiles({"draft": path})["draft"]
        self.assertEqual(profile.qualified_id, "system:draft")
        self.assertEqual(profile.kind, "quality")
        self.assertEqual(profile.cad["offset"], (1, 2.5, None))
        with self.assertRaises(TypeError):
            profile.cad["flag"] = False

    def test_rejects_schema_unknown_keys_kinds_names_and_non_finite_values(self):
        cases = (
            (self.profile_value(schema="old"), "schema"),
            (self.profile_value(extra=True), "extra"),
            (self.profile_value(kind="speed"), "kind"),
            (self.profile_value(name="different"), "must match"),
            (self.profile_value(cad={"bad": math.inf}), "finite"),
        )
        for index, (value, message) in enumerate(cases):
            with self.subTest(index=index):
                path = self.write_json(f"cad/profiles/case{index}.json", value)
                with self.assertRaisesRegex(CadProfileError, message):
                    load_system_profiles({"draft": path})

    def test_profile_hash_is_canonical_and_content_sensitive(self):
        first = self.profile_value(cad={"b": 2, "a": 1})
        second = {
            "machine": {}, "slicing": {"supports": "optional"},
            "cad": {"a": 1, "b": 2}, "kind": "quality", "name": "draft",
            "schema": "plamp-cad-profile/1",
        }
        self.assertEqual(profile_content_hash(first), profile_content_hash(second))
        second["cad"]["a"] = 3
        self.assertNotEqual(profile_content_hash(first), profile_content_hash(second))
        self.assertEqual(len(profile_content_hash(first)), 64)

    def test_discovers_local_profiles_and_absent_directory_is_empty(self):
        self.assertEqual(dict(discover_local_profiles(self.root / "data")), {})
        self.write_json(
            "data/cad/profiles/x1c.json", self.profile_value("x1c", "printer")
        )
        profiles = discover_local_profiles(self.root / "data")
        self.assertEqual(tuple(profiles), ("x1c",))
        self.assertEqual(profiles["x1c"].qualified_id, "local:x1c")

    def test_malformed_present_local_profile_is_diagnostic(self):
        path = self.root / "data/cad/profiles/broken.json"
        path.parent.mkdir(parents=True)
        path.write_text("{", encoding="utf-8")
        with self.assertRaises(CadProfileError) as caught:
            discover_local_profiles(self.root / "data")
        self.assertEqual(caught.exception.diagnostics[0].kind, "invalid_profile_json")
        self.assertEqual(caught.exception.diagnostics[0].source, str(path))

    def test_loads_preferences_and_absent_file_has_empty_defaults(self):
        preferences = load_preferences(self.root / "data")
        self.assertIsNone(preferences.default_system)
        self.assertEqual(dict(preferences.default_profiles), {})
        self.write_json("data/cad/preferences.json", {
            "schema": "plamp-cad-preferences/1",
            "default_system": "plamp",
            "default_profiles": {"plamp": ["local:x1c", "system:petg"]},
        })
        preferences = load_preferences(self.root / "data")
        self.assertEqual(preferences.default_system, "plamp")
        self.assertEqual(preferences.default_profiles["plamp"],
                         ("local:x1c", "system:petg"))
        with self.assertRaises(TypeError):
            preferences.default_profiles["plamp"] = ()

    def test_rejects_malformed_preferences_strictly(self):
        cases = (
            ({"schema": "wrong", "default_profiles": {}}, "schema"),
            ({"schema": "plamp-cad-preferences/1", "default_profiles": {}, "extra": 1}, "extra"),
            ({"schema": "plamp-cad-preferences/1", "default_system": 2, "default_profiles": {}}, "default_system"),
            ({"schema": "plamp-cad-preferences/1", "default_profiles": {"plamp": "x"}}, "array"),
        )
        for index, (value, message) in enumerate(cases):
            with self.subTest(index=index):
                self.write_json("data/cad/preferences.json", value)
                with self.assertRaisesRegex(CadProfileError, message):
                    load_preferences(self.root / "data")

    def test_rejects_unsafe_or_malformed_default_profile_ids_at_load_time(self):
        invalid_ids = (
            "../../outside", "system:", "local:", "remote:draft",
            "system:draft:extra", ":draft", "not safe",
        )
        for profile_id in invalid_ids:
            with self.subTest(profile_id=profile_id):
                self.write_json("data/cad/preferences.json", {
                    "schema": "plamp-cad-preferences/1",
                    "default_profiles": {"plamp": [profile_id]},
                })
                with self.assertRaises(CadProfileError) as caught:
                    load_preferences(self.root / "data")
                diagnostic = caught.exception.diagnostics[0]
                self.assertEqual(
                    diagnostic.json_path, "$.default_profiles.plamp[0]"
                )
                self.assertEqual(diagnostic.kind, "invalid_profile_id")

    def test_accepts_short_and_exact_qualified_default_profile_ids(self):
        self.write_json("data/cad/preferences.json", {
            "schema": "plamp-cad-preferences/1",
            "default_profiles": {
                "plamp": ["draft", "system:petg", "local:x1c"],
            },
        })
        preferences = load_preferences(self.root / "data")
        self.assertEqual(
            preferences.default_profiles["plamp"],
            ("draft", "system:petg", "local:x1c"),
        )

    def test_present_non_directory_local_profile_path_is_an_error(self):
        path = self.root / "data/cad/profiles"
        path.parent.mkdir(parents=True)
        path.write_text("not a directory", encoding="utf-8")
        with self.assertRaises(CadProfileError) as caught:
            discover_local_profiles(self.root / "data")
        self.assertEqual(caught.exception.diagnostics[0].kind,
                         "invalid_profile_directory")
        self.assertEqual(caught.exception.diagnostics[0].source, str(path))

    def test_local_profile_directory_symlink_is_an_error(self):
        target = self.root / "actual-profiles"
        target.mkdir()
        path = self.root / "data/cad/profiles"
        path.parent.mkdir(parents=True)
        path.symlink_to(target, target_is_directory=True)
        with self.assertRaises(CadProfileError) as caught:
            discover_local_profiles(self.root / "data")
        self.assertEqual(caught.exception.diagnostics[0].kind,
                         "unsafe_profile_path")

    def test_local_profile_file_cannot_escape_data_directory_by_symlink(self):
        outside = self.root / "outside"
        outside.mkdir()
        target = outside / "draft.json"
        target.write_text(json.dumps(self.profile_value()), encoding="utf-8")
        directory = self.root / "data/cad/profiles"
        directory.mkdir(parents=True)
        (directory / "draft.json").symlink_to(target)
        with self.assertRaises(CadProfileError) as caught:
            discover_local_profiles(self.root / "data")
        self.assertEqual(caught.exception.diagnostics[0].kind,
                         "unsafe_profile_path")

    def test_resolves_namespaces_defaults_and_explicit_profiles_in_order(self):
        system_profiles = {"draft": self.load_profile("draft", "quality")}
        local_profiles = {"x1c": self.load_profile("x1c", "printer", local=True)}
        result = resolve_profile_ids(
            system_profiles, local_profiles,
            defaults=("local:x1c",), requested=("system:draft",),
            use_defaults=True,
        )
        self.assertEqual(tuple(profile.qualified_id for profile in result),
                         ("local:x1c", "system:draft"))
        without_defaults = resolve_profile_ids(
            system_profiles, local_profiles,
            defaults=("local:x1c",), requested=("draft",),
            use_defaults=False,
        )
        self.assertEqual(tuple(profile.qualified_id for profile in without_defaults),
                         ("system:draft",))

    def test_ambiguous_short_name_requires_qualified_id(self):
        system = {"petg": self.load_profile("petg", "material")}
        local = {"petg": self.load_profile("petg", "material", local=True)}
        with self.assertRaisesRegex(CadProfileError, "system:petg.*local:petg"):
            resolve_profile_ids(system, local, defaults=(), requested=("petg",),
                                use_defaults=True)

    def test_missing_profile_lists_qualified_choices_and_suggestion(self):
        system = {"draft": self.load_profile("draft", "quality")}
        with self.assertRaises(CadProfileError) as caught:
            resolve_profile_ids(system, {}, defaults=(), requested=("system:draf",),
                                use_defaults=True)
        diagnostic = caught.exception.diagnostics[0]
        self.assertEqual(diagnostic.kind, "unknown_profile")
        self.assertIn("system:draft", diagnostic.choices)
        self.assertEqual(diagnostic.suggestion, "system:draft")

    def test_repository_draft_profile_contains_only_portable_quality_guidance(self):
        path = REPO_ROOT / "cad" / "profiles" / "draft.json"
        profile = load_system_profiles({"draft": path})["draft"]
        self.assertEqual(profile.qualified_id, "system:draft")
        self.assertEqual(profile.kind, "quality")
        self.assertEqual(dict(profile.cad), {
            "render_fn": 24,
            "render_text": False,
        })
        self.assertEqual(dict(profile.machine), {})
        self.assertEqual(set(profile.slicing), {"notes"})


if __name__ == "__main__":
    unittest.main()
