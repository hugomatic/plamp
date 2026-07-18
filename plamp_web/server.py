from __future__ import annotations

import copy
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
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import serial
from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from plamp.camera import CameraError, capture_camera
from plamp.config import ConfigError, load_config as read_config_file, save_config as write_config_file
from plamp.context import resolve_context
from plamp.locks import LockTimeout
from plamp.pico_firmware import firmware_revision, render_scheduler_firmware
from plamp.pico_health import PicoHealth, failed_health, probe_pico
from plamp.pico_scheduler import SchedulerApplyResult, apply_scheduler_state
from plamp.pico_transport import PicoClient, PicoCommandError, PicoExchange, PicoFlashError, PicoReportTimeout, PicoUnavailable
from plamp.scheduler_state import EXPECTED_FIRMWARE_PROTOCOL, FirmwareIdentity, firmware_identity, normalize_scheduler_state
from plamp.usb_events import UsbSerialEvent, start_usb_serial_observer
from plamp_web import camera_capture, hardware_inventory
from plamp_web.pages import render_api_test_page, render_system_info_page, set_app_revision
from plamp_web.hardware_config import (
    apply_config_section,
    config_view,
    empty_config,
    scheduler_controller_ids,
    scheduler_devices_for_controller,
)
from plamp_web.timer_schedule import channel_metadata_for_role, compile_controller_state


RUNTIME_CONTEXT = resolve_context()
REPO_ROOT = RUNTIME_CONTEXT.root
STATIC_DIR = Path(__file__).resolve().parent / "static"
HOSTS_FILE = Path("/etc/hosts")
DATA_DIR = RUNTIME_CONTEXT.data_dir
CONFIG_FILE = RUNTIME_CONTEXT.config_file
TIMERS_DIR = DATA_DIR / "timers"
PICO_GENERATOR_FILE = REPO_ROOT / "pico_scheduler" / "src" / "generator.py"
PICO_TEMPLATES_DIR = REPO_ROOT / "pico_scheduler" / "src" / "templates"
LOG_FILE = DATA_DIR / "plamp.log"
PICO_NAME_HINTS = ("pico", "rp2", "raspberry", "micropython")
RASPBERRY_PI_USB_VENDOR_ID = "2e8a"
PICO_HEALTH_INTERVAL_SECONDS = 5.0
ROLE_RE = re.compile(r"^[A-Za-z0-9_-]+$")
HOSTNAME_RE = re.compile(
    r"^(?=.{1,63}$)[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?$"
)
LOGGER = logging.getLogger("plamp_web")

config_lock = threading.Lock()
role_locks: dict[str, threading.Lock] = {}
monitors_lock = threading.Lock()
monitors: dict[str, "PicoMonitor"] = {}
usb_observer: Any | None = None
camera_worker_lock = threading.Lock()
camera_worker: "CameraWorker | None" = None

app = FastAPI(title="plamp web")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
APP_REVISION = "unknown"


@app.on_event("startup")
def startup() -> None:
    global APP_REVISION
    APP_REVISION = git_output(["git", "rev-parse", "--short", "HEAD"], repo_root=REPO_ROOT) or "unknown"
    set_app_revision(APP_REVISION)
    ensure_data_dir()
    configure_logging()
    start_configured_monitors()
    start_usb_observer()
    get_or_start_camera_worker()


@app.get("/favicon.svg")
def favicon_svg() -> FileResponse:
    return FileResponse(STATIC_DIR / "favicon.svg", media_type="image/svg+xml")


@app.on_event("shutdown")
def shutdown() -> None:
    stop_camera_worker()
    stop_usb_observer()
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
        write_config_file(CONFIG_FILE, empty_config())


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
    try:
        return read_config_file(CONFIG_FILE)
    except ConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


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
    report_every = require_int(raw.get("report_every", 1), "report_every must be an integer")
    if report_every <= 0:
        raise HTTPException(status_code=422, detail="report_every must be > 0")
    try:
        pico_state = normalize_scheduler_state(raw)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"report_every": report_every, "devices": pico_state["devices"]}


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
                result = capture_camera(
                    command.camera_id or "camera",
                    lock_dir=RUNTIME_CONTEXT.lock_dir,
                    timeout=60.0,
                    capture_func=self.capture_func,
                    repo_root=camera_capture.REPO_ROOT,
                    data_dir=camera_capture.DATA_DIR,
                    config_file=camera_capture.CONFIG_FILE,
                    capture_kind=command.capture_kind,
                )
            except (CameraError, LockTimeout) as exc:
                command.error = camera_capture.CameraCaptureError(
                    str(exc), status_code=getattr(exc, "status_code", 409)
                )
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


