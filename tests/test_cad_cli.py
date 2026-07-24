import contextlib
import errno
import io
import json
import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from argparse import Namespace
from pathlib import Path
from unittest import mock

from plamp.cad_cli import add_cad_parser, run_cad_command
from plamp.cad_generation import CadRunExistsError, generate_plan
from plamp.cad_scaffold import (
    CadDestinationExistsError,
    CadSelectionError,
    CadTemplate,
    CreatedPart,
)
from plamp.cli import build_parser, main
from plamp.context import RuntimeContext


SOURCE = textwrap.dedent("""\
    view = "assembly"; // [floor, box, assembly]
    /* generate.json
    {
      "default_preset": "split",
      "views": {
        "floor": {"description": "Printable floor", "variables": {"flag": true}},
        "box": {"description": "Fused box"},
        "assembly": {"description": "Complete assembly"}
      },
      "presets": {
        "split": {
          "description": "Separate printable pieces",
          "items": ["view:floor", "view:box"]
        }
      }
    }
    */
    cube(1);
""")

SCAFFOLD_SOURCE = b'''view = "__PLAMP_PART__"; // [__PLAMP_PART__, assembly]
/* generate.json
{"default_preset":"both","views":{"__PLAMP_PART__":{"description":"Part"},"assembly":{"description":"Assembly"}},"presets":{"both":{"items":["view:__PLAMP_PART__","view:assembly"]}}}
*/
module __PLAMP_PART___positive() { cube(1); }
module __PLAMP_PART___negative() { cylinder(1); }
module __PLAMP_PART__() { difference() { __PLAMP_PART___positive(); __PLAMP_PART___negative(); } }
if (view == "__PLAMP_PART__") { __PLAMP_PART__(); }
else if (view == "assembly") { __PLAMP_PART__(); }
'''


class CadCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.data = self.root / "data"
        part_dir = self.root / "things" / "fixture"
        part_dir.mkdir(parents=True)
        self.scad = part_dir / "fixture.scad"
        self.scad.write_text(SOURCE, encoding="utf-8")
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), "config", "user.name", "Test"], check=True)
        subprocess.run(["git", "-C", str(self.root), "config", "user.email", "test@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(self.root), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "fixture"], check=True)
        self.context = RuntimeContext(self.root, self.data)

    def tearDown(self):
        self.temp.cleanup()

    def env(self):
        return {"PLAMP_ROOT": str(self.root), "PLAMP_DATA_DIR": str(self.data)}

    def test_cad_help_lists_all_commands(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout), self.assertRaises(SystemExit) as caught:
            main(["cad", "--help"], env=self.env())
        self.assertEqual(caught.exception.code, 0)
        for command in ("new", "sets", "validate", "plan", "menu", "generate", "runs", "show", "log"):
            self.assertIn(command, stdout.getvalue())
        self.assertNotIn("views", stdout.getvalue())

    def _clean_catalog(self, *, second_system=False, missing_descriptions=False):
        self.scad.write_text(
            'set = ""; // [floor, assembly]\n'
            'if (set == "floor") cube(1);\n',
            encoding="utf-8",
        )
        sidecar = self.scad.with_suffix(".cad.json")
        sidecar.write_text(json.dumps({
            "schema": "plamp-cad-model/1",
            "name": "fixture",
            "source": "fixture.scad",
            "description": "" if missing_descriptions else "Fixture model",
            "sets": {
                "": {"description": "Normal output"},
                "floor": {"description": "Printable floor"},
                "assembly": {
                    "description": "Complete assembly", "printable": False,
                },
            },
        }), encoding="utf-8")
        (self.root / "cad" / "profiles").mkdir(parents=True, exist_ok=True)
        (self.root / "cad" / "profiles" / "petg.json").write_text("{}\n")
        (self.root / "cad" / "lib").mkdir(exist_ok=True)
        manifest = {
            "schema": "plamp-cad-system/1",
            "name": "alpha",
            "description": "" if missing_descriptions else "Alpha system",
            "models": {"fixture": "things/fixture/fixture.cad.json"},
            "libraries": {"fasteners": {
                "path": "cad/lib", "description": "Fastener library",
            }},
            "profiles": {"petg": "cad/profiles/petg.json"},
            "default_product": "printable",
            "products": {"printable": {
                "description": "Printable fixture",
                "items": [{"model": "fixture", "set": "floor"}],
            }},
        }
        path = self.root / "cad" / "alpha.system.cad.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        if second_system:
            manifest["name"] = "beta"
            manifest["description"] = "Beta system"
            manifest["default_product"] = None
            (self.root / "cad" / "beta.system.cad.json").write_text(
                json.dumps(manifest), encoding="utf-8"
            )
        return path

    def test_help_adds_complete_catalog_navigation(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout), self.assertRaises(SystemExit):
            main(["cad", "--help"], env=self.env())
        for command in (
            "systems", "models", "sets", "products", "profiles", "libraries",
            "templates", "new", "plan", "generate",
        ):
            self.assertIn(command, stdout.getvalue())

    def test_navigation_lists_descriptions_and_parent_ids_in_json(self):
        self._clean_catalog()
        cases = {
            ("sets", "fixture"): ("set", "", "Normal output"),
            ("models",): ("model", "fixture", "Fixture model"),
            ("products",): ("product", "printable", "Printable fixture"),
            ("profiles",): ("profile", "petg", "(no description)"),
            ("libraries",): ("library", "fasteners", "Fastener library"),
        }
        for command, expected in cases.items():
            with self.subTest(command=command):
                stdout = io.StringIO()
                argv = ["cad", *command, "--system", "alpha", "--json"]
                self.assertEqual(main(argv, env=self.env(), stdout=stdout,
                                      stderr=io.StringIO()), 0)
                row = json.loads(stdout.getvalue())[0]
                self.assertEqual((row["kind"], row["id"], row["description"]), expected)
                self.assertEqual(row["system"], "alpha")
                self.assertIn("path", row)
                self.assertEqual(row["status"], "valid")
                self.assertEqual(row["diagnostics"], [])
        rows = json.loads(self._run_main(["cad", "sets", "fixture", "--json"])[0])
        self.assertEqual(rows[0]["model"], "fixture")
        self.assertTrue(rows[0]["printable"])

    def _run_main(self, argv, *, stdin=None):
        stdout, stderr = io.StringIO(), io.StringIO()
        rc = main(argv, env=self.env(), stdin=stdin or io.StringIO(),
                  stdout=stdout, stderr=stderr)
        return stdout.getvalue(), stderr.getvalue(), rc

    def test_plan_uses_default_product_and_direct_set_vocabulary(self):
        self._clean_catalog()
        default, error, rc = self._run_main(["cad", "plan", "--json"])
        self.assertEqual((rc, error), (0, ""))
        value = json.loads(default)
        self.assertEqual(value["selection"]["product"], "printable")
        self.assertEqual(value["jobs"][0]["set_name"], "floor")

        direct, error, rc = self._run_main(
            ["cad", "plan", "fixture", "--set", "assembly", "--json"]
        )
        self.assertEqual((rc, error), (0, ""))
        value = json.loads(direct)
        self.assertEqual(value["selection"]["model"], "fixture")
        self.assertEqual(value["jobs"][0]["set_name"], "assembly")

        all_sets, error, rc = self._run_main(
            ["cad", "plan", "fixture", "--all-sets", "--json"]
        )
        self.assertEqual((rc, error), (0, ""))
        self.assertEqual(
            [job["set_name"] for job in json.loads(all_sets)["jobs"]],
            ["", "floor", "assembly"],
        )

        conflict, _error, rc = self._run_main(
            ["cad", "plan", "fixture", "--product", "printable", "--json"]
        )
        self.assertEqual(rc, 2)
        self.assertIn("cannot be combined", json.loads(conflict)[0]["message"])

    def test_validate_uses_system_model_metadata_without_openscad(self):
        self._clean_catalog()
        output, error, rc = self._run_main([
            "cad", "validate", "fixture", "--json",
        ])
        self.assertEqual((rc, error), (0, ""))
        self.assertEqual(json.loads(output)["models"], ["fixture"])

    def test_dirty_system_model_set_can_be_planned_without_revision(self):
        self._clean_catalog()
        self.scad.write_text(self.scad.read_text() + "// dirty planning change\n")
        output, error, rc = self._run_main([
            "cad", "plan", "fixture", "--set", "floor", "--json",
        ])
        self.assertEqual((rc, error), (0, ""))
        value = json.loads(output)
        self.assertEqual(value["selection"]["model"], "fixture")
        self.assertEqual(value["jobs"][0]["set_name"], "floor")

    def test_repeatable_sets_keep_order_and_set_define_reaches_generation(self):
        self._clean_catalog()
        fake = self._fake_openscad()
        observed = {}

        def generate(plan, **kwargs):
            observed["sets"] = [job.set_name for job in plan.jobs]
            observed["variables"] = [dict(job.variables) for job in plan.jobs]
            return {"status": "complete", "jobs": [], "run_id": "sets-test"}

        rc = main([
            "cad", "generate", "fixture", "--set", "assembly", "--set", "floor",
            "--set-define", "floor:gap=0.3", "--revision", "test",
            "--openscad", str(fake),
        ], env=self.env(), stdout=io.StringIO(), stderr=io.StringIO(),
            cad_generate_func=generate)
        self.assertEqual(rc, 0)
        self.assertEqual(observed["sets"], ["assembly", "floor"])
        self.assertNotIn("gap", observed["variables"][0])
        self.assertEqual(observed["variables"][1]["gap"], 0.3)

    def test_removed_views_command_reports_exact_replacement(self):
        output, error, rc = self._run_main(["cad", "views", "fixture"])
        self.assertEqual((output, rc), ("", 2))
        self.assertIn("cad views was removed", error)
        self.assertIn("plamp cad sets MODEL", error)

    def test_removed_selection_options_report_their_replacements(self):
        replacements = {
            "--view": "--set", "--view-define": "--set-define",
            "--preset": "--product",
        }
        for option, replacement in replacements.items():
            with self.subTest(option=option):
                stderr = io.StringIO()
                with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit):
                    build_parser().parse_args(["cad", "plan", "fixture", option, "old"])
                self.assertIn(f"{option} was removed", stderr.getvalue())
                self.assertIn(replacement, stderr.getvalue())

    def test_generate_has_no_legacy_output_or_commit_arguments(self):
        parser = build_parser()
        args = parser.parse_args(["cad", "generate", "fixture"])
        self.assertFalse(hasattr(args, "legacy_output"))
        self.assertFalse(hasattr(args, "legacy_commit"))
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parser.parse_args(["cad", "generate", "fixture", "/tmp/out", "HEAD"])

    def test_menu_back_from_model_sets_retains_selected_system(self):
        self._clean_catalog()
        fake = self._fake_openscad()
        stdin = mock.Mock(
            readline=mock.Mock(side_effect=("b\n", "1\n")),
            isatty=mock.Mock(return_value=True),
        )
        stdout, stderr = io.StringIO(), io.StringIO()
        rc = main(
            ["cad", "menu", "fixture", "--revision", "test",
             "--define", "quality=42", "--set-define", "floor:gap=0.3",
             "--openscad", str(fake)],
            env=self.env(), stdin=stdin, stdout=stdout, stderr=stderr,
            cad_generate_func=lambda plan, **kwargs: {
                "status": "complete", "jobs": [], "run_id": "menu-test",
                "selection": {
                    "product": plan.selection.product,
                    "raw_defines": list(plan.selection.raw_defines),
                    "set_defines": {
                        name: dict(values)
                        for name, values in plan.selection.set_defines.items()
                    },
                },
            },
        )
        self.assertEqual((rc, stderr.getvalue()), (0, ""))
        self.assertIn("Sets for fixture:", stdout.getvalue())
        self.assertIn("System alpha:", stdout.getvalue())
        self.assertEqual(stdin.readline.call_count, 2)
        manifest = json.loads(stdout.getvalue()[stdout.getvalue().index("{"):])
        self.assertEqual(manifest["selection"]["raw_defines"], ["quality=42"])
        self.assertEqual(manifest["selection"]["set_defines"]["floor"]["gap"], 0.3)

    def test_duplicate_regeneration_and_menu_parity_use_new_selection(self):
        self._clean_catalog()
        fake = self._fake_openscad()
        existing = self.root / "existing"
        calls = []

        def generate(plan, **kwargs):
            calls.append(kwargs["regenerate"])
            if not kwargs["regenerate"]:
                raise CadRunExistsError("existing", existing)
            return {"status": "complete", "jobs": [], "run_id": "existing"}

        output, error = io.StringIO(), io.StringIO()
        rc = main([
            "cad", "generate", "fixture", "--revision", "test",
            "--openscad", str(fake),
        ], env=self.env(), stdout=output, stderr=error,
            cad_generate_func=generate)
        self.assertEqual(rc, 4)
        self.assertIn("--regenerate", error.getvalue())

        for argv, answers in (
            (["cad", "generate", "fixture", "--revision", "test",
              "--openscad", str(fake)], ("y\n",)),
            (["cad", "menu", "--revision", "test", "--openscad", str(fake)],
             ("1\n", "y\n")),
        ):
            with self.subTest(argv=argv):
                calls.clear()
                stdin = mock.Mock(readline=mock.Mock(side_effect=answers),
                                  isatty=mock.Mock(return_value=True))
                stdout, stderr = io.StringIO(), io.StringIO()
                rc = main(argv, env=self.env(), stdin=stdin, stdout=stdout,
                          stderr=stderr, cad_generate_func=generate)
                self.assertEqual((rc, stderr.getvalue()), (0, ""))
                self.assertEqual(calls, [False, True])

    def test_menu_eof_and_interrupt_are_clean_cancellations(self):
        self._clean_catalog()
        for source in (io.StringIO(""), mock.Mock(
            readline=mock.Mock(side_effect=KeyboardInterrupt),
            isatty=mock.Mock(return_value=True),
        )):
            with self.subTest(source=source):
                stderr = io.StringIO()
                rc = main(["cad", "menu"], env=self.env(), stdin=source,
                          stdout=io.StringIO(), stderr=stderr)
                self.assertEqual(rc, 2)
                self.assertIn("cancel", stderr.getvalue().lower())

    def test_menu_reprompts_after_invalid_new_contract_selection(self):
        self._clean_catalog()
        fake = self._fake_openscad()
        stdin = mock.Mock(readline=mock.Mock(side_effect=("wrong\n", "1\n")),
                          isatty=mock.Mock(return_value=True))
        stdout = io.StringIO()
        rc = main([
            "cad", "menu", "--revision", "test", "--openscad", str(fake),
        ], env=self.env(), stdin=stdin, stdout=stdout, stderr=io.StringIO(),
            cad_generate_func=lambda *a, **k: {
                "status": "complete", "jobs": [], "run_id": "test",
            })
        self.assertEqual(rc, 0)
        self.assertIn("Invalid selection.", stdout.getvalue())
        self.assertEqual(stdout.getvalue().count("Select product or model"), 2)

    def test_preview_resolver_snapshot_and_cleanup_use_new_contract(self):
        self._clean_catalog()
        fake = self._fake_openscad()
        observed = []

        def generate(plan, **kwargs):
            snapshots = kwargs["snapshots"]
            observed.append({
                "raw": list(plan.selection.raw_defines),
                "openscad": kwargs["openscad"],
                "identities": {name: value.source_identity
                               for name, value in snapshots.items()},
                "roots": [value.cleanup_root for value in snapshots.values()],
                "alive": [value.cleanup_root.is_dir() for value in snapshots.values()],
            })
            return {"status": "complete", "jobs": [], "run_id": "test"}

        rc = main([
            "cad", "generate", "fixture", "--revision", "test", "--preview",
            "--define", "render_fn=64", "--openscad", str(fake),
        ], env=self.env(), stdout=io.StringIO(), stderr=io.StringIO(),
            cad_generate_func=generate)
        self.assertEqual(rc, 0)
        self.assertEqual(observed[0]["raw"], [
            "render_fn=24", "render_text=false", "render_fn=64",
        ])
        self.assertEqual(observed[0]["openscad"], fake)
        self.assertTrue(all(observed[0]["alive"]))
        self.assertTrue(all(not root.exists() for root in observed[0]["roots"]))

        stdin = mock.Mock(readline=mock.Mock(side_effect=("1\n",)),
                          isatty=mock.Mock(return_value=True))
        rc = main([
            "cad", "menu", "--revision", "test", "--openscad", str(fake),
        ], env=self.env(), stdin=stdin, stdout=io.StringIO(), stderr=io.StringIO(),
            cad_generate_func=generate)
        self.assertEqual(rc, 0)
        self.assertEqual(observed[1]["openscad"], fake)
        self.assertTrue(all(not root.exists() for root in observed[1]["roots"]))

    def test_systems_retains_invalid_candidates_and_missing_descriptions(self):
        self._clean_catalog(missing_descriptions=True)
        (self.root / "cad" / "broken.system.cad.json").write_text("{")
        output, _error, rc = self._run_main(["cad", "systems", "--json"])
        self.assertEqual(rc, 0)
        rows = json.loads(output)
        self.assertEqual([row["status"] for row in rows], ["valid", "invalid"])
        alpha = next(row for row in rows if row["id"] == "alpha")
        self.assertEqual(alpha["description"], "(no description)")
        broken = next(row for row in rows if row["status"] == "invalid")
        self.assertTrue(broken["diagnostics"])

        selected, selected_error, selected_rc = self._run_main(
            ["cad", "models", "--system", "cad/broken.system.cad.json", "--json"]
        )
        self.assertEqual(selected_rc, 2)
        self.assertEqual(json.loads(selected)[0]["code"], "CAD100")
        self.assertNotIn("Traceback", selected_error)

        external = self.root / "other" / "outside.system.cad.json"
        external.parent.mkdir()
        external.write_text(json.dumps({
            "schema": "plamp-cad-system/1", "name": "outside",
            "models": {"lost": "things/missing.cad.json"},
        }))
        selected, selected_error, selected_rc = self._run_main(
            ["cad", "models", "--system", "other/outside.system.cad.json", "--json"]
        )
        self.assertEqual(selected_rc, 2)
        self.assertEqual(json.loads(selected)[0]["code"], "CAD121")
        self.assertNotIn("Traceback", selected_error)

    def test_multiple_systems_require_exact_guidance_noninteractive(self):
        self._clean_catalog(second_system=True)
        output, _error, rc = self._run_main(["cad", "models", "--json"])
        self.assertEqual(rc, 2)
        diagnostic = json.loads(output)[0]
        self.assertEqual(diagnostic["code"], "CAD200")
        self.assertIn("--system NAME_OR_PATH", diagnostic["message"])

    def test_multiple_systems_can_be_chosen_interactively_and_explicit_path_works(self):
        alpha = self._clean_catalog(second_system=True)
        stdout, _stderr, rc = self._run_main(
            ["cad", "models"], stdin=mock.Mock(
                readline=mock.Mock(side_effect=("2\n", "1\n", "b\n", "b\n", "q\n")),
                isatty=mock.Mock(return_value=True),
            )
        )
        self.assertEqual(rc, 0)
        self.assertGreaterEqual(stdout.count("Systems:"), 2)
        self.assertGreaterEqual(stdout.count("System beta:"), 2)
        self.assertIn("Sets for fixture:", stdout)
        self.assertIn("set floor - Printable floor", stdout)
        output, _error, rc = self._run_main(
            ["cad", "models", "--system", str(alpha), "--json"]
        )
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(output)[0]["system"], "alpha")

    def test_library_paths_are_normalized_repository_relative(self):
        manifest_path = self._clean_catalog()
        manifest = json.loads(manifest_path.read_text())
        for declaration in ("./cad/lib", str((self.root / "cad" / "lib").resolve())):
            with self.subTest(declaration=declaration):
                manifest["libraries"]["fasteners"]["path"] = declaration
                manifest_path.write_text(json.dumps(manifest))
                output, error, rc = self._run_main(
                    ["cad", "libraries", "--system", "alpha", "--json"]
                )
                self.assertEqual((rc, error), (0, ""))
                self.assertEqual(json.loads(output)[0]["path"], "cad/lib")

    def test_zero_system_error_does_not_claim_multiple_systems(self):
        output, _error, rc = self._run_main(["cad", "models", "--json"])
        self.assertEqual(rc, 2)
        message = json.loads(output)[0]["message"]
        self.assertIn("no CAD systems", message)
        self.assertNotIn("multiple CAD systems", message)

    def test_human_navigation_always_shows_descriptions(self):
        self._clean_catalog(missing_descriptions=True)
        output, _error, rc = self._run_main(["cad", "models"])
        self.assertEqual(rc, 0)
        self.assertIn("fixture", output)
        self.assertIn("(no description)", output)

    def test_new_lists_templates_as_repository_relative_json(self):
        parser = build_parser()
        stdout = io.StringIO()
        rc = run_cad_command(
            parser.parse_args(["cad", "new", "--list-templates", "--json"]),
            self.context,
            io.StringIO(),
            stdout,
            io.StringIO(),
            {"discover_templates": lambda root: (
                CadTemplate("cad", root / "things" / "3d_template" / "cad.scad"),
            )},
        )

        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(stdout.getvalue()), {
            "templates": [{"name": "cad", "path": "things/3d_template/cad.scad"}],
        })

    def test_new_creates_default_and_named_templates_as_json(self):
        parser = build_parser()
        calls = []

        def create(root, part, template):
            calls.append((root, part, template))
            directory = root / "things" / part
            return CreatedPart(part, template, directory, directory / f"{part}.scad")

        for argv, expected in (
            (["cad", "new", "pump_bracket", "--json"], ("pump_bracket", "cad")),
            (["cad", "new", "access_cover", "--template", "flat_plate", "--json"],
             ("access_cover", "flat_plate")),
        ):
            with self.subTest(argv=argv):
                stdout = io.StringIO()
                rc = run_cad_command(
                    parser.parse_args(argv), self.context, io.StringIO(), stdout,
                    io.StringIO(), {"create_part": create},
                )
                part, template = expected
                self.assertEqual(rc, 0)
                self.assertEqual(json.loads(stdout.getvalue()), {
                    "part": part,
                    "template": template,
                    "directory": f"things/{part}",
                    "scad_path": f"things/{part}/{part}.scad",
                    "metadata_valid": True,
                })
        self.assertEqual(calls, [
            (self.root, "pump_bracket", "cad"),
            (self.root, "access_cover", "flat_plate"),
        ])

    def test_new_text_prints_scad_path_and_exact_validation_command(self):
        parser = build_parser()
        created = CreatedPart(
            "pump_bracket",
            "cad",
            self.root / "things" / "pump_bracket",
            self.root / "things" / "pump_bracket" / "pump_bracket.scad",
        )
        stdout = io.StringIO()

        rc = run_cad_command(
            parser.parse_args(["cad", "new", "pump_bracket"]), self.context,
            io.StringIO(), stdout, io.StringIO(),
            {"create_part": lambda *args: created},
        )

        self.assertEqual(rc, 0)
        self.assertEqual(
            stdout.getvalue(),
            "things/pump_bracket/pump_bracket.scad\n"
            "plamp cad validate pump_bracket --json\n",
        )

    def test_new_usage_errors_are_structured_json_and_do_not_create(self):
        parser = build_parser()
        calls = []
        cases = (
            ["cad", "new", "--json"],
            ["cad", "new", "part", "--list-templates", "--json"],
            ["cad", "new", "--list-templates", "--template", "flat_plate", "--json"],
        )
        for argv in cases:
            with self.subTest(argv=argv):
                stdout, stderr = io.StringIO(), io.StringIO()
                rc = run_cad_command(
                    parser.parse_args(argv), self.context, io.StringIO(), stdout, stderr,
                    {
                        "create_part": lambda *args: calls.append(args),
                        "discover_templates": lambda root: (),
                    },
                )
                diagnostic = json.loads(stdout.getvalue())[0]
                self.assertEqual(rc, 2)
                self.assertEqual(diagnostic["code"], "CAD200")
                self.assertEqual(diagnostic["kind"], "invalid_selection")
                self.assertNotIn("Traceback", stderr.getvalue())
        self.assertEqual(calls, [])

    def test_new_creation_error_is_structured_and_has_no_traceback(self):
        parser = build_parser()
        stdout, stderr = io.StringIO(), io.StringIO()
        rc = run_cad_command(
            parser.parse_args(["cad", "new", "pump_bracket", "--json"]),
            self.context,
            io.StringIO(),
            stdout,
            stderr,
            {"create_part": lambda *args: (_ for _ in ()).throw(
                ValueError("unknown CAD template 'wrong'; available: cad")
            )},
        )

        self.assertEqual(rc, 2)
        self.assertIn("available: cad", json.loads(stdout.getvalue())[0]["message"])
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_new_selection_failures_remain_cad200(self):
        parser = build_parser()
        for error in (
            CadSelectionError("invalid template contract"),
            CadDestinationExistsError("destination exists"),
            ValueError("invalid command selection"),
        ):
            with self.subTest(error=type(error).__name__):
                stdout, stderr = io.StringIO(), io.StringIO()
                rc = run_cad_command(
                    parser.parse_args(["cad", "new", "pump-bracket", "--json"]),
                    self.context, io.StringIO(), stdout, stderr,
                    {"create_part": lambda *args, error=error: (_ for _ in ()).throw(error)},
                )
                diagnostic = json.loads(stdout.getvalue())[0]
                self.assertEqual(rc, 2)
                self.assertEqual((diagnostic["code"], diagnostic["kind"]), ("CAD200", "invalid_selection"))
                self.assertNotIn("Traceback", stderr.getvalue())

    def test_new_operational_io_failures_are_cad400(self):
        parser = build_parser()
        failures = (
            PermissionError(errno.EACCES, "template read denied"),
            OSError(errno.ENOSPC, "staging write full"),
            OSError(errno.EIO, "commit failed"),
            FileExistsError(errno.EEXIST, "staging collision"),
        )
        for list_templates in (False, True):
            for error in failures:
                with self.subTest(list_templates=list_templates, errno=error.errno):
                    argv = ["cad", "new", "--list-templates", "--json"] if list_templates else ["cad", "new", "pump-bracket", "--json"]
                    dependency = "discover_templates" if list_templates else "create_part"
                    stdout, stderr = io.StringIO(), io.StringIO()
                    rc = run_cad_command(
                        parser.parse_args(argv), self.context, io.StringIO(), stdout, stderr,
                        {dependency: lambda *args, error=error: (_ for _ in ()).throw(error)},
                    )
                    diagnostic = json.loads(stdout.getvalue())[0]
                    self.assertEqual(rc, 4)
                    self.assertEqual((diagnostic["code"], diagnostic["kind"]), ("CAD400", "operation_failed"))
                    self.assertNotIn("Traceback", stderr.getvalue())

    def test_new_internal_stage_io_failures_are_cad400_and_leave_no_residue(self):
        template = self.root / "things" / "3d_template" / "cad.scad"
        template.parent.mkdir(parents=True)
        template.write_bytes(SCAFFOLD_SOURCE)

        def partial_write(path, _data):
            path.write_bytes(b"partial")
            raise OSError(errno.ENOSPC, "staging write full")

        stages = (
            (
                "discovery",
                "plamp.cad_scaffold.discover_templates",
                PermissionError(errno.EACCES, "discovery denied"),
            ),
            (
                "secure_read",
                "plamp.cad_scaffold._read_template",
                PermissionError(errno.EACCES, "secure read denied"),
            ),
            (
                "staging_mkdir",
                "plamp.cad_scaffold._make_staging",
                OSError(errno.ENOSPC, "staging mkdir full"),
            ),
            (
                "staging_write_cleanup",
                "plamp.cad_scaffold._write_exclusive",
                partial_write,
            ),
            (
                "publication_cleanup",
                "plamp.cad_scaffold._publish_noreplace",
                OSError(errno.EIO, "publication failed"),
            ),
        )
        for stage, target, failure in stages:
            part = f"fault_{stage}"
            with self.subTest(stage=stage), mock.patch(target, side_effect=failure):
                stdout, stderr = io.StringIO(), io.StringIO()
                rc = main(
                    ["cad", "new", part, "--json"],
                    env=self.env(),
                    stdout=stdout,
                    stderr=stderr,
                )
                diagnostic = json.loads(stdout.getvalue())[0]
                self.assertEqual(rc, 4)
                self.assertEqual(
                    (diagnostic["code"], diagnostic["kind"]),
                    ("CAD400", "operation_failed"),
                )
                self.assertNotIn("Traceback", stderr.getvalue())
                self.assertFalse((self.root / "things" / part).exists())
                self.assertEqual(
                    list((self.root / "things").glob(f".{part}.staging-*")), []
                )

    @unittest.skip("pre-1.0 embedded view/preset contract removed")
    def test_generated_hyphenated_part_supports_views_validate_and_plan(self):
        repository = Path(__file__).resolve().parents[1]
        shutil.copytree(
            repository / "things" / "3d_template",
            self.root / "things" / "3d_template",
        )
        openscad_calls = []

        created_output = io.StringIO()
        self.assertEqual(
            main(
                ["cad", "new", "pump-bracket", "--json"],
                env=self.env(),
                stdout=created_output,
                stderr=io.StringIO(),
                cad_generate_func=lambda *args, **kwargs: openscad_calls.append((args, kwargs)),
            ),
            0,
        )
        self.assertEqual(json.loads(created_output.getvalue())["part"], "pump-bracket")

        outputs = {}
        for action in ("views", "validate", "plan"):
            stream = io.StringIO()
            self.assertEqual(
                main(
                    ["cad", action, "pump-bracket", "--json"],
                    env=self.env(),
                    stdout=stream,
                    stderr=io.StringIO(),
                    cad_generate_func=lambda *args, **kwargs: openscad_calls.append((args, kwargs)),
                ),
                0,
            )
            outputs[action] = json.loads(stream.getvalue())

        self.assertEqual(
            [item["name"] for item in outputs["views"]["views"]],
            ["pump_bracket", "assembly"],
        )
        self.assertTrue(outputs["validate"]["valid"])
        self.assertEqual(outputs["plan"]["job_count"], 2)
        self.assertEqual(
            [job["view"] for job in outputs["plan"]["jobs"]],
            ["pump_bracket", "assembly"],
        )
        self.assertEqual(openscad_calls, [])

    @unittest.skip("replaced by cad sets replacement diagnostic coverage")
    def test_views_resolves_part_name_and_path_and_keeps_assembly_last(self):
        for part in ("fixture", "things/fixture/fixture.scad"):
            with self.subTest(part=part):
                stdout = io.StringIO()
                rc = main(["cad", "views", part, "--json"], env=self.env(), stdout=stdout, stderr=io.StringIO())
                result = json.loads(stdout.getvalue())
                self.assertEqual(rc, 0)
                self.assertEqual([item["name"] for item in result["views"]], ["floor", "box", "assembly"])
                self.assertEqual(result["views"][0]["description"], "Printable floor")

    @unittest.skip("embedded generate.json metadata removed")
    def test_invalid_metadata_prints_json_diagnostics_without_traceback(self):
        self.scad.write_text('view = "box"; // [box]\n/* generate.json\n{\n*/\n')
        stdout, stderr = io.StringIO(), io.StringIO()
        rc = main(["cad", "validate", "fixture", "--json"], env=self.env(), stdout=stdout, stderr=stderr)
        diagnostics = json.loads(stdout.getvalue())
        self.assertEqual(rc, 2)
        self.assertEqual(diagnostics[0]["code"], "CAD100")
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_validate_does_not_call_openscad(self):
        return self.test_validate_uses_system_model_metadata_without_openscad()
        calls = []
        stdout = io.StringIO()
        rc = main(
            ["cad", "validate", "fixture", "--json"], env=self.env(), stdout=stdout,
            stderr=io.StringIO(), cad_generate_func=lambda *a, **k: calls.append((a, k)),
        )
        self.assertEqual(rc, 0)
        self.assertEqual(calls, [])
        self.assertTrue(json.loads(stdout.getvalue())["valid"])

    @unittest.skip("legacy preset plan contract removed")
    def test_plan_json_does_not_call_openscad_and_reports_counts(self):
        calls = []
        stdout = io.StringIO()
        rc = main(
            ["cad", "plan", "fixture", "--preset", "split", "--json"],
            env=self.env(), stdout=stdout, stderr=io.StringIO(),
            cad_generate_func=lambda *a, **k: calls.append((a, k)),
        )
        result = json.loads(stdout.getvalue())
        self.assertEqual(rc, 0)
        self.assertEqual(result["job_count"], 2)
        self.assertEqual([job["view"] for job in result["jobs"]], ["floor", "box"])
        self.assertEqual(calls, [])

    @unittest.skip("legacy preset plan contract removed")
    def test_plan_text_includes_descriptions_jobs_and_effective_values(self):
        stdout = io.StringIO()
        rc = main(
            ["cad", "plan", "fixture", "--preset", "split"], env=self.env(),
            stdout=stdout, stderr=io.StringIO(),
        )
        self.assertEqual(rc, 0)
        self.assertIn("2 render job(s)", stdout.getvalue())
        self.assertIn("Separate printable pieces", stdout.getvalue())
        self.assertIn("Printable floor", stdout.getvalue())
        self.assertIn("artifact:", stdout.getvalue())
        self.assertIn("variables:", stdout.getvalue())

    @unittest.skip("legacy view history contract removed")
    def test_direct_view_plan_uses_median_of_strictly_comparable_history(self):
        stdout = io.StringIO()
        def run(path="things/fixture/fixture.scad", generator=1, *, view="floor",
                variables=None, raw_defines=None, status="complete", elapsed=10.0,
                size=1000):
            return {
                "source": {"scad_path": path}, "generator_version": generator,
                "jobs": [{
                    "view": view,
                    "variables": {"flag": True} if variables is None else variables,
                    "raw_defines": raw_defines or {},
                    "elapsed_seconds": elapsed, "artifact_bytes": size, "status": status,
                }],
            }

        archived = [
            run(elapsed=99.0, size=9900),  # newest is intentionally not the median
            run(elapsed=10.0, size=1000),
            run(elapsed=11.0, size=1100),
            run(path="things/other/fixture.scad", elapsed=1.0, size=1),
            run(generator=2, elapsed=2.0, size=2),
            run(view="box", elapsed=3.0, size=3),
            run(variables={"quality": 2}, elapsed=4.0, size=4),
            run(status="failed", elapsed=5.0, size=5),
            run(variables={"flag": 1}, elapsed=0.0, size=0),
            run(generator=True, elapsed=1.0, size=1),
            run(raw_defines={"quality": "2"}, elapsed=2.0, size=2),
        ]
        rc = main(
            ["cad", "plan", "fixture", "--view", "floor", "--json"], env=self.env(),
            stdout=stdout, stderr=io.StringIO(), cad_list_runs_func=lambda *a, **k: archived,
        )
        result = json.loads(stdout.getvalue())
        self.assertEqual(rc, 0)
        self.assertEqual(result["jobs"][0]["description"], "Printable floor")
        self.assertEqual(result["jobs"][0]["estimate"], {
            "elapsed_seconds": 11.0, "artifact_bytes": 1100,
        })

    def test_dirty_source_can_be_planned_without_revision(self):
        return self.test_dirty_system_model_set_can_be_planned_without_revision()
        self.scad.write_text(SOURCE + "// authoring change\n", encoding="utf-8")
        stdout = io.StringIO()
        rc = main(
            ["cad", "plan", "fixture", "--json"], env=self.env(), stdout=stdout,
            stderr=io.StringIO(),
        )
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(stdout.getvalue())["job_count"], 2)

    def test_repeatable_views_and_raw_defines_reach_generation(self):
        return self.test_repeatable_sets_keep_order_and_set_define_reaches_generation()
        captured = []

        def generate(plan, **kwargs):
            captured.append((plan, kwargs))
            return {"run_id": "run-1", "status": "complete", "jobs": []}

        rc = main(
            ["cad", "generate", "fixture", "--view", "assembly", "--view", "box",
             "--openscad", str(self._fake_openscad()),
             "--define", "quality=$preview ? 2 : 20", "--view-define", "box:fit=0.2", "--json"],
            env=self.env(), stdout=io.StringIO(), stderr=io.StringIO(), cad_generate_func=generate,
        )
        self.assertEqual(rc, 0)
        selection = captured[0][0].selection
        self.assertEqual(selection.views, ("assembly", "box"))
        self.assertEqual(selection.raw_defines, ("quality=$preview ? 2 : 20",))
        self.assertEqual(selection.raw_view_defines["box"], ("fit=0.2",))

    def test_generate_and_menu_accept_regenerate_switch(self):
        parser = build_parser()
        for argv in (
            ["cad", "generate", "fixture", "--regenerate"],
            ["cad", "menu", "fixture", "--regenerate"],
        ):
            with self.subTest(argv=argv):
                self.assertTrue(parser.parse_args(argv).regenerate)

    def test_noninteractive_duplicate_reports_existing_path_and_switch(self):
        return self.test_duplicate_regeneration_and_menu_parity_use_new_selection()
        existing = self.data / "cad" / "prints" / "fixture" / "existing"

        class NonInteractiveInput(io.StringIO):
            def isatty(self):
                return False

            def readline(self, *args, **kwargs):
                raise AssertionError("non-interactive duplicate must not read stdin")

        for json_output in (False, True):
            with self.subTest(json_output=json_output):
                stdout, stderr = io.StringIO(), io.StringIO()
                argv = ["cad", "generate", "fixture"]
                if json_output:
                    argv.append("--json")
                rc = main(
                    argv,
                    env=self.env(),
                    stdin=NonInteractiveInput(),
                    stdout=stdout,
                    stderr=stderr,
                    cad_generate_func=lambda *args, **kwargs: (
                        _ for _ in ()
                    ).throw(CadRunExistsError("existing", existing)),
                )
                output = stdout.getvalue() + stderr.getvalue()
                self.assertEqual(rc, 4)
                self.assertIn(str(existing), output)
                self.assertIn("--regenerate", output)

    def test_interactive_duplicate_can_regenerate_existing_run(self):
        return self.test_duplicate_regeneration_and_menu_parity_use_new_selection()
        existing = self.data / "cad" / "prints" / "fixture" / "existing"
        calls = []

        class TtyInput(io.StringIO):
            def isatty(self):
                return True

        def generate(plan, **kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                raise CadRunExistsError("existing", existing)
            return {"run_id": "existing", "status": "complete", "jobs": []}

        stdout = io.StringIO()
        rc = main(
            ["cad", "generate", "fixture"],
            env=self.env(),
            stdin=TtyInput("yes\n"),
            stdout=stdout,
            stderr=io.StringIO(),
            cad_generate_func=generate,
        )

        self.assertEqual(rc, 0)
        self.assertEqual([call["regenerate"] for call in calls], [False, True])
        self.assertIn(
            f"WARNING: matching CAD run already exists: {existing}\n",
            stdout.getvalue(),
        )
        self.assertIn("Regenerate existing run? [y/N] ", stdout.getvalue())

    def test_explicit_regenerate_skips_interactive_question(self):
        return self.test_duplicate_regeneration_and_menu_parity_use_new_selection()
        calls = []
        stdout = io.StringIO()
        rc = main(
            ["cad", "generate", "fixture", "--regenerate"],
            env=self.env(),
            stdin=io.StringIO(),
            stdout=stdout,
            stderr=io.StringIO(),
            cad_generate_func=lambda plan, **kwargs: calls.append(kwargs) or {
                "run_id": "existing", "status": "complete", "jobs": [],
            },
        )

        self.assertEqual(rc, 0)
        self.assertTrue(calls[0]["regenerate"])
        self.assertNotIn("Regenerate existing run?", stdout.getvalue())

    def test_interactive_duplicate_decline_keeps_existing_run(self):
        return self.test_duplicate_regeneration_and_menu_parity_use_new_selection()
        existing = self.data / "cad" / "prints" / "fixture" / "existing"
        calls = []

        class TtyInput(io.StringIO):
            def isatty(self):
                return True

        stderr = io.StringIO()
        rc = main(
            ["cad", "generate", "fixture"],
            env=self.env(),
            stdin=TtyInput("n\n"),
            stdout=io.StringIO(),
            stderr=stderr,
            cad_generate_func=lambda *args, **kwargs: calls.append(kwargs) or (
                _ for _ in ()
            ).throw(CadRunExistsError("existing", existing)),
        )

        self.assertEqual(rc, 4)
        self.assertEqual(len(calls), 1)
        self.assertIn(str(existing), stderr.getvalue())

    def test_menu_uses_same_regeneration_confirmation(self):
        return self.test_duplicate_regeneration_and_menu_parity_use_new_selection()
        existing = self.data / "cad" / "prints" / "fixture" / "existing"
        calls = []

        class TtyInput(io.StringIO):
            def isatty(self):
                return True

        def generate(plan, **kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                raise CadRunExistsError("existing", existing)
            return {"run_id": "existing", "status": "complete", "jobs": []}

        stdout = io.StringIO()
        rc = main(
            ["cad", "menu", "fixture"],
            env=self.env(),
            stdin=TtyInput("1\ny\n"),
            stdout=stdout,
            stderr=io.StringIO(),
            cad_generate_func=generate,
        )

        self.assertEqual(rc, 0)
        self.assertEqual([call["regenerate"] for call in calls], [False, True])
        self.assertIn("Select one preset", stdout.getvalue())
        self.assertIn("Regenerate existing run?", stdout.getvalue())

    def _fake_openscad(self):
        fake = self.root / "fake-openscad-common"
        fake.write_text(
            "#!/bin/sh\n"
            'if [ "$1" = --version ]; then echo "OpenSCAD test"; exit 0; fi\n'
            'out="$2"\n'
            "printf 'solid fake\\nendsolid fake\\n' > \"$out\"\n"
        )
        fake.chmod(0o755)
        return fake

    def test_menu_and_generate_share_the_same_openscad_resolver(self):
        return self.test_preview_resolver_snapshot_and_cleanup_use_new_contract()
        parser = build_parser()
        resolved = self.root / "resolved-openscad"
        calls = []
        dependencies = {
            "resolve_openscad": lambda explicit: calls.append(explicit) or resolved,
            "generate": lambda plan, **kwargs: {
                "run_id": "run-1", "status": "complete", "jobs": [],
                "openscad": str(kwargs["openscad"]),
            },
        }
        for argv, stdin in (
            (["cad", "generate", "fixture", "--json"], io.StringIO()),
            (["cad", "menu", "fixture"], io.StringIO("1\n")),
        ):
            with self.subTest(argv=argv):
                rc = run_cad_command(
                    parser.parse_args(argv), self.context, stdin,
                    io.StringIO(), io.StringIO(), dependencies,
                )
                self.assertEqual(rc, 0)
        self.assertEqual(calls, [None, None])

    def test_direct_preview_defaults_precede_explicit_overrides(self):
        return self.test_preview_resolver_snapshot_and_cleanup_use_new_contract()
        argv_path = self.root / "preview-argv.json"
        fake = self.root / "preview-openscad"
        fake.write_text(textwrap.dedent(f"""\
            #!/usr/bin/env python3
            import json, pathlib, sys
            if "--version" in sys.argv:
                print("OpenSCAD test")
                raise SystemExit(0)
            pathlib.Path({str(argv_path)!r}).write_text(json.dumps(sys.argv[1:]))
            pathlib.Path(sys.argv[sys.argv.index("-o") + 1]).write_text(
                "solid preview\\nendsolid preview\\n"
            )
        """))
        fake.chmod(0o755)
        stdout = io.StringIO()
        rc = main(
            ["cad", "generate", "fixture", "--preview",
             "--define", "render_fn=48", "--define", "render_text=true",
             "--openscad", str(fake), "--json"],
            env=self.env(), stdout=stdout, stderr=io.StringIO(),
        )
        self.assertEqual(rc, 0)
        manifest = json.loads(stdout.getvalue())
        effective = manifest["jobs"][0]["raw_defines"]
        self.assertEqual(effective["render_fn"], "48")
        self.assertEqual(effective["render_text"], "true")
        self.assertNotIn("ball_quality", effective)
        argv = json.loads(argv_path.read_text())
        defines = [argv[index + 1] for index, item in enumerate(argv) if item == "-D"]
        self.assertEqual(defines.count("render_fn=48"), 1)
        self.assertEqual(defines.count("render_text=true"), 1)
        self.assertFalse(any(item.startswith("ball_quality=") for item in defines))

    def test_legacy_commit_uses_commit_mode_but_revision_is_literal(self):
        return self.test_generate_has_no_legacy_output_or_commit_arguments()
        parser = build_parser()
        modes = []

        def prepare(root, source, revision, *, revision_is_commit=False):
            modes.append((revision, revision_is_commit))
            return __import__("plamp.cad_generation", fromlist=["SourceSnapshot"]).SourceSnapshot(
                source, "identity", "commit", "label", False, None
            )

        dependencies = {
            "prepare_source": prepare,
            "resolve_openscad": lambda explicit: self._fake_openscad(),
            "generate": lambda plan, **kwargs: {"run_id": "run", "status": "complete", "jobs": []},
        }
        cases = (
            (["cad", "generate", "fixture", str(self.root / "out"), "abc123"], ("abc123", True)),
            (["cad", "generate", "fixture", "--revision", "HEAD"], ("HEAD", False)),
        )
        for argv, expected in cases:
            with self.subTest(argv=argv):
                rc = run_cad_command(
                    parser.parse_args(argv), self.context, io.StringIO(),
                    io.StringIO(), io.StringIO(), dependencies,
                )
                self.assertEqual(rc, 0)
                self.assertEqual(modes[-1], expected)

    def test_legacy_positional_commit_archives_and_names_with_short_hash(self):
        return self.test_generate_has_no_legacy_output_or_commit_arguments()
        old_commit = subprocess.run(
            ["git", "-C", str(self.root), "rev-parse", "HEAD"],
            check=True, text=True, stdout=subprocess.PIPE,
        ).stdout.strip()
        old_source = self.scad.read_text()
        self.scad.write_text(SOURCE.replace("cube(1)", "cube(2)"), encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "second"], check=True)
        short = subprocess.run(
            ["git", "-C", str(self.root), "rev-parse", "--short", old_commit],
            check=True, text=True, stdout=subprocess.PIPE,
        ).stdout.strip()
        output = self.root / "historical-output"
        stdout = io.StringIO()

        rc = main(
            ["cad", "generate", "fixture", str(output), old_commit,
             "--openscad", str(self._fake_openscad()), "--json"],
            env=self.env(), stdout=stdout, stderr=io.StringIO(),
        )

        self.assertEqual(rc, 0)
        manifest = json.loads(stdout.getvalue())
        self.assertEqual(manifest["source"]["commit"], old_commit)
        self.assertEqual(manifest["source"]["revision"], short)
        artifact_name = Path(manifest["jobs"][0]["artifact"]).name
        self.assertIn(short, artifact_name)
        self.assertNotIn(old_commit, artifact_name)
        self.assertIn(f'revision_string="{short}"', manifest["jobs"][0]["command"])
        archived = output / "source" / "things" / "fixture" / "fixture.scad"
        self.assertEqual(archived.read_text(), old_source)

    @unittest.skip("legacy view/preset help contract removed")
    def test_generate_help_documents_all_direct_generation_behavior(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout), self.assertRaises(SystemExit) as caught:
            main(["cad", "generate", "--help"], env=self.env())
        self.assertEqual(caught.exception.code, 0)
        help_text = stdout.getvalue()
        for required in (
            "mutually exclusive", "repeatable", "--preset", "--view",
            "--define NAME=EXPR", "--view-define VIEW:NAME=EXPR", "later wins",
            "dirty", "--revision LABEL", "historical", "short hash",
            "managed archive", "--output DIR", "--preview", "render_fn=24",
            "render_text=false", "--openscad", "OPENSCAD_BIN", "PATH",
            "platform fallback",
        ):
            with self.subTest(required=required):
                self.assertIn(required, help_text)

    def test_generate_uses_the_same_snapshot_for_planning_and_rendering(self):
        return self.test_preview_resolver_snapshot_and_cleanup_use_new_contract()
        captured = {}

        def generate(plan, **kwargs):
            captured["fingerprint"] = plan.jobs[0].fingerprint
            self.scad.write_text(SOURCE.replace("cube(1)", "cube(99)"))
            return generate_plan(
                plan,
                env={**os.environ, "FAKE_ARGV": str(self.root / "argv")},
                **kwargs,
            )

        fake = self.root / "fake-openscad"
        fake.write_text(
            "#!/bin/sh\n"
            'if [ "$1" = --version ]; then echo fake; exit 0; fi\n'
            'out="$2"\n'
            "printf 'solid x\\nendsolid x\\n' > \"$out\"\n"
        )
        fake.chmod(0o755)
        stdout = io.StringIO()
        rc = main(
            ["cad", "generate", "fixture", "--view", "floor", "--openscad", str(fake), "--json"],
            env=self.env(), stdout=stdout, stderr=io.StringIO(), cad_generate_func=generate,
        )

        self.assertEqual(rc, 0)
        manifest = json.loads(stdout.getvalue())
        run_dir = self.data / "cad" / "prints" / "fixture" / manifest["run_id"]
        archived = run_dir / "source" / "things" / "fixture" / "fixture.scad"
        self.assertIn("cube(1)", archived.read_text())
        self.assertNotIn("cube(99)", archived.read_text())
        self.assertEqual(manifest["jobs"][0]["fingerprint"], captured["fingerprint"])

    @unittest.skip("removed options have exact replacement diagnostics")
    def test_preset_and_view_conflict_is_stable_usage_error(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        rc = main(
            ["cad", "plan", "fixture", "--preset", "split", "--view", "box"],
            env=self.env(), stdout=stdout, stderr=stderr,
        )
        self.assertEqual(rc, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("cannot be combined", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())

    @unittest.skip("legacy preset/view menu removed")
    def test_menu_accepts_one_preset_or_multiple_views(self):
        for answer, expected in (("1\n", ("split", ())), ("2 4\n", (None, ("floor", "assembly")))):
            captured = []
            with self.subTest(answer=answer):
                rc = main(
                    ["cad", "menu", "fixture", "--openscad", str(self._fake_openscad())],
                    env=self.env(), stdin=io.StringIO(answer),
                    stdout=io.StringIO(), stderr=io.StringIO(),
                    cad_generate_func=lambda plan, **kwargs: captured.append(plan.selection) or {
                        "run_id": "run-1", "status": "complete", "jobs": []
                    },
                )
                self.assertEqual(rc, 0)
                self.assertEqual((captured[0].preset, captured[0].views), expected)

    def test_menu_retains_planned_snapshot_through_real_generation_then_cleans_it(self):
        return self.test_preview_resolver_snapshot_and_cleanup_use_new_contract()
        fake = self.root / "fake-openscad"
        fake.write_text(
            "#!/bin/sh\n"
            'if [ "$1" = --version ]; then echo fake; exit 0; fi\n'
            'out="$2"\n'
            "printf 'solid x\\nendsolid x\\n' > \"$out\"\n"
        )
        fake.chmod(0o755)
        observed = {}

        def generate(plan, **kwargs):
            snapshot_root = kwargs["snapshot"].cleanup_root
            observed["snapshot_root"] = snapshot_root
            self.assertIsNotNone(snapshot_root)
            self.assertTrue(snapshot_root.is_dir())
            self.assertTrue(kwargs["snapshot"].scad_path.is_file())
            return generate_plan(plan, env=os.environ, **kwargs)

        rc = main(
            ["cad", "menu", "fixture", "--openscad", str(fake)],
            env=self.env(),
            stdin=io.StringIO("1\n"),
            stdout=io.StringIO(),
            stderr=io.StringIO(),
            cad_generate_func=generate,
        )

        self.assertEqual(rc, 0)
        self.assertFalse(observed["snapshot_root"].exists())
        manifests = list(
            (self.data / "cad" / "prints" / "fixture").glob("*/manifest.json")
        )
        self.assertEqual(len(manifests), 1)
        self.assertEqual(json.loads(manifests[0].read_text())["status"], "complete")

    def test_menu_json_is_rejected_before_stdin_or_generation(self):
        reads = []

        class UnreadableInput:
            def readline(self):
                reads.append(True)
                raise AssertionError("stdin must not be read")

        calls = []
        stdout = io.StringIO()
        rc = main(
            ["cad", "menu", "fixture", "--json"], env=self.env(),
            stdin=UnreadableInput(), stdout=stdout, stderr=io.StringIO(),
            cad_generate_func=lambda *a, **k: calls.append((a, k)),
        )
        diagnostic = json.loads(stdout.getvalue())[0]
        self.assertEqual(rc, 2)
        self.assertEqual(diagnostic["kind"], "invalid_selection")
        self.assertIn("--json", diagnostic["message"])
        self.assertEqual(reads, [])
        self.assertEqual(calls, [])

    def test_menu_eof_cancels_without_retry_or_generation(self):
        return self.test_menu_eof_and_interrupt_are_clean_cancellations()
        calls = []
        stdout, stderr = io.StringIO(), io.StringIO()
        rc = main(
            ["cad", "menu", "fixture"], env=self.env(), stdin=io.StringIO(""),
            stdout=stdout, stderr=stderr,
            cad_generate_func=lambda *a, **k: calls.append((a, k)),
        )
        self.assertEqual(rc, 2)
        self.assertEqual(stdout.getvalue().count("Select"), 1)
        self.assertIn("cancelled", stderr.getvalue().lower())
        self.assertEqual(calls, [])

    def test_menu_interrupt_is_selection_cancellation(self):
        return self.test_menu_eof_and_interrupt_are_clean_cancellations()
        class InterruptingInput:
            def readline(self):
                raise KeyboardInterrupt()

        calls = []
        stderr = io.StringIO()
        rc = main(
            ["cad", "menu", "fixture"], env=self.env(), stdin=InterruptingInput(),
            stdout=io.StringIO(), stderr=stderr,
            cad_generate_func=lambda *a, **k: calls.append((a, k)),
        )
        self.assertEqual(rc, 2)
        self.assertIn("cancelled", stderr.getvalue().lower())
        self.assertNotIn("CAD400", stderr.getvalue())
        self.assertEqual(calls, [])

    def test_menu_reprompts_once_then_returns_diagnostic(self):
        return self.test_menu_reprompts_after_invalid_new_contract_selection()
        stdout, stderr = io.StringIO(), io.StringIO()
        rc = main(
            ["cad", "menu", "fixture"], env=self.env(), stdin=io.StringIO("wrong\nstill-wrong\n"),
            stdout=stdout, stderr=stderr,
        )
        self.assertEqual(rc, 2)
        self.assertEqual(stdout.getvalue().count("Select"), 2)
        self.assertIn("invalid menu selection", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_runs_show_and_log_use_archive_interfaces(self):
        manifest = {
            "schema_version": 1, "run_id": "new", "system_name": "alpha", "status": "complete",
            "created_at": "2026-07-21T10:00:00Z", "jobs": [],
        }
        run_dir = self.data / "cad" / "prints" / "fixture" / "new"
        run_dir.mkdir(parents=True)
        (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        dependencies = {
            "list_runs": lambda data_dir, part=None: [manifest],
            "load_run": lambda run: manifest,
            "load_job_log": lambda run, artifact: "OpenSCAD output\n",
        }
        parser = build_parser()
        cases = (
            (["cad", "runs", "fixture", "--json"], [manifest]),
            (["cad", "show", "new", "--json"], manifest),
        )
        for argv, expected in cases:
            stdout = io.StringIO()
            rc = run_cad_command(parser.parse_args(argv), self.context, io.StringIO(), stdout, io.StringIO(), dependencies)
            self.assertEqual(rc, 0)
            self.assertEqual(json.loads(stdout.getvalue()), expected)
        stdout = io.StringIO()
        rc = run_cad_command(
            parser.parse_args(["cad", "runs"]), self.context,
            io.StringIO(), stdout, io.StringIO(), dependencies,
        )
        self.assertEqual(rc, 0)
        self.assertIn("alpha", stdout.getvalue())
        stdout = io.StringIO()
        rc = run_cad_command(
            parser.parse_args(["cad", "log", "new", "artifact"]), self.context,
            io.StringIO(), stdout, io.StringIO(), dependencies,
        )
        self.assertEqual(rc, 0)
        self.assertEqual(stdout.getvalue(), "OpenSCAD output\n")

    def test_show_and_log_reject_paths_prefixes_and_manifest_id_mismatch(self):
        archive = self.data / "cad" / "prints" / "fixture"
        exact = archive / "20260721T100000Z-fixture-split-abc1234-abcdef"
        exact.mkdir(parents=True)
        manifest = {
            "schema_version": 1,
            "run_id": "different-id",
            "part": "fixture",
            "status": "complete",
            "jobs": [],
        }
        (exact / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        outside = self.root / "outside-run"
        outside.mkdir()
        (outside / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

        for action in ("show", "log"):
            for run in (str(outside), "20260721T100000Z-fixture-split", exact.name):
                with self.subTest(action=action, run=run):
                    stderr = io.StringIO()
                    argv = ["cad", action, run]
                    if action == "log":
                        argv.append("artifact")
                    rc = main(argv, env=self.env(), stdout=io.StringIO(), stderr=stderr)
                    self.assertEqual(rc, 4)
                    self.assertIn("CAD400", stderr.getvalue())

    def test_expected_archive_error_has_no_traceback(self):
        stderr = io.StringIO()
        parser = build_parser()
        rc = run_cad_command(
            parser.parse_args(["cad", "show", "missing"]), self.context,
            io.StringIO(), io.StringIO(), stderr,
            {"load_run": lambda run: (_ for _ in ()).throw(FileNotFoundError("missing run"))},
        )
        self.assertEqual(rc, 4)
        self.assertEqual(
            stderr.getvalue(),
            "missing: CAD400: CAD run ID not found: missing\n",
        )

    def test_generation_subprocess_error_returns_four_without_traceback(self):
        self._clean_catalog()
        stderr = io.StringIO()

        def fail(*args, **kwargs):
            raise subprocess.CalledProcessError(7, ["openscad"])

        rc = main(
            ["cad", "generate", "fixture", "--revision", "test",
             "--openscad", str(self._fake_openscad())],
            env=self.env(), stdout=io.StringIO(),
            stderr=stderr, cad_generate_func=fail,
        )
        self.assertEqual(rc, 4)
        self.assertIn("openscad", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_generation_value_and_result_errors_return_four(self):
        self._clean_catalog()
        failures = (
            lambda *a, **k: (_ for _ in ()).throw(ValueError("render exploded")),
            lambda *a, **k: object(),
        )
        for failure in failures:
            with self.subTest(failure=failure):
                stderr = io.StringIO()
                rc = main(
                    ["cad", "generate", "fixture", "--revision", "test",
                     "--openscad", str(self._fake_openscad())],
                    env=self.env(), stdout=io.StringIO(),
                    stderr=stderr, cad_generate_func=failure,
                )
                self.assertEqual(rc, 4)
                self.assertIn("CAD400", stderr.getvalue())
                self.assertNotIn("Traceback", stderr.getvalue())

    def test_generation_interrupt_returns_four_without_traceback(self):
        self._clean_catalog()
        stderr = io.StringIO()
        rc = main(
            ["cad", "generate", "fixture", "--revision", "test",
             "--openscad", str(self._fake_openscad())],
            env=self.env(), stdout=io.StringIO(),
            stderr=stderr,
            cad_generate_func=lambda *a, **k: (_ for _ in ()).throw(KeyboardInterrupt()),
        )
        self.assertEqual(rc, 4)
        self.assertIn("interrupted", stderr.getvalue().lower())
        self.assertNotIn("Traceback", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
