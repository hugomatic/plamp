from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, TextIO

from plamp.camera import CameraError, capture_camera
from plamp.config import ConfigError, controller_pico_serial, load_config, save_config
from plamp.context import resolve_context
from plamp.locks import LockTimeout
from plamp.pico_commands import configure_scheduler, upgrade_scheduler
from plamp.pico_transport import PicoCommandError, PicoFlashError, PicoReportTimeout, PicoUnavailable, pulse_gpio, request_report
from plamp.scheduler_state import normalize_scheduler_state

REPO_ROOT = Path(__file__).resolve().parents[1]


def _non_negative_finite_timeout(value: str) -> float:
    timeout = float(value)
    if not math.isfinite(timeout) or timeout < 0:
        raise argparse.ArgumentTypeError("timeout must be finite and non-negative")
    return timeout


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m plamp")
    parser.add_argument("--lock-dir", type=Path)
    parser.add_argument(
        "--timeout",
        type=_non_negative_finite_timeout,
        default=3.0,
        help=(
            "wait budget in seconds (bounds hardware lock and Pico response waits; "
            "synchronous camera/OS calls cannot be forcibly interrupted)"
        ),
    )
    areas = parser.add_subparsers(dest="area", required=True)
    areas.add_parser("context")
    config = areas.add_parser("config")
    config_actions = config.add_subparsers(dest="action", required=True)
    config_actions.add_parser("get")
    config_write = config_actions.add_parser("write")
    config_write.add_argument("file")
    pico = areas.add_parser("pico")
    actions = pico.add_subparsers(dest="action", required=True)
    report = actions.add_parser("report")
    report.add_argument("controller")
    pulse = actions.add_parser("pulse")
    pulse.add_argument("controller")
    pulse.add_argument("pin", type=int)
    pulse.add_argument("seconds", type=int)
    configure = actions.add_parser("configure")
    configure.add_argument("controller")
    configure.add_argument("state_file")
    upgrade = actions.add_parser("upgrade")
    upgrade.add_argument("controller")
    upgrade.add_argument("state_file")
    camera = areas.add_parser("camera")
    camera_actions = camera.add_subparsers(dest="action", required=True)
    capture = camera_actions.add_parser("capture")
    capture.add_argument("camera_id")
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
    stdin: TextIO = sys.stdin,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
    report_func: Callable[..., dict[str, Any]] = request_report,
    pulse_func: Callable[..., dict[str, Any]] = pulse_gpio,
    camera_capture_func: Callable[..., dict[str, Any]] = capture_camera,
    configure_func: Callable[..., dict[str, Any]] = configure_scheduler,
    upgrade_func: Callable[..., dict[str, Any]] = upgrade_scheduler,
) -> int:
    args = build_parser().parse_args(argv)
    context = resolve_context(env=env)
    lock_dir = args.lock_dir or context.lock_dir
    try:
        if args.area == "context":
            revision = "unknown"
            try:
                revision = subprocess.check_output(
                    ["git", "rev-parse", "--short", "HEAD"],
                    cwd=context.root,
                    text=True,
                    stderr=subprocess.DEVNULL,
                ).strip()
            except (OSError, subprocess.SubprocessError):
                pass
            result = {
                "config_file": str(context.config_file),
                "data_dir": str(context.data_dir),
                "revision": revision,
                "root": str(context.root),
            }
        elif args.area == "config":
            if args.action == "get":
                result = load_config(context.config_file)
            else:
                try:
                    raw = stdin.read() if args.file == "-" else Path(args.file).read_text(encoding="utf-8")
                    submitted = json.loads(raw)
                except (OSError, json.JSONDecodeError) as exc:
                    raise ConfigError(f"cannot read submitted configuration: {exc}") from exc
                result = save_config(context.config_file, submitted)
        elif args.area == "camera":
            result = camera_capture_func(
                args.camera_id,
                lock_dir=lock_dir,
                timeout=args.timeout,
                repo_root=context.root,
                data_dir=context.data_dir,
                config_file=context.config_file,
                capture_kind="manual",
            )
        else:
            state = None
            if args.action in {"configure", "upgrade"}:
                try:
                    raw = stdin.read() if args.state_file == "-" else Path(args.state_file).read_text(encoding="utf-8")
                    state = normalize_scheduler_state(json.loads(raw))
                except (OSError, json.JSONDecodeError, ValueError) as exc:
                    raise ConfigError(f"cannot read submitted scheduler state: {exc}") from exc
            pico_serial = controller_pico_serial(context.config_file, args.controller)
            if args.action == "report":
                result = report_func(pico_serial, lock_dir=lock_dir, timeout=args.timeout)
            elif args.action == "pulse":
                result = pulse_func(
                    pico_serial,
                    args.pin,
                    args.seconds,
                    lock_dir=lock_dir,
                    timeout=args.timeout,
                )
            else:
                operation = configure_func if args.action == "configure" else upgrade_func
                result = operation(
                    pico_serial,
                    state,
                    lock_dir=lock_dir,
                    timeout=args.timeout,
                    repo_root=context.root,
                    data_dir=context.data_dir,
                )
    except ConfigError as exc:
        stderr.write(f"{exc}\n")
        return 2
    except (CameraError, PicoCommandError, PicoFlashError, PicoUnavailable, PicoReportTimeout, LockTimeout, ConnectionError, OSError, ValueError) as exc:
        stderr.write(f"{exc}\n")
        return 4
    stdout.write(json.dumps(result, sort_keys=True) + "\n")
    return 0