def identity_payload(identity: FirmwareIdentity | None) -> dict[str, Any] | None:
    if identity is None:
        return None
    return {
        "name": identity.name,
        "revision": identity.revision,
        "protocol": identity.protocol,
    }


def expected_scheduler_identity() -> FirmwareIdentity:
    return FirmwareIdentity(
        "pico_scheduler",
        firmware_revision(REPO_ROOT),
        EXPECTED_FIRMWARE_PROTOCOL,
    )


def scheduler_firmware_status(report: Any) -> dict[str, Any]:
    expected = expected_scheduler_identity()
    try:
        observed = firmware_identity(report)
    except ValueError:
        observed = None
    return {
        "current": observed == expected,
        "expected": identity_payload(expected),
        "observed": identity_payload(observed),
    }


class PicoMonitor:
    def __init__(self, role: str, pico_serial: str):
        self.role = role
        self.pico_serial = pico_serial
        self.client = PicoClient(pico_serial, lock_dir=RUNTIME_CONTEXT.lock_dir)
        self.subscribers: set[queue.Queue[dict[str, Any]]] = set()
        self.lock = threading.Lock()
        self.serial_entries = deque(maxlen=200)
        self.stop_event = threading.Event()
        self.wake_event = threading.Event()
        self.thread = threading.Thread(target=self.run, name=f"pico-monitor-{role}", daemon=True)
        self.report_sequence = 0
        initial_health = failed_health(
            pico_serial,
            kind="unavailable",
            step="report",
            message="no valid report received",
        )
        self.summary: dict[str, Any] = {
            "role": role,
            "serial": pico_serial,
            "state": "starting",
            "connected": False,
            "ok": False,
            "status": "ERROR",
            "checked_at": initial_health.checked_at,
            "port": None,
            "last_seen": None,
            "last_error": initial_health.error.message,
            "error": initial_health.error.as_dict(),
            "raw_lines": [],
            "last_verified_at": None,
            "last_report": None,
            "report_sequence": 0,
        }

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        self.wake_event.set()

    def wake(self) -> None:
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

    def record_serial(self, direction: str, text: str, *, journal: bool = True) -> dict[str, Any]:
        entry = {
            "at": datetime.now().isoformat(timespec="seconds"),
            "direction": direction,
            "role": self.role,
            "text": text,
        }
        with self.lock:
            self.serial_entries.append(entry)
        if not journal:
            return entry
        if direction == "tx":
            LOGGER.info("pico-cmd tx role=%s cmd=%r", self.role, text)
        elif direction == "rx":
            LOGGER.info("pico-cmd rx role=%s text=%r", self.role, text)
        else:
            LOGGER.warning("pico-cmd err role=%s text=%r", self.role, text)
        return entry

    def serial_log(self) -> list[dict[str, Any]]:
        with self.lock:
            return list(self.serial_entries)

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

    def update_health(self, health: PicoHealth) -> None:
        error = health.error.as_dict() if health.error else None
        state = "connected" if health.ok else ("disconnected" if health.error and health.error.kind == "unavailable" else "error")
        firmware = scheduler_firmware_status(health.report) if health.ok else None
        with self.lock:
            transition = any(
                (
                    self.summary.get("ok") != health.ok,
                    self.summary.get("status") != health.status,
                    self.summary.get("port") != health.port,
                    self.summary.get("error") != error,
                )
            )
            self.summary.update(
                {
                    "ok": health.ok,
                    "status": health.status,
                    "state": state,
                    "connected": health.ok,
                    "checked_at": health.checked_at,
                    "port": health.port,
                    "error": error,
                    "last_error": health.error.message if health.error else None,
                    "raw_lines": list(health.raw_lines),
                    "updated_at": health.checked_at,
                }
            )
            if firmware is not None:
                self.summary["firmware"] = firmware
            if health.ok:
                self.summary["last_verified_at"] = health.checked_at
            snapshot = dict(self.summary)
        if transition:
            LOGGER.info(
                "pico health role=%s status=%s serial=%s port=%s error=%s",
                self.role,
                health.status,
                health.serial,
                health.port,
                error,
            )
        self.publish("status", snapshot)

    def health_for_exchange(self, result: Any) -> PicoHealth:
        raw_lines = tuple(
            raw.decode("utf-8", errors="replace").strip()
            for raw in result.raw_lines
        )
        return PicoHealth(
            ok=True,
            status="OK",
            checked_at=datetime.now().astimezone().isoformat(timespec="seconds"),
            serial=self.pico_serial,
            port=result.port,
            report=result.message,
            raw_lines=raw_lines,
            error=None,
        )

    def record_apply_result(self, result: SchedulerApplyResult) -> None:
        """Publish one completed transaction through the normal health/report path."""
        exchange = PicoExchange(result.report, result.port, result.raw_lines)
        self.record_exchange("configure", exchange)
        self.handle_line(json.dumps(result.report).encode("utf-8"), record=False)
        self.update_health(self.health_for_exchange(exchange))
        self.update_status("connected", connected=True, port=result.port, error=None)

    def handle_usb_event(self, event: UsbSerialEvent) -> None:
        if event.serial != self.pico_serial:
            return
        if event.action == "remove":
            self.update_health(
                failed_health(
                    self.pico_serial,
                    kind="unavailable",
                    step="discover",
                    message=f"configured Pico is not connected: {self.pico_serial}",
                    port=event.port,
                )
            )
        else:
            self.wake()

    def find_port(self) -> str | None:
        for pico in enumerate_picos():
            if pico.get("serial") == self.pico_serial:
                return str(pico["port"])
        return None

    def handle_line(self, raw: bytes, *, record: bool = True) -> None:
        text = raw.decode("utf-8", errors="replace").strip()
        if not text:
            return
        if record:
            self.record_serial("rx", text)
        now = datetime.now().isoformat(timespec="seconds")
        try:
            report = json.loads(text)
        except json.JSONDecodeError as exc:
            error = f"invalid JSON from Pico: {exc}"
            with self.lock:
                self.summary["last_seen"] = now
                self.summary["last_error"] = error
            LOGGER.warning("pico monitor %s invalid JSON: %s", self.role, text)
            self.record_serial("err", error)
            self.publish("error", {"role": self.role, "serial": self.pico_serial, "message": error, "raw": text})
            return
        reduced = reduce_report(report)
        is_report = isinstance(reduced, dict) and reduced.get("type") == "report"
        with self.lock:
            self.summary["last_seen"] = now
            self.summary["last_error"] = None
            if is_report:
                self.report_sequence += 1
                self.summary["report_sequence"] = self.report_sequence
                self.summary["last_report"] = reduced
                if "pins" in reduced:
                    self.summary["pins"] = reduced["pins"]
        if is_report:
            self.publish(
                "report",
                {
                    "role": self.role,
                    "serial": self.pico_serial,
                    "received_at": now,
                    "report_sequence": self.report_sequence,
                    "report": reduced,
                },
            )

    def apply(self, path: Path, timeout: float = 60.0) -> dict[str, Any]:
        self.update_status("applying", connected=False, error=None)
        mpremote = shutil.which("mpremote")
        if not mpremote:
            raise HTTPException(status_code=500, detail="mpremote not found")
        try:
            result = self.client.flash_main(
                path,
                timeout=timeout,
                mpremote=mpremote,
                command_runner=lambda args, budget: run_command(args, timeout=budget),
                interrupter=interrupt_pico_program,
                sleeper=self.stop_event.wait,
            )
        except LockTimeout as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except PicoFlashError as exc:
            self.update_health(failed_health(self.pico_serial, kind="protocol", step=f"flash:{exc.step}", message=str(exc)))
            self.update_status("error", connected=False, error=exc.detail())
            raise HTTPException(status_code=502, detail=exc.detail()) from exc
        except PicoUnavailable as exc:
            self.update_health(failed_health(self.pico_serial, kind="unavailable", step="discover", message=str(exc)))
            self.update_status("disconnected", connected=False, error=str(exc))
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except PicoReportTimeout as exc:
            raw_lines = tuple(raw.decode("utf-8", errors="replace").strip() for raw in exc.raw_lines)
            self.update_health(failed_health(self.pico_serial, kind="protocol" if raw_lines else "timeout", step="report", message=str(exc), raw_lines=raw_lines))
            self.update_status("error", connected=False, error=str(exc))
            raise HTTPException(status_code=504, detail=str(exc)) from exc
        except (OSError, serial.SerialException) as exc:
            self.update_health(failed_health(self.pico_serial, kind="serial", step="report", message=str(exc)))
            self.update_status("disconnected", connected=False, error=str(exc))
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        self.record_exchange("r", result)
        self.handle_line(json.dumps(result.message).encode("utf-8"), record=False)
        self.update_health(self.health_for_exchange(result))
        self.update_status("connected", connected=True, port=result.port, error=None)
        return {
            "role": self.role,
            "port": result.port,
            "serial": self.pico_serial,
            "report_sequence": self.report_sequence,
        }

    def send_serial_command(self, text: str, timeout: float = 5.0) -> dict[str, Any]:
        try:
            result = self.client.command(text, timeout=timeout)
        except LockTimeout as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except PicoUnavailable as exc:
            self.update_health(failed_health(self.pico_serial, kind="unavailable", step="discover", message=str(exc)))
            self.update_status("disconnected", connected=False, error=str(exc))
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except PicoReportTimeout as exc:
            self.record_timeout(text, exc)
            raw_lines = tuple(raw.decode("utf-8", errors="replace").strip() for raw in exc.raw_lines)
            self.update_health(failed_health(self.pico_serial, kind="protocol" if raw_lines else "timeout", step="report", message=str(exc), raw_lines=raw_lines))
            raise HTTPException(status_code=504, detail=str(exc)) from exc
        except (OSError, serial.SerialException) as exc:
            self.update_health(failed_health(self.pico_serial, kind="serial", step="report", message=str(exc)))
            self.update_status("disconnected", connected=False, error=str(exc))
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        self.record_exchange(text, result)
        if result.message.get("type") == "error":
            raise HTTPException(status_code=409, detail=result.message.get("content"))
        self.handle_line(json.dumps(result.message).encode("utf-8"), record=False)
        self.update_health(self.health_for_exchange(result))
        self.update_status("connected", connected=True, port=result.port, error=None)
        return {"role": self.role, "serial": self.pico_serial, "command": text}

    def record_exchange(self, command: str, result: Any, *, journal: bool = True) -> None:
        self.record_serial("tx", command, journal=journal)
        for raw in result.raw_lines:
            text = raw.decode("utf-8", errors="replace").strip()
            if text:
                self.record_serial("rx", text, journal=journal)

    def record_timeout(self, command: str, exc: PicoReportTimeout) -> None:
        self.record_serial("tx", command)
        for raw in exc.raw_lines:
            text = raw.decode("utf-8", errors="replace").strip()
            if text:
                self.record_serial("rx", text)
        self.record_serial("err", str(exc))

    def collect_report(self, timeout: float = 3.0) -> PicoHealth:
        health = probe_pico(self.client, timeout=timeout)
        self.record_serial("tx", "r", journal=False)
        for text in health.raw_lines:
            if text:
                self.record_serial("rx", text, journal=False)
        if health.ok and health.report is not None:
            self.handle_line(json.dumps(health.report).encode("utf-8"), record=False)
        elif health.error is not None:
            self.record_serial("err", health.error.message)
        self.update_health(health)
        return health

    def require_fresh_report(self, timeout: float = 3.0) -> dict[str, Any]:
        health = self.collect_report(timeout=timeout)
        if health.ok and health.report is not None:
            return health.report
        error = health.error
        status_code = {
            "unavailable": 409,
            "timeout": 504,
            "serial": 502,
            "protocol": 502,
        }.get(error.kind if error else "", 502)
        raise HTTPException(
            status_code=status_code,
            detail={
                "message": error.message if error else "Pico health check failed",
                "health": health.as_dict(),
            },
        )

    def run(self) -> None:
        while not self.stop_event.is_set():
            started = time.monotonic()
            try:
                self.collect_report()
            except LockTimeout:
                # Another local process owns the Pico; that is normal, not a fault.
                pass
            except Exception as exc:
                self.update_status("error", connected=False, error=str(exc))
            self.wake_event.wait(max(0.0, PICO_HEALTH_INTERVAL_SECONDS - (time.monotonic() - started)))
            self.wake_event.clear()
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


