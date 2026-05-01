import unittest
import subprocess
import tempfile
from contextlib import redirect_stderr
from io import BytesIO, StringIO
from pathlib import Path
from unittest.mock import patch

from plamp_cli.http import ApiError, NetworkError
from plamp_cli.io import InputError
from plamp_cli.main import build_parser, main


class PlampCliBootstrapTests(unittest.TestCase):
    def test_build_parser_accepts_config_get_shape(self):
        parser = build_parser()
        args = parser.parse_args(["config", "get"])

        self.assertEqual(args.area, "config")
        self.assertEqual(args.action, "get")

    def test_main_returns_zero_for_help(self):
        code = main(["--help"])
        self.assertEqual(code, 0)

    def test_main_returns_nonzero_for_missing_required_subcommand(self):
        self.assertNotEqual(main([]), 0)
        self.assertNotEqual(main(["config"]), 0)

    def test_package_installs_with_console_script(self):
        repo_root = Path(__file__).resolve().parents[1]
        python = Path("/usr/bin/python3")
        self.assertTrue(python.exists())
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [
                    python,
                    "-m",
                    "pip",
                    "install",
                    "--no-deps",
                    "--no-build-isolation",
                    "--target",
                    tmpdir,
                    str(repo_root),
                ],
                cwd=repo_root,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            self.assertEqual(
                result.returncode,
                0,
                msg=f"pip install failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}",
            )
            self.assertTrue((Path(tmpdir) / "plamp_cli" / "__init__.py").exists())


