import tempfile
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

    def reset_input_buffer(self):
        self.input_reset = True

    def write(self, value):
        self.writes.append(value)

    def flush(self):
        self.flushed = True

    def readline(self):
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
                    timeout=0.0,
                    port_finder=lambda serial: "/dev/ttyACM0",
                    serial_factory=lambda *args, **kwargs: conn,
                )
        self.assertEqual(caught.exception.raw_lines, (b'bad\n',))
        self.assertTrue(conn.closed)