def dispatch_usb_event(event: UsbSerialEvent) -> None:
    with monitors_lock:
        active = list(monitors.values())
    for monitor in active:
        monitor.handle_usb_event(event)


def start_usb_observer() -> None:
    global usb_observer
    if usb_observer is None:
        usb_observer = start_usb_serial_observer(dispatch_usb_event)


def stop_usb_observer() -> None:
    global usb_observer
    observer = usb_observer
    usb_observer = None
    if observer is not None:
        observer.stop()


def reconcile_configured_monitors() -> None:
    try:
        serials = configured_monitor_serials()
    except HTTPException:
        return
    stale = []
    retained = []
    with monitors_lock:
        for role, monitor in list(monitors.items()):
            if role not in serials or monitor.pico_serial != serials[role]:
                stale.append(monitors.pop(role))
            else:
                retained.append(monitor)
    for monitor in stale:
        monitor.stop()
    for monitor in stale:
        monitor.join()
    for monitor in retained:
        monitor.wake()
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


def send_timer_command(role: str, command: str) -> dict[str, Any]:
    return get_or_start_monitor(role).send_serial_command(command)


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
    config = load_config()
    summary = system_response()
    summary["config"] = config
    summary["controllers"] = controller_status_tree(config)
    summary["monitors"] = monitor_summaries()
    summary["camera_worker"] = camera_worker_summary()
    return summary


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
    return render_system_info_page(system_response(), read_log_tail(200), configured_timer_roles())


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
        write_config_file(CONFIG_FILE, saved)
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
        write_config_file(CONFIG_FILE, saved)
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
    state = state_for_role(controller)
    state = dict(state)
    state["report_every"] = require_int(
        timer_role(controller).get("payload", {}).get("report_every", 10),
        "report_every must be an integer",
    )
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
    controller_firmware(controller)
    raise HTTPException(
        status_code=409,
        detail=(
            "compiled scheduler state PUT is not supported; submit the desired "
            f"controller config to POST /api/controllers/{controller}/schedule"
        ),
    )


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
    controllers = copy.deepcopy(config.get("controllers", {}))
    controller = controllers.get(role)
    if not isinstance(controller, dict) or controller.get("type", "pico_scheduler") != "pico_scheduler":
        raise HTTPException(status_code=404, detail=f"unknown pico-scheduler controller: {role}")
    devices = controller.get("settings", {}).get("devices", {})
    device = devices.get(channel_id) if isinstance(devices, dict) else None
    if not isinstance(device, dict):
        raise HTTPException(status_code=422, detail=f"unknown channel: {channel_id}")
    mode = schedule.get("mode")
    if mode == "clock_window":
        editor = {
            "kind": "daily_window",
            "on_time": str(schedule.get("on_time", "")),
            "off_time": str(schedule.get("off_time", "")),
        }
    elif mode == "cycle":
        existing_editor = device.get("editor") if isinstance(device.get("editor"), dict) else {}
        editor = {
            "kind": "cycle",
            "on_seconds": require_int(schedule.get("on_seconds"), "on_seconds must be an integer"),
            "off_seconds": require_int(schedule.get("off_seconds"), "off_seconds must be an integer"),
            "start_at_seconds": require_int(schedule.get("start_at_seconds", 0), "start_at_seconds must be an integer"),
        }
        unit = schedule.get("unit", existing_editor.get("unit"))
        if unit in {"seconds", "minutes", "hours"}:
            editor["unit"] = unit
    else:
        raise HTTPException(status_code=422, detail="mode must be cycle or clock_window")
    device["editor"] = editor
    updated_config = copy.deepcopy(config)
    updated_config["controllers"] = controllers
    compiled_timer_state_for_controller(role, config=updated_config, now=datetime.now().time())
    applied = post_controller_schedule(role, controller)
    return {
        "role": role,
        "channel": channel_id,
        "success": applied["success"],
        "message": applied["message"],
        "firmware": applied.get("firmware"),
        "firmware_upgraded": applied.get("firmware_upgraded", False),
        "pico": applied.get("pico"),
        "state": applied.get("state"),
    }


