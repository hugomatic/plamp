import unittest

from plamp_web.hardware_config import (
    apply_config_section,
    apply_hardware_section,
    config_view,
    empty_config,
    hardware_view,
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
            "devices": {"dev_1": {"controller": "ctrl_a", "pin": 3, "type": "gpio", "editor": "cycle"}},
            "cameras": {"cam_1": {}},
            "timers": {"legacy": {}},
            "hardware": {"legacy": True},
        }
        self.assertEqual(
            config_view(config),
            {
                "controllers": {"ctrl_a": {"type": "pico_scheduler", "pico_serial": "PICO123", "report_every": 10}},
                "devices": {"dev_1": {"controller": "ctrl_a", "pin": 3, "type": "gpio", "editor": "cycle"}},
                "cameras": {"cam_1": {}},
            },
        )

    def test_validate_controllers(self):
        self.assertEqual(
            validate_controllers({"ctrl_a": {}, "ctrl_b": {"pico_serial": "PICO123"}}),
            {
                "ctrl_a": {"type": "pico_scheduler", "report_every": 10},
                "ctrl_b": {"type": "pico_scheduler", "pico_serial": "PICO123", "report_every": 10},
            },
        )

    def test_validate_controllers_defaults_to_pico_scheduler_type_and_report_every(self):
        self.assertEqual(
            validate_controllers({"ctrl_a": {"pico_serial": "PICO123"}}),
            {"ctrl_a": {"type": "pico_scheduler", "pico_serial": "PICO123", "report_every": 10}},
        )

    def test_validate_controllers_accepts_pico_scheduler_report_every(self):
        self.assertEqual(
            validate_controllers({"ctrl_a": {"type": "pico_scheduler", "report_every": 30}}),
            {"ctrl_a": {"type": "pico_scheduler", "report_every": 30}},
        )

    def test_validate_controllers_accepts_pico_doser_type(self):
        self.assertEqual(
            validate_controllers({"doser_a": {"type": "pico_doser"}}),
            {"doser_a": {"type": "pico_doser"}},
        )

    def test_validate_controllers_rejects_reserved_controller_ids(self):
        with self.assertRaisesRegex(ValueError, "reserved"):
            validate_controllers({"pico_scheduler": {}})

    def test_validate_controllers_rejects_invalid_type_and_report_every(self):
        with self.assertRaisesRegex(ValueError, "controller ctrl_a type"):
            validate_controllers({"ctrl_a": {"type": "ph_doser"}})
        with self.assertRaisesRegex(ValueError, "report_every"):
            validate_controllers({"ctrl_a": {"type": "pico_scheduler", "report_every": 0}})
        with self.assertRaisesRegex(ValueError, "report_every"):
            validate_controllers({"ctrl_a": {"type": "pico_scheduler", "report_every": True}})

    def test_validate_devices_defaults_missing_editor(self):
        self.assertEqual(
            validate_devices({"dev_1": {"controller": "ctrl_a", "pin": 3}}, {"ctrl_a": {}}),
            {"dev_1": {"controller": "ctrl_a", "pin": 3, "editor": "cycle", "type": "gpio"}},
        )

    def test_validate_devices_allows_configured_pin_type(self):
        self.assertEqual(
            validate_devices({"dev_1": {"controller": "ctrl_a", "pin": 3, "type": "pwm"}}, {"ctrl_a": {}}),
            {"dev_1": {"controller": "ctrl_a", "pin": 3, "editor": "cycle", "type": "pwm"}},
        )

    def test_validate_devices_requires_known_controller(self):
        with self.assertRaises(ValueError):
            validate_devices({"dev_1": {"controller": "missing", "pin": 3, "editor": "cycle"}}, {})

    def test_validate_devices_requires_pico_scheduler_controller(self):
        import plamp_web.hardware_config as hardware_config

        controllers = {"timer": {"type": "pico_scheduler"}, "future": {"type": "future_controller"}}
        original_types = hardware_config._CONTROLLER_TYPES
        try:
            hardware_config._CONTROLLER_TYPES = {"pico_scheduler", "future_controller"}
            with self.assertRaisesRegex(ValueError, "pico_scheduler"):
                validate_devices({"pump": {"controller": "future", "pin": 3}}, controllers)
        finally:
            hardware_config._CONTROLLER_TYPES = original_types

    def test_scheduler_controller_ids_returns_only_pico_scheduler_controllers(self):
        from plamp_web.hardware_config import scheduler_controller_ids

        self.assertEqual(
            scheduler_controller_ids(
                {
                    "timer": {"type": "pico_scheduler"},
                    "legacy": {},
                    "future": {"type": "future_controller"},
                }
            ),
            {"timer", "legacy"},
        )

    def test_validate_devices_requires_valid_editor_and_pin(self):
        controllers = {"ctrl_a": {}}
        with self.assertRaises(ValueError):
            validate_devices({"dev_1": {"controller": "ctrl_a", "pin": 30, "editor": "cycle"}}, controllers)
        with self.assertRaises(ValueError):
            validate_devices({"dev_1": {"controller": "ctrl_a", "pin": 3, "editor": "bad"}}, controllers)
        with self.assertRaises(ValueError):
            validate_devices({"dev_1": {"controller": "ctrl_a", "pin": 3, "type": "bad"}}, controllers)

    def test_validate_devices_rejects_duplicate_pin_per_controller(self):
        controllers = {"ctrl_a": {}, "ctrl_b": {}}
        with self.assertRaisesRegex(ValueError, "duplicate pin"):
            validate_devices(
                {
                    "dev_1": {"controller": "ctrl_a", "pin": 3, "editor": "cycle"},
                    "dev_2": {"controller": "ctrl_a", "pin": 3, "editor": "clock_window"},
                    "dev_3": {"controller": "ctrl_b", "pin": 3, "editor": "cycle"},
                },
                controllers,
            )

    def test_validate_cameras(self):
        self.assertEqual(validate_cameras({"cam_1": {}}), {"cam_1": {}})


    def test_validate_controllers_allows_optional_label(self):
        self.assertEqual(
            validate_controllers({"ctrl_a": {"pico_serial": "PICO123", "label": "Pump lights"}}),
            {"ctrl_a": {"type": "pico_scheduler", "pico_serial": "PICO123", "report_every": 10, "label": "Pump lights"}},
        )

    def test_validate_devices_allows_optional_label(self):
        self.assertEqual(
            validate_devices({"dev_1": {"controller": "ctrl_a", "pin": 3, "editor": "cycle", "label": "Main pump"}}, {"ctrl_a": {}}),
            {"dev_1": {"controller": "ctrl_a", "pin": 3, "editor": "cycle", "type": "gpio", "label": "Main pump"}},
        )

    def test_validate_cameras_allows_optional_label(self):
        self.assertEqual(validate_cameras({"cam_1": {"label": "Tent"}}), {"cam_1": {"label": "Tent"}})

    def test_validate_cameras_allows_detected_key(self):
        self.assertEqual(
            validate_cameras({"picam0": {"label": "Tent", "detected_key": "rpicam_cam0"}}),
            {"picam0": {"label": "Tent", "detected_key": "rpicam_cam0"}},
        )

    def test_validate_cameras_accepts_capture_ownership_fields(self):
        self.assertEqual(
            validate_cameras(
                {
                    "rpicam_cam0": {
                        "label": "Tent top",
                        "detected_key": "rpicam_cam0",
                        "capture_dir": "grow/grows/grow-basil/captures",
                        "enabled": True,
                        "auto_enabled": True,
                        "capture_every_seconds": 3600,
                        "manual_prefix": "manual",
                        "auto_prefix": "auto",
                        "autofocus_mode": "auto",
                        "autofocus_delay_ms": 1200,
                    }
                }
            ),
            {
                "rpicam_cam0": {
                    "label": "Tent top",
                    "detected_key": "rpicam_cam0",
                    "capture_dir": "grow/grows/grow-basil/captures",
                    "enabled": True,
                    "auto_enabled": True,
                    "capture_every_seconds": 3600,
                    "manual_prefix": "manual",
                    "auto_prefix": "auto",
                    "autofocus_mode": "auto",
                    "autofocus_delay_ms": 1200,
                }
            },
        )

    def test_validate_cameras_rejects_absolute_capture_dir(self):
        with self.assertRaisesRegex(ValueError, "capture_dir must be repo-relative"):
            validate_cameras({"rpicam_cam0": {"capture_dir": "/tmp/captures"}})

    def test_validate_cameras_rejects_non_relative_capture_dir_traversal(self):
        with self.assertRaisesRegex(ValueError, "capture_dir must be repo-relative"):
            validate_cameras({"rpicam_cam0": {"capture_dir": "../captures"}})

    def test_validate_cameras_requires_capture_every_seconds_when_auto_enabled(self):
        with self.assertRaisesRegex(ValueError, "capture_every_seconds"):
            validate_cameras({"rpicam_cam0": {"auto_enabled": True, "capture_dir": "grow/grows/grow-basil/captures"}})

    def test_validate_cameras_rejects_invalid_boolean_fields(self):
        with self.assertRaisesRegex(ValueError, "enabled"):
            validate_cameras({"rpicam_cam0": {"enabled": "yes"}})
        with self.assertRaisesRegex(ValueError, "auto_enabled"):
            validate_cameras({"rpicam_cam0": {"auto_enabled": 1}})

    def test_validate_cameras_rejects_invalid_prefix_and_autofocus(self):
        with self.assertRaisesRegex(ValueError, "manual_prefix"):
            validate_cameras({"rpicam_cam0": {"manual_prefix": "manual pics"}})
        with self.assertRaisesRegex(ValueError, "auto_prefix"):
            validate_cameras({"rpicam_cam0": {"auto_prefix": ""}})
        with self.assertRaisesRegex(ValueError, "autofocus_mode"):
            validate_cameras({"rpicam_cam0": {"autofocus_mode": "tracking"}})

    def test_validate_cameras_rejects_invalid_autofocus_delay(self):
        with self.assertRaisesRegex(ValueError, "autofocus_delay_ms"):
            validate_cameras({"rpicam_cam0": {"autofocus_delay_ms": -1}})

    def test_validate_rejects_non_string_label(self):
        with self.assertRaisesRegex(ValueError, "label"):
            validate_controllers({"ctrl_a": {"label": 123}})

    def test_apply_config_section_devices_happy_path(self):
        config = {"controllers": {"ctrl_a": {}}, "devices": {}, "cameras": {}}
        updated = apply_config_section(
            config,
            "devices",
            {"dev_1": {"controller": "ctrl_a", "pin": 3, "editor": "clock_window"}},
        )
        self.assertEqual(updated["devices"], {"dev_1": {"controller": "ctrl_a", "pin": 3, "type": "gpio", "editor": "clock_window"}})

    def test_apply_config_section_controllers_happy_path_and_runtime_serials(self):
        config = {
            "controllers": {"ctrl_a": {}, "ctrl_b": {"pico_serial": "OLD"}},
            "devices": {"dev_1": {"controller": "ctrl_a", "pin": 3, "editor": "cycle"}},
            "cameras": {},
        }
        updated = apply_config_section(
            config,
            "controllers",
            {"ctrl_a": {}, "ctrl_b": {"pico_serial": "PICO123"}},
        )
        self.assertEqual(
            updated["controllers"],
            {
                "ctrl_a": {"type": "pico_scheduler", "report_every": 10},
                "ctrl_b": {"type": "pico_scheduler", "pico_serial": "PICO123", "report_every": 10},
            },
        )
        self.assertEqual(runtime_controller_serials(updated), {"ctrl_b": "PICO123"})

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

    def test_compatibility_wrappers_resolve(self):
        config = empty_config()
        self.assertEqual(hardware_view(config), config_view(config))
        self.assertEqual(apply_hardware_section(config, "cameras", {}), config_view(config))


if __name__ == "__main__":
    unittest.main()
