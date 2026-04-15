from __future__ import annotations

import glob
import json
import logging
import logging.handlers
import os
import queue
import re
import shutil
import socket
import subprocess
import threading
import time
from dataclasses import dataclass, field
from functools import lru_cache
from datetime import datetime
from pathlib import Path
from typing import Any

import serial
from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from plamp_web import camera_capture, hardware_inventory
from plamp_web.pages import render_api_test_page, render_config_page, render_settings_page, render_timer_dashboard_page
from plamp_web.hardware_config import apply_config_section, config_view, empty_config
from plamp_web.timer_schedule import channel_metadata_for_role, patch_channel_schedule


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
CONFIG_FILE = DATA_DIR / "config.json"
TIMERS_DIR = DATA_DIR / "timers"
PICO_MAIN_FILE = REPO_ROOT / "pico_scheduler" / "main.py"
STATE_FILE = REPO_ROOT / "pico_scheduler" / "state.json"
LOG_FILE = DATA_DIR / "plamp.log"
PICO_NAME_HINTS = ("pico", "rp2", "raspberry", "micropython")
RASPBERRY_PI_USB_VENDOR_ID = "2e8a"
ROLE_RE = re.compile(r"^[A-Za-z0-9_-]+$")
LOGGER = logging.getLogger("plamp_web")

config_lock = threading.Lock()
role_locks: dict[str, threading.Lock] = {}
monitors_lock = threading.Lock()
monitors: dict[str, "PicoMonitor"] = {}

app = FastAPI(title="plamp web")


@app.on_event("startup")
def startup() -> None:
    ensure_data_dir()
    configure_logging()
    start_configured_monitors()


@app.on_event("shutdown")
def shutdown() -> None:
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
    for section in ("controllers", "devices", "cameras"):
        value = data.get(section, {})
        if not isinstance(value, dict):
            raise HTTPException(status_code=500, detail=f"config.json {section} must be an object")
    return data


def load_config() -> dict[str, Any]:
    data = load_raw_config()
    result = {section: data.get(section, {}) for section in ("controllers", "devices", "cameras")}
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
    return controllers


def configured_monitor_serials() -> dict[str, str]:
    result: dict[str, str] = {}
    for role, item in timer_roles().items():
        if not isinstance(role, str) or not ROLE_RE.match(role):
            raise HTTPException(status_code=500, detail=f"invalid controller role: {role}")
        if not isinstance(item, dict):
            raise HTTPException(status_code=500, detail=f"controller {role} must be an object")
        serial = item.get("pico_serial")
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


def pico_serial_for_role(role: str) -> str:
    serial = timer_role(role).get("pico_serial")
    if not isinstance(serial, str) or not serial:
        raise HTTPException(status_code=409, detail=f"timer role {role} has no configured pico_serial")
    return serial


def timer_state_path(role: str) -> Path:
    timer_role(role)
    ensure_data_dir()
    return TIMERS_DIR / f"{role}.json"


def require_int(value: Any, message: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail=message)


