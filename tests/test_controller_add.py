import copy
import json
import tempfile
import unittest
from pathlib import Path

from plamp.controller_add import (
    add_controller,
    controller_config_from_report,
    display_device_id,
    preview_controller_add,
    provisioned_plamp8_state,
)
from plamp.scheduler_state import FirmwareIdentity
from plamp.config import ConfigError


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

EXPECTED_REVISION = "generated-rev"


def protocol_2_report():
    return {
        "type": "report",
        "content": {
            "firmware": {
                "name": "pico_scheduler",
                "revision": "legacy-rev",
                "protocol": 2,
            },
            "devices": [
                {
                    "id": prototype_id,
                    "type": "gpio",
                    "pin": pin,
                    "elapsed_t": index + 5,
                    "cycle_t": index + 5,
                    "current_value": 1,
                    "reschedule": 1,
                    "pattern": [{"val": 1, "dur": index + 10}, {"val": 0, "dur": index + 20}],
                }
                for index, (pin, prototype_id) in enumerate(
                    zip(range(21, 13, -1), ("one", "two", "three", "four", "five", "six", "seven", "eight"))
                )
            ],
            "overlays": [],
        },
    }


def protocol_3_report(*, revision=EXPECTED_REVISION, name="pico_scheduler", protocol=3):
    report = {
        "type": "report",
        "content": {
            "firmware": {"name": name, "revision": revision, "protocol": protocol},
            "devices": [],
            "overlays": [],
        },
    }
    for index, (pin, device_id, enabled) in enumerate(EXPECTED):
        report["content"]["devices"].append(
            {
                "id": device_id,
                "type": "gpio",
                "pin": pin,
                "enabled": enabled,
                "elapsed_t": index + 5,
                "cycle_t": index + 5,
                "current_value": 0 if not enabled else 1,
                "reschedule": 1,
                "pattern": [
                    {"val": 1, "dur": index + 10},
                    {"val": 0, "dur": index + 20},
                ],
            }
        )
    return report


