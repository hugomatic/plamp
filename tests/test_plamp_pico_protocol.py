import unittest

from plamp.pico_protocol import PicoProtocolError, decode_report_line


class PicoProtocolTests(unittest.TestCase):
    def test_accepts_type_report_with_newline(self):
        report = decode_report_line(b'{"type":"report","content":{"devices":[]}}\r\n')
        self.assertEqual(report["type"], "report")

    def test_normalizes_legacy_kind_report(self):
        report = decode_report_line(b'{"kind":"report","content":{"devices":[]}}\n')
        self.assertEqual(report["type"], "report")
        self.assertNotIn("kind", report)

    def test_accepts_report_with_firmware_identity_object(self):
        report = decode_report_line(
            b'{"type":"report","content":{"firmware":{"name":"pico_scheduler",'
            b'"revision":"abc1234","protocol":2},"devices":[]}}\n'
        )
        self.assertEqual(report["content"]["firmware"]["protocol"], 2)

    def test_rejects_report_with_non_object_firmware_identity(self):
        with self.assertRaisesRegex(PicoProtocolError, "content.firmware must be an object"):
            decode_report_line(
                b'{"type":"report","content":{"firmware":"pico_scheduler","devices":[]}}\n'
            )

    def test_rejects_incomplete_line(self):
        with self.assertRaisesRegex(PicoProtocolError, "newline"):
            decode_report_line(b'{"type":"report"}')

    def test_rejects_malformed_json_and_non_report(self):
        with self.assertRaisesRegex(PicoProtocolError, "JSON"):
            decode_report_line(b'bad\n')
        with self.assertRaisesRegex(PicoProtocolError, "not a report"):
            decode_report_line(b'{"type":"error","content":"bad"}\n')
