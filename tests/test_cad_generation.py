import io
import json
import os
import subprocess
import tempfile
import textwrap
import unittest
import shutil
import errno
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
from plamp.cad_model import CadModel, CadSet
from plamp.cad_planning import CadSelection, RenderJob, RenderPlan, ResolvedProfile
from plamp.cad_manufacturing import DirectiveSource, merge_manufacturing
from plamp.cad_values import ResolvedVariable, VariableLayer


JOB_FIELDS = {
    "artifact_id", "geometry_fingerprint", "manufacturing_fingerprint", "model", "set", "variant_name", "product_paths",
    "variables", "raw_defines", "status", "queued_at", "started_at",
    "variable_sources", "profiles", "manufacturing",
    "finished_at", "elapsed_seconds", "command", "artifact",
    "artifact_bytes", "log", "exit_code", "echoes", "messages", "warnings",
    "errors", "geometry", "artifact_sha256", "reused_from",
}


def plan(*views):
    jobs = tuple(
        RenderJob(
            artifact_id=f"{view}--{'a' * 11}{index}",
            geometry_fingerprint=f"{'a' * 63}{index}",
            manufacturing_fingerprint="c" * 64,
            model_id="fixture", set_name=view,
            variant_name=view,
            variables={"count": index, "label": "a b", "enabled": True},
            raw_defines={"quality": "$preview ? 2 : 20"},
            variable_sources={}, profiles=(), manufacturing=merge_manufacturing(()),
            product_paths=(("print",),),
        )
        for index, view in enumerate(views, 1)
    )
    return RenderPlan("fixture-system", Path("cad/fixture.system.cad.json"),
                      CadSelection(product="print"), jobs, "c" * 64)


