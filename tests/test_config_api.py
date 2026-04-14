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
            config_file = self.make_config(root, {"timers": [{"role": "pump_lights", "pico_serial": "abc", "channels": []}]})
            with (
                patch.object(server, "CONFIG_FILE", config_file),
                patch.object(server, "enumerate_picos", return_value=[{"serial": "abc", "port": "/dev/ttyACM0"}]),
                patch.object(server.hardware_inventory, "detect_rpicam_cameras", return_value=[{"key": "rpicam:cam0", "index": 0, "model": "imx708_wide", "sensor": "imx708", "lens": "wide"}]),
            ):
                data = server.get_config()

        self.assertIn("config", data)
        self.assertIn("detected", data)
        self.assertEqual(data["config"]["controllers"]["controller:pump_lights"]["name"], "pump_lights")
        self.assertEqual(data["detected"]["picos"][0]["serial"], "abc")
        self.assertEqual(data["detected"]["cameras"][0]["key"], "rpicam:cam0")

    def test_put_config_devices_updates_hardware_and_timers_projection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = self.make_config(root, {"timers": [], "hardware": {"controllers": {"controller:pump_lights": {"name": "pump_lights", "type": "pico_scheduler", "match": {"pico_serial": "e66038b71387a039"}}}, "devices": {}, "cameras": {}}})
            with patch.object(server, "CONFIG_FILE", config_file):
                data = server.put_config_devices({"pump": {"name": "Pump", "type": "gpio", "controller": "controller:pump_lights", "pin": 3, "default_editor": "cycle"}})

            saved = json.loads(config_file.read_text(encoding="utf-8"))

        self.assertEqual(data["config"]["devices"]["pump"]["pin"], 3)
        self.assertEqual(saved["timers"][0]["channels"][0]["id"], "pump")

    def test_put_config_devices_rejects_unknown_controller(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = self.make_config(root, {"timers": [], "hardware": {"controllers": {}, "devices": {}, "cameras": {}}})
            with patch.object(server, "CONFIG_FILE", config_file):
                with self.assertRaises(HTTPException) as cm:
                    server.put_config_devices({"pump": {"name": "Pump", "type": "gpio", "controller": "controller:missing", "pin": 3}})

        self.assertEqual(cm.exception.status_code, 422)
        self.assertIn("unknown controller", cm.exception.detail)
