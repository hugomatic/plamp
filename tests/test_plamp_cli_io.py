import io
import json
import tempfile
import unittest
from pathlib import Path

from plamp_cli.io import format_json_output, load_json_input, render_table


class PlampCliIoTests(unittest.TestCase):
    def test_load_json_input_reads_at_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "payload.json"
            path.write_text(json.dumps({"ok": True}), encoding="utf-8")

            self.assertEqual(load_json_input(f"@{path}", stdin=io.StringIO("")), {"ok": True})

    def test_load_json_input_reads_stdin_marker(self):
        self.assertEqual(load_json_input("-", stdin=io.StringIO('{"ok": true}')), {"ok": True})

    def test_format_json_output_pretty_adds_indent(self):
        output = format_json_output({"ok": True}, pretty=True)
        self.assertEqual(output, '{\n  "ok": true\n}\n')

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
