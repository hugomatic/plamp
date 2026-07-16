import io
import json
import sys
import types
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from pico_scheduler.generator import GeneratorOptions, generate_main_py


class PicoGeneratorTests(unittest.TestCase):
    def firmware_runtime(self, *, current_t: int, pattern: list[dict[str, int]]) -> dict:
        source = generate_main_py(
            controller_id="pump_lights",
            state={
                "report_every": 10,
                "devices": [{"id": "lights", "type": "gpio", "pin": 21, "current_t": current_t, "reschedule": 1, "pattern": pattern}],
            },
            git_version="test",
            generated_at="2026-07-15T00:00:00",
            options=GeneratorOptions(),
        )

        class FakePin:
            OUT = 1

            def __init__(self, pin: int, mode: int):
                self.pin = pin
                self.state = 0

            def value(self, state=None):
                if state is not None:
                    self.state = state
                return self.state

        class FakePoll:
            def register(self, stream, event):
                pass

            def poll(self, timeout):
                return []

        machine = types.ModuleType("machine")
        machine.Pin = FakePin
        select = types.ModuleType("select")
        select.POLLIN = 1
        select.poll = FakePoll
        runtime = {"__name__": "firmware_test"}
        with patch.dict(sys.modules, {"machine": machine, "select": select, "ujson": json}):
            exec(source, runtime)
        return runtime

    def test_generated_scheduler_rejects_pulse_when_physical_pin_is_on(self):
        runtime = self.firmware_runtime(current_t=6, pattern=[{"val": 0, "dur": 5}, {"val": 1, "dur": 10}])
        runtime["apply"]()

        output = io.StringIO()
        with redirect_stdout(output):
            runtime["handle_command"]("p 21 5")

        self.assertEqual(len(runtime["devices"]), 1)
        self.assertIn("pulse pin is already on", output.getvalue())

    def test_pulse_expiry_uses_schedule_state_after_transition(self):
        runtime = self.firmware_runtime(current_t=4, pattern=[{"val": 0, "dur": 5}, {"val": 1, "dur": 10}])
        scheduled = runtime["devices"][0]
        runtime["apply"]()

        with redirect_stdout(io.StringIO()):
            runtime["pulse_device"](scheduled, 2)
            runtime["tick"](2)

        self.assertEqual(runtime["devices"], [scheduled])
        self.assertEqual(scheduled["elapsed_t"], 6)
        self.assertEqual(scheduled["output"].value(), 1)

    def test_schedule_ticks_are_silent_but_report_command_answers(self):
        runtime = self.firmware_runtime(current_t=4, pattern=[{"val": 0, "dur": 5}, {"val": 1, "dur": 10}])
        runtime["apply"]()

        output = io.StringIO()
        with redirect_stdout(output):
            runtime["tick"](2)
            runtime["apply"]()
        self.assertEqual(output.getvalue(), "")

        with redirect_stdout(output):
            runtime["handle_command"]("r")
        self.assertIn('"type": "report"', output.getvalue())

    def test_generated_scheduler_includes_nonblocking_serial_commands(self):
        source = generate_main_py(
            controller_id="pump_lights",
            state={
                "report_every": 10,
                "devices": [
                    {
                        "id": "pump",
                        "type": "gpio",
                        "pin": 21,
                        "current_t": 0,
                        "reschedule": 1,
                        "pattern": [{"val": 1, "dur": 10}, {"val": 0, "dur": 20}],
                    }
                ],
            },
            git_version="test",
            generated_at="2026-07-06T00:00:00",
            options=GeneratorOptions(),
        )

        self.assertIn("import select", source)
        self.assertIn("poller = select.poll()", source)
        self.assertIn("def handle_command(line):", source)
        self.assertIn('if line == "r":', source)
        self.assertIn('if parts[0] == "p" and len(parts) == 3:', source)
        self.assertIn("devices.append(pulse)", source)
        self.assertIn('"reschedule": 0', source)
        self.assertIn('if not device["reschedule"] and device["elapsed_t"] >= device["total_t"]:', source)
        self.assertIn("devices.remove(device)", source)
        self.assertNotIn("pulse_until_ms", source)
        self.assertIn("read_commands()", source)


if __name__ == "__main__":
    unittest.main()
