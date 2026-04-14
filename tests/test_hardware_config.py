import copy
import unittest

from plamp_web.hardware_config import (
    apply_hardware_section,
    hardware_config_from_timers,
    hardware_view,
    project_timers_from_hardware,
)


class HardwareConfigTests(unittest.TestCase):
    def test_hardware_config_from_timers_initializes_controller_and_devices(self):
        config = {
            "timers": [
                {
                    "role": "pump_lights",
                    "pico_serial": "e66038b71387a039",
                    "channels": [
                        {"id": "pump", "name": "Pump", "pin": 3, "type": "gpio", "default_editor": "cycle"},
                        {"id": "lights", "name": "Lights", "pin": 2, "type": "gpio", "default_editor": "clock_window"},
                    ],
                }
            ]
        }

        self.assertEqual(
            hardware_config_from_timers(config),
            {
                "controllers": {
                    "controller:pump_lights": {"name": "pump_lights", "type": "pico_scheduler", "match": {"pico_serial": "e66038b71387a039"}}
                },
                "devices": {
                    "pump": {"name": "Pump", "type": "gpio", "controller": "controller:pump_lights", "pin": 3, "default_editor": "cycle"},
                    "lights": {"name": "Lights", "type": "gpio", "controller": "controller:pump_lights", "pin": 2, "default_editor": "clock_window"},
                },
                "cameras": {},
            },
        )

    def test_hardware_view_prefers_existing_hardware(self):
        config = {"timers": [], "hardware": {"controllers": {"controller:pump_lights": {"name": "pump_lights", "type": "pico_scheduler", "match": {"pico_serial": "abc"}}}, "devices": {}, "cameras": {}}}

        self.assertEqual(hardware_view(config), config["hardware"])

    def test_apply_devices_rejects_unknown_controller(self):
        config = {"hardware": {"controllers": {}, "devices": {}, "cameras": {}}}

        with self.assertRaises(ValueError) as cm:
            apply_hardware_section(config, "devices", {"pump": {"name": "Pump", "type": "gpio", "controller": "controller:missing", "pin": 3}})

        self.assertIn("unknown controller", str(cm.exception))

    def test_apply_cameras_rejects_unknown_ir_filter(self):
        config = {"hardware": {"controllers": {}, "devices": {}, "cameras": {}}}

        with self.assertRaises(ValueError) as cm:
            apply_hardware_section(config, "cameras", {"rpicam:cam0": {"name": "Tent", "ir_filter": "magic"}})

        self.assertIn("ir_filter", str(cm.exception))

    def test_project_timers_from_hardware_preserves_runtime_compatibility(self):
        config = {
            "timers": [{"role": "old", "pico_serial": "oldserial"}],
            "hardware": {
                "controllers": {"controller:pump_lights": {"name": "pump_lights", "type": "pico_scheduler", "match": {"pico_serial": "e66038b71387a039"}}},
                "devices": {
                    "pump": {"name": "Pump", "type": "gpio", "controller": "controller:pump_lights", "pin": 3, "default_editor": "cycle"},
                    "lights": {"name": "Lights", "type": "gpio", "controller": "controller:pump_lights", "pin": 2, "default_editor": "clock_window"},
                },
                "cameras": {},
            },
        }

        projected = project_timers_from_hardware(copy.deepcopy(config))

        self.assertEqual(
            projected["timers"],
            [
                {
                    "role": "pump_lights",
                    "pico_serial": "e66038b71387a039",
                    "channels": [
                        {"id": "lights", "name": "Lights", "pin": 2, "type": "gpio", "default_editor": "clock_window"},
                        {"id": "pump", "name": "Pump", "pin": 3, "type": "gpio", "default_editor": "cycle"},
                    ],
                }
            ],
        )
