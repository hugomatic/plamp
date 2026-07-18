import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from plamp.cli import main
from plamp.config import ConfigError, controller_pico_serial
from plamp.pico_transport import PicoFlashError


STATE = {
    "devices": [
        {
            "id": "lights",
            "type": "gpio",
            "pin": 2,
            "current_t": 0,
            "reschedule": 1,
            "pattern": [{"val": 1, "dur": 10}],
        }
    ]
}


class DirectCliTests(unittest.TestCase):
    def runtime_env(self, root):
        return {"PLAMP_ROOT": str(root), "PLAMP_DATA_DIR": str(root)}

    def write_config(self, root):
        path = root / "config.json"
        path.write_text(json.dumps({
            "controllers": {
                "tower": {"type": "pico_scheduler", "payload": {"pico_serial": "PICO-A"}}
            }
        }), encoding="utf-8")
        return path

    def test_help_uses_plamp_command_name(self):
        stdout = io.StringIO()
        with self.assertRaises(SystemExit) as caught:
            with contextlib.redirect_stdout(stdout):
                main(["--help"])
        self.assertEqual(caught.exception.code, 0)
        self.assertIn("usage: plamp", stdout.getvalue())
        self.assertNotIn("python -m plamp", stdout.getvalue())

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
                ["--lock-dir", str(root / "locks"), "pico", "report", "tower"],
                env=self.runtime_env(root),
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
                ["--lock-dir", str(root / "locks"), "pico", "report", "tower"],
                env=self.runtime_env(root),
                stdout=stdout,
                stderr=stderr,
                report_func=fail,
            )
            self.assertEqual(rc, 4)
            self.assertEqual(stdout.getvalue(), "")
            self.assertEqual(stderr.getvalue(), "Pico unplugged\n")

    def test_invalid_timeout_is_a_usage_error_without_calling_library(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self.write_config(Path(tmp))
            for timeout in ("-1", "nan", "inf", "-inf"):
                with self.subTest(timeout=timeout):
                    calls = []
                    stderr = io.StringIO()
                    with contextlib.redirect_stderr(stderr):
                        with self.assertRaises(SystemExit) as caught:
                            main(
                                ["--timeout", timeout, "pico", "report", "tower"],
                                env=self.runtime_env(config.parent),
                                report_func=lambda *args, **kwargs: calls.append((args, kwargs)),
                            )
                    self.assertEqual(caught.exception.code, 2)
                    self.assertEqual(calls, [])
                    self.assertIn("timeout", stderr.getvalue())

    def test_zero_timeout_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self.write_config(Path(tmp))
            calls = []
            rc = main(
                ["--timeout", "0", "pico", "report", "tower"],
                env=self.runtime_env(config.parent),
                stdout=io.StringIO(), stderr=io.StringIO(),
                report_func=lambda serial, **kwargs: calls.append(kwargs) or {"type": "report"},
            )
            self.assertEqual(rc, 0)
            self.assertEqual(calls[0]["timeout"], 0.0)

    def test_pico_pulse_calls_focused_library_operation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.write_config(root)
            stdout, stderr = io.StringIO(), io.StringIO()
            calls = []

            def fake_pulse(serial, pin, seconds, **kwargs):
                calls.append((serial, pin, seconds, kwargs))
                return {"type": "report", "content": {"devices": []}}

            rc = main(
                ["--lock-dir", str(root / "locks"), "pico", "pulse", "tower", "21", "5"],
                env=self.runtime_env(root),
                stdout=stdout,
                stderr=stderr,
                pulse_func=fake_pulse,
            )

        self.assertEqual(rc, 0)
        self.assertEqual(calls[0][:3], ("PICO-A", 21, 5))
        self.assertEqual(json.loads(stdout.getvalue())["type"], "report")
        self.assertEqual(stderr.getvalue(), "")

    def test_pico_configure_normalizes_state_before_calling_library(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_config(root)
            state_file = root / "state.json"
            state_file.write_text(json.dumps({**STATE, "report_every": 5}), encoding="utf-8")
            stdout, stderr = io.StringIO(), io.StringIO()
            calls = []

            def fake_configure(serial, state, **kwargs):
                calls.append((serial, state, kwargs))
                return {"type": "report", "content": {"devices": state["devices"]}}

            rc = main(
                ["pico", "configure", "tower", str(state_file)],
                env=self.runtime_env(root), stdout=stdout, stderr=stderr,
                configure_func=fake_configure,
            )

        self.assertEqual(rc, 0)
        self.assertEqual(calls[0][0], "PICO-A")
        self.assertEqual(calls[0][1], STATE)
        self.assertEqual(calls[0][2]["repo_root"], root.resolve())
        self.assertEqual(calls[0][2]["data_dir"], root.resolve())
        self.assertEqual(json.loads(stdout.getvalue())["type"], "report")
        self.assertEqual(stderr.getvalue(), "")

    def test_pico_configure_reads_state_from_stdin(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_config(root)
            calls = []

            rc = main(
                ["pico", "configure", "tower", "-"],
                env=self.runtime_env(root), stdin=io.StringIO(json.dumps(STATE)),
                stdout=io.StringIO(), stderr=io.StringIO(),
                configure_func=lambda serial, state, **kwargs: calls.append((serial, state)) or {},
            )

        self.assertEqual(rc, 0)
        self.assertEqual(calls, [("PICO-A", STATE)])

    def test_pico_state_errors_return_usage_error_before_hardware_access(self):
        invalid_cases = (
            ("missing.json", None),
            ("invalid.json", "{"),
            ("invalid-state.json", '{"devices":"wrong"}'),
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_config(root)
            for filename, content in invalid_cases:
                with self.subTest(filename=filename):
                    path = root / filename
                    if content is not None:
                        path.write_text(content, encoding="utf-8")
                    calls = []
                    stdout, stderr = io.StringIO(), io.StringIO()
                    rc = main(
                        ["pico", "configure", "tower", str(path)],
                        env=self.runtime_env(root), stdout=stdout, stderr=stderr,
                        configure_func=lambda *args, **kwargs: calls.append((args, kwargs)),
                    )
                    self.assertEqual(rc, 2)
                    self.assertEqual(calls, [])
                    self.assertEqual(stdout.getvalue(), "")
                    self.assertNotIn("Traceback", stderr.getvalue())

    def test_pico_configure_hardware_error_returns_four_without_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_config(root)
            state_file = root / "state.json"
            state_file.write_text(json.dumps(STATE), encoding="utf-8")
            stdout, stderr = io.StringIO(), io.StringIO()

            rc = main(
                ["pico", "configure", "tower", str(state_file)],
                env=self.runtime_env(root), stdout=stdout, stderr=stderr,
                configure_func=lambda *args, **kwargs: (_ for _ in ()).throw(ConnectionError("Pico unplugged")),
            )

        self.assertEqual(rc, 4)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "Pico unplugged\n")

    def test_pico_upgrade_prints_stable_identity_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_config(root)
            calls = []
            stdout, stderr = io.StringIO(), io.StringIO()

            result = {
                "report": {"type": "report", "content": {"devices": []}},
                "previous_identity": {"revision": "old", "protocol": 2, "name": "pico_scheduler"},
                "identity": {"revision": "new", "protocol": 2, "name": "pico_scheduler"},
            }
            rc = main(
                ["pico", "upgrade", "tower", "-"],
                env=self.runtime_env(root), stdin=io.StringIO(json.dumps(STATE)),
                stdout=stdout, stderr=stderr,
                upgrade_func=lambda serial, state, **kwargs: calls.append((serial, state, kwargs)) or result,
            )

        self.assertEqual(rc, 0)
        self.assertEqual(calls[0][0:2], ("PICO-A", STATE))
        self.assertEqual(json.loads(stdout.getvalue()), result)
        self.assertEqual(stdout.getvalue(), json.dumps(result, sort_keys=True) + "\n")
        self.assertEqual(stderr.getvalue(), "")

    def test_pico_upgrade_prints_null_previous_identity_for_legacy_pico(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_config(root)
            stdout, stderr = io.StringIO(), io.StringIO()
            result = {
                "report": {"type": "report", "content": {"devices": []}},
                "previous_identity": None,
                "identity": {"revision": "new", "protocol": 2, "name": "pico_scheduler"},
            }

            rc = main(
                ["pico", "upgrade", "tower", "-"],
                env=self.runtime_env(root), stdin=io.StringIO(json.dumps(STATE)),
                stdout=stdout, stderr=stderr,
                upgrade_func=lambda *args, **kwargs: result,
            )

        self.assertEqual(rc, 0)
        self.assertIsNone(json.loads(stdout.getvalue())["previous_identity"])
        self.assertEqual(stdout.getvalue(), json.dumps(result, sort_keys=True) + "\n")
        self.assertEqual(stderr.getvalue(), "")

    def test_pico_upgrade_failure_returns_four_without_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_config(root)
            stdout, stderr = io.StringIO(), io.StringIO()

            def fail(*args, **kwargs):
                raise PicoFlashError("firmware", 7, "", "copy failed")

            rc = main(
                ["pico", "upgrade", "tower", "-"],
                env=self.runtime_env(root), stdin=io.StringIO(json.dumps(STATE)),
                stdout=stdout, stderr=stderr, upgrade_func=fail,
            )

        self.assertEqual(rc, 4)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("copy failed", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_pico_help_lists_direct_configuration_commands(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout), self.assertRaises(SystemExit) as caught:
            main(["pico", "--help"])
        self.assertEqual(caught.exception.code, 0)
        self.assertIn("configure", stdout.getvalue())
        self.assertIn("upgrade", stdout.getvalue())

    def test_camera_capture_calls_shared_library_operation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.write_config(root)
            stdout, stderr = io.StringIO(), io.StringIO()
            calls = []

            def fake_capture(camera_id, **kwargs):
                calls.append((camera_id, kwargs))
                return {"camera_id": camera_id, "image_path": "data/pic.jpg"}

            rc = main(
                ["--lock-dir", str(root / "locks"), "camera", "capture", "cam0"],
                env=self.runtime_env(root),
                stdout=stdout,
                stderr=stderr,
                camera_capture_func=fake_capture,
            )

        self.assertEqual(rc, 0)
        self.assertEqual(calls[0][0], "cam0")
        self.assertEqual(calls[0][1]["config_file"], config)
        self.assertEqual(json.loads(stdout.getvalue())["camera_id"], "cam0")
        self.assertEqual(stderr.getvalue(), "")

    def test_context_prints_resolved_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stdout = io.StringIO()

            rc = main(["context"], env=self.runtime_env(root), stdout=stdout, stderr=io.StringIO())

            self.assertEqual(rc, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["root"], str(root.resolve()))
            self.assertEqual(payload["data_dir"], str(root.resolve()))
            self.assertEqual(payload["config_file"], str((root / "config.json").resolve()))

    def test_config_get_prints_validated_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_config(root)
            stdout = io.StringIO()

            rc = main(["config", "get"], env=self.runtime_env(root), stdout=stdout, stderr=io.StringIO())

            self.assertEqual(rc, 0)
            self.assertIn("tower", json.loads(stdout.getvalue())["controllers"])

    def test_config_write_reads_stdin_and_replaces_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_config(root)
            replacement = {"controllers": {}, "cameras": {}}
            stdout, stderr = io.StringIO(), io.StringIO()

            rc = main(
                ["config", "write", "-"],
                env=self.runtime_env(root),
                stdin=io.StringIO(json.dumps(replacement)),
                stdout=stdout,
                stderr=stderr,
            )

            self.assertEqual(rc, 0)
            self.assertEqual(json.loads((root / "config.json").read_text(encoding="utf-8")), replacement)
            self.assertEqual(json.loads(stdout.getvalue()), replacement)
            self.assertEqual(stderr.getvalue(), "")
