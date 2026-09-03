import unittest
from datetime import time

from plamp_web.timer_schedule import (
    apply_clock_window_schedule,
    apply_cycle_schedule,
    channel_metadata_for_role,
    compile_controller_state,
    inspect_two_step_pattern,
    patch_channel_schedule,
)


class TimerScheduleTests(unittest.TestCase):
    def test_compile_controller_state_builds_all_channels(self):
        channels = [
            {
                "id": "pump",
                "pin": 3,
                "type": "gpio",
                "programming": "scheduled",
                "editor": {"kind": "cycle", "on_seconds": 300, "off_seconds": 2400, "start_at_seconds": 0, "unit": "minutes"},
            },
            {
                "id": "lights",
                "pin": 2,
                "type": "gpio",
                "programming": "ready",
                "editor": {"kind": "cycle", "on_seconds": 1, "off_seconds": 1},
            },
        ]

        state = compile_controller_state(channels, report_every=10, now=time(9, 30))

        self.assertEqual(state["report_every"], 10)
        self.assertEqual(
            state["devices"],
            [
                {"id": "pump", "type": "gpio", "pin": 3, "mode": "scheduled", "current_t": 0, "reschedule": 1, "pattern": [{"val": 1, "dur": 300}, {"val": 0, "dur": 2400}]},
                {"id": "lights", "type": "gpio", "pin": 2, "mode": "ready", "current_t": 0, "reschedule": 1, "pattern": [{"val": 1, "dur": 1}, {"val": 0, "dur": 1}]},
            ],
        )
        self.assertEqual(state["devices"][0]["mode"], "scheduled")
        self.assertEqual(state["devices"][1]["mode"], "ready")
        self.assertEqual(state["devices"][1]["pattern"], [
            {"val": 1, "dur": 1}, {"val": 0, "dur": 1},
        ])

    def test_compile_controller_state_preserves_live_phase_for_unchanged_pattern(self):
        channels = [{
            "id": "pump", "pin": 3, "type": "gpio", "programming": "scheduled",
            "editor": {"kind": "cycle", "on_seconds": 300, "off_seconds": 2400},
        }]

        state = compile_controller_state(
            channels, report_every=10,
            live_devices=[{
                "id": "old_name", "pin": 3, "type": "gpio", "mode": "scheduled",
                "cycle_t": 247, "current_value": 1,
                "pattern": [{"val": 1, "dur": 300}, {"val": 0, "dur": 2400}],
            }],
        )

        self.assertEqual(state["devices"][0]["id"], "pump")
        self.assertEqual(state["devices"][0]["current_t"], 247)

    def test_compile_controller_state_uses_elapsed_t_when_live_cycle_t_is_absent(self):
        channels = [{
            "id": "pump", "pin": 3, "type": "gpio", "programming": "scheduled",
            "editor": {"kind": "cycle", "on_seconds": 300, "off_seconds": 2400},
        }]

        state = compile_controller_state(
            channels,
            report_every=10,
            live_devices=[{
                "id": "pump", "pin": 3, "type": "gpio", "mode": "scheduled",
                "elapsed_t": 247, "current_value": 1,
                "pattern": [{"val": 1, "dur": 300}, {"val": 0, "dur": 2400}],
            }],
        )

        self.assertEqual(state["devices"][0]["current_t"], 247)

    def test_compile_controller_state_reanchors_daily_window_to_host_time(self):
        channels = [{
            "id": "lights", "pin": 2, "type": "gpio", "programming": "scheduled",
            "editor": {"kind": "daily_window", "on_time": "06:00", "off_time": "23:00"},
        }]

        state = compile_controller_state(
            channels,
            report_every=10,
            now=time(11, 30),
            live_devices=[{
                "id": "lights", "pin": 2, "type": "gpio", "mode": "scheduled",
                "cycle_t": 23400, "current_value": 1,
                "pattern": [{"val": 1, "dur": 61200}, {"val": 0, "dur": 25200}],
            }],
        )

        self.assertEqual(state["devices"][0]["current_t"], 19800)

    def test_compile_controller_state_applies_events_start_at_seconds_directly(self):
        events = [
            {"val": 1, "dur": 4},
            {"val": 0, "dur": 6},
            {"val": 1, "dur": 8},
        ]
        channels = [{
            "id": "pump", "pin": 3, "type": "gpio", "programming": "scheduled",
            "editor": {"kind": "events", "events": events, "start_at_seconds": 7},
        }]

        state = compile_controller_state(channels, report_every=10)

        self.assertEqual(state["devices"][0]["pattern"], events)
        self.assertEqual(state["devices"][0]["current_t"], 7)

    def test_compile_controller_state_rejects_pwm_channel(self):
        channels = [{
            "id": "fan", "pin": 3, "type": "pwm", "programming": "scheduled",
            "editor": {"kind": "cycle", "on_seconds": 10, "off_seconds": 20},
        }]

        with self.assertRaisesRegex(ValueError, "type.*gpio"):
            compile_controller_state(channels, report_every=10)

    def test_channel_metadata_rejects_pwm_live_report(self):
        config = {
            "controllers": {"sprouter": {"config": {"pico_serial": "abc123"}, "devices": {
                "fan": {"type": "scheduled_output", "config": {"pin": 3}, "settings": {"schedule": {"kind": "cycle"}}},
            }}},
        }
        state = {"devices": [{"id": "fan", "type": "pwm", "pin": 3}]}

        with self.assertRaisesRegex(ValueError, "report.*type.*gpio"):
            channel_metadata_for_role("sprouter", config, state)

    def test_channel_metadata_uses_configured_devices_for_role(self):
        config = {
            "controllers": {
                "sprouter": {"config": {"pico_serial": "abc123"}, "devices": {
                    "lamp": {"type": "scheduled_output", "config": {"pin": 2, "output_type": "gpio"}, "settings": {"schedule": {"kind": "daily_window", "on_time": "06:00", "off_time": "18:00"}}},
                    "fan": {"type": "scheduled_output", "config": {"pin": 3}, "settings": {"schedule": {"kind": "cycle", "on_seconds": 300, "off_seconds": 1800, "start_at_seconds": 0, "unit": "minutes"}}},
                }},
                "other": {"config": {"pico_serial": "def456"}, "devices": {
                    "pump": {"type": "scheduled_output", "config": {"pin": 4}, "settings": {"schedule": {"kind": "cycle"}}},
                }},
            },
        }
        state = {
            "devices": [
                {"id": "runtime-lamp", "type": "gpio", "pin": 2},
                {"id": "runtime-fan", "type": "gpio", "pin": 3},
                {"id": "stray", "type": "gpio", "pin": 9},
            ]
        }

        self.assertEqual(
            channel_metadata_for_role("sprouter", config, state),
            [
                {"role": "sprouter", "id": "lamp", "name": "Lamp", "pin": 2, "type": "gpio", "default_editor": "clock_window", "visibility": "visible", "programming": "scheduled", "display_order": 0, "editor": {"kind": "daily_window", "on_time": "06:00", "off_time": "18:00"}},
                {"role": "sprouter", "id": "fan", "name": "Fan", "pin": 3, "type": "gpio", "default_editor": "cycle", "visibility": "visible", "programming": "scheduled", "display_order": 1, "editor": {"kind": "cycle", "on_seconds": 300, "off_seconds": 1800, "start_at_seconds": 0, "unit": "minutes"}},
            ],
        )

    def test_channel_metadata_uses_configured_gpio_when_no_live_event_exists(self):
        config = {
            "controllers": {"sprouter": {"config": {"pico_serial": "abc123"}, "devices": {
                "lamp": {"type": "scheduled_output", "config": {"pin": 2, "output_type": "gpio"}, "settings": {"schedule": {"kind": "daily_window", "on_time": "06:00", "off_time": "18:00"}}},
            }}},
        }

        self.assertEqual(
            channel_metadata_for_role("sprouter", config, {"devices": []}),
            [
                {"role": "sprouter", "id": "lamp", "name": "Lamp", "pin": 2, "type": "gpio", "default_editor": "clock_window", "visibility": "visible", "programming": "scheduled", "display_order": 0, "editor": {"kind": "daily_window", "on_time": "06:00", "off_time": "18:00"}},
            ],
        )

    def test_channel_metadata_humanizes_profile_id(self):
        config = {
            "controllers": {"sprouter": {"config": {"pico_serial": "abc123"}, "devices": {
                "ph_up": {"type": "scheduled_output", "config": {"pin": 2}, "settings": {"schedule": {"kind": "cycle"}}},
            }}},
        }

        self.assertEqual(channel_metadata_for_role("sprouter", config, {"devices": []})[0]["name"], "Ph up")

    def test_channel_metadata_ignores_unconfigured_runtime_events(self):
        config = {
            "controllers": {"sprouter": {"config": {"pico_serial": "abc123"}, "devices": {
                "lamp": {"type": "scheduled_output", "config": {"pin": 2}, "settings": {"schedule": {"kind": "daily_window", "on_time": "06:00", "off_time": "18:00"}}},
            }}},
        }
        state = {"devices": [{"id": "lamp-live", "type": "gpio", "pin": 2}, {"type": "gpio", "pin": 3}]}

        self.assertEqual(
            channel_metadata_for_role("sprouter", config, state),
            [
                {"role": "sprouter", "id": "lamp", "name": "Lamp", "pin": 2, "type": "gpio", "default_editor": "clock_window", "visibility": "visible", "programming": "scheduled", "display_order": 0, "editor": {"kind": "daily_window", "on_time": "06:00", "off_time": "18:00"}},
            ],
        )

    def test_channel_metadata_shows_disabled_and_hidden_devices(self):
        config = {
            "controllers": {"sprouter": {"config": {"pico_serial": "abc123"}, "devices": {
                "pump": {"type": "scheduled_output", "config": {"pin": 2}, "settings": {"programming": "ready"}},
                "lights": {"type": "scheduled_output", "config": {"pin": 3, "visibility": "hidden"}, "settings": {"programming": "ready"}},
            }}},
        }

        self.assertEqual(
            channel_metadata_for_role("sprouter", config, {"devices": []}),
            [
                {"role": "sprouter", "id": "pump", "name": "Pump", "pin": 2, "type": "gpio", "default_editor": "ready", "visibility": "visible", "programming": "ready", "display_order": 0, "editor": {"kind": "cycle", "on_seconds": 1, "off_seconds": 1, "start_at_seconds": 0}},
                {"role": "sprouter", "id": "lights", "name": "Lights", "pin": 3, "type": "gpio", "default_editor": "hidden", "visibility": "hidden", "programming": "ready", "display_order": 1, "editor": {"kind": "cycle", "on_seconds": 1, "off_seconds": 1, "start_at_seconds": 0}},
            ],
        )

    def test_inspect_two_step_pattern_accepts_on_off(self):
        event = {"pattern": [{"val": 1, "dur": 30}, {"val": 0, "dur": 600}], "current_t": 10}

        self.assertEqual(inspect_two_step_pattern(event), {"on_seconds": 30, "off_seconds": 600, "total_seconds": 630})

    def test_apply_cycle_schedule_defaults_to_start_at_zero(self):
        event = {"id": "fan", "type": "gpio", "pin": 3, "mode": "scheduled", "current_t": 200, "reschedule": 1, "pattern": [{"val": 1, "dur": 30}, {"val": 0, "dur": 600}]}

        updated = apply_cycle_schedule(event, on_seconds=10, off_seconds=20)

        self.assertEqual(updated["pattern"], [{"val": 1, "dur": 10}, {"val": 0, "dur": 20}])
        self.assertEqual(updated["current_t"], 0)
        self.assertEqual(updated["id"], "fan")
        self.assertEqual(updated["type"], "gpio")
        self.assertEqual(updated["pin"], 3)

    def test_apply_cycle_schedule_can_start_at_explicit_seconds(self):
        event = {"id": "fan", "type": "gpio", "pin": 3, "mode": "scheduled", "current_t": 200, "reschedule": 1, "pattern": [{"val": 1, "dur": 30}, {"val": 0, "dur": 600}]}

        updated = apply_cycle_schedule(event, on_seconds=10, off_seconds=20, start_at_seconds=28)

        self.assertEqual(updated["current_t"], 28)

    def test_apply_clock_window_schedule_uses_host_time(self):
        event = {"id": "lamp", "type": "gpio", "pin": 2, "mode": "scheduled", "current_t": 0, "reschedule": 1, "pattern": [{"val": 1, "dur": 1}, {"val": 0, "dur": 1}]}

        updated = apply_clock_window_schedule(event, on_time="06:00", off_time="18:30", now=time(7, 0, 0))

        self.assertEqual(updated["pattern"], [{"val": 1, "dur": 45000}, {"val": 0, "dur": 41400}])
        self.assertEqual(updated["current_t"], 3600)

    def test_apply_clock_window_schedule_rejects_identical_times(self):
        event = {"id": "lamp", "type": "gpio", "pin": 2, "mode": "scheduled", "current_t": 0, "reschedule": 1, "pattern": [{"val": 1, "dur": 1}, {"val": 0, "dur": 1}]}

        with self.assertRaisesRegex(ValueError, "ON and OFF times must be different"):
            apply_clock_window_schedule(event, on_time="06:00", off_time="06:00", now=time(7, 0, 0))

    def test_patch_channel_schedule_replaces_only_target_event(self):
        state = {
            "report_every": 1,
            "devices": [
                {"id": "fan", "type": "gpio", "pin": 3, "mode": "scheduled", "current_t": 4, "reschedule": 1, "pattern": [{"val": 1, "dur": 10}, {"val": 0, "dur": 50}]},
                {"id": "lamp", "type": "gpio", "pin": 2, "mode": "scheduled", "current_t": 0, "reschedule": 1, "pattern": [{"val": 1, "dur": 3600}, {"val": 0, "dur": 82800}]},
            ],
        }
        channels = [
            {"id": "fan", "pin": 3, "type": "gpio", "default_editor": "cycle"},
            {"id": "lamp", "pin": 2, "type": "gpio", "default_editor": "clock_window"},
        ]
        live_devices = [{"id": "fan", "cycle_t": 25}, {"id": "lamp", "cycle_t": 7200}]

        updated = patch_channel_schedule(
            state,
            channels,
            "fan",
            {"mode": "cycle", "on_seconds": 20, "off_seconds": 40, "start_at_seconds": 25},
            live_devices=live_devices,
            now=time(12, 0, 0),
        )

        self.assertEqual(updated["devices"][0]["pattern"], [{"val": 1, "dur": 20}, {"val": 0, "dur": 40}])
        self.assertEqual(updated["devices"][0]["current_t"], 25)
        self.assertEqual(updated["devices"][1]["pattern"], [{"val": 1, "dur": 3600}, {"val": 0, "dur": 82800}])
        self.assertEqual(updated["devices"][1]["current_t"], 7200)

    def test_patch_channel_schedule_matches_target_by_pin_and_rewrites_event_id(self):
        state = {
            "report_every": 1,
            "devices": [
                {"id": "runtime-lamp", "type": "gpio", "pin": 2, "mode": "scheduled", "current_t": 5, "reschedule": 1, "pattern": [{"val": 1, "dur": 15}, {"val": 0, "dur": 45}]},
                {"id": "fan", "type": "gpio", "pin": 3, "mode": "scheduled", "current_t": 9, "reschedule": 1, "pattern": [{"val": 1, "dur": 30}, {"val": 0, "dur": 90}]},
            ],
        }
        channels = [
            {"id": "lamp", "pin": 2, "type": "gpio", "default_editor": "cycle"},
            {"id": "fan", "pin": 3, "type": "gpio", "default_editor": "cycle"},
        ]
        live_devices = [{"id": "runtime-lamp", "cycle_t": 12}, {"id": "fan", "cycle_t": 44}]

        updated = patch_channel_schedule(
            state,
            channels,
            "lamp",
            {"mode": "cycle", "on_seconds": 20, "off_seconds": 40, "start_at_seconds": 12},
            live_devices=live_devices,
            now=time(12, 0, 0),
        )

        self.assertEqual(updated["devices"][0]["id"], "lamp")
        self.assertEqual(updated["devices"][0]["pin"], 2)
        self.assertEqual(updated["devices"][0]["pattern"], [{"val": 1, "dur": 20}, {"val": 0, "dur": 40}])
        self.assertEqual(updated["devices"][0]["current_t"], 12)
        self.assertEqual(updated["devices"][1]["id"], "fan")
        self.assertEqual(updated["devices"][1]["current_t"], 44)

    def test_patch_channel_schedule_migrates_id_matched_pin_change(self):
        state = {"report_every": 1, "devices": [{"id": "fan", "type": "gpio", "pin": 4, "mode": "scheduled", "current_t": 0, "reschedule": 1, "pattern": [{"val": 1, "dur": 10}, {"val": 0, "dur": 50}]}]}
        channels = [{"id": "fan", "pin": 3, "type": "gpio", "default_editor": "cycle"}]

        updated = patch_channel_schedule(state, channels, "fan", {"mode": "cycle", "on_seconds": 20, "off_seconds": 40, "start_at_seconds": 0})

        self.assertEqual(updated["devices"][0]["pin"], 3)
        self.assertEqual(updated["devices"][0]["type"], "gpio")
        self.assertEqual(updated["devices"][0]["pattern"], [{"val": 1, "dur": 20}, {"val": 0, "dur": 40}])

    def test_patch_channel_schedule_rejects_pin_match_with_wrong_type(self):
        state = {"report_every": 1, "devices": [{"id": "other", "type": "relay", "pin": 3, "mode": "scheduled", "current_t": 0, "reschedule": 1, "pattern": [{"val": 1, "dur": 10}, {"val": 0, "dur": 50}]}]}
        channels = [{"id": "fan", "pin": 3, "type": "gpio", "default_editor": "cycle"}]

        with self.assertRaisesRegex(ValueError, "pin/type"):
            patch_channel_schedule(state, channels, "fan", {"mode": "cycle", "on_seconds": 20, "off_seconds": 40, "start_at_seconds": 0})

    def test_patch_channel_schedule_creates_missing_configured_event(self):
        state = {
            "report_every": 1,
            "devices": [
                {"id": "test_pin", "type": "gpio", "pin": 25, "mode": "scheduled", "current_t": 0, "reschedule": 1, "pattern": [{"val": 1, "dur": 12}, {"val": 0, "dur": 5}]}
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

        self.assertEqual(updated["devices"][0]["id"], "test_pin")
        self.assertEqual(updated["devices"][1]["id"], "pump")
        self.assertEqual(updated["devices"][1]["pin"], 2)
        self.assertEqual(updated["devices"][1]["pattern"], [{"val": 1, "dur": 20}, {"val": 0, "dur": 40}])
        self.assertEqual(updated["devices"][1]["current_t"], 7)


if __name__ == "__main__":
    unittest.main()
