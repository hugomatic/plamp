import unittest
from contextlib import contextmanager

from plamp import FirmwareIdentity
from plamp.pico_scheduler import apply_scheduler_state
from plamp.pico_transport import PicoCommandError, PicoExchange


EXPECTED = FirmwareIdentity("pico_scheduler", "newrev", 2)
CURRENT = {"devices": [{"id": "old"}]}
PROPOSED = {"devices": [{"id": "new"}]}


def report(identity=EXPECTED, *, devices=None):
    firmware = None if identity is None else {
        "name": identity.name,
        "revision": identity.revision,
        "protocol": identity.protocol,
    }
    content = {"devices": devices or []}
    if firmware is not None:
        content["firmware"] = firmware
    return {"type": "report", "content": content}


class FakeOperation:
    def __init__(self, before, configured, *, active=None, upgrade_error=None):
        self.before = before
        self.active = active
        self.configured = configured
        self.upgrade_error = upgrade_error
        self.calls = []
        self.entered = False
        self.upgrade_states = []
        self.configure_states = []

    def _record(self, call):
        if not self.entered:
            raise AssertionError("operation method called without operation lock")
        self.calls.append(call)

    def report(self):
        self._record("report")
        return self.before

    def upgrade_scheduler(self, state, expected):
        self._record("upgrade")
        self.upgrade_states.append(state)
        if self.upgrade_error is not None:
            raise self.upgrade_error
        return self.active

    def configure(self, state):
        self._record("configure")
        self.configure_states.append(state)
        return self.configured


class FakeClient:
    def __init__(self, operation):
        self.fake_operation = operation
        self.operation_calls = 0
        self.timeouts = []

    @contextmanager
    def operation(self, *, timeout):
        self.operation_calls += 1
        self.timeouts.append(timeout)
        self.fake_operation.entered = True
        try:
            yield self.fake_operation
        finally:
            self.fake_operation.entered = False


def exchange(identity, port, raw_line, *, devices=None):
    return PicoExchange(report(identity, devices=devices), port, (raw_line,))


class SchedulerApplyTests(unittest.TestCase):
    def apply(self, operation, *, expected=EXPECTED, timeout=60):
        client = FakeClient(operation)

        def upgrade(active_operation, state, identity):
            self.assertIs(active_operation, operation)
            self.assertEqual(identity, expected)
            return active_operation.upgrade_scheduler(state, identity)

        result = apply_scheduler_state(
            client=client,
            current_state=CURRENT,
            proposed_state=PROPOSED,
            expected=expected,
            upgrade=upgrade,
            timeout=timeout,
        )
        return client, result

    def test_mismatched_firmware_upgrades_committed_state_then_configures_proposal(self):
        previous = FirmwareIdentity("pico_scheduler", "oldrev", 2)
        proposed_report = report(EXPECTED, devices=[{"id": "new"}])
        operation = FakeOperation(
            exchange(previous, "/dev/old", b"before\n"),
            PicoExchange(proposed_report, "/dev/new", (b"configured\n",)),
            active=exchange(EXPECTED, "/dev/new", b"upgraded\n"),
        )

        client, result = self.apply(operation)

        self.assertEqual(operation.calls, ["report", "upgrade", "configure"])
        self.assertEqual(operation.upgrade_states, [CURRENT])
        self.assertEqual(operation.configure_states, [PROPOSED])
        self.assertEqual(client.operation_calls, 1)
        self.assertEqual(client.timeouts, [60])
        self.assertTrue(result.upgraded)
        self.assertEqual(result.previous_identity, previous)
        self.assertEqual(result.identity, EXPECTED)
        self.assertEqual(result.report, proposed_report)
        self.assertEqual(result.port, "/dev/new")
        self.assertEqual(
            result.raw_lines,
            (b"before\n", b"upgraded\n", b"configured\n"),
        )

    def test_current_firmware_configures_without_upgrade_or_duplicate_report_lines(self):
        operation = FakeOperation(
            exchange(EXPECTED, "/dev/pico", b"before\n"),
            exchange(EXPECTED, "/dev/pico", b"configured\n"),
        )

        client, result = self.apply(operation, timeout=4.5)

        self.assertEqual(operation.calls, ["report", "configure"])
        self.assertEqual(client.operation_calls, 1)
        self.assertEqual(client.timeouts, [4.5])
        self.assertFalse(result.upgraded)
        self.assertEqual(result.raw_lines, (b"before\n", b"configured\n"))

    def test_legacy_report_triggers_upgrade(self):
        operation = FakeOperation(
            exchange(None, "/dev/pico", b"legacy\n"),
            exchange(EXPECTED, "/dev/pico", b"configured\n"),
            active=exchange(EXPECTED, "/dev/pico", b"upgraded\n"),
        )

        _, result = self.apply(operation)

        self.assertEqual(operation.calls, ["report", "upgrade", "configure"])
        self.assertIsNone(result.previous_identity)
        self.assertTrue(result.upgraded)

    def test_each_firmware_identity_field_mismatch_triggers_upgrade(self):
        mismatches = (
            FirmwareIdentity("other_firmware", "newrev", 2),
            FirmwareIdentity("pico_scheduler", "oldrev", 2),
            FirmwareIdentity("pico_scheduler", "newrev", 1),
        )
        for previous in mismatches:
            with self.subTest(previous=previous):
                operation = FakeOperation(
                    exchange(previous, "/dev/pico", b"before\n"),
                    exchange(EXPECTED, "/dev/pico", b"configured\n"),
                    active=exchange(EXPECTED, "/dev/pico", b"upgraded\n"),
                )

                _, result = self.apply(operation)

                self.assertEqual(operation.calls, ["report", "upgrade", "configure"])
                self.assertTrue(result.upgraded)

    def test_upgrade_failure_does_not_configure(self):
        operation = FakeOperation(
            exchange(None, "/dev/pico", b"legacy\n"),
            exchange(EXPECTED, "/dev/pico", b"configured\n"),
            upgrade_error=RuntimeError("upgrade failed"),
        )

        with self.assertRaisesRegex(RuntimeError, "upgrade failed"):
            self.apply(operation)

        self.assertEqual(operation.calls, ["report", "upgrade"])

    def test_upgrade_that_does_not_reach_expected_identity_does_not_configure(self):
        old = FirmwareIdentity("pico_scheduler", "oldrev", 2)
        operation = FakeOperation(
            exchange(None, "/dev/pico", b"legacy\n"),
            exchange(EXPECTED, "/dev/pico", b"configured\n"),
            active=exchange(old, "/dev/pico", b"upgraded\n"),
        )

        with self.assertRaisesRegex(PicoCommandError, "does not match expected"):
            self.apply(operation)

        self.assertEqual(operation.calls, ["report", "upgrade"])

    def test_configure_identity_mismatch_is_rejected(self):
        changed = FirmwareIdentity("pico_scheduler", "otherrev", 2)
        operation = FakeOperation(
            exchange(EXPECTED, "/dev/pico", b"before\n"),
            exchange(changed, "/dev/pico", b"configured\n"),
        )

        with self.assertRaisesRegex(PicoCommandError, "changed during configuration"):
            self.apply(operation)

        self.assertEqual(operation.calls, ["report", "configure"])


if __name__ == "__main__":
    unittest.main()
