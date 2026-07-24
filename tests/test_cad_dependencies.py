from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import io
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from plamp.cad_dependencies import (
    CadDependencyError,
    DependencyRecord,
    DiscoveryEnvironment,
    cleanup_discovery_environment,
    content_hash,
    parse_make_dependencies,
    parse_openscad_info,
    prepare_discovery_environment,
    query_openscad_info,
    run_dependency_discovery,
    _extract_git_archive,
)
from plamp.cad_generation import _command


class CadDependencyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def write(self, relative: str, content: str | bytes = "") -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content)
        return path

    def job(self, set_name: str = "top_panel") -> SimpleNamespace:
        return SimpleNamespace(
            set_name=set_name,
            variables={"count": 1, "label": "a b", "enabled": True},
            raw_defines={"quality": "$preview ? 2 : 20"},
        )

    def test_make_dependencies_handle_continuations_spaces_and_escapes(self):
        expected = [
            self.write("root.scad"),
            self.write("lib file.scad"),
            self.write("nested/part.scad"),
            self.write("asset#1.svg"),
        ]
        path = self.write(
            "deps.d",
            "out.csg: root.scad lib\\ file.scad \\\n nested/part.scad asset\\#1.svg\n",
        )
        self.assertEqual(parse_make_dependencies(path, self.root), tuple(expected))

    def test_make_dependencies_handle_crlf_drive_target_and_duplicates(self):
        dependency = self.write("part.scad")
        path = self.write(
            "deps.d", "C:\\build\\out.csg: part.scad \\\r\n part.scad\r\n"
        )
        self.assertEqual(parse_make_dependencies(path, self.root), (dependency,))

    def test_make_dependencies_allow_whitespace_before_drive_target(self):
        dependency = self.write("part.scad")
        path = self.write("deps.d", "  C:\\build\\out.csg: part.scad\n")
        self.assertEqual(parse_make_dependencies(path, self.root), (dependency,))

    def test_make_dependencies_preserve_escaped_backslash(self):
        dependency = self.write(r"dir\part.scad")
        path = self.write("deps.d", r"out.csg: dir\\part.scad" + "\n")
        self.assertEqual(parse_make_dependencies(path, self.root), (dependency,))

    def test_make_dependencies_reject_missing_and_non_file_paths(self):
        directory = self.root / "folder"
        directory.mkdir()
        for text, message in (
            ("out: absent.scad\n", "does not exist"),
            ("out: folder\n", "not a file"),
        ):
            path = self.write("deps.d", text)
            with self.subTest(text=text), self.assertRaisesRegex(
                CadDependencyError, message
            ):
                parse_make_dependencies(path, self.root)

    def test_make_dependencies_reject_malformed_input(self):
        for text in ("out.csg root.scad\n", "out.csg: dangling\\"):
            path = self.write("deps.d", text)
            with self.subTest(text=text), self.assertRaises(CadDependencyError):
                parse_make_dependencies(path, self.root)

    def test_make_dependencies_wrap_invalid_path_tokens(self):
        path = self.write("deps.d", "out.csg: invalid\x00name.scad\n")
        with self.assertRaisesRegex(
            CadDependencyError, r"invalid.*invalid.*name\.scad"
        ):
            parse_make_dependencies(path, self.root)

    def test_parses_active_library_roots_from_openscad_info(self):
        info = parse_openscad_info(
            """OpenSCAD Version: 2021.01
User Library Path: /home/me/.local/share/OpenSCAD/libraries
OpenSCAD library path:
/home/me/.local/share/OpenSCAD/libraries
/opt/OpenSCAD/libraries

OPENSCAD_FONT_PATH:
"""
        )
        self.assertEqual(info.version, "2021.01")
        self.assertEqual(
            info.user_library_path,
            Path("/home/me/.local/share/OpenSCAD/libraries"),
        )
        self.assertEqual(
            info.library_paths,
            (
                Path("/home/me/.local/share/OpenSCAD/libraries"),
                Path("/opt/OpenSCAD/libraries"),
            ),
        )

    def test_info_parser_accepts_crlf_and_user_path_on_following_line(self):
        info = parse_openscad_info(
            "OpenSCAD Version: 2025.02.19\r\nUser Library Path:\r\n"
            "C:/Users/me/Documents/OpenSCAD/libraries\r\n"
            "OpenSCAD library path:\r\n/opt/lib\r\nOPENSCAD_FONT_PATH:\r\n"
        )
        self.assertEqual(info.version, "2025.02.19")
        self.assertEqual(
            info.user_library_path,
            Path("C:/Users/me/Documents/OpenSCAD/libraries"),
        )
        self.assertEqual(info.library_paths, (Path("/opt/lib"),))

    def test_info_parser_rejects_missing_version_or_library_section(self):
        for output in (
            "OpenSCAD library path:\n/opt/lib\n",
            "OpenSCAD Version: 2021.01\n",
            "OpenSCAD Version:\nOpenSCAD library path:\n",
        ):
            with self.subTest(output=output), self.assertRaises(
                CadDependencyError
            ):
                parse_openscad_info(output)

    @patch("plamp.cad_dependencies.subprocess.run")
    def test_query_uses_safe_argv_and_injected_environment(self, run):
        output = "OpenSCAD Version: 2021.01\nOpenSCAD library path:\n/opt/lib\n"
        run.return_value = subprocess.CompletedProcess([], 0, stdout=output)
        environment = {"OPENSCADPATH": "/chosen/library", "HOME": "/isolated"}
        info = query_openscad_info("/opt/OpenSCAD/bin/openscad", env=environment)
        self.assertEqual(info.version, "2021.01")
        run.assert_called_once_with(
            ["/opt/OpenSCAD/bin/openscad", "--info"],
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )

    @patch("plamp.cad_dependencies.subprocess.run")
    def test_query_reports_nonzero_status_and_output(self, run):
        run.return_value = subprocess.CompletedProcess([], 23, stdout="bad library")
        with self.assertRaisesRegex(CadDependencyError, "23.*bad library"):
            query_openscad_info("openscad")

    @patch("plamp.cad_dependencies.subprocess.run")
    def test_query_reports_process_launch_failure(self, run):
        run.side_effect = OSError("executable vanished")
        with self.assertRaisesRegex(CadDependencyError, "executable vanished"):
            query_openscad_info("/missing/openscad")

    def test_content_hash_reads_file_bytes(self):
        first = self.write("first.bin", b"same\x00bytes")
        second = self.write("second.bin", b"same\x00bytes")
        self.assertEqual(content_hash(first), content_hash(second))
        self.assertEqual(len(content_hash(first)), 64)
        second.write_bytes(b"different")
        self.assertNotEqual(content_hash(first), content_hash(second))

    def test_records_are_immutable(self):
        source = self.write("part.scad", "cube(1);")
        record = DependencyRecord(
            source_path=source,
            classification="model-local",
            logical_name="part.scad",
            archive_path=Path("model/part.scad"),
            content_hash=content_hash(source),
        )
        with self.assertRaises(FrozenInstanceError):
            record.logical_name = "changed"  # type: ignore[misc]

        info = parse_openscad_info(
            "OpenSCAD Version: 2021.01\nOpenSCAD library path:\n/opt/lib\n"
        )
        with self.assertRaises(FrozenInstanceError):
            info.version = "changed"  # type: ignore[misc]

    def init_repository(self) -> tuple[Path, Path]:
        repo = self.root / "repo"
        source = repo / "things/widget/widget.scad"
        source.parent.mkdir(parents=True)
        source.write_text("include <../../shared/lib.scad>\ncube(1);\n")
        (repo / "shared").mkdir()
        (repo / "shared/lib.scad").write_text("old geometry")
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-qm", "old"], check=True)
        return repo, source

    def revision(self, repo: Path) -> str:
        return subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"], check=True,
            text=True, stdout=subprocess.PIPE,
        ).stdout.strip()

    def test_historical_and_clean_discovery_archive_selected_repository_revision(self):
        repo, source = self.init_repository()
        old = self.revision(repo)
        (repo / "shared/lib.scad").write_text("new geometry")
        subprocess.run(["git", "-C", str(repo), "commit", "-am", "new", "-q"], check=True)
        unrelated = repo / "notes.txt"
        unrelated.write_text("uncommitted and irrelevant")

        old_env = prepare_discovery_environment(
            repo, source, revision=old, dirty=False
        )
        self.addCleanup(cleanup_discovery_environment, old_env)
        self.assertEqual((old_env.root / "shared/lib.scad").read_text(), "old geometry")
        self.assertEqual(old_env.revision, old)
        self.assertFalse(old_env.dirty)
        self.assertEqual(old_env.source_path.relative_to(old_env.root), Path("things/widget/widget.scad"))

        current = prepare_discovery_environment(repo, source, dirty=False)
        self.addCleanup(cleanup_discovery_environment, current)
        self.assertEqual((current.root / "shared/lib.scad").read_text(), "new geometry")
        self.assertNotEqual(current.root, repo)

    def test_dirty_discovery_references_worktree_and_requires_revision_label(self):
        repo, source = self.init_repository()
        source.write_text("cube(2);\n")
        with self.assertRaisesRegex(ValueError, "dirty.*revision label"):
            prepare_discovery_environment(repo, source, dirty=True)
        environment = prepare_discovery_environment(
            repo, source, dirty=True, revision_label="fit-1"
        )
        self.assertEqual(environment.root, repo.resolve())
        self.assertEqual(environment.source_path, source.resolve())
        self.assertTrue(environment.dirty)
        self.assertIsNone(environment.cleanup_root)

    def test_dirty_discovery_rejects_symlink_escape_and_directory_sources(self):
        repo, source = self.init_repository()
        outside = self.root / "outside.scad"
        outside.write_text("cube(9);\n")
        source.unlink()
        source.symlink_to(outside)
        with self.assertRaisesRegex(CadDependencyError, "symlink|inside"):
            prepare_discovery_environment(
                repo, source, dirty=True, revision_label="dirty-fit"
            )
        source.unlink()
        source.mkdir()
        with self.assertRaisesRegex(CadDependencyError, "regular file"):
            prepare_discovery_environment(
                repo, source, dirty=True, revision_label="dirty-fit"
            )

    def test_dirty_discovery_detects_source_replacement_during_validation(self):
        repo, source = self.init_repository()
        replacement = source.with_name("replacement.scad")
        replacement.write_text("cube(8);\n")
        real_open = os.open
        swapped = False

        def replace_before_open(path, flags, *args, **kwargs):
            nonlocal swapped
            if not swapped and Path(path) == source:
                swapped = True
                source.unlink()
                source.mkdir()
            return real_open(path, flags, *args, **kwargs)

        with patch("plamp.cad_dependencies.os.open", side_effect=replace_before_open):
            with self.assertRaisesRegex(CadDependencyError, "changed|regular file"):
                prepare_discovery_environment(
                    repo, source, dirty=True, revision_label="dirty-fit"
                )

    def test_historical_source_is_lexical_and_independent_of_current_symlinks(self):
        repo, source = self.init_repository()
        old = self.revision(repo)
        source.unlink()
        outside = self.root / "outside.scad"
        outside.write_text("wrong current content")
        source.symlink_to(outside)

        environment = prepare_discovery_environment(repo, source, revision=old)
        self.addCleanup(environment.cleanup)
        self.assertEqual(environment.source_path.read_text(), "include <../../shared/lib.scad>\ncube(1);\n")

    def test_historical_source_rejects_escape_and_reports_missing_at_revision(self):
        repo, source = self.init_repository()
        old = self.revision(repo)
        with self.assertRaisesRegex(CadDependencyError, "inside the repository"):
            prepare_discovery_environment(repo, repo / "../outside.scad", revision=old)
        later = repo / "things/later/later.scad"
        later.parent.mkdir()
        later.write_text("cube(2);\n")
        subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-qm", "later"], check=True)
        with self.assertRaisesRegex(CadDependencyError, "absent from revision"):
            prepare_discovery_environment(repo, later, revision=old)

    def test_archive_rejects_traversal_and_links_and_cleans_temporary_root(self):
        repo, source = self.init_repository()
        import io
        import tarfile

        for kind in ("traversal", "symlink"):
            stream = io.BytesIO()
            with tarfile.open(fileobj=stream, mode="w") as archive:
                member = tarfile.TarInfo("../escape" if kind == "traversal" else "bad-link")
                if kind == "symlink":
                    member.type = tarfile.SYMTYPE
                    member.linkname = "/outside"
                archive.addfile(member)
            completed = subprocess.CompletedProcess([], 0, stdout=stream.getvalue(), stderr=b"")
            with self.subTest(kind=kind), patch(
                "plamp.cad_dependencies.subprocess.run", return_value=completed
            ), patch(
                "plamp.cad_dependencies.shutil.rmtree", wraps=shutil.rmtree
            ) as remove:
                with self.assertRaisesRegex(CadDependencyError, "unsafe"):
                    prepare_discovery_environment(repo, source, dirty=False)
                remove.assert_called_once()

    def test_dependency_pass_uses_csg_exact_defines_environment_and_cwd(self):
        repo, source = self.init_repository()
        environment = DiscoveryEnvironment(repo, source, None, True, None)
        output = self.root / "discovery"
        fake = self.root / "fake-openscad"
        argv_log = self.root / "argv"
        cwd_log = self.root / "cwd"
        env_log = self.root / "env"
        fake.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, pathlib, sys\n"
            f"pathlib.Path({str(argv_log)!r}).write_text(json.dumps(sys.argv[1:]))\n"
            f"pathlib.Path({str(cwd_log)!r}).write_text(os.getcwd())\n"
            f"pathlib.Path({str(env_log)!r}).write_text(os.environ['OPENSCADPATH'])\n"
            "deps=pathlib.Path(sys.argv[sys.argv.index('-d')+1])\n"
            "deps.write_text('out: '+str(pathlib.Path(sys.argv[-1]).resolve())+'\\n')\n"
            "pathlib.Path(sys.argv[sys.argv.index('-o')+1]).write_text('csg')\n"
        )
        fake.chmod(0o755)
        job = self.job()
        result = run_dependency_discovery(
            fake, environment, job, output, revision="fit-7",
            env={"OPENSCADPATH": "/chosen", "PATH": "/usr/bin"}
        )
        self.assertEqual(result.argv[1:5], (
            "-o", str(output / "discovery.csg"), "-d", str(output / "discovery.d")
        ))
        self.assertIn('set="top_panel"', result.argv)
        self.assertIn('revision_string="fit-7"', result.argv)
        self.assertIn("count=1", result.argv)
        self.assertIn("quality=$preview ? 2 : 20", result.argv)
        self.assertNotIn("--export-format", result.argv)
        self.assertFalse(any(value.endswith(".stl") for value in result.argv))
        self.assertEqual(Path(cwd_log.read_text()), source.parent)
        self.assertEqual(env_log.read_text(), "/chosen")
        self.assertEqual(result.dependencies, (source.resolve(),))
        final = _command(Path(fake), self.root / "final.stl", source, "fit-7", job)
        discovery_defines = [
            result.argv[index + 1] for index, value in enumerate(result.argv) if value == "-D"
        ]
        final_defines = [
            final[index + 1] for index, value in enumerate(final) if value == "-D"
        ]
        self.assertEqual(discovery_defines, final_defines)

    def test_revision_define_controls_conditional_discovery_dependency(self):
        repo, source = self.init_repository()
        conditional = repo / "shared/historical.scad"
        conditional.write_text("historical")
        environment = DiscoveryEnvironment(repo, source, None, True, None)
        fake = self.root / "conditional-openscad"
        fake.write_text(
            "#!/usr/bin/env python3\n"
            "import pathlib, sys\n"
            "defines=[sys.argv[i+1] for i,v in enumerate(sys.argv) if v=='-D']\n"
            "assert 'revision_string=\"historical\"' in defines\n"
            "dep=pathlib.Path(sys.argv[-1]).parents[2]/'shared/historical.scad'\n"
            "pathlib.Path(sys.argv[sys.argv.index('-d')+1]).write_text('out: '+str(dep)+'\\n')\n"
        )
        fake.chmod(0o755)
        result = run_dependency_discovery(
            fake, environment, self.job(), self.root / "conditional",
            revision="historical", env={"PATH": "/usr/bin"},
        )
        self.assertEqual(result.dependencies, (conditional.resolve(),))

    def test_dependency_pass_reports_launch_failure_exit_and_missing_makefile(self):
        repo, source = self.init_repository()
        environment = DiscoveryEnvironment(repo, source, None, True, None)
        output = self.root / "failure"
        with self.assertRaisesRegex(CadDependencyError, "cannot run.*vanished"):
            run_dependency_discovery(
                self.root / "vanished", environment, self.job("one"), output,
                revision="fit-7", env={},
            )
        fake = self.root / "failing-openscad"
        fake.write_text("#!/bin/sh\necho diagnostic output\nexit 9\n")
        fake.chmod(0o755)
        with self.assertRaises(CadDependencyError) as raised:
            run_dependency_discovery(
                fake, environment, self.job("one"), output,
                revision="fit-7",
                env={"OPENSCADPATH": "/approved/lib", "SECRET_TOKEN": "never-show"},
            )
        message = str(raised.exception)
        self.assertIn("status 9", message)
        self.assertIn("diagnostic output", message)
        self.assertIn(repr(str(fake)), message)
        self.assertIn(f"cwd={source.parent!s}", message)
        self.assertIn("OPENSCADPATH", message)
        self.assertIn("/approved/lib", message)
        self.assertNotIn("SECRET_TOKEN", message)
        self.assertNotIn("never-show", message)
        fake.write_text("#!/bin/sh\nexit 0\n")
        output.mkdir(parents=True, exist_ok=True)
        (output / "discovery.d").write_text(f"old: {source}\n")
        (output / "discovery.csg").write_text("stale")
        with self.assertRaisesRegex(CadDependencyError, "did not produce.*discovery.d"):
            run_dependency_discovery(
                fake, environment, self.job("one"), output,
                revision="fit-7", env={},
            )

    def test_discovery_archive_cleanup_is_explicit_idempotent_and_never_removes_worktree(self):
        repo, source = self.init_repository()
        archived = prepare_discovery_environment(repo, source, dirty=False)
        archived_root = archived.root
        self.assertTrue(archived_root.is_dir())
        archived.cleanup()
        archived.cleanup()
        self.assertFalse(archived_root.exists())

        dirty = prepare_discovery_environment(
            repo, source, dirty=True, revision_label="working-fit"
        )
        cleanup_discovery_environment(dirty)
        self.assertTrue(repo.is_dir())

    def test_cleanup_rejects_forged_and_mutated_roots_without_deleting(self):
        repo, source = self.init_repository()
        arbitrary = self.root / "valuable"
        arbitrary.mkdir()
        forged = DiscoveryEnvironment(arbitrary, arbitrary / "x.scad", None, False, arbitrary)
        with self.assertRaisesRegex(CadDependencyError, "not owned"):
            cleanup_discovery_environment(forged)
        self.assertTrue(arbitrary.is_dir())

        archived = prepare_discovery_environment(repo, source)
        mutated = replace(archived, cleanup_root=arbitrary)
        with self.assertRaisesRegex(CadDependencyError, "does not match"):
            cleanup_discovery_environment(mutated)
        self.assertTrue(arbitrary.is_dir())
        self.assertTrue(archived.root.is_dir())

        archived.cleanup()

    def test_cleanup_tracks_owned_inode_across_validation_deletion_swap(self):
        repo, source = self.init_repository()
        archived = prepare_discovery_environment(repo, source)
        moved = archived.root.with_name(archived.root.name + "-moved")
        from plamp import cad_dependencies

        real_clear = cad_dependencies._clear_cleanup_descriptor
        swapped = False

        def swap_then_clear(descriptor):
            nonlocal swapped
            if not swapped:
                swapped = True
                archived.root.rename(moved)
                archived.root.mkdir()
                (archived.root / "replacement").write_text("keep")
            return real_clear(descriptor)

        with patch(
            "plamp.cad_dependencies._clear_cleanup_descriptor",
            side_effect=swap_then_clear,
        ):
            cleanup_discovery_environment(archived)
        self.assertEqual((archived.root / "replacement").read_text(), "keep")
        self.assertFalse(moved.exists())
        self.assertEqual(
            list(archived.root.parent.glob(f".{archived.root.name}.*")), []
        )
        shutil.rmtree(archived.root)

    def test_archive_applies_directory_modes_after_writing_children(self):
        import tarfile

        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w") as archive:
            directory = tarfile.TarInfo("locked")
            directory.type = tarfile.DIRTYPE
            directory.mode = 0o500
            archive.addfile(directory)
            payload = b"content"
            child = tarfile.TarInfo("locked/child.scad")
            child.size = len(payload)
            child.mode = 0o400
            archive.addfile(child, io.BytesIO(payload))
        destination = self.root / "modes"
        destination.mkdir()
        _extract_git_archive(stream.getvalue(), destination)
        self.assertEqual((destination / "locked/child.scad").read_text(), "content")
        self.assertEqual(stat.S_IMODE((destination / "locked").stat().st_mode), 0o500)


if __name__ == "__main__":
    unittest.main()
