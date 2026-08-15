import unittest

from plamp.controller_add import (
    controller_config_from_report,
    display_device_id,
    preview_controller_add,
    provisioned_plamp8_state,
)
from plamp.scheduler_state import FirmwareIdentity


EXPECTED = [
    (21, "ph_up", False),
    (20, "ph_down", False),
    (19, "agitator", False),
    (18, "nutrients", False),
    (17, "pump", True),
    (16, "fan", True),
    (15, "lights_1", True),
    (14, "lights_2", True),
]


def protocol_2_report():
    return {
        "type": "report",
        "content": {
            "devices": [
                {
                    "id": prototype_id,
                    "type": "gpio",
                    "pin": pin,
                    "enabled": True,
                    "cycle_t": index + 5,
                    "reschedule": 1,
                    "pattern": [{"val": 1, "dur": index + 10}, {"val": 0, "dur": index + 20}],
                }
                for index, (pin, prototype_id) in enumerate(
                    zip(range(21, 13, -1), ("one", "two", "three", "four", "five", "six", "seven", "eight"))
                )
            ]
        },
    }


def protocol_3_report():
    report = protocol_2_report()
    report["content"]["firmware"] = {
        "name": "pico_scheduler", "revision": "plamp8", "protocol": 3,
    }
    return report


class ControllerAddTests(unittest.TestCase):
    def test_provisioned_plamp8_state_replaces_prototype_ids_by_pin(self):
        state = provisioned_plamp8_state(protocol_2_report())

        self.assertEqual(
            [(item["pin"], item["id"], item["enabled"]) for item in state["devices"]],
            EXPECTED,
        )
        self.assertEqual(
            [item["pattern"] for item in state["devices"]],
            [item["pattern"] for item in protocol_2_report()["content"]["devices"]],
        )
        self.assertEqual([item["current_t"] for item in state["devices"]], list(range(5, 13)))

    def test_display_device_id_humanizes_profile_ids(self):
        self.assertEqual(display_device_id("lights_1"), "Lights 1")
        self.assertEqual(display_device_id("ph_up"), "Ph up")

    def test_provisioned_plamp8_state_rejects_duplicate_or_missing_profile_pins(self):
        duplicate = protocol_2_report()
        duplicate["content"]["devices"][-1]["pin"] = 15
        with self.assertRaisesRegex(ValueError, "unique profile pins"):
            provisioned_plamp8_state(duplicate)

        missing = protocol_2_report()
        missing["content"]["devices"] = missing["content"]["devices"][:-1]
        with self.assertRaisesRegex(ValueError, "exactly eight"):
            provisioned_plamp8_state(missing)

    def test_provisioned_plamp8_state_rejects_another_firmware_family(self):
        report = protocol_3_report()
        report["content"]["firmware"]["name"] = "pico_doser"

        with self.assertRaisesRegex(ValueError, "pico_scheduler"):
            provisioned_plamp8_state(report)

    def test_preview_imports_compatible_protocol_3_report(self):
        expected = FirmwareIdentity("pico_scheduler", "plamp8", 3)

        preview = preview_controller_add("tower", "PICO-1", protocol_3_report(), expected)

        self.assertEqual(preview["action"], "import")
        self.assertFalse(preview["requires_reset"])
        self.assertEqual(preview["controller"], "tower")
        self.assertEqual(preview["serial"], "PICO-1")
        self.assertEqual(preview["profile"], "plamp8")
        self.assertEqual(preview["before"][0]["id"], "one")
        self.assertEqual(preview["after"][0]["id"], "ph_up")

    def test_preview_provisions_protocol_2_report(self):
        preview = preview_controller_add(
            "tower", "PICO-1", protocol_2_report(), FirmwareIdentity("pico_scheduler", "plamp8", 3)
        )

        self.assertEqual(preview["action"], "provision")
        self.assertTrue(preview["requires_reset"])
        self.assertIsNone(preview["observed_identity"])

    def test_controller_config_from_report_converts_semantic_devices_and_editors(self):
        report = protocol_2_report()
        report["content"]["devices"][0].update(
            {"type": "pwm", "elapsed_t": 42, "pattern": [{"val": 10, "dur": 4}, {"val": 0, "dur": 6}, {"val": 5, "dur": 8}]}
        )
        report["content"]["devices"][0].pop("cycle_t")

        controller = controller_config_from_report("PICO-1", report)
        devices = controller["settings"]["devices"]

        self.assertEqual(set(controller), {"type", "payload", "settings"})
        self.assertEqual(controller["payload"], {"pico_serial": "PICO-1", "report_every": 10})
        self.assertEqual(devices["ph_up"], {
            "pin": 21,
            "output_type": "pwm",
            "display_order": 0,
            "visibility": "visible",
            "programming": "disabled",
            "editor": {"kind": "events", "events": [{"val": 10, "dur": 4}, {"val": 0, "dur": 6}, {"val": 5, "dur": 8}], "start_at_seconds": 42},
        })
        self.assertEqual(devices["pump"]["programming"], "enabled")
        self.assertEqual(devices["pump"]["editor"], {"kind": "cycle", "on_seconds": 14, "off_seconds": 24, "start_at_seconds": 9})
        self.assertNotIn("label", devices["pump"])


if __name__ == "__main__":
    unittest.main()
