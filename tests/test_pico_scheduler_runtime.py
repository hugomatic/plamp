import io
import json
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from pico_scheduler.generator import GeneratorOptions, generate_main_py


def gpio(pin=2, value=1, current_t=0):
    return {
        "id": "lights",
        "type": "gpio",
        "pin": pin,
        "current_t": current_t,
        "reschedule": 1,
        "pattern": [{"val": value, "dur": 10}],
    }


class FirmwareHarness:
    def __init__(self, root: Path):
        self.paths = (root / "state-a.json", root / "state-b.json")
        self.output = io.StringIO()
        self.input = io.StringIO()
        self.pins = {}
        self.pwms = {}
        harness = self

        class FakePin:
            OUT = 1

            def __init__(self, pin, mode=None):
                self.pin = pin
                self.mode = mode
                self.state = 0
                harness.pins[pin] = self

            def value(self, state=None):
                if state is not None:
                    self.state = state
                return self.state

        class FakePWM:
            def __init__(self, pin):
                self.pin = pin.pin
                self.frequency = None
                self.duty = 0
                self.deinitialized = False
                harness.pwms[self.pin] = self

            def freq(self, frequency):
                self.frequency = frequency

            def duty_u16(self, duty):
                self.duty = duty

            def deinit(self):
                self.deinitialized = True

        class FakePoll:
            def register(self, stream, event):
                self.stream = stream

            def poll(self, timeout):
                position = self.stream.tell()
                char = self.stream.read(1)
                self.stream.seek(position)
                return [1] if char else []

        machine = types.ModuleType("machine")
        machine.Pin = FakePin
        machine.PWM = FakePWM
        select = types.ModuleType("select")
        select.POLLIN = 1
        select.poll = FakePoll
        source = generate_main_py(
            firmware_revision="abc1234", options=GeneratorOptions()
        )
        source = source.replace(
            'STATE_PATHS = ("/plamp_state_a.json", "/plamp_state_b.json")',
            "STATE_PATHS = (%s, %s)" % (repr(str(self.paths[0])), repr(str(self.paths[1]))),
        )
        runtime = {"__name__": "pico_test"}
        with patch.dict(
            sys.modules,
            {"machine": machine, "select": select, "ujson": json},
        ), patch("sys.stdin", self.input), redirect_stdout(self.output):
            exec(source, runtime)
        class Runtime:
            def __getattr__(self, name):
                return runtime[name]

            def __setattr__(self, name, value):
                runtime[name] = value

        self.runtime = Runtime()

    def call(self, name, *args):
        with redirect_stdout(self.output):
            return getattr(self.runtime, name)(*args)

    def messages(self):
        return [json.loads(line) for line in self.output.getvalue().splitlines()]


class PicoSchedulerRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def harness(self):
        return FirmwareHarness(Path(self.temp.name))

    def test_configure_persists_applies_and_reports(self):
        firmware = self.harness()
        state = {"devices": [gpio()]}

        firmware.call("handle_message", {"type": "configure", "content": state})

        stored = json.loads(firmware.paths[0].read_text())
        self.assertEqual(stored, {"generation": 1, "devices": state["devices"]})
        self.assertEqual(firmware.pins[2].value(), 1)
        self.assertEqual(firmware.messages()[-1]["type"], "report")
        self.assertEqual(
            firmware.messages()[-1]["content"]["firmware"],
            {"name": "pico_scheduler", "revision": "abc1234", "protocol": 2},
        )

    def test_invalid_duplicate_pin_does_not_change_persistence_or_outputs(self):
        firmware = self.harness()
        firmware.call("handle_message", {"type": "configure", "content": {"devices": [gpio()]}})
        before = firmware.paths[0].read_text()
        duplicate = {"devices": [gpio(2), {**gpio(2), "id": "pump"}]}

        firmware.call("handle_message", {"type": "configure", "content": duplicate})

        self.assertEqual(firmware.paths[0].read_text(), before)
        self.assertEqual(firmware.messages()[-1]["type"], "error")
        self.assertIn("duplicate pin", firmware.messages()[-1]["content"]["message"])

    def test_configure_order_is_persist_build_replace_apply_report(self):
        firmware = self.harness()
        calls = []
        for name in ("persist_state", "build_outputs", "replace_devices", "apply", "report"):
            original = getattr(firmware.runtime, name)

            def wrapper(*args, _name=name, _original=original, **kwargs):
                calls.append(_name.removesuffix("_state").removesuffix("_outputs").removesuffix("_devices"))
                return _original(*args, **kwargs)

            setattr(firmware.runtime, name, wrapper)

        firmware.call("handle_message", {"type": "configure", "content": {"devices": [gpio()]}})

        self.assertEqual(calls, ["persist", "build", "replace", "apply", "report"])

    def test_boot_chooses_highest_valid_generation_and_restores_phase(self):
        root = Path(self.temp.name)
        (root / "state-a.json").write_text(json.dumps({"generation": 2, "devices": [gpio(value=0)]}))
        (root / "state-b.json").write_text(json.dumps({"generation": 4, "devices": [gpio(value=1, current_t=7)]}))

        firmware = self.harness()

        self.assertEqual(firmware.runtime.active_generation, 4)
        self.assertEqual(firmware.runtime.devices[0]["elapsed_t"], 7)
        self.assertEqual(firmware.pins[2].value(), 1)
        self.assertEqual(firmware.output.getvalue(), "")

    def test_boot_ignores_torn_newer_slot(self):
        root = Path(self.temp.name)
        (root / "state-a.json").write_text(json.dumps({"generation": 2, "devices": [gpio(value=1)]}))
        (root / "state-b.json").write_text('{"generation": 3, "devices":')

        firmware = self.harness()

        self.assertEqual(firmware.runtime.active_generation, 2)
        self.assertEqual(firmware.pins[2].value(), 1)

    def test_boot_without_state_uses_generation_zero_and_no_devices(self):
        firmware = self.harness()

        self.assertEqual(firmware.runtime.active_generation, 0)
        self.assertEqual(firmware.runtime.devices, [])
        self.assertIsNone(firmware.runtime.active_state_path)

    def test_configure_replaces_gpio_with_pwm(self):
        firmware = self.harness()
        firmware.call("handle_message", {"type": "configure", "content": {"devices": [gpio()]}})
        pwm = {
            "id": "fan", "type": "pwm", "pin": 3, "current_t": 0,
            "reschedule": 1, "pattern": [{"val": 1234, "dur": 10}],
        }

        firmware.call("handle_message", {"type": "configure", "content": {"devices": [pwm]}})

        self.assertEqual([(d["type"], d["pin"]) for d in firmware.runtime.devices], [("pwm", 3)])
        self.assertEqual(firmware.pwms[3].frequency, 1000)
        self.assertEqual(firmware.pwms[3].duty, 1234)
        self.assertTrue(firmware.paths[1].exists())

    def test_configure_retires_removed_gpio(self):
        firmware = self.harness()
        firmware.call("handle_message", {"type": "configure", "content": {"devices": [gpio(value=1)]}})
        removed = firmware.pins[2]

        firmware.call("handle_message", {"type": "configure", "content": {"devices": []}})

        self.assertEqual(removed.value(), 0)

    def test_configure_retires_removed_pwm(self):
        firmware = self.harness()
        pwm = {
            "id": "fan", "type": "pwm", "pin": 3, "current_t": 0,
            "reschedule": 1, "pattern": [{"val": 1234, "dur": 10}],
        }
        firmware.call("handle_message", {"type": "configure", "content": {"devices": [pwm]}})
        removed = firmware.pwms[3]

        firmware.call("handle_message", {"type": "configure", "content": {"devices": []}})

        self.assertEqual(removed.duty, 0)
        self.assertTrue(removed.deinitialized)

    def test_command_buffer_overflow_emits_one_error_and_clears_buffer(self):
        firmware = self.harness()
        oversized = "x" * (firmware.runtime.MAX_COMMAND_BYTES + 50)
        firmware.input.write(oversized)
        firmware.input.seek(0)

        firmware.call("read_commands")

        self.assertEqual(firmware.runtime.command_buffer, "")
        errors = [m for m in firmware.messages() if m["type"] == "error"]
        self.assertEqual(len(errors), 1)
        self.assertIn("command too long", errors[0]["content"])

    def test_pulse_rejected_while_pin_is_on(self):
        firmware = self.harness()
        firmware.call("handle_message", {"type": "configure", "content": {"devices": [gpio(value=1)]}})

        firmware.call("handle_command", "p 2 5")

        self.assertEqual(len(firmware.runtime.devices), 1)
        self.assertIn("already on", firmware.messages()[-1]["content"])

    def test_pulse_completion_restores_configured_base_device(self):
        firmware = self.harness()
        firmware.call("handle_message", {"type": "configure", "content": {"devices": [gpio(value=0)]}})

        firmware.call("handle_command", "p 2 2")
        self.assertEqual(firmware.pins[2].value(), 1)
        firmware.call("tick", 2)
        firmware.call("apply")

        self.assertEqual(len(firmware.runtime.devices), 1)
        self.assertEqual(firmware.runtime.devices[0]["id"], "lights")
        self.assertEqual(firmware.pins[2].value(), 0)

    def test_configure_during_pulse_preserves_overlay_then_restores_new_base(self):
        firmware = self.harness()
        firmware.call("handle_message", {"type": "configure", "content": {"devices": [gpio(value=0)]}})
        firmware.call("handle_command", "p 2 2")
        newer = gpio(value=1)
        newer["id"] = "new-lights"

        firmware.call("handle_message", {"type": "configure", "content": {"devices": [newer]}})

        self.assertEqual(len(firmware.runtime.devices), 2)
        self.assertEqual(firmware.pins[2].value(), 1)
        firmware.call("tick", 2)
        self.assertEqual(len(firmware.runtime.devices), 1)
        self.assertEqual(firmware.runtime.devices[0]["id"], "new-lights")
        self.assertEqual(firmware.pins[2].value(), 1)

    def test_removed_base_pulse_expiry_turns_physical_pin_off(self):
        firmware = self.harness()
        firmware.call("handle_message", {"type": "configure", "content": {"devices": [gpio(value=0)]}})
        firmware.call("handle_command", "p 2 2")
        pulsed_pin = firmware.pins[2]

        firmware.call("handle_message", {"type": "configure", "content": {"devices": []}})

        self.assertEqual(len(firmware.runtime.devices), 1)
        self.assertEqual(pulsed_pin.value(), 1)
        firmware.call("tick", 2)
        self.assertEqual(firmware.runtime.devices, [])
        self.assertEqual(pulsed_pin.value(), 0)

    def test_non_rescheduling_configured_gpio_can_be_pulsed(self):
        firmware = self.harness()
        base = gpio(value=0)
        base["reschedule"] = 0
        firmware.call("handle_message", {"type": "configure", "content": {"devices": [base]}})

        firmware.call("handle_command", "p 2 2")

        self.assertEqual(len(firmware.runtime.devices), 2)
        self.assertEqual(firmware.pins[2].value(), 1)

    def test_json_configure_command_is_parsed(self):
        firmware = self.harness()

        firmware.call("handle_command", json.dumps({"type": "configure", "content": {"devices": [gpio()]}}))

        self.assertEqual(firmware.runtime.active_generation, 1)
        self.assertEqual(firmware.messages()[-1]["type"], "report")


if __name__ == "__main__":
    unittest.main()
