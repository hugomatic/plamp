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

    def test_pico_scheduler_get_missing_controller_prints_example(self):
        stdout = StringIO()
        stderr = StringIO()

        with redirect_stderr(stderr):
            code = main(["pico-scheduler", "get"], stdout=stdout, stderr=stderr)

        self.assertNotEqual(code, 0)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("the following arguments are required: controller", stderr.getvalue())
        self.assertIn("Example: plamp pico-scheduler get pump_n_lights", stderr.getvalue())

    def test_pico_scheduler_wrong_argument_order_prints_example_and_try(self):
        stdout = StringIO()
        stderr = StringIO()

        with redirect_stderr(stderr):
            code = main(["pico-scheduler", "pump_n_lights", "get"], stdout=stdout, stderr=stderr)

        self.assertNotEqual(code, 0)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("invalid choice", stderr.getvalue())
        self.assertIn("Example: plamp pico-scheduler get pump_n_lights", stderr.getvalue())
        self.assertIn("Try: plamp pico-scheduler list", stderr.getvalue())

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

    def test_main_py_runs_as_direct_script(self):
        repo_root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            ["/usr/bin/python3", "plamp_cli/main.py", "--help"],
            cwd=repo_root,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        self.assertEqual(result.returncode, 0, msg=f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
        self.assertIn("{config,controllers,pico-scheduler,pics}", result.stdout)
        self.assertNotIn("timers", result.stdout)


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
    def test_controllers_list_groups_pico_scheduler_ids(self, request_json):
        request_json.return_value = {"roles": ["pump_lights"], "channels": {}, "time_format": "12h"}
        stdout = StringIO()
        stderr = StringIO()

        code = main(["controllers", "list"], stdout=stdout, stderr=stderr)

        self.assertEqual(code, 0)
        self.assertEqual(stdout.getvalue(), '{"controllers": {"pico_scheduler": {"ids": ["pump_lights"]}}}\n')
        self.assertEqual(stderr.getvalue(), "")
        request_json.assert_called_once_with("GET", "http://127.0.0.1:8000", "/api/timer-config")

    @patch("plamp_cli.main.request_json")
    def test_pico_scheduler_list_returns_ids_only(self, request_json):
        request_json.return_value = {"roles": ["pump_lights"], "channels": {}, "time_format": "12h"}
        stdout = StringIO()
        stderr = StringIO()

        code = main(["pico-scheduler", "list"], stdout=stdout, stderr=stderr)

        self.assertEqual(code, 0)
        self.assertEqual(stdout.getvalue(), '{"ids": ["pump_lights"]}\n')
        self.assertEqual(stderr.getvalue(), "")
        request_json.assert_called_once_with("GET", "http://127.0.0.1:8000", "/api/timer-config")

    @patch("plamp_cli.main.request_json")
    def test_timers_list_alias_is_not_available(self, request_json):
        request_json.return_value = {"roles": ["pump_lights"], "channels": {}, "time_format": "12h"}
        stdout = StringIO()
        stderr = StringIO()

        with redirect_stderr(stderr):
            code = main(["timers", "list"], stdout=stdout, stderr=stderr)

        self.assertNotEqual(code, 0)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("invalid choice", stderr.getvalue())
        request_json.assert_not_called()

    @patch("plamp_cli.main.request_json")
    @patch("plamp_cli.main.load_json_input")
    def test_pico_scheduler_set_puts_controller_state(self, load_json_input, request_json):
        load_json_input.return_value = {"devices": [{"id": "pump", "enabled": True}], "report_every": 10}
        request_json.return_value = {"role": "pump_lights", "success": True}
        stdout = StringIO()
        stderr = StringIO()

        code = main(["pico-scheduler", "set", "pump_lights", "@state.json"], stdout=stdout, stderr=stderr)

        self.assertEqual(code, 0)
        self.assertEqual(stdout.getvalue(), '{"controller": "pump_lights", "success": true}\n')
        self.assertEqual(stderr.getvalue(), "")
        request_json.assert_called_once_with(
            "PUT",
            "http://127.0.0.1:8000",
            "/api/timers/pump_lights",
            {"devices": [{"id": "pump", "enabled": True}], "report_every": 10},
        )

    @patch("plamp_cli.main.request_json")
    def test_pico_scheduler_get_returns_devices_state(self, request_json):
        request_json.return_value = {"devices": [{"id": "pump", "enabled": True}], "report_every": 10}
        stdout = StringIO()
        stderr = StringIO()

        code = main(["pico-scheduler", "get", "pump_lights"], stdout=stdout, stderr=stderr)

        self.assertEqual(code, 0)
        self.assertEqual(stdout.getvalue(), '{"devices": [{"enabled": true, "id": "pump"}], "report_every": 10}\n')
        self.assertEqual(stderr.getvalue(), "")
        request_json.assert_called_once_with("GET", "http://127.0.0.1:8000", "/api/timers/pump_lights")

    @patch("plamp_cli.main.request_json", side_effect=ApiError(404, "unknown timer role: pump_n_ligths"))
    def test_pico_scheduler_get_unknown_controller_prints_hint(self, request_json):
        stdout = StringIO()
        stderr = StringIO()

        code = main(["pico-scheduler", "get", "pump_n_ligths"], stdout=stdout, stderr=stderr)

        self.assertEqual(code, 3)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("API 404: unknown pico-scheduler controller: pump_n_ligths", stderr.getvalue())
        self.assertIn("Try: plamp pico-scheduler list", stderr.getvalue())
        self.assertIn("Example: plamp pico-scheduler get pump_n_lights", stderr.getvalue())
        request_json.assert_called_once_with("GET", "http://127.0.0.1:8000", "/api/timers/pump_n_ligths")

    @patch("plamp_cli.main.request_json")
    @patch("plamp_cli.main.load_json_input")
    def test_pico_scheduler_channels_set_schedule_returns_channel_state(self, load_json_input, request_json):
        load_json_input.return_value = {"minutes": [0, 15, 30, 45]}
        request_json.return_value = {"channel": "main", "role": "pump_lights", "success": True}
        stdout = StringIO()
        stderr = StringIO()

        code = main(
            ["pico-scheduler", "channels", "set-schedule", "pump_lights", "main", "@schedule.json"],
            stdout=stdout,
            stderr=stderr,
        )

        self.assertEqual(code, 0)
        self.assertEqual(stdout.getvalue(), '{"channel": "main", "controller": "pump_lights", "success": true}\n')
        self.assertEqual(stderr.getvalue(), "")
        request_json.assert_called_once_with(
            "POST",
            "http://127.0.0.1:8000",
            "/api/timers/pump_lights/channels/main/schedule",
            {"minutes": [0, 15, 30, 45]},
        )

    @patch("plamp_cli.main.request_json")
    def test_pico_scheduler_get_renders_table_output(self, request_json):
        request_json.return_value = {"mode": "auto"}
        stdout = StringIO()
        stderr = StringIO()

        code = main(["--table", "pico-scheduler", "get", "pump_lights"], stdout=stdout, stderr=stderr)

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
        self.assertIn("invalid choice", stderr.getvalue())


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

    @patch("plamp_cli.main.download_bytes")
    def test_pics_get_out_writes_binary_file(self, download_bytes):
        download_bytes.return_value = b"jpeg-bytes"
        stderr = StringIO()

        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "latest.jpg"
            code = main(["pics", "get", "grow:latest", "--out", str(out_path)], stderr=stderr)

            self.assertEqual(code, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertEqual(out_path.read_bytes(), b"jpeg-bytes")

        download_bytes.assert_called_once_with("http://127.0.0.1:8000", "/api/camera/images/grow:latest")


class PlampCliDocsTests(unittest.TestCase):
    def test_readmes_match_pico_scheduler_cli_shape(self):
        cli_readme = Path("plamp_cli/README.md").read_text(encoding="utf-8")
        root_readme = Path("README.md").read_text(encoding="utf-8")
        web_readme = Path("plamp_web/README.md").read_text(encoding="utf-8")

        self.assertIn("JSON-first", cli_readme)
        self.assertIn("python3 -m pip install --user --no-deps --editable /home/hugo/.openclaw/workspace/code/plamp", cli_readme)
        self.assertIn("uv run python -m plamp_cli --help", cli_readme)
        self.assertIn("uv run python -m plamp_cli config get", cli_readme)
        self.assertIn("uv run python -m plamp_cli controllers list", cli_readme)
        self.assertIn("uv run python -m plamp_cli pico-scheduler list", cli_readme)
        self.assertIn("uv run python -m plamp_cli pics get <image_key> --out latest.jpg", cli_readme)
        self.assertIn("--stdout", cli_readme)
        self.assertIn("ssh localhost /home/hugo/.local/bin/plamp pics get <image_key> --stdout > latest.jpg", cli_readme)
        self.assertNotIn("uv run python -m plamp_cli timers", cli_readme)

        self.assertIn("plamp config get", root_readme)
        self.assertIn("plamp controllers list", root_readme)
        self.assertIn("plamp pico-scheduler list", root_readme)
        self.assertNotIn("plamp timers", root_readme)
        self.assertNotIn("data/timers/<controller>.json", root_readme)
        self.assertNotIn("schedule events", root_readme)

        self.assertIn("- `/` - main Pico scheduler page", web_readme)
        self.assertIn("## Pico Scheduler State", web_readme)
        self.assertIn("state files keep device state", web_readme)
        self.assertNotIn("timers and camera", web_readme)
        self.assertNotIn("## Timer State", web_readme)
        self.assertNotIn("schedule devices", web_readme)
