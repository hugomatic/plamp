import unittest

from pico_scheduler.generator import GeneratorOptions, generate_main_py


class PicoGeneratorTests(unittest.TestCase):
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
