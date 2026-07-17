import unittest

import serial

from plamp.locks import LockTimeout
from plamp.pico_health import failed_health, probe_pico
from plamp.pico_transport import PicoExchange, PicoReportTimeout, PicoUnavailable


class FakeClient:
    def __init__(self, result):
        self.pico_serial = "PICO-A"
        self.result = result
        self.timeouts = []

    def report(self, *, timeout):
        self.timeouts.append(timeout)
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


class PicoHealthTests(unittest.TestCase):
    def test_success_contains_valid_report_evidence(self):
        exchange = PicoExchange(
            {"type": "report", "content": {"devices": []}},
            "/dev/ttyACM0",
            (b'{"type":"report"}\n',),
        )

        result = probe_pico(FakeClient(exchange), timeout=2.5)

        self.assertTrue(result.ok)
        self.assertEqual(result.status, "OK")
        self.assertEqual(result.serial, "PICO-A")
        self.assertEqual(result.port, "/dev/ttyACM0")
        self.assertEqual(result.report["type"], "report")
        self.assertEqual(result.raw_lines, ('{"type":"report"}',))
        self.assertIsNone(result.error)
        self.assertIn("+00:00", result.checked_at)

    def test_missing_pico_is_unavailable_during_discovery(self):
        result = probe_pico(FakeClient(PicoUnavailable("configured Pico is not connected: PICO-A")))

        self.assertFalse(result.ok)
        self.assertEqual(result.status, "ERROR")
        self.assertEqual(result.error.kind, "unavailable")
        self.assertEqual(result.error.step, "discover")
        self.assertIn("not connected", result.error.message)

    def test_timeout_preserves_raw_lines_and_distinguishes_protocol_failure(self):
        result = probe_pico(FakeClient(PicoReportTimeout("timed out", [b">>>\n", b"bad json\n"])))

        self.assertEqual(result.error.kind, "protocol")
        self.assertEqual(result.error.step, "report")
        self.assertEqual(result.error.raw_lines, (">>>", "bad json"))

    def test_silent_timeout_is_a_timeout(self):
        result = probe_pico(FakeClient(PicoReportTimeout("timed out", [])))

        self.assertEqual(result.error.kind, "timeout")
        self.assertEqual(result.error.raw_lines, ())

    def test_serial_failures_are_diagnostic_errors(self):
        for failure in (OSError("device vanished"), serial.SerialException("port failed")):
            with self.subTest(failure=failure):
                result = probe_pico(FakeClient(failure))
                self.assertEqual(result.error.kind, "serial")
                self.assertEqual(result.error.step, "report")
                self.assertIn(str(failure), result.error.message)

    def test_lock_contention_is_not_controller_health(self):
        with self.assertRaises(LockTimeout):
            probe_pico(FakeClient(LockTimeout("busy")))

    def test_failed_health_uses_same_public_shape(self):
        result = failed_health(
            "PICO-A",
            kind="unavailable",
            step="discover",
            message="configured Pico is not connected",
            port="/dev/ttyACM0",
        )

        self.assertEqual(
            result.as_dict()["error"],
            {
                "kind": "unavailable",
                "step": "discover",
                "message": "configured Pico is not connected",
                "raw_lines": [],
            },
        )


if __name__ == "__main__":
    unittest.main()