class PlampCliConfigTests(unittest.TestCase):
    @patch("plamp_cli.main.request_json")
    def test_config_get_calls_api_config(self, request_json):
        request_json.return_value = {"config": {"controllers": {}}, "detected": {"picos": [], "cameras": []}}
        stdout = StringIO()
        stderr = StringIO()

        code = main(["config", "get"], stdout=stdout, stderr=stderr)

        self.assertEqual(code, 0)
        request_json.assert_called_once_with("GET", "http://127.0.0.1:8000", "/api/config")
        self.assertEqual(
            stdout.getvalue(),
            '{"config": {"controllers": {}}, "detected": {"cameras": [], "picos": []}}\n',
        )
        self.assertEqual(stderr.getvalue(), "")

    @patch("plamp_cli.main.request_json")
    @patch("plamp_cli.main.load_json_input")
    def test_config_devices_set_calls_section_endpoint(self, load_json_input, request_json):
        load_json_input.return_value = {"pump": {"controller": "timer", "pin": 3, "editor": "cycle"}}
        request_json.return_value = {"config": {"devices": {}}, "detected": {"picos": [], "cameras": []}}

        code = main(["config", "devices", "set", "@devices.json"], stdout=StringIO(), stderr=StringIO())

        self.assertEqual(code, 0)
        request_json.assert_called_once_with(
            "PUT",
            "http://127.0.0.1:8000",
            "/api/config/devices",
            {"pump": {"controller": "timer", "pin": 3, "editor": "cycle"}},
        )

    @patch("plamp_cli.main.request_json")
    def test_config_devices_get_returns_section_payload(self, request_json):
        request_json.return_value = {
            "config": {
                "controllers": {"main": {}},
                "devices": {"pump": {"controller": "timer"}},
                "cameras": {},
            },
            "detected": {"picos": [], "cameras": []},
        }
        stdout = StringIO()
        stderr = StringIO()

        code = main(["config", "devices", "get"], stdout=stdout, stderr=stderr)

        self.assertEqual(code, 0)
        self.assertEqual(stdout.getvalue(), '{"pump": {"controller": "timer"}}\n')
        self.assertEqual(stderr.getvalue(), "")
        request_json.assert_called_once_with("GET", "http://127.0.0.1:8000", "/api/config")

    @patch("plamp_cli.main.request_json")
    @patch("plamp_cli.main.load_json_input", side_effect=InputError("invalid JSON input: Expecting value"))
    def test_config_set_input_error_returns_exit_code_five(self, load_json_input, request_json):
        stdout = StringIO()
        stderr = StringIO()

        code = main(["config", "set", "@config.json"], stdout=stdout, stderr=stderr)

        self.assertEqual(code, 5)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("invalid JSON input: Expecting value", stderr.getvalue())
        request_json.assert_not_called()

    @patch("plamp_cli.main.request_json", side_effect=ApiError(422, "bad payload"))
    def test_config_get_api_error_returns_exit_code_three(self, request_json):
        stdout = StringIO()
        stderr = StringIO()

        code = main(["config", "get"], stdout=stdout, stderr=stderr)

        self.assertEqual(code, 3)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("API 422: bad payload", stderr.getvalue())

    @patch("plamp_cli.main.request_json", side_effect=NetworkError("connection refused"))
    def test_config_get_network_error_returns_exit_code_four(self, request_json):
        stdout = StringIO()
        stderr = StringIO()

        code = main(["config", "get"], stdout=stdout, stderr=stderr)

        self.assertEqual(code, 4)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("connection refused", stderr.getvalue())

    @patch("plamp_cli.main.request_json")
    def test_config_devices_get_renders_table_output(self, request_json):
        request_json.return_value = {
            "config": {
                "controllers": {},
                "devices": {
                    "pump": {"controller": "timer", "pin": 3},
                    "fan": {"controller": "timer", "pin": 4},
                },
                "cameras": {},
            },
            "detected": {"picos": [], "cameras": []},
        }
        stdout = StringIO()
        stderr = StringIO()

        code = main(["--table", "config", "devices", "get"], stdout=stdout, stderr=stderr)

        self.assertEqual(code, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(
            stdout.getvalue(),
            "id   | controller | pin\n"
            "----+----------+---\n"
            "pump | timer      | 3  \n"
            "fan  | timer      | 4  \n",
        )
        request_json.assert_called_once_with("GET", "http://127.0.0.1:8000", "/api/config")

    @patch("plamp_cli.main.request_json")
    def test_config_get_table_falls_back_to_json_for_root_envelope(self, request_json):
        request_json.return_value = {
            "config": {
                "controllers": {"main": {"type": "pico_scheduler"}},
                "devices": {"pump": {"controller": "main", "pin": 3}},
                "cameras": {},
            },
            "detected": {"picos": [{"serial": "ABC"}], "cameras": []},
        }
        stdout = StringIO()
        stderr = StringIO()

        code = main(["--table", "config", "get"], stdout=stdout, stderr=stderr)

        self.assertEqual(code, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(
            stdout.getvalue(),
            '{"config": {"cameras": {}, "controllers": {"main": {"type": "pico_scheduler"}}, "devices": {"pump": {"controller": "main", "pin": 3}}}, "detected": {"cameras": [], "picos": [{"serial": "ABC"}]}}\n',
        )
        request_json.assert_called_once_with("GET", "http://127.0.0.1:8000", "/api/config")


class PlampCliTimerTests(unittest.TestCase):
    @patch("plamp_cli.main.request_json")
    def test_timers_list_calls_timer_config(self, request_json):
        request_json.return_value = {"roles": ["pump_lights"], "channels": {}, "time_format": "12h"}
        stdout = StringIO()
        stderr = StringIO()

        code = main(["timers", "list"], stdout=stdout, stderr=stderr)

        self.assertEqual(code, 0)
        self.assertEqual(stdout.getvalue(), '{"channels": {}, "roles": ["pump_lights"], "time_format": "12h"}\n')
        self.assertEqual(stderr.getvalue(), "")
        request_json.assert_called_once_with("GET", "http://127.0.0.1:8000", "/api/timer-config")

    @patch("plamp_cli.main.request_json")
    @patch("plamp_cli.main.load_json_input")
    def test_timers_set_puts_role_state(self, load_json_input, request_json):
        load_json_input.return_value = {"report_every": 10, "events": []}
        request_json.return_value = {"role": "pump_lights", "success": True}
        stdout = StringIO()
        stderr = StringIO()

        code = main(["timers", "set", "pump_lights", "@state.json"], stdout=stdout, stderr=stderr)

        self.assertEqual(code, 0)
        self.assertEqual(stdout.getvalue(), '{"role": "pump_lights", "success": true}\n')
        self.assertEqual(stderr.getvalue(), "")
        request_json.assert_called_once_with(
            "PUT",
            "http://127.0.0.1:8000",
            "/api/timers/pump_lights",
            {"report_every": 10, "events": []},
        )

    @patch("plamp_cli.main.request_json")
    def test_timers_get_returns_role_state(self, request_json):
        request_json.return_value = {"enabled": True, "mode": "auto"}
        stdout = StringIO()
        stderr = StringIO()

        code = main(["timers", "get", "pump_lights"], stdout=stdout, stderr=stderr)

        self.assertEqual(code, 0)
        self.assertEqual(stdout.getvalue(), '{"enabled": true, "mode": "auto"}\n')
        self.assertEqual(stderr.getvalue(), "")
        request_json.assert_called_once_with("GET", "http://127.0.0.1:8000", "/api/timers/pump_lights")

    @patch("plamp_cli.main.request_json")
    @patch("plamp_cli.main.load_json_input")
    def test_timers_channels_set_schedule_returns_channel_state(self, load_json_input, request_json):
        load_json_input.return_value = {"minutes": [0, 15, 30, 45]}
        request_json.return_value = {"channel_id": "main", "success": True}
        stdout = StringIO()
        stderr = StringIO()

        code = main(
            ["timers", "channels", "set-schedule", "pump_lights", "main", "@schedule.json"],
            stdout=stdout,
            stderr=stderr,
        )

        self.assertEqual(code, 0)
        self.assertEqual(stdout.getvalue(), '{"channel_id": "main", "success": true}\n')
        self.assertEqual(stderr.getvalue(), "")
        request_json.assert_called_once_with(
            "POST",
            "http://127.0.0.1:8000",
            "/api/timers/pump_lights/channels/main/schedule",
            {"minutes": [0, 15, 30, 45]},
        )

    @patch("plamp_cli.main.request_json")
    def test_timers_get_renders_table_output(self, request_json):
        request_json.return_value = {"mode": "auto"}
        stdout = StringIO()
        stderr = StringIO()

        code = main(["--table", "timers", "get", "pump_lights"], stdout=stdout, stderr=stderr)

        self.assertEqual(code, 0)
        self.assertEqual(stdout.getvalue(), "key  | value\n----+-----\nmode | auto \n")
        self.assertEqual(stderr.getvalue(), "")
        request_json.assert_called_once_with("GET", "http://127.0.0.1:8000", "/api/timers/pump_lights")

    def test_bare_timers_returns_nonzero(self):
        stdout = StringIO()
        stderr = StringIO()

        with redirect_stderr(stderr):
            code = main(["timers"], stdout=stdout, stderr=stderr)

        self.assertNotEqual(code, 0)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("the following arguments are required", stderr.getvalue())


class PlampCliPictureTests(unittest.TestCase):
    @patch("plamp_cli.main.request_json")
    def test_pics_list_uses_camera_captures_endpoint(self, request_json):
        request_json.return_value = {"captures": [], "limit": 24, "offset": 0, "has_more": False, "total": 0}
        stdout = StringIO()
        stderr = StringIO()

        code = main(["pics", "list", "--source", "grow", "--limit", "5"], stdout=stdout, stderr=stderr)

        self.assertEqual(code, 0)
        self.assertEqual(stderr.getvalue(), "")
        request_json.assert_called_once_with(
            "GET",
            "http://127.0.0.1:8000",
            "/api/camera/captures",
            query={"source": "grow", "limit": 5, "offset": 0},
        )

    @patch("plamp_cli.main.request_json")
    def test_pics_take_posts_camera_capture_request(self, request_json):
        request_json.return_value = {"capture_id": "cap-123", "success": True}
        stdout = StringIO()
        stderr = StringIO()

        code = main(["pics", "take", "--camera-id", "front"], stdout=stdout, stderr=stderr)

        self.assertEqual(code, 0)
        self.assertEqual(stderr.getvalue(), "")
        request_json.assert_called_once_with(
            "POST",
            "http://127.0.0.1:8000",
            "/api/camera/captures",
            query={"camera_id": "front"},
        )

    @patch("plamp_cli.main.download_bytes")
    def test_pics_get_stdout_streams_binary(self, download_bytes):
        download_bytes.return_value = b"jpeg-bytes"

        class BinaryStdout:
            def __init__(self):
                self.buffer = BytesIO()

        stdout = BinaryStdout()
        stderr = StringIO()

        code = main(["pics", "get", "grow:latest", "--stdout"], stdout=stdout, stderr=stderr)

        self.assertEqual(code, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(stdout.buffer.getvalue(), b"jpeg-bytes")
        download_bytes.assert_called_once_with("http://127.0.0.1:8000", "/api/camera/images/grow:latest")
