import unittest
from unittest.mock import patch

from plamp_web import server


class PulseLogFormattingTests(unittest.TestCase):
    def test_format_pulse_tx_includes_on_off_channel_and_duration(self):
        self.assertEqual(
            server.format_pico_tx_log("plamp8", "p 19 1 20", channel_name="Agitator"),
            "pico pulse role=plamp8 channel=Agitator pin=19 ON for 20s",
        )
        self.assertEqual(
            server.format_pico_tx_log("plamp8", "p 19 0 5", channel_name="Agitator"),
            "pico pulse role=plamp8 channel=Agitator pin=19 OFF for 5s",
        )

    def test_format_pulse_tx_accepts_legacy_pin_seconds_as_on(self):
        self.assertEqual(
            server.format_pico_tx_log("plamp8", "p 19 15", channel_name="Agitator"),
            "pico pulse role=plamp8 channel=Agitator pin=19 ON for 15s",
        )

    def test_format_non_pulse_tx_keeps_raw_command(self):
        self.assertEqual(
            server.format_pico_tx_log("plamp8", "configure"),
            "pico-cmd tx role=plamp8 cmd='configure'",
        )

    def test_channel_name_for_pin_uses_configured_device_id(self):
        config = {
            "controllers": {
                "plamp8": {
                    "type": "pico_scheduler",
                    "settings": {
                        "devices": {
                            "agitator": {"pin": 19, "output_type": "gpio"},
                        }
                    },
                }
            }
        }
        with patch.object(server, "load_config", return_value=config):
            self.assertEqual(server.channel_name_for_pin("plamp8", 19), "Agitator")
            self.assertIsNone(server.channel_name_for_pin("plamp8", 21))


if __name__ == "__main__":
    unittest.main()
