from __future__ import annotations

import argparse
from collections.abc import Sequence
import sys

from plamp_cli.http import build_base_url, request_json
from plamp_cli.io import format_json_output, load_json_input

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


def main(argv: Sequence[str]) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(list(argv))
    except SystemExit as exc:
        return int(exc.code)

    base_url = build_base_url(args.host, args.port, args.base_url)

    if args.area == "config":
        result = _handle_config(args, base_url)
        if result is not None:
            sys.stdout.write(format_json_output(result, pretty=args.pretty))
    else:
        raise ValueError(f"unsupported area: {args.area}")

    return 0


def run() -> int:
    return main(sys.argv[1:])
