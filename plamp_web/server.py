from __future__ import annotations

import glob
import getpass
import grp
import json
import logging
import logging.handlers
import os
import platform
import queue
import re
import shutil
import socket
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
import time as pytime
from pathlib import Path
from typing import Any

import serial
from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pico_scheduler.generator import GeneratorOptions, generate_main_py
from plamp_web import camera_capture, hardware_inventory
from plamp_web.pages import render_api_test_page, render_settings_page, render_system_info_page, render_timer_dashboard_page
from plamp_web.hardware_config import (
    apply_config_section,
    config_view,
    empty_config,
    scheduler_controller_ids,
    scheduler_devices_for_controller,
)
from plamp_web.timer_schedule import channel_metadata_for_role, patch_channel_schedule


REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = Path(__file__).resolve().parent / "static"
HOSTS_FILE = Path("/etc/hosts")
DATA_DIR = REPO_ROOT / "data"
CONFIG_FILE = DATA_DIR / "config.json"
TIMERS_DIR = DATA_DIR / "timers"
PICO_GENERATOR_FILE = REPO_ROOT / "pico_scheduler" / "generator.py"
PICO_TEMPLATES_DIR = REPO_ROOT / "pico_scheduler" / "templates"
LOG_FILE = DATA_DIR / "plamp.log"
PICO_NAME_HINTS = ("pico", "rp2", "raspberry", "micropython")
RASPBERRY_PI_USB_VENDOR_ID = "2e8a"
ROLE_RE = re.compile(r"^[A-Za-z0-9_-]+$")
HOSTNAME_RE = re.compile(
    r"^(?=.{1,63}$)[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?$"
)
LOGGER = logging.getLogger("plamp_web")

config_lock = threading.Lock()
role_locks: dict[str, threading.Lock] = {}
monitors_lock = threading.Lock()
monitors: dict[str, "PicoMonitor"] = {}
camera_worker_lock = threading.Lock()
camera_worker: "CameraWorker | None" = None

app = FastAPI(title="plamp web")


@app.on_event("startup")
def startup() -> None:
    ensure_data_dir()
    configure_logging()
    start_configured_monitors()
    get_or_start_camera_worker()


@app.get("/favicon.svg")
def favicon_svg() -> FileResponse:
    return FileResponse(STATIC_DIR / "favicon.svg", media_type="image/svg+xml")


@app.on_event("shutdown")
def shutdown() -> None:
    stop_camera_worker()
    stop_monitors()


def lock_for(mapping: dict[str, threading.Lock], key: str) -> threading.Lock:
    with config_lock:
        lock = mapping.get(key)
        if lock is None:
            lock = threading.Lock()
            mapping[key] = lock
        return lock


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    TIMERS_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_FILE.exists():
        atomic_write_json(CONFIG_FILE, empty_config())


def configure_logging() -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    for handler in root.handlers:
        if getattr(handler, "baseFilename", None) == str(LOG_FILE):
            return
    handler = logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3)
    handler.setFormatter(formatter)
    root.addHandler(handler)
    root.setLevel(logging.INFO)


def read_log_tail(max_lines: int = 200) -> str:
    if not LOG_FILE.exists():
        return ""
    lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[-max_lines:]) + ("\n" if lines else "")


