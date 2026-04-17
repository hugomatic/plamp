import unittest
from unittest.mock import patch

from plamp_web.hardware_inventory import rpicam_key, detect_rpicam_cameras, parse_rpicam_list_cameras


RPICAM_OUTPUT = """
Available cameras
-----------------
0 : imx708_wide [4608x2592 10-bit RGGB] (/base/soc/i2c0mux/i2c@1/imx708@1a)
    Modes: 'SRGGB10_CSI2P' : 1536x864 [120.13 fps - (0, 0)/4608x2592 crop]
1 : ov5647 [2592x1944 10-bit GBRG] (/base/soc/i2c0mux/i2c@2/ov5647@36)
"""


class HardwareInventoryTests(unittest.TestCase):
    def test_parse_rpicam_list_cameras_detects_sensor_and_wide_lens(self):
        self.assertEqual(
            parse_rpicam_list_cameras(RPICAM_OUTPUT),
            [
                {"key": "rpicam:cam0", "connector": "cam0", "index": 0, "sensor": "imx708", "model": "imx708_wide", "lens": "wide", "path": "/base/soc/i2c0mux/i2c@1/imx708@1a"},
                {"key": "rpicam:cam1", "connector": "cam1", "index": 1, "sensor": "ov5647", "model": "ov5647", "lens": "normal", "path": "/base/soc/i2c0mux/i2c@2/ov5647@36"},
            ],
        )

    def test_rpicam_key_uses_connector_name(self):
        self.assertEqual(rpicam_key("cam0"), "rpicam:cam0")

    def test_detect_rpicam_cameras_falls_back_to_libcamera_hello(self):
        calls = []

        def fake_check_output(command, **kwargs):
            calls.append(command)
            if command[0] == "rpicam-hello":
                raise FileNotFoundError("missing")
            return RPICAM_OUTPUT

        with patch("plamp_web.hardware_inventory.subprocess.check_output", side_effect=fake_check_output):
            cameras = detect_rpicam_cameras()

        self.assertEqual([call[0] for call in calls], ["rpicam-hello", "libcamera-hello"])
        self.assertEqual(cameras[0]["key"], "rpicam:cam0")
