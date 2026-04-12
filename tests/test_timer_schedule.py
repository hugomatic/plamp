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
    def test_channel_metadata_uses_configured_channels(self):
        role_config = {
            "role": "sprouter",
            "pico_serial": "abc123",
            "channels": [
                {"id": "lamp", "name": "Lamp", "pin": 2, "type": "gpio", "default_editor": "clock_window"},
                {"id": "fan", "name": "Fan", "pin": 3, "type": "gpio", "default_editor": "cycle"},
            ],
        }
        state = {"events": [{"id": "lamp", "type": "gpio", "ch": 2}, {"id": "fan", "type": "gpio", "ch": 3}]}

        self.assertEqual(
            channel_metadata_for_role("sprouter", role_config, state),
            [
                {"role": "sprouter", "id": "lamp", "name": "Lamp", "pin": 2, "type": "gpio", "default_editor": "clock_window"},
                {"role": "sprouter", "id": "fan", "name": "Fan", "pin": 3, "type": "gpio", "default_editor": "cycle"},
            ],
        )

    def test_channel_metadata_falls_back_to_state_events(self):
        role_config = {"role": "sprouter", "pico_serial": "abc123"}
        state = {"events": [{"id": "lamp", "type": "gpio", "ch": 2}, {"type": "gpio", "ch": 3}]}

        self.assertEqual(
            channel_metadata_for_role("sprouter", role_config, state),
            [
                {"role": "sprouter", "id": "lamp", "name": "lamp", "pin": 2, "type": "gpio", "default_editor": "cycle"},
                {"role": "sprouter", "id": "pin-3", "name": "pin 3", "pin": 3, "type": "gpio", "default_editor": "cycle"},
            ],
        )

    def test_inspect_two_step_pattern_accepts_on_off(self):
        event = {"pattern": [{"val": 1, "dur": 30}, {"val": 0, "dur": 600}], "current_t": 10}

        self.assertEqual(inspect_two_step_pattern(event), {"on_seconds": 30, "off_seconds": 600, "total_seconds": 630})

    def test_apply_cycle_schedule_can_start_now(self):
        event = {"id": "fan", "type": "gpio", "ch": 3, "current_t": 200, "reschedule": 1, "pattern": [{"val": 1, "dur": 30}, {"val": 0, "dur": 600}]}

        updated = apply_cycle_schedule(event, on_seconds=10, off_seconds=20, apply_behavior="start_now", live_event={"cycle_t": 12})

        self.assertEqual(updated["pattern"], [{"val": 1, "dur": 10}, {"val": 0, "dur": 20}])
        self.assertEqual(updated["current_t"], 0)
        self.assertEqual(updated["id"], "fan")
        self.assertEqual(updated["type"], "gpio")
        self.assertEqual(updated["ch"], 3)

    def test_apply_cycle_schedule_can_jump_to_next_change(self):
        event = {"id": "fan", "type": "gpio", "ch": 3, "current_t": 200, "reschedule": 1, "pattern": [{"val": 1, "dur": 30}, {"val": 0, "dur": 600}]}

        updated = apply_cycle_schedule(event, on_seconds=10, off_seconds=20, apply_behavior="jump_to_next_change", live_event={"cycle_t": 2})

        self.assertEqual(updated["current_t"], 5)

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
            {"mode": "cycle", "on_seconds": 20, "off_seconds": 40, "apply_behavior": "preserve"},
            live_events=live_events,
            now=time(12, 0, 0),
        )

        self.assertEqual(updated["events"][0]["pattern"], [{"val": 1, "dur": 20}, {"val": 0, "dur": 40}])
        self.assertEqual(updated["events"][0]["current_t"], 25)
        self.assertEqual(updated["events"][1]["pattern"], [{"val": 1, "dur": 3600}, {"val": 0, "dur": 82800}])
        self.assertEqual(updated["events"][1]["current_t"], 7200)

    def test_patch_channel_schedule_rejects_pin_type_mismatch(self):
        state = {"report_every": 1, "events": [{"id": "fan", "type": "gpio", "ch": 4, "current_t": 0, "reschedule": 1, "pattern": [{"val": 1, "dur": 10}, {"val": 0, "dur": 50}]}]}
        channels = [{"id": "fan", "pin": 3, "type": "gpio", "default_editor": "cycle"}]

        with self.assertRaisesRegex(ValueError, "pin/type"):
            patch_channel_schedule(state, channels, "fan", {"mode": "cycle", "on_seconds": 20, "off_seconds": 40, "apply_behavior": "preserve"})


if __name__ == "__main__":
    unittest.main()
