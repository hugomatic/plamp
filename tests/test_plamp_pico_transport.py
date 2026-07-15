import tempfile
import time
import unittest
from pathlib import Path

from plamp.pico_transport import PicoReportTimeout, PicoUnavailable, request_report


class FakeSerial:
    def __init__(self, lines):
        self.lines = list(lines)
        self.writes = []
        self.flushed = False
        self.input_reset = False
        self.closed = False
        self.read_timeouts = []
        self.readline_calls = 0
        self._timeout = None

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
        self.writes.append(value)

    def flush(self):
        self.flushed = True

    def readline(self):
        self.readline_calls += 1
        return self.lines.pop(0) if self.lines else b""

    def close(self):
        self.closed = True


class PicoTransportTests(unittest.TestCase):
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
