from __future__ import annotations

import hashlib
import logging
import math
import re
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import serial

from plamp.locks import exclusive_lock
from plamp.pico_discovery import find_pico_port
from plamp.pico_protocol import PicoProtocolError, decode_message_line, decode_report_line

LOGGER = logging.getLogger(__name__)


class PicoUnavailable(ConnectionError):
    pass


class PicoCommandError(RuntimeError):
    pass


class PicoFlashError(RuntimeError):
    def __init__(self, step: str, returncode: int | None, stdout: str, stderr: str):
        super().__init__(f"Pico flash {step} failed: {stderr or stdout or returncode}")
        self.step = step
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

    def detail(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }


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


@dataclass(frozen=True)
class PicoExchange:
    message: dict[str, Any]
    port: str
    raw_lines: tuple[bytes, ...]


class PicoOperation:
    """A deadline-bound operation that already owns one Pico's process lock."""

    def __init__(
        self,
        pico_serial: str,
        deadline: float,
        *,
        serial_factory: Callable[..., Any],
        port_finder: Callable[[str], str | None],
    ):
        self.pico_serial = pico_serial
        self.deadline = deadline
        self.serial_factory = serial_factory
        self.port_finder = port_finder

    def remaining(self, raw_lines: list[bytes] | None = None) -> float:
        return _remaining_or_timeout(self.deadline, self.pico_serial, raw_lines or [])

    def find_port(self) -> str:
        self.remaining()
        port = self.port_finder(self.pico_serial)
        self.remaining()
        if port is None:
            raise PicoUnavailable(f"configured Pico is not connected: {self.pico_serial}")
        return port

    def exchange(
        self,
        command: str,
        *,
        accepted_types: set[str],
        timeout: float | None = None,
    ) -> PicoExchange:
        raw_lines: list[bytes] = []
        deadline = self.deadline
        if timeout is not None:
            if not math.isfinite(timeout) or timeout < 0:
                raise ValueError("timeout must be finite and non-negative")
            deadline = min(deadline, time.monotonic() + timeout)

        def remaining() -> float:
            return _remaining_or_timeout(deadline, self.pico_serial, raw_lines)

        remaining()
        port = self.port_finder(self.pico_serial)
        remaining_value = remaining()
        if port is None:
            raise PicoUnavailable(f"configured Pico is not connected: {self.pico_serial}")
        conn = self.serial_factory(
            port,
            baudrate=115200,
            timeout=min(0.05, remaining_value),
            write_timeout=remaining_value,
            exclusive=True,
        )
        try:
            remaining()
            conn.reset_input_buffer()
            remaining_value = remaining()
            conn.write_timeout = remaining_value
            # The empty line terminates bytes left in the Pico's command buffer.
            conn.write(("\n" + command.strip() + "\n").encode("utf-8"))
            remaining()
            conn.flush()
            buffered = b""
            while True:
                remaining_value = remaining()
                conn.timeout = min(0.05, remaining_value)
                raw = conn.readline()
                if not raw:
                    continue
                raw_lines.append(raw)
                buffered += raw
                while b"\n" in buffered:
                    line, buffered = buffered.split(b"\n", 1)
                    line += b"\n"
                    LOGGER.debug(
                        "pico raw serial=%s len=%d newline=%s repr=%r",
                        self.pico_serial,
                        len(line),
                        True,
                        line,
                    )
                    try:
                        message = decode_message_line(line)
                        if message["type"] not in accepted_types:
                            raise PicoProtocolError(
                                f"unexpected message type: {message['type']}"
                            )
                        if message["type"] == "report":
                            message = decode_report_line(line)
                        return PicoExchange(message, port, tuple(raw_lines))
                    except PicoProtocolError:
                        LOGGER.warning(
                            "ignored invalid Pico line serial=%s repr=%r",
                            self.pico_serial,
                            line,
                        )
        finally:
            conn.close()

    def report(self, *, timeout: float | None = None) -> PicoExchange:
        return self.exchange("r", accepted_types={"report"}, timeout=timeout)


