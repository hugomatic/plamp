import unittest

from plamp_web.hardware_config import (
    apply_config_section,
    apply_hardware_section,
    config_view,
    empty_config,
    hardware_view,
    runtime_controller_serials,
    scheduler_devices_for_controller,
    validate_cameras,
    validate_controllers,
    validate_controller_devices,
)


class HardwareConfigTests(unittest.TestCase):
    def test_empty_config_uses_new_top_level_shape(self):
        self.assertEqual(
            empty_config(),
            {"controllers": {}, "cameras": {}},
        )

    def test_config_view_rejects_legacy_top_level_devices(self):
        config = {
            "controllers": {},
            "devices": {"dev_1": {"controller": "ctrl_a", "pin": 3, "type": "gpio", "editor": "cycle"}},
            "cameras": {},
        }
        with self.assertRaisesRegex(ValueError, "top-level devices"):
            config_view(config)

    def test_validate_controllers(self):
        self.assertEqual(
            validate_controllers({"ctrl_a": {}, "ctrl_b": {"config": {"pico_serial": "PICO123"}}}),
            {
                "ctrl_a": {"type": "pico_scheduler", "payload": {"report_every": 10, "devices": []}, "settings": {"devices": {}}},
                "ctrl_b": {
                    "type": "pico_scheduler",
                    "payload": {"pico_serial": "PICO123", "report_every": 10, "devices": []},
                    "settings": {"devices": {}},
                },
            },
        )

    def test_validate_controllers_defaults_to_pico_scheduler_type_and_report_every(self):
        self.assertEqual(
            validate_controllers({"ctrl_a": {"config": {"pico_serial": "PICO123"}}}),
            {
                "ctrl_a": {
                    "type": "pico_scheduler",
                    "payload": {"pico_serial": "PICO123", "report_every": 10, "devices": []},
                    "settings": {"devices": {}},
                }
            },
        )

    def test_validate_controllers_accepts_pico_scheduler_report_every(self):
        self.assertEqual(
            validate_controllers({"ctrl_a": {"type": "pico_scheduler", "settings": {"report_every": 30}}}),
            {"ctrl_a": {"type": "pico_scheduler", "payload": {"report_every": 30, "devices": []}, "settings": {"devices": {}}}},
        )

    def test_validate_controllers_accepts_pico_doser_type(self):
        self.assertEqual(
            validate_controllers({"doser_a": {"type": "pico_doser"}}),
            {"doser_a": {"type": "pico_doser", "config": {}, "settings": {}, "devices": {}}},
        )

    def test_validate_controllers_rejects_reserved_controller_ids(self):
        with self.assertRaisesRegex(ValueError, "reserved"):
            validate_controllers({"pico_scheduler": {}})

    def test_validate_controllers_rejects_invalid_type_and_report_every(self):
        with self.assertRaisesRegex(ValueError, "controller ctrl_a type"):
            validate_controllers({"ctrl_a": {"type": "ph_doser"}})
        with self.assertRaisesRegex(ValueError, "report_every"):
            validate_controllers({"ctrl_a": {"type": "pico_scheduler", "settings": {"report_every": 0}}})
        with self.assertRaisesRegex(ValueError, "report_every"):
            validate_controllers({"ctrl_a": {"type": "pico_scheduler", "settings": {"report_every": True}}})

    def test_validate_controller_devices_defaults_schedule(self):
        self.assertEqual(
            validate_controller_devices(
                {"dev_1": {"type": "scheduled_output", "config": {"pin": 3}}},
                "ctrl_a",
                "pico_scheduler",
            ),
            {
                "dev_1": {
                    "type": "scheduled_output",
                    "config": {"pin": 3, "output_type": "gpio", "display_order": 0, "visibility": "visible"},
                    "settings": {
                        "programming": "enabled",
                        "schedule": {"kind": "cycle", "on_seconds": 1, "off_seconds": 1, "start_at_seconds": 0},
                    },
                }
            },
        )

    def test_validate_controller_devices_allows_configured_pin_type(self):
        self.assertEqual(
            validate_controller_devices(
                {"dev_1": {"type": "scheduled_output", "config": {"pin": 3, "output_type": "pwm"}}},
                "ctrl_a",
                "pico_scheduler",
            )["dev_1"]["config"]["output_type"],
            "pwm",
        )

    def test_validate_controller_devices_requires_pico_scheduler_controller(self):
        with self.assertRaisesRegex(ValueError, "pico_scheduler"):
            validate_controller_devices(
                {"pump": {"type": "scheduled_output", "config": {"pin": 3}}},
                "future",
                "pico_doser",
            )

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

    def test_validate_controller_devices_requires_valid_schedule_and_pin(self):
        with self.assertRaises(ValueError):
            validate_controller_devices({"dev_1": {"type": "scheduled_output", "config": {"pin": 30}}}, "ctrl_a", "pico_scheduler")
        with self.assertRaises(ValueError):
            validate_controller_devices(
                {"dev_1": {"type": "scheduled_output", "config": {"pin": 3}, "settings": {"schedule": {"kind": "bad"}}}},
                "ctrl_a",
                "pico_scheduler",
            )
        with self.assertRaises(ValueError):
            validate_controller_devices(
                {"dev_1": {"type": "scheduled_output", "config": {"pin": 3, "output_type": "bad"}}},
                "ctrl_a",
                "pico_scheduler",
            )

    def test_validate_controller_devices_accepts_disabled_and_hidden_state(self):
        devices = validate_controller_devices(
            {
                "disabled_pump": {
                    "type": "scheduled_output",
                    "config": {"pin": 3},
                    "settings": {"programming": "disabled"},
                },
                "hidden_light": {
                    "type": "scheduled_output",
                    "config": {"pin": 4, "visibility": "hidden"},
                    "settings": {"programming": "disabled"},
                },
            },
            "ctrl_a",
            "pico_scheduler",
        )
        self.assertEqual(devices["disabled_pump"]["settings"]["programming"], "disabled")
        self.assertEqual(devices["hidden_light"]["config"]["visibility"], "hidden")

    def test_validate_controller_devices_rejects_duplicate_pin_per_controller(self):
        with self.assertRaisesRegex(ValueError, "duplicate pin"):
            validate_controller_devices(
                {
                    "dev_1": {"type": "scheduled_output", "config": {"pin": 3}},
                    "dev_2": {"type": "scheduled_output", "config": {"pin": 3}},
                },
                "ctrl_a",
                "pico_scheduler",
            )

    def test_validate_cameras(self):
        self.assertEqual(validate_cameras({"cam_1": {}}), {"cam_1": {}})


    def test_validate_controllers_allows_optional_legacy_label(self):
        self.assertEqual(
            validate_controllers({"ctrl_a": {"config": {"pico_serial": "PICO123", "label": "Pump lights"}}}),
            {
                "ctrl_a": {
                    "type": "pico_scheduler",
                    "payload": {"pico_serial": "PICO123", "report_every": 10, "devices": []},
                    "settings": {"devices": {}},
                }
            },
        )

    def test_validate_controller_devices_allows_optional_label(self):
        self.assertEqual(
            validate_controller_devices({"dev_1": {"type": "scheduled_output", "config": {"pin": 3, "label": "Main pump"}}}, "ctrl_a", "pico_scheduler")["dev_1"]["config"]["label"],
            "Main pump",
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
                        "capture_dir": "data/grow/grows/grow-basil/captures",
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
                    "capture_dir": "data/grow/grows/grow-basil/captures",
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
            validate_cameras({"rpicam_cam0": {"auto_enabled": True, "capture_dir": "data/grow/grows/grow-basil/captures"}})

    def test_validate_cameras_rejects_invalid_boolean_fields(self):
        with self.assertRaisesRegex(ValueError, "enabled"):
            validate_cameras({"rpicam_cam0": {"enabled": "yes"}})
        with self.assertRaisesRegex(ValueError, "auto_enabled"):
            validate_cameras({"rpicam_cam0": {"auto_enabled": 1}})

    def test_validate_cameras_accepts_zero_capture_every_seconds(self):
        self.assertEqual(
            validate_cameras({"rpicam_cam0": {"capture_every_seconds": 0}}),
            {"rpicam_cam0": {"capture_every_seconds": 0}},
        )

    def test_validate_cameras_legacy_auto_enabled_false_maps_to_zero_seconds(self):
        self.assertEqual(
            validate_cameras({"rpicam_cam0": {"auto_enabled": False}}),
            {"rpicam_cam0": {"capture_every_seconds": 0}},
        )

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
            validate_controllers({"ctrl_a": {"config": {"label": 123}}})

    def test_apply_config_section_rejects_devices_section(self):
        with self.assertRaisesRegex(ValueError, "unknown section"):
            apply_config_section(empty_config(), "devices", {})

    def test_apply_config_section_controllers_happy_path_and_runtime_serials(self):
        config = {
            "controllers": {"ctrl_a": {}, "ctrl_b": {"config": {"pico_serial": "OLD"}}},
            "cameras": {},
        }
        updated = apply_config_section(
            config,
            "controllers",
            {"ctrl_a": {}, "ctrl_b": {"config": {"pico_serial": "PICO123"}}},
        )
        self.assertEqual(
            updated["controllers"],
            {
                "ctrl_a": {"type": "pico_scheduler", "payload": {"report_every": 10, "devices": []}, "settings": {"devices": {}}},
                "ctrl_b": {
                    "type": "pico_scheduler",
                    "payload": {"pico_serial": "PICO123", "report_every": 10, "devices": []},
                    "settings": {"devices": {}},
                },
            },
        )
        self.assertEqual(runtime_controller_serials(updated), {"ctrl_b": "PICO123"})

    def test_runtime_controller_serials(self):
        config = {
            "controllers": {"ctrl_a": {}, "ctrl_b": {"config": {"pico_serial": "PICO123"}}},
            "cameras": {},
            "timers": {"legacy": {}},
        }
        self.assertEqual(runtime_controller_serials(config), {"ctrl_b": "PICO123"})

    def test_scheduler_devices_for_controller_returns_settings_devices(self):
        config = {
            "controllers": {
                "ctrl_a": {
                    "type": "pico_scheduler",
                    "payload": {
                        "report_every": 10,
                        "devices": [{"pin": 3, "type": "gpio", "pattern": [{"val": 1, "dur": 10}, {"val": 0, "dur": 20}]}],
                    },
                    "settings": {
                        "devices": {
                            "pump": {
                                "pin": 3,
                                "display_order": 0,
                                "visibility": "visible",
                                "programming": "enabled",
                                "editor": {"kind": "cycle", "on_seconds": 10, "off_seconds": 20, "start_at_seconds": 0},
                            }
                        }
                    },
                }
            },
            "cameras": {},
        }

        self.assertEqual(
            scheduler_devices_for_controller(config, "ctrl_a"),
            {
                "pump": {
                    "pin": 3,
                    "display_order": 0,
                    "visibility": "visible",
                    "programming": "enabled",
                    "editor": {"kind": "cycle", "on_seconds": 10, "off_seconds": 20, "start_at_seconds": 0},
                }
            },
        )

    def test_compatibility_wrappers_resolve(self):
        config = empty_config()
        self.assertEqual(hardware_view(config), config_view(config))
        self.assertEqual(apply_hardware_section(config, "cameras", {}), config_view(config))


if __name__ == "__main__":
    unittest.main()
