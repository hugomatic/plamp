import unittest
from datetime import time

from plamp_web.timer_schedule import (
    apply_clock_window_schedule,
    apply_cycle_schedule,
    channel_metadata_for_role,
    inspect_two_step_pattern,
    patch_channel_schedule,
)


class TimerScheduleTests(unittest.TestCase):
    def test_channel_metadata_uses_configured_devices_for_role(self):
        config = {
            "controllers": {"sprouter": {"pico_serial": "abc123"}, "other": {"pico_serial": "def456"}},
            "devices": {
                "lamp": {"controller": "sprouter", "pin": 2, "editor": "clock_window"},
                "fan": {"controller": "sprouter", "pin": 3, "editor": "cycle"},
                "pump": {"controller": "other", "pin": 4, "editor": "cycle"},
            },
        }
        state = {
            "events": [
                {"id": "runtime-lamp", "type": "pwm", "ch": 2},
                {"id": "runtime-fan", "type": "gpio", "ch": 3},
                {"id": "stray", "type": "gpio", "ch": 9},
            ]
        }

        self.assertEqual(
            channel_metadata_for_role("sprouter", config, state),
            [
                {"role": "sprouter", "id": "fan", "name": "fan", "pin": 3, "type": "gpio", "default_editor": "cycle"},
                {"role": "sprouter", "id": "lamp", "name": "lamp", "pin": 2, "type": "pwm", "default_editor": "clock_window"},
            ],
        )

    def test_channel_metadata_ignores_unconfigured_runtime_events(self):
        config = {
            "controllers": {"sprouter": {"pico_serial": "abc123"}},
            "devices": {"lamp": {"controller": "sprouter", "pin": 2, "editor": "clock_window"}},
        }
        state = {"events": [{"id": "lamp-live", "type": "gpio", "ch": 2}, {"type": "gpio", "ch": 3}]}

        self.assertEqual(
            channel_metadata_for_role("sprouter", config, state),
            [
                {"role": "sprouter", "id": "lamp", "name": "lamp", "pin": 2, "type": "gpio", "default_editor": "clock_window"},
            ],
        )

    def test_inspect_two_step_pattern_accepts_on_off(self):
        event = {"pattern": [{"val": 1, "dur": 30}, {"val": 0, "dur": 600}], "current_t": 10}

        self.assertEqual(inspect_two_step_pattern(event), {"on_seconds": 30, "off_seconds": 600, "total_seconds": 630})

    def test_apply_cycle_schedule_defaults_to_start_at_zero(self):
        event = {"id": "fan", "type": "gpio", "ch": 3, "current_t": 200, "reschedule": 1, "pattern": [{"val": 1, "dur": 30}, {"val": 0, "dur": 600}]}

        updated = apply_cycle_schedule(event, on_seconds=10, off_seconds=20)

        self.assertEqual(updated["pattern"], [{"val": 1, "dur": 10}, {"val": 0, "dur": 20}])
        self.assertEqual(updated["current_t"], 0)
        self.assertEqual(updated["id"], "fan")
        self.assertEqual(updated["type"], "gpio")
        self.assertEqual(updated["ch"], 3)

    def test_apply_cycle_schedule_can_start_at_explicit_seconds(self):
        event = {"id": "fan", "type": "gpio", "ch": 3, "current_t": 200, "reschedule": 1, "pattern": [{"val": 1, "dur": 30}, {"val": 0, "dur": 600}]}

        updated = apply_cycle_schedule(event, on_seconds=10, off_seconds=20, start_at_seconds=28)

        self.assertEqual(updated["current_t"], 28)

    def test_apply_clock_window_schedule_uses_host_time(self):
        event = {"id": "lamp", "type": "gpio", "ch": 2, "current_t": 0, "reschedule": 1, "pattern": [{"val": 1, "dur": 1}, {"val": 0, "dur": 1}]}

        updated = apply_clock_window_schedule(event, on_time="06:00", off_time="18:30", now=time(7, 0, 0))

        self.assertEqual(updated["pattern"], [{"val": 1, "dur": 45000}, {"val": 0, "dur": 41400}])
        self.assertEqual(updated["current_t"], 3600)

    def test_apply_clock_window_schedule_rejects_identical_times(self):
        event = {"id": "lamp", "type": "gpio", "ch": 2, "current_t": 0, "reschedule": 1, "pattern": [{"val": 1, "dur": 1}, {"val": 0, "dur": 1}]}

        with self.assertRaisesRegex(ValueError, "ON and OFF times must be different"):
            apply_clock_window_schedule(event, on_time="06:00", off_time="06:00", now=time(7, 0, 0))

    def test_patch_channel_schedule_replaces_only_target_event(self):
        state = {
            "report_every": 1,
            "events": [
                {"id": "fan", "type": "gpio", "ch": 3, "current_t": 4, "reschedule": 1, "pattern": [{"val": 1, "dur": 10}, {"val": 0, "dur": 50}]},
                {"id": "lamp", "type": "gpio", "ch": 2, "current_t": 0, "reschedule": 1, "pattern": [{"val": 1, "dur": 3600}, {"val": 0, "dur": 82800}]},
            ],
        }
        channels = [
            {"id": "fan", "pin": 3, "type": "gpio", "default_editor": "cycle"},
            {"id": "lamp", "pin": 2, "type": "gpio", "default_editor": "clock_window"},
        ]
        live_events = [{"id": "fan", "cycle_t": 25}, {"id": "lamp", "cycle_t": 7200}]

        updated = patch_channel_schedule(
            state,
            channels,
            "fan",
            {"mode": "cycle", "on_seconds": 20, "off_seconds": 40, "start_at_seconds": 25},
            live_events=live_events,
            now=time(12, 0, 0),
        )

        self.assertEqual(updated["events"][0]["pattern"], [{"val": 1, "dur": 20}, {"val": 0, "dur": 40}])
        self.assertEqual(updated["events"][0]["current_t"], 25)
        self.assertEqual(updated["events"][1]["pattern"], [{"val": 1, "dur": 3600}, {"val": 0, "dur": 82800}])
        self.assertEqual(updated["events"][1]["current_t"], 7200)

    def test_patch_channel_schedule_matches_target_by_pin_and_rewrites_event_id(self):
        state = {
            "report_every": 1,
            "events": [
                {"id": "runtime-lamp", "type": "gpio", "ch": 2, "current_t": 5, "reschedule": 1, "pattern": [{"val": 1, "dur": 15}, {"val": 0, "dur": 45}]},
                {"id": "fan", "type": "gpio", "ch": 3, "current_t": 9, "reschedule": 1, "pattern": [{"val": 1, "dur": 30}, {"val": 0, "dur": 90}]},
            ],
        }
        channels = [
            {"id": "lamp", "pin": 2, "type": "gpio", "default_editor": "cycle"},
            {"id": "fan", "pin": 3, "type": "gpio", "default_editor": "cycle"},
        ]
        live_events = [{"id": "runtime-lamp", "cycle_t": 12}, {"id": "fan", "cycle_t": 44}]

        updated = patch_channel_schedule(
            state,
            channels,
            "lamp",
            {"mode": "cycle", "on_seconds": 20, "off_seconds": 40, "start_at_seconds": 12},
            live_events=live_events,
            now=time(12, 0, 0),
        )

        self.assertEqual(updated["events"][0]["id"], "lamp")
        self.assertEqual(updated["events"][0]["ch"], 2)
        self.assertEqual(updated["events"][0]["pattern"], [{"val": 1, "dur": 20}, {"val": 0, "dur": 40}])
        self.assertEqual(updated["events"][0]["current_t"], 12)
        self.assertEqual(updated["events"][1]["id"], "fan")
        self.assertEqual(updated["events"][1]["current_t"], 44)

    def test_patch_channel_schedule_rejects_pin_type_mismatch(self):
        state = {"report_every": 1, "events": [{"id": "fan", "type": "gpio", "ch": 4, "current_t": 0, "reschedule": 1, "pattern": [{"val": 1, "dur": 10}, {"val": 0, "dur": 50}]}]}
        channels = [{"id": "fan", "pin": 3, "type": "gpio", "default_editor": "cycle"}]

        with self.assertRaisesRegex(ValueError, "pin/type"):
            patch_channel_schedule(state, channels, "fan", {"mode": "cycle", "on_seconds": 20, "off_seconds": 40, "start_at_seconds": 0})

    def test_patch_channel_schedule_creates_missing_configured_event(self):
        state = {
            "report_every": 1,
            "events": [
                {"id": "test_pin", "type": "gpio", "ch": 25, "current_t": 0, "reschedule": 1, "pattern": [{"val": 1, "dur": 12}, {"val": 0, "dur": 5}]}
            ],
        }
        channels = [{"id": "pump", "pin": 2, "type": "gpio", "default_editor": "cycle"}]

        updated = patch_channel_schedule(
            state,
            channels,
            "pump",
            {"mode": "cycle", "on_seconds": 20, "off_seconds": 40, "start_at_seconds": 7},
            now=time(12, 0, 0),
        )

        self.assertEqual(updated["events"][0]["id"], "test_pin")
        self.assertEqual(updated["events"][1]["id"], "pump")
        self.assertEqual(updated["events"][1]["ch"], 2)
        self.assertEqual(updated["events"][1]["pattern"], [{"val": 1, "dur": 20}, {"val": 0, "dur": 40}])
        self.assertEqual(updated["events"][1]["current_t"], 7)


if __name__ == "__main__":
    unittest.main()
