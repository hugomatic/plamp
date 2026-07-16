import unittest

from plamp.scheduler_state import (
    EXPECTED_FIRMWARE_PROTOCOL,
    FirmwareIdentity,
    firmware_identity,
    normalize_scheduler_state,
    report_matches_state,
)


STATE = {
    "report_every": 5,
    "devices": [{
        "id": "lights", "type": "gpio", "pin": 2, "current_t": 7,
        "reschedule": 1,
        "pattern": [{"val": 1, "dur": 10}, {"val": 0, "dur": 20}],
    }],
}


class SchedulerStateTests(unittest.TestCase):
    def test_normalizes_complete_state_without_host_poll_setting(self):
        self.assertEqual(normalize_scheduler_state(STATE), {"devices": STATE["devices"]})

    def test_rejects_duplicate_pin_before_returning_state(self):
        raw = {"devices": [STATE["devices"][0], dict(STATE["devices"][0], id="pump")]}
        with self.assertRaisesRegex(ValueError, "duplicate pin: 2"):
            normalize_scheduler_state(raw)

    def test_reads_firmware_identity_from_report(self):
        report = {"type": "report", "content": {
            "firmware": {"name": "pico_scheduler", "revision": "abc1234", "protocol": 2},
            "devices": [],
        }}
        self.assertEqual(
            firmware_identity(report),
            FirmwareIdentity("pico_scheduler", "abc1234", EXPECTED_FIRMWARE_PROTOCOL),
        )

    def test_legacy_report_has_no_identity(self):
        self.assertIsNone(firmware_identity({"type": "report", "content": {"devices": []}}))

    def test_report_comparison_ignores_runtime_elapsed_fields(self):
        report = {"type": "report", "content": {"devices": [{
            "id": "lights", "type": "gpio", "pin": 2, "elapsed_t": 19,
            "cycle_t": 19, "current_value": 0, "reschedule": 1,
            "pattern": STATE["devices"][0]["pattern"],
        }]}}
        self.assertTrue(report_matches_state(report, STATE))
