# Agent-First Pico Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a service-independent `python -m plamp pico report <controller>` path that safely locks, discovers, queries, and releases a configured Pico.

**Architecture:** A new `plamp` package provides focused lock, discovery, protocol, and transport modules. Its CLI adapter reads the controller USB serial from existing configuration and performs a short-lived `r` transaction directly; it does not call REST or import `plamp_web`. Existing `plamp_cli`, REST, SSE, firmware generation, and service behavior remain unchanged in this slice. Until the next slice migrates the legacy monitor, direct hardware commands must be run with `plamp-web` stopped because that monitor does not yet participate in the filesystem lock.

**Tech Stack:** Python 3.11, `fcntl.flock`, pyserial, `unittest`, `unittest.mock`, existing `uv` environment.

## Global Constraints

- The direct CLI must work while `plamp-web` is stopped.
- Hardware identity is the configured USB serial number, never a stored `/dev/ttyACM*` path.
- Hold one per-Pico filesystem lock through open, request, complete response, and close.
- Do not introduce a daemon, broker, leader election, WebSocket, or P2P dependency.
- Do not change Pico firmware or `report_every` behavior in this slice.
- Preserve every existing CLI and REST command.
- Do not run a direct serial command concurrently with the legacy `plamp-web` monitor in this slice.
- Do not run OpenSCAD.
- Use dependency injection in hardware tests; unit tests must not open real serial devices.

---

## File Structure

- Create `plamp/__init__.py`: public exception and report exports only; importing it has no side effects.
- Create `plamp/__main__.py`: `python -m plamp` entry point.
- Create `plamp/cli.py`: direct CLI argument parsing, configuration lookup, JSON output, and exit-code mapping.
- Create `plamp/config.py`: read-only controller-to-Pico-serial lookup for this slice.
- Create `plamp/locks.py`: deadline-bound advisory file lock.
- Create `plamp/pico_discovery.py`: current device-path discovery by stable USB serial.
- Create `plamp/pico_protocol.py`: complete-line JSON report validation.
- Create `plamp/pico_transport.py`: locked open/send/read/close report transaction.
- Create `tests/test_plamp_locks.py`: process-lock behavior.
- Create `tests/test_plamp_pico_discovery.py`: USB serial matching behavior.
- Create `tests/test_plamp_pico_protocol.py`: framing and validation behavior.
- Create `tests/test_plamp_pico_transport.py`: serial lifecycle, malformed input, and timeout behavior.
- Create `tests/test_plamp_direct_cli.py`: service-independent CLI contract.
- Modify `pyproject.toml`: include the new `plamp` package in package discovery without changing the existing console-script target.

---

### Task 1: Budget-Bound Cross-Process Lock

The timeout is a finite, non-negative enforced budget for lock polling; `0` means
an immediate attempt. Synchronous filesystem calls cannot be forcibly interrupted.

**Files:**
- Create: `plamp/__init__.py`
- Create: `plamp/locks.py`
- Create: `tests/test_plamp_locks.py`

**Interfaces:**
- Produces: `LockTimeout(TimeoutError)`.
- Produces: `exclusive_lock(path: Path, *, timeout: float, poll_interval: float = 0.01) -> ContextManager[None]`.
- Consumes: no earlier task interfaces.

- [ ] **Step 1: Write failing lock tests**

```python
# tests/test_plamp_locks.py
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from plamp.locks import LockTimeout, exclusive_lock


class LockTests(unittest.TestCase):
    def test_lock_creates_parent_and_releases_for_next_caller(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "pico-abc.lock"
            with exclusive_lock(path, timeout=0.1):
                self.assertTrue(path.exists())
            with exclusive_lock(path, timeout=0.1):
                pass

    def test_lock_times_out_while_same_file_is_held(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pico-abc.lock"
            with exclusive_lock(path, timeout=0.1):
                with patch("plamp.locks.time.sleep"):
                    with self.assertRaisesRegex(LockTimeout, "pico-abc.lock"):
                        with exclusive_lock(path, timeout=0.0):
                            pass
```

