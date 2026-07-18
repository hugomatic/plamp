import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class SetupShTests(unittest.TestCase):
    def make_checkout(self, parent: Path, name: str) -> Path:
        root = parent / name
        root.mkdir()
        shutil.copy2(REPO_ROOT / "setup.sh", root / "setup.sh")
        (root / "bin").mkdir()
        shutil.copy2(REPO_ROOT / "bin" / "plamp", root / "bin" / "plamp")
        venv_bin = root / ".venv" / "bin"
        venv_bin.mkdir(parents=True)
        python = venv_bin / "python"
        python.write_text(
            "#!/usr/bin/env bash\n"
            "printf 'python=%s\\n' \"$0\"\n"
            "printf 'pythonpath=%s\\n' \"${PYTHONPATH:-}\"\n"
            "printf 'arg=%s\\n' \"$@\"\n",
            encoding="utf-8",
        )
        python.chmod(0o755)
        return root

    def run_bash(self, script: str) -> list[str]:
        completed = subprocess.run(
            ["bash", "--noprofile", "--norc", "-c", script],
            cwd=REPO_ROOT,
            env={"HOME": os.environ["HOME"], "PATH": "/usr/bin:/bin"},
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        return completed.stdout.splitlines()

    def test_default_context_uses_checkout_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_checkout(Path(tmp), "checkout")

            lines = self.run_bash(
                f'source "{root}/setup.sh" >/dev/null\n'
                'printf "%s\\n%s\\n" "$PLAMP_ROOT" "$PLAMP_DATA_DIR"'
            )

            self.assertEqual(lines, [str(root), str(root / "data")])

    def test_setup_exposes_direct_module_launcher_with_hidden_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_checkout(Path(tmp), "checkout")

            lines = self.run_bash(
                f'source "{root}/setup.sh" >/dev/null\n'
                'command -v plamp\n'
                'plamp pico report pump_lights'
            )

            self.assertEqual(
                lines,
                [
                    str(root / "bin" / "plamp"),
                    f"python={root}/.venv/bin/python",
                    f"pythonpath={root}",
                    "arg=-m",
                    "arg=plamp",
                    "arg=pico",
                    "arg=report",
                    "arg=pump_lights",
                ],
            )

    def test_launcher_reports_missing_environment_without_invoking_uv(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_checkout(Path(tmp), "checkout")
            (root / ".venv" / "bin" / "python").unlink()

            completed = subprocess.run(
                [root / "bin" / "plamp", "--help"],
                cwd=Path(tmp),
                env={"HOME": os.environ["HOME"], "PATH": "/usr/bin:/bin"},
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            self.assertNotEqual(completed.returncode, 0)
            self.assertEqual(completed.stdout, "")
            self.assertIn("Plamp environment is missing", completed.stderr)
            self.assertIn(f"{root}/plampctl reinstall", completed.stderr)
            self.assertNotIn("uv", completed.stderr.lower())
            self.assertNotIn("traceback", completed.stderr.lower())

    def test_second_activation_removes_first_checkout_from_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            first = self.make_checkout(parent, "first")
            second = self.make_checkout(parent, "second")
            second_data = parent / "second-data"

            lines = self.run_bash(
                f'source "{first}/setup.sh" >/dev/null\n'
                f'source "{second}/setup.sh" "{second_data}" >/dev/null\n'
                'printf "%s\\n%s\\n%s\\n" "$PLAMP_ROOT" "$PLAMP_DATA_DIR" "$PATH"'
            )

            self.assertEqual(lines[0], str(second))
            self.assertEqual(lines[1], str(second_data))
            self.assertEqual(
                lines[2],
                f"{second}/bin:{second}/.venv/bin:{second}:/usr/bin:/bin",
            )
            self.assertNotIn(str(first), lines[2])


if __name__ == "__main__":
    unittest.main()
