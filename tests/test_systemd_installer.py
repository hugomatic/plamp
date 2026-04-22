import subprocess
import tempfile
import unittest
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "deploy" / "systemd" / "install-plamp-web-service.sh"


class SystemdInstallerTests(unittest.TestCase):
    def print_unit(self, env: dict[str, str] | None = None) -> str:
        result = subprocess.run(
            [
                "bash",
                str(INSTALLER),
                "--print-unit",
                "--user",
                "plantbot",
                "--repo-root",
                "/opt/plamp",
                "--uv",
                "/usr/local/bin/uv",
            ],
            check=True,
            text=True,
            capture_output=True,
            env=env,
        )
        return result.stdout

    def test_print_unit_uses_supplied_user_paths_and_port(self):
        unit = self.print_unit()

        self.assertIn("User=plantbot\n", unit)
        self.assertIn("WorkingDirectory=/opt/plamp\n", unit)
        self.assertIn("RequiresMountsFor=/opt/plamp\n", unit)
        self.assertIn(
            "ExecStart=/usr/local/bin/uv run uvicorn plamp_web.server:app --host 127.0.0.1 --port 8000\n",
            unit,
        )

    def test_print_unit_has_boot_and_restart_settings(self):
        unit = self.print_unit()

        self.assertIn("After=network.target\n", unit)
        self.assertIn("Restart=on-failure\n", unit)
        self.assertIn("RestartSec=3\n", unit)
        self.assertIn("WantedBy=multi-user.target\n", unit)

    def test_print_unit_has_no_machine_specific_user(self):
        unit = self.print_unit()

        self.assertNotIn("User=hugo", unit)

    def test_print_unit_adds_mpremote_directory_to_service_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp)
            mpremote = bin_dir / "mpremote"
            mpremote.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            mpremote.chmod(0o755)
            env = dict(os.environ)
            env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"

            unit = self.print_unit(env=env)

        self.assertIn(
            f"Environment=PATH={bin_dir}:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\n",
            unit,
        )


if __name__ == "__main__":
    unittest.main()