@app.post("/api/controllers/{controller}/channels/{channel_id}/schedule")
def post_controller_channel_schedule(controller: str, channel_id: str, schedule: dict[str, Any] = Body(...)) -> dict[str, Any]:
    if controller_firmware(controller) != "pico_scheduler":
        raise HTTPException(status_code=422, detail="channel schedule is only supported for pico_scheduler controllers")
    response = post_timer_channel_schedule(controller, channel_id, schedule)
    response["controller"] = response.pop("role")
    return response


def compiled_timer_state_for_controller(
    controller: str,
    *,
    config: dict[str, Any] | None = None,
    now: Any = None,
) -> dict[str, Any]:
    config = load_config() if config is None else config
    controller_data = config.get("controllers", {}).get(controller)
    if not isinstance(controller_data, dict) or controller_data.get("type", "pico_scheduler") != "pico_scheduler":
        raise HTTPException(status_code=404, detail=f"unknown pico-scheduler controller: {controller}")
    channels = channel_metadata_for_role(controller, config, None)
    report_every = require_int(
        controller_data.get("payload", {}).get("report_every", 10),
        "report_every must be an integer",
    )
    try:
        return compile_controller_state(channels, report_every=report_every, now=now)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def controller_schedule_candidate(
    raw_config: dict[str, Any],
    controller: str,
    proposed_controller: dict[str, Any],
) -> dict[str, Any]:
    current_controllers = raw_config.get("controllers")
    if not isinstance(current_controllers, dict) or controller not in current_controllers:
        raise HTTPException(status_code=404, detail=f"unknown controller: {controller}")

    candidate = copy.deepcopy(raw_config)
    candidate_controllers = copy.deepcopy(current_controllers)
    candidate_controllers[controller] = copy.deepcopy(proposed_controller)
    try:
        validated = config_view({"controllers": candidate_controllers, "cameras": candidate.get("cameras", {})})
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    candidate.update(validated)

    current_controller = current_controllers[controller]
    proposed = candidate["controllers"].get(controller)
    if not isinstance(proposed, dict) or proposed.get("type", "pico_scheduler") != "pico_scheduler":
        raise HTTPException(status_code=422, detail="schedule is only supported for pico_scheduler controllers")
    current_serial = current_controller.get("payload", {}).get("pico_serial")
    if proposed.get("payload", {}).get("pico_serial") != current_serial:
        raise HTTPException(status_code=422, detail="pico_serial cannot be changed by the schedule endpoint")
    return candidate


