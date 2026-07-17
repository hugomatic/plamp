import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

from plamp.pico_commands import configure_scheduler, upgrade_scheduler
from plamp.pico_transport import PicoCommandError, PicoExchange
from plamp.scheduler_state import FirmwareIdentity

from tests.test_plamp_direct_cli import STATE


def report(revision):
    return {
        "type": "report",
        "content": {
            "firmware": {
                "name": "pico_scheduler",
                "revision": revision,
                "protocol": 2,
            },
            "devices": STATE["devices"],
        },
    }


class FakeOperation:
    def __init__(self):
        self.calls = []

    def report(self):
        self.calls.append("report")
        return PicoExchange(report("oldrev"), "/dev/ttyACM0", (b"old\n",))

    def upgrade_scheduler(self, main_path, state_path, expected, **kwargs):
        self.calls.append((
            "upgrade",
            Path(main_path).read_text(encoding="utf-8"),
            json.loads(Path(state_path).read_text(encoding="utf-8")),
            expected,
            kwargs,
        ))
        return PicoExchange(report("newrev"), "/dev/ttyACM1", (b"new\n",))


class FakeClient:
    def __init__(self, serial, *, lock_dir):
        self.serial = serial
        self.lock_dir = lock_dir
        self.operation_timeout = None
        self.active = FakeOperation()

    def configure(self, state, *, timeout):
        self.configured = (state, timeout)
        return PicoExchange({"type": "report", "content": {"devices": []}}, "/dev/pico", ())

    @contextmanager
    def operation(self, *, timeout):
        self.operation_timeout = timeout
        yield self.active


class PicoCommandTests(unittest.TestCase):
    def test_configure_uses_locked_client_operation_and_returns_report(self):
        clients = []

        def factory(*args, **kwargs):
            client = FakeClient(*args, **kwargs)
            clients.append(client)
            return client

        result = configure_scheduler(
            "PICO-A", STATE,
            lock_dir=Path("/locks"), timeout=4,
            repo_root=Path("/repo"), data_dir=Path("/data"),
            client_factory=factory,
        )

        self.assertEqual(result["type"], "report")
        self.assertEqual(clients[0].serial, "PICO-A")
        self.assertEqual(clients[0].lock_dir, Path("/locks"))
        self.assertEqual(clients[0].configured, (STATE, 4))

    def test_upgrade_stages_generic_firmware_and_state_under_one_lock(self):
        clients = []
        command_runner = object()
        interrupter = object()

        def factory(*args, **kwargs):
            client = FakeClient(*args, **kwargs)
            clients.append(client)
            return client

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = upgrade_scheduler(
                "PICO-A", {**STATE, "report_every": 9},
                lock_dir=root / "locks", timeout=60,
                repo_root=root, data_dir=root / "data",
                client_factory=factory,
                render_func=lambda repo_root: ("newrev", "# generic firmware\n"),
                mpremote_finder=lambda name: "/usr/bin/mpremote",
                command_runner=command_runner,
                interrupter=interrupter,
            )

        client = clients[0]
        self.assertEqual(client.operation_timeout, 60)
        self.assertEqual(client.active.calls[0], "report")
        upgrade = client.active.calls[1]
        self.assertEqual(upgrade[0:3], ("upgrade", "# generic firmware\n", STATE))
        self.assertEqual(upgrade[3], FirmwareIdentity("pico_scheduler", "newrev", 2))
        self.assertIs(upgrade[4]["command_runner"], command_runner)
        self.assertIs(upgrade[4]["interrupter"], interrupter)
        self.assertEqual(upgrade[4]["mpremote"], "/usr/bin/mpremote")
        self.assertEqual(result["previous_identity"]["revision"], "oldrev")
        self.assertEqual(result["identity"]["revision"], "newrev")
        self.assertEqual(result["port"], "/dev/ttyACM1")
        self.assertEqual(result["report"], report("newrev"))

    def test_upgrade_accepts_legacy_initial_report_with_null_previous_identity(self):
        class LegacyOperation(FakeOperation):
            def report(self):
                self.calls.append("report")
                message = {"type": "report", "content": {"devices": STATE["devices"]}}
                return PicoExchange(message, "/dev/ttyACM0", (b"legacy\n",))

        class LegacyClient(FakeClient):
            def __init__(self, serial, *, lock_dir):
                super().__init__(serial, lock_dir=lock_dir)
                self.active = LegacyOperation()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = upgrade_scheduler(
                "PICO-A", STATE,
                lock_dir=root / "locks", timeout=60,
                repo_root=root, data_dir=root / "data",
                client_factory=LegacyClient,
                render_func=lambda repo_root: ("newrev", "# generic firmware\n"),
                mpremote_finder=lambda name: "/usr/bin/mpremote",
                command_runner=object(), interrupter=object(),
            )

        self.assertIsNone(result["previous_identity"])
        self.assertEqual(
            result["identity"],
            {"name": "pico_scheduler", "revision": "newrev", "protocol": 2},
        )

    def test_upgrade_converts_missing_verified_identity_to_protocol_error(self):
        class MissingIdentityOperation(FakeOperation):
            def upgrade_scheduler(self, main_path, state_path, expected, **kwargs):
                message = {"type": "report", "content": {"devices": STATE["devices"]}}
                return PicoExchange(message, "/dev/ttyACM1", (b"missing\n",))

        class MissingIdentityClient(FakeClient):
            def __init__(self, serial, *, lock_dir):
                super().__init__(serial, lock_dir=lock_dir)
                self.active = MissingIdentityOperation()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(PicoCommandError, "upgraded.*identity"):
                upgrade_scheduler(
                    "PICO-A", STATE,
                    lock_dir=root / "locks", timeout=60,
                    repo_root=root, data_dir=root / "data",
                    client_factory=MissingIdentityClient,
                    render_func=lambda repo_root: ("newrev", "# generic firmware\n"),
                    mpremote_finder=lambda name: "/usr/bin/mpremote",
                    command_runner=object(), interrupter=object(),
                )


if __name__ == "__main__":
    unittest.main()
