import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "deploy" / "bootstrap" / "install-plamp.sh"


def package_group(script: str, name: str) -> list[str]:
    match = re.search(
        rf"^{name}=\(\n(?P<body>.*?)^\)$",
        script,
        re.MULTILINE | re.DOTALL,
    )
    if match is None:
        raise AssertionError(f"missing package group: {name}")
    return match.group("body").split()


class BootstrapInstallerTests(unittest.TestCase):
    def test_host_tools_documentation_is_linked_and_covers_agent_commands(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        tools_doc = (ROOT / "docs" / "host-tools.md").read_text(encoding="utf-8")

        self.assertIn("[Host tools](./docs/host-tools.md)", readme)
        for command in (
            "rg",
            "gh",
            "shellcheck",
            "jq",
            "lsusb",
            "lsof",
            "strace",
            "openscad",
        ):
            self.assertIn(f"`{command}`", tools_doc)
        self.assertIn("sed -n", tools_doc)
        self.assertIn("sed -i.bak", tools_doc)
        self.assertIn("CPU- and memory-heavy", tools_doc)

    def test_install_script_separates_runtime_dependencies(self):
        script = INSTALLER.read_text(encoding="utf-8")

        self.assertEqual(
            package_group(script, "runtime_packages"),
            [
                "bash",
                "coreutils",
                "findutils",
                "grep",
                "sed",
                "tar",
                "cron",
                "git",
                "curl",
                "ca-certificates",
                "ffmpeg",
                "python3-picamera2",
                "avahi-daemon",
                "avahi-utils",
                "libnss-mdns",
            ],
        )
        self.assertIn("Installing Plamp runtime dependencies", script)

    def test_install_script_installs_agentic_efficiency_tools_by_default(self):
        script = INSTALLER.read_text(encoding="utf-8")

        self.assertEqual(
            package_group(script, "agentic_efficiency_packages"),
            [
                "ripgrep",
                "gh",
                "shellcheck",
                "jq",
                "usbutils",
                "lsof",
                "strace",
                "openscad",
            ],
        )
        self.assertIn("Installing tools for agentic efficiency", script)
        self.assertIn(
            'apt-get install -y "${agentic_efficiency_packages[@]}"',
            script,
        )


if __name__ == "__main__":
    unittest.main()
