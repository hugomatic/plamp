import unittest
from types import SimpleNamespace

from plamp.pico_discovery import discover_picos, find_pico_port


class PicoDiscoveryTests(unittest.TestCase):
    def test_discovers_raspberry_pi_usb_serial_devices(self):
        ports = lambda: [
            SimpleNamespace(device="/dev/ttyACM1", vid=0x2E8A, serial_number="PICO-B"),
            SimpleNamespace(device="/dev/ttyUSB0", vid=0x1234, serial_number="OTHER"),
        ]
        self.assertEqual(
            [(item.serial, item.device) for item in discover_picos(comports=ports)],
            [("PICO-B", "/dev/ttyACM1")],
        )

    def test_finds_reassigned_path_by_serial_number(self):
        ports = lambda: [
            SimpleNamespace(device="/dev/ttyACM7", vid=0x2E8A, serial_number="PICO-A")
        ]
        self.assertEqual(find_pico_port("PICO-A", comports=ports), "/dev/ttyACM7")

    def test_missing_serial_returns_none(self):
        self.assertIsNone(find_pico_port("missing", comports=lambda: []))
