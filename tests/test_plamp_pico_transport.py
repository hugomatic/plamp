import json
import math
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import plamp
from plamp import LockTimeout as ExportedLockTimeout
from plamp.locks import LockTimeout
from plamp.pico_transport import PicoClient, PicoCommandError, PicoExchange, PicoFlashError, PicoOperation, PicoReportTimeout, PicoUnavailable, _lock_name, pulse_gpio, request_report


class FakeSerial:
    def __init__(self, lines):
        self.lines = list(lines)
        self.writes = []
        self.flushed = False
        self.input_reset = False
        self.closed = False
        self.read_timeouts = []
        self.readline_calls = 0
        self.write_timeouts_at_write = []
        self._timeout = None
        self.write_timeout = None

    @property
    def timeout(self):
        return self._timeout

    @timeout.setter
    def timeout(self, value):
        self._timeout = value
        self.read_timeouts.append(value)

    def reset_input_buffer(self):
        self.input_reset = True

    def write(self, value):
        self.write_timeouts_at_write.append(self.write_timeout)
        self.writes.append(value)

    def flush(self):
        self.flushed = True

    def readline(self):
        self.readline_calls += 1
        return self.lines.pop(0) if self.lines else b""

    def close(self):
        self.closed = True


class PicoTransportTests(unittest.TestCase):
    CONFIGURED_STATE = {"devices": [{
        "id": "lights", "type": "gpio", "pin": 2, "current_t": 0,
        "reschedule": 1, "pattern": [{"val": 1, "dur": 10}],
    }]}
    MATCHING_REPORT = b'{"type":"report","content":{"devices":[{"id":"lights","type":"gpio","pin":2,"elapsed_t":0,"cycle_t":0,"current_value":1,"reschedule":1,"pattern":[{"val":1,"dur":10}]}]}}\n'

    def test_package_exports_lock_timeout(self):
        self.assertIs(ExportedLockTimeout, LockTimeout)

    def test_package_exports_transport_operation_types(self):
        self.assertIs(plamp.PicoExchange, PicoExchange)
        self.assertIs(plamp.PicoOperation, PicoOperation)

    def test_configure_writes_one_json_document(self):
        conn = FakeSerial([self.MATCHING_REPORT])
        with tempfile.TemporaryDirectory() as tmp:
            result = PicoClient(
                "PICO-A", lock_dir=Path(tmp),
                serial_factory=lambda *args, **kwargs: conn,
                port_finder=lambda serial: "/dev/ttyACM0",
            ).configure(self.CONFIGURED_STATE, timeout=0.2)

        self.assertEqual(
            json.loads(conn.writes[0].strip()),
            {"type": "configure", "content": self.CONFIGURED_STATE},
        )
        self.assertEqual(result.message["type"], "report")

    def test_configure_recovers_lost_reply_with_report(self):
        first = FakeSerial([b"first attempt noise\n"])
        second = FakeSerial([self.MATCHING_REPORT])
        connections = iter([first, second])
        with tempfile.TemporaryDirectory() as tmp:
            result = PicoClient(
                "PICO-A", lock_dir=Path(tmp),
                serial_factory=lambda *args, **kwargs: next(connections),
                port_finder=lambda serial: "/dev/ttyACM0",
            ).configure(self.CONFIGURED_STATE, timeout=0.04)

        self.assertEqual(len(first.writes), 1)
        self.assertEqual(json.loads(first.writes[0].strip())["type"], "configure")
        self.assertEqual(second.writes, [b"\nr\n"])
        self.assertEqual(
            result.raw_lines, (b"first attempt noise\n", self.MATCHING_REPORT)
        )

    def test_configure_rejects_mismatched_recovery_report(self):
        first = FakeSerial([b"first attempt noise\n"])
        mismatch = b'{"type":"report","content":{"devices":[]}}\n'
        second = FakeSerial([mismatch])
        connections = iter([first, second])
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(PicoCommandError, "does not match") as caught:
                PicoClient(
                    "PICO-A", lock_dir=Path(tmp),
                    serial_factory=lambda *args, **kwargs: next(connections),
                    port_finder=lambda serial: "/dev/ttyACM0",
                ).configure(self.CONFIGURED_STATE, timeout=0.04)

        self.assertEqual(len(first.writes), 1)
        self.assertEqual(second.writes, [b"\nr\n"])
        self.assertEqual(
            caught.exception.raw_lines, (b"first attempt noise\n", mismatch)
        )

    def test_configure_raises_concise_structured_error_with_raw_evidence(self):
        raw = b'{"type":"error","content":"invalid scheduler state"}\n'
        conn = FakeSerial([raw])
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(PicoCommandError, "invalid scheduler state") as caught:
                PicoClient(
                    "PICO-A", lock_dir=Path(tmp),
                    serial_factory=lambda *args, **kwargs: conn,
                    port_finder=lambda serial: "/dev/ttyACM0",
                ).configure(self.CONFIGURED_STATE, timeout=0.2)

        self.assertEqual(str(caught.exception), "invalid scheduler state")
        self.assertEqual(caught.exception.raw_lines, (raw,))

    def test_configure_recovery_returns_structured_error_with_all_evidence(self):
        first_raw = b"first attempt noise\n"
        proof_noise = b"proof attempt noise\n"
        error_raw = b'{"type":"error","content":"configure rejected"}\n'
        first = FakeSerial([first_raw])
        second = FakeSerial([proof_noise, error_raw])
        connections = iter([first, second])
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(PicoCommandError, "configure rejected") as caught:
                PicoClient(
                    "PICO-A", lock_dir=Path(tmp),
                    serial_factory=lambda *args, **kwargs: next(connections),
                    port_finder=lambda serial: "/dev/ttyACM0",
                ).configure(self.CONFIGURED_STATE, timeout=0.04)

        self.assertEqual(str(caught.exception), "configure rejected")
        self.assertEqual(
            caught.exception.raw_lines, (first_raw, proof_noise, error_raw)
        )
        self.assertEqual(len(first.writes), 1)
        self.assertEqual(json.loads(first.writes[0].strip())["type"], "configure")
        self.assertEqual(second.writes, [b"\nr\n"])

    def test_configure_recovery_timeout_retains_both_attempts_evidence(self):
        first_raw = b"first attempt noise\n"
        proof_raw = b"proof attempt noise\n"
        first = FakeSerial([first_raw])
        second = FakeSerial([proof_raw])
        connections = iter([first, second])
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(PicoReportTimeout) as caught:
                PicoClient(
                    "PICO-A", lock_dir=Path(tmp),
                    serial_factory=lambda *args, **kwargs: next(connections),
                    port_finder=lambda serial: "/dev/ttyACM0",
                ).configure(self.CONFIGURED_STATE, timeout=0.04)

        self.assertEqual(caught.exception.raw_lines, (first_raw, proof_raw))
        self.assertEqual(len(first.writes), 1)
        self.assertEqual(json.loads(first.writes[0].strip())["type"], "configure")
        self.assertEqual(second.writes, [b"\nr\n"])

    def test_rejects_invalid_timeouts_before_side_effects(self):
        discovery_calls = []
        with tempfile.TemporaryDirectory() as tmp:
            for timeout in (-0.01, math.nan, math.inf, -math.inf):
                with self.subTest(timeout=timeout):
                    with self.assertRaisesRegex(ValueError, "timeout"):
                        request_report(
                            "PICO-A", lock_dir=Path(tmp), timeout=timeout,
                            port_finder=lambda serial: discovery_calls.append(serial),
                        )
        self.assertEqual(discovery_calls, [])

    def test_colliding_sanitized_serials_have_distinct_lock_names(self):
        first = _lock_name("PICO/A")
        second = _lock_name("PICO?A")
        self.assertNotEqual(first, second)
        self.assertTrue(first.startswith("pico-PICO_A-"))
        self.assertTrue(first.endswith(".lock"))

    def test_serial_write_timeout_uses_remaining_deadline(self):
        conn = FakeSerial([b'{"type":"report","content":{"devices":[]}}\n'])
        calls = []

        def serial_factory(*args, **kwargs):
            calls.append((args, kwargs))
            return conn

        with tempfile.TemporaryDirectory() as tmp:
            request_report(
                "PICO-A", lock_dir=Path(tmp), timeout=0.1,
                port_finder=lambda serial: "/dev/ttyACM0", serial_factory=serial_factory,
            )
        self.assertGreater(calls[0][1]["write_timeout"], 0)
        self.assertLessEqual(calls[0][1]["write_timeout"], 0.1)

    def test_write_timeout_is_refreshed_after_serial_open(self):
        conn = FakeSerial([b'{"type":"report","content":{"devices":[]}}\n'])
        clock = [10.0]

        def serial_factory(*args, **kwargs):
            conn.write_timeout = kwargs["write_timeout"]
            clock[0] += 0.04
            return conn

        with tempfile.TemporaryDirectory() as tmp:
            with patch("plamp.pico_transport.time.monotonic", side_effect=lambda: clock[0]):
                request_report(
                    "PICO-A", lock_dir=Path(tmp), timeout=0.1,
                    port_finder=lambda serial: "/dev/ttyACM0", serial_factory=serial_factory,
                )
        self.assertEqual(len(conn.write_timeouts_at_write), 1)
        self.assertAlmostEqual(conn.write_timeouts_at_write[0], 0.06)

    def test_requests_valid_report_and_always_closes(self):
        conn = FakeSerial([b'{"type":"report","content":{"devices":[]}}\n'])
        with tempfile.TemporaryDirectory() as tmp:
            report = request_report(
                "PICO-A",
                lock_dir=Path(tmp),
                timeout=0.1,
                port_finder=lambda serial: "/dev/ttyACM7",
                serial_factory=lambda *args, **kwargs: conn,
            )
        self.assertEqual(report["type"], "report")
        self.assertTrue(conn.input_reset)
        self.assertEqual(conn.writes, [b"\nr\n"])
        self.assertTrue(conn.flushed)
        self.assertTrue(conn.closed)

    def test_client_command_returns_error_or_report_and_releases_serial(self):
        conn = FakeSerial([b'{"type":"error","content":"pulse pin is already on"}\n'])
        with tempfile.TemporaryDirectory() as tmp:
            result = PicoClient(
                "PICO-A",
                lock_dir=Path(tmp),
                serial_factory=lambda *args, **kwargs: conn,
                port_finder=lambda serial: "/dev/ttyACM7",
            ).command("p 21 5", timeout=0.1)

        self.assertEqual(result.message["type"], "error")
        self.assertEqual(result.port, "/dev/ttyACM7")
        self.assertEqual(conn.writes, [b"\np 21 5\n"])
        self.assertTrue(conn.closed)

    def test_focused_pulse_raises_firmware_error(self):
        conn = FakeSerial([b'{"type":"error","content":"pulse pin is already on"}\n'])
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(PicoCommandError, "already on"):
                pulse_gpio(
                    "PICO-A", 21, 5, lock_dir=Path(tmp), timeout=0.1,
                    serial_factory=lambda *args, **kwargs: conn,
                    port_finder=lambda serial: "/dev/ttyACM7",
                )

    def test_one_locked_operation_can_rediscover_after_usb_reconnect(self):
        ports = iter(["/dev/ttyACM0", "/dev/ttyACM1"])
        first = FakeSerial([b'{"type":"report","content":{"devices":[]}}\n'])
        second = FakeSerial([b'{"type":"report","content":{"devices":[]}}\n'])
        serials = iter([first, second])
        with tempfile.TemporaryDirectory() as tmp:
            client = PicoClient(
                "PICO-A",
                lock_dir=Path(tmp),
                serial_factory=lambda *args, **kwargs: next(serials),
                port_finder=lambda serial: next(ports),
            )
            with client.operation(timeout=0.2) as operation:
                before = operation.report()
                after = operation.report()

        self.assertEqual(before.port, "/dev/ttyACM0")
        self.assertEqual(after.port, "/dev/ttyACM1")
        self.assertTrue(first.closed)
        self.assertTrue(second.closed)

    def test_flash_holds_operation_until_reconnected_valid_report(self):
        conn = FakeSerial([b'{"type":"report","content":{"devices":[]}}\n'])
        ports = iter(["/dev/ttyACM0", "/dev/ttyACM1"])
        commands = []
        interrupts = []
        with tempfile.TemporaryDirectory() as tmp:
            client = PicoClient(
                "PICO-A",
                lock_dir=Path(tmp),
                serial_factory=lambda *args, **kwargs: conn,
                port_finder=lambda serial: next(ports),
            )
            result = client.flash_main(
                Path(tmp) / "main.py",
                timeout=0.2,
                mpremote="/usr/bin/mpremote",
                command_runner=lambda args, timeout: commands.append(args) or (0, "", ""),
                interrupter=lambda port: interrupts.append(port),
                sleeper=lambda seconds: None,
            )

        self.assertEqual(interrupts, ["/dev/ttyACM0"])
        self.assertIn("resume", commands[0])
        self.assertIn(":main.py", commands[0])
        self.assertEqual(commands[1][-1], "reset")
        self.assertEqual(result.port, "/dev/ttyACM1")
        self.assertEqual(result.message["type"], "report")

    def test_flash_failure_identifies_failed_step(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = PicoClient(
                "PICO-A",
                lock_dir=Path(tmp),
                port_finder=lambda serial: "/dev/ttyACM0",
            )
            with self.assertRaises(PicoFlashError) as caught:
                client.flash_main(
                    Path(tmp) / "main.py",
                    timeout=0.2,
                    mpremote="/usr/bin/mpremote",
                    command_runner=lambda args, timeout: (7, "out", "bad"),
                    interrupter=lambda port: None,
                )

        self.assertEqual(caught.exception.step, "firmware")
        self.assertEqual(caught.exception.returncode, 7)

    def test_logs_malformed_line_in_timeout_and_keeps_reading(self):
        conn = FakeSerial([b'bad\n', b'{"type":"report","content":{"devices":[]}}\n'])
        with tempfile.TemporaryDirectory() as tmp:
            report = request_report(
                "PICO-A",
                lock_dir=Path(tmp),
                timeout=0.1,
                port_finder=lambda serial: "/dev/ttyACM0",
                serial_factory=lambda *args, **kwargs: conn,
            )
        self.assertEqual(report["content"]["devices"], [])

    def test_accumulates_valid_report_split_across_reads(self):
        conn = FakeSerial(
            [b'{"type":"report","content":', b'{"devices":[]}}\n']
        )
        with tempfile.TemporaryDirectory() as tmp:
            report = request_report(
                "PICO-A",
                lock_dir=Path(tmp),
                timeout=0.1,
                port_finder=lambda serial: "/dev/ttyACM0",
                serial_factory=lambda *args, **kwargs: conn,
            )
        self.assertEqual(report["content"]["devices"], [])
        self.assertEqual(conn.readline_calls, 2)

    def test_missing_pico_is_clear_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(PicoUnavailable, "PICO-A"):
                request_report("PICO-A", lock_dir=Path(tmp), timeout=0.1, port_finder=lambda serial: None)

    def test_no_valid_report_times_out_with_raw_lines(self):
        conn = FakeSerial([b'bad\n'])
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(PicoReportTimeout) as caught:
                request_report(
                    "PICO-A",
                    lock_dir=Path(tmp),
                    timeout=0.01,
                    port_finder=lambda serial: "/dev/ttyACM0",
                    serial_factory=lambda *args, **kwargs: conn,
                )
        self.assertEqual(caught.exception.raw_lines, (b'bad\n',))
        self.assertTrue(conn.closed)

    def test_read_timeout_never_exceeds_remaining_deadline(self):
        conn = FakeSerial([b""])
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(PicoReportTimeout):
                request_report(
                    "PICO-A",
                    lock_dir=Path(tmp),
                    timeout=0.01,
                    port_finder=lambda serial: "/dev/ttyACM0",
                    serial_factory=lambda *args, **kwargs: conn,
                )
        self.assertTrue(conn.read_timeouts)
        self.assertTrue(all(0 < value <= 0.01 for value in conn.read_timeouts))

    def test_expired_deadline_does_not_discover_or_read(self):
        conn = FakeSerial([])
        discovery_calls = []

        def find_port(serial):
            discovery_calls.append(serial)
            return "/dev/ttyACM0"

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(PicoReportTimeout) as caught:
                request_report(
                    "PICO-A",
                    lock_dir=Path(tmp),
                    timeout=0.0,
                    port_finder=find_port,
                    serial_factory=lambda *args, **kwargs: conn,
                )
        self.assertEqual(caught.exception.raw_lines, ())
        self.assertEqual(discovery_calls, [])
        self.assertEqual(conn.readline_calls, 0)

    def test_discovery_cannot_return_an_error_after_deadline(self):
        def slow_missing_port(serial):
            time.sleep(0.01)
            return None

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(PicoReportTimeout):
                request_report(
                    "PICO-A",
                    lock_dir=Path(tmp),
                    timeout=0.001,
                    port_finder=slow_missing_port,
                )
