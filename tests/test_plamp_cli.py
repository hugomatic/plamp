import unittest
import subprocess
import tempfile
from contextlib import redirect_stderr
from io import BytesIO, StringIO
from pathlib import Path
from unittest.mock import patch

from plamp_cli.http import ApiError, NetworkError
from plamp_cli.io import InputError
from plamp_cli.main import _generate_firmware_source, build_parser, main


class PlampCliBootstrapTests(unittest.TestCase):
    def test_build_parser_accepts_config_get_shape(self):
        parser = build_parser()
        args = parser.parse_args(["config", "get"])

        self.assertEqual(args.area, "config")
        self.assertEqual(args.action, "get")

    def test_build_parser_accepts_system_status_shape(self):
        parser = build_parser()
        args = parser.parse_args(["system", "status"])

        self.assertEqual(args.area, "system")
        self.assertEqual(args.system_action, "status")

    def test_build_parser_accepts_status_shape(self):
        parser = build_parser()
        args = parser.parse_args(["status", "--path", "controllers.pump_lights"])

        self.assertEqual(args.area, "status")
        self.assertEqual(args.path, ["controllers.pump_lights"])

    def test_main_returns_zero_for_help(self):
        code = main(["--help"])
        self.assertEqual(code, 0)

    def test_main_without_args_prints_help_and_returns_zero(self):
        stdout = StringIO()
        stderr = StringIO()
        code = main([], stdout=stdout, stderr=stderr)
        self.assertEqual(code, 0)
        self.assertIn("usage: plamp", stdout.getvalue())
        self.assertEqual(stderr.getvalue(), "")

    def test_main_returns_nonzero_for_missing_required_nested_subcommand(self):
        self.assertNotEqual(main(["config"]), 0)

    def test_main_missing_area_with_flags_prints_choices_hint(self):
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stderr(stderr):
            code = main(["--pretty"], stdout=stdout, stderr=stderr)
        self.assertNotEqual(code, 0)
        self.assertIn("missing top-level command section", stderr.getvalue())
        self.assertIn("Choices: config, controllers, system, status, pico-scheduler, pics, firmware", stderr.getvalue())

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
        self.assertIn("status", result.stdout)
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

    def test_config_devices_subcommand_is_removed(self):
        stdout = StringIO()
        stderr = StringIO()

        with redirect_stderr(stderr):
            code = main(["config", "devices", "get"], stdout=stdout, stderr=stderr)

        self.assertNotEqual(code, 0)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("invalid choice", stderr.getvalue())

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
    def test_config_get_table_falls_back_to_json_for_root_envelope(self, request_json):
        request_json.return_value = {
            "config": {
                "controllers": {
                    "main": {
                        "type": "pico_scheduler",
                        "payload": {"report_every": 10, "devices": [{"pin": 3, "type": "gpio", "pattern": []}]},
                        "settings": {"devices": {"pump": {"pin": 3, "editor": {"kind": "cycle"}}}},
                    }
                },
                "cameras": {},
            }
        }
        stdout = StringIO()
        stderr = StringIO()

        code = main(["--table", "config", "get"], stdout=stdout, stderr=stderr)

        self.assertEqual(code, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(
            stdout.getvalue(),
            '{"config": {"cameras": {}, "controllers": {"main": {"payload": {"devices": [{"pattern": [], "pin": 3, "type": "gpio"}], "report_every": 10}, "settings": {"devices": {"pump": {"editor": {"kind": "cycle"}, "pin": 3}}}, "type": "pico_scheduler"}}}}\n',
        )
        request_json.assert_called_once_with("GET", "http://127.0.0.1:8000", "/api/config")


class PlampCliSystemTests(unittest.TestCase):
    @patch("plamp_cli.main.request_json")
    def test_system_status_reads_api_status(self, request_json):
        request_json.return_value = {
            "software": {
                "git_branch": "main",
                "git_commit": "8d92806abcdef",
                "git_short_commit": "8d92806",
                "git_dirty": False,
            }
        }
        stdout = StringIO()
        stderr = StringIO()

        code = main(["system", "status"], stdout=stdout, stderr=stderr)

        self.assertEqual(code, 0)
        self.assertEqual(
            stdout.getvalue(),
            '{"software": {"git_branch": "main", "git_commit": "8d92806abcdef", "git_dirty": false, "git_short_commit": "8d92806"}}\n',
        )
        self.assertEqual(stderr.getvalue(), "")
        request_json.assert_called_once_with("GET", "http://127.0.0.1:8000", "/api/system")

    @patch("plamp_cli.main.request_json")
    def test_system_status_table_shows_branch_and_commit(self, request_json):
        request_json.return_value = {
            "hostname": "sprout",
            "software": {
                "git_branch": "main",
                "git_commit": "8d92806abcdef",
                "git_short_commit": "8d92806",
                "git_dirty": False,
            },
        }
        stdout = StringIO()
        stderr = StringIO()

        code = main(["--table", "system", "status"], stdout=stdout, stderr=stderr)

        self.assertEqual(code, 0)
        self.assertIn("git_branch | main", stdout.getvalue())
        self.assertIn("git_commit | 8d92806", stdout.getvalue())
        self.assertIn("hostname   | sprout", stdout.getvalue())
        self.assertEqual(stderr.getvalue(), "")
        request_json.assert_called_once_with("GET", "http://127.0.0.1:8000", "/api/system")


class PlampCliStatusTests(unittest.TestCase):
    @patch("plamp_cli.main.stream_json_events")
    def test_status_streams_status_endpoint_with_path_filters(self, stream_json_events):
        stream_json_events.return_value = iter([{"ok": True}])
        stdout = StringIO()
        stderr = StringIO()

        code = main(
            ["status", "--path", "controllers.pump_lights", "--path", "controllers.grow"],
            stdout=stdout,
            stderr=stderr,
        )

        self.assertEqual(code, 0)
        self.assertEqual(stdout.getvalue(), '{"ok": true}\n')
        self.assertEqual(stderr.getvalue(), "")
        stream_json_events.assert_called_once_with(
            "http://127.0.0.1:8000",
            "/api/status?stream=true&path=controllers.pump_lights&path=controllers.grow",
        )


class PlampCliTimerTests(unittest.TestCase):
    @patch("plamp_cli.main.request_json")
    def test_controllers_list_groups_pico_scheduler_ids(self, request_json):
        request_json.return_value = {
            "controllers": {
                "pump_lights": {"firmware": "pico_scheduler"}
            }
        }
        stdout = StringIO()
        stderr = StringIO()

        code = main(["controllers", "list"], stdout=stdout, stderr=stderr)

        self.assertEqual(code, 0)
        self.assertEqual(
            stdout.getvalue(),
            '{"controllers": {"pump_lights": {"firmware": "pico_scheduler"}}}\n',
        )
        self.assertEqual(stderr.getvalue(), "")
        request_json.assert_called_once_with("GET", "http://127.0.0.1:8000", "/api/controllers")

    @patch("plamp_cli.main.request_json")
    def test_pico_scheduler_list_returns_ids_only(self, request_json):
        request_json.return_value = {
            "controllers": {
                "pump_lights": {"firmware": "pico_scheduler"}
            }
        }
        stdout = StringIO()
        stderr = StringIO()

        code = main(["pico-scheduler", "list"], stdout=stdout, stderr=stderr)

        self.assertEqual(code, 0)
        self.assertEqual(stdout.getvalue(), '{"ids": ["pump_lights"]}\n')
        self.assertEqual(stderr.getvalue(), "")
        request_json.assert_called_once_with("GET", "http://127.0.0.1:8000", "/api/controllers")

    @patch("plamp_cli.main.request_json")
    def test_controllers_get_uses_status_path_filter(self, request_json):
        request_json.return_value = [
            {"path": "controllers.pump_lights", "value": {"firmware": "pico_scheduler"}}
        ]
        stdout = StringIO()
        stderr = StringIO()

        code = main(["controllers", "get", "pump_lights"], stdout=stdout, stderr=stderr)

        self.assertEqual(code, 0)
        self.assertEqual(stdout.getvalue(), '{"firmware": "pico_scheduler"}\n')
        self.assertEqual(stderr.getvalue(), "")
        request_json.assert_called_once_with(
            "GET",
            "http://127.0.0.1:8000",
            "/api/status",
            query={"path": "controllers.pump_lights"},
        )

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
        request_json.return_value = {"controller": "pump_lights", "success": True}
        stdout = StringIO()
        stderr = StringIO()

        code = main(["pico-scheduler", "set", "pump_lights", "@state.json"], stdout=stdout, stderr=stderr)

        self.assertEqual(code, 0)
        self.assertEqual(stdout.getvalue(), '{"controller": "pump_lights", "success": true}\n')
        self.assertEqual(stderr.getvalue(), "")
        request_json.assert_called_once_with(
            "PUT",
            "http://127.0.0.1:8000",
            "/api/controllers/pump_lights",
            {"devices": [{"id": "pump", "enabled": True}], "report_every": 10},
        )

    @patch("plamp_cli.main.request_json")
    def test_pico_scheduler_get_returns_devices_state(self, request_json):
        request_json.return_value = [
            {
                "path": "controllers.pump_lights",
                "value": {"devices": [{"id": "pump", "enabled": True}], "report_every": 10},
            }
        ]
        stdout = StringIO()
        stderr = StringIO()

        code = main(["pico-scheduler", "get", "pump_lights"], stdout=stdout, stderr=stderr)

        self.assertEqual(code, 0)
        self.assertEqual(stdout.getvalue(), '{"devices": [{"enabled": true, "id": "pump"}], "report_every": 10}\n')
        self.assertEqual(stderr.getvalue(), "")
        request_json.assert_called_once_with(
            "GET",
            "http://127.0.0.1:8000",
            "/api/status",
            query={"path": "controllers.pump_lights"},
        )

    @patch("plamp_cli.main.request_json", side_effect=ApiError(404, "unknown status path: controllers.pump_n_ligths"))
    def test_pico_scheduler_get_unknown_controller_prints_hint(self, request_json):
        stdout = StringIO()
        stderr = StringIO()

        code = main(["pico-scheduler", "get", "pump_n_ligths"], stdout=stdout, stderr=stderr)

        self.assertEqual(code, 3)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("API 404: unknown pico-scheduler controller: pump_n_ligths", stderr.getvalue())
        self.assertIn("Try: plamp pico-scheduler list", stderr.getvalue())
        self.assertIn("Example: plamp pico-scheduler get pump_n_lights", stderr.getvalue())
        request_json.assert_called_once_with(
            "GET",
            "http://127.0.0.1:8000",
            "/api/status",
            query={"path": "controllers.pump_n_ligths"},
        )

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
            "/api/controllers/pump_lights/channels/main/schedule",
            {"minutes": [0, 15, 30, 45]},
        )

    @patch("plamp_cli.main.request_json")
    def test_pico_scheduler_pulse_posts_pin_duration(self, request_json):
        request_json.return_value = {"controller": "pump_lights", "pin": 21, "seconds": 5, "success": True}
        stdout = StringIO()
        stderr = StringIO()

        code = main(
            ["pico-scheduler", "pulse", "pump_lights", "21", "--seconds", "5"],
            stdout=stdout,
            stderr=stderr,
        )

        self.assertEqual(code, 0)
        self.assertEqual(stdout.getvalue(), '{"controller": "pump_lights", "pin": 21, "seconds": 5, "success": true}\n')
        self.assertEqual(stderr.getvalue(), "")
        request_json.assert_called_once_with(
            "POST",
            "http://127.0.0.1:8000",
            "/api/controllers/pump_lights/pins/21/pulse",
            {"seconds": 5},
        )

    @patch("plamp_cli.main.request_json")
    def test_pico_scheduler_get_renders_table_output(self, request_json):
        request_json.return_value = [{"path": "controllers.pump_lights", "value": {"mode": "auto"}}]
        stdout = StringIO()
        stderr = StringIO()

        code = main(["--table", "pico-scheduler", "get", "pump_lights"], stdout=stdout, stderr=stderr)

        self.assertEqual(code, 0)
        self.assertEqual(stdout.getvalue(), "key  | value\n----+-----\nmode | auto \n")
        self.assertEqual(stderr.getvalue(), "")
        request_json.assert_called_once_with(
            "GET",
            "http://127.0.0.1:8000",
            "/api/status",
            query={"path": "controllers.pump_lights"},
        )

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
    def test_pics_list_uses_camera_captures_endpoint_with_camera_filter(self, request_json):
        request_json.return_value = {"captures": [], "limit": 24, "offset": 0, "has_more": False, "total": 0}
        stdout = StringIO()
        stderr = StringIO()

        code = main(["pics", "list", "--camera-id", "rpicam_cam0", "--limit", "5"], stdout=stdout, stderr=stderr)

        self.assertEqual(code, 0)
        self.assertEqual(stderr.getvalue(), "")
        request_json.assert_called_once_with(
            "GET",
            "http://127.0.0.1:8000",
            "/api/camera/captures",
            query={"camera_id": "rpicam_cam0", "limit": 5, "offset": 0},
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


class PlampCliFirmwareTests(unittest.TestCase):
    def test_firmware_families_lists_only_scheduler(self):
        stdout = StringIO()
        stderr = StringIO()

        code = main(["firmware", "families"], stdout=stdout, stderr=stderr)

        self.assertEqual(code, 0)
        self.assertEqual(stdout.getvalue(), '{"families": ["pico_scheduler"]}\n')
        self.assertEqual(stderr.getvalue(), "")

    def test_unimplemented_doser_generation_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unsupported firmware family"):
            _generate_firmware_source("pico_doser", {}, None)

    def test_scheduler_generation_rejects_nonempty_payload_until_state_seeding_exists(self):
        payload = {
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

        with self.assertRaisesRegex(ValueError, "persistent state seeding is unavailable"):
            _generate_firmware_source("pico_scheduler", payload, "tower")

    def test_scheduler_generation_allows_empty_generic_firmware(self):
        source = _generate_firmware_source("pico_scheduler", {"devices": []}, "tower")

        self.assertIn('FIRMWARE_REVISION = "local-cli"', source)

    @patch("plamp_cli.main.subprocess.Popen")
    @patch("plamp_cli.main._run_command")
    @patch("plamp_cli.main.load_json_input")
    def test_scheduler_flash_rejects_nonempty_payload_before_hardware_mutation(self, load_json_input, run_command, popen):
        load_json_input.return_value = {
            "devices": [{"id": "lights", "type": "gpio", "pin": 2, "current_t": 0,
                         "reschedule": 1, "pattern": [{"val": 1, "dur": 10}]}]
        }
        stdout = StringIO()
        stderr = StringIO()

        code = main(
            ["firmware", "flash", "--firmware", "pico_scheduler", "--controller", "tower", "payload.json", "--port", "/dev/ttyACM0"],
            stdout=stdout,
            stderr=stderr,
        )

        self.assertEqual(code, 2)
        self.assertIn("persistent state seeding is unavailable", stderr.getvalue())
        self.assertEqual(stdout.getvalue(), "")
        popen.assert_not_called()
        run_command.assert_not_called()

    def test_scheduler_generation_rejects_invalid_payload_before_rendering(self):
        with self.assertRaisesRegex(ValueError, "devices must be a list"):
            _generate_firmware_source("pico_scheduler", {"devices": "bad"}, "tower")

    @patch("plamp_cli.main._run_command")
    def test_firmware_pull_defaults_to_stdout(self, run_command):
        run_command.return_value = (0, "print('hello')\n", "")
        stdout = BytesIO()
        stderr = StringIO()

        code = main(["firmware", "pull", "--port", "/dev/ttyACM0"], stdout=stdout, stderr=stderr)

        self.assertEqual(code, 0)
        self.assertEqual(stdout.getvalue(), b"print('hello')\n")
        self.assertEqual(stderr.getvalue(), "")

    @patch("plamp_cli.main._run_command")
    def test_firmware_show_writes_stdout(self, run_command):
        run_command.return_value = (0, "print('hello')\n", "")
        stdout = BytesIO()
        stderr = StringIO()

        code = main(["firmware", "show", "--port", "/dev/ttyACM0"], stdout=stdout, stderr=stderr)

        self.assertEqual(code, 0)
        self.assertEqual(stdout.getvalue(), b"print('hello')\n")
        self.assertEqual(stderr.getvalue(), "")

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
    def test_readmes_match_new_camera_cli_shape(self):
        cli_readme = Path("plamp_cli/README.md").read_text(encoding="utf-8")
        root_readme = Path("README.md").read_text(encoding="utf-8")
        web_readme = Path("plamp_web/README.md").read_text(encoding="utf-8")

        self.assertIn("JSON-first", cli_readme)
        self.assertNotIn("pip install", cli_readme)
        self.assertIn("python3 -m plamp_cli --help", cli_readme)
        self.assertIn("python3 -m plamp_cli config get", cli_readme)
        self.assertIn("python3 -m plamp_cli controllers list", cli_readme)
        self.assertIn("python3 -m plamp_cli pico-scheduler list", cli_readme)
        self.assertIn("python3 -m plamp_cli pics list --camera-id rpicam_cam0", cli_readme)
        self.assertIn("python3 -m plamp_cli --pretty pics take --camera-id rpicam_cam0", cli_readme)
        self.assertIn("python3 -m plamp_cli pics get <image_key> --out latest.jpg", cli_readme)
        self.assertIn("--stdout", cli_readme)
        self.assertIn("python3 -m plamp_cli pics get <image_key> --stdout", cli_readme)
        self.assertNotIn("/home/hugo/.local/bin/plamp", cli_readme)
        self.assertNotIn("camera_roll", cli_readme)
        self.assertNotIn("python3 -m plamp_cli timers", cli_readme)

        self.assertIn("plamp context", root_readme)
        self.assertIn("plamp config get", root_readme)
        self.assertIn("plamp pico report pump_lights", root_readme)
        self.assertIn("plamp camera capture rpicam_cam0", root_readme)
        self.assertNotIn("plamp controllers list", root_readme)
        self.assertNotIn("plamp pico-scheduler list", root_readme)
        self.assertNotIn("plamp pics list", root_readme)
        self.assertNotIn("plamp timers", root_readme)
        self.assertNotIn("data/timers/<controller>.json", root_readme)
        self.assertNotIn("schedule events", root_readme)

        self.assertIn("- `/` - static main Pico scheduler and camera client", web_readme)
        self.assertIn("runtime state through REST and SSE", web_readme)
        self.assertIn("## Pico Scheduler State", web_readme)
        self.assertIn("state files keep device state", web_readme)
        self.assertNotIn("timers and camera", web_readme)
        self.assertNotIn("## Timer State", web_readme)
        self.assertNotIn("schedule devices", web_readme)
