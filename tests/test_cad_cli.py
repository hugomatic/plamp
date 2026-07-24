import contextlib
import errno
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from plamp.cad_cli import add_cad_parser, run_cad_command
from plamp.cad_generation import CadRunExistsError, generate_plan
from plamp.cad_scaffold import (
    CadDestinationExistsError,
    CadSelectionError,
    CadTemplate,
    CreatedModel,
)
from plamp.cli import build_parser, main
from plamp.context import RuntimeContext


SOURCE = 'set = ""; // [floor, assembly]\ncube(1);\n'


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
        (self.root / "cad" / "profiles" / "petg.json").write_text(json.dumps({
            "schema": "plamp-cad-profile/1", "name": "petg",
            "kind": "material", "cad": {}, "slicing": {}, "machine": {},
        }) + "\n")
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

    def test_templates_lists_descriptions_and_both_files(self):
        parser = build_parser()
        root = self.context.root
        template = CadTemplate(
            "cad", root / "things/3d_template/cad.scad",
            root / "things/3d_template/cad.cad.json", "General model",
        )
        stdout = io.StringIO()
        rc = run_cad_command(
            parser.parse_args(["cad", "templates", "--json"]), self.context,
            io.StringIO(), stdout, io.StringIO(),
            {"discover_templates": lambda _root: (template,)},
        )
        self.assertEqual(rc, 0)
        row = json.loads(stdout.getvalue())[0]
        self.assertEqual(row["description"], "General model")
        self.assertEqual(row["files"], [
            "things/3d_template/cad.scad", "things/3d_template/cad.cad.json",
        ])

    def test_new_uses_noninteractive_default_and_explicit_template(self):
        self._clean_catalog()
        parser = build_parser(); calls = []
        def create(root, system, model, template):
            calls.append((root, system.name, model, template))
            directory = root / "things" / model
            return CreatedModel(model, template, directory,
                                directory / f"{model}.scad",
                                directory / f"{model}.cad.json")
        for argv, expected in (
            (["cad", "new", "pump", "--system", "alpha", "--json"], "cad"),
            (["cad", "new", "plate", "--system", "alpha", "--template", "flat_plate", "--json"], "flat_plate"),
        ):
            stdout = io.StringIO()
            rc = run_cad_command(parser.parse_args(argv), self.context,
                                 io.StringIO(), stdout, io.StringIO(),
                                 {"create_model": create})
            self.assertEqual(rc, 0)
            value = json.loads(stdout.getvalue())
            self.assertEqual((value["system"], value["template"]), ("alpha", expected))
            self.assertIn("sidecar_path", value)
        self.assertEqual(tuple(call[3] for call in calls), ("cad", "flat_plate"))

    def test_new_interactive_menu_selects_described_template(self):
        self._clean_catalog()
        parser = build_parser(); root = self.root
        templates = (
            CadTemplate("cad", root / "cad.scad", root / "cad.cad.json", "General"),
            CadTemplate("flat_plate", root / "flat.scad", root / "flat.cad.json", "Flat plate"),
        )
        created = CreatedModel("pump", "flat_plate", root / "things/pump",
                               root / "things/pump/pump.scad",
                               root / "things/pump/pump.cad.json")
        stdin = io.StringIO("2\n"); stdin.isatty = lambda: True
        stdout = io.StringIO(); calls = []
        rc = run_cad_command(
            parser.parse_args(["cad", "new", "pump", "--system", "alpha"]),
            self.context, stdin, stdout, io.StringIO(), {
                "discover_templates": lambda _root: templates,
                "create_model": lambda *args: calls.append(args) or created,
            })
        self.assertEqual(rc, 0)
        self.assertIn("2. flat_plate - Flat plate", stdout.getvalue())
        self.assertEqual(calls[0][-1], "flat_plate")
        self.assertIn("plamp cad sets pump --system alpha", stdout.getvalue())

    def test_new_requires_model_and_removed_list_option_is_rejected(self):
        output, _error, rc = self._run_main(["cad", "new", "--json"])
        self.assertEqual(rc, 2)
        self.assertIn("requires MODEL", json.loads(output)[0]["message"])
        with self.assertRaises(SystemExit):
            build_parser().parse_args(["cad", "new", "--list-templates"])

    def test_new_selection_and_operational_failures_are_structured(self):
        self._clean_catalog(); parser = build_parser()
        for error, expected in (
            (CadSelectionError("bad template"), (2, "CAD200")),
            (CadDestinationExistsError("exists"), (2, "CAD200")),
            (OSError(errno.ENOSPC, "full"), (4, "CAD400")),
        ):
            stdout, stderr = io.StringIO(), io.StringIO()
            rc = run_cad_command(
                parser.parse_args(["cad", "new", "pump", "--system", "alpha", "--json"]),
                self.context, io.StringIO(), stdout, stderr,
                {"create_model": lambda *args, error=error: (_ for _ in ()).throw(error)},
            )
            self.assertEqual(rc, expected[0])
            self.assertEqual(json.loads(stdout.getvalue())[0]["code"], expected[1])
            self.assertNotIn("Traceback", stderr.getvalue())

    def test_generated_hyphenated_model_is_immediately_navigable_and_plannable(self):
        self._clean_catalog()
        repository = Path(__file__).resolve().parents[1]
        shutil.copytree(
            repository / "things" / "3d_template",
            self.root / "things" / "3d_template",
        )
        openscad_calls = []

        created_output = io.StringIO()
        self.assertEqual(
            main(
                ["cad", "new", "pump-bracket", "--system", "alpha", "--json"],
                env=self.env(),
                stdout=created_output,
                stderr=io.StringIO(),
                cad_generate_func=lambda *args, **kwargs: openscad_calls.append((args, kwargs)),
            ),
            0,
        )
        self.assertEqual(json.loads(created_output.getvalue())["model"], "pump-bracket")

        outputs = {}
        commands = {
            "sets": ["cad", "sets", "pump-bracket", "--system", "alpha", "--json"],
            "validate": ["cad", "validate", "pump-bracket", "--system", "alpha", "--json"],
            "plan": ["cad", "plan", "pump-bracket", "--system", "alpha", "--all-sets", "--json"],
        }
        for action, command in commands.items():
            stream = io.StringIO()
            self.assertEqual(
                main(
                    command,
                    env=self.env(),
                    stdout=stream,
                    stderr=io.StringIO(),
                    cad_generate_func=lambda *args, **kwargs: openscad_calls.append((args, kwargs)),
                ),
                0,
            )
            outputs[action] = json.loads(stream.getvalue())

        self.assertEqual(
            [item["id"] for item in outputs["sets"]],
            ["pump_bracket", "assembly"],
        )
        self.assertTrue(outputs["validate"]["valid"])
        self.assertEqual(outputs["plan"]["job_count"], 2)
        self.assertEqual(
            [job["set_name"] for job in outputs["plan"]["jobs"]],
            ["pump_bracket", "assembly"],
        )
        self.assertEqual(openscad_calls, [])

    def test_invalid_sidecar_metadata_prints_json_diagnostics_without_traceback(self):
        self._clean_catalog()
        self.scad.with_suffix(".cad.json").write_text("{", encoding="utf-8")
        stdout, stderr = io.StringIO(), io.StringIO()
        rc = main(["cad", "validate", "fixture", "--system", "alpha", "--json"], env=self.env(), stdout=stdout, stderr=stderr)
        diagnostics = json.loads(stdout.getvalue())
        self.assertEqual(rc, 2)
        self.assertEqual(diagnostics[0]["code"], "CAD100")
        self.assertNotIn("Traceback", stderr.getvalue())




    def test_generate_and_menu_accept_regenerate_switch(self):
        parser = build_parser()
        for argv in (
            ["cad", "generate", "fixture", "--regenerate"],
            ["cad", "menu", "fixture", "--regenerate"],
        ):
            with self.subTest(argv=argv):
                self.assertTrue(parser.parse_args(argv).regenerate)












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