class PicoClient:
    def __init__(
        self,
        pico_serial: str,
        *,
        lock_dir: Path,
        serial_factory: Callable[..., Any] = serial.Serial,
        port_finder: Callable[[str], str | None] = find_pico_port,
    ):
        self.pico_serial = pico_serial
        self.lock_dir = lock_dir
        self.serial_factory = serial_factory
        self.port_finder = port_finder

    @contextmanager
    def operation(self, *, timeout: float) -> Iterator[PicoOperation]:
        if not math.isfinite(timeout) or timeout < 0:
            raise ValueError("timeout must be finite and non-negative")
        deadline = time.monotonic() + timeout
        with exclusive_lock(
            self.lock_dir / _lock_name(self.pico_serial),
            timeout=max(deadline - time.monotonic(), 0.0),
        ):
            yield PicoOperation(
                self.pico_serial,
                deadline,
                serial_factory=self.serial_factory,
                port_finder=self.port_finder,
            )

    def report(self, *, timeout: float = 3.0) -> PicoExchange:
        with self.operation(timeout=timeout) as operation:
            return operation.report()

    def command(self, text: str, *, timeout: float = 3.0) -> PicoExchange:
        with self.operation(timeout=timeout) as operation:
            return operation.exchange(text, accepted_types={"report", "error"})

    def flash_main(
        self,
        path: Path,
        *,
        timeout: float,
        mpremote: str,
        command_runner: Callable[[list[str], float], tuple[int | None, str, str]],
        interrupter: Callable[[str], None],
        sleeper: Callable[[float], Any] = time.sleep,
    ) -> PicoExchange:
        """Copy, reset, rediscover, and verify firmware under one Pico lock."""
        attempted_lines: list[bytes] = []
        with self.operation(timeout=timeout) as operation:
            port = operation.find_port()
            interrupter(port)
            firmware_rc, firmware_out, firmware_err = command_runner(
                [mpremote, "connect", port, "resume", "cp", str(path), ":main.py"],
                min(30, operation.remaining()),
            )
            if firmware_rc != 0:
                raise PicoFlashError("firmware", firmware_rc, firmware_out, firmware_err)
            reset_rc, reset_out, reset_err = command_runner(
                [mpremote, "connect", port, "reset"],
                min(15, operation.remaining()),
            )
            if reset_rc != 0:
                raise PicoFlashError("reset", reset_rc, reset_out, reset_err)
            while True:
                try:
                    result = operation.report(timeout=min(0.5, operation.remaining()))
                    return PicoExchange(
                        result.message,
                        result.port,
                        tuple(attempted_lines) + result.raw_lines,
                    )
                except PicoReportTimeout as exc:
                    attempted_lines.extend(exc.raw_lines)
                except (PicoUnavailable, OSError, serial.SerialException):
                    pass
                try:
                    remaining = operation.remaining(attempted_lines)
                except PicoReportTimeout:
                    raise PicoReportTimeout(
                        f"timed out waiting for report from {self.pico_serial}",
                        attempted_lines,
                    ) from None
                sleeper(min(0.05, remaining))


def request_report(
    pico_serial: str,
    *,
    lock_dir: Path,
    timeout: float = 3.0,
    serial_factory: Callable[..., Any] = serial.Serial,
    port_finder: Callable[[str], str | None] = find_pico_port,
) -> dict[str, Any]:
    """Request one report using ``timeout`` as an enforced operation budget.

    The remaining budget is checked around synchronous discovery, open, reset, and
    flush operations and is supplied to lock, serial read, and serial write waits.
    Synchronous OS and driver calls cannot be preempted, so this is not a hard interrupt
    guarantee for those calls.
    """
    return PicoClient(
        pico_serial,
        lock_dir=lock_dir,
        serial_factory=serial_factory,
        port_finder=port_finder,
    ).report(timeout=timeout).message


def pulse_gpio(
    pico_serial: str,
    pin: int,
    seconds: int,
    *,
    lock_dir: Path,
    timeout: float = 3.0,
    serial_factory: Callable[..., Any] = serial.Serial,
    port_finder: Callable[[str], str | None] = find_pico_port,
) -> dict[str, Any]:
    if isinstance(pin, bool) or not isinstance(pin, int) or pin < 0 or pin > 29:
        raise ValueError("pin must be an integer in range 0..29")
    if isinstance(seconds, bool) or not isinstance(seconds, int) or seconds <= 0:
        raise ValueError("seconds must be a positive integer")
    result = PicoClient(
        pico_serial,
        lock_dir=lock_dir,
        serial_factory=serial_factory,
        port_finder=port_finder,
    ).command(f"p {pin} {seconds}", timeout=timeout)
    if result.message.get("type") == "error":
        raise PicoCommandError(str(result.message.get("content", "Pico rejected command")))
    return result.message
