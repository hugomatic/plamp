import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "deploy" / "bootstrap" / "install-plamp.sh"


class BootstrapInstallerTests(unittest.TestCase):
    def test_install_script_includes_mdns_runtime_and_tools(self):
        script = INSTALLER.read_text(encoding="utf-8")

        self.assertIn("avahi-daemon", script)
        self.assertIn("libnss-mdns", script)
        self.assertIn("avahi-utils", script)


if __name__ == "__main__":
    unittest.main()