def scheduler_failure_health(monitor: PicoMonitor, exc: BaseException) -> tuple[int, PicoHealth]:
    raw_bytes = getattr(exc, "raw_lines", ())
    raw_lines = tuple(
        raw.decode("utf-8", errors="replace").strip()
        for raw in raw_bytes
    )
    if isinstance(exc, PicoUnavailable):
        status_code, kind, step = 409, "unavailable", "discover"
    elif isinstance(exc, LockTimeout):
        status_code, kind, step = 409, "unavailable", "lock"
    elif isinstance(exc, PicoReportTimeout):
        status_code, kind, step = 504, "protocol" if raw_lines else "timeout", "report"
    elif isinstance(exc, PicoFlashError):
        status_code, kind, step = 502, "upgrade", f"upgrade:{exc.step}"
    elif isinstance(exc, PicoCommandError):
        status_code, kind, step = 502, "protocol", "configure"
    elif isinstance(exc, (OSError, serial.SerialException)):
        status_code, kind, step = 502, "serial", "configure"
    else:
        status_code, kind, step = 422, "validation", "configure"
    health = failed_health(
        monitor.pico_serial,
        kind=kind,
        step=step,
        message=str(exc),
        raw_lines=raw_lines,
    )
    return status_code, health


def configure_and_commit_controller_schedule(
    controller: str,
    candidate: dict[str, Any],
    current_state: dict[str, Any],
    proposed_state: dict[str, Any],
    monitor: PicoMonitor,
) -> SchedulerApplyResult:
    ensure_data_dir()
    revision, firmware_source = render_scheduler_firmware(REPO_ROOT)
    expected = FirmwareIdentity("pico_scheduler", revision, EXPECTED_FIRMWARE_PROTOCOL)
    with tempfile.TemporaryDirectory(dir=DATA_DIR, prefix=f".{controller}-upgrade-") as staging_dir:
        staging_path = Path(staging_dir)
        firmware_path = staging_path / "main.py"
        current_path = staging_path / f"{controller}.json"
        firmware_path.write_text(firmware_source, encoding="utf-8")
        current_path.write_text(
            json.dumps(normalize_scheduler_state(current_state), separators=(",", ":")),
            encoding="utf-8",
        )
        mpremote = shutil.which("mpremote")

        def upgrade(operation: Any, state: dict[str, Any], identity: FirmwareIdentity) -> PicoExchange:
            if not mpremote:
                raise PicoFlashError("prepare", None, "", "mpremote not found")
            if normalize_scheduler_state(state) != normalize_scheduler_state(current_state):
                raise ValueError("upgrade state must be the committed scheduler state")
            return operation.upgrade_scheduler(
                firmware_path,
                current_path,
                identity,
                command_runner=lambda args, budget: run_command(args, timeout=budget),
                interrupter=interrupt_pico_program,
                mpremote=mpremote,
                sleeper=monitor.stop_event.wait,
            )

        try:
            result = apply_scheduler_state(
                client=monitor.client,
                current_state=current_state,
                proposed_state=proposed_state,
                expected=expected,
                upgrade=upgrade,
                timeout=60.0,
            )
        except (ValueError, LockTimeout, PicoUnavailable, PicoReportTimeout, PicoFlashError, PicoCommandError, OSError, serial.SerialException) as exc:
            status_code, health = scheduler_failure_health(monitor, exc)
            monitor.update_health(health)
            raise HTTPException(
                status_code=status_code,
                detail={"message": str(exc), "health": health.as_dict()},
            ) from exc

    monitor.record_apply_result(result)
    write_config_file(CONFIG_FILE, candidate)
    atomic_write_json(TIMERS_DIR / f"{controller}.json", proposed_state)
    return result


