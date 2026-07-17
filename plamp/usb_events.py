from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

import pyudev


@dataclass(frozen=True)
class UsbSerialEvent:
    action: str
    serial: str
    port: str | None


def usb_serial_event(action: str, properties: Mapping[str, Any]) -> UsbSerialEvent | None:
    serial_number = str(properties.get("ID_SERIAL_SHORT") or "").strip()
    if action not in {"add", "remove"} or not serial_number:
        return None
    port = str(properties.get("DEVNAME") or "").strip() or None
    return UsbSerialEvent(action=action, serial=serial_number, port=port)


def start_usb_serial_observer(
    callback: Callable[[UsbSerialEvent], None],
    *,
    context_factory: Callable[[], Any] = pyudev.Context,
    monitor_factory: Callable[[Any], Any] = pyudev.Monitor.from_netlink,
    observer_factory: Callable[..., Any] = pyudev.MonitorObserver,
) -> Any:
    context = context_factory()
    monitor = monitor_factory(context)
    monitor.filter_by(subsystem="tty")

    def handle(action: str, device: Any) -> None:
        properties = getattr(device, "properties", device)
        event = usb_serial_event(action, properties)
        if event is not None:
            callback(event)

    observer = observer_factory(monitor, callback=handle, name="plamp-usb-monitor")
    observer.start()
    return observer
