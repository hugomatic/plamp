import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
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


class PulseHistoryTests(unittest.TestCase):
    def test_parse_dressed_and_legacy_pulse_log_lines(self):
        now = datetime(2026, 9, 2, 12, 0, 0)
        lines = [
            "2026-09-02 11:59:00,000 INFO plamp_web pico pulse role=plamp8 channel=Agitator pin=19 ON for 20s",
            "2026-09-02 11:50:00,000 INFO plamp_web pico-cmd tx role=plamp8 cmd='p 18 0 5'",
            "2026-09-02 11:40:00,000 INFO plamp_web pico-cmd tx role=other cmd='p 19 1 10'",
            "2026-09-02 10:00:00,000 INFO plamp_web pico pulse role=plamp8 channel=Agitator pin=19 ON for 10s",
        ]
        events = server.parse_pulse_history_lines(lines, role="plamp8", since=now - timedelta(hours=1))
        self.assertEqual(
            events,
            [
                {"started_at": "2026-09-02T11:59:00", "pin": 19, "value": 1, "seconds": 20},
                {"started_at": "2026-09-02T11:50:00", "pin": 18, "value": 0, "seconds": 5},
            ],
        )

    def test_pulse_history_reads_rotated_logs_and_maps_channel_ids(self):
        now = datetime(2026, 9, 2, 12, 0, 0)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log = root / "plamp.log"
            rotated = root / "plamp.log.1"
            log.write_text(
                "2026-09-02 11:58:00,000 INFO plamp_web pico pulse role=plamp8 channel=Agitator pin=19 ON for 30s\n",
                encoding="utf-8",
            )
            rotated.write_text(
                "2026-09-02 11:00:00,000 INFO plamp_web pico-cmd tx role=plamp8 cmd='p 19 1 15'\n",
                encoding="utf-8",
            )
            config = {
                "controllers": {
                    "plamp8": {
                        "type": "pico_scheduler",
                        "config": {"pico_serial": "abc"},
                        "settings": {
                            "devices": {
                                "agitator": {
                                    "pin": 19,
                                    "output_type": "gpio",
                                    "programming": "ready",
                                    "editor": {
                                        "kind": "cycle",
                                        "on_seconds": 1,
                                        "off_seconds": 1,
                                        "start_at_seconds": 0,
                                    },
                                },
                            }
                        },
                    }
                },
                "cameras": {},
            }
            with (
                patch.object(server, "LOG_FILE", log),
                patch.object(server, "load_config", return_value=server.config_view(config)),
            ):
                payload = server.controller_pulse_history(
                    "plamp8", horizon_seconds=3600, now=now
                )
        self.assertEqual(
            payload["pulses"],
            [
                {
                    "channel_id": "agitator",
                    "pin": 19,
                    "value": 1,
                    "seconds": 30,
                    "started_at": "2026-09-02T11:58:00",
                    "ended_at": "2026-09-02T11:58:30",
                },
                {
                    "channel_id": "agitator",
                    "pin": 19,
                    "value": 1,
                    "seconds": 15,
                    "started_at": "2026-09-02T11:00:00",
                    "ended_at": "2026-09-02T11:00:15",
                },
            ],
        )


if __name__ == "__main__":
    unittest.main()