@app.post("/api/controllers/{controller}/schedule")
def post_controller_schedule(controller: str, proposed_controller: dict[str, Any] = Body(...)) -> dict[str, Any]:
    if not isinstance(proposed_controller, dict):
        raise HTTPException(status_code=422, detail="controller schedule must be an object")

    with lock_for(role_locks, controller), config_lock:
        current_config = load_raw_config()
        candidate = controller_schedule_candidate(current_config, controller, proposed_controller)
        captured_time = datetime.now().time()
        current_state = validate_timer_state(
            compiled_timer_state_for_controller(controller, config=current_config, now=captured_time)
        )
        proposed_state = validate_timer_state(
            compiled_timer_state_for_controller(controller, config=candidate, now=captured_time)
        )
        result = configure_and_commit_controller_schedule(
            controller,
            candidate,
            current_state,
            proposed_state,
            get_or_start_monitor(controller),
        )

    reconcile_configured_monitors()
    reconcile_camera_worker()
    return {
        "controller": controller,
        "firmware": identity_payload(result.identity),
        "firmware_upgraded": result.upgraded,
        "success": True,
        "message": "schedule verified, saved, and applied",
        "pico": {"serial": pico_serial_for_role(controller), "port": result.port},
        "state": state_with_current_values(proposed_state),
    }


