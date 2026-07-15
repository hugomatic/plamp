from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import serial

from plamp.locks import LockTimeout, exclusive_lock
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
    return f"pico-{safe}.lock"


def request_report(
    pico_serial: str,
    *,
    lock_dir: Path,
    timeout: float = 3.0,
    serial_factory: Callable[..., Any] = serial.Serial,
    port_finder: Callable[[str], str | None] = find_pico_port,
) -> dict[str, Any]:
    deadline = time.monotonic() + max(timeout, 0.0)
    lock_timeout = max(deadline - time.monotonic(), 0.0)
    with exclusive_lock(lock_dir / _lock_name(pico_serial), timeout=lock_timeout):
        port = port_finder(pico_serial)
        if port is None:
            raise PicoUnavailable(f"configured Pico is not connected: {pico_serial}")
        conn = serial_factory(port, baudrate=115200, timeout=0.05, exclusive=True)
        raw_lines = []
        try:
            conn.reset_input_buffer()
            conn.write(b"r\n")
            conn.flush()
            while True:
                raw = conn.readline()
                if raw:
                    raw_lines.append(raw)
                    LOGGER.debug(
                        "pico raw serial=%s len=%d newline=%s repr=%r",
                        pico_serial,
                        len(raw),
                        raw.endswith(b"\n"),
                        raw,
                    )
                    try:
                        return decode_report_line(raw)
                    except PicoProtocolError:
                        LOGGER.warning(
                            "ignored invalid Pico line serial=%s repr=%r",
                            pico_serial,
                            raw,
                        )
                if time.monotonic() >= deadline:
                    raise PicoReportTimeout(
                        f"timed out waiting for report from {pico_serial}", raw_lines
                    )
        finally:
            conn.close()