def run_plampctl_action(*args: str) -> dict[str, Any]:
    completed = subprocess.run(
        [str(REPO_ROOT / "plampctl"), *args],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    output = (completed.stdout or completed.stderr or "").strip()
    if completed.returncode != 0:
        raise HTTPException(status_code=500, detail=output or f"plampctl {' '.join(args)} failed")
    return {"message": output or f"{args[0]} complete"}


def load_json_file(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"missing file: {path.name}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"invalid JSON in {path.name}: {exc}") from exc


def atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def load_raw_config() -> dict[str, Any]:
    ensure_data_dir()
    data = load_json_file(CONFIG_FILE)
    if not isinstance(data, dict):
        raise HTTPException(status_code=500, detail="config.json must be an object")
    for section in ("controllers", "cameras"):
        value = data.get(section, {})
        if not isinstance(value, dict):
            raise HTTPException(status_code=500, detail=f"config.json {section} must be an object")
    return data


def load_config() -> dict[str, Any]:
    data = load_raw_config()
    result = {section: data.get(section, {}) for section in ("controllers", "cameras")}
    try:
        return config_view(result)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def normalize_camera_key(value: Any) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", str(value or "").strip())


def normalized_detected_cameras(cameras: Any) -> list[dict[str, Any]]:
    if not isinstance(cameras, list):
        return []
    result = []
    for item in cameras:
        if not isinstance(item, dict):
            continue
        normalized = dict(item)
        key = normalize_camera_key(item.get("key"))
        if key:
            normalized["key"] = key
        result.append(normalized)
    return result


def timer_roles() -> dict[str, dict[str, Any]]:
    config = load_config()
    controllers = config.get("controllers", {})
    if not isinstance(controllers, dict):
        raise HTTPException(status_code=500, detail="config controllers must be an object")
    scheduler_ids = scheduler_controller_ids(controllers)
    return {role: controllers[role] for role in controllers if role in scheduler_ids}


def controllers_index() -> dict[str, dict[str, Any]]:
    config = load_config()
    controllers = config.get("controllers", {})
    if not isinstance(controllers, dict):
        raise HTTPException(status_code=500, detail="config controllers must be an object")
    normalized: dict[str, dict[str, Any]] = {}
    for controller_id, controller_data in controllers.items():
        if not isinstance(controller_id, str) or not ROLE_RE.match(controller_id):
            raise HTTPException(status_code=500, detail=f"invalid controller id: {controller_id}")
        if not isinstance(controller_data, dict):
            raise HTTPException(status_code=500, detail=f"controller {controller_id} must be an object")
        normalized[controller_id] = controller_data
    return normalized


def configured_monitor_serials() -> dict[str, str]:
    result: dict[str, str] = {}
    for role, item in timer_roles().items():
        if not isinstance(role, str) or not ROLE_RE.match(role):
            raise HTTPException(status_code=500, detail=f"invalid controller role: {role}")
        if not isinstance(item, dict):
            raise HTTPException(status_code=500, detail=f"controller {role} must be an object")
        serial = item.get("payload", {}).get("pico_serial")
        if isinstance(serial, str) and serial:
            result[role] = serial
    return result


def role_for_serial(serial: str | None) -> str | None:
    if not serial:
        return None
    try:
        for role, configured_serial in configured_monitor_serials().items():
            if configured_serial == serial:
                return role
    except HTTPException:
        return None
    return None


def timer_role(role: str) -> dict[str, Any]:
    roles = timer_roles()
    item = roles.get(role)
    if item is None:
        raise HTTPException(status_code=404, detail=f"unknown timer role: {role}")
    return item


def controller_item(controller: str) -> dict[str, Any]:
    item = controllers_index().get(controller)
    if item is None:
        raise HTTPException(status_code=404, detail=f"unknown controller: {controller}")
    return item


def pico_serial_for_role(role: str) -> str:
    serial = timer_role(role).get("payload", {}).get("pico_serial")
    if not isinstance(serial, str) or not serial:
        raise HTTPException(status_code=409, detail=f"timer role {role} has no configured pico_serial")
    return serial


def timer_state_path(role: str) -> Path:
    timer_role(role)
    ensure_data_dir()
    return TIMERS_DIR / f"{role}.json"


def controller_state_path(controller: str) -> Path:
    controller_item(controller)
    ensure_data_dir()
    return TIMERS_DIR / f"{controller}.json"


def require_int(value: Any, message: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail=message)


def timer_state_items_key(state: Any) -> str | None:
    if not isinstance(state, dict):
        return None
    if isinstance(state.get("devices"), list):
        return "devices"
    if isinstance(state.get("events"), list):
        return "events"
    return None


def timer_state_items(state: Any) -> list[dict[str, Any]] | None:
    key = timer_state_items_key(state)
    if key is None or not isinstance(state, dict):
        return None
    items = state.get(key)
    return items if isinstance(items, list) else None


def timer_state_as_events(state: Any) -> dict[str, Any]:
    if not isinstance(state, dict):
        return {}
    items = timer_state_items(state)
    if items is None:
        return dict(state)
    converted = dict(state)
    converted["events"] = [dict(item) if isinstance(item, dict) else item for item in items]
    converted.pop("devices", None)
    return converted


def validate_timer_state(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise HTTPException(status_code=422, detail="top-level JSON must be an object")
    if "report_every" not in raw:
        raise HTTPException(status_code=422, detail="missing top-level field: report_every")

    report_every = require_int(raw["report_every"], "report_every must be an integer")
    if report_every <= 0:
        raise HTTPException(status_code=422, detail="report_every must be > 0")

    if "devices" in raw:
        raw_items = raw["devices"]
        if not isinstance(raw_items, list):
            raise HTTPException(status_code=422, detail="devices must be a list")
    elif "events" in raw:
        raw_items = raw["events"]
        if not isinstance(raw_items, list):
            raise HTTPException(status_code=422, detail="events must be a list")
    else:
        raise HTTPException(status_code=422, detail="missing top-level field: devices")

    devices = []
    for i, src in enumerate(raw_items):
        if not isinstance(src, dict):
            raise HTTPException(status_code=422, detail=f"device {i} must be an object")
        for name in ["type", "pin", "current_t", "reschedule", "pattern"]:
            if name not in src:
                raise HTTPException(status_code=422, detail=f"device {i} missing field: {name}")

        event_type = src["type"]
        if event_type not in {"gpio", "pwm"}:
            raise HTTPException(status_code=422, detail=f"device {i} type must be gpio or pwm")
        pin = require_int(src["pin"], f"device {i} pin must be an integer")
        current_t = require_int(src["current_t"], f"device {i} current_t must be an integer")
        reschedule = 1 if require_int(src["reschedule"], f"device {i} reschedule must be an integer") else 0
        if pin < 0 or pin > 29:
            raise HTTPException(status_code=422, detail=f"device {i} pin must be in range 0..29")
        if current_t < 0:
            raise HTTPException(status_code=422, detail=f"device {i} current_t must be >= 0")

        pattern_src = src["pattern"]
        if not isinstance(pattern_src, list) or not pattern_src:
            raise HTTPException(status_code=422, detail=f"device {i} pattern must be a non-empty list")

        pattern = []
        total_t = 0
        for j, step in enumerate(pattern_src):
            if not isinstance(step, dict):
                raise HTTPException(status_code=422, detail=f"device {i} pattern step {j} must be an object")
            if "val" not in step or "dur" not in step:
                raise HTTPException(status_code=422, detail=f"device {i} pattern step {j} missing val or dur")
            val = require_int(step["val"], f"device {i} pattern step {j} val must be an integer")
            dur = require_int(step["dur"], f"device {i} pattern step {j} dur must be an integer")
            if dur <= 0:
                raise HTTPException(status_code=422, detail=f"device {i} pattern step {j} dur must be > 0")
            if event_type == "gpio" and val not in {0, 1}:
                raise HTTPException(status_code=422, detail=f"device {i} pattern step {j} gpio val must be 0 or 1")
            if event_type == "pwm" and (val < 0 or val > 65535):
                raise HTTPException(status_code=422, detail=f"device {i} pattern step {j} pwm val must be in range 0..65535")
            pattern.append({"val": val, "dur": dur})
            total_t += dur

        if not reschedule and current_t > total_t:
            current_t = total_t

        device = {
            "type": event_type,
            "pin": pin,
            "current_t": current_t,
            "reschedule": reschedule,
            "pattern": pattern,
        }
        if "id" in src:
            if not isinstance(src["id"], str) or not src["id"]:
                raise HTTPException(status_code=422, detail=f"device {i} id must be a non-empty string")
            device["id"] = src["id"]
        devices.append(device)

    return {"report_every": report_every, "devices": devices}


def timer_state_for_pico(role: str, raw_state: Any) -> dict[str, Any]:
    state = validate_timer_state(raw_state)
    role_config = timer_role(role)
    report_every = require_int(role_config.get("payload", {}).get("report_every", 10), "report_every must be an integer")
    if report_every <= 0:
        raise HTTPException(status_code=422, detail="report_every must be > 0")
    disabled = disabled_timer_device_keys(role)
    devices = [
        device
        for device in state["devices"]
        if (device.get("id"), int(device.get("pin"))) not in disabled
        and (None, int(device.get("pin"))) not in disabled
    ]
    return {"report_every": report_every, "devices": devices}


def disabled_timer_device_keys(role: str) -> set[tuple[str | None, int]]:
    disabled: set[tuple[str | None, int]] = set()
    config = load_config()
    devices = scheduler_devices_for_controller(config, role)
    for device_id, device in devices.items():
        if not isinstance(device_id, str) or not isinstance(device, dict):
            continue
        if device.get("programming") != "disabled" and device.get("visibility") != "hidden":
            continue
        try:
            pin = int(device.get("pin"))
        except (TypeError, ValueError):
            continue
        disabled.add((device_id, pin))
        disabled.add((None, pin))
    return disabled


def empty_timer_state() -> dict[str, Any]:
    return {"report_every": 1, "devices": []}


def load_timer_state_for_schedule_edit(path: Path) -> dict[str, Any]:
    try:
        return validate_timer_state(load_json_file(path))
    except HTTPException as exc:
        if exc.status_code in {404, 422, 500}:
            return empty_timer_state()
        raise


def pico_for_role(role: str) -> dict[str, Any]:
    serial = pico_serial_for_role(role)
    for pico in enumerate_picos():
        if pico.get("serial") == serial:
            return pico
    raise HTTPException(status_code=409, detail=f"Pico for role {role} is not connected: {serial}")


def total_duration(pattern: Any) -> int | None:
    if not isinstance(pattern, list) or not pattern:
        return None
    total = 0
    for step in pattern:
        if not isinstance(step, dict):
            return None
        try:
            duration = int(step["dur"])
        except (KeyError, TypeError, ValueError):
            return None
        if duration <= 0:
            return None
        total += duration
    return total


def event_elapsed_t(event: dict[str, Any]) -> int | None:
    raw = event.get("elapsed_t")
    if raw is None:
        raw = event.get("current_t")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def event_cycle_t(event: dict[str, Any]) -> int | None:
    elapsed_t = event_elapsed_t(event)
    if elapsed_t is None:
        return None
    total = total_duration(event.get("pattern"))
    if total is None:
        return None
    try:
        reschedule = int(event.get("reschedule", 1))
    except (TypeError, ValueError):
        reschedule = 1
    return elapsed_t % total if reschedule else min(elapsed_t, total)


def current_value_for_event(event: dict[str, Any]) -> int | None:
    pattern = event.get("pattern")
    cycle_t = event_cycle_t(event)
    if cycle_t is None or not isinstance(pattern, list):
        return None
    elapsed = 0
    fallback: int | None = None
    for step in pattern:
        if not isinstance(step, dict):
            return None
        try:
            value = int(step["val"])
            duration = int(step["dur"])
        except (KeyError, TypeError, ValueError):
            return None
        fallback = value
        elapsed += duration
        if cycle_t < elapsed:
            return value
    return fallback


def reduce_report(report: Any) -> dict[str, Any]:
    if not isinstance(report, dict):
        return {"kind": "unknown", "raw": report}
    reduced = dict(report)
    if "type" not in reduced and isinstance(reduced.get("kind"), str):
        reduced["type"] = reduced["kind"]
    reduced.pop("kind", None)
    content = reduced.get("content")
    if not isinstance(content, dict):
        return reduced
    items = content.get("devices")
    if not isinstance(items, list):
        items = content.get("events")
    if not isinstance(items, list):
        return reduced
    reduced_items = []
    pins: dict[str, dict[str, Any]] = {}
    for index, event in enumerate(items):
        if not isinstance(event, dict):
            reduced_items.append(event)
            continue
        item = dict(event)
        old_pin_key = "c" + "h"
        if "pin" not in item and old_pin_key in item:
            item["pin"] = item.pop(old_pin_key)
        elif old_pin_key in item:
            item.pop(old_pin_key)
        if "elapsed_t" not in item:
            elapsed_t = event_elapsed_t(item)
            if elapsed_t is not None:
                item["elapsed_t"] = elapsed_t
        if "cycle_t" not in item:
            cycle_t = event_cycle_t(item)
            if cycle_t is not None:
                item["cycle_t"] = cycle_t
        if "current_value" not in item:
            value = current_value_for_event(item)
            if value is not None:
                item["current_value"] = value
        event_id = str(item.get("id") or item.get("pin") or index)
        pins[event_id] = {
            "id": item.get("id"),
            "type": item.get("type"),
            "pin": item.get("pin"),
            "elapsed_t": item.get("elapsed_t"),
            "cycle_t": item.get("cycle_t"),
            "current_value": item.get("current_value"),
        }
        reduced_items.append(item)
    reduced["content"] = dict(content)
    reduced["content"]["devices"] = reduced_items
    reduced["content"].pop("events", None)
    reduced["pins"] = pins
    return reduced


def state_with_current_values(state: dict[str, Any]) -> dict[str, Any]:
    items = state.get("devices")
    if not isinstance(items, list):
        return state
    enriched = dict(state)
    enriched_items = []
    for event in items:
        if not isinstance(event, dict):
            enriched_items.append(event)
            continue
        item = dict(event)
        if "elapsed_t" not in item:
            elapsed_t = event_elapsed_t(item)
            if elapsed_t is not None:
                item["elapsed_t"] = elapsed_t
        if "cycle_t" not in item:
            cycle_t = event_cycle_t(item)
            if cycle_t is not None:
                item["cycle_t"] = cycle_t
        if "current_value" not in item:
            value = current_value_for_event(item)
            if value is not None:
                item["current_value"] = value
        enriched_items.append(item)
    enriched["devices"] = enriched_items
    enriched.pop("events", None)
    return enriched


def latest_timer_state(role: str) -> dict[str, Any] | None:
    snapshot = get_or_start_monitor(role).snapshot()
    report = snapshot.get("last_report")
    if not isinstance(report, dict):
        return None
    reduced = reduce_report(report)
    content = reduced.get("content")
    if not isinstance(content, dict):
        return None
    items = content.get("devices")
    if not isinstance(items, list):
        return None
    normalized_items = []
    for item in items:
        if not isinstance(item, dict):
            normalized_items.append(item)
            continue
        normalized = dict(item)
        if "current_t" not in normalized:
            elapsed_t = event_elapsed_t(normalized)
            if elapsed_t is not None:
                normalized["current_t"] = elapsed_t
        normalized_items.append(normalized)
    state: dict[str, Any] = {"devices": normalized_items}
    if "report_every" in content:
        state["report_every"] = content["report_every"]
    else:
        try:
            state["report_every"] = load_json_file(timer_state_path(role))["report_every"]
        except (HTTPException, KeyError, TypeError):
            pass
    return state


@dataclass
class ApplyCommand:
    path: Path
    done: threading.Event = field(default_factory=threading.Event)
    result: dict[str, Any] | None = None
    error_status: int | None = None
    error_detail: Any = None


@dataclass
class CameraCommand:
    camera_id: str | None
    capture_kind: str
    done: threading.Event = field(default_factory=threading.Event)
    result: dict[str, Any] | None = None
    error: camera_capture.CameraCaptureError | None = None


class CameraWorker:
    def __init__(self, capture_func: Any | None = None):
        self.capture_func = capture_func or camera_capture.capture_camera_image
        self.commands: queue.Queue[CameraCommand] = queue.Queue()
        self.stop_event = threading.Event()
        self.wake_event = threading.Event()
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self.run, name="camera-worker", daemon=True)
        self.schedule_seconds: dict[str, int] = {}
        self.next_due_at: dict[str, float] = {}
        self.pending_auto: set[str] = set()
        self.status: dict[str, Any] = {
            "state": "starting",
            "available": True,
            "last_capture_at": None,
            "last_error": None,
            "queue_depth": 0,
            "scheduled_cameras": [],
        }

    def start(self) -> None:
        self.refresh_schedule(now=time.monotonic())
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        self.wake_event.set()

    def join(self, timeout: float = 2.0) -> None:
        self.thread.join(timeout=timeout)

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            snapshot = dict(self.status)
            snapshot["scheduled_cameras"] = list(self.status.get("scheduled_cameras", []))
            return snapshot

    def update_status(self, **changes: Any) -> None:
        with self.lock:
            self.status.update(changes)
            self.status["queue_depth"] = self.commands.qsize()
            self.status["scheduled_cameras"] = sorted(self.schedule_seconds)
            self.status["updated_at"] = datetime.now().isoformat(timespec="seconds")

    def refresh_schedule(self, cameras: dict[str, Any] | None = None, *, now: float | None = None) -> None:
        now_value = time.monotonic() if now is None else now
        if cameras is None:
            config = load_config()
            cameras = config.get("cameras", {}) if isinstance(config.get("cameras", {}), dict) else {}
        next_schedule_seconds: dict[str, int] = {}
        next_due_at: dict[str, float] = {}
        for camera_id, item in sorted(cameras.items()):
            if not isinstance(camera_id, str) or not isinstance(item, dict):
                continue
            every_seconds = item.get("capture_every_seconds")
            if not isinstance(every_seconds, int) or every_seconds <= 0:
                continue
            next_schedule_seconds[camera_id] = every_seconds
            next_due_at[camera_id] = self.next_due_at.get(camera_id, now_value)
        self.schedule_seconds = next_schedule_seconds
        self.next_due_at = next_due_at
        self.pending_auto.intersection_update(self.schedule_seconds)
        self.update_status()

    def collect_due_camera_ids(self, *, now: float | None = None) -> list[str]:
        now_value = time.monotonic() if now is None else now
        due = [
            camera_id
            for camera_id in sorted(self.schedule_seconds)
            if self.next_due_at.get(camera_id, now_value + 1) <= now_value and camera_id not in self.pending_auto
        ]
        return due

    def mark_capture_complete(self, *, camera_id: str | None, capture_kind: str, now: float | None = None) -> None:
        now_value = time.monotonic() if now is None else now
        if capture_kind == "auto" and camera_id and camera_id in self.schedule_seconds:
            self.next_due_at[camera_id] = now_value + self.schedule_seconds[camera_id]
            self.pending_auto.discard(camera_id)
        self.update_status(last_capture_at=datetime.now().isoformat(timespec="seconds"), last_error=None)

    def mark_capture_failure(self, *, camera_id: str | None, capture_kind: str, error: str) -> None:
        if capture_kind == "auto" and camera_id:
            self.pending_auto.discard(camera_id)
        self.update_status(last_error=error, available=False)

    def enqueue_due_captures(self, *, now: float | None = None) -> None:
        for camera_id in self.collect_due_camera_ids(now=now):
            self.pending_auto.add(camera_id)
            self.commands.put(CameraCommand(camera_id=camera_id, capture_kind="auto"))
        self.update_status()

    def capture(self, *, camera_id: str | None, capture_kind: str) -> dict[str, Any]:
        command = CameraCommand(camera_id=camera_id, capture_kind=capture_kind)
        self.commands.put(command)
        self.update_status()
        self.wake_event.set()
        if not command.done.wait(timeout=60.0):
            raise HTTPException(status_code=504, detail="timed out waiting for camera capture")
        if command.error is not None:
            raise HTTPException(status_code=command.error.status_code, detail=str(command.error))
        if command.result is None:
            raise HTTPException(status_code=500, detail="camera capture finished without a result")
        return command.result

    def run(self) -> None:
        self.update_status(state="idle", available=True)
        while not self.stop_event.is_set():
            self.refresh_schedule()
            self.enqueue_due_captures()
            try:
                command = self.commands.get(timeout=1.0)
            except queue.Empty:
                continue
            self.update_status(state="capturing", available=True)
            try:
                result = self.capture_func(
                    repo_root=camera_capture.REPO_ROOT,
                    data_dir=camera_capture.DATA_DIR,
                    config_file=camera_capture.CONFIG_FILE,
                    camera_id=command.camera_id,
                    capture_kind=command.capture_kind,
                )
            except camera_capture.CameraCaptureError as exc:
                command.error = exc
                self.mark_capture_failure(camera_id=command.camera_id, capture_kind=command.capture_kind, error=str(exc))
            else:
                command.result = result
                self.mark_capture_complete(camera_id=command.camera_id, capture_kind=command.capture_kind)
            finally:
                command.done.set()
                self.update_status(state="idle")
        self.update_status(state="stopped")


def get_or_start_camera_worker() -> CameraWorker:
    global camera_worker
    with camera_worker_lock:
        if camera_worker is None:
            camera_worker = CameraWorker()
            camera_worker.start()
        return camera_worker


def camera_worker_summary() -> dict[str, Any]:
    with camera_worker_lock:
        if camera_worker is None:
            return {
                "state": "stopped",
                "available": True,
                "last_capture_at": None,
                "last_error": None,
                "queue_depth": 0,
                "scheduled_cameras": [],
            }
        return camera_worker.snapshot()


def reconcile_camera_worker() -> None:
    with camera_worker_lock:
        active = camera_worker
    if active is not None:
        active.refresh_schedule()


def stop_camera_worker() -> None:
    global camera_worker
    with camera_worker_lock:
        active = camera_worker
        camera_worker = None
    if active is not None:
        active.stop()
        active.join()


class PicoMonitor:
    def __init__(self, role: str, pico_serial: str):
        self.role = role
        self.pico_serial = pico_serial
        self.commands: queue.Queue[ApplyCommand] = queue.Queue()
        self.subscribers: set[queue.Queue[dict[str, Any]]] = set()
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.wake_event = threading.Event()
        self.thread = threading.Thread(target=self.run, name=f"pico-monitor-{role}", daemon=True)
        self.summary: dict[str, Any] = {
            "role": role,
            "serial": pico_serial,
            "state": "starting",
            "connected": False,
            "port": None,
            "last_seen": None,
            "last_error": None,
            "last_report": None,
        }

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        self.wake_event.set()

    def join(self, timeout: float = 2.0) -> None:
        self.thread.join(timeout=timeout)

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return dict(self.summary)

    def subscribe(self) -> queue.Queue[dict[str, Any]]:
        subscriber: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=100)
        with self.lock:
            self.subscribers.add(subscriber)
        return subscriber

    def unsubscribe(self, subscriber: queue.Queue[dict[str, Any]]) -> None:
        with self.lock:
            self.subscribers.discard(subscriber)

    def publish(self, event: str, data: dict[str, Any]) -> None:
        payload = {"event": event, "data": data}
        with self.lock:
            subscribers = list(self.subscribers)
        for subscriber in subscribers:
            try:
                subscriber.put_nowait(payload)
            except queue.Full:
                try:
                    subscriber.get_nowait()
                except queue.Empty:
                    pass
                try:
                    subscriber.put_nowait(payload)
                except queue.Full:
                    pass

    def update_status(self, state: str, *, connected: bool | None = None, port: str | None = None, error: Any = None) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        changed = False
        with self.lock:
            if self.summary.get("state") != state:
                self.summary["state"] = state
                changed = True
            if connected is not None and self.summary.get("connected") != connected:
                self.summary["connected"] = connected
                changed = True
            if port is not None and self.summary.get("port") != port:
                self.summary["port"] = port
                changed = True
            if error != self.summary.get("last_error"):
                self.summary["last_error"] = error
                changed = True
            self.summary["updated_at"] = now
            snapshot = dict(self.summary)
        if changed:
            LOGGER.info(
                "pico monitor %s state=%s connected=%s port=%s error=%s",
                self.role,
                snapshot.get("state"),
                snapshot.get("connected"),
                snapshot.get("port"),
                snapshot.get("last_error"),
            )
            self.publish("status", snapshot)

    def find_port(self) -> str | None:
        for pico in enumerate_picos():
            if pico.get("serial") == self.pico_serial:
                return str(pico["port"])
        return None

    def open_serial(self) -> serial.Serial | None:
        port = self.find_port()
        if not port:
            self.update_status("disconnected", connected=False, error="configured Pico is not connected")
            return None
        try:
            conn = serial.Serial(port, baudrate=115200, timeout=0.5)
        except (OSError, serial.SerialException) as exc:
            self.update_status("disconnected", connected=False, port=port, error=str(exc))
            return None
        self.update_status("connected", connected=True, port=port, error=None)
        self.publish("snapshot", self.snapshot())
        return conn

    def close_serial(self, conn: serial.Serial | None) -> None:
        if conn is None:
            return
        try:
            conn.close()
        except (OSError, serial.SerialException):
            pass

    def handle_line(self, raw: bytes) -> None:
        text = raw.decode("utf-8", errors="replace").strip()
        if not text:
            return
        now = datetime.now().isoformat(timespec="seconds")
        try:
            report = json.loads(text)
        except json.JSONDecodeError as exc:
            error = f"invalid JSON from Pico: {exc}"
            with self.lock:
                self.summary["last_seen"] = now
                self.summary["last_error"] = error
            LOGGER.warning("pico monitor %s invalid JSON: %s", self.role, text)
            self.publish("error", {"role": self.role, "serial": self.pico_serial, "message": error, "raw": text})
            return
        reduced = reduce_report(report)
        with self.lock:
            self.summary["last_seen"] = now
            self.summary["last_error"] = None
            self.summary["last_report"] = reduced
            if isinstance(reduced, dict) and "pins" in reduced:
                self.summary["pins"] = reduced["pins"]
            snapshot = dict(self.summary)
        self.publish("report", {"role": self.role, "serial": self.pico_serial, "received_at": now, "report": reduced})

    def apply(self, path: Path, timeout: float = 60.0) -> dict[str, Any]:
        command = ApplyCommand(path=path)
        self.commands.put(command)
        self.wake_event.set()
        if not command.done.wait(timeout=timeout):
            raise HTTPException(status_code=504, detail="timed out waiting for Pico apply")
        if command.error_status is not None:
            raise HTTPException(status_code=command.error_status, detail=command.error_detail)
        if command.result is None:
            raise HTTPException(status_code=500, detail="Pico apply finished without a result")
        return command.result

    def handle_apply(self, command: ApplyCommand, conn: serial.Serial | None) -> serial.Serial | None:
        self.close_serial(conn)
        self.update_status("applying", connected=False, error=None)
        port = self.find_port()
        if not port:
            command.error_status = 409
            command.error_detail = f"Pico for role {self.role} is not connected: {self.pico_serial}"
            command.done.set()
            self.update_status("disconnected", connected=False, error=command.error_detail)
            return None

        mpremote = shutil.which("mpremote")
        if not mpremote:
            command.error_status = 500
            command.error_detail = "mpremote not found"
            command.done.set()
            self.update_status("error", connected=False, port=port, error=command.error_detail)
            return None

        interrupt_pico_program(port)

        firmware_rc, firmware_out, firmware_err = run_command([mpremote, "connect", port, "resume", "cp", str(command.path), ":main.py"], timeout=30)
        if firmware_rc != 0:
            command.error_status = 502
            command.error_detail = {"step": "firmware", "returncode": firmware_rc, "stdout": firmware_out, "stderr": firmware_err}
            command.done.set()
            LOGGER.error("pico monitor %s mpremote firmware copy failed: %s", self.role, command.error_detail)
            self.publish("error", {"role": self.role, "step": "firmware", "detail": command.error_detail})
            self.update_status("error", connected=False, port=port, error=command.error_detail)
            return None

        reset_rc, reset_out, reset_err = run_command([mpremote, "connect", port, "reset"], timeout=15)
        if reset_rc != 0:
            command.error_status = 502
            command.error_detail = {"step": "reset", "returncode": reset_rc, "stdout": reset_out, "stderr": reset_err}
            command.done.set()
            LOGGER.error("pico monitor %s mpremote reset failed: %s", self.role, command.error_detail)
            self.publish("error", {"role": self.role, "step": "reset", "detail": command.error_detail})
            self.update_status("error", connected=False, port=port, error=command.error_detail)
            return None

        command.result = {"role": self.role, "port": port, "serial": self.pico_serial}
        command.done.set()
        self.publish("status", {"role": self.role, "state": "reconnecting", "port": port, "serial": self.pico_serial})
        self.update_status("reconnecting", connected=False, port=port, error=None)
        time.sleep(0.5)
        return None

    def run(self) -> None:
        conn: serial.Serial | None = None
        retry_sleep = 1.0
        while not self.stop_event.is_set():
            try:
                try:
                    command = self.commands.get_nowait()
                except queue.Empty:
                    command = None
                if command is not None:
                    conn = self.handle_apply(command, conn)
                    continue

                if conn is None or not conn.is_open:
                    conn = self.open_serial()
                    if conn is None:
                        self.wake_event.wait(retry_sleep)
                        self.wake_event.clear()
                        retry_sleep = min(retry_sleep * 2, 5.0)
                        continue
                    retry_sleep = 1.0

                try:
                    line = conn.readline()
                except (OSError, serial.SerialException) as exc:
                    port = getattr(conn, "port", None)
                    self.close_serial(conn)
                    conn = None
                    self.update_status("disconnected", connected=False, port=port, error=str(exc))
                    continue
                if line:
                    self.handle_line(line)
            except Exception as exc:
                self.update_status("error", connected=False, error=str(exc))
                self.stop_event.wait(1.0)
        self.close_serial(conn)
        self.update_status("stopped", connected=False)


def get_or_start_monitor(role: str) -> PicoMonitor:
    pico_serial = pico_serial_for_role(role)
    with monitors_lock:
        monitor = monitors.get(role)
        if monitor is None or monitor.pico_serial != pico_serial:
            if monitor is not None:
                monitor.stop()
            monitor = PicoMonitor(role, pico_serial)
            monitors[role] = monitor
            monitor.start()
        return monitor


def start_configured_monitors() -> None:
    try:
        roles = configured_monitor_serials()
    except HTTPException:
        return
    for role in roles:
        get_or_start_monitor(role)


def reconcile_configured_monitors() -> None:
    try:
        serials = configured_monitor_serials()
    except HTTPException:
        return
    stale = []
    with monitors_lock:
        for role, monitor in list(monitors.items()):
            if role not in serials or monitor.pico_serial != serials[role]:
                stale.append(monitors.pop(role))
    for monitor in stale:
        monitor.stop()
    for monitor in stale:
        monitor.join()
    for role in sorted(serials):
        get_or_start_monitor(role)


def stop_monitors() -> None:
    with monitors_lock:
        active = list(monitors.values())
        monitors.clear()
    for monitor in active:
        monitor.stop()
    for monitor in active:
        monitor.join()


def monitor_summaries() -> dict[str, dict[str, Any]]:
    with monitors_lock:
        active = dict(monitors)
    return {role: monitor.snapshot() for role, monitor in active.items()}


def rendered_pico_main(role: str, raw_state: Any) -> str:
    state = timer_state_for_pico(role, raw_state)
    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    git_version = git_output(["git", "rev-parse", "--short", "HEAD"], repo_root=REPO_ROOT) or "unknown"
    return generate_main_py(
        controller_id=role,
        state=state,
        git_version=git_version,
        generated_at=generated_at,
        options=GeneratorOptions(),
    )


def apply_timer_state(role: str, path: Path) -> dict[str, Any]:
    generated = rendered_pico_main(role, load_json_file(path))
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".py", delete=False) as temp:
        temp_path = Path(temp.name)
        temp.write(generated)
    try:
        return get_or_start_monitor(role).apply(temp_path)
    finally:
        try:
            temp_path.unlink()
        except OSError:
            pass


