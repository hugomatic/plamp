from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from plamp.pico_transport import (
    PicoClient,
    PicoCommandError,
    PicoExchange,
    PicoOperation,
)
from plamp.scheduler_state import FirmwareIdentity, firmware_identity


@dataclass(frozen=True)
class SchedulerApplyResult:
    report: dict[str, Any]
    port: str
    upgraded: bool
    previous_identity: FirmwareIdentity | None
    identity: FirmwareIdentity
    raw_lines: tuple[bytes, ...]


def apply_scheduler_state(
    *,
    client: PicoClient,
    current_state: dict[str, Any],
    proposed_state: dict[str, Any],
    expected: FirmwareIdentity,
    upgrade: Callable[
        [PicoOperation, dict[str, Any], FirmwareIdentity], PicoExchange
    ],
    timeout: float,
) -> SchedulerApplyResult:
    with client.operation(timeout=timeout) as operation:
        before = operation.report()
        raw_lines = list(before.raw_lines)
        previous = firmware_identity(before.message)
        upgraded = previous != expected
        if upgraded:
            active = upgrade(operation, current_state, expected)
            raw_lines.extend(active.raw_lines)
        else:
            active = before
        if firmware_identity(active.message) != expected:
            raise PicoCommandError(
                "Pico firmware identity does not match expected firmware"
            )

        configured = operation.configure(proposed_state)
        raw_lines.extend(configured.raw_lines)
        identity = firmware_identity(configured.message)
        if identity != expected:
            raise PicoCommandError("Pico firmware changed during configuration")

        return SchedulerApplyResult(
            report=configured.message,
            port=configured.port,
            upgraded=upgraded,
            previous_identity=previous,
            identity=identity,
            raw_lines=tuple(raw_lines),
        )
