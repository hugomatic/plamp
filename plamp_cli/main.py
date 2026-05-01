from __future__ import annotations

import argparse
from collections.abc import Sequence
import sys
from typing import TextIO

from plamp_cli.http import ApiError, NetworkError, build_base_url, request_json
from plamp_cli.io import InputError, format_json_output, load_json_input, render_table

_CONFIG_SECTIONS = ("controllers", "devices", "cameras")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="plamp")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--base-url")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--table", action="store_true")
    subparsers = parser.add_subparsers(dest="area", required=True)

    config = subparsers.add_parser("config")
    config_subparsers = config.add_subparsers(dest="command", required=True)

    config_get = config_subparsers.add_parser("get")
    config_get.set_defaults(action="get", section=None)

    config_set = config_subparsers.add_parser("set")
    config_set.add_argument("payload")
    config_set.set_defaults(action="set", section=None)

    for section_name in _CONFIG_SECTIONS:
        section = config_subparsers.add_parser(section_name)
        section_subparsers = section.add_subparsers(dest="section_action", required=True)

        section_get = section_subparsers.add_parser("get")
        section_get.set_defaults(action="get", section=section_name)

        section_set = section_subparsers.add_parser("set")
        section_set.add_argument("payload")
        section_set.set_defaults(action="set", section=section_name)

    timers = subparsers.add_parser("timers")
    timer_subparsers = timers.add_subparsers(dest="timer_action", required=True)

    timer_list = timer_subparsers.add_parser("list")
    timer_list.set_defaults(timer_action="list")

    timer_get = timer_subparsers.add_parser("get")
    timer_get.add_argument("role")
    timer_get.set_defaults(timer_action="get")

    timer_set = timer_subparsers.add_parser("set")
    timer_set.add_argument("role")
    timer_set.add_argument("payload")
    timer_set.set_defaults(timer_action="set")

    timer_channels = timer_subparsers.add_parser("channels")
    channel_subparsers = timer_channels.add_subparsers(dest="channel_action", required=True)

    schedule = channel_subparsers.add_parser("set-schedule")
    schedule.add_argument("role")
    schedule.add_argument("channel_id")
    schedule.add_argument("payload")
    schedule.set_defaults(timer_action="channels", channel_action="set-schedule")

    return parser


def _handle_config(args: argparse.Namespace, base_url: str) -> object:
    if args.action == "get":
        response = request_json("GET", base_url, "/api/config")
        if args.section is None:
            return response
        return response["config"][args.section]

    if args.action == "set":
        payload = load_json_input(args.payload)
        path = "/api/config" if args.section is None else f"/api/config/{args.section}"
        return request_json("PUT", base_url, path, payload)

    raise ValueError(f"unsupported config action: {args.action}")


def _handle_timers(args: argparse.Namespace, base_url: str) -> object:
    if args.timer_action == "list":
        return request_json("GET", base_url, "/api/timer-config")

    if args.timer_action == "get":
        return request_json("GET", base_url, f"/api/timers/{args.role}")

    if args.timer_action == "set":
        payload = load_json_input(args.payload)
        return request_json("PUT", base_url, f"/api/timers/{args.role}", payload)

    if args.timer_action == "channels" and args.channel_action == "set-schedule":
        payload = load_json_input(args.payload)
        return request_json(
            "POST",
            base_url,
            f"/api/timers/{args.role}/channels/{args.channel_id}/schedule",
            payload,
        )

    raise ValueError(f"unsupported timers action: {args.timer_action}")


def _format_config_output(value: object, table: bool, pretty: bool) -> str:
    if not table:
        return format_json_output(value, pretty=pretty)

    if isinstance(value, list):
        if all(isinstance(item, dict) for item in value):
            return render_table([dict(item) for item in value])
        return format_json_output(value, pretty=pretty)

    if isinstance(value, dict):
        if not value:
            return render_table([])

        if all(isinstance(item, dict) for item in value.values()) and all(
            all(not isinstance(nested, (dict, list)) for nested in item.values())
            for item in value.values()
        ):
            rows = []
            for key, item in value.items():
                row = {"id": key}
                row.update(item)
                rows.append(row)
            return render_table(rows)

        if any(isinstance(item, (dict, list)) for item in value.values()):
            return format_json_output(value, pretty=pretty)

        rows = [{"key": key, "value": value[key]} for key in value]
        return render_table(rows)

    return format_json_output(value, pretty=pretty)


def main(
    argv: Sequence[str],
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    parser = build_parser()
    try:
        args = parser.parse_args(list(argv))
    except SystemExit as exc:
        return int(exc.code)

    try:
        base_url = build_base_url(args.host, args.port, args.base_url)

        if args.area == "config":
            result = _handle_config(args, base_url)
            if result is not None:
                stdout.write(_format_config_output(result, table=args.table, pretty=args.pretty))
        elif args.area == "timers":
            result = _handle_timers(args, base_url)
            if result is not None:
                stdout.write(format_json_output(result, pretty=args.pretty))
        else:
            raise ValueError(f"unsupported area: {args.area}")
    except InputError as exc:
        stderr.write(f"{exc}\n")
        return 5
    except ApiError as exc:
        stderr.write(f"{exc}\n")
        return 3
    except NetworkError as exc:
        stderr.write(f"{exc}\n")
        return 4
    except ValueError as exc:
        stderr.write(f"{exc}\n")
        return 2

    return 0


def run() -> int:
    return main(sys.argv[1:])
