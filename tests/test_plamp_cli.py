import unittest
import subprocess
import tempfile
from io import StringIO
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
    def test_config_get_rejects_table_flag(self, request_json):
        stdout = StringIO()
        stderr = StringIO()

        code = main(["--table", "config", "get"], stdout=stdout, stderr=stderr)

        self.assertEqual(code, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("--table is not supported for config commands", stderr.getvalue())
        request_json.assert_not_called()
