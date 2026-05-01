import io
import json
import tempfile
import unittest
from pathlib import Path

from plamp_cli.io import InputError, format_json_output, load_json_input, render_table


class PlampCliIoTests(unittest.TestCase):
    def test_load_json_input_reads_at_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "payload.json"
            path.write_text(json.dumps({"ok": True}), encoding="utf-8")

            self.assertEqual(load_json_input(f"@{path}", stdin=io.StringIO("")), {"ok": True})

    def test_load_json_input_missing_at_file_raises_input_error(self):
        with self.assertRaises(InputError):
            load_json_input("@/definitely/missing/plamp-payload.json", stdin=io.StringIO(""))

    def test_load_json_input_directory_path_raises_input_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(InputError):
                load_json_input(f"@{tmp}", stdin=io.StringIO(""))

    def test_load_json_input_reads_stdin_marker(self):
        self.assertEqual(load_json_input("-", stdin=io.StringIO('{"ok": true}')), {"ok": True})

    def test_format_json_output_pretty_adds_indent(self):
        output = format_json_output({"ok": True}, pretty=True)
        self.assertEqual(output, '{\n  "ok": true\n}\n')

    def test_format_json_output_compact_returns_single_line_json(self):
        output = format_json_output({"ok": True}, pretty=False)
        self.assertEqual(output, '{"ok": true}\n')

    def test_render_table_formats_rows(self):
        output = render_table([
            {"name": "pump", "state": "on"},
            {"name": "fan", "state": "off"},
        ])

        self.assertEqual(
            output,
            "name | state\n"
            "----+-----\n"
            "pump | on   \n"
            "fan  | off  \n",
        )

    def test_render_table_sanitizes_newlines_and_keeps_missing_columns(self):
        output = render_table([
            {"name": "pump", "note": "line one\nline two"},
            {"name": "fan", "note": None, "state": "idle"},
        ])

        self.assertIn("line one line two", output)
        self.assertNotIn("line one\nline two", output)
        self.assertIn("state", output)
        self.assertIn("idle", output)
