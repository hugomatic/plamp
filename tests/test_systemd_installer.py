import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "deploy" / "systemd" / "install-plamp-web-service.sh"


class SystemdInstallerTests(unittest.TestCase):
    def print_unit(self) -> str:
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

        self.assertNotIn("/home/hugo", unit)
        self.assertNotIn("User=hugo", unit)


if __name__ == "__main__":
    unittest.main()
