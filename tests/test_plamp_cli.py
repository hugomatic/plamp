import unittest
import subprocess
import tempfile
from pathlib import Path

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
