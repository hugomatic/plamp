from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
import subprocess
import sys
from typing import TextIO

if __package__ in {None, ""}:
    repo_root = str(Path(__file__).resolve().parents[1])
    if sys.path:
        sys.path[0] = repo_root
    else:
        sys.path.insert(0, repo_root)

from plamp_cli.http import ApiError, NetworkError, build_base_url, download_bytes, request_json
from plamp_cli.io import InputError, format_json_output, load_json_input, render_table, write_binary_output

_CONFIG_SECTIONS = ("controllers", "devices", "cameras")


def _usage_hint(argv: Sequence[str]) -> str | None:
    args = list(argv)
    if not args:
        return None

    if args[:2] == ["pico-scheduler", "get"]:
        return "Example: plamp pico-scheduler get pump_n_lights\n"

    if args and args[0] == "pico-scheduler":
        return (
            "Example: plamp pico-scheduler get pump_n_lights\n"
            "Try: plamp pico-scheduler list\n"
        )

    return None


def _format_api_error(exc: ApiError) -> str:
    if exc.status == 404 and (
        exc.detail.startswith("unknown timer role:") or exc.detail.startswith("unknown controller:")
    ):
        controller = exc.detail.split(":", 1)[1].strip()
        return (
            f"API 404: unknown pico-scheduler controller: {controller}\n"
            "Try: plamp pico-scheduler list\n"
            "Example: plamp pico-scheduler get pump_n_lights\n"
        )
    return f"{exc}\n"


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

    controllers = subparsers.add_parser("controllers")
    controller_subparsers = controllers.add_subparsers(dest="controllers_action", required=True)
    controllers_list = controller_subparsers.add_parser("list")
    controllers_list.set_defaults(controllers_action="list")
    controllers_get = controller_subparsers.add_parser("get")
    controllers_get.add_argument("controller")
    controllers_get.set_defaults(controllers_action="get")
    controllers_set = controller_subparsers.add_parser("set")
    controllers_set.add_argument("controller")
    controllers_set.add_argument("payload")
    controllers_set.set_defaults(controllers_action="set")

    pico_scheduler = subparsers.add_parser("pico-scheduler")
    pico_scheduler.set_defaults(area="pico-scheduler")
    pico_scheduler_subparsers = pico_scheduler.add_subparsers(dest="timer_action", required=True)

    timer_list = pico_scheduler_subparsers.add_parser("list")
    timer_list.set_defaults(timer_action="list")

    timer_get = pico_scheduler_subparsers.add_parser("get")
    timer_get.add_argument("controller")
    timer_get.set_defaults(timer_action="get")

    timer_set = pico_scheduler_subparsers.add_parser("set")
    timer_set.add_argument("controller")
    timer_set.add_argument("payload")
    timer_set.set_defaults(timer_action="set")

    timer_channels = pico_scheduler_subparsers.add_parser("channels")
    channel_subparsers = timer_channels.add_subparsers(dest="channel_action", required=True)

    schedule = channel_subparsers.add_parser("set-schedule")
    schedule.add_argument("controller")
    schedule.add_argument("channel_id")
    schedule.add_argument("payload")
    schedule.set_defaults(timer_action="channels", channel_action="set-schedule")

    pics = subparsers.add_parser("pics")
    pic_subparsers = pics.add_subparsers(dest="pics_action", required=True)

    pic_list = pic_subparsers.add_parser("list")
    pic_list.add_argument("--source", default="all")
    pic_list.add_argument("--grow-id")
    pic_list.add_argument("--limit", type=int, default=24)
    pic_list.add_argument("--offset", type=int, default=0)
    pic_list.set_defaults(pics_action="list")

    pic_take = pic_subparsers.add_parser("take")
    pic_take.add_argument("--camera-id")
    pic_take.set_defaults(pics_action="take")

    pic_get = pic_subparsers.add_parser("get")
    pic_get.add_argument("image_key")
    pic_get.add_argument("--out")
    pic_get.add_argument("--stdout", action="store_true")
    pic_get.set_defaults(pics_action="get")

    firmware = subparsers.add_parser("firmware")
    firmware_subparsers = firmware.add_subparsers(dest="firmware_action", required=True)
    firmware_families = firmware_subparsers.add_parser("families")
    firmware_families.set_defaults(firmware_action="families")

    firmware_generate = firmware_subparsers.add_parser("generate")
    firmware_generate.add_argument("--firmware", required=True)
    firmware_generate.add_argument("--controller")
    firmware_generate.add_argument("payload")
    firmware_generate.add_argument("--out")
    firmware_generate.set_defaults(firmware_action="generate")

    firmware_flash = firmware_subparsers.add_parser("flash")
    firmware_flash.add_argument("--firmware", required=True)
    firmware_flash.add_argument("--controller")
    firmware_flash.add_argument("payload")
    firmware_flash.add_argument("--port", required=True)
    firmware_flash.set_defaults(firmware_action="flash")

    firmware_pull = firmware_subparsers.add_parser("pull")
    firmware_pull.add_argument("--port", required=True)
    firmware_pull.add_argument("--out")
    firmware_pull.set_defaults(firmware_action="pull")

    firmware_show = firmware_subparsers.add_parser("show")
    firmware_show.add_argument("--port", required=True)
    firmware_show.set_defaults(firmware_action="show")

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


