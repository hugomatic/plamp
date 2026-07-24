import unittest

from plamp.cad_readme import render_run_readme


class CadReadmeTests(unittest.TestCase):
    def manifest(self, directives=None, notes=()):
        return {
            "run_id": "run-1",
            "status": "complete",
            "selection": {"product": "ready-panels", "model": None, "sets": []},
            "jobs": [{
                "artifact_id": "panel--abc",
                "model": "box",
                "set": "panel",
                "status": "complete",
                "artifact": "artifacts/panel--abc.stl",
                "artifact_sha256": "1" * 64,
                "variables": {"clearance": 0.2},
                "raw_defines": {"quality": "$preview ? 2 : 20"},
                "variable_sources": {
                    "clearance": {
                        "layers": [{"kind": "model", "source_id": "box", "value": 0.1,
                                    "raw_expression": None},
                                   {"kind": "cli", "source_id": "defines", "value": 0.2,
                                    "raw_expression": None}],
                        "winner": {"kind": "cli", "source_id": "defines", "value": 0.2,
                                   "raw_expression": None},
                    },
                },
                "profiles": [{"qualified_id": "repo:petg", "kind": "printer",
                              "content_hash": "2" * 64}],
                "manufacturing": {"directives": directives or {},
                                  "notes": [list(note) for note in notes]},
                "geometry_fingerprint": "3" * 64,
                "manufacturing_fingerprint": "4" * 64,
                "reused_from": None,
                "dependencies": [{
                    "logical_name": "box/fixture.scad", "classification": "model",
                    "archive_path": "repository/things/box/fixture.scad",
                    "content_hash": "5" * 64, "git_revision": "abc123",
                    "license": None, "asset": False,
                }],
            }],
        }

    @staticmethod
    def directive(value, strength="preference", source="set:panel"):
        return {"value": value, "strength": strength, "source": source}

    def test_leads_with_artifacts_and_plain_complete_slicing_guidance(self):
        directives = {
            "orientation": self.directive("as-exported"),
            "supports": self.directive("forbidden", "requirement"),
            "support_style": self.directive("tree"),
            "ironing": self.directive("recommended"),
            "material": self.directive("PETG"),
            "layer_height": self.directive(0.2),
            "minimum_perimeters": self.directive(4),
            "adhesion": self.directive("brim"),
        }
        text = render_run_readme(self.manifest(
            directives, (("model:box", "Inspect the tabs."),
                         ("set:panel", "Remove the brim.")),
        ))
        for phrase in (
            "Use the exported orientation.", "Do not generate supports.",
            "Use tree supports if supports are enabled.", "Enable ironing.",
            "Use PETG.", "Use a 0.2 mm layer height.",
            "Use at least 4 perimeters.", "Use brim bed adhesion.",
        ):
            self.assertIn(phrase, text)
        self.assertLess(text.index("Artifacts"), text.index("Variable provenance"))
        self.assertLess(text.index("Product `ready-panels`"), text.index("Artifacts"))
        self.assertIn("`artifacts/panel--abc.stl`", text)
        self.assertLess(text.index("Inspect the tabs."), text.index("Remove the brim."))
        self.assertIn("Requirement from `set:panel`", text)

    def test_missing_advice_is_explicit_and_checksum_help_is_actionable(self):
        text = render_run_readme(self.manifest())
        self.assertIn("No slicing guidance was supplied", text)
        self.assertIn("sha256sum artifacts/panel--abc.stl", text)
        self.assertIn("plamp cad show run-1", text)
        self.assertIn("`manifest.json`", text)
        self.assertIn("`logs/`", text)
        self.assertIn("`source/`", text)
        self.assertIn("1111111111111111", text)

    def test_rendering_is_deterministic(self):
        manifest = self.manifest({"supports": self.directive("recommended")})
        self.assertEqual(render_run_readme(manifest), render_run_readme(manifest))

    def test_dependency_inventory_explains_checksums_and_external_libraries(self):
        manifest = self.manifest()
        text = render_run_readme(manifest)
        self.assertIn("Dependency inventory", text)
        self.assertIn("repository/things/box/fixture.scad", text)
        self.assertIn("5555555555555555", text)
        self.assertIn("No external or shared libraries were used", text)
        manifest["jobs"][0]["dependencies"].append({
            "logical_name": "BOSL2/std.scad", "classification": "library",
            "archive_path": "libraries/BOSL2/std.scad", "content_hash": "6" * 64,
            "git_revision": "v2.0", "license": "BSD-2-Clause", "asset": False,
        })
        text = render_run_readme(manifest)
        self.assertIn("External/shared libraries were used", text)
        self.assertIn("BOSL2/std.scad", text)


if __name__ == "__main__":
    unittest.main()