def distinct_plan(view):
    source_plan = plan(view)
    job = replace(
        source_plan.jobs[0],
        artifact_id=f"{view}--{'b' * 12}",
        geometry_fingerprint="b" * 64,
    )
    return RenderPlan(source_plan.system_name, source_plan.system_path,
                      source_plan.selection, (job,), source_plan.system_manifest_hash)


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
        self.model = CadModel(
            "fixture", "fixture", "Fixture", self.scad, None, "",
            {"": CadSet(""), "first": CadSet("first"), "second": CadSet("second")},
            {}, {}, (),
        )
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
            if "--info" in sys.argv:
                print("OpenSCAD Version: 2099.01")
                print("User Library Path: " + os.environ["FAKE_USER_LIBRARY"])
                print("OpenSCAD library path:")
                if os.environ.get("FAKE_INFO_ECHO_OPENSCADPATH"):
                    for item in os.environ.get("OPENSCADPATH", "").split(os.pathsep):
                        if item:
                            print(item)
                print(os.environ["FAKE_INSTALL_LIBRARY"])
                print()
                raise SystemExit(0)
            pathlib.Path(os.environ["FAKE_ARGV"]).write_text(json.dumps(sys.argv[1:]))
            output = pathlib.Path(sys.argv[sys.argv.index("-o") + 1])
            state_log = os.environ.get("FAKE_STATE_LOG")
            if state_log and os.environ.get("PLAMP_CAD_MANIFEST"):
                manifest = json.loads(pathlib.Path(os.environ["PLAMP_CAD_MANIFEST"]).read_text())
                with pathlib.Path(state_log).open("a") as stream:
                    stream.write(json.dumps([manifest["status"], [job["status"] for job in manifest["jobs"]]]) + "\\n")
            defines = [sys.argv[i + 1] for i, arg in enumerate(sys.argv) if arg == "-D"]
            view = next((item.split("=", 1)[1].strip('"') for item in defines if item.startswith("set=")), "default")
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
            if "-d" in sys.argv:
                dependency = pathlib.Path(sys.argv[sys.argv.index("-d") + 1])
                final_render = "--export-format" in sys.argv
                if final_render and os.environ.get("FAKE_MUTATE_SOURCE"):
                    pathlib.Path(sys.argv[-1]).write_text("changed during render")
                if not (final_render and os.environ.get("FAKE_SKIP_FINAL_D")):
                    rows = [sys.argv[-1]]
                    if not final_render and os.environ.get("FAKE_DISCOVERY_DEP"):
                        rows.append(os.environ["FAKE_DISCOVERY_DEP"])
                    if final_render and os.environ.get("FAKE_FINAL_DEP"):
                        rows.append(os.environ["FAKE_FINAL_DEP"])
                    dependency.write_text(str(output) + ": " + " ".join(rows) + "\\n")
            env_log = os.environ.get("FAKE_ENV_LOG")
            if env_log:
                pathlib.Path(env_log).write_text(json.dumps({
                    key: os.environ.get(key) for key in
                    ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "OPENSCADPATH")
                }))
            if not os.environ.get("FAKE_EMPTY"):
                output.write_text("solid fixture\\nendsolid fixture\\n")
        """))
        self.fake.chmod(0o755)
        self.argv_file = self.root / "argv.json"
        self.user_library = self.root / "user-library"
        self.install_library = self.root / "install-library"
        self.user_library.mkdir()
        self.install_library.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def env(self, **values):
        return {
            **os.environ, "FAKE_ARGV": str(self.argv_file),
            "FAKE_USER_LIBRARY": str(self.user_library),
            "FAKE_INSTALL_LIBRARY": str(self.install_library), **values,
        }

    def test_render_uses_staged_source_makefile_and_isolated_library_environment(self):
        environment_log = self.root / "render-env.json"
        result = self.generate(env=self.env(FAKE_ENV_LOG=str(environment_log)))
        self.assertEqual(result.status, "complete")
        argv = json.loads(self.argv_file.read_text())
        self.assertIn("-d", argv)
        self.assertIn("/repository/things/fixture/fixture.scad", argv[-1])
        rendered_env = json.loads(environment_log.read_text())
        self.assertNotEqual(rendered_env["HOME"], str(Path.home()))
        self.assertTrue(rendered_env["OPENSCADPATH"].endswith("/libraries"))

    def test_successful_openscad_with_host_fallback_discards_artifact(self):
        host_dependency = self.root / "host-only.scad"
        host_dependency.write_text("cube(99);")
        result = self.generate(env=self.env(FAKE_FINAL_DEP=str(host_dependency)))
        job = load_run(result.run_dir)["jobs"][0]
        self.assertEqual(job["status"], "failed")
        self.assertIsNone(job["artifact"])
        self.assertIn("outside staged dependency closure", job["errors"][-1])
        self.assertFalse(list((result.run_dir / "artifacts").glob("*.stl")))

    def test_configured_openscadpath_is_not_an_implicit_installation_root(self):
        host_root = self.root / "configured-host-library"
        host_root.mkdir()
        host_dependency = host_root / "undeclared.scad"
        host_dependency.write_text("cube(77);")
        result = self.generate(env=self.env(
            OPENSCADPATH=str(host_root),
            FAKE_INFO_ECHO_OPENSCADPATH="1",
            FAKE_DISCOVERY_DEP=str(host_dependency),
        ))
        job = load_run(result.run_dir)["jobs"][0]
        self.assertEqual(job["status"], "failed")
        self.assertIn("undeclared host CAD dependency", job["errors"][-1])
        self.assertIsNone(job["artifact"])

    def test_classification_failure_log_retains_discovery_output(self):
        host_dependency = self.root / "undeclared-classification.scad"
        host_dependency.write_text("cube(88);")
        result = self.generate(env=self.env(
            FAKE_DISCOVERY_DEP=str(host_dependency),
        ))
        job = load_run(result.run_dir)["jobs"][0]
        log = (result.run_dir / str(job["log"])).read_text()
        self.assertEqual(job["status"], "failed")
        self.assertIn("OpenSCAD dependency discovery:", log)
        self.assertIn('ECHO: "ordinary"', log)
        self.assertIn("dependency transaction failed:", log)

    def test_missing_second_makefile_and_staged_content_change_fail_closed(self):
        for variable, expected in (
            ("FAKE_SKIP_FINAL_D", "cannot read dependency file"),
            ("FAKE_MUTATE_SOURCE", "content hash mismatch"),
        ):
            with self.subTest(variable=variable):
                output = self.root / variable.lower()
                result = self.generate(
                    output=output, env=self.env(**{variable: "1"})
                )
                job = load_run(result.run_dir)["jobs"][0]
                self.assertEqual(job["status"], "failed")
                self.assertIsNone(job["artifact"])
                self.assertIn(expected, job["errors"][-1])

    def generate(self, source_plan=None, **kwargs):
        environment = kwargs.pop("env", self.env())
        stdout = kwargs.pop("stdout", io.StringIO())
        openscad = kwargs.pop("openscad", self.fake)
        snapshot = kwargs.pop("snapshot", None) or prepare_source(
            self.repo, self.scad, kwargs.get("revision")
        )
        return generate_plan(
            source_plan or plan("first"), repo_root=self.repo,
            data_dir=self.data, models={"fixture": self.model},
            snapshots={"fixture": snapshot}, openscad=openscad,
            env=environment, stdout=stdout, **kwargs,
        )

    @staticmethod
    def tree_bytes(root):
        return {
            path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*")
            if path.is_file()
        }

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
        self.assertTrue(manifest["models"]["fixture"]["dirty"])
        self.assertIsNone(manifest["models"]["fixture"]["commit"])
        self.assertEqual(manifest["models"]["fixture"]["revision"], "fit-test")
        archived = result.run_dir / "source" / "fixture" / "fixture.scad"
        self.assertEqual(archived.read_text(), "cube(2);\n")

    def test_dirty_explicit_output_beneath_part_does_not_copy_itself(self):
        self.scad.write_text("cube(2);\n")
        output = self.scad.parent / "prints" / "nested-run"

        result = self.generate(revision="fit-test", output=output)

        archived = result.run_dir / "source" / "fixture" / "fixture.scad"
        self.assertEqual(archived.read_text(), "cube(2);\n")
        self.assertFalse((result.run_dir / "source" / "fixture" / "prints").exists())

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
        archived = result.run_dir / "source" / "fixture" / "fixture.scad"
        self.assertEqual(manifest["models"]["fixture"]["commit"], old_commit)
        self.assertEqual(archived.read_text(), "cube(1);\n")
        self.assertRegex(
            manifest["jobs"][0]["command"][-1],
            r"/stage/repository/things/fixture/fixture\.scad$",
        )

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
        archived = result.run_dir / "source" / "fixture" / "fixture.scad"
        self.assertEqual(archived.read_text(), "cube(1);\n")
        self.assertEqual(manifest["models"]["fixture"]["revision"], short)
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
        self.assertEqual(result.run_dir.parent, self.data / "cad" / "prints" / "fixture-system")
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

        expected = f"2026-jul23-fixture-system-product-print-22h:19m-{self.commit[:7]}"
        self.assertEqual(load_run(managed.run_dir)["run_id"], expected)
        self.assertEqual(managed.run_dir.name, expected)
        self.assertEqual(load_run(explicit.run_dir)["run_id"], expected)
        self.assertEqual(explicit.run_dir, self.root / "chosen-run")

    def test_distinct_same_minute_runs_are_allocated_without_raw_collision(self):
        instant = datetime(
            2026, 7, 23, 22, 19,
            tzinfo=timezone(timedelta(hours=-10)),
        )
        with mock.patch("plamp.cad_generation._local_now", return_value=instant):
            first = self.generate(plan("first"))
            second = self.generate(distinct_plan("second"))

        self.assertNotEqual(second.run_dir, first.run_dir)
        self.assertTrue(second.run_dir.name.endswith("-2"))

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

    def test_product_jobs_render_their_own_archived_model_sources(self):
        holder_dir = self.repo / "things" / "holder"
        holder_dir.mkdir()
        holder_scad = holder_dir / "holder.scad"
        holder_scad.write_text("sphere(1);\n")
        subprocess.run(["git", "-C", str(self.repo), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-qm", "holder"], check=True)
        holder = CadModel(
            "holder", "holder", "Holder", holder_scad, None, "mount",
            {"mount": CadSet("mount")}, {}, {}, (),
        )
        box_snapshot = prepare_source(self.repo, self.scad)
        holder_snapshot = prepare_source(self.repo, holder_scad)
        self.addCleanup(lambda: __import__("shutil").rmtree(box_snapshot.cleanup_root, ignore_errors=True))
        self.addCleanup(lambda: __import__("shutil").rmtree(holder_snapshot.cleanup_root, ignore_errors=True))
        source_plan = plan("floor")
        second = replace(
            source_plan.jobs[0], artifact_id=f"mount--{'d' * 12}",
            geometry_fingerprint="d" * 64, model_id="holder", set_name="mount",
            variant_name="mount",
        )
        two_model = replace(source_plan, jobs=(source_plan.jobs[0], second))
        result = generate_plan(
            two_model, repo_root=self.repo, data_dir=self.data,
            models={"fixture": self.model, "holder": holder},
            snapshots={"fixture": box_snapshot, "holder": holder_snapshot},
            openscad=self.fake, env=self.env(), stdout=io.StringIO(),
        )
        jobs = load_run(result.run_dir)["jobs"]
        self.assertIn('set="floor"', jobs[0]["command"])
        self.assertRegex(jobs[0]["command"][-1], r"/stage/repository/things/fixture/fixture\.scad$")
        self.assertRegex(jobs[1]["command"][-1], r"/stage/repository/things/holder/holder\.scad$")
        self.assertEqual(set(load_run(result.run_dir)["models"]), {"fixture", "holder"})

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

    def test_regeneration_replaces_the_existing_run_after_success(self):
        zone = timezone(timedelta(hours=-10))
        times = (
            datetime(2026, 7, 23, 8, 1, tzinfo=zone),
            datetime(2026, 7, 23, 22, 19, tzinfo=zone),
        )
        with mock.patch("plamp.cad_generation._local_now", side_effect=times):
            original = self.generate()
            old_manifest = (original.run_dir / "manifest.json").read_bytes()
            self.argv_file.unlink()
            replacement = self.generate(regenerate=True)

        self.assertEqual(replacement.run_dir, original.run_dir)
        self.assertEqual(replacement.status, "complete")
        self.assertTrue(self.argv_file.exists())
        self.assertNotEqual(
            (replacement.run_dir / "manifest.json").read_bytes(),
            old_manifest,
        )
        self.assertEqual(
            list(original.run_dir.parent.glob(f".{original.run_dir.name}.*")),
            [],
        )

    def test_failed_regeneration_preserves_old_run_and_failed_diagnostics(self):
        zone = timezone(timedelta(hours=-10))
        times = (
            datetime(2026, 7, 23, 8, 1, tzinfo=zone),
            datetime(2026, 7, 23, 22, 19, tzinfo=zone),
        )
        with mock.patch("plamp.cad_generation._local_now", side_effect=times):
            original = self.generate()
            original_files = self.tree_bytes(original.run_dir)
            failed = self.generate(
                regenerate=True,
                env=self.env(FAKE_FAIL_VIEW="first"),
            )

        self.assertEqual(failed.status, "failed")
        self.assertIn("regeneration-failed", failed.run_dir.name)
        self.assertEqual(self.tree_bytes(original.run_dir), original_files)
        self.assertTrue((failed.run_dir / "manifest.json").is_file())
        self.assertEqual(load_run(failed.run_dir)["status"], "failed")
        self.assertEqual(
            [run["run_id"] for run in list_runs(self.data, "fixture-system")],
            [original.run_dir.name],
        )

    def test_regeneration_publication_failure_rolls_back_old_run(self):
        zone = timezone(timedelta(hours=-10))
        times = (
            datetime(2026, 7, 23, 8, 1, tzinfo=zone),
            datetime(2026, 7, 23, 22, 19, tzinfo=zone),
        )
        with mock.patch("plamp.cad_generation._local_now", side_effect=times):
            original = self.generate()
            original_files = self.tree_bytes(original.run_dir)
            real_replace = os.replace

            def fail_staging_publication(source, target, **kwargs):
                source_path = Path(source)
                target_path = Path(target)
                if (
                    ".regenerating." in source_path.name
                    and target_path == original.run_dir
                ):
                    raise OSError("injected publication failure")
                return real_replace(source, target, **kwargs)

            with mock.patch(
                "plamp.cad_generation.os.replace",
                side_effect=fail_staging_publication,
            ), self.assertRaisesRegex(OSError, "injected publication failure"):
                self.generate(regenerate=True)

        self.assertEqual(self.tree_bytes(original.run_dir), original_files)
        failed = list(
            original.run_dir.parent.glob(
                f".{original.run_dir.name}.regeneration-failed.*"
            )
        )
        self.assertEqual(len(failed), 1)
        self.assertEqual(load_run(failed[0])["status"], "complete")

    def test_manifest_schema_and_job_schema_are_frozen(self):
        result = self.generate()
        manifest = load_run(result.run_dir)
        self.assertEqual(set(manifest), {
            "schema_version", "generator_version", "run_id", "system_name", "status",
            "created_at", "updated_at", "started_at", "finished_at",
            "selection", "system", "models", "openscad_version", "jobs",
        })
        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(manifest["generator_version"], 1)
        self.assertEqual(set(manifest["jobs"][0]), JOB_FIELDS)
        self.assertEqual(manifest["jobs"][0]["variable_sources"], {})
        self.assertEqual(manifest["jobs"][0]["profiles"], [])
        self.assertEqual(manifest["jobs"][0]["manufacturing"], {
            "directives": {}, "notes": [],
        })
        self.assertEqual(set(manifest["jobs"][0]["geometry"]), {
            "render_seconds", "simple", "vertices", "facets", "volumes",
        })
        self.assertEqual(manifest["models"]["fixture"]["commit"], self.commit)
        self.assertRegex(manifest["created_at"], r"Z$")

    def test_snapshot_geometry_identity_ignores_sidecar_only_commits(self):
        sidecar = self.scad.with_suffix(".cad.json")
        sidecar.write_text('{"slicing":{"supports":"forbidden"}}\n')
        subprocess.run(["git", "-C", str(self.repo), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-qm", "sidecar one"], check=True)
        first = prepare_source(self.repo, self.scad)
        self.addCleanup(lambda: __import__("shutil").rmtree(first.cleanup_root, ignore_errors=True))

        sidecar.write_text('{"slicing":{"supports":"recommended"}}\n')
        subprocess.run(["git", "-C", str(self.repo), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-qm", "sidecar two"], check=True)
        second = prepare_source(self.repo, self.scad)
        self.addCleanup(lambda: __import__("shutil").rmtree(second.cleanup_root, ignore_errors=True))

        self.assertNotEqual(first.source_identity, second.source_identity)
        self.assertEqual(first.geometry_identity, second.geometry_identity)

        self.scad.write_text("cube(2);\n")
        subprocess.run(["git", "-C", str(self.repo), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-qm", "geometry"], check=True)
        third = prepare_source(self.repo, self.scad)
        self.addCleanup(lambda: __import__("shutil").rmtree(third.cleanup_root, ignore_errors=True))
        self.assertNotEqual(second.geometry_identity, third.geometry_identity)

    def test_manifest_preserves_resolved_profile_provenance(self):
        source_plan = plan("first")
        profiled = replace(
            source_plan.jobs[0],
            profiles=(ResolvedProfile(
                "draft", "local:draft", "local", "local", "quality",
                "f" * 64, "cad/profiles/draft.json",
            ),),
        )
        result = self.generate(replace(source_plan, jobs=(profiled,)))
        profile = load_run(result.run_dir)["jobs"][0]["profiles"][0]
        self.assertEqual(profile, {
            "name": "draft", "qualified_id": "local:draft",
            "namespace": "local", "source": "local", "kind": "quality",
            "content_hash": "f" * 64, "path": "cad/profiles/draft.json",
        })

    def test_manifest_preserves_complete_variable_provenance(self):
        source_plan = plan("first")
        job = replace(
            source_plan.jobs[0],
            variable_sources={"count": ResolvedVariable("count", (
                VariableLayer("model", "fixture", value=3),
                VariableLayer("cli", "defines", value=1),
            ))},
        )
        result = self.generate(replace(source_plan, jobs=(job,)))
        self.assertEqual(load_run(result.run_dir)["jobs"][0]["variable_sources"], {
            "count": {
                "layers": [
                    {"kind": "model", "source_id": "fixture", "value": 3,
                     "raw_expression": None},
                    {"kind": "cli", "source_id": "defines", "value": 1,
                     "raw_expression": None},
                ],
                "winner": {"kind": "cli", "source_id": "defines", "value": 1,
                           "raw_expression": None},
            },
        })

    def test_manufacturing_change_reuses_geometry_with_fresh_archive_metadata(self):
        first_plan = plan("first")
        first = self.generate(first_plan)
        original_job = first_plan.jobs[0]
        changed_job = replace(
            original_job,
            manufacturing=merge_manufacturing(((
                DirectiveSource("profile:ironing"),
                {"ironing": "recommended"},
            ),)),
            manufacturing_fingerprint="d" * 64,
        )
        changed_plan = replace(first_plan, jobs=(changed_job,))
        self.argv_file.unlink()
        zone = timezone(timedelta(hours=-10))
        with mock.patch("plamp.cad_generation._local_now", return_value=datetime(
            2026, 7, 23, 22, 20, tzinfo=zone,
        )):
            second = self.generate(changed_plan)
        first_manifest = load_run(first.run_dir)
        second_manifest = load_run(second.run_dir)
        old_job = first_manifest["jobs"][0]
        new_job = second_manifest["jobs"][0]

        self.assertFalse(self.argv_file.exists())
        self.assertNotEqual(first.run_dir, second.run_dir)
        self.assertEqual(new_job["status"], "complete")
        self.assertEqual(new_job["artifact_sha256"], old_job["artifact_sha256"])
        self.assertEqual(new_job["reused_from"], {
            "run_id": first_manifest["run_id"],
            "artifact_id": old_job["artifact_id"],
            "artifact": old_job["artifact"],
        })
        self.assertIn("Enable ironing", (second.run_dir / "readme.md").read_text())
        self.assertEqual((second.run_dir / new_job["log"]).read_text(), "")

    def test_same_minute_manufacturing_change_gets_distinct_run_identity(self):
        source_plan = plan("first")
        changed_plan = replace(source_plan, jobs=(replace(
            source_plan.jobs[0], manufacturing_fingerprint="d" * 64,
        ),))
        instant = datetime(
            2026, 7, 23, 22, 19,
            tzinfo=timezone(timedelta(hours=-10)),
        )
        with mock.patch("plamp.cad_generation._local_now", return_value=instant):
            first = self.generate(source_plan)
            second = self.generate(changed_plan)
        self.assertNotEqual(first.run_dir, second.run_dir)
        self.assertTrue(second.run_dir.name.endswith("-mfgddddddd"))

    def test_manufacturing_suffix_extends_when_short_prefix_is_occupied(self):
        source_plan = plan("first")
        first_changed = replace(source_plan, jobs=(replace(
            source_plan.jobs[0], manufacturing_fingerprint="d" * 64,
        ),))
        second_fingerprint = "d" * 7 + "e" * 57
        second_changed = replace(source_plan, jobs=(replace(
            source_plan.jobs[0], manufacturing_fingerprint=second_fingerprint,
        ),))
        instant = datetime(2026, 7, 23, 22, 19,
                           tzinfo=timezone(timedelta(hours=-10)))
        with mock.patch("plamp.cad_generation._local_now", return_value=instant):
            self.generate(source_plan)
            short = self.generate(first_changed)
            extended = self.generate(second_changed)
        self.assertTrue(short.run_dir.name.endswith("-mfgddddddd"), short.run_dir.name)
        self.assertTrue(extended.run_dir.name.endswith("-mfgddddddde"), extended.run_dir.name)

    def test_reuse_requires_valid_recorded_lowercase_checksum(self):
        for checksum in (None, "bad", "A" * 64):
            with self.subTest(checksum=checksum):
                first = self.generate(plan("first"), output=self.root / f"seed-{checksum}")
                manifest = load_run(first.run_dir)
                manifest["jobs"][0]["artifact_sha256"] = checksum
                first.manifest_path.write_text(json.dumps(manifest))
                archive = self.data / "cad" / "prints" / "fixture-system" / first.run_dir.name
                shutil.copytree(first.run_dir, archive)
                self.argv_file.unlink(missing_ok=True)
                changed = replace(plan("first"), jobs=(replace(
                    plan("first").jobs[0], manufacturing_fingerprint=("d" if checksum is None else "e") * 64,
                ),))
                self.generate(changed, output=self.root / f"result-{checksum}")
                self.assertTrue(self.argv_file.exists())
                shutil.rmtree(archive)

    def _assert_symlink_candidate_is_not_reused(self, component):
        first = self.generate(plan("first"))
        manifest = load_run(first.run_dir)
        component(first, manifest)
        self.argv_file.unlink(missing_ok=True)
        changed = replace(plan("first"), jobs=(replace(
            plan("first").jobs[0], manufacturing_fingerprint="d" * 64,
        ),))
        self.generate(changed, output=self.root / "symlink-result")
        self.assertTrue(self.argv_file.exists())

    def test_reuse_rejects_symlinked_run(self):
        def mutate(first, _manifest):
            real = self.root / "real-run"
            first.run_dir.rename(real)
            first.run_dir.symlink_to(real, target_is_directory=True)
        self._assert_symlink_candidate_is_not_reused(mutate)

    def test_duplicate_lookup_ignores_symlinked_run(self):
        first = self.generate(plan("first"))
        real = self.root / "real-run"
        first.run_dir.rename(real)
        first.run_dir.symlink_to(real, target_is_directory=True)
        second = self.generate(plan("first"))
        self.assertNotEqual(second.run_dir, first.run_dir)
        self.assertTrue(second.run_dir.name.endswith("-2"))

    def test_reuse_rejects_symlinked_manifest(self):
        def mutate(first, _manifest):
            outside = self.root / "outside-manifest.json"
            outside.write_bytes(first.manifest_path.read_bytes())
            first.manifest_path.unlink()
            first.manifest_path.symlink_to(outside)
        self._assert_symlink_candidate_is_not_reused(mutate)

    def test_reuse_rejects_symlinked_artifact(self):
        def mutate(first, manifest):
            artifact = first.run_dir / manifest["jobs"][0]["artifact"]
            outside = self.root / "outside.stl"
            outside.write_bytes(artifact.read_bytes())
            artifact.unlink()
            artifact.symlink_to(outside)
        self._assert_symlink_candidate_is_not_reused(mutate)

    def test_reuse_copies_verified_descriptor_not_swapped_path(self):
        import plamp.cad_generation as generation
        first = self.generate(plan("first"))
        manifest = load_run(first.run_dir)
        artifact = first.run_dir / manifest["jobs"][0]["artifact"]
        original = artifact.read_bytes()
        real_copy = generation._copy_verified_artifact

        def swap_then_copy(candidate, target, destination_fd=None):
            replacement = artifact.with_suffix(".replacement")
            replacement.write_bytes(b"swapped")
            os.replace(replacement, artifact)
            return real_copy(candidate, target, destination_fd)

        changed = replace(plan("first"), jobs=(replace(
            plan("first").jobs[0], manufacturing_fingerprint="d" * 64,
        ),))
        with mock.patch("plamp.cad_generation._copy_verified_artifact",
                        side_effect=swap_then_copy):
            second = self.generate(changed, output=self.root / "race-result")
        second_manifest = load_run(second.run_dir)
        copied = second.run_dir / second_manifest["jobs"][0]["artifact"]
        self.assertEqual(copied.read_bytes(), original)

    def test_reuse_publication_never_overwrites_concurrent_target(self):
        import plamp.cad_generation as generation
        first = self.generate(plan("first"))
        changed = replace(plan("first"), jobs=(replace(
            plan("first").jobs[0], manufacturing_fingerprint="d" * 64,
        ),))
        real_link = os.link

        def inject_target(source, target, **kwargs):
            target_fd = kwargs["dst_dir_fd"]
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                         0o644, dir_fd=target_fd)
            os.write(fd, b"concurrent-owner")
            os.close(fd)
            return real_link(source, target, **kwargs)

        with mock.patch("plamp.cad_generation.os.link", side_effect=inject_target):
            result = self.generate(changed, output=self.root / "publish-race")

        expected = result.run_dir / "artifacts" / (
            f"{changed.jobs[0].artifact_id}--{self.commit[:7]}.stl"
        )
        self.assertEqual(result.status, "failed")
        self.assertEqual(expected.read_bytes(), b"concurrent-owner")
        self.assertEqual(list(expected.parent.glob("*.reuse.tmp")), [])
        self.assertEqual(list(expected.parent.glob(".*.reuse.tmp")), [])

    def test_reuse_publication_failure_cleans_temporary_and_falls_back(self):
        self.generate(plan("first"))
        changed = replace(plan("first"), jobs=(replace(
            plan("first").jobs[0], manufacturing_fingerprint="d" * 64,
        ),))
        import plamp.cad_generation as generation
        real_copy = generation._copy_verified_artifact

        def fail_reuse_only(source, target, destination_fd=None):
            if source.manifest:
                raise OSError(errno.EIO, "injected publish failure")
            return real_copy(source, target, destination_fd)

        with mock.patch("plamp.cad_generation._copy_verified_artifact",
                        side_effect=fail_reuse_only):
            result = self.generate(changed, output=self.root / "publish-failure")
        self.assertEqual(result.status, "complete")
        self.assertFalse(list((result.run_dir / "artifacts").glob(".*.reuse.tmp")))

    def test_generic_reuse_failure_preserves_concurrent_target_and_does_not_render(self):
        self.generate(plan("first"))
        changed = replace(plan("first"), jobs=(replace(
            plan("first").jobs[0], manufacturing_fingerprint="d" * 64,
        ),))
        output = self.root / "generic-reuse-race"
        final = output / "artifacts" / (
            f"{changed.jobs[0].artifact_id}--{self.commit[:7]}.stl"
        )

        def fail_copy(_source, _target, _destination_fd=None):
            final.write_bytes(b"concurrent-owner")
            raise OSError(errno.EIO, "injected generic reuse failure")

        self.argv_file.unlink(missing_ok=True)
        with mock.patch("plamp.cad_generation._copy_verified_artifact",
                        side_effect=fail_copy):
            result = self.generate(changed, output=output)
        self.assertEqual(result.status, "failed")
        self.assertEqual(final.read_bytes(), b"concurrent-owner")
        self.assertFalse(self.argv_file.exists())
        self.assertFalse(list(final.parent.glob(".*.reuse.tmp")))

    def test_archive_intermediate_symlinks_are_rejected(self):
        for component in ("cad", "prints", "fixture-system"):
            with self.subTest(component=component):
                data = self.root / f"data-{component}"
                outside = self.root / f"outside-{component}"
                outside.mkdir()
                if component == "cad":
                    data.mkdir()
                    (data / "cad").symlink_to(outside, target_is_directory=True)
                elif component == "prints":
                    (data / "cad").mkdir(parents=True)
                    (data / "cad" / "prints").symlink_to(outside, target_is_directory=True)
                else:
                    (data / "cad" / "prints").mkdir(parents=True)
                    (data / "cad" / "prints" / component).symlink_to(
                        outside, target_is_directory=True
                    )
                with self.assertRaises(OSError):
                    snapshot = prepare_source(self.repo, self.scad)
                    self.addCleanup(lambda snapshot=snapshot: shutil.rmtree(
                        snapshot.cleanup_root, ignore_errors=True
                    ))
                    generate_plan(
                        plan("first"), repo_root=self.repo, data_dir=data,
                        models={"fixture": self.model},
                        snapshots={"fixture": snapshot},
                        openscad=self.fake, env=self.env(), stdout=io.StringIO(),
                    )

    def test_archive_system_swap_is_detected_during_run_allocation(self):
        import plamp.cad_generation as generation
        archive, archive_fd = generation._open_archive_directory(
            self.data, "fixture-system"
        )
        moved = archive.with_name("fixture-system-moved")
        outside = self.root / "replacement-system"
        outside.mkdir()
        archive.rename(moved)
        archive.symlink_to(outside, target_is_directory=True)
        try:
            with self.assertRaisesRegex(OSError, "archive path changed"):
                generation._create_managed_run_directory(
                    archive, "run", plan("first"),
                    generation._generation_identity(
                        generation.plan_as_dict(plan("first")),
                        {"fixture": "source"},
                    ),
                    archive_fd,
                )
        finally:
            os.close(archive_fd)
        self.assertFalse((outside / "run").exists())

    def _swap_run_path(self, output, label):
        moved = self.root / f"held-{label}"
        outside = self.root / f"outside-{label}"
        output.rename(moved)
        outside.mkdir()
        output.symlink_to(outside, target_is_directory=True)
        return outside

    def test_post_claim_run_swap_before_source_never_writes_replacement(self):
        import plamp.cad_generation as generation
        output = self.root / "source-swap"
        real_copy = generation._copy_snapshot
        outside = None

        def swap_then_copy(*args, **kwargs):
            nonlocal outside
            outside = self._swap_run_path(output, "source")
            return real_copy(*args, **kwargs)

        with mock.patch("plamp.cad_generation._copy_snapshot",
                        side_effect=swap_then_copy), self.assertRaisesRegex(
                            OSError, "path changed"
                        ):
            self.generate(output=output)
        self.assertEqual(list(outside.iterdir()), [])

    def test_post_claim_run_swap_before_manifest_never_writes_replacement(self):
        import plamp.cad_generation as generation
        output = self.root / "manifest-swap"
        real_write = generation._write_manifest
        outside = None

        def swap_then_write(*args, **kwargs):
            nonlocal outside
            if outside is None:
                outside = self._swap_run_path(output, "manifest")
            return real_write(*args, **kwargs)

        with mock.patch("plamp.cad_generation._write_manifest",
                        side_effect=swap_then_write), self.assertRaisesRegex(
                            OSError, "path changed"
                        ):
            self.generate(output=output)
        self.assertEqual(list(outside.iterdir()), [])

    def test_post_claim_run_swap_before_render_never_starts_openscad(self):
        import plamp.cad_generation as generation
        output = self.root / "render-swap"
        real_write = generation._write_readme
        outside = None

        def swap_running_readme(run_dir, manifest, run_fd=None):
            nonlocal outside
            jobs = manifest.get("jobs", [])
            if outside is None and jobs and jobs[0].get("status") == "running":
                outside = self._swap_run_path(output, "render")
            return real_write(run_dir, manifest, run_fd)

        self.argv_file.unlink(missing_ok=True)
        with mock.patch("plamp.cad_generation._write_readme",
                        side_effect=swap_running_readme), self.assertRaisesRegex(
                            OSError, "path changed"
                        ):
            self.generate(output=output)
        self.assertTrue(self.argv_file.exists())
        self.assertNotIn("--export-format", json.loads(self.argv_file.read_text()))
        self.assertEqual(list(outside.iterdir()), [])

    def test_post_claim_run_swap_before_reuse_never_writes_replacement(self):
        import plamp.cad_generation as generation
        self.generate(plan("first"))
        changed = replace(plan("first"), jobs=(replace(
            plan("first").jobs[0], manufacturing_fingerprint="d" * 64,
        ),))
        output = self.root / "reuse-swap"
        real_copy = generation._copy_verified_artifact
        outside = None

        def swap_then_copy(source, target, destination_fd=None):
            nonlocal outside
            outside = self._swap_run_path(output, "reuse")
            return real_copy(source, target, destination_fd)

        with mock.patch("plamp.cad_generation._copy_verified_artifact",
                        side_effect=swap_then_copy), self.assertRaisesRegex(
                            OSError, "path changed"
                        ):
            self.generate(changed, output=output)
        self.assertEqual(list(outside.iterdir()), [])

    def test_popen_boundary_uses_anchored_source_output_and_swap_cleanup(self):
        output = self.root / "popen-swap"
        held = self.root / "held-popen"
        replacement = self.root / "outside-popen"
        real_popen = subprocess.Popen
        captured = []

        def swap_inside_popen(command, **kwargs):
            if "--export-format" not in command:
                return real_popen(command, **kwargs)
            captured.extend(command)
            output.rename(held)
            replacement.mkdir()
            output.symlink_to(replacement, target_is_directory=True)
            return real_popen(command, **kwargs)

        with mock.patch("plamp.cad_generation.subprocess.Popen",
                        side_effect=swap_inside_popen), self.assertRaisesRegex(
                            OSError, "path changed"
                        ):
            self.generate(output=output)
        output_arg = captured[captured.index("-o") + 1]
        self.assertRegex(output_arg, r"^/proc/self/fd/\d+/")
        self.assertRegex(captured[-1], r"/stage/repository/things/fixture/fixture\.scad$")
        self.assertEqual(list(replacement.iterdir()), [])
        self.assertFalse(list((held / "artifacts").glob("*.tmp.stl")))

    def test_popen_boundary_artifacts_swap_uses_retained_directory(self):
        output = self.root / "artifacts-popen-swap"
        held = self.root / "held-artifacts"
        replacement = self.root / "outside-artifacts"
        real_popen = subprocess.Popen

        def swap_inside_popen(command, **kwargs):
            if "-o" not in command:
                return real_popen(command, **kwargs)
            (output / "artifacts").rename(held)
            replacement.mkdir()
            (output / "artifacts").symlink_to(replacement, target_is_directory=True)
            return real_popen(command, **kwargs)

        with mock.patch("plamp.cad_generation.subprocess.Popen",
                        side_effect=swap_inside_popen), self.assertRaisesRegex(
                            OSError, "path changed"
                        ):
            self.generate(output=output)
        self.assertEqual(list(replacement.iterdir()), [])
        self.assertFalse(list(held.glob("*.tmp.stl")))

    def test_descriptor_anchoring_fails_safely_without_proc(self):
        read_fd, write_fd = os.pipe()
        try:
            with mock.patch("plamp.cad_generation.Path.is_dir", return_value=False), \
                    self.assertRaisesRegex(RuntimeError, "requires Linux /proc"):
                __import__("plamp.cad_generation", fromlist=["_proc_fd_path"])._proc_fd_path(
                    read_fd, "artifact.stl"
                )
        finally:
            os.close(read_fd)
            os.close(write_fd)

    def test_geometry_reuse_rejects_failed_artifact(self):
        source_plan = plan("first")
        first = self.generate(source_plan)
        manifest = load_run(first.run_dir)
        manifest["jobs"][0]["status"] = "failed"
        first.manifest_path.write_text(json.dumps(manifest))
        changed = replace(source_plan, jobs=(replace(
            source_plan.jobs[0], manufacturing_fingerprint="d" * 64,
        ),))
        zone = timezone(timedelta(hours=-10))
        with mock.patch("plamp.cad_generation._local_now", return_value=datetime(
            2026, 7, 23, 22, 20, tzinfo=zone,
        )):
            self.generate(changed)
        self.assertTrue(self.argv_file.exists())

    def test_geometry_reuse_rejects_missing_artifact(self):
        source_plan = plan("first")
        first = self.generate(source_plan)
        manifest = load_run(first.run_dir)
        (first.run_dir / manifest["jobs"][0]["artifact"]).unlink()
        self.argv_file.unlink()
        changed = replace(source_plan, jobs=(replace(
            source_plan.jobs[0], manufacturing_fingerprint="d" * 64,
        ),))
        with mock.patch("plamp.cad_generation._local_now", return_value=datetime(
            2026, 7, 23, 22, 20, tzinfo=timezone(timedelta(hours=-10)),
        )):
            self.generate(changed)
        self.assertTrue(self.argv_file.exists())

    def test_geometry_reuse_rejects_wrong_model_source_identity(self):
        source_plan = plan("first")
        first = self.generate(source_plan)
        manifest = load_run(first.run_dir)
        manifest["models"]["fixture"]["geometry_hash"] = "wrong-source"
        first.manifest_path.write_text(json.dumps(manifest))
        self.argv_file.unlink()
        changed = replace(source_plan, jobs=(replace(
            source_plan.jobs[0], manufacturing_fingerprint="d" * 64,
        ),))
        with mock.patch("plamp.cad_generation._local_now", return_value=datetime(
            2026, 7, 23, 22, 20, tzinfo=timezone(timedelta(hours=-10)),
        )):
            self.generate(changed)
        self.assertTrue(self.argv_file.exists())

    def test_multiple_collision_allocated_jobs_publish_distinct_artifacts(self):
        source_plan = plan("a", "a-2", "a-2-2")
        result = self.generate(source_plan)
        manifest = load_run(result.run_dir)
        artifact_names = [job["artifact"] for job in manifest["jobs"]]
        self.assertEqual(len(set(artifact_names)), 3)
        self.assertTrue(all((result.run_dir / name).is_file() for name in artifact_names))

    def test_exact_argv_uses_argument_list_and_effective_plan_values(self):
        result = self.generate()
        manifest = load_run(result.run_dir)
        command = manifest["jobs"][0]["command"]
        anchored_output = command[2]
        anchored_source = command[-1]
        self.assertRegex(anchored_output, r"^/proc/self/fd/\d+/\.first--")
        self.assertRegex(anchored_source, r"/stage/repository/things/fixture/fixture\.scad$")
        dependency_file = command[4]
        expected = [
            str(self.fake), "-o", anchored_output,
            "-d", dependency_file,
            "-D", f'revision_string="{self.commit[:7]}"',
            "-D", 'set="first"', "-D", "count=1", "-D", 'label="a b"',
            "-D", "enabled=true", "-D", "quality=$preview ? 2 : 20",
            "--export-format", "asciistl", anchored_source,
        ]
        self.assertEqual(command, expected)
        self.assertEqual(json.loads(self.argv_file.read_text()), command[1:])

    def test_generation_emits_exactly_one_selector_owned_set_define(self):
        source_plan = plan("first")
        unsafe_job = replace(
            source_plan.jobs[0],
            variables={**source_plan.jobs[0].variables, "set": "typed-override"},
            raw_defines={**source_plan.jobs[0].raw_defines, "set": '"raw-override"'},
        )
        unsafe_plan = replace(source_plan, jobs=(unsafe_job,))

        result = self.generate(unsafe_plan)
        command = load_run(result.run_dir)["jobs"][0]["command"]
        defines = [command[index + 1] for index, value in enumerate(command) if value == "-D"]

        self.assertEqual([value for value in defines if value.startswith("set=")],
                         ['set="first"'])

    def test_output_is_streamed_logged_and_statistics_are_extracted(self):
        stream = io.StringIO()
        result = self.generate(plan("first"), stdout=stream)
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
        result = self.generate(
            plan("first"),
            env=self.env(FAKE_ECHO=f'ECHO: ["PLAMP", "robot", ["touch", "{marker}"]]'),
            stdout=io.StringIO(),
        )
        message = load_run(result.run_dir)["jobs"][0]["messages"][0]
        self.assertEqual(message["channel"], "robot")
        self.assertFalse(marker.exists())

    def test_later_failure_keeps_completed_artifact_and_all_logs(self):
        result = self.generate(
            plan("first", "second"),
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
        result = self.generate(
            plan("first", "second"),
            env=self.env(FAKE_STATE_LOG=str(state_log)), stdout=io.StringIO(),
        )
        states = [json.loads(line) for line in state_log.read_text().splitlines()]
        self.assertEqual(states, [
            ["running", ["running", "queued"]],
            ["running", ["complete", "running"]],
        ])
        self.assertFalse(list(result.run_dir.glob(".manifest.json.*")))

    def test_empty_output_is_failure_and_never_publishes_artifact(self):
        result = self.generate(
            plan("first"),
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

        result = self.generate(
            plan("first"), openscad=disappearing, output=output,
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
                self.generate(
                    plan("first"), output=output,
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
                output=self.data / "cad" / "prints" / "fixture-system" / "older"
            )
        with mock.patch("plamp.cad_generation._utc_now", return_value=new_time):
            newer = self.generate(
                output=self.data / "cad" / "prints" / "fixture-system" / "newer"
            )
        self.assertEqual(
            [item["run_id"] for item in list_runs(self.data, "fixture-system")],
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