def sse_message(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"


def stream_status() -> StreamingResponse:
    def events():
        yield sse_message("snapshot", status_response())
        while True:
            time.sleep(15)
            yield sse_message("snapshot", status_response())

    return StreamingResponse(events(), media_type="text/event-stream")


def stream_timer_events(role: str) -> StreamingResponse:
    monitor = get_or_start_monitor(role)

    def events():
        subscriber = monitor.subscribe()
        try:
            yield sse_message("snapshot", monitor.snapshot())
            while True:
                try:
                    item = subscriber.get(timeout=15)
                except queue.Empty:
                    yield sse_message("keepalive", {"role": role})
                    continue
                yield sse_message(str(item["event"]), item["data"])
        finally:
            monitor.unsubscribe(subscriber)

    return StreamingResponse(events(), media_type="text/event-stream")


def seconds_since_midnight() -> int:
    now = datetime.now()
    return now.hour * 3600 + now.minute * 60 + now.second


def parse_hhmmss(value: str) -> int:
    try:
        parts = [int(part) for part in value.split(":")]
    except ValueError:
        raise HTTPException(status_code=422, detail=f"invalid time: {value}")
    if len(parts) != 3:
        raise HTTPException(status_code=422, detail=f"invalid time: {value}")
    hour, minute, second = parts
    if hour < 0 or hour > 23 or minute < 0 or minute > 59 or second < 0 or second > 59:
        raise HTTPException(status_code=422, detail=f"invalid time: {value}")
    return hour * 3600 + minute * 60 + second


def current_t_for_window(start: str, stop: str) -> int:
    start_s = parse_hhmmss(start)
    stop_s = parse_hhmmss(stop)
    now_s = seconds_since_midnight()
    on_dur = (stop_s - start_s) % 86400
    if on_dur == 0:
        on_dur = 86400
    off_dur = 86400 - on_dur
    if off_dur == 0:
        off_dur = 1
    return (now_s - start_s) % (on_dur + off_dur)

def run_command(args: list[str], timeout: float = 2.0) -> tuple[int | None, str, str]:
    try:
        proc = subprocess.run(
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
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def interrupt_pico_program(port: str, attempts: int = 3) -> None:
    conn = None
    try:
        conn = serial.serial_for_url(
            port,
            do_not_open=True,
            baudrate=115200,
            timeout=0.2,
            write_timeout=0.2,
            exclusive=True,
        )
        conn.dtr = False
        conn.rts = False
        conn.open()
        for _ in range(attempts):
            conn.write(b"\r\x03")
            conn.flush()
            time.sleep(0.1)
            try:
                conn.read(conn.in_waiting or 1)
            except (OSError, serial.SerialException):
                break
    except (OSError, serial.SerialException) as exc:
        LOGGER.warning("could not pre-interrupt Pico on %s before mpremote: %s", port, exc)
    finally:
        if conn is not None:
            try:
                conn.close()
            except (OSError, serial.SerialException):
                pass


def split_nmcli_line(line: str) -> list[str]:
    fields: list[str] = []
    current = []
    escaped = False
    for char in line:
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == ":":
            fields.append("".join(current))
            current = []
        else:
            current.append(char)
    fields.append("".join(current))
    return fields


def host_ips() -> list[str]:
    ips = set()
    hostname = socket.gethostname()

    try:
        for info in socket.getaddrinfo(hostname, None):
            addr = info[4][0]
            if ":" not in addr and not addr.startswith("127."):
                ips.add(addr)
    except socket.gaierror:
        pass

    rc, out, _ = run_command(["ip", "-o", "-4", "addr", "show"])
    if rc == 0:
        for line in out.splitlines():
            parts = line.split()
            if "inet" in parts:
                cidr = parts[parts.index("inet") + 1]
                addr = cidr.split("/", 1)[0]
                if not addr.startswith("127."):
                    ips.add(addr)

    return sorted(ips)


def default_route() -> dict[str, str] | None:
    rc, out, _ = run_command(["ip", "route", "show", "default"])
    if rc != 0 or not out:
        return None

    parts = out.split()
    route: dict[str, str] = {"raw": out.splitlines()[0]}
    if "via" in parts:
        route["gateway"] = parts[parts.index("via") + 1]
    if "dev" in parts:
        route["interface"] = parts[parts.index("dev") + 1]
    return route


def device_ipv4(device: str) -> str | None:
    rc, out, _ = run_command(["ip", "-o", "-4", "addr", "show", "dev", device])
    if rc != 0:
        return None
    for line in out.splitlines():
        parts = line.split()
        if "inet" in parts:
            return parts[parts.index("inet") + 1].split("/", 1)[0]
    return None


def network_summary() -> list[dict[str, Any]]:
    devices: list[dict[str, Any]] = []

    rc, out, _ = run_command(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "dev", "status"])
    if rc == 0:
        for line in out.splitlines():
            fields = split_nmcli_line(line)
            if len(fields) < 4 or fields[1] not in {"wifi", "ethernet"}:
                continue

            device = fields[0]
            kind = fields[1]
            state = fields[2]
            connection = fields[3] or None
            label = "LAN cable" if kind == "ethernet" else "WiFi"

            item: dict[str, Any] = {
                "device": device,
                "type": kind,
                "state": state,
                "ipv4": device_ipv4(device),
                "network": label,
            }
            if connection:
                item["connection"] = connection
            devices.append(item)

    if not devices:
        wireless = Path("/proc/net/wireless")
        if wireless.exists():
            for line in wireless.read_text(encoding="utf-8", errors="replace").splitlines()[2:]:
                name = line.split(":", 1)[0].strip()
                if name:
                    devices.append({"device": name, "type": "wifi", "state": "unknown", "ipv4": device_ipv4(name), "network": "WiFi"})

    for device in devices:
        if device.get("type") != "wifi":
            continue
        rc, ssid, _ = run_command(["iwgetid", "-r", str(device["device"])])
        if rc == 0 and ssid:
            device["ssid"] = ssid
            device["network"] = f"WiFi, SSID: {ssid}"

    return devices


def serial_symlinks_by_target() -> dict[str, list[dict[str, str]]]:
    by_target: dict[str, list[dict[str, str]]] = {}
    for path in glob.glob("/dev/serial/by-id/*"):
        link = Path(path)
        try:
            target = str(link.resolve())
        except OSError:
            continue
        by_target.setdefault(target, []).append({"path": path, "name": link.name})
    return by_target


def udev_properties(device_path: str) -> dict[str, str]:
    rc, out, _ = run_command(["udevadm", "info", "--query=property", "--name", device_path])
    if rc != 0:
        return {}

    props: dict[str, str] = {}
    for line in out.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        props[key] = value
    return props


def pico_role(serial: str | None, index: int) -> str:
    configured = role_for_serial(serial)
    if configured:
        return configured
    return f"pico {index + 1}"


def usb_device_label(symlinks: list[dict[str, str]], vendor: str | None, model: str | None, serial: str | None) -> str | None:
    if symlinks:
        name = symlinks[0]["name"]
        if name.startswith("usb-"):
            name = name[4:]
        if serial:
            name = name.replace(f"_{serial}", "")
        return name
    if vendor and model:
        return f"{vendor}_{model}"
    return model or vendor


def enumerate_picos() -> list[dict[str, Any]]:
    by_target = serial_symlinks_by_target()
    device_paths = set(by_target)
    device_paths.update(glob.glob("/dev/ttyACM*"))
    device_paths.update(glob.glob("/dev/ttyUSB*"))

    detected: list[dict[str, Any]] = []
    for device_path in sorted(device_paths):
        symlinks = by_target.get(device_path, [])
        props = udev_properties(device_path)
        vendor_id = props.get("ID_VENDOR_ID", "").lower()
        product_id = props.get("ID_MODEL_ID", "").lower()
        vendor = props.get("ID_VENDOR_FROM_DATABASE") or props.get("ID_VENDOR")
        model = props.get("ID_MODEL_FROM_DATABASE") or props.get("ID_MODEL")
        serial = props.get("ID_SERIAL_SHORT") or props.get("ID_SERIAL")
        names = " ".join([
            Path(device_path).name,
            vendor or "",
            model or "",
            serial or "",
            *[item["name"] for item in symlinks],
        ]).lower()

        is_pico = vendor_id == RASPBERRY_PI_USB_VENDOR_ID or any(hint in names for hint in PICO_NAME_HINTS)
        if not is_pico:
            continue

        detected.append(
            {
                "port": device_path,
                "stable_paths": [item["path"] for item in symlinks],
                "vendor_id": vendor_id or None,
                "product_id": product_id or None,
                "vendor": vendor,
                "model": model,
                "usb_device": usb_device_label(symlinks, vendor, model, serial),
                "serial": serial,
            }
        )

    for index, item in enumerate(detected):
        item["role"] = pico_role(item.get("serial"), index)

    return detected


def state_for_role(role: str) -> dict[str, Any]:
    latest = latest_timer_state(role)
    if latest is not None:
        return latest
    path = timer_state_path(role)
    state = load_json_file(path)
    return state_with_current_values(validate_timer_state(state))


def live_events_for_role(role: str) -> list[dict[str, Any]]:
    return live_devices_for_role(role)


def live_devices_for_role(role: str) -> list[dict[str, Any]]:
    latest = latest_timer_state(role)
    if not isinstance(latest, dict):
        return []
    devices = latest.get("devices")
    return devices if isinstance(devices, list) else []


def configured_timer_roles() -> list[str]:
    try:
        return list(timer_roles())
    except HTTPException:
        return []


def configured_timer_channels() -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    try:
        config = load_config()
        roles = list(timer_roles())
    except HTTPException:
        return result
    for role in roles:
        try:
            state = state_for_role(role)
        except HTTPException:
            state = None
        try:
            result[role] = channel_metadata_for_role(role, config, state)
        except ValueError:
            result[role] = []
    return result



def configured_camera_ids() -> list[str]:
    try:
        config = load_config()
    except HTTPException:
        return []
    cameras = config.get("cameras", {})
    return list(cameras) if isinstance(cameras, dict) else []

def configured_time_format() -> str:
    try:
        config = load_raw_config()
    except HTTPException:
        config = {}
    return "24h" if str(config.get("time_format", "12h")).lower() in {"24", "24h"} else "12h"


def host_time_summary() -> dict[str, Any]:
    now = datetime.now()
    seconds = now.hour * 3600 + now.minute * 60 + now.second
    if configured_time_format() == "24h":
        display = now.strftime("%H:%M")
    else:
        hour = now.hour % 12 or 12
        suffix = "AM" if now.hour < 12 else "PM"
        display = f"{hour}:{now.minute:02d} {suffix}"
    return {"iso": now.isoformat(timespec="seconds"), "seconds_since_midnight": seconds, "display": display}



def human_bytes(value: int) -> str:
    amount = float(value)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if amount < 1024 or unit == "TB":
            return f"{amount:.1f} {unit}"
        amount /= 1024
    return f"{amount:.1f} TB"


def storage_summary(path: Path = REPO_ROOT) -> dict[str, Any]:
    usage = shutil.disk_usage(path)
    return {
        "path": str(path),
        "free_bytes": usage.free,
        "used_bytes": usage.used,
        "total_bytes": usage.total,
        "free": human_bytes(usage.free),
        "used": human_bytes(usage.used),
        "total": human_bytes(usage.total),
    }


def computer_hardware_model(
    *,
    device_tree_model_path: Path = Path("/proc/device-tree/model"),
    cpuinfo_path: Path = Path("/proc/cpuinfo"),
) -> str:
    try:
        model = device_tree_model_path.read_text(errors="replace").replace("\x00", "").strip()
        if model:
            return model
    except OSError:
        pass
    try:
        for line in cpuinfo_path.read_text(errors="replace").splitlines():
            if line.lower().startswith("model name"):
                _, value = line.split(":", 1)
                model = value.strip()
                if model:
                    return model
    except OSError:
        pass
    return platform.machine() or platform.processor() or "unknown"


def git_output(args: list[str], *, repo_root: Path = REPO_ROOT) -> str | None:
    try:
        return subprocess.check_output(args, cwd=repo_root, text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def software_summary(*, repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    commit = git_output(["git", "rev-parse", "HEAD"], repo_root=repo_root)
    branch = git_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo_root=repo_root)
    commit_timestamp = git_output(["git", "show", "-s", "--format=%cI", "HEAD"], repo_root=repo_root)
    status = git_output(["git", "status", "--short"], repo_root=repo_root)
    dirty_files: list[str] = []
    if status:
        for line in status.splitlines():
            path_text = line[3:].strip() if len(line) > 3 else line.strip()
            if " -> " in path_text:
                path_text = path_text.split(" -> ", 1)[1].strip()
            if path_text:
                dirty_files.append(path_text)
    mpremote_path = shutil.which("mpremote")
    mpremote_version = None
    if mpremote_path:
        rc, out, _ = run_command([mpremote_path, "--version"], timeout=5)
        if rc == 0:
            first_line = next((line.strip() for line in out.splitlines() if line.strip()), "")
            if first_line:
                mpremote_version = first_line
    user_name = getpass.getuser()
    try:
        user_groups = sorted({grp.getgrgid(group_id).gr_name for group_id in os.getgroups()})
    except KeyError:
        user_groups = []
    user_is_sudoer = "sudo" in user_groups or "wheel" in user_groups
    user_has_serial_access = "dialout" in user_groups
    user_has_video_access = "video" in user_groups
    os_release = platform.freedesktop_os_release()
    os_name = os_release.get("NAME") or platform.system()
    os_version = os_release.get("VERSION") or os_release.get("VERSION_ID") or "unknown"
    return {
        "name": "plamp",
        "path": str(repo_root.resolve()),
        "user_name": user_name,
        "user_is_sudoer": user_is_sudoer,
        "user_has_serial_access": user_has_serial_access,
        "user_has_video_access": user_has_video_access,
        "os_name": os_name,
        "os_arch": platform.machine(),
        "os_version": os_version,
        "git_commit": commit,
        "git_short_commit": commit[:7] if commit else None,
        "git_branch": branch,
        "git_commit_timestamp": commit_timestamp,
        "git_dirty": None if status is None else bool(status),
        "git_dirty_files": dirty_files,
        "mpremote_path": mpremote_path,
        "mpremote_version": mpremote_version,
    }


def system_response() -> dict[str, Any]:
    return {
        "detected": {
            "picos": enumerate_picos(),
            "cameras": normalized_detected_cameras(hardware_inventory.detect_rpicam_cameras()),
        },
        "host_time": host_time_summary(),
        "host": {
            "hostname": socket.gethostname(),
            "hardware_model": computer_hardware_model(),
            "ips": host_ips(),
            "default_route": default_route(),
            "network": network_summary(),
        },
        "picos": enumerate_picos(),
        "tools": {
            "pyserial": getattr(serial, "VERSION", "unknown"),
        },
        "software": software_summary(),
        "paths": {
            "repo_root": str(REPO_ROOT.resolve()),
            "data_dir": str(DATA_DIR.resolve()),
        },
        "cameras": {"rpicam": hardware_inventory.detect_rpicam_cameras()},
        "storage": storage_summary(REPO_ROOT),
        "monitors": monitor_summaries(),
        "camera_worker": camera_worker_summary(),
        "firmware": {
            "generator_path": str(PICO_GENERATOR_FILE),
            "generator_exists": PICO_GENERATOR_FILE.exists(),
            "templates_path": str(PICO_TEMPLATES_DIR),
            "templates_exist": PICO_TEMPLATES_DIR.exists(),
        },
        "log": {
            "path": str(LOG_FILE),
            "exists": LOG_FILE.exists(),
        },
    }


def controller_telemetry(controller: str) -> dict[str, Any]:
    if controller_firmware(controller) == "pico_scheduler":
        with monitors_lock:
            monitor = monitors.get(controller)
        if monitor is None:
            return {}
        return monitor.snapshot()
    path = controller_state_path(controller)
    try:
        state = load_json_file(path)
    except HTTPException as exc:
        if exc.status_code == 404:
            return {}
        raise
    return state if isinstance(state, dict) else {}


def controller_status_tree(config: dict[str, Any], controller_ids: set[str] | None = None) -> dict[str, Any]:
    controllers = config.get("controllers", {})
    if not isinstance(controllers, dict):
        return {}
    status = {}
    for controller_id, controller in controllers.items():
        if not isinstance(controller_id, str) or not isinstance(controller, dict):
            continue
        if controller_ids is not None and controller_id not in controller_ids:
            continue
        item = dict(controller)
        item["telemetry"] = controller_telemetry(controller_id)
        status[controller_id] = item
    return status


def status_response() -> dict[str, Any]:
    config = load_config()
    return {
        "config": config,
        "controllers": controller_status_tree(config),
        "monitors": monitor_summaries(),
        "camera_worker": camera_worker_summary(),
    }


def status_response_for_paths(paths: list[str] | None = None) -> dict[str, Any]:
    if not paths:
        return status_response()

    config = load_config()
    requested_roots = {path.split(".", 1)[0] for path in paths if path}
    status: dict[str, Any] = {"config": config}

    if "controllers" in requested_roots:
        controller_ids: set[str] | None = set()
        for path in paths:
            if not path.startswith("controllers."):
                continue
            parts = [part for part in path.split(".") if part]
            if len(parts) > 1:
                controller_ids.add(parts[1])
        status["controllers"] = controller_status_tree(config, controller_ids or None)

    if "monitors" in requested_roots:
        status["monitors"] = monitor_summaries()

    if "camera_worker" in requested_roots:
        status["camera_worker"] = camera_worker_summary()

    return status


def resolve_status_path(node: Any, path: str) -> Any:
    current = node
    if not path:
        raise HTTPException(status_code=404, detail=f"unknown status path: {path}")
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            raise HTTPException(status_code=404, detail=f"unknown status path: {path}")
        current = current[part]
    return current


def filtered_status_response(paths: list[str] | None = None, *, status: dict[str, Any] | None = None) -> Any:
    status = status if status is not None else status_response_for_paths(paths)
    if not paths:
        return status
    result = []
    for path in paths:
        result.append({"path": path, "value": resolve_status_path(status, path)})
    return result


def iter_status_events(paths: list[str] | None = None, *, poll_interval: float = 1.0):
    last_payload: Any = object()
    first = True
    while True:
        payload = filtered_status_response(paths, status=status_response_for_paths(paths))
        if first:
            yield sse_message("snapshot", payload)
            last_payload = payload
            first = False
        elif payload != last_payload:
            yield sse_message("update", payload)
            last_payload = payload
        time.sleep(poll_interval)


def stream_status(paths: list[str] | None = None) -> StreamingResponse:
    return StreamingResponse(iter_status_events(paths), media_type="text/event-stream")


def settings_summary() -> dict[str, Any]:
    return status_response()


def validate_hostname(value: object) -> str:
    if not isinstance(value, str):
        raise HTTPException(status_code=422, detail="hostname must be a string")
    hostname = value.strip()
    if not HOSTNAME_RE.fullmatch(hostname):
        raise HTTPException(
            status_code=422,
            detail="hostname must be 1-63 letters, numbers, or hyphens, and cannot start or end with a hyphen",
        )
    return hostname


def update_hostname_hosts_file(path: Path, hostname: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    updated = False
    rewritten: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("127.0.1.1"):
            rewritten.append(f"127.0.1.1\t{hostname}")
            updated = True
        else:
            rewritten.append(line)
    if not updated:
        rewritten.append(f"127.0.1.1\t{hostname}")
    path.write_text("\n".join(rewritten) + "\n", encoding="utf-8")


def run_hostname_command(args: list[str], *, timeout: int, timeout_detail: str, error_prefix: str) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            args,
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=504, detail=timeout_detail) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"{error_prefix}: {exc}") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or error_prefix).strip()
        raise HTTPException(status_code=409, detail=detail)
    return completed


