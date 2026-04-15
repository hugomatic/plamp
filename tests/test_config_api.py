import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

import plamp_web.server as server


class DummyMonitor:
    def __init__(self, pico_serial: str):
        self.pico_serial = pico_serial
        self.started = False
        self.stopped = False
        self.joined = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    def join(self) -> None:
        self.joined = True


class ConfigApiTests(unittest.TestCase):
    def make_config(self, root: Path, data: dict) -> Path:
        path = root / "data" / "config.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_get_config_returns_config_and_detected_hardware_separately(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = self.make_config(
                root,
                {
                    "controllers": {"pump_lights": {"pico_serial": "abc"}},
                    "devices": {"pump": {"controller": "pump_lights", "pin": 3, "editor": "cycle"}},
                    "cameras": {"rpicam_cam0": {}},
                },
            )
            with (
                patch.object(server, "CONFIG_FILE", config_file),
                patch.object(server, "enumerate_picos", return_value=[{"serial": "abc", "port": "/dev/ttyACM0"}]),
                patch.object(server.hardware_inventory, "detect_rpicam_cameras", return_value=[{"key": "rpicam:cam0", "index": 0, "model": "imx708_wide", "sensor": "imx708", "lens": "wide"}]),
            ):
                data = server.get_config()

        self.assertIn("config", data)
        self.assertIn("detected", data)
        self.assertEqual(data["config"]["controllers"]["pump_lights"]["pico_serial"], "abc")
        self.assertEqual(data["config"]["devices"]["pump"]["editor"], "cycle")
        self.assertEqual(data["detected"]["picos"][0]["serial"], "abc")
        self.assertEqual(data["detected"]["cameras"][0]["key"], "rpicam_cam0")

    def test_settings_summary_includes_config_and_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = self.make_config(
                root,
                {
                    "controllers": {"pump_lights": {"pico_serial": "abc", "label": "Pump lights"}},
                    "devices": {},
                    "cameras": {},
                },
            )
            with (
                patch.object(server, "CONFIG_FILE", config_file),
                patch.object(server, "enumerate_picos", return_value=[]),
                patch.object(server.hardware_inventory, "detect_rpicam_cameras", return_value=[]),
            ):
                summary = server.settings_summary()

        self.assertIn("config", summary)
        self.assertIn("detected", summary)
        self.assertEqual(summary["config"]["controllers"]["pump_lights"]["label"], "Pump lights")

    def test_get_settings_page_uses_combined_settings_payload(self):
        with patch.object(
            server,
            "settings_summary",
            return_value={
                "config": {"controllers": {}, "devices": {}, "cameras": {}},
                "detected": {"picos": [], "cameras": []},
                "host": {"hostname": "plamp", "network": []},
                "picos": [],
                "software": {"git_short_commit": "abc123", "git_branch": "main", "git_dirty": False},
                "storage": {"path": "/tmp", "free": "1 GB", "used": "1 GB", "total": "2 GB"},
            },
        ):
            response = server.get_settings_page()

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Plamp setup", response.body)

    def test_config_route_is_removed(self):
        routes = {route.path for route in server.app.routes}
        self.assertNotIn("/config", routes)

    def test_get_host_config_returns_hostname(self):
        with patch.object(server.socket, "gethostname", return_value="plamp"):
            data = server.get_host_config()

        self.assertEqual(data, {"hostname": "plamp"})

    def test_post_host_config_hostname_rejects_invalid_value(self):
        with self.assertRaises(HTTPException) as cm:
            server.post_host_config_hostname({"hostname": "bad host name"})

        self.assertEqual(cm.exception.status_code, 422)
        self.assertIn("hostname", cm.exception.detail)

    def test_post_host_config_hostname_applies_value(self):
        with patch.object(
            server,
            "apply_hostname",
            return_value={"hostname": "plamp-kiosk", "message": "hostname updated"},
        ) as apply_hostname:
            data = server.post_host_config_hostname({"hostname": "plamp-kiosk"})

        apply_hostname.assert_called_once_with("plamp-kiosk")
        self.assertEqual(data["hostname"], "plamp-kiosk")
        self.assertEqual(data["message"], "hostname updated")

    def test_put_config_devices_updates_top_level_devices(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = self.make_config(
                root,
                {
                    "controllers": {"pump_lights": {"pico_serial": "e66038b71387a039"}},
                    "devices": {},
                    "cameras": {},
                },
            )
            with patch.object(server, "CONFIG_FILE", config_file):
                data = server.put_config_devices({"pump": {"controller": "pump_lights", "pin": 3, "editor": "cycle"}})

            saved = json.loads(config_file.read_text(encoding="utf-8"))

        self.assertEqual(data["config"]["devices"]["pump"]["pin"], 3)
        self.assertEqual(saved["devices"]["pump"], {"controller": "pump_lights", "pin": 3, "editor": "cycle"})

    def test_put_config_devices_preserves_unrelated_top_level_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = self.make_config(
                root,
                {
                    "controllers": {"pump_lights": {"pico_serial": "e66038b71387a039"}},
                    "devices": {},
                    "cameras": {"rpicam_cam0": {}},
                    "time_format": "12h",
                    "camera": {"ir_filter": "auto"},
                },
            )
            with patch.object(server, "CONFIG_FILE", config_file):
                server.put_config_devices({"pump": {"controller": "pump_lights", "pin": 3, "editor": "cycle"}})

            saved = json.loads(config_file.read_text(encoding="utf-8"))

        self.assertEqual(saved["time_format"], "12h")
        self.assertEqual(saved["camera"], {"ir_filter": "auto"})
        self.assertEqual(saved["cameras"], {"rpicam_cam0": {}})
        self.assertEqual(saved["devices"]["pump"], {"controller": "pump_lights", "pin": 3, "editor": "cycle"})

    def test_get_timer_config_reflects_config_device_changes_immediately(self):
        state = {
            "report_every": 1,
            "events": [
                {"id": "runtime-lamp", "type": "gpio", "ch": 2, "current_t": 1, "reschedule": 1, "pattern": [{"val": 1, "dur": 10}, {"val": 0, "dur": 50}]},
                {"id": "runtime-fan", "type": "pwm", "ch": 3, "current_t": 2, "reschedule": 1, "pattern": [{"val": 1000, "dur": 10}, {"val": 0, "dur": 50}]},
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = self.make_config(
                root,
                {
                    "controllers": {"sprouter": {"pico_serial": "abc"}},
                    "devices": {"lamp": {"controller": "sprouter", "pin": 2, "editor": "clock_window"}},
                    "cameras": {},
                },
            )
            with (
                patch.object(server, "CONFIG_FILE", config_file),
                patch.object(server, "state_for_role", return_value=state),
            ):
                initial = server.get_timer_config()
                server.put_config_devices({"fan": {"controller": "sprouter", "pin": 3, "editor": "cycle"}})
                updated = server.get_timer_config()

        self.assertEqual(
            initial,
            {
                "roles": ["sprouter"],
                "channels": {
                    "sprouter": [
                        {"role": "sprouter", "id": "lamp", "name": "lamp", "pin": 2, "type": "gpio", "default_editor": "clock_window"}
                    ]
                },
                "time_format": "12h",
            },
        )
        self.assertEqual(
            updated,
            {
                "roles": ["sprouter"],
                "channels": {
                    "sprouter": [
                        {"role": "sprouter", "id": "fan", "name": "fan", "pin": 3, "type": "pwm", "default_editor": "cycle"}
                    ]
                },
                "time_format": "12h",
            },
        )

    def test_configured_time_format_reads_top_level_value_from_raw_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = self.make_config(
                root,
                {
                    "controllers": {},
                    "devices": {},
                    "cameras": {},
                    "time_format": "24h",
                },
            )
            with patch.object(server, "CONFIG_FILE", config_file):
                self.assertEqual(server.configured_time_format(), "24h")

    def test_api_test_page_uses_empty_payload_when_default_timer_state_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = self.make_config(root, {"controllers": {}, "devices": {}, "cameras": {}})
            timers_dir = root / "data" / "timers"
            timers_dir.mkdir(parents=True)
            with (
                patch.object(server, "CONFIG_FILE", config_file),
                patch.object(server, "TIMERS_DIR", timers_dir),
                patch.object(server, "configured_timer_roles", return_value=["pump_n_lights"]),
            ):
                response = server.api_test_page_response()

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"pump_n_lights", response.body)
        self.assertIn(b"{}", response.body)

    def test_put_config_devices_rejects_unknown_controller(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = self.make_config(root, {"controllers": {}, "devices": {}, "cameras": {}})
            with patch.object(server, "CONFIG_FILE", config_file):
                with self.assertRaises(HTTPException) as cm:
                    server.put_config_devices({"pump": {"controller": "missing", "pin": 3, "editor": "cycle"}})

        self.assertEqual(cm.exception.status_code, 422)
        self.assertIn("unknown controller", cm.exception.detail)

    def test_put_config_controllers_reconciles_running_monitors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = self.make_config(
                root,
                {
                    "controllers": {
                        "keep": {"pico_serial": "KEEP_NEW"},
                        "drop": {"pico_serial": "DROP_OLD"},
                    },
                    "devices": {},
                    "cameras": {},
                },
            )
            old_keep = DummyMonitor("KEEP_OLD")
            old_drop = DummyMonitor("DROP_OLD")
            new_keep = DummyMonitor("KEEP_NEW")
            monitor_map = {"keep": old_keep, "drop": old_drop}
            with (
                patch.object(server, "CONFIG_FILE", config_file),
                patch.object(server, "monitors", monitor_map),
                patch.object(server, "PicoMonitor", side_effect=[new_keep]),
            ):
                server.put_config_controllers({"keep": {"pico_serial": "KEEP_NEW"}})

        self.assertTrue(old_keep.stopped)
        self.assertFalse(old_keep.started)
        self.assertTrue(old_drop.stopped)
        self.assertFalse(old_drop.started)
        self.assertTrue(new_keep.started)
        self.assertIs(monitor_map["keep"], new_keep)
        self.assertEqual(monitor_map["keep"].pico_serial, "KEEP_NEW")
        self.assertNotIn("drop", monitor_map)

    def test_post_timer_channel_schedule_uses_saved_state_not_stale_live_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = self.make_config(
                root,
                {
                    "controllers": {"pump_lights": {"pico_serial": "abc"}},
                    "devices": {
                        "pump": {"controller": "pump_lights", "pin": 2, "editor": "cycle"},
                        "lights": {"controller": "pump_lights", "pin": 3, "editor": "clock_window"},
                    },
                    "cameras": {},
                },
            )
            timers_dir = root / "data" / "timers"
            timers_dir.mkdir(parents=True)
            (timers_dir / "pump_lights.json").write_text(
                json.dumps(
                    {
                        "report_every": 1,
                        "events": [
                            {"id": "pump", "type": "gpio", "ch": 2, "current_t": 0, "reschedule": 1, "pattern": [{"val": 1, "dur": 10}, {"val": 0, "dur": 20}]}
                        ],
                    }
                ),
                encoding="utf-8",
            )
            stale_live = {
                "report_every": 1,
                "events": [
                    {"id": "test_pin", "type": "gpio", "ch": 25, "current_t": 0, "reschedule": 1, "pattern": [{"val": 1, "dur": 12}, {"val": 0, "dur": 5}]}
                ],
            }
            with (
                patch.object(server, "CONFIG_FILE", config_file),
                patch.object(server, "TIMERS_DIR", timers_dir),
                patch.object(server, "latest_timer_state", return_value=stale_live),
                patch.object(server, "apply_timer_state", return_value={"ok": True}),
            ):
                server.post_timer_channel_schedule("pump_lights", "lights", {"mode": "clock_window", "on_time": "06:00", "off_time": "18:00"})

            saved = json.loads((timers_dir / "pump_lights.json").read_text(encoding="utf-8"))

        self.assertEqual([event["id"] for event in saved["events"]], ["pump", "lights"])
        self.assertEqual(saved["events"][0]["ch"], 2)
        self.assertEqual(saved["events"][1]["ch"], 3)

    def test_post_timer_channel_schedule_reports_saved_when_pico_is_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = self.make_config(
                root,
                {
                    "controllers": {"pump_lights": {"pico_serial": "abc"}},
                    "devices": {"pump": {"controller": "pump_lights", "pin": 2, "editor": "cycle"}},
                    "cameras": {},
                },
            )
            timers_dir = root / "data" / "timers"
            timers_dir.mkdir(parents=True)
            (timers_dir / "pump_lights.json").write_text(json.dumps({"report_every": 1, "events": []}), encoding="utf-8")
            with (
                patch.object(server, "CONFIG_FILE", config_file),
                patch.object(server, "TIMERS_DIR", timers_dir),
                patch.object(server, "latest_timer_state", return_value=None),
                patch.object(server, "apply_timer_state", side_effect=HTTPException(status_code=409, detail="Pico for role pump_lights is not connected: abc")),
            ):
                response = server.post_timer_channel_schedule("pump_lights", "pump", {"mode": "cycle", "on_seconds": 10, "off_seconds": 20, "start_at_seconds": 0})

            saved = json.loads((timers_dir / "pump_lights.json").read_text(encoding="utf-8"))

        self.assertTrue(response["success"])
        self.assertIn("saved", response["message"])
        self.assertIn("not connected", response["message"])
        self.assertEqual(saved["events"][0]["id"], "pump")
