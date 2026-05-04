import unittest
from unittest.mock import patch

import plamp_web.server as server


class SettingsSummaryTests(unittest.TestCase):
    def test_software_summary_uses_git_identity_without_version_numbers(self):
        commands = {
            ("git", "rev-parse", "HEAD"): "d5883da4abcdef\n",
            ("git", "rev-parse", "--abbrev-ref", "HEAD"): "main\n",
            ("git", "status", "--short"): " M plamp_web/server.py\n",
        }

        def fake_check_output(command, **kwargs):
            return commands[tuple(command)]

        with patch.object(server.subprocess, "check_output", side_effect=fake_check_output):
            data = server.software_summary(repo_root=server.REPO_ROOT)

        self.assertEqual(data["name"], "plamp")
        self.assertEqual(data["git_commit"], "d5883da4abcdef")
        self.assertEqual(data["git_short_commit"], "d5883da")
        self.assertEqual(data["git_branch"], "main")
        self.assertTrue(data["git_dirty"])
        self.assertNotIn("version", data)

    def test_software_summary_handles_missing_git(self):
        with patch.object(server.subprocess, "check_output", side_effect=OSError("git missing")):
            data = server.software_summary(repo_root=server.REPO_ROOT)

        self.assertEqual(data["name"], "plamp")
        self.assertIsNone(data["git_commit"])
        self.assertIsNone(data["git_short_commit"])
        self.assertIsNone(data["git_branch"])
        self.assertIsNone(data["git_dirty"])
        self.assertNotIn("version", data)

    def test_software_summary_reflects_git_changes_between_calls(self):
        responses = [
            "aaaaaaaaaaaa\n",
            "main\n",
            "\n",
            "bbbbbbbbbbbb\n",
            "feature-branch\n",
            " M deploy/systemd/install-plamp-web-service.sh\n",
        ]

        with patch.object(server.subprocess, "check_output", side_effect=responses):
            first = server.software_summary(repo_root=server.REPO_ROOT)
            second = server.software_summary(repo_root=server.REPO_ROOT)

        self.assertEqual(first["git_branch"], "main")
        self.assertFalse(first["git_dirty"])
        self.assertEqual(second["git_branch"], "feature-branch")
        self.assertTrue(second["git_dirty"])

    def test_settings_summary_includes_software_identity(self):
        with (
            patch.object(server, "host_time_summary", return_value={}),
            patch.object(server, "host_ips", return_value=[]),
            patch.object(server, "default_route", return_value=None),
            patch.object(server, "network_summary", return_value=[]),
            patch.object(server, "enumerate_picos", return_value=[]),
            patch.object(server, "monitor_summaries", return_value={}),
            patch.object(server, "storage_summary", return_value={}),
            patch.object(server, "software_summary", return_value={"name": "plamp", "git_short_commit": "d5883da"}),
        ):
            data = server.settings_summary()

        self.assertEqual(data["software"]["git_short_commit"], "d5883da")

    def test_settings_summary_includes_firmware_generator_details(self):
        with (
            patch.object(server, "host_time_summary", return_value={}),
            patch.object(server, "host_ips", return_value=[]),
            patch.object(server, "default_route", return_value=None),
            patch.object(server, "network_summary", return_value=[]),
            patch.object(server, "enumerate_picos", return_value=[]),
            patch.object(server, "monitor_summaries", return_value={}),
            patch.object(server, "storage_summary", return_value={}),
            patch.object(server, "software_summary", return_value={"name": "plamp", "git_short_commit": "d5883da"}),
        ):
            data = server.settings_summary()

        self.assertEqual(data["firmware"]["generator_path"], str(server.PICO_GENERATOR_FILE))
        self.assertEqual(data["firmware"]["templates_path"], str(server.PICO_TEMPLATES_DIR))


if __name__ == "__main__":
    unittest.main()