def verify_mdns_hostname(hostname: str) -> None:
    if not shutil.which("avahi-resolve-host-name"):
        raise HTTPException(status_code=500, detail="mDNS verification tool missing: install avahi-utils")
    run_hostname_command(
        ["avahi-resolve-host-name", "-4", f"{hostname}.local"],
        timeout=15,
        timeout_detail=(
            "mDNS verification timed out; check avahi-daemon, UDP 5353, and that client multicast "
            "route 224.0.0.251 uses the LAN interface"
        ),
        error_prefix="mDNS verification failed",
    )


def apply_hostname(hostname: str) -> dict[str, Any]:
    run_hostname_command(
        ["hostnamectl", "set-hostname", hostname],
        timeout=15,
        timeout_detail="hostname update timed out",
        error_prefix="hostname update failed",
    )
    update_hostname_hosts_file(HOSTS_FILE, hostname)
    run_hostname_command(
        ["systemctl", "restart", "avahi-daemon"],
        timeout=15,
        timeout_detail="avahi restart timed out",
        error_prefix="avahi restart failed",
    )
    verify_mdns_hostname(hostname)
    return {
        "hostname": hostname,
        "message": f"hostname updated; /etc/hosts updated; mDNS ready at {hostname}.local",
    }


@app.get("/api/host-config")
def get_host_config() -> dict[str, Any]:
    return {"hostname": socket.gethostname()}


