from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import time
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any

import serial

from plamp.pico_firmware import render_scheduler_firmware
from plamp.pico_transport import (
    PicoClient,
    PicoCommandError,
    PicoExchange,
    PicoFlashError,
)
from plamp.scheduler_state import (
    EXPECTED_FIRMWARE_PROTOCOL,
    FirmwareIdentity,
    firmware_identity,
    normalize_scheduler_state,
)


def run_mpremote(
    args: list[str], timeout: float
) -> tuple[int | None, str, str]:
    try:
        completed = subprocess.run(
            args,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        return None, "", "command not found"
    except subprocess.TimeoutExpired:
        return None, "", "command timed out"
    return completed.returncode, completed.stdout.strip(), completed.stderr.strip()


def interrupt_pico_program(port: str, attempts: int = 3) -> None:
    connection = None
    try:
        connection = serial.serial_for_url(
            port,
            do_not_open=True,
            baudrate=115200,
            timeout=0.2,
            write_timeout=0.2,
            exclusive=True,
        )
        connection.dtr = False
        connection.rts = False
        connection.open()
        for _ in range(attempts):
            connection.write(b"\r\x03")
            connection.flush()
            time.sleep(0.1)
            try:
                connection.read(connection.in_waiting or 1)
            except (OSError, serial.SerialException):
                break
    except (OSError, serial.SerialException):
        # mpremote can still interrupt a running program itself; this is best effort.
        pass
    finally:
        if connection is not None:
            try:
                connection.close()
            except (OSError, serial.SerialException):
                pass


def configure_scheduler(
    pico_serial: str,
    state: dict[str, Any],
    *,
    lock_dir: Path,
    timeout: float,
    repo_root: Path,
    data_dir: Path,
    client_factory: Callable[..., PicoClient] = PicoClient,
) -> dict[str, Any]:
    del repo_root, data_dir
    normalized = normalize_scheduler_state(state)
    return client_factory(pico_serial, lock_dir=lock_dir).configure(
        normalized, timeout=timeout
    ).message


def _report_identity(
    exchange: PicoExchange, *, label: str, required: bool
) -> FirmwareIdentity | None:
    try:
        identity = firmware_identity(exchange.message)
    except (TypeError, ValueError) as exc:
        raise PicoCommandError(
            f"invalid firmware identity in {label} Pico report: {exc}",
            raw_lines=exchange.raw_lines,
        ) from exc
    if identity is None:
        if required:
            raise PicoCommandError(
                f"{label} Pico report has no firmware identity",
                raw_lines=exchange.raw_lines,
            )
        return None
    if not isinstance(identity, FirmwareIdentity):
        raise PicoCommandError(
            f"invalid firmware identity in {label} Pico report",
            raw_lines=exchange.raw_lines,
        )
    return identity


def upgrade_scheduler(
    pico_serial: str,
    state: dict[str, Any],
    *,
    lock_dir: Path,
    timeout: float,
    repo_root: Path,
    data_dir: Path,
    client_factory: Callable[..., PicoClient] = PicoClient,
    render_func: Callable[[Path], tuple[str, str]] = render_scheduler_firmware,
    mpremote_finder: Callable[[str], str | None] = shutil.which,
    command_runner: Callable[[list[str], float], tuple[int | None, str, str]] = run_mpremote,
    interrupter: Callable[[str], None] = interrupt_pico_program,
) -> dict[str, Any]:
    normalized = normalize_scheduler_state(state)
    revision, firmware_source = render_func(repo_root)
    expected = FirmwareIdentity(
        "pico_scheduler", revision, EXPECTED_FIRMWARE_PROTOCOL
    )
    if revision == "unknown":
        raise PicoFlashError("prepare", None, "", "firmware revision is unknown")
    mpremote = mpremote_finder("mpremote")
    if not mpremote:
        raise PicoFlashError("prepare", None, "", "mpremote not found")

    data_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=data_dir, prefix=".pico-upgrade-") as staging:
        staging_path = Path(staging)
        firmware_path = staging_path / "main.py"
        state_path = staging_path / "state.json"
        firmware_path.write_text(firmware_source, encoding="utf-8")
        state_path.write_text(
            json.dumps(normalized, separators=(",", ":")), encoding="utf-8"
        )

        client = client_factory(pico_serial, lock_dir=lock_dir)
        with client.operation(timeout=timeout) as operation:
            before = operation.report()
            previous = _report_identity(before, label="initial", required=False)
            upgraded = operation.upgrade_scheduler(
                firmware_path,
                state_path,
                expected,
                command_runner=command_runner,
                interrupter=interrupter,
                mpremote=mpremote,
            )

    identity = _report_identity(upgraded, label="upgraded", required=True)
    return {
        "identity": asdict(identity),
        "port": upgraded.port,
        "previous_identity": None if previous is None else asdict(previous),
        "report": upgraded.message,
    }
