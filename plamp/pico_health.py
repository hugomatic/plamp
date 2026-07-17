from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import serial

from plamp.locks import LockTimeout
from plamp.pico_transport import PicoClient, PicoReportTimeout, PicoUnavailable


@dataclass(frozen=True)
class PicoHealthError:
    kind: str
    step: str
    message: str
    raw_lines: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "step": self.step,
            "message": self.message,
            "raw_lines": list(self.raw_lines),
        }


@dataclass(frozen=True)
class PicoHealth:
    ok: bool
    status: str
    checked_at: str
    serial: str
    port: str | None
    report: dict[str, Any] | None
    raw_lines: tuple[str, ...]
    error: PicoHealthError | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "checked_at": self.checked_at,
            "serial": self.serial,
            "port": self.port,
            "report": self.report,
            "raw_lines": list(self.raw_lines),
            "error": self.error.as_dict() if self.error else None,
        }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _text_lines(raw_lines: tuple[bytes, ...] | list[bytes]) -> tuple[str, ...]:
    return tuple(raw.decode("utf-8", errors="replace").strip() for raw in raw_lines)


def failed_health(
    serial_number: str,
    *,
    kind: str,
    step: str,
    message: str,
    port: str | None = None,
    raw_lines: tuple[str, ...] = (),
) -> PicoHealth:
    return PicoHealth(
        ok=False,
        status="ERROR",
        checked_at=_now(),
        serial=serial_number,
        port=port,
        report=None,
        raw_lines=raw_lines,
        error=PicoHealthError(kind=kind, step=step, message=message, raw_lines=raw_lines),
    )


def probe_pico(client: PicoClient, *, timeout: float = 3.0) -> PicoHealth:
    try:
        exchange = client.report(timeout=timeout)
    except PicoUnavailable as exc:
        return failed_health(client.pico_serial, kind="unavailable", step="discover", message=str(exc))
    except PicoReportTimeout as exc:
        raw_lines = _text_lines(exc.raw_lines)
        kind = "protocol" if raw_lines else "timeout"
        return failed_health(
            client.pico_serial,
            kind=kind,
            step="report",
            message=str(exc),
            raw_lines=raw_lines,
        )
    except LockTimeout:
        raise
    except (OSError, serial.SerialException) as exc:
        return failed_health(client.pico_serial, kind="serial", step="report", message=str(exc))

    raw_lines = _text_lines(exchange.raw_lines)
    return PicoHealth(
        ok=True,
        status="OK",
        checked_at=_now(),
        serial=client.pico_serial,
        port=exchange.port,
        report=exchange.message,
        raw_lines=raw_lines,
        error=None,
    )
