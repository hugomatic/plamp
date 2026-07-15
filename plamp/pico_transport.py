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
    """Request one report using ``timeout`` as an enforced operation budget.

    The remaining budget is checked around synchronous discovery, open, reset, and
    flush operations and is supplied to lock, serial read, and serial write waits.
    Synchronous OS and driver calls cannot be preempted, so this is not a hard interrupt
    guarantee for those calls.
    """
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
