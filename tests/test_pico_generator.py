import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from tests.test_pico_scheduler_runtime import FirmwareHarness


class PicoGeneratorTests(unittest.TestCase):
    def firmware_runtime(self, *, current_t: int, pattern: list[dict[str, int]]) -> FirmwareHarness:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        firmware = FirmwareHarness(Path(temp.name))
        firmware.call(
            "handle_message",
            {
                "type": "configure",
                "content": {
                    "devices": [
                        {
                            "id": "lights",
                            "type": "gpio",
                            "pin": 21,
                            "current_t": current_t,
                            "reschedule": 1,
                            "pattern": pattern,
                        }
                    ]
                },
            },
        )
        firmware.output.seek(0)
        firmware.output.truncate()
        return firmware

    def test_generated_scheduler_rejects_pulse_when_physical_pin_is_on(self):
        firmware = self.firmware_runtime(
            current_t=6,
            pattern=[{"val": 0, "dur": 5}, {"val": 1, "dur": 10}],
        )

        firmware.call("handle_command", "p 21 5")

        self.assertEqual(len(firmware.runtime.devices), 1)
        self.assertIn("pulse pin is already on", firmware.output.getvalue())

    def test_pulse_expiry_uses_schedule_state_after_transition(self):
        firmware = self.firmware_runtime(
            current_t=4,
            pattern=[{"val": 0, "dur": 5}, {"val": 1, "dur": 10}],
        )
        scheduled = firmware.runtime.devices[0]

        with redirect_stdout(io.StringIO()):
            firmware.runtime.pulse_device(scheduled, 2)
            firmware.runtime.tick(2)

        self.assertEqual(firmware.runtime.devices, [scheduled])
        self.assertEqual(scheduled["elapsed_t"], 6)
        self.assertEqual(scheduled["output"].value(), 1)

    def test_schedule_ticks_are_silent_but_report_command_answers(self):
        firmware = self.firmware_runtime(
            current_t=4,
            pattern=[{"val": 0, "dur": 5}, {"val": 1, "dur": 10}],
        )

        firmware.call("tick", 2)
        firmware.call("apply")
        self.assertEqual(firmware.output.getvalue(), "")

        firmware.call("handle_command", "r")
        self.assertIn('"type": "report"', firmware.output.getvalue())

    def test_generated_scheduler_includes_nonblocking_serial_commands(self):
        firmware = self.firmware_runtime(
            current_t=0,
            pattern=[{"val": 1, "dur": 10}, {"val": 0, "dur": 20}],
        )
        source = firmware.runtime.handle_command.__globals__

        self.assertIn("poller", source)
        self.assertIn("handle_command", source)
        self.assertIn("read_commands", source)
        self.assertEqual(source["MAX_COMMAND_BYTES"], 16384)
        self.assertIn("pulse_device", source)
        self.assertIn("tick", source)


if __name__ == "__main__":
    unittest.main()
