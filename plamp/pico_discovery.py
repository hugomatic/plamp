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


def discover_picos(
    *, comports: Callable[[], Iterable[Any]] = list_ports.comports
) -> list[PicoPort]:
    found = []
    for port in comports():
        serial = getattr(port, "serial_number", None)
        if getattr(port, "vid", None) != RASPBERRY_PI_USB_VENDOR_ID or not serial:
            continue
        found.append(PicoPort(serial=str(serial), device=str(port.device)))
    return sorted(found, key=lambda item: item.device)


def find_pico_port(
    pico_serial: str,
    *,
    comports: Callable[[], Iterable[Any]] = list_ports.comports,
) -> str | None:
    for pico in discover_picos(comports=comports):
        if pico.serial == pico_serial:
            return pico.device
    return None
