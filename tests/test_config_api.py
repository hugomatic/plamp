import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

import plamp_web.server as server


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
