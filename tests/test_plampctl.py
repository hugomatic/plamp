import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAMPCTL = ROOT / "plampctl"


class PlampctlTests(unittest.TestCase):
    def make_script(self, path: Path, body: str) -> None:
        path.write_text(body, encoding="utf-8")
        path.chmod(0o755)

    def run_with_stubs(self, *args: str) -> tuple[subprocess.CompletedProcess[str], str]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            bin_dir = root / "bin"
            repo.mkdir()
            bin_dir.mkdir()
            shutil.copy2(PLAMPCTL, repo / "plampctl")
            log = root / "calls.log"

            stub = textwrap.dedent(
                f"""\
                #!/usr/bin/env bash
                printf '%s\\n' "$(basename "$0") $*" >> {log}
                """
            )
            self.make_script(bin_dir / "git", stub)
            self.make_script(bin_dir / "uv", stub)
            self.make_script(bin_dir / "sudo", stub)
            env = dict(os.environ)
            env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"

            result = subprocess.run(
                [str(repo / "plampctl"), *args],
                cwd=repo,
                env=env,
                text=True,
                capture_output=True,
            )
            return result, log.read_text(encoding="utf-8") if log.exists() else ""

    def test_upgrade_pulls_main_syncs_and_restarts_by_default(self):
        result, calls = self.run_with_stubs("upgrade")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("git -C", calls)
        self.assertIn("fetch origin main", calls)
        self.assertIn("switch main", calls)
        self.assertIn("pull --ff-only origin main", calls)
        self.assertIn("uv sync --project", calls)
        self.assertIn("sudo systemctl restart plamp-web", calls)

    def test_upgrade_accepts_optional_branch(self):
        result, calls = self.run_with_stubs("upgrade", "feature-x")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("fetch origin feature-x", calls)
        self.assertIn("switch feature-x", calls)
        self.assertIn("pull --ff-only origin feature-x", calls)

    def test_upgrade_rejects_extra_args(self):
        result, _ = self.run_with_stubs("upgrade", "main", "extra")

        self.assertEqual(result.returncode, 2)
        self.assertIn("upgrade accepts at most one branch", result.stderr)


if __name__ == "__main__":
    unittest.main()
