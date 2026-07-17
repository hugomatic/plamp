import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

import plamp
from plamp.pico_firmware import firmware_revision, render_scheduler_firmware


class PicoFirmwareTests(unittest.TestCase):
    def test_revision_is_latest_commit_touching_scheduler_source_directory(self):
        calls = []

        self.assertEqual(
            firmware_revision(
                Path("/repo"),
                git_runner=lambda args, cwd: calls.append((args, cwd)) or "abc1234\n",
            ),
            "abc1234",
        )
        self.assertEqual(
            calls,
            [
                (
                    ["git", "log", "-1", "--format=%h", "--", "pico_scheduler/src"],
                    Path("/repo"),
                )
            ],
        )

    def test_revision_is_unknown_without_git_metadata(self):
        def missing_git(args, cwd):
            raise subprocess.CalledProcessError(128, args)

        self.assertEqual(
            firmware_revision(Path("/archive"), git_runner=missing_git), "unknown"
        )

    def test_revision_is_unknown_when_git_has_no_scheduler_commit(self):
        self.assertEqual(
            firmware_revision(Path("/repo"), git_runner=lambda args, cwd: "\n"),
            "unknown",
        )

    def test_render_uses_scheduler_revision_and_generic_generator(self):
        with patch("plamp.pico_firmware.firmware_revision", return_value="abc1234"):
            revision, source = render_scheduler_firmware(Path("/repo"))

        self.assertEqual(revision, "abc1234")
        self.assertIn('FIRMWARE_REVISION = "abc1234"', source)
        self.assertIn('STATE_PATHS = ("/plamp_state_a.json", "/plamp_state_b.json")', source)

    def test_package_exports_firmware_helpers(self):
        self.assertIs(plamp.firmware_revision, firmware_revision)
        self.assertIs(plamp.render_scheduler_firmware, render_scheduler_firmware)


if __name__ == "__main__":
    unittest.main()
