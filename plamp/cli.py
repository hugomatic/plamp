from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, TextIO

from plamp.cad_cli import add_cad_parser, run_cad_command
from plamp.cad_generation import generate_plan, list_runs, load_job_log, load_run
from plamp.config import ConfigError, controller_pico_serial, load_config, save_config
from plamp.context import resolve_context

REPO_ROOT = Path(__file__).resolve().parents[1]


def _non_negative_finite_timeout(value: str) -> float:
    timeout = float(value)
    if not math.isfinite(timeout) or timeout < 0:
        raise argparse.ArgumentTypeError("timeout must be finite and non-negative")
    return timeout


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="plamp")
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
    add_cad_parser(areas)
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
    controllers = areas.add_parser("controllers")
    controller_actions = controllers.add_subparsers(dest="action", required=True)
    controller_actions.add_parser("candidates")
    add = controller_actions.add_parser("add")
    add.add_argument("controller")
    add.add_argument("--serial", required=True)
    add.add_argument("--profile", choices=("plamp8",), required=True)
    add.add_argument("--apply", action="store_true")
    add.add_argument("--provision", action="store_true")
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
    stdin: TextIO = sys.stdin,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
    report_func: Callable[..., dict[str, Any]] | None = None,
    pulse_func: Callable[..., dict[str, Any]] | None = None,
    camera_capture_func: Callable[..., dict[str, Any]] | None = None,
    configure_func: Callable[..., dict[str, Any]] | None = None,
    upgrade_func: Callable[..., dict[str, Any]] | None = None,
    add_controller_func: Callable[..., dict[str, Any]] | None = None,
    discover_picos_func: Callable[[], list[Any]] | None = None,
    cad_generate_func: Callable[..., Any] = generate_plan,
    cad_list_runs_func: Callable[..., Any] = list_runs,
    cad_load_run_func: Callable[..., Any] = load_run,
    cad_load_log_func: Callable[..., Any] = load_job_log,
) -> int:
    raw_argv = sys.argv[1:] if argv is None else argv
    args = build_parser().parse_args(raw_argv)
    context = resolve_context(env=env)
    if args.area == "cad":
        return run_cad_command(
            args,
            context,
            stdin,
            stdout,
            stderr,
            {
                "generate": cad_generate_func,
                "list_runs": cad_list_runs_func,
                "load_run": cad_load_run_func,
                "load_job_log": cad_load_log_func,
            },
        )
    from plamp.camera import CameraError, capture_camera
    from plamp.controller_add import add_controller
    from plamp.locks import LockTimeout
    from plamp.pico_commands import configure_scheduler, upgrade_scheduler
    from plamp.pico_discovery import discover_picos
    from plamp.pico_transport import (
        PicoCommandError,
        PicoFlashError,
        PicoReportTimeout,
        PicoUnavailable,
        pulse_gpio,
        request_report,
    )
    from plamp.scheduler_state import normalize_scheduler_state

    report_func = report_func or request_report
    pulse_func = pulse_func or pulse_gpio
    camera_capture_func = camera_capture_func or capture_camera
    configure_func = configure_func or configure_scheduler
    upgrade_func = upgrade_func or upgrade_scheduler
    add_controller_func = add_controller_func or add_controller
    discover_picos_func = discover_picos_func or discover_picos
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
        elif args.area == "controllers":
            if args.action == "candidates":
                result = [
                    {"serial": candidate.serial, "device": candidate.device}
                    for candidate in discover_picos_func()
                ]
            else:
                if args.provision and not args.apply:
                    raise ConfigError("--provision requires --apply")
                result = add_controller_func(
                    args.controller,
                    args.serial,
                    args.profile,
                    apply=args.apply,
                    allow_provision=args.provision,
                    config_file=context.config_file,
                    data_dir=context.data_dir,
                    repo_root=context.root,
                    lock_dir=lock_dir,
                    timeout=args.timeout,
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
