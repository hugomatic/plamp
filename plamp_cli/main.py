from __future__ import annotations

import argparse
from collections.abc import Sequence
import sys
from typing import TextIO

from plamp_cli.http import ApiError, NetworkError, build_base_url, request_json
from plamp_cli.io import InputError, format_json_output, load_json_input

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
        if args.area == "config" and args.table:
            raise ValueError("--table is not supported for config commands")

        base_url = build_base_url(args.host, args.port, args.base_url)

        if args.area == "config":
            result = _handle_config(args, base_url)
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