- [ ] **Step 2: Run the tests and confirm the missing module failure**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest tests.test_plamp_locks -v
```

Expected: the test run fails because the `plamp` package cannot yet be imported.

- [ ] **Step 3: Implement the lock context manager**

```python
# plamp/locks.py
from __future__ import annotations

import errno
import fcntl
import math
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class LockTimeout(TimeoutError):
    pass


@contextmanager
def exclusive_lock(path: Path, *, timeout: float, poll_interval: float = 0.01) -> Iterator[None]:
    if not math.isfinite(timeout) or timeout < 0:
        raise ValueError("timeout must be finite and non-negative")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR, 0o664)
    deadline = time.monotonic() + timeout
    try:
        while True:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as exc:
                if exc.errno not in (errno.EACCES, errno.EAGAIN):
                    raise
                if time.monotonic() >= deadline:
                    raise LockTimeout(f"timed out waiting for {path.name}") from exc
                time.sleep(min(poll_interval, max(deadline - time.monotonic(), 0.0)))
        yield
    finally:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)
```

Keep `plamp/__init__.py` empty in this task so importing the package has no side effects.

- [ ] **Step 4: Run the lock tests**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest tests.test_plamp_locks -v
```

Expected: 4 tests pass, including invalid-budget coverage and true subprocess contention/release.

- [ ] **Step 5: Commit the lock primitive**

```bash
git add plamp/__init__.py plamp/locks.py tests/test_plamp_locks.py
git commit -m "Add cross-process Plamp hardware lock"
```

---

### Task 2: Stable Pico USB Discovery

**Files:**
- Create: `plamp/pico_discovery.py`
- Create: `tests/test_plamp_pico_discovery.py`

**Interfaces:**
- Produces: immutable `PicoPort(serial: str, device: str)`.
- Produces: `discover_picos(*, comports: Callable[[], Iterable[Any]] = list_ports.comports) -> list[PicoPort]`.
- Produces: `find_pico_port(pico_serial: str, *, comports: Callable[[], Iterable[Any]] = list_ports.comports) -> str | None`.
- Consumes: no earlier task interfaces.

- [ ] **Step 1: Write failing discovery tests**

```python
# tests/test_plamp_pico_discovery.py
import unittest
from types import SimpleNamespace

from plamp.pico_discovery import discover_picos, find_pico_port


class PicoDiscoveryTests(unittest.TestCase):
    def test_discovers_raspberry_pi_usb_serial_devices(self):
        ports = lambda: [
            SimpleNamespace(device="/dev/ttyACM1", vid=0x2E8A, serial_number="PICO-B"),
            SimpleNamespace(device="/dev/ttyUSB0", vid=0x1234, serial_number="OTHER"),
        ]
        self.assertEqual(
            [(item.serial, item.device) for item in discover_picos(comports=ports)],
            [("PICO-B", "/dev/ttyACM1")],
        )

    def test_finds_reassigned_path_by_serial_number(self):
        ports = lambda: [SimpleNamespace(device="/dev/ttyACM7", vid=0x2E8A, serial_number="PICO-A")]
        self.assertEqual(find_pico_port("PICO-A", comports=ports), "/dev/ttyACM7")

    def test_missing_serial_returns_none(self):
        self.assertIsNone(find_pico_port("missing", comports=lambda: []))
```

- [ ] **Step 2: Run the discovery tests and confirm failure**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest tests.test_plamp_pico_discovery -v
```

Expected: import failure for `plamp.pico_discovery`.

- [ ] **Step 3: Implement stable discovery**

```python
# plamp/pico_discovery.py
from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from serial.tools import list_ports


RASPBERRY_PI_USB_VENDOR_ID = 0x2E8A


@dataclass(frozen=True)
class PicoPort:
    serial: str
    device: str