@app.post("/api/controllers/{controller}/apply")
def post_controller_apply(controller: str) -> dict[str, Any]:
    if controller_firmware(controller) != "pico_scheduler":
        raise HTTPException(status_code=422, detail="apply is only supported for pico_scheduler controllers")
    return post_controller_schedule(controller, controller_item(controller))


@app.post("/api/controllers/{controller}/commands/report")
def post_controller_report_command(controller: str) -> dict[str, Any]:
    if controller_firmware(controller) != "pico_scheduler":
        raise HTTPException(status_code=422, detail="report command is only supported for pico_scheduler controllers")
    result = send_timer_command(controller, "r")
    response = {"controller": controller, "success": True, "message": "report requested"}
    response.update(result)
    return response


def pulse_seconds_from_payload(payload: dict[str, Any]) -> int:
    try:
        seconds = int((payload or {}).get("seconds", 5))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="pulse seconds must be an integer") from exc
    if seconds <= 0:
        raise HTTPException(status_code=422, detail="pulse seconds must be > 0")
    return seconds


def pulse_device_command(controller: str, device_id: str, device: dict[str, Any], payload: dict[str, Any]) -> tuple[str, int, int]:
    if str(device.get("output_type") or "gpio") != "gpio":
        raise HTTPException(status_code=422, detail="pulse only supports gpio channels")
    try:
        pin = int(device["pin"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="channel has no valid GPIO pin") from exc
    seconds = pulse_seconds_from_payload(payload)
    return f"p {pin} {seconds}", pin, seconds


def pulse_channel_command(controller: str, channel_id: str, payload: dict[str, Any]) -> tuple[str, int, int]:
    if controller_firmware(controller) != "pico_scheduler":
        raise HTTPException(status_code=422, detail="pulse is only supported for pico_scheduler controllers")
    config = load_config()
    devices = scheduler_devices_for_controller(config, controller)
    device = devices.get(channel_id)
    if not isinstance(device, dict):
        raise HTTPException(status_code=404, detail=f"unknown channel: {channel_id}")
    return pulse_device_command(controller, channel_id, device, payload)


def pulse_pin_command(controller: str, pin: int, payload: dict[str, Any]) -> tuple[str, str, int, int]:
    if controller_firmware(controller) != "pico_scheduler":
        raise HTTPException(status_code=422, detail="pulse is only supported for pico_scheduler controllers")
    config = load_config()
    for device_id, device in scheduler_devices_for_controller(config, controller).items():
        if not isinstance(device, dict):
            continue
        try:
            device_pin = int(device.get("pin"))
        except (TypeError, ValueError):
            continue
        if device_pin == pin:
            command, command_pin, seconds = pulse_device_command(controller, device_id, device, payload)
            return command, device_id, command_pin, seconds
    raise HTTPException(status_code=404, detail=f"unknown configured pin: {pin}")


def reject_pulse_if_reported_on(controller: str, pin: int) -> None:
    state = latest_timer_state(controller)
    if not isinstance(state, dict):
        return
    for device in state.get("devices") or []:
        if not isinstance(device, dict):
            continue
        try:
            device_pin = int(device.get("pin"))
            current_value = int(device.get("current_value"))
        except (TypeError, ValueError):
            continue
        if device_pin == pin and current_value == 1:
            raise HTTPException(status_code=409, detail=f"pin {pin} is already on")


def schedule_pulse_completion_report(controller: str, seconds: int) -> None:
    monitor = get_or_start_monitor(controller)
    timer = threading.Timer(seconds + 0.1, monitor.wake)
    timer.daemon = True
    timer.start()


@app.post("/api/controllers/{controller}/channels/{channel_id}/pulse")
def post_controller_channel_pulse(controller: str, channel_id: str, payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    command, pin, seconds = pulse_channel_command(controller, channel_id, payload)
    reject_pulse_if_reported_on(controller, pin)
    result = send_timer_command(controller, command)
    schedule_pulse_completion_report(controller, seconds)
    response = {
        "controller": controller,
        "channel": channel_id,
        "pin": pin,
        "seconds": seconds,
        "success": True,
        "message": f"pulse requested for pin {pin}",
    }
    response.update(result)
    return response


@app.post("/api/controllers/{controller}/pins/{pin}/pulse")
def post_controller_pin_pulse(controller: str, pin: int, payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    command, channel_id, command_pin, seconds = pulse_pin_command(controller, pin, payload)
    reject_pulse_if_reported_on(controller, command_pin)
    result = send_timer_command(controller, command)
    schedule_pulse_completion_report(controller, seconds)
    response = {
        "controller": controller,
        "channel": channel_id,
        "pin": command_pin,
        "seconds": seconds,
        "success": True,
        "message": f"pulse requested for pin {command_pin}",
    }
    response.update(result)
    return response


@app.get("/api/controllers/{controller}/serial-log")
def get_controller_serial_log(controller: str) -> dict[str, Any]:
    if controller_firmware(controller) != "pico_scheduler":
        raise HTTPException(status_code=422, detail="serial log is only supported for pico_scheduler controllers")
    return {"controller": controller, "entries": get_or_start_monitor(controller).serial_log()}


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
    return HTMLResponse(render_api_test_page(roles, default_role, default_payload, configured_time_format(), socket.gethostname(), roles))


@app.get("/api/test", response_class=HTMLResponse)
def api_test_page() -> HTMLResponse:
    return api_test_page_response()


@app.get("/settings.json")
def get_settings_json() -> dict[str, Any]:
    return settings_summary()


@app.get("/settings", response_class=FileResponse)
def get_settings_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "settings.html", media_type="text/html")


@app.get("/", response_class=FileResponse)
def get_timer_dashboard_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html", media_type="text/html")


@app.get("/controllers/{controller}", response_class=FileResponse)
def get_controller_page(controller: str) -> FileResponse:
    return FileResponse(STATIC_DIR / "controller.html", media_type="text/html")
