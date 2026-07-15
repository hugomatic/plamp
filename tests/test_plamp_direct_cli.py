import io
import json
import tempfile
import unittest
from pathlib import Path

from plamp.cli import main
from plamp.config import ConfigError, controller_pico_serial


class DirectCliTests(unittest.TestCase):
    def write_config(self, root):
        path = root / "config.json"
        path.write_text(json.dumps({
            "controllers": {
                "tower": {"type": "pico_scheduler", "payload": {"pico_serial": "PICO-A"}}
            }
        }), encoding="utf-8")
        return path

    def test_controller_serial_reads_existing_config_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_config(Path(tmp))
            self.assertEqual(controller_pico_serial(path, "tower"), "PICO-A")

    def test_unknown_controller_is_clear_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_config(Path(tmp))
            with self.assertRaisesRegex(ConfigError, "missing"):
                controller_pico_serial(path, "missing")

    def test_pico_report_calls_library_and_prints_stable_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.write_config(root)
            stdout, stderr = io.StringIO(), io.StringIO()
            calls = []

            def fake_report(serial, **kwargs):
                calls.append((serial, kwargs))
                return {"type": "report", "content": {"devices": []}}

            rc = main(
                ["--config", str(config), "--lock-dir", str(root / "locks"), "pico", "report", "tower"],
                stdout=stdout,
                stderr=stderr,
                report_func=fake_report,
            )
            self.assertEqual(rc, 0)
            self.assertEqual(json.loads(stdout.getvalue())["type"], "report")
            self.assertEqual(calls[0][0], "PICO-A")
            self.assertEqual(stderr.getvalue(), "")

    def test_hardware_error_returns_nonzero_without_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.write_config(root)
            stdout, stderr = io.StringIO(), io.StringIO()

            def fail(*args, **kwargs):
                raise ConnectionError("Pico unplugged")

            rc = main(
                ["--config", str(config), "--lock-dir", str(root / "locks"), "pico", "report", "tower"],
                stdout=stdout,
                stderr=stderr,
                report_func=fail,
            )
            self.assertEqual(rc, 4)
            self.assertEqual(stdout.getvalue(), "")
            self.assertEqual(stderr.getvalue(), "Pico unplugged\n")