class ControllerAddTests(unittest.TestCase):
    def write_config(self, root, config=None):
        path = root / "config.json"
        path.write_text(json.dumps(config or {"controllers": {}, "cameras": {}}), encoding="utf-8")
        return path

    def add(self, root, *, report, apply, allow_provision, config=None, upgrade=None):
        config_file = self.write_config(root, config)
        result = add_controller(
            "plamp8", "PICO-A", "plamp8",
            apply=apply, allow_provision=allow_provision,
            config_file=config_file, data_dir=root / "data", repo_root=root,
            lock_dir=root / "locks", timeout=3,
            report_func=report,
            upgrade_func=upgrade or (lambda *args, **kwargs: self.fail("upgrade must not run")),
            firmware_revision_func=lambda repo_root: EXPECTED_REVISION,
        )
        return result, config_file

    def test_preview_reads_once_without_changing_host_files_or_hardware(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = {"controllers": {}, "cameras": {}}
            calls = []
            result, config_file = self.add(
                root, apply=False, allow_provision=False, config=original,
                report=lambda *args, **kwargs: calls.append((args, kwargs)) or protocol_3_report(),
            )

            self.assertEqual(result["action"], "import")
            self.assertFalse(result["hardware_changed"])
            self.assertFalse(result["host_config_changed"])
            self.assertFalse(result["verified"])
            self.assertEqual(len(calls), 1)
            self.assertEqual(json.loads(config_file.read_text(encoding="utf-8")), original)
            self.assertFalse((root / "data").exists())

    def test_add_rejects_unknown_generated_revision_before_hardware_access(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = self.write_config(root)
            report_calls = []

            with self.assertRaisesRegex(ConfigError, "generated firmware revision"):
                add_controller(
                    "plamp8",
                    "PICO-A",
                    "plamp8",
                    apply=False,
                    allow_provision=False,
                    config_file=config_file,
                    data_dir=root / "data",
                    repo_root=root,
                    lock_dir=root / "locks",
                    timeout=3,
                    report_func=lambda *args, **kwargs: report_calls.append(
                        (args, kwargs)
                    )
                    or protocol_3_report(revision="unknown"),
                    firmware_revision_func=lambda repo_root: "unknown",
                )

            self.assertEqual(report_calls, [])

    def test_apply_imports_compatible_report_without_upgrade_and_saves_timer_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            observed = protocol_3_report()
            observed["content"]["devices"].reverse()
            observed["content"]["devices"][0]["cycle_t"] = 97
            result, config_file = self.add(
                root, apply=True, allow_provision=False,
                report=lambda *args, **kwargs: observed,
            )

            self.assertEqual(result["action"], "import")
            self.assertFalse(result["hardware_changed"])
            self.assertTrue(result["host_config_changed"])
            self.assertTrue(result["verified"])
            self.assertIsNone(result["recovery_path"])
            saved = json.loads(config_file.read_text(encoding="utf-8"))
            self.assertEqual(saved["controllers"]["plamp8"]["payload"]["pico_serial"], "PICO-A")
            self.assertEqual(
                list(saved["controllers"]["plamp8"]["settings"]["devices"]),
                ["lights_2", "lights_1", "fan", "pump", "nutrients", "agitator", "ph_down", "ph_up"],
            )
            persisted = json.loads(
                (root / "data" / "timers" / "plamp8.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                [device["id"] for device in persisted["devices"]],
                [device["id"] for device in observed["content"]["devices"]],
            )
            self.assertEqual(persisted["devices"][0]["current_t"], 97)
            self.assertEqual(
                persisted["devices"][0]["pattern"],
                [{"val": 1, "dur": 17}, {"val": 0, "dur": 27}],
            )

    def test_apply_rejects_required_provision_without_host_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = self.write_config(root)

            with self.assertRaisesRegex(ConfigError, "explicit --provision"):
                add_controller(
                    "plamp8", "PICO-A", "plamp8", apply=True, allow_provision=False,
                    config_file=config_file, data_dir=root / "data", repo_root=root,
                    lock_dir=root / "locks", timeout=3,
                    report_func=lambda *args, **kwargs: protocol_2_report(),
                    upgrade_func=lambda *args, **kwargs: self.fail("unauthorized provision must not upgrade"),
                    firmware_revision_func=lambda repo_root: EXPECTED_REVISION,
                )

            self.assertEqual(json.loads(config_file.read_text(encoding="utf-8")), {"controllers": {}, "cameras": {}})
            self.assertFalse((root / "data").exists())

    def test_apply_provision_backs_up_maps_verifies_and_imports(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            calls = []

            def upgrade(serial, state, **kwargs):
                calls.append((serial, state, kwargs))
                return {"report": protocol_3_report()}

            result, config_file = self.add(
                root, apply=True, allow_provision=True,
                report=lambda *args, **kwargs: protocol_2_report(), upgrade=upgrade,
            )

            recovery = root / "data" / "controller-backups" / "plamp8-PICO-A-pre-provision.json"
            self.assertEqual(result["action"], "provision")
            self.assertTrue(result["hardware_changed"])
            self.assertTrue(result["reset"])
            self.assertTrue(result["verified"])
            self.assertEqual(result["recovery_path"], str(recovery))
            self.assertEqual(json.loads(recovery.read_text(encoding="utf-8")), protocol_2_report())
            self.assertEqual(calls[0][0], "PICO-A")
            self.assertEqual(calls[0][1], provisioned_plamp8_state(protocol_2_report()))
            self.assertEqual(calls[0][2]["repo_root"], root)
            self.assertEqual(json.loads(config_file.read_text(encoding="utf-8"))["controllers"]["plamp8"]["payload"]["pico_serial"], "PICO-A")

    def test_provision_accepts_the_generated_scheduler_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            generated_report = protocol_3_report()
            result, config_file = self.add(
                root, apply=True, allow_provision=True,
                report=lambda *args, **kwargs: protocol_2_report(),
                upgrade=lambda *args, **kwargs: {"report": generated_report},
            )

            self.assertTrue(result["verified"])
            self.assertEqual(result["action"], "provision")
            self.assertIn("plamp8", json.loads(config_file.read_text(encoding="utf-8"))["controllers"])

    def test_provision_rejects_upgraded_report_with_wrong_firmware_family_or_protocol(self):
        for upgraded_report, error in (
            (protocol_3_report(name="pico_doser"), "pico_scheduler"),
            (protocol_3_report(protocol=4), "unsupported firmware protocol"),
        ):
            with self.subTest(firmware=upgraded_report["content"]["firmware"]):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    config_file = self.write_config(root)
                    with self.assertRaisesRegex(ValueError, error):
                        add_controller(
                            "plamp8", "PICO-A", "plamp8", apply=True, allow_provision=True,
                            config_file=config_file, data_dir=root / "data", repo_root=root,
                            lock_dir=root / "locks", timeout=3,
                            report_func=lambda *args, **kwargs: protocol_2_report(),
                            upgrade_func=lambda *args, **kwargs: {"report": upgraded_report},
                            firmware_revision_func=lambda repo_root: EXPECTED_REVISION,
                        )
                    self.assertEqual(json.loads(config_file.read_text(encoding="utf-8")), {"controllers": {}, "cameras": {}})

    def test_upgrade_failure_keeps_config_and_recovery_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = self.write_config(root)

            with self.assertRaisesRegex(ConnectionError, "flash failed"):
                add_controller(
                    "plamp8", "PICO-A", "plamp8", apply=True, allow_provision=True,
                    config_file=config_file, data_dir=root / "data", repo_root=root,
                    lock_dir=root / "locks", timeout=3,
                    report_func=lambda *args, **kwargs: protocol_2_report(),
                    upgrade_func=lambda *args, **kwargs: (_ for _ in ()).throw(ConnectionError("flash failed")),
                    firmware_revision_func=lambda repo_root: EXPECTED_REVISION,
                )

            self.assertEqual(json.loads(config_file.read_text(encoding="utf-8")), {"controllers": {}, "cameras": {}})
            self.assertEqual(
                json.loads((root / "data" / "controller-backups" / "plamp8-PICO-A-pre-provision.json").read_text(encoding="utf-8")),
                protocol_2_report(),
            )

    def test_existing_empty_matching_controller_is_filled_without_duplication(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            empty = {
                "controllers": {"plamp8": {"type": "pico_scheduler", "payload": {"pico_serial": "PICO-A"}}},
                "cameras": {},
            }
            result, config_file = self.add(
                root, config=empty, apply=True, allow_provision=False,
                report=lambda *args, **kwargs: protocol_3_report(),
            )

            self.assertTrue(result["host_config_changed"])
            self.assertEqual(list(json.loads(config_file.read_text(encoding="utf-8"))["controllers"]), ["plamp8"])

    def test_existing_nonempty_controller_or_assigned_serial_is_rejected(self):
        for config in (
            {"controllers": {"plamp8": controller_config_from_report("PICO-A", protocol_3_report())}, "cameras": {}},
            {"controllers": {"other": controller_config_from_report("PICO-A", protocol_3_report())}, "cameras": {}},
        ):
            with self.subTest(config=config):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    config_file = self.write_config(root, copy.deepcopy(config))
                    with self.assertRaisesRegex(ConfigError, "already"):
                        add_controller(
                            "plamp8", "PICO-A", "plamp8", apply=True, allow_provision=False,
                            config_file=config_file, data_dir=root / "data", repo_root=root,
                            lock_dir=root / "locks", timeout=3,
                            report_func=lambda *args, **kwargs: protocol_3_report(),
                            firmware_revision_func=lambda repo_root: EXPECTED_REVISION,
                        )
                    self.assertEqual(json.loads(config_file.read_text(encoding="utf-8")), config)

    def test_failed_post_upgrade_verification_does_not_commit_host_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = self.write_config(root)
            with self.assertRaisesRegex(ConfigError, "verification"):
                add_controller(
                    "plamp8", "PICO-A", "plamp8", apply=True, allow_provision=True,
                    config_file=config_file, data_dir=root / "data", repo_root=root,
                    lock_dir=root / "locks", timeout=3,
                    report_func=lambda *args, **kwargs: protocol_2_report(),
                    upgrade_func=lambda *args, **kwargs: {"report": protocol_2_report()},
                    firmware_revision_func=lambda repo_root: EXPECTED_REVISION,
                )
            self.assertEqual(json.loads(config_file.read_text(encoding="utf-8")), {"controllers": {}, "cameras": {}})
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
        expected = FirmwareIdentity("pico_scheduler", EXPECTED_REVISION, 3)

        preview = preview_controller_add("tower", "PICO-1", protocol_3_report(), expected)

        self.assertEqual(preview["action"], "import")
        self.assertFalse(preview["requires_reset"])
        self.assertEqual(preview["controller"], "tower")
        self.assertEqual(preview["serial"], "PICO-1")
        self.assertEqual(preview["profile"], "plamp8")
        self.assertEqual(preview["before"][0]["id"], "ph_up")
        self.assertEqual(preview["after"][0]["id"], "ph_up")

    def test_preview_provisions_protocol_2_report(self):
        preview = preview_controller_add(
            "tower", "PICO-1", protocol_2_report(),
            FirmwareIdentity("pico_scheduler", EXPECTED_REVISION, 3),
        )

        self.assertEqual(preview["action"], "provision")
        self.assertTrue(preview["requires_reset"])
        self.assertEqual(
            preview["observed_identity"],
            {"name": "pico_scheduler", "revision": "legacy-rev", "protocol": 2},
        )
        self.assertIsNone(preview["before"][0]["enabled"])

    def test_preview_requires_firmware_identity_and_supported_scheduler_protocol(self):
        expected = FirmwareIdentity("pico_scheduler", EXPECTED_REVISION, 3)
        unidentified = protocol_2_report()
        del unidentified["content"]["firmware"]
        foreign = protocol_2_report()
        foreign["content"]["firmware"]["name"] = "pico_doser"
        unsupported = protocol_3_report(protocol=4)

        for report, message in (
            (unidentified, "firmware identity"),
            (foreign, "pico_scheduler"),
            (unsupported, "unsupported firmware protocol"),
        ):
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    preview_controller_add("tower", "PICO-1", report, expected)

    def test_protocol_3_revision_or_profile_mismatch_requires_provision(self):
        expected = FirmwareIdentity("pico_scheduler", EXPECTED_REVISION, 3)
        wrong_revision = protocol_3_report(revision="old-rev")
        wrong_id = protocol_3_report()
        wrong_id["content"]["devices"][0]["id"] = "one"
        wrong_enabled = protocol_3_report()
        wrong_enabled["content"]["devices"][0]["enabled"] = True

        for report in (wrong_revision, wrong_id, wrong_enabled):
            with self.subTest(report=report):
                preview = preview_controller_add("tower", "PICO-1", report, expected)
                self.assertEqual(preview["action"], "provision")
                self.assertTrue(preview["requires_reset"])

    def test_preview_rejects_incomplete_or_pwm_report(self):
        expected = FirmwareIdentity("pico_scheduler", EXPECTED_REVISION, 3)
        incomplete = protocol_3_report()
        del incomplete["content"]["devices"][0]["pattern"]
        pwm = protocol_3_report()
        pwm["content"]["devices"][0]["type"] = "pwm"

        with self.assertRaisesRegex(ValueError, "invalid fields"):
            preview_controller_add("tower", "PICO-1", incomplete, expected)
        with self.assertRaisesRegex(ValueError, "unsupported type: pwm"):
            preview_controller_add("tower", "PICO-1", pwm, expected)

    def test_preview_rejects_invalid_complete_report_fields(self):
        expected = FirmwareIdentity("pico_scheduler", EXPECTED_REVISION, 3)
        invalid_elapsed = protocol_3_report()
        invalid_elapsed["content"]["devices"][0]["elapsed_t"] = "five"
        invalid_value = protocol_3_report()
        invalid_value["content"]["devices"][0]["current_value"] = []
        empty_revision = protocol_3_report(revision="")

        for report, message in (
            (invalid_elapsed, "elapsed_t must be an integer"),
            (invalid_value, "current_value must be an integer"),
            (empty_revision, "firmware revision"),
        ):
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    preview_controller_add("tower", "PICO-1", report, expected)

    def test_controller_config_from_report_converts_semantic_devices_and_editors(self):
        report = protocol_3_report()
        report["content"]["devices"][0].update(
            {
                "elapsed_t": 42,
                "cycle_t": 42,
                "pattern": [
                    {"val": 1, "dur": 4},
                    {"val": 0, "dur": 6},
                    {"val": 1, "dur": 8},
                ],
            }
        )

        controller = controller_config_from_report("PICO-1", report)
        devices = controller["settings"]["devices"]

        self.assertEqual(set(controller), {"type", "payload", "settings"})
        self.assertEqual(controller["payload"], {"pico_serial": "PICO-1", "report_every": 10})
        self.assertEqual(devices["ph_up"], {
            "pin": 21,
            "output_type": "gpio",
            "display_order": 0,
            "visibility": "visible",
            "programming": "disabled",
            "editor": {
                "kind": "events",
                "events": [
                    {"val": 1, "dur": 4},
                    {"val": 0, "dur": 6},
                    {"val": 1, "dur": 8},
                ],
                "start_at_seconds": 42,
            },
        })
        self.assertEqual(devices["pump"]["programming"], "enabled")
        self.assertEqual(devices["pump"]["editor"], {"kind": "cycle", "on_seconds": 14, "off_seconds": 24, "start_at_seconds": 9})
        self.assertNotIn("label", devices["pump"])


if __name__ == "__main__":
    unittest.main()
