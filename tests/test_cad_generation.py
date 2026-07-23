import io
import json
import os
import subprocess
import tempfile
import textwrap
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from plamp.cad_generation import (
    CadRunExistsError,
    generate_plan,
    list_runs,
    load_job_log,
    load_run,
    prepare_source,
    resolve_openscad,
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


def distinct_plan(view):
    source_plan = plan(view)
    job = replace(
        source_plan.jobs[0],
        artifact_id=f"{view}--{'b' * 12}",
        fingerprint="b" * 64,
    )
    return RenderPlan(source_plan.selection, (job,), source_plan.preset_tree)


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

    def test_resolve_openscad_honors_strict_override_precedence(self):
        explicit = self.root / "explicit"
        env_bin = self.root / "env-bin"
        path_bin = self.root / "path-bin"
        for executable in (explicit, env_bin, path_bin):
            executable.write_text("#!/bin/sh\n")
            executable.chmod(0o755)
        which = lambda name: {"named": str(explicit), "openscad": str(path_bin)}.get(name)

        self.assertEqual(
            resolve_openscad(str(explicit), env={"OPENSCAD_BIN": str(env_bin)},
                             system="Linux", which=which, home=self.root),
            explicit,
        )
        self.assertEqual(
            resolve_openscad("named", env={"OPENSCAD_BIN": str(env_bin)},
                             system="Linux", which=which, home=self.root),
            explicit,
        )
        self.assertEqual(
            resolve_openscad(None, env={"OPENSCAD_BIN": str(env_bin)},
                             system="Linux", which=which, home=self.root),
            env_bin,
        )
        self.assertEqual(
            resolve_openscad(None, env={}, system="Linux", which=which, home=self.root),
            path_bin,
        )

    def test_resolve_openscad_invalid_override_fails_without_fallback(self):
        fallback = self.root / "fallback"
        fallback.write_text("#!/bin/sh\n")
        fallback.chmod(0o755)
        which = lambda _name: str(fallback)
        for explicit, env, expected in (
            (str(self.root / "missing"), {}, "--openscad"),
            ("missing-command", {}, "--openscad"),
            (None, {"OPENSCAD_BIN": str(self.root / "missing")}, "OPENSCAD_BIN"),
        ):
            with self.subTest(explicit=explicit, env=env), self.assertRaisesRegex(
                FileNotFoundError, expected
            ):
                resolve_openscad(explicit, env=env, system="Linux",
                                 which=(lambda name: None if "missing" in name else which(name)),
                                 home=self.root)

    def test_resolve_openscad_path_lookup_uses_injected_environment(self):
        binary_dir = self.root / "bin"
        binary_dir.mkdir()
        executable = binary_dir / "openscad"
        executable.write_text("#!/bin/sh\n")
        executable.chmod(0o755)

        self.assertEqual(
            resolve_openscad(
                None,
                env={"PATH": str(binary_dir)},
                system="Plan9",
                home=self.root,
            ),
            executable,
        )

    def test_resolve_openscad_makes_explicit_relative_path_safe_to_execute(self):
        executable = self.root / "local-openscad"
        executable.write_text("#!/bin/sh\n")
        executable.chmod(0o755)
        previous = Path.cwd()
        try:
            os.chdir(self.root)
            resolved = resolve_openscad(
                "./local-openscad", env={}, system="Plan9",
                which=lambda _name: None, home=self.root,
            )
        finally:
            os.chdir(previous)
        self.assertEqual(resolved, executable)
        self.assertTrue(resolved.is_absolute())

    def test_resolve_openscad_uses_platform_fallbacks_in_order(self):
        darwin_system = Path("/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD")
        darwin_user = self.root / "Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD"
        linux_paths = [
            Path("/usr/bin/openscad"), Path("/usr/local/bin/openscad"),
            Path("/snap/bin/openscad"),
            Path("/var/lib/flatpak/exports/bin/org.openscad.OpenSCAD"),
            self.root / ".local/share/flatpak/exports/bin/org.openscad.OpenSCAD",
        ]
        with mock.patch("plamp.cad_generation._is_executable",
                        side_effect=lambda path: Path(path) == darwin_system):
            self.assertEqual(resolve_openscad(None, env={}, system="Darwin",
                                              which=lambda _name: None, home=self.root),
                             darwin_system)
        with mock.patch("plamp.cad_generation._is_executable",
                        side_effect=lambda path: Path(path) == darwin_user):
            self.assertEqual(resolve_openscad(None, env={}, system="Darwin",
                                              which=lambda _name: None, home=self.root),
                             darwin_user)
        for expected in linux_paths:
            with self.subTest(expected=expected), mock.patch(
                "plamp.cad_generation._is_executable",
                side_effect=lambda path, expected=expected: Path(path) == expected,
            ):
                self.assertEqual(resolve_openscad(None, env={}, system="Linux",
                                                  which=lambda _name: None, home=self.root),
                                 expected)

    def test_resolve_openscad_missing_or_unsupported_is_humane(self):
        for system in ("Linux", "Plan9"):
            with self.subTest(system=system), mock.patch(
                "plamp.cad_generation._is_executable", return_value=False
            ), self.assertRaisesRegex(FileNotFoundError, "--openscad.*OPENSCAD_BIN"):
                resolve_openscad(None, env={}, system=system,
                                 which=lambda _name: None, home=self.root)

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
        self.addCleanup(lambda: snapshot.cleanup_root and __import__("shutil").rmtree(snapshot.cleanup_root))
        self.assertTrue(snapshot.dirty)
        self.assertIsNone(snapshot.full_commit)
        self.assertEqual(snapshot.revision_label, "fit-test")
        self.assertNotEqual(snapshot.scad_path, self.scad)
        self.assertEqual(snapshot.scad_path.read_text(), "cube(2);\n")

    def test_dirty_generation_records_revision_and_archives_working_source(self):
        self.scad.write_text("cube(2);\n")
        result = self.generate(revision="fit-test")
        manifest = load_run(result.run_dir)
        self.assertTrue(manifest["source"]["dirty"])
        self.assertIsNone(manifest["source"]["commit"])
        self.assertEqual(manifest["source"]["revision"], "fit-test")
        archived = result.run_dir / "source" / "things" / "fixture" / "fixture.scad"
        self.assertEqual(archived.read_text(), "cube(2);\n")

    def test_dirty_explicit_output_beneath_part_does_not_copy_itself(self):
        self.scad.write_text("cube(2);\n")
        output = self.scad.parent / "prints" / "nested-run"

        result = self.generate(revision="fit-test", output=output)

        archived = result.run_dir / "source" / "things" / "fixture" / "fixture.scad"
        self.assertEqual(archived.read_text(), "cube(2);\n")
        self.assertFalse((result.run_dir / "source" / "things" / "fixture" / "prints").exists())

    def test_committed_source_rejects_symlink_that_escapes_archive(self):
        outside = self.repo / "outside.scad"
        outside.write_text("cube(99);\n")
        (self.scad.parent / "escape.scad").symlink_to("../../outside.scad")
        subprocess.run(["git", "-C", str(self.repo), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-qm", "escaping link"], check=True)

        with self.assertRaisesRegex(ValueError, "unsafe symlink.*Git source archive"):
            prepare_source(self.repo, self.scad)

    def test_committed_source_accepts_symlink_within_part(self):
        (self.scad.parent / "safe.scad").symlink_to("fixture.scad")
        subprocess.run(["git", "-C", str(self.repo), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-qm", "safe link"], check=True)

        snapshot = prepare_source(self.repo, self.scad)
        self.addCleanup(lambda: snapshot.cleanup_root and __import__("shutil").rmtree(snapshot.cleanup_root))
        safe = snapshot.scad_path.parent / "safe.scad"
        self.assertTrue(safe.is_symlink())
        self.assertEqual(safe.resolve(), snapshot.scad_path)

    def test_historical_committed_revision_archives_and_renders_that_content(self):
        old_commit = self.commit
        self.scad.write_text("cube(2);\n")
        subprocess.run(["git", "-C", str(self.repo), "add", "."], check=True)
        subprocess.run(
            ["git", "-C", str(self.repo), "commit", "-qm", "second fixture"],
            check=True,
        )

        result = self.generate(revision=old_commit)

        manifest = load_run(result.run_dir)
        archived = result.run_dir / "source" / "things" / "fixture" / "fixture.scad"
        self.assertEqual(manifest["source"]["commit"], old_commit)
        self.assertEqual(archived.read_text(), "cube(1);\n")
        self.assertEqual(Path(manifest["jobs"][0]["command"][-1]), archived)

    def test_commit_revision_mode_engraves_resolved_short_hash(self):
        old_commit = self.commit
        self.scad.write_text("cube(2);\n")
        subprocess.run(["git", "-C", str(self.repo), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-qm", "second"], check=True)

        snapshot = prepare_source(
            self.repo, self.scad, old_commit, revision_is_commit=True
        )
        short = subprocess.run(
            ["git", "-C", str(self.repo), "rev-parse", "--short", old_commit],
            check=True, text=True, stdout=subprocess.PIPE,
        ).stdout.strip()
        self.assertEqual(snapshot.scad_path.read_text(), "cube(1);\n")
        self.assertEqual(snapshot.revision_label, short)
        self.assertNotEqual(snapshot.revision_label, old_commit)
        result = self.generate(snapshot=snapshot)
        manifest = load_run(result.run_dir)
        archived = result.run_dir / "source" / "things" / "fixture" / "fixture.scad"
        self.assertEqual(archived.read_text(), "cube(1);\n")
        self.assertEqual(manifest["source"]["revision"], short)
        self.assertTrue(manifest["run_id"].endswith(f"-{short}"))
        self.assertIn(f'revision_string="{short}"', manifest["jobs"][0]["command"])
        self.assertIn(short, Path(manifest["jobs"][0]["artifact"]).name)
        self.assertNotIn(old_commit, manifest["run_id"])

    def test_commit_revision_mode_archives_commit_even_with_dirty_worktree(self):
        old_commit = self.commit
        self.scad.write_text("cube(99);\n")
        snapshot = prepare_source(
            self.repo, self.scad, old_commit, revision_is_commit=True
        )
        self.addCleanup(lambda: snapshot.cleanup_root and __import__("shutil").rmtree(snapshot.cleanup_root))
        short = subprocess.run(
            ["git", "-C", str(self.repo), "rev-parse", "--short", old_commit],
            check=True, text=True, stdout=subprocess.PIPE,
        ).stdout.strip()
        self.assertFalse(snapshot.dirty)
        self.assertEqual(snapshot.revision_label, short)
        self.assertEqual(snapshot.scad_path.read_text(), "cube(1);\n")

    def test_literal_revision_keeps_label_for_committed_and_dirty_sources(self):
        head = prepare_source(self.repo, self.scad, "HEAD", revision_is_commit=False)
        self.addCleanup(lambda: head.cleanup_root and __import__("shutil").rmtree(head.cleanup_root))
        self.assertEqual(head.full_commit, self.commit)
        self.assertEqual(head.revision_label, "HEAD")

        self.scad.write_text("cube(3);\n")
        dirty = prepare_source(self.repo, self.scad, "fit-test-1", revision_is_commit=False)
        self.addCleanup(lambda: dirty.cleanup_root and __import__("shutil").rmtree(dirty.cleanup_root))
        self.assertTrue(dirty.dirty)
        self.assertEqual(dirty.revision_label, "fit-test-1")
        self.assertEqual(dirty.scad_path.read_text(), "cube(3);\n")

    def test_default_and_explicit_output_locations(self):
        result = self.generate()
        self.assertEqual(result.run_dir.parent, self.data / "cad" / "prints" / "fixture")
        explicit = self.root / "chosen-run"
        result = self.generate(output=explicit)
        self.assertEqual(result.run_dir, explicit)

    def test_run_ids_are_human_readable(self):
        instant = datetime(
            2026, 7, 23, 22, 19,
            tzinfo=timezone(timedelta(hours=-10)),
        )
        with mock.patch("plamp.cad_generation._local_now", return_value=instant):
            managed = self.generate()
            explicit = self.generate(output=self.root / "chosen-run")

        expected = f"2026-jul23-fixture-print-22h:19m-{self.commit[:7]}"
        self.assertEqual(load_run(managed.run_dir)["run_id"], expected)
        self.assertEqual(managed.run_dir.name, expected)
        self.assertEqual(load_run(explicit.run_dir)["run_id"], expected)
        self.assertEqual(explicit.run_dir, self.root / "chosen-run")

    def test_distinct_same_minute_runs_fail_clearly(self):
        instant = datetime(
            2026, 7, 23, 22, 19,
            tzinfo=timezone(timedelta(hours=-10)),
        )
        with mock.patch("plamp.cad_generation._local_now", return_value=instant):
            first = self.generate(plan("first"))
            with self.assertRaises(FileExistsError) as caught:
                self.generate(distinct_plan("second"))

        self.assertEqual(
            Path(caught.exception.filename),
            first.run_dir,
        )

    def test_same_day_duplicate_is_rejected_before_openscad(self):
        zone = timezone(timedelta(hours=-10))
        first_time = datetime(2026, 7, 23, 8, 1, tzinfo=zone)
        second_time = datetime(2026, 7, 23, 22, 19, tzinfo=zone)
        with mock.patch(
            "plamp.cad_generation._local_now",
            side_effect=(first_time, second_time),
        ):
            first = self.generate()
            self.argv_file.unlink()
            with self.assertRaises(CadRunExistsError) as caught:
                self.generate()

        self.assertEqual(caught.exception.existing_run_id, first.run_dir.name)
        self.assertEqual(caught.exception.existing_run_dir, first.run_dir)
        self.assertIn(str(first.run_dir), str(caught.exception))
        self.assertFalse(self.argv_file.exists())

    def test_duplicate_identity_allows_different_jobs_or_local_day(self):
        zone = timezone(timedelta(hours=-10))
        times = (
            datetime(2026, 7, 23, 8, 1, tzinfo=zone),
            datetime(2026, 7, 23, 8, 2, tzinfo=zone),
            datetime(2026, 7, 23, 8, 3, tzinfo=zone),
            datetime(2026, 7, 24, 8, 1, tzinfo=zone),
        )
        with mock.patch("plamp.cad_generation._local_now", side_effect=times):
            first = self.generate(plan("first"))
            different_job = self.generate(distinct_plan("second"))
            self.scad.write_text("cube(2);\n")
            subprocess.run(
                ["git", "-C", str(self.repo), "add", "."], check=True
            )
            subprocess.run(
                ["git", "-C", str(self.repo), "commit", "-qm", "change source"],
                check=True,
            )
            different_source = self.generate(plan("first"))
            next_day = self.generate(plan("first"))

        self.assertNotEqual(first.run_dir, different_job.run_dir)
        self.assertNotEqual(first.run_dir, different_source.run_dir)
        self.assertNotEqual(first.run_dir, next_day.run_dir)

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
        archived = result.run_dir / "source" / "things" / "fixture" / "fixture.scad"
        expected = [
            str(self.fake), "-o", str(
                result.run_dir / "artifacts"
                / f".first--aaaaaaaaaaa1--{self.commit[:7]}.tmp.stl"
            ),
            "-D", f'revision_string="{self.commit[:7]}"',
            "-D", 'view="first"', "-D", "count=1", "-D", 'label="a b"',
            "-D", "enabled=true", "-D", "quality=$preview ? 2 : 20",
            "--export-format", "asciistl", str(archived),
        ]
        self.assertEqual(command, expected)
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

    def test_process_launch_failure_after_version_check_is_archived_as_failed(self):
        disappearing = self.root / "disappearing-openscad"
        disappearing.write_text(textwrap.dedent("""\
            #!/usr/bin/env python3
            import pathlib, sys
            if "--version" in sys.argv:
                pathlib.Path(__file__).unlink()
                print("OpenSCAD version 2099.01")
        """))
        disappearing.chmod(0o755)
        output = self.root / "launch-failure"

        result = generate_plan(
            plan("first"), repo_root=self.repo, data_dir=self.data,
            scad_path=self.scad, openscad=disappearing, output=output,
            env=self.env(), stdout=io.StringIO(), stderr=io.StringIO(),
        )

        manifest = load_run(output)
        job = manifest["jobs"][0]
        self.assertEqual(result.status, "failed")
        self.assertEqual(manifest["status"], "failed")
        self.assertEqual(job["status"], "failed")
        self.assertIsNotNone(job["finished_at"])
        self.assertIsNotNone(job["elapsed_seconds"])
        self.assertTrue(job["errors"])
        self.assertIsNotNone(manifest["finished_at"])
        self.assertTrue((output / job["log"]).is_file())

    def test_interrupted_job_records_elapsed_time_before_reraising(self):
        output = self.root / "interrupted"
        with mock.patch(
            "plamp.cad_generation._capture_line", side_effect=KeyboardInterrupt
        ):
            with self.assertRaises(KeyboardInterrupt):
                generate_plan(
                    plan("first"), repo_root=self.repo, data_dir=self.data,
                    scad_path=self.scad, openscad=self.fake, output=output,
                    env=self.env(), stdout=io.StringIO(),
                )

        manifest = load_run(output)
        self.assertEqual(manifest["status"], "interrupted")
        self.assertEqual(manifest["jobs"][0]["status"], "interrupted")
        self.assertIsNotNone(manifest["jobs"][0]["elapsed_seconds"])

    def test_catalog_is_newest_first_and_log_uses_exact_artifact_id(self):
        old_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
        new_time = datetime(2026, 1, 2, tzinfo=timezone.utc)
        with mock.patch("plamp.cad_generation._utc_now", return_value=old_time):
            older = self.generate(
                output=self.data / "cad" / "prints" / "fixture" / "older"
            )
        with mock.patch("plamp.cad_generation._utc_now", return_value=new_time):
            newer = self.generate(
                output=self.data / "cad" / "prints" / "fixture" / "newer"
            )
        self.assertEqual(
            [item["run_id"] for item in list_runs(self.data, "fixture")],
            [load_run(newer.run_dir)["run_id"], load_run(older.run_dir)["run_id"]],
        )
        with self.assertRaisesRegex(KeyError, "missing"):
            load_job_log(newer.run_dir, "missing")

    def test_list_runs_rejects_unsafe_part_components(self):
        for part in ("../fixture", "/tmp/fixture", "fixture/child", ".", ""):
            with self.subTest(part=part):
                with self.assertRaisesRegex(ValueError, "single path component"):
                    list_runs(self.data, part)

    def test_load_job_log_rejects_manifest_path_escape_and_unexpected_path(self):
        result = self.generate()
        manifest_path = result.manifest_path
        manifest = load_run(result.run_dir)
        job = manifest["jobs"][0]
        outside = self.root / "outside.log"
        outside.write_text("secret")
        for tampered in (str(outside), "../../outside.log", "logs/other.log"):
            with self.subTest(log=tampered):
                job["log"] = tampered
                manifest_path.write_text(json.dumps(manifest))
                with self.assertRaisesRegex(ValueError, "unsafe CAD job log path"):
                    load_job_log(result.run_dir, job["artifact_id"])


if __name__ == "__main__":
    unittest.main()
