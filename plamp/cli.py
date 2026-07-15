from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, TextIO

from plamp.config import ConfigError, controller_pico_serial
from plamp.locks import LockTimeout
from plamp.pico_transport import PicoReportTimeout, PicoUnavailable, request_report

REPO_ROOT = Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m plamp")
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "data" / "config.json")
    parser.add_argument("--lock-dir", type=Path, default=REPO_ROOT / "data" / "locks")
    parser.add_argument("--timeout", type=float, default=3.0)
    areas = parser.add_subparsers(dest="area", required=True)
    pico = areas.add_parser("pico")
    actions = pico.add_subparsers(dest="action", required=True)
    report = actions.add_parser("report")
    report.add_argument("controller")
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
    report_func: Callable[..., dict[str, Any]] = request_report,
) -> int:
    args = build_parser().parse_args(argv)
    try:
        pico_serial = controller_pico_serial(args.config, args.controller)
        report = report_func(pico_serial, lock_dir=args.lock_dir, timeout=args.timeout)
    except ConfigError as exc:
        stderr.write(f"{exc}\n")
        return 2
    except (PicoUnavailable, PicoReportTimeout, LockTimeout, ConnectionError, OSError) as exc:
        stderr.write(f"{exc}\n")
        return 4
    stdout.write(json.dumps(report, sort_keys=True) + "\n")
    return 0