def discover_picos(*, comports: Callable[[], Iterable[Any]] = list_ports.comports) -> list[PicoPort]:
    found = []
    for port in comports():
        serial = getattr(port, "serial_number", None)
        if getattr(port, "vid", None) != RASPBERRY_PI_USB_VENDOR_ID or not serial:
            continue
        found.append(PicoPort(serial=str(serial), device=str(port.device)))
    return sorted(found, key=lambda item: item.device)


def find_pico_port(pico_serial: str, *, comports: Callable[[], Iterable[Any]] = list_ports.comports) -> str | None:
    for pico in discover_picos(comports=comports):
        if pico.serial == pico_serial:
            return pico.device
    return None
```

- [ ] **Step 4: Run discovery tests**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest tests.test_plamp_pico_discovery -v
```

Expected: 3 tests pass.

- [ ] **Step 5: Commit stable discovery**

```bash
git add plamp/pico_discovery.py tests/test_plamp_pico_discovery.py
git commit -m "Discover Picos by stable USB serial"
```

---

### Task 3: Strict Pico Report Protocol

**Files:**
- Create: `plamp/pico_protocol.py`
- Create: `tests/test_plamp_pico_protocol.py`

**Interfaces:**
- Produces: `PicoProtocolError(ValueError)`.
- Produces: `decode_report_line(raw: bytes) -> dict[str, Any]`.
- Consumes: no earlier task interfaces.

- [ ] **Step 1: Write failing protocol tests**

```python
# tests/test_plamp_pico_protocol.py
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

    def test_rejects_incomplete_line(self):
        with self.assertRaisesRegex(PicoProtocolError, "newline"):
            decode_report_line(b'{"type":"report"}')

    def test_rejects_malformed_json_and_non_report(self):
        with self.assertRaisesRegex(PicoProtocolError, "JSON"):
            decode_report_line(b'bad\n')
        with self.assertRaisesRegex(PicoProtocolError, "not a report"):
            decode_report_line(b'{"type":"error","content":"bad"}\n')
```

- [ ] **Step 2: Run protocol tests and confirm failure**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest tests.test_plamp_pico_protocol -v
```

Expected: import failure for `plamp.pico_protocol`.

- [ ] **Step 3: Implement strict line decoding**

```python
# plamp/pico_protocol.py
from __future__ import annotations

import json
from typing import Any


class PicoProtocolError(ValueError):
    pass


