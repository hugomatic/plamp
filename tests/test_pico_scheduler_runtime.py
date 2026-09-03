import io
import json
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from pico_scheduler.src.generator import GeneratorOptions, generate_main_py
from plamp.scheduler_state import report_matches_state


def gpio(pin=2, value=1, current_t=0, *, mode="scheduled"):
    return {
        "id": "lights",
        "type": "gpio",
        "pin": pin,
        "mode": mode,
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
            {"name": "pico_scheduler", "revision": "abc1234", "protocol": 4},
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

    def test_configure_rejects_pwm_before_persistence_or_output_changes(self):
        firmware = self.harness()
        firmware.call("handle_message", {"type": "configure", "content": {"devices": [gpio()]}})
        active_path = firmware.runtime.active_state_path
        active_text = Path(active_path).read_text()
        pwm = {
            "id": "fan",
            "type": "pwm",
            "pin": 3,
            "mode": "scheduled",
            "current_t": 0,
            "reschedule": 1,
            "pattern": [{"val": 1234, "dur": 10}],
        }

        firmware.call(
            "handle_message", {"type": "configure", "content": {"devices": [pwm]}}
        )

        self.assertEqual(firmware.runtime.active_generation, 1)
        self.assertEqual(firmware.runtime.active_state_path, active_path)
        self.assertEqual(Path(active_path).read_text(), active_text)
        self.assertEqual([(device["type"], device["pin"]) for device in firmware.runtime.devices], [("gpio", 2)])
        self.assertEqual(firmware.messages()[-1]["type"], "error")
        self.assertIn("unsupported type: pwm", firmware.messages()[-1]["content"]["message"])

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

    def test_boot_from_disabled_state_keeps_gpio_off(self):
        root = Path(self.temp.name)
        (root / "state-a.json").write_text(json.dumps({
            "generation": 1,
            "devices": [gpio(value=1, current_t=7, mode="ready")],
        }))

        firmware = self.harness()

        self.assertEqual(firmware.runtime.devices[0]["elapsed_t"], 7)
        self.assertEqual(firmware.pins[2].value(), 0)

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

    def test_configure_retires_removed_gpio(self):
        firmware = self.harness()
        firmware.call("handle_message", {"type": "configure", "content": {"devices": [gpio(value=1)]}})
        removed = firmware.pins[2]

        firmware.call("handle_message", {"type": "configure", "content": {"devices": []}})

        self.assertEqual(removed.value(), 0)

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

    def test_timed_off_override_forces_on_pin_off(self):
        firmware = self.harness()
        firmware.call("handle_message", {"type": "configure", "content": {"devices": [gpio(value=1)]}})

        firmware.call("handle_command", "p 2 0 5")

        self.assertEqual(len(firmware.runtime.devices), 2)
        self.assertEqual(firmware.pins[2].value(), 0)
        self.assertEqual(firmware.messages()[-1]["content"]["overlays"][0]["current_value"], 0)

    def test_disabled_gpio_is_off_and_phase_does_not_advance(self):
        firmware = self.harness()
        firmware.call("handle_message", {
            "type": "configure",
            "content": {"devices": [gpio(value=1, current_t=4, mode="ready")]},
        })

        self.assertEqual(firmware.pins[2].value(), 0)
        firmware.call("tick", 5)
        firmware.call("apply")

        self.assertEqual(firmware.runtime.devices[0]["elapsed_t"], 4)
        self.assertEqual(firmware.pins[2].value(), 0)
        reported = firmware.messages()[-1]["content"]["devices"][0]
        self.assertEqual(reported["mode"], "ready")
        self.assertEqual(reported["current_value"], 0)

    def test_disabled_schedule_allows_timed_on_override(self):
        firmware = self.harness()
        firmware.call("handle_message", {
            "type": "configure", "content": {"devices": [gpio(value=0, mode="ready")]},
        })

        firmware.call("handle_command", "p 2 1 5")

        self.assertEqual(firmware.pins[2].value(), 1)
        firmware.call("tick", 5)
        firmware.call("apply")
        self.assertEqual(firmware.pins[2].value(), 0)

    def test_disabling_schedule_preserves_active_override_then_returns_off(self):
        firmware = self.harness()
        firmware.call("handle_message", {
            "type": "configure", "content": {"devices": [gpio(value=0)]},
        })
        firmware.call("handle_command", "p 2 5")

        firmware.call("handle_message", {
            "type": "configure",
            "content": {"devices": [gpio(value=1, current_t=3, mode="ready")]},
        })

        self.assertEqual(len(firmware.runtime.devices), 2)
        self.assertEqual(firmware.pins[2].value(), 1)
        firmware.call("tick", 5)
        firmware.call("apply")
        self.assertEqual(len(firmware.runtime.devices), 1)
        self.assertEqual(firmware.pins[2].value(), 0)

    def test_new_override_replaces_existing_override_on_same_pin(self):
        firmware = self.harness()
        firmware.call("handle_message", {"type": "configure", "content": {"devices": [gpio(value=0)]}})
        firmware.call("handle_command", "p 2 1 30")

        firmware.call("handle_command", "p 2 0 10")

        overlays = [device for device in firmware.runtime.devices if device.get("overlay")]
        self.assertEqual(len(overlays), 1)
        self.assertEqual(overlays[0]["pattern"], [{"val": 0, "dur": 10}])
        self.assertEqual(firmware.pins[2].value(), 0)

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

    def test_pulsed_gpio_rejects_pwm_before_persistence(self):
        firmware = self.harness()
        firmware.call("handle_message", {"type": "configure", "content": {"devices": [gpio(value=0)]}})
        firmware.call("handle_command", "p 2 5")
        active_path = firmware.runtime.active_state_path
        active_text = Path(active_path).read_text()
        inactive_path = firmware.paths[1]
        proposal = {
            "devices": [{"id": "fan", "type": "pwm", "pin": 2, "current_t": 0,
                         "mode": "scheduled", "reschedule": 1, "pattern": [{"val": 1234, "dur": 10}]}]
        }

        firmware.call("handle_message", {"type": "configure", "content": proposal})

        self.assertEqual(firmware.runtime.active_generation, 1)
        self.assertEqual(firmware.runtime.active_state_path, active_path)
        self.assertEqual(Path(active_path).read_text(), active_text)
        self.assertFalse(inactive_path.exists())
        self.assertEqual(len(firmware.runtime.devices), 2)
        self.assertEqual(firmware.messages()[-1]["type"], "error")
        self.assertEqual(firmware.messages()[-1]["content"]["command"], "configure")

    def test_configure_report_separates_overlay_and_verifies_base_state(self):
        firmware = self.harness()
        firmware.call("handle_message", {"type": "configure", "content": {"devices": [gpio(value=0)]}})
        firmware.call("handle_command", "p 2 2")
        proposal = {
            "devices": [{"id": "lights", "type": "gpio", "pin": 2, "current_t": 0,
                         "mode": "scheduled", "reschedule": 1,
                         "pattern": [{"val": 0, "dur": 2}, {"val": 1, "dur": 8}]}]
        }

        firmware.call("handle_message", {"type": "configure", "content": proposal})

        report = firmware.messages()[-1]
        self.assertEqual(report["type"], "report")
        self.assertEqual(len(report["content"]["devices"]), 1)
        self.assertEqual(report["content"]["devices"][0]["current_value"], 1)
        self.assertEqual(len(report["content"]["overlays"]), 1)
        self.assertEqual(report["content"]["overlays"][0]["current_value"], 1)
        self.assertTrue(report_matches_state(report, proposal))
        firmware.call("tick", 2)
        self.assertEqual(len(firmware.runtime.devices), 1)
        self.assertEqual(firmware.pins[2].value(), 1)

    def test_removing_base_cancels_active_pulse_and_turns_physical_pin_off(self):
        firmware = self.harness()
        firmware.call("handle_message", {"type": "configure", "content": {"devices": [gpio(value=0)]}})
        firmware.call("handle_command", "p 2 2")
        pulsed_pin = firmware.pins[2]

        firmware.call("handle_message", {"type": "configure", "content": {"devices": []}})

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
