import inspect
import unittest

from pico_scheduler.src.generator import GeneratorOptions, generate_main_py


class PicoSchedulerGeneratorTests(unittest.TestCase):
    def test_generated_firmware_has_generic_runtime_contract(self) -> None:
        text = generate_main_py(
            firmware_revision="abc1234", options=GeneratorOptions()
        )

        self.assertIn('FIRMWARE_REVISION = "abc1234"', text)
        self.assertIn("FIRMWARE_PROTOCOL = 2", text)
        self.assertIn(
            'STATE_PATHS = ("/plamp_state_a.json", "/plamp_state_b.json")',
            text,
        )
        self.assertIn('message["type"] == "configure"', text)
        self.assertNotIn("Pin(15, Pin.OUT)", text)
        self.assertNotIn("Generator input:", text)

    def test_output_is_independent_of_host_schedule_context(self) -> None:
        first_host_context = {
            "controller_id": "pump_n_lights",
            "generated_at": "2026-07-16T01:00:00-10:00",
            "state": {"devices": [{"type": "gpio", "pin": 15}]},
        }
        second_host_context = {
            "controller_id": "other",
            "generated_at": "later",
            "state": {"devices": []},
        }

        first = generate_main_py(
            firmware_revision="abc1234", options=GeneratorOptions()
        )
        second = generate_main_py(
            firmware_revision="abc1234", options=GeneratorOptions()
        )

        self.assertNotEqual(first_host_context, second_host_context)
        self.assertEqual(first, second)
        self.assertEqual(
            set(inspect.signature(generate_main_py).parameters),
            {"firmware_revision", "options"},
        )

    def test_options_are_rendered_into_generic_runtime(self) -> None:
        text = generate_main_py(
            firmware_revision="rev", options=GeneratorOptions(loop_sleep_ms=25, pwm_freq=700)
        )

        self.assertIn("LOOP_SLEEP_MS = 25", text)
        self.assertIn("PWM_FREQ = 700", text)


if __name__ == "__main__":
    unittest.main()