def decode_report_line(raw: bytes) -> dict[str, Any]:
    if not raw.endswith(b"\n"):
        raise PicoProtocolError("report is not newline terminated")
    try:
        value = json.loads(raw.decode("utf-8").strip())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PicoProtocolError(f"invalid report JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise PicoProtocolError("report JSON must be an object")
    if "type" not in value and "kind" in value:
        value = dict(value)
        value["type"] = value.pop("kind")
    if value.get("type") != "report" or not isinstance(value.get("content"), dict):
        raise PicoProtocolError("message is not a report")
    if not isinstance(value["content"].get("devices"), list):
        raise PicoProtocolError("report content.devices must be a list")
    return value
```

- [ ] **Step 4: Run protocol tests**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest tests.test_plamp_pico_protocol -v
```

Expected: 4 tests pass.

- [ ] **Step 5: Commit protocol validation**

```bash
git add plamp/pico_protocol.py tests/test_plamp_pico_protocol.py
git commit -m "Validate complete Pico report lines"
```

---

### Task 4: Locked Short-Lived Report Transaction

**Files:**
- Create: `plamp/pico_transport.py`
- Create: `tests/test_plamp_pico_transport.py`
- Modify: `plamp/__init__.py`

**Interfaces:**
- Produces: `PicoUnavailable(ConnectionError)`.
- Produces: `PicoReportTimeout(TimeoutError)` with `raw_lines: tuple[bytes, ...]`.
- Produces: `request_report(pico_serial: str, *, lock_dir: Path, timeout: float = 3.0, serial_factory: Callable[..., Any] = serial.Serial, port_finder: Callable[[str], str | None] = find_pico_port) -> dict[str, Any]`.
- Consumes: `exclusive_lock`, `decode_report_line`, `PicoProtocolError`, and `find_pico_port`.

- [ ] **Step 1: Write a fake serial connection and failing transaction tests**

```python
# tests/test_plamp_pico_transport.py
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
        conn = FakeSerial([b'{"type":"report","content":', b'{"devices":[]}}\n'])
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
```

- [ ] **Step 2: Run transport tests and confirm failure**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest tests.test_plamp_pico_transport -v
```

Expected: import failure for `plamp.pico_transport`.

- [ ] **Step 3: Implement the locked transaction**

```python
# plamp/pico_transport.py
from __future__ import annotations

import hashlib
import logging
import math
import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import serial

from plamp.locks import exclusive_lock
from plamp.pico_discovery import find_pico_port
from plamp.pico_protocol import PicoProtocolError, decode_report_line

LOGGER = logging.getLogger(__name__)


class PicoUnavailable(ConnectionError):
    pass


class PicoReportTimeout(TimeoutError):
    def __init__(self, message: str, raw_lines: list[bytes]):
        super().__init__(message)
        self.raw_lines = tuple(raw_lines)


def _lock_name(pico_serial: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", pico_serial)
    digest = hashlib.sha256(pico_serial.encode("utf-8")).hexdigest()[:12]
    return f"pico-{safe}-{digest}.lock"


def _remaining_or_timeout(
    deadline: float, pico_serial: str, raw_lines: list[bytes]
) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise PicoReportTimeout(
            f"timed out waiting for report from {pico_serial}", raw_lines
        )
    return remaining


def request_report(
    pico_serial: str,
    *,
    lock_dir: Path,
    timeout: float = 3.0,
    serial_factory: Callable[..., Any] = serial.Serial,
    port_finder: Callable[[str], str | None] = find_pico_port,
) -> dict[str, Any]:
    if not math.isfinite(timeout) or timeout < 0:
        raise ValueError("timeout must be finite and non-negative")
    deadline = time.monotonic() + timeout
    lock_timeout = max(deadline - time.monotonic(), 0.0)
    with exclusive_lock(lock_dir / _lock_name(pico_serial), timeout=lock_timeout):
        raw_lines: list[bytes] = []
        _remaining_or_timeout(deadline, pico_serial, raw_lines)
        port = port_finder(pico_serial)
        remaining = _remaining_or_timeout(deadline, pico_serial, raw_lines)
        if port is None:
            raise PicoUnavailable(f"configured Pico is not connected: {pico_serial}")
        conn = serial_factory(
            port,
            baudrate=115200,
            timeout=min(0.05, remaining),
            write_timeout=remaining,
            exclusive=True,
        )
        try:
            _remaining_or_timeout(deadline, pico_serial, raw_lines)
            conn.reset_input_buffer()
            remaining = _remaining_or_timeout(deadline, pico_serial, raw_lines)
            conn.write_timeout = remaining
            conn.write(b"r\n")
            _remaining_or_timeout(deadline, pico_serial, raw_lines)
            conn.flush()
            buffered = b""
            while True:
                remaining = _remaining_or_timeout(deadline, pico_serial, raw_lines)
                conn.timeout = min(0.05, remaining)
                raw = conn.readline()
                if raw:
                    raw_lines.append(raw)
                    buffered += raw
                    while b"\n" in buffered:
                        line, buffered = buffered.split(b"\n", 1)
                        line += b"\n"
                        LOGGER.debug(
                            "pico raw serial=%s len=%d newline=%s repr=%r",
                            pico_serial,
                            len(line),
                            True,
                            line,
                        )
                        try:
                            return decode_report_line(line)
                        except PicoProtocolError:
                            LOGGER.warning(
                                "ignored invalid Pico line serial=%s repr=%r",
                                pico_serial,
                                line,
                            )
        finally:
            conn.close()
```

Export `LockTimeout`, `PicoReportTimeout`, `PicoUnavailable`, and `request_report` from `plamp/__init__.py`. Do not export CLI functions.

`request_report` treats the timeout as an enforced transaction budget: it is used
for the file lock and serial read/write timeouts and checked around discovery,
open, reset, and flush. Close remains unconditional. These synchronous OS/driver
calls cannot safely be preempted, so the budget is not a hard interrupt guarantee.
Do not add worker threads.

- [ ] **Step 4: Run transaction and earlier unit tests**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest \
  tests.test_plamp_locks \
  tests.test_plamp_pico_discovery \
  tests.test_plamp_pico_protocol \
  tests.test_plamp_pico_transport -v
```

Expected: 24 tests pass (4 lock, 3 discovery, 4 protocol, and 13 transport tests).

- [ ] **Step 5: Commit the transaction**

```bash
git add plamp/__init__.py plamp/pico_transport.py tests/test_plamp_pico_transport.py
git commit -m "Add locked direct Pico report transaction"
```

---

### Task 5: Direct Agent CLI

**Files:**
- Create: `plamp/config.py`
- Create: `plamp/cli.py`
- Create: `plamp/__main__.py`
- Create: `tests/test_plamp_direct_cli.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Produces: `controller_pico_serial(config_file: Path, controller: str) -> str`.
- Produces: `main(argv: Sequence[str] | None = None, *, stdout: TextIO = sys.stdout, stderr: TextIO = sys.stderr, report_func: Callable[..., dict[str, Any]] = request_report) -> int`.
- Consumes: `request_report`, `PicoUnavailable`, `PicoReportTimeout`, and the existing `data/config.json` controller shape.

- [ ] **Step 1: Write failing configuration and CLI tests**

```python
# tests/test_plamp_direct_cli.py
import io
import json
import tempfile
import unittest
from pathlib import Path

from plamp.cli import main
from plamp.config import ConfigError, controller_pico_serial


class DirectCliTests(unittest.TestCase):
    def write_config(self, root):
        path = root / "config.json"
        path.write_text(json.dumps({
            "controllers": {
                "tower": {"type": "pico_scheduler", "payload": {"pico_serial": "PICO-A"}}
            }
        }), encoding="utf-8")
        return path

    def test_controller_serial_reads_existing_config_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_config(Path(tmp))
            self.assertEqual(controller_pico_serial(path, "tower"), "PICO-A")

    def test_unknown_controller_is_clear_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_config(Path(tmp))
            with self.assertRaisesRegex(ConfigError, "missing"):
                controller_pico_serial(path, "missing")

    def test_pico_report_calls_library_and_prints_stable_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.write_config(root)
            stdout, stderr = io.StringIO(), io.StringIO()
            calls = []

            def fake_report(serial, **kwargs):
                calls.append((serial, kwargs))
                return {"type": "report", "content": {"devices": []}}

            rc = main(
                ["--config", str(config), "--lock-dir", str(root / "locks"), "pico", "report", "tower"],
                stdout=stdout,
                stderr=stderr,
                report_func=fake_report,
            )
            self.assertEqual(rc, 0)
            self.assertEqual(json.loads(stdout.getvalue())["type"], "report")
            self.assertEqual(calls[0][0], "PICO-A")
            self.assertEqual(stderr.getvalue(), "")

    def test_hardware_error_returns_nonzero_without_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.write_config(root)
            stdout, stderr = io.StringIO(), io.StringIO()

            def fail(*args, **kwargs):
                raise ConnectionError("Pico unplugged")

            rc = main(
                ["--config", str(config), "--lock-dir", str(root / "locks"), "pico", "report", "tower"],
                stdout=stdout,
                stderr=stderr,
                report_func=fail,
            )
            self.assertEqual(rc, 4)
            self.assertEqual(stdout.getvalue(), "")
            self.assertEqual(stderr.getvalue(), "Pico unplugged\n")
```

- [ ] **Step 2: Run direct CLI tests and confirm failure**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest tests.test_plamp_direct_cli -v
```

Expected: import failures for `plamp.cli` and `plamp.config`.

- [ ] **Step 3: Implement read-only configuration lookup**

```python
# plamp/config.py
from __future__ import annotations

import json
from pathlib import Path


class ConfigError(ValueError):
    pass


def controller_pico_serial(config_file: Path, controller: str) -> str:
    try:
        config = json.loads(config_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"cannot read configuration: {config_file}: {exc}") from exc
    controllers = config.get("controllers") if isinstance(config, dict) else None
    item = controllers.get(controller) if isinstance(controllers, dict) else None
    payload = item.get("payload") if isinstance(item, dict) else None
    serial = payload.get("pico_serial") if isinstance(payload, dict) else None
    if not isinstance(serial, str) or not serial:
        raise ConfigError(f"controller has no configured Pico serial: {controller}")
    return serial
```

- [ ] **Step 4: Implement the direct CLI adapter and module entry point**

```python
# plamp/cli.py
from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, TextIO

from plamp.config import ConfigError, controller_pico_serial
from plamp.locks import LockTimeout
from plamp.pico_transport import PicoReportTimeout, PicoUnavailable, request_report

REPO_ROOT = Path(__file__).resolve().parents[1]


def _non_negative_finite_timeout(value: str) -> float:
    timeout = float(value)
    if not math.isfinite(timeout) or timeout < 0:
        raise argparse.ArgumentTypeError("timeout must be finite and non-negative")
    return timeout


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m plamp")
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "data" / "config.json")
    parser.add_argument("--lock-dir", type=Path, default=REPO_ROOT / "data" / "locks")
    parser.add_argument(
        "--timeout",
        type=_non_negative_finite_timeout,
        default=3.0,
        help=(
            "operation budget in seconds (used for lock/read/write waits and checked "
            "around synchronous OS calls; those calls cannot be forcibly interrupted)"
        ),
    )
    areas = parser.add_subparsers(dest="area", required=True)
    pico = areas.add_parser("pico")
    actions = pico.add_subparsers(dest="action", required=True)
    report = actions.add_parser("report")
    report.add_argument("controller")
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
    report_func: Callable[..., dict[str, Any]] = request_report,
) -> int:
    args = build_parser().parse_args(argv)
    try:
        pico_serial = controller_pico_serial(args.config, args.controller)
        report = report_func(pico_serial, lock_dir=args.lock_dir, timeout=args.timeout)
    except ConfigError as exc:
        stderr.write(f"{exc}\n")
        return 2
    except (PicoUnavailable, PicoReportTimeout, LockTimeout, ConnectionError, OSError) as exc:
        stderr.write(f"{exc}\n")
        return 4
    stdout.write(json.dumps(report, sort_keys=True) + "\n")
    return 0
```

```python
# plamp/__main__.py
from plamp.cli import main

raise SystemExit(main())
```

Change package discovery in `pyproject.toml` to:

```toml
[tool.setuptools.packages.find]
include = ["plamp*"]
```

Do not change `[project.scripts]` in this slice; the installed `plamp` command continues to invoke the existing mature CLI until the CLI migration plan is executed.

- [ ] **Step 5: Run CLI tests and an import side-effect check**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest tests.test_plamp_direct_cli -v
/home/hugo/.local/bin/uv run python -c 'import plamp; print("ok")'
```

Expected: 4 tests pass, then `ok`.

- [ ] **Step 6: Run the existing CLI regression suite**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest \
  tests.test_plamp_cli \
  tests.test_plamp_cli_http \
  tests.test_plamp_cli_io -v
```

Expected: all existing CLI tests pass.

- [ ] **Step 7: Commit the direct CLI**

```bash
git add plamp/config.py plamp/cli.py plamp/__main__.py tests/test_plamp_direct_cli.py pyproject.toml
git commit -m "Add service-independent Pico report CLI"
```

---

### Task 6: Full Verification and Sprout Acceptance

**Files:**
- Modify: `docs/superpowers/specs/2026-07-14-agent-first-plamp-architecture-design.md` only if measured behavior contradicts the recorded acceptance numbers.

**Interfaces:**
- Consumes: `python -m plamp pico report <controller>` from Task 5.
- Produces: verified direct-report behavior while `plamp-web` is stopped, followed by verified service restoration.

- [ ] **Step 1: Run all new tests together**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest \
  tests.test_plamp_locks \
  tests.test_plamp_pico_discovery \
  tests.test_plamp_pico_protocol \
  tests.test_plamp_pico_transport \
  tests.test_plamp_direct_cli -v
```

Expected: 30 tests pass (4 lock, 3 discovery, 4 protocol, 13 transport, and 6 direct CLI tests).

- [ ] **Step 2: Run the complete Python test suite**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest discover -s tests -v
```

Expected: all tests pass. Do not treat unrelated pre-existing failures as passing; record and resolve or explicitly stop for review.

- [ ] **Step 3: Deploy the feature branch to Sprout**

Run from the repository root. The implementation branch for this plan is `feature/agent-first-pico-report`:

```bash
./plampctl remote-install hugo@sprout.local ~/plamp --branch feature/agent-first-pico-report
```

Expected: installation finishes and `plamp-web.service` is active.

- [ ] **Step 4: Stop the legacy service before direct serial acceptance**

Run:

```bash
ssh hugo@sprout.local 'sudo systemctl stop plamp-web'
```

Expected: `systemctl` exits successfully. This avoids racing the legacy permanent serial reader, which is intentionally migrated in the next slice.

- [ ] **Step 5: Verify direct report with the service stopped**

Run:

```bash
ssh hugo@sprout.local 'cd /home/hugo/plamp && /home/hugo/.local/bin/uv run python -m plamp pico report octo_relay'
```

Expected: exit 0 and one JSON object with `"type": "report"` and a `content.devices` list.

- [ ] **Step 6: Measure five direct transactions on Sprout**

Run:

```bash
ssh hugo@sprout.local 'cd /home/hugo/plamp && for n in 1 2 3 4 5; do /usr/bin/time -f "%e" /home/hugo/.local/bin/uv run python -m plamp pico report octo_relay >/dev/null; done'
```

Expected: all five exit successfully. Record process-level elapsed time separately from the earlier 8.2–8.6 ms serial transaction measurement; Python/`uv` startup overhead is not serial latency.

- [ ] **Step 7: Restore and verify the service even if an acceptance command failed**

Run as separate commands:

```bash
ssh hugo@sprout.local 'sudo systemctl start plamp-web'
ssh hugo@sprout.local 'systemctl is-active plamp-web'
```

Expected: the final command prints `active`. Perform this step before investigating any failure from Steps 5 or 6.

- [ ] **Step 8: Commit any evidence-only documentation correction**

If and only if Step 6 contradicts a number in the architecture spec, update that exact statement and commit it:

```bash
git add docs/superpowers/specs/2026-07-14-agent-first-plamp-architecture-design.md
git commit -m "Record direct Pico report acceptance timing"
```

If no correction is needed, do not create an empty commit.

## Follow-On Plans

After this slice is accepted, write separate plans in this order:

1. Demand-driven Pico firmware reports and host `report_poll_seconds` collection.
2. Firmware reconnect confirmation using the shared transaction mechanisms.
3. Cross-process camera capture and direct camera CLI.
4. Atomic configuration writes and desired/applied state separation.
5. Runtime Pico configuration without flashing.
6. MicroPython provisioning, application upgrade, and recovery.
7. REST/SSE migration and interchangeable fallback web apps.
