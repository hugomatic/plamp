import math
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from plamp import LockTimeout as ExportedLockTimeout
from plamp.locks import LockTimeout
from plamp.pico_transport import PicoReportTimeout, PicoUnavailable, _lock_name, request_report


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
    def test_package_exports_lock_timeout(self):
        self.assertIs(ExportedLockTimeout, LockTimeout)

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
        self.assertEqual(conn.writes, [b"r\n"])
        self.assertTrue(conn.flushed)
        self.assertTrue(conn.closed)

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