@app.post("/api/host-config/hostname")
def post_host_config_hostname(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return apply_hostname(validate_hostname(payload.get("hostname")))


@app.get("/api/logs")
def get_logs(lines: int = Query(200, ge=1, le=1000)) -> dict[str, Any]:
    return {"path": str(LOG_FILE), "content": read_log_tail(lines)}


@app.post("/api/system/restart")
def post_system_restart() -> dict[str, Any]:
    return run_plampctl_action("restart")


@app.post("/api/system/reinstall")
def post_system_reinstall() -> dict[str, Any]:
    return run_plampctl_action("reinstall")


@app.post("/api/system/upgrade")
def post_system_upgrade() -> dict[str, Any]:
    return run_plampctl_action("upgrade")


def config_response() -> dict[str, Any]:
    return {"config": load_config()}


@app.get("/api/config")
def get_config() -> dict[str, Any]:
    return config_response()


@app.get("/api/system")
def get_system() -> dict[str, Any]:
    return system_response()


@app.get("/system", response_class=HTMLResponse)
def get_system_page() -> str:
    return render_system_info_page(system_response(), read_log_tail(200))


def get_status(path: list[str] | None = None, stream: bool = False) -> Any:
    if stream:
        return stream_status(path)
    return filtered_status_response(path)


@app.get("/api/status")
def get_status_route(path: list[str] | None = Query(default=None), stream: bool = Query(default=False)) -> Any:
    return get_status(path, stream)


@app.put("/api/config")
def put_config(config: dict[str, Any] = Body(...)) -> dict[str, Any]:
    with config_lock:
        raw_config = load_raw_config()
        submitted = {name: config.get(name, {}) for name in ("controllers", "cameras")}
        try:
            updated = config_view(submitted)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        saved = dict(raw_config)
        saved.update(updated)
        atomic_write_json(CONFIG_FILE, saved)
    reconcile_configured_monitors()
    reconcile_camera_worker()
    return config_response()


def put_config_section(section: str, value: dict[str, Any]) -> dict[str, Any]:
    with config_lock:
        raw_config = load_raw_config()
        config = {name: raw_config.get(name, {}) for name in ("controllers", "cameras")}
        try:
            updated = apply_config_section(config, section, value)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        saved = dict(raw_config)
        saved.update(updated)
        atomic_write_json(CONFIG_FILE, saved)
    reconcile_configured_monitors()
    reconcile_camera_worker()
    return config_response()


@app.put("/api/config/controllers")
def put_config_controllers(controllers: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return put_config_section("controllers", controllers)


@app.put("/api/config/cameras")
def put_config_cameras(cameras: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return put_config_section("cameras", cameras)


def controller_firmware(controller: str) -> str:
    return str(controller_item(controller).get("type", "pico_scheduler"))


def controller_discovery_payload() -> dict[str, Any]:
    return {
        "controllers": {
            controller_id: {"firmware": str(controller_data.get("type", "pico_scheduler"))}
            for controller_id, controller_data in controllers_index().items()
        }
    }


def controller_state_payload(controller: str) -> dict[str, Any]:
    firmware = controller_firmware(controller)
    if firmware == "pico_scheduler":
        state = state_for_role(controller)
        state = dict(state)
        state["report_every"] = require_int(
            timer_role(controller).get("payload", {}).get("report_every", 10),
            "report_every must be an integer",
        )
    else:
        path = controller_state_path(controller)
        try:
            state = load_json_file(path)
        except HTTPException as exc:
            if exc.status_code == 404:
                state = {}
            else:
                raise
    if not isinstance(state, dict):
        state = {}
    payload = dict(state)
    payload["controller"] = controller
    payload["firmware"] = firmware
    return payload


@app.get("/api/controllers")
def get_controllers() -> dict[str, Any]:
    return controller_discovery_payload()


@app.get("/api/controllers/{controller}", response_model=None)
def get_controller(controller: str, stream: bool = False) -> Any:
    if stream:
        if controller_firmware(controller) != "pico_scheduler":
            raise HTTPException(status_code=422, detail="stream is only supported for pico_scheduler controllers")
        return stream_timer_events(controller)
    return controller_state_payload(controller)


@app.put("/api/controllers/{controller}")
def put_controller(controller: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    firmware = controller_firmware(controller)
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="top-level JSON must be an object")
    payload_controller = payload.get("controller")
    if payload_controller not in (None, controller):
        raise HTTPException(status_code=422, detail="controller payload mismatch")
    payload_firmware = payload.get("firmware")
    if payload_firmware not in (None, firmware):
        raise HTTPException(status_code=422, detail="firmware payload mismatch")

    content = dict(payload)
    content.pop("controller", None)
    content.pop("firmware", None)

    if firmware == "pico_scheduler":
        path = timer_state_path(controller)
        validated = validate_timer_state(content)
        with lock_for(role_locks, controller):
            atomic_write_json(path, validated)
            sent = apply_timer_state(controller, path)
        response = {
            "controller": controller,
            "firmware": firmware,
            "success": True,
            "message": "state saved and sent to Pico",
            "pico": sent,
        }
        response.update(validated)
        return response

    path = controller_state_path(controller)
    with lock_for(role_locks, controller):
        atomic_write_json(path, content)
    response = {"controller": controller, "firmware": firmware, "success": True}
    response.update(content)
    return response


@app.get("/api/timer-config")
def get_timer_config() -> dict[str, Any]:
    payload = controller_discovery_payload()
    roles = [
        controller_id
        for controller_id, item in payload.get("controllers", {}).items()
        if isinstance(item, dict) and item.get("firmware") == "pico_scheduler"
    ]
    return {"roles": roles, "channels": configured_timer_channels(), "time_format": configured_time_format()}


@app.get("/api/host-time")
def get_host_time() -> dict[str, Any]:
    return host_time_summary()


@app.get("/api/camera/captures")
def get_camera_captures(
    camera_id: str | None = None,
    source: str = "all",
    grow_id: str | None = None,
    limit: int = 24,
    offset: int = 0,
) -> dict[str, Any]:
    safe_limit = max(0, min(limit, 200))
    safe_offset = max(0, offset)
    all_captures = camera_capture.collect_camera_captures(
        repo_root=camera_capture.REPO_ROOT,
        data_dir=camera_capture.DATA_DIR,
        grows_dir=camera_capture.GROWS_DIR,
        config_file=camera_capture.CONFIG_FILE,
        source=source,
        grow_id=grow_id,
    )
    selected_camera_id = str(camera_id or "").strip()
    if selected_camera_id:
        all_captures = [item for item in all_captures if str(item.get("camera_id") or "") == selected_camera_id]
    captures = all_captures[safe_offset : safe_offset + safe_limit + 1]
    return {
        "captures": captures[:safe_limit],
        "limit": safe_limit,
        "offset": safe_offset,
        "has_more": len(captures) > safe_limit,
        "total": len(all_captures),
    }


@app.get("/api/camera/images/{image_key}")
def get_camera_image_by_key(image_key: str) -> FileResponse:
    image_path = camera_capture.resolve_capture_image_key(image_key, repo_root=camera_capture.REPO_ROOT)
    if image_path is None:
        raise HTTPException(status_code=404, detail="unknown camera image")
    return FileResponse(image_path, media_type="image/jpeg")


@app.post("/api/camera/captures")
def post_camera_capture(camera_id: str | None = None) -> dict[str, Any]:
    return get_or_start_camera_worker().capture(camera_id=camera_id, capture_kind="manual")


@app.get("/api/camera/captures/{capture_id}/image")
def get_camera_capture_image(capture_id: str) -> FileResponse:
    image_path = camera_capture.find_capture_image(
        capture_id,
        repo_root=camera_capture.REPO_ROOT,
        data_dir=camera_capture.DATA_DIR,
        grows_dir=camera_capture.GROWS_DIR,
        config_file=camera_capture.CONFIG_FILE,
    )
    if image_path is None:
        raise HTTPException(status_code=404, detail=f"unknown camera capture: {capture_id}")
    return FileResponse(image_path, media_type="image/jpeg")


def post_timer_channel_schedule(role: str, channel_id: str, schedule: dict[str, Any] = Body(...)) -> dict[str, Any]:
    config = load_config()
    timer_role(role)
    path = timer_state_path(role)
    saved_state = load_timer_state_for_schedule_edit(path)
    live_state = latest_timer_state(role)
    channel_state = live_state if isinstance(live_state, dict) else saved_state
    channels = channel_metadata_for_role(role, config, channel_state)
    try:
        updated = patch_channel_schedule(
            saved_state,
            channels,
            channel_id,
            schedule,
            live_devices=live_devices_for_role(role),
            now=datetime.now().time(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    validated = validate_timer_state(updated)
    sent = None
    message = "schedule saved and sent to Pico"
    with lock_for(role_locks, role):
        atomic_write_json(path, validated)
        try:
            sent = apply_timer_state(role, path)
        except HTTPException as exc:
            detail = str(exc.detail) if getattr(exc, "detail", None) else str(exc)
            if detail.startswith(f"Pico for role {role} is not connected:"):
                reconnected = False
                for _ in range(6):
                    pytime.sleep(0.5)
                    try:
                        pico_for_role(role)
                    except HTTPException:
                        continue
                    reconnected = True
                    break
                message = "schedule saved; Pico briefly reconnected while applying." if reconnected else f"schedule saved; {detail}"
            else:
                message = f"schedule saved; {detail}"
    return {
        "role": role,
        "channel": channel_id,
        "success": True,
        "message": message,
        "pico": sent,
        "state": state_with_current_values(validated),
    }


@app.post("/api/controllers/{controller}/channels/{channel_id}/schedule")
def post_controller_channel_schedule(controller: str, channel_id: str, schedule: dict[str, Any] = Body(...)) -> dict[str, Any]:
    if controller_firmware(controller) != "pico_scheduler":
        raise HTTPException(status_code=422, detail="channel schedule is only supported for pico_scheduler controllers")
    response = post_timer_channel_schedule(controller, channel_id, schedule)
    response["controller"] = response.pop("role")
    return response


@app.post("/api/controllers/{controller}/apply")
def post_controller_apply(controller: str) -> dict[str, Any]:
    if controller_firmware(controller) != "pico_scheduler":
        raise HTTPException(status_code=422, detail="apply is only supported for pico_scheduler controllers")
    path = timer_state_path(controller)
    validated = load_timer_state_for_schedule_edit(path)
    sent = None
    message = "state sent to Pico"
    with lock_for(role_locks, controller):
        atomic_write_json(path, validated)
        try:
            sent = apply_timer_state(controller, path)
        except HTTPException as exc:
            detail = str(exc.detail) if getattr(exc, "detail", None) else str(exc)
            message = f"state saved; {detail}"
    return {
        "controller": controller,
        "firmware": "pico_scheduler",
        "success": True,
        "message": message,
        "pico": sent,
        "state": state_with_current_values(validated),
    }


def default_timer_payload_for_api_test(default_role: str | None) -> str:
    if not default_role:
        return "{}"
    try:
        return json.dumps(load_json_file(timer_state_path(default_role)), indent=2)
    except HTTPException as exc:
        if exc.status_code == 404:
            return "{}"
        raise


def api_test_page_response() -> HTMLResponse:
    roles = configured_timer_roles()
    default_role = roles[0] if roles else "pump_lights"
    default_payload = default_timer_payload_for_api_test(default_role if roles else None)
    return HTMLResponse(render_api_test_page(roles, default_role, default_payload, configured_time_format()))


@app.get("/api/test", response_class=HTMLResponse)
def api_test_page() -> HTMLResponse:
    return api_test_page_response()


@app.get("/settings.json")
def get_settings_json() -> dict[str, Any]:
    return settings_summary()


@app.get("/settings", response_class=HTMLResponse)
def get_settings_page() -> HTMLResponse:
    return HTMLResponse(render_settings_page(settings_summary()))


@app.get("/", response_class=HTMLResponse)
def get_timer_dashboard_page() -> HTMLResponse:
    return HTMLResponse(
        render_timer_dashboard_page(
            configured_timer_roles(),
            configured_time_format(),
            configured_timer_channels(),
            seconds_since_midnight(),
            configured_camera_ids(),
            socket.gethostname(),
        )
    )
