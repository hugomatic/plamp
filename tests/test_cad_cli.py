import contextlib
import io
import json
import os
import subprocess
import tempfile
import textwrap
import unittest
from argparse import Namespace
from pathlib import Path

from plamp.cad_cli import add_cad_parser, run_cad_command
from plamp.cad_generation import generate_plan
from plamp.cad_scaffold import CadTemplate, CreatedPart
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
        for command in ("new", "views", "validate", "plan", "menu", "generate", "runs", "show", "log"):
            self.assertIn(command, stdout.getvalue())

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

    def test_views_resolves_part_name_and_path_and_keeps_assembly_last(self):
        for part in ("fixture", "things/fixture/fixture.scad"):
            with self.subTest(part=part):
                stdout = io.StringIO()
                rc = main(["cad", "views", part, "--json"], env=self.env(), stdout=stdout, stderr=io.StringIO())
                result = json.loads(stdout.getvalue())
                self.assertEqual(rc, 0)
                self.assertEqual([item["name"] for item in result["views"]], ["floor", "box", "assembly"])
                self.assertEqual(result["views"][0]["description"], "Printable floor")

    def test_invalid_metadata_prints_json_diagnostics_without_traceback(self):
        self.scad.write_text('view = "box"; // [box]\n/* generate.json\n{\n*/\n')
        stdout, stderr = io.StringIO(), io.StringIO()
        rc = main(["cad", "validate", "fixture", "--json"], env=self.env(), stdout=stdout, stderr=stderr)
        diagnostics = json.loads(stdout.getvalue())
        self.assertEqual(rc, 2)
        self.assertEqual(diagnostics[0]["code"], "CAD100")
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_validate_does_not_call_openscad(self):
        calls = []
        stdout = io.StringIO()
        rc = main(
            ["cad", "validate", "fixture", "--json"], env=self.env(), stdout=stdout,
            stderr=io.StringIO(), cad_generate_func=lambda *a, **k: calls.append((a, k)),
        )
        self.assertEqual(rc, 0)
        self.assertEqual(calls, [])
        self.assertTrue(json.loads(stdout.getvalue())["valid"])

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
        self.scad.write_text(SOURCE + "// authoring change\n", encoding="utf-8")
        stdout = io.StringIO()
        rc = main(
            ["cad", "plan", "fixture", "--json"], env=self.env(), stdout=stdout,
            stderr=io.StringIO(),
        )
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(stdout.getvalue())["job_count"], 2)

    def test_repeatable_views_and_raw_defines_reach_generation(self):
        captured = []

        def generate(plan, **kwargs):
            captured.append((plan, kwargs))
            return {"run_id": "run-1", "status": "complete", "jobs": []}

        rc = main(
            ["cad", "generate", "fixture", "--view", "assembly", "--view", "box",
             "--define", "quality=$preview ? 2 : 20", "--view-define", "box:fit=0.2", "--json"],
            env=self.env(), stdout=io.StringIO(), stderr=io.StringIO(), cad_generate_func=generate,
        )
        self.assertEqual(rc, 0)
        selection = captured[0][0].selection
        self.assertEqual(selection.views, ("assembly", "box"))
        self.assertEqual(selection.raw_defines, ("quality=$preview ? 2 : 20",))
        self.assertEqual(selection.raw_view_defines["box"], ("fit=0.2",))

    def test_generate_uses_the_same_snapshot_for_planning_and_rendering(self):
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

    def test_menu_accepts_one_preset_or_multiple_views(self):
        for answer, expected in (("1\n", ("split", ())), ("2 4\n", (None, ("floor", "assembly")))):
            captured = []
            with self.subTest(answer=answer):
                rc = main(
                    ["cad", "menu", "fixture"], env=self.env(), stdin=io.StringIO(answer),
                    stdout=io.StringIO(), stderr=io.StringIO(),
                    cad_generate_func=lambda plan, **kwargs: captured.append(plan.selection) or {
                        "run_id": "run-1", "status": "complete", "jobs": []
                    },
                )
                self.assertEqual(rc, 0)
                self.assertEqual((captured[0].preset, captured[0].views), expected)

    def test_menu_retains_planned_snapshot_through_real_generation_then_cleans_it(self):
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
            "schema_version": 1, "run_id": "new", "part": "fixture", "status": "complete",
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
        stderr = io.StringIO()

        def fail(*args, **kwargs):
            raise subprocess.CalledProcessError(7, ["openscad"])

        rc = main(
            ["cad", "generate", "fixture"], env=self.env(), stdout=io.StringIO(),
            stderr=stderr, cad_generate_func=fail,
        )
        self.assertEqual(rc, 4)
        self.assertIn("openscad", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_generation_value_and_result_errors_return_four(self):
        failures = (
            lambda *a, **k: (_ for _ in ()).throw(ValueError("render exploded")),
            lambda *a, **k: object(),
        )
        for failure in failures:
            with self.subTest(failure=failure):
                stderr = io.StringIO()
                rc = main(
                    ["cad", "generate", "fixture"], env=self.env(), stdout=io.StringIO(),
                    stderr=stderr, cad_generate_func=failure,
                )
                self.assertEqual(rc, 4)
                self.assertIn("CAD400", stderr.getvalue())
                self.assertNotIn("Traceback", stderr.getvalue())

    def test_generation_interrupt_returns_four_without_traceback(self):
        stderr = io.StringIO()
        rc = main(
            ["cad", "generate", "fixture"], env=self.env(), stdout=io.StringIO(),
            stderr=stderr,
            cad_generate_func=lambda *a, **k: (_ for _ in ()).throw(KeyboardInterrupt()),
        )
        self.assertEqual(rc, 4)
        self.assertIn("interrupted", stderr.getvalue().lower())
        self.assertNotIn("Traceback", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
