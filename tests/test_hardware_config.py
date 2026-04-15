import unittest

from plamp_web.hardware_config import (
    apply_config_section,
    config_view,
    empty_config,
    runtime_controller_serials,
    validate_cameras,
    validate_controllers,
    validate_devices,
)


class HardwareConfigTests(unittest.TestCase):
    def test_empty_config_uses_new_top_level_shape(self):
        self.assertEqual(
            empty_config(),
            {
                "controllers": {},
                "devices": {},
                "cameras": {},
            },
        )

    def test_config_view_ignores_legacy_top_level_keys(self):
        config = {
            "controllers": {"ctrl_a": {"pico_serial": "PICO123"}},
            "devices": {"dev_1": {"controller": "ctrl_a", "pin": 3, "editor": "cycle"}},
            "cameras": {"cam_1": {}},
            "timers": {"legacy": {}},
            "hardware": {"legacy": True},
        }
        self.assertEqual(
            config_view(config),
            {
                "controllers": {"ctrl_a": {"pico_serial": "PICO123"}},
                "devices": {"dev_1": {"controller": "ctrl_a", "pin": 3, "editor": "cycle"}},
                "cameras": {"cam_1": {}},
            },
        )

    def test_validate_controllers(self):
        self.assertEqual(
            validate_controllers({"ctrl_a": {}, "ctrl_b": {"pico_serial": "PICO123"}}),
            {"ctrl_a": {}, "ctrl_b": {"pico_serial": "PICO123"}},
        )

    def test_validate_devices_requires_known_controller(self):
        with self.assertRaises(ValueError):
            validate_devices({"dev_1": {"controller": "missing", "pin": 3, "editor": "cycle"}}, {})

    def test_validate_devices_requires_valid_editor_and_pin(self):
        controllers = {"ctrl_a": {}}
        with self.assertRaises(ValueError):
            validate_devices({"dev_1": {"controller": "ctrl_a", "pin": 30, "editor": "cycle"}}, controllers)
        with self.assertRaises(ValueError):
            validate_devices({"dev_1": {"controller": "ctrl_a", "pin": 3, "editor": "bad"}}, controllers)

    def test_validate_cameras(self):
        self.assertEqual(validate_cameras({"cam_1": {}}), {"cam_1": {}})

    def test_apply_config_section_validates_dependent_devices(self):
        config = {
            "controllers": {"ctrl_a": {}, "ctrl_b": {}},
            "devices": {"dev_1": {"controller": "ctrl_a", "pin": 3, "editor": "cycle"}},
            "cameras": {},
        }
        with self.assertRaises(ValueError):
            apply_config_section(config, "controllers", {"ctrl_b": {}})

    def test_runtime_controller_serials(self):
        config = {
            "controllers": {"ctrl_a": {}, "ctrl_b": {"pico_serial": "PICO123"}},
            "devices": {},
            "cameras": {},
            "timers": {"legacy": {}},
        }
        self.assertEqual(runtime_controller_serials(config), {"ctrl_b": "PICO123"})


if __name__ == "__main__":
    unittest.main()
