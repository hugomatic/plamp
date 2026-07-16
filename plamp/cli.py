from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, TextIO

from plamp.camera import CameraError, capture_camera
from plamp.config import ConfigError, controller_pico_serial
from plamp.locks import LockTimeout
from plamp.pico_transport import PicoCommandError, PicoReportTimeout, PicoUnavailable, pulse_gpio, request_report

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
            "wait budget in seconds (bounds hardware lock and Pico response waits; "
            "synchronous camera/OS calls cannot be forcibly interrupted)"
        ),
    )
    areas = parser.add_subparsers(dest="area", required=True)
    pico = areas.add_parser("pico")
    actions = pico.add_subparsers(dest="action", required=True)
    report = actions.add_parser("report")
    report.add_argument("controller")
    pulse = actions.add_parser("pulse")
    pulse.add_argument("controller")
    pulse.add_argument("pin", type=int)
    pulse.add_argument("seconds", type=int)
    camera = areas.add_parser("camera")
    camera_actions = camera.add_subparsers(dest="action", required=True)
    capture = camera_actions.add_parser("capture")
    capture.add_argument("camera_id")
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
    report_func: Callable[..., dict[str, Any]] = request_report,
    pulse_func: Callable[..., dict[str, Any]] = pulse_gpio,
    camera_capture_func: Callable[..., dict[str, Any]] = capture_camera,
) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.area == "camera":
            result = camera_capture_func(
                args.camera_id,
                lock_dir=args.lock_dir,
                timeout=args.timeout,
                repo_root=args.config.parent.parent,
                data_dir=args.config.parent,
                config_file=args.config,
                capture_kind="manual",
            )
        else:
            pico_serial = controller_pico_serial(args.config, args.controller)
            if args.action == "report":
                result = report_func(pico_serial, lock_dir=args.lock_dir, timeout=args.timeout)
            else:
                result = pulse_func(
                    pico_serial,
                    args.pin,
                    args.seconds,
                    lock_dir=args.lock_dir,
                    timeout=args.timeout,
                )
    except ConfigError as exc:
        stderr.write(f"{exc}\n")
        return 2
    except (CameraError, PicoCommandError, PicoUnavailable, PicoReportTimeout, LockTimeout, ConnectionError, OSError, ValueError) as exc:
        stderr.write(f"{exc}\n")
        return 4
    stdout.write(json.dumps(result, sort_keys=True) + "\n")
    return 0
