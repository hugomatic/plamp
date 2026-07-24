from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from plamp.cad_dependencies import (
    CadDependencyError,
    DependencyRecord,
    content_hash,
    parse_make_dependencies,
    parse_openscad_info,
    query_openscad_info,
)


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


if __name__ == "__main__":
    unittest.main()