def _handle_controllers(args: argparse.Namespace, base_url: str) -> object:
    if args.controllers_action == "list":
        return request_json("GET", base_url, "/api/controllers")
    if args.controllers_action == "get":
        return request_json("GET", base_url, f"/api/controllers/{args.controller}")
    if args.controllers_action == "set":
        payload = load_json_input(args.payload)
        return request_json("PUT", base_url, f"/api/controllers/{args.controller}", payload)

    raise ValueError(f"unsupported controllers action: {args.controllers_action}")


def _normalize_pico_scheduler_list(response: object) -> object:
    if not isinstance(response, dict):
        return response
    controllers = response.get("controllers")
    names: list[str] = []
    if isinstance(controllers, dict):
        names = [
            str(controller_id)
            for controller_id, item in controllers.items()
            if isinstance(item, dict) and item.get("firmware") == "pico_scheduler"
        ]
    return {"ids": names}


def _normalize_pico_scheduler_response(response: object) -> object:
    if not isinstance(response, dict):
        return response

    normalized = dict(response)
    if "role" in normalized:
        normalized["controller"] = normalized.pop("role")
    return normalized


def _handle_timers(args: argparse.Namespace, base_url: str) -> object:
    if args.timer_action == "list":
        return _normalize_pico_scheduler_list(request_json("GET", base_url, "/api/controllers"))

    if args.timer_action == "get":
        return request_json("GET", base_url, f"/api/controllers/{args.controller}")

    if args.timer_action == "set":
        payload = load_json_input(args.payload)
        response = request_json("PUT", base_url, f"/api/controllers/{args.controller}", payload)
        return _normalize_pico_scheduler_response(response)

    if args.timer_action == "channels" and args.channel_action == "set-schedule":
        payload = load_json_input(args.payload)
        response = request_json(
            "POST",
            base_url,
            f"/api/timers/{args.controller}/channels/{args.channel_id}/schedule",
            payload,
        )
        return _normalize_pico_scheduler_response(response)

    raise ValueError(f"unsupported timers action: {args.timer_action}")


