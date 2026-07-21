import io
import json
import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

from plamp.cad_generation import (
    generate_plan,
    list_runs,
    load_job_log,
    load_run,
    prepare_source,
    resolve_part,
)
from plamp.cad_recipes import RenderJob, RenderPlan, Selection


JOB_FIELDS = {
    "artifact_id", "fingerprint", "view", "variant_name", "preset_paths",
    "variables", "raw_defines", "status", "queued_at", "started_at",
    "finished_at", "elapsed_seconds", "command", "artifact",
    "artifact_bytes", "log", "exit_code", "echoes", "messages", "warnings",
    "errors", "geometry",
}


def plan(*views):
    jobs = tuple(
        RenderJob(
            artifact_id=f"{view}--{'a' * 11}{index}",
            fingerprint=f"{'a' * 63}{index}",
            view=view,
            variant_name=view,
            variables={"count": index, "label": "a b", "enabled": True},
            raw_defines={"quality": "$preview ? 2 : 20"},
            preset_paths=(("print",),),
        )
        for index, view in enumerate(views, 1)
    )
    return RenderPlan(Selection(preset="print"), jobs, ())


class CadGenerationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.data = self.root / "data"
        part_dir = self.repo / "things" / "fixture"
        part_dir.mkdir(parents=True)
        self.scad = part_dir / "fixture.scad"
        self.scad.write_text("cube(1);\n")
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.name", "Test"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.email", "test@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-qm", "fixture"], check=True)
        self.commit = subprocess.run(
            ["git", "-C", str(self.repo), "rev-parse", "HEAD"],
            check=True, text=True, stdout=subprocess.PIPE,
        ).stdout.strip()
        self.fake = self.root / "fake-openscad"
        self.fake.write_text(textwrap.dedent("""\
            #!/usr/bin/env python3
            import json, os, pathlib, sys
            if "--version" in sys.argv:
                print("OpenSCAD version 2099.01")
                raise SystemExit(0)
            pathlib.Path(os.environ["FAKE_ARGV"]).write_text(json.dumps(sys.argv[1:]))
            output = pathlib.Path(sys.argv[sys.argv.index("-o") + 1])
            state_log = os.environ.get("FAKE_STATE_LOG")
            if state_log:
                manifest = json.loads((output.parent.parent / "manifest.json").read_text())
                with pathlib.Path(state_log).open("a") as stream:
                    stream.write(json.dumps([manifest["status"], [job["status"] for job in manifest["jobs"]]]) + "\\n")
            defines = [sys.argv[i + 1] for i, arg in enumerate(sys.argv) if arg == "-D"]
            view = next((item.split("=", 1)[1].strip('"') for item in defines if item.startswith("view=")), "default")
            print('ECHO: "ordinary"')
            print(os.environ.get("FAKE_ECHO", 'ECHO: ["PLAMP", "measure", ["width", 12, "mm"]]'))
            print("WARNING: harmless warning")
            print("Total rendering time: 0:00:01.250")
            print("   Top level object is a 3D object:")
            print("   Simple: yes")
            print("   Vertices: 8")
            print("   Facets: 12")
            print("   Volumes: 2")
            if os.environ.get("FAKE_FAIL_VIEW") == view:
                print("ERROR: requested failure")
                raise SystemExit(7)
            if not os.environ.get("FAKE_EMPTY"):
                output.write_text("solid fixture\\nendsolid fixture\\n")
        """))
        self.fake.chmod(0o755)
        self.argv_file = self.root / "argv.json"

    def tearDown(self):
        self.temp.cleanup()

    def env(self, **values):
        return {**os.environ, "FAKE_ARGV": str(self.argv_file), **values}

    def generate(self, source_plan=None, **kwargs):
        return generate_plan(
            source_plan or plan("first"), repo_root=self.repo,
            data_dir=self.data, scad_path=self.scad, openscad=self.fake,
            env=self.env(), stdout=io.StringIO(), **kwargs,
        )

    def test_resolve_part_accepts_part_name_and_repository_path(self):
        self.assertEqual(resolve_part("fixture", self.repo), self.scad)
        self.assertEqual(resolve_part("things/fixture/fixture.scad", self.repo), self.scad)

    def test_clean_source_is_archived_and_ignores_later_unrelated_dirt(self):
        unrelated = self.repo / "notes.txt"
        unrelated.write_text("dirty")
        snapshot = prepare_source(self.repo, self.scad)
        self.addCleanup(lambda: snapshot.cleanup_root and __import__("shutil").rmtree(snapshot.cleanup_root))
        self.scad.write_text("cube(99);\n")
        self.assertEqual(snapshot.scad_path.read_text(), "cube(1);\n")
        self.assertEqual(snapshot.full_commit, self.commit)
        self.assertFalse(snapshot.dirty)
        self.assertEqual(snapshot.revision_label, self.commit[:7])

    def test_dirty_part_requires_an_honest_revision(self):
        self.scad.write_text("cube(2);\n")
        with self.assertRaisesRegex(ValueError, "dirty.*revision"):
            prepare_source(self.repo, self.scad)
        snapshot = prepare_source(self.repo, self.scad, revision="fit-test")
        self.assertTrue(snapshot.dirty)
        self.assertIsNone(snapshot.full_commit)
        self.assertEqual(snapshot.revision_label, "fit-test")
        self.assertEqual(snapshot.scad_path, self.scad)

    def test_dirty_generation_records_revision_and_archives_working_source(self):
        self.scad.write_text("cube(2);\n")
        result = self.generate(revision="fit-test")
        manifest = load_run(result.run_dir)
        self.assertTrue(manifest["source"]["dirty"])
        self.assertIsNone(manifest["source"]["commit"])
        self.assertEqual(manifest["source"]["revision"], "fit-test")
        archived = result.run_dir / "source" / "things" / "fixture" / "fixture.scad"
        self.assertEqual(archived.read_text(), "cube(2);\n")

    def test_default_and_explicit_output_locations(self):
        result = self.generate()
        self.assertEqual(result.run_dir.parent, self.data / "cad" / "prints" / "fixture")
        explicit = self.root / "chosen-run"
        result = self.generate(output=explicit)
        self.assertEqual(result.run_dir, explicit)

    def test_manifest_schema_and_job_schema_are_frozen(self):
        result = self.generate(metadata={"z": 1})
        manifest = load_run(result.run_dir)
        self.assertEqual(set(manifest), {
            "schema_version", "generator_version", "run_id", "part", "status",
            "created_at", "updated_at", "started_at", "finished_at", "source",
            "selection", "metadata", "preset_tree", "openscad_version", "jobs",
        })
        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(manifest["generator_version"], 1)
        self.assertEqual(set(manifest["jobs"][0]), JOB_FIELDS)
        self.assertEqual(set(manifest["jobs"][0]["geometry"]), {
            "render_seconds", "simple", "vertices", "facets", "volumes",
        })
        self.assertEqual(manifest["metadata"], {"z": 1})
        self.assertEqual(manifest["source"]["commit"], self.commit)
        self.assertRegex(manifest["created_at"], r"Z$")

    def test_exact_argv_uses_argument_list_and_effective_plan_values(self):
        result = self.generate()
        manifest = load_run(result.run_dir)
        command = manifest["jobs"][0]["command"]
        self.assertEqual(command[0], str(self.fake))
        self.assertEqual(command[1], "-o")
        self.assertEqual(command[-1], str(result.run_dir / "source" / "things" / "fixture" / "fixture.scad"))
        defines = [command[index + 1] for index, item in enumerate(command) if item == "-D"]
        self.assertEqual(defines, [
            f'revision_string="{self.commit[:7]}"', 'view="first"', "count=1",
            'label="a b"', "enabled=true", "quality=$preview ? 2 : 20",
        ])
        self.assertEqual(json.loads(self.argv_file.read_text()), command[1:])

    def test_output_is_streamed_logged_and_statistics_are_extracted(self):
        stream = io.StringIO()
        result = generate_plan(
            plan("first"), repo_root=self.repo, data_dir=self.data,
            scad_path=self.scad, openscad=self.fake, env=self.env(), stdout=stream,
        )
        job = load_run(result.run_dir)["jobs"][0]
        self.assertIn('ECHO: "ordinary"', stream.getvalue())
        self.assertEqual(job["echoes"], ['"ordinary"', '["PLAMP", "measure", ["width", 12, "mm"]]'])
        self.assertEqual(job["messages"], [{"channel": "measure", "payload": ["width", 12, "mm"]}])
        self.assertEqual(job["warnings"], ["WARNING: harmless warning"])
        self.assertEqual(job["geometry"], {
            "render_seconds": 1.25, "simple": True, "vertices": 8,
            "facets": 12, "volumes": 2,
        })
        self.assertIn("Total rendering time", load_job_log(result.run_dir, job["artifact_id"]))

    def test_cad_messages_are_data_and_never_executed(self):
        marker = self.root / "must-not-exist"
        result = generate_plan(
            plan("first"), repo_root=self.repo, data_dir=self.data,
            scad_path=self.scad, openscad=self.fake,
            env=self.env(FAKE_ECHO=f'ECHO: ["PLAMP", "robot", ["touch", "{marker}"]]'),
            stdout=io.StringIO(),
        )
        message = load_run(result.run_dir)["jobs"][0]["messages"][0]
        self.assertEqual(message["channel"], "robot")
        self.assertFalse(marker.exists())

    def test_later_failure_keeps_completed_artifact_and_all_logs(self):
        result = generate_plan(
            plan("first", "second"), repo_root=self.repo, data_dir=self.data,
            scad_path=self.scad, openscad=self.fake,
            env=self.env(FAKE_FAIL_VIEW="second"), stdout=io.StringIO(),
        )
        manifest = load_run(result.run_dir)
        self.assertEqual(result.status, "failed")
        self.assertEqual([job["status"] for job in manifest["jobs"]], ["complete", "failed"])
        self.assertTrue((result.run_dir / manifest["jobs"][0]["artifact"]).is_file())
        self.assertIsNone(manifest["jobs"][1]["artifact"])
        self.assertTrue((result.run_dir / manifest["jobs"][1]["log"]).is_file())
        self.assertIn("requested failure", manifest["jobs"][1]["errors"][-1])

    def test_manifest_is_valid_and_running_before_each_openscad_process(self):
        state_log = self.root / "states.jsonl"
        result = generate_plan(
            plan("first", "second"), repo_root=self.repo, data_dir=self.data,
            scad_path=self.scad, openscad=self.fake,
            env=self.env(FAKE_STATE_LOG=str(state_log)), stdout=io.StringIO(),
        )
        states = [json.loads(line) for line in state_log.read_text().splitlines()]
        self.assertEqual(states, [
            ["running", ["running", "queued"]],
            ["running", ["complete", "running"]],
        ])
        self.assertFalse(list(result.run_dir.glob(".manifest.json.*")))

    def test_empty_output_is_failure_and_never_publishes_artifact(self):
        result = generate_plan(
            plan("first"), repo_root=self.repo, data_dir=self.data,
            scad_path=self.scad, openscad=self.fake,
            env=self.env(FAKE_EMPTY="1"), stdout=io.StringIO(),
        )
        job = load_run(result.run_dir)["jobs"][0]
        self.assertEqual(job["status"], "failed")
        self.assertIsNone(job["artifact"])
        self.assertIn("non-empty output", job["errors"][-1])

    def test_catalog_is_newest_first_and_log_uses_exact_artifact_id(self):
        older = self.generate(output=self.data / "cad" / "prints" / "fixture" / "20260101T000000Z-old")
        newer = self.generate(output=self.data / "cad" / "prints" / "fixture" / "20260102T000000Z-new")
        self.assertEqual([item["run_id"] for item in list_runs(self.data, "fixture")], [newer.run_dir.name, older.run_dir.name])
        with self.assertRaisesRegex(KeyError, "missing"):
            load_job_log(newer.run_dir, "missing")


if __name__ == "__main__":
    unittest.main()
