from __future__ import annotations

import argparse
from collections.abc import Sequence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="plamp")
    subparsers = parser.add_subparsers(dest="area", required=True)

    config = subparsers.add_parser("config")
    config_subparsers = config.add_subparsers(dest="action", required=True)
    config_subparsers.add_parser("get")

    return parser


def main(argv: Sequence[str]) -> int:
    parser = build_parser()
    try:
        parser.parse_args(list(argv))
    except SystemExit as exc:
        return int(exc.code)
    return 0


def run() -> int:
    import sys

    return main(sys.argv[1:])