def _run_command(args: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return proc.returncode, proc.stdout, proc.stderr


def _generate_firmware_source(firmware: str, payload: object, controller: str | None) -> str:
    if firmware == "pico_scheduler":
        from pico_scheduler.generator import GeneratorOptions, generate_main_py

        if not controller:
            raise ValueError("--controller is required for pico_scheduler")
        if not isinstance(payload, dict):
            raise ValueError("pico_scheduler payload must be a JSON object")
        return generate_main_py(
            controller_id=controller,
            state=payload,
            git_version="local-cli",
            generated_at="local-cli",
            options=GeneratorOptions(),
        )
    if firmware == "pico_doser":
        from pico_doser.generator import generate_main_py as generate_doser_main_py

        if not isinstance(payload, dict):
            raise ValueError("pico_doser payload must be a JSON object")
        return generate_doser_main_py(payload)
    raise ValueError(f"unsupported firmware family: {firmware}")


def _handle_firmware(args: argparse.Namespace, stderr: TextIO) -> object | bytes | None:
    if args.firmware_action == "families":
        return {"families": ["pico_scheduler", "pico_doser"]}

    if args.firmware_action == "generate":
        payload = load_json_input(args.payload)
        source = _generate_firmware_source(args.firmware, payload, args.controller)
        if args.out:
            Path(args.out).write_text(source, encoding="utf-8")
            return {"success": True, "out": args.out, "bytes": len(source.encode("utf-8"))}
        return source.encode("utf-8")

    if args.firmware_action == "flash":
        payload = load_json_input(args.payload)
        source = _generate_firmware_source(args.firmware, payload, args.controller)
        with subprocess.Popen(["mktemp"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as proc:
            out, err = proc.communicate()
        if proc.returncode != 0:
            raise ValueError(err.strip() or "failed to allocate temporary file")
        temp_path = Path(out.strip())
        try:
            temp_path.write_text(source, encoding="utf-8")
            rc, stdout, cmd_stderr = _run_command(
                ["mpremote", "connect", args.port, "resume", "cp", str(temp_path), ":main.py"]
            )
            if rc != 0:
                raise ValueError(cmd_stderr.strip() or stdout.strip() or "mpremote copy failed")
            rc, stdout, cmd_stderr = _run_command(["mpremote", "connect", args.port, "reset"])
            if rc != 0:
                raise ValueError(cmd_stderr.strip() or stdout.strip() or "mpremote reset failed")
            return {"success": True, "port": args.port}
        finally:
            try:
                temp_path.unlink()
            except OSError:
                pass

    if args.firmware_action in {"pull", "show"}:
        rc, stdout, cmd_stderr = _run_command(["mpremote", "connect", args.port, "resume", "cat", "main.py"])
        if rc != 0:
            raise ValueError(cmd_stderr.strip() or stdout.strip() or "unable to read firmware from Pico")
        if args.firmware_action == "show":
            return stdout.encode("utf-8")
        if args.out:
            Path(args.out).write_text(stdout, encoding="utf-8")
            return {"success": True, "out": args.out, "bytes": len(stdout.encode("utf-8"))}
        return stdout.encode("utf-8")

    raise ValueError(f"unsupported firmware action: {args.firmware_action}")


def _handle_pics(args: argparse.Namespace, base_url: str) -> object | bytes:
    if args.pics_action == "list":
        query = {"source": args.source, "limit": args.limit, "offset": args.offset}
        if args.grow_id:
            query["grow_id"] = args.grow_id
        return request_json("GET", base_url, "/api/camera/captures", query=query)

    if args.pics_action == "take":
        query = {"camera_id": args.camera_id} if args.camera_id else None
        return request_json("POST", base_url, "/api/camera/captures", query=query)

    if args.pics_action == "get":
        if not args.stdout and not args.out:
            raise ValueError("pics get requires --stdout or --out")
        return download_bytes(base_url, f"/api/camera/images/{args.image_key}")

    raise ValueError(f"unsupported pics action: {args.pics_action}")


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
        if exc.code and stderr is not None:
            hint = _usage_hint(argv)
            if hint:
                stderr.write(hint)
        return int(exc.code)

    try:
        base_url = build_base_url(args.host, args.port, args.base_url)

        if args.area == "config":
            result = _handle_config(args, base_url)
            if result is not None:
                stdout.write(_format_config_output(result, table=args.table, pretty=args.pretty))
        elif args.area == "controllers":
            result = _handle_controllers(args, base_url)
            if result is not None:
                stdout.write(_format_config_output(result, table=args.table, pretty=args.pretty))
        elif args.area == "pico-scheduler":
            result = _handle_timers(args, base_url)
            if result is not None:
                stdout.write(_format_config_output(result, table=args.table, pretty=args.pretty))
        elif args.area == "pics":
            result = _handle_pics(args, base_url)
            if args.pics_action == "get":
                stdout_buffer = stdout.buffer if hasattr(stdout, "buffer") else stdout
                write_binary_output(result, args.out, stdout_buffer)
            elif result is not None:
                stdout.write(_format_config_output(result, table=args.table, pretty=args.pretty))
        elif args.area == "firmware":
            result = _handle_firmware(args, stderr)
            if args.firmware_action in {"generate", "pull", "show"} and isinstance(result, bytes):
                stdout_buffer = stdout.buffer if hasattr(stdout, "buffer") else stdout
                write_binary_output(result, None, stdout_buffer)
            elif result is not None:
                stdout.write(_format_config_output(result, table=args.table, pretty=args.pretty))
        else:
            raise ValueError(f"unsupported area: {args.area}")
    except InputError as exc:
        stderr.write(f"{exc}\n")
        return 5
    except ApiError as exc:
        stderr.write(_format_api_error(exc))
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


if __name__ == "__main__":
    raise SystemExit(run())
