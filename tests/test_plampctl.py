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

    def run_with_stubs(self, *args: str, local_commit: str = "local", remote_commit: str = "remote") -> tuple[subprocess.CompletedProcess[str], str]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            bin_dir = root / "bin"
            repo.mkdir()
            bin_dir.mkdir()
            shutil.copy2(PLAMPCTL, repo / "plampctl")
            log = root / "calls.log"

            git_stub = textwrap.dedent(
                f"""\
                #!/usr/bin/env bash
                printf '%s\\n' "$(basename "$0") $*" >> {log}
                if [[ "$1" == "-C" ]]; then
                  shift 2
                fi
                if [[ "$1" == "rev-parse" && "$2" == "--verify" ]]; then
                  if [[ "$3" == origin/* ]]; then
                    printf '%s\\n' "{remote_commit}"
                  else
                    printf '%s\\n' "{local_commit}"
                  fi
                fi
                if [[ "$1" == "status" && "$2" == "--porcelain" ]]; then
                  exit 0
                fi
                if [[ "$1" == "log" ]]; then
                  printf '%s\\n' "remote change"
                fi
                """
            )
            command_stub = textwrap.dedent(
                f"""\
                #!/usr/bin/env bash
                printf '%s\\n' "$(basename "$0") $*" >> {log}
                """
            )
            self.make_script(bin_dir / "git", git_stub)
            self.make_script(bin_dir / "uv", command_stub)
            self.make_script(bin_dir / "sudo", command_stub)
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
        self.assertIn("log --format=%h %s local..origin/main", calls)
        self.assertIn("pull --ff-only origin main", calls)
        self.assertIn("uv sync --project", calls)
        self.assertIn("sudo systemctl restart plamp-web", calls)

    def test_upgrade_stops_when_branch_is_already_current(self):
        result, calls = self.run_with_stubs("upgrade", local_commit="same", remote_commit="same")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("fetch origin main", calls)
        self.assertIn("rev-parse --verify main", calls)
        self.assertIn("rev-parse --verify origin/main", calls)
        self.assertNotIn("switch main", calls)
        self.assertNotIn("pull --ff-only origin main", calls)
        self.assertNotIn("uv sync --project", calls)
        self.assertNotIn("sudo systemctl restart plamp-web", calls)
        self.assertIn("already up to date", result.stdout)

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