def validate_timer_state(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise HTTPException(status_code=422, detail="top-level JSON must be an object")
    if "report_every" not in raw:
        raise HTTPException(status_code=422, detail="missing top-level field: report_every")
    if "events" not in raw:
        raise HTTPException(status_code=422, detail="missing top-level field: events")

    report_every = require_int(raw["report_every"], "report_every must be an integer")
    if report_every <= 0:
        raise HTTPException(status_code=422, detail="report_every must be > 0")

    raw_events = raw["events"]
    if not isinstance(raw_events, list):
        raise HTTPException(status_code=422, detail="events must be a list")

    events = []
    for i, src in enumerate(raw_events):
        if not isinstance(src, dict):
            raise HTTPException(status_code=422, detail=f"event {i} must be an object")
        for name in ["type", "ch", "current_t", "reschedule", "pattern"]:
            if name not in src:
                raise HTTPException(status_code=422, detail=f"event {i} missing field: {name}")

        event_type = src["type"]
        if event_type not in {"gpio", "pwm"}:
            raise HTTPException(status_code=422, detail=f"event {i} type must be gpio or pwm")
        ch = require_int(src["ch"], f"event {i} ch must be an integer")
        current_t = require_int(src["current_t"], f"event {i} current_t must be an integer")
        reschedule = 1 if require_int(src["reschedule"], f"event {i} reschedule must be an integer") else 0
        if ch < 0 or ch > 29:
            raise HTTPException(status_code=422, detail=f"event {i} ch must be in range 0..29")
        if current_t < 0:
            raise HTTPException(status_code=422, detail=f"event {i} current_t must be >= 0")

        pattern_src = src["pattern"]
        if not isinstance(pattern_src, list) or not pattern_src:
            raise HTTPException(status_code=422, detail=f"event {i} pattern must be a non-empty list")

        pattern = []
        total_t = 0
        for j, step in enumerate(pattern_src):
            if not isinstance(step, dict):
                raise HTTPException(status_code=422, detail=f"event {i} pattern step {j} must be an object")
            if "val" not in step or "dur" not in step:
                raise HTTPException(status_code=422, detail=f"event {i} pattern step {j} missing val or dur")
            val = require_int(step["val"], f"event {i} pattern step {j} val must be an integer")
            dur = require_int(step["dur"], f"event {i} pattern step {j} dur must be an integer")
            if dur <= 0:
                raise HTTPException(status_code=422, detail=f"event {i} pattern step {j} dur must be > 0")
            if event_type == "gpio" and val not in {0, 1}:
                raise HTTPException(status_code=422, detail=f"event {i} pattern step {j} gpio val must be 0 or 1")
            if event_type == "pwm" and (val < 0 or val > 65535):
                raise HTTPException(status_code=422, detail=f"event {i} pattern step {j} pwm val must be in range 0..65535")
            pattern.append({"val": val, "dur": dur})
            total_t += dur

        if not reschedule and current_t > total_t:
            current_t = total_t

        event = {
            "type": event_type,
            "ch": ch,
            "current_t": current_t,
            "reschedule": reschedule,
            "pattern": pattern,
        }
        if "id" in src:
            if not isinstance(src["id"], str) or not src["id"]:
                raise HTTPException(status_code=422, detail=f"event {i} id must be a non-empty string")
            event["id"] = src["id"]
        events.append(event)

    return {"report_every": report_every, "events": events}


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
    try:
        return int(event.get("elapsed_t", event["current_t"]))
    except (KeyError, TypeError, ValueError):
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
    content = reduced.get("content")
    if not isinstance(content, dict):
        return reduced
    events = content.get("events")
    if not isinstance(events, list):
        return reduced
    reduced_events = []
    pins: dict[str, dict[str, Any]] = {}
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            reduced_events.append(event)
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
        event_id = str(item.get("id") or item.get("ch") or index)
        pins[event_id] = {
            "id": item.get("id"),
            "type": item.get("type"),
            "ch": item.get("ch"),
            "elapsed_t": item.get("elapsed_t"),
            "cycle_t": item.get("cycle_t"),
            "current_value": item.get("current_value"),
        }
        reduced_events.append(item)
    reduced["content"] = dict(content)
    reduced["content"]["events"] = reduced_events
    reduced["pins"] = pins
    return reduced


def state_with_current_values(state: dict[str, Any]) -> dict[str, Any]:
    events = state.get("events")
    if not isinstance(events, list):
        return state
    enriched = dict(state)
    enriched_events = []
    for event in events:
        if not isinstance(event, dict):
            enriched_events.append(event)
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
        enriched_events.append(item)
    enriched["events"] = enriched_events
    return enriched


def latest_timer_state(role: str) -> dict[str, Any] | None:
    snapshot = get_or_start_monitor(role).snapshot()
    report = snapshot.get("last_report")
    if not isinstance(report, dict):
        return None
    content = report.get("content")
    if not isinstance(content, dict):
        return None
    events = content.get("events")
    if not isinstance(events, list):
        return None
    state: dict[str, Any] = {"events": events}
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
        if isinstance(report, dict) and report.get("type") == "startup":
            self.publish("snapshot", snapshot)

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

        firmware_rc, firmware_out, firmware_err = run_command([mpremote, "connect", port, "cp", str(PICO_MAIN_FILE), ":main.py"], timeout=30)
        if firmware_rc != 0:
            command.error_status = 502
            command.error_detail = {"step": "firmware", "returncode": firmware_rc, "stdout": firmware_out, "stderr": firmware_err}
            command.done.set()
            LOGGER.error("pico monitor %s mpremote firmware copy failed: %s", self.role, command.error_detail)
            self.publish("error", {"role": self.role, "step": "firmware", "detail": command.error_detail})
            self.update_status("error", connected=False, port=port, error=command.error_detail)
            return None

        copy_rc, copy_out, copy_err = run_command([mpremote, "connect", port, "cp", str(command.path), ":state.json"], timeout=30)
        if copy_rc != 0:
            command.error_status = 502
            command.error_detail = {"step": "state", "returncode": copy_rc, "stdout": copy_out, "stderr": copy_err}
            command.done.set()
            LOGGER.error("pico monitor %s mpremote state copy failed: %s", self.role, command.error_detail)
            self.publish("error", {"role": self.role, "step": "state", "detail": command.error_detail})
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


def apply_timer_state(role: str, path: Path) -> dict[str, Any]:
    return get_or_start_monitor(role).apply(path)


def sse_message(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"


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
    latest = latest_timer_state(role)
    events = latest.get("events") if isinstance(latest, dict) else None
    return events if isinstance(events, list) else []


def configured_timer_roles() -> list[str]:
    try:
        return sorted(timer_roles())
    except HTTPException:
        return []


def configured_timer_channels() -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    try:
        config = load_config()
        roles = sorted(config.get("controllers", {}))
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


def git_output(args: list[str], *, repo_root: Path = REPO_ROOT) -> str | None:
    try:
        return subprocess.check_output(args, cwd=repo_root, text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


@lru_cache(maxsize=1)
def software_summary(*, repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    commit = git_output(["git", "rev-parse", "HEAD"], repo_root=repo_root)
    branch = git_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo_root=repo_root)
    status = git_output(["git", "status", "--short"], repo_root=repo_root)
    return {
        "name": "plamp",
        "git_commit": commit,
        "git_short_commit": commit[:7] if commit else None,
        "git_branch": branch,
        "git_dirty": None if status is None else bool(status),
    }


def settings_summary() -> dict[str, Any]:
    return {
        "host_time": host_time_summary(),
        "host": {
            "hostname": socket.gethostname(),
            "fqdn": socket.getfqdn(),
            "ips": host_ips(),
            "default_route": default_route(),
            "network": network_summary(),
        },
        "picos": enumerate_picos(),
        "tools": {
            "mpremote": shutil.which("mpremote"),
            "pyserial": getattr(serial, "VERSION", "unknown"),
        },
        "software": software_summary(),
        "cameras": {"rpicam": hardware_inventory.detect_rpicam_cameras()},
        "storage": storage_summary(REPO_ROOT),
        "monitors": monitor_summaries(),
        "state": {
            "path": str(STATE_FILE),
            "exists": STATE_FILE.exists(),
        },
        "log": {
            "path": str(LOG_FILE),
            "exists": LOG_FILE.exists(),
        },
    }


@app.get("/api/logs")
def get_logs(lines: int = Query(200, ge=1, le=1000)) -> dict[str, Any]:
    return {"path": str(LOG_FILE), "content": read_log_tail(lines)}


def config_response() -> dict[str, Any]:
    return {
        "config": load_config(),
        "detected": {
            "picos": enumerate_picos(),
            "cameras": normalized_detected_cameras(hardware_inventory.detect_rpicam_cameras()),
        },
    }


@app.get("/api/config")
def get_config() -> dict[str, Any]:
    return config_response()


def put_config_section(section: str, value: dict[str, Any]) -> dict[str, Any]:
    with config_lock:
        raw_config = load_raw_config()
        config = {name: raw_config.get(name, {}) for name in ("controllers", "devices", "cameras")}
        try:
            updated = apply_config_section(config, section, value)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        saved = dict(raw_config)
        saved.update(updated)
        atomic_write_json(CONFIG_FILE, saved)
    reconcile_configured_monitors()
    return config_response()


@app.put("/api/config/controllers")
def put_config_controllers(controllers: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return put_config_section("controllers", controllers)


@app.put("/api/config/devices")
def put_config_devices(devices: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return put_config_section("devices", devices)


@app.put("/api/config/cameras")
def put_config_cameras(cameras: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return put_config_section("cameras", cameras)


@app.get("/api/timer-config")
def get_timer_config() -> dict[str, Any]:
    return {"roles": configured_timer_roles(), "channels": configured_timer_channels(), "time_format": configured_time_format()}


@app.get("/api/host-time")
def get_host_time() -> dict[str, Any]:
    return host_time_summary()


@app.get("/api/camera/captures")
def get_camera_captures(
    source: str = "all",
    grow_id: str | None = None,
    limit: int = 24,
    offset: int = 0,
) -> dict[str, Any]:
    safe_limit = max(0, min(limit, 200))
    safe_offset = max(0, offset)
    captures = camera_capture.list_camera_captures(
        repo_root=camera_capture.REPO_ROOT,
        data_dir=camera_capture.DATA_DIR,
        grows_dir=camera_capture.GROWS_DIR,
        source=source,
        grow_id=grow_id,
        limit=safe_limit + 1,
        offset=safe_offset,
    )
    return {
        "captures": captures[:safe_limit],
        "limit": safe_limit,
        "offset": safe_offset,
        "has_more": len(captures) > safe_limit,
    }


@app.get("/api/camera/images/{image_key}")
def get_camera_image_by_key(image_key: str) -> FileResponse:
    image_path = camera_capture.resolve_capture_image_key(image_key, repo_root=camera_capture.REPO_ROOT)
    if image_path is None:
        raise HTTPException(status_code=404, detail="unknown camera image")
    return FileResponse(image_path, media_type="image/jpeg")


@app.post("/api/camera/captures")
def post_camera_capture() -> dict[str, Any]:
    try:
        return camera_capture.capture_camera_image(
            repo_root=camera_capture.REPO_ROOT,
            data_dir=camera_capture.DATA_DIR,
            config_file=camera_capture.CONFIG_FILE,
            grow_config_file=camera_capture.TRANSITIONAL_GROW_CONFIG_FILE,
        )
    except camera_capture.CameraCaptureError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@app.get("/api/camera/captures/{capture_id}/image")
def get_camera_capture_image(capture_id: str) -> FileResponse:
    image_path = camera_capture.find_capture_image(capture_id, data_dir=camera_capture.DATA_DIR)
    if image_path is None:
        raise HTTPException(status_code=404, detail=f"unknown camera capture: {capture_id}")
    return FileResponse(image_path, media_type="image/jpeg")


@app.post("/api/timers/{role}/channels/{channel_id}/schedule")
def post_timer_channel_schedule(role: str, channel_id: str, schedule: dict[str, Any] = Body(...)) -> dict[str, Any]:
    config = load_config()
    timer_role(role)
    current_state = state_for_role(role)
    channels = channel_metadata_for_role(role, config, current_state)
    try:
        updated = patch_channel_schedule(
            current_state,
            channels,
            channel_id,
            schedule,
            live_events=live_events_for_role(role),
            now=datetime.now().time(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    validated = validate_timer_state(updated)
    path = timer_state_path(role)
    with lock_for(role_locks, role):
        atomic_write_json(path, validated)
        sent = apply_timer_state(role, path)
    return {
        "role": role,
        "channel": channel_id,
        "success": True,
        "message": "schedule saved and sent to Pico",
        "pico": sent,
        "state": state_with_current_values(validated),
    }


@app.get("/api/timers/{role}", response_model=None)
def get_timer(role: str, stream: bool = Query(False)) -> Any:
    if stream:
        return stream_timer_events(role)
    return state_for_role(role)


@app.put("/api/timers/{role}")
def put_timer(role: str, state: dict[str, Any] = Body(...)) -> dict[str, Any]:
    path = timer_state_path(role)
    validated = validate_timer_state(state)
    with lock_for(role_locks, role):
        atomic_write_json(path, validated)
        sent = apply_timer_state(role, path)
    return {"role": role, "success": True, "message": "state saved and sent to Pico", "pico": sent}


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


@app.get("/timers/test", response_class=HTMLResponse)
def timer_test_page() -> HTMLResponse:
    return api_test_page_response()


@app.get("/settings.json")
def get_settings_json() -> dict[str, Any]:
    return settings_summary()


@app.get("/runtime")
def get_runtime() -> dict[str, Any]:
    return settings_summary()


@app.get("/config", response_class=HTMLResponse)
def get_config_page() -> HTMLResponse:
    data = config_response()
    return HTMLResponse(render_config_page(data["config"], data["detected"]))


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
        )
    )
