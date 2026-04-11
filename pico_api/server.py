from __future__ import annotations

import glob
import html
import json
import os
import re
import shutil
import socket
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_FILE = REPO_ROOT / "config.json"
TIMERS_DIR = REPO_ROOT / "timers"
STATE_FILE = REPO_ROOT / "pico_scheduler" / "state.json"
PICO_NAME_HINTS = ("pico", "rp2", "raspberry", "micropython")
RASPBERRY_PI_USB_VENDOR_ID = "2e8a"
ROLE_RE = re.compile(r"^[A-Za-z0-9_-]+$")

config_lock = threading.Lock()
role_locks: dict[str, threading.Lock] = {}
pico_locks: dict[str, threading.Lock] = {}

app = FastAPI(title="plamp Pico API")



def lock_for(mapping: dict[str, threading.Lock], key: str) -> threading.Lock:
    with config_lock:
        lock = mapping.get(key)
        if lock is None:
            lock = threading.Lock()
            mapping[key] = lock
        return lock


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


def load_config() -> dict[str, Any]:
    data = load_json_file(CONFIG_FILE)
    if not isinstance(data, dict):
        raise HTTPException(status_code=500, detail="config.json must be an object")
    timers = data.get("timers")
    if not isinstance(timers, list):
        raise HTTPException(status_code=500, detail="config.json timers must be a list")
    return data


def timer_roles() -> dict[str, dict[str, Any]]:
    roles: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(load_config()["timers"]):
        if not isinstance(item, dict):
            raise HTTPException(status_code=500, detail=f"config timer {index} must be an object")
        role = item.get("role")
        serial = item.get("pico_serial")
        if not isinstance(role, str) or not ROLE_RE.match(role):
            raise HTTPException(status_code=500, detail=f"config timer {index} has invalid role")
        if not isinstance(serial, str) or not serial:
            raise HTTPException(status_code=500, detail=f"config timer {role} missing pico_serial")
        roles[role] = item
    return roles


def role_for_serial(serial: str | None) -> str | None:
    if not serial:
        return None
    try:
        for role, item in timer_roles().items():
            if item.get("pico_serial") == serial:
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


def timer_state_path(role: str) -> Path:
    timer_role(role)
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

        if reschedule:
            current_t = current_t % total_t
        elif current_t > total_t:
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
    serial = timer_role(role)["pico_serial"]
    for pico in enumerate_picos():
        if pico.get("serial") == serial:
            return pico
    raise HTTPException(status_code=409, detail=f"Pico for role {role} is not connected: {serial}")


def apply_timer_state(role: str, path: Path) -> dict[str, Any]:
    pico = pico_for_role(role)
    port = pico["port"]
    mpremote = shutil.which("mpremote")
    if not mpremote:
        raise HTTPException(status_code=500, detail="mpremote not found")

    serial = str(pico["serial"])
    with lock_for(pico_locks, serial):
        copy_rc, copy_out, copy_err = run_command([mpremote, "connect", port, "cp", str(path), ":state.json"], timeout=30)
        if copy_rc != 0:
            raise HTTPException(status_code=502, detail={"step": "copy", "stdout": copy_out, "stderr": copy_err})
        reset_rc, reset_out, reset_err = run_command([mpremote, "connect", port, "reset"], timeout=15)
        if reset_rc != 0:
            raise HTTPException(status_code=502, detail={"step": "reset", "stdout": reset_out, "stderr": reset_err})

    return {"role": role, "port": port, "serial": serial, "copy_stdout": copy_out, "reset_stdout": reset_out}


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


def runtime_summary() -> dict[str, Any]:
    return {
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
        },
        "state": {
            "path": str(STATE_FILE),
            "exists": STATE_FILE.exists(),
        },
    }


def render_runtime_page(summary: dict[str, Any]) -> str:
    host = summary["host"]
    picos = summary["picos"]
    networks = host["network"]

    pico_rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(str(item.get('role') or '-'))}</td>"
        f"<td>{html.escape(str(item.get('port') or '-'))}</td>"
        f"<td>{html.escape(str(item.get('usb_device') or '-'))}</td>"
        f"<td>{html.escape(str(item.get('serial') or '-'))}</td>"
        f"<td>{html.escape(str(item.get('vendor_id') or '-'))}:{html.escape(str(item.get('product_id') or '-'))}</td>"
        "</tr>"
        for item in picos
    ) or '<tr><td colspan="5">No Picos found.</td></tr>'

    network_rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(str(item.get('device') or '-'))}</td>"
        f"<td>{html.escape(str(item.get('ipv4') or '-'))}</td>"
        f"<td>{html.escape(str(item.get('network') or '-'))}</td>"
        "</tr>"
        for item in networks
    ) or '<tr><td colspan="3">No network devices found.</td></tr>'

    software_rows = (
        "<tr>"
        "<td>mpremote</td>"
        f"<td><code>{html.escape(str(summary['tools']['mpremote'] or 'not found'))}</code></td>"
        "</tr>"
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Plamp node runtime</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; line-height: 1.4; }}
    table {{ border-collapse: collapse; margin: 1rem 0 2rem; width: 100%; max-width: 960px; }}
    th, td {{ border: 1px solid #ccc; padding: .45rem .6rem; text-align: left; }}
    th {{ background: #f4f4f4; }}
    code {{ background: #f4f4f4; padding: .1rem .25rem; }}
    footer {{ color: #555; font-size: .9rem; margin-top: 2rem; }}
  </style>
</head>
<body>
  <h1>Plamp node runtime</h1>
  <h2>Picos</h2>
  <table>
    <thead><tr><th>Role</th><th>Port</th><th>USB Device</th><th>Serial</th><th>USB ID</th></tr></thead>
    <tbody>{pico_rows}</tbody>
  </table>

  <h2>Network</h2>
  <p><strong>Hostname:</strong> {html.escape(host['hostname'])}</p>
  <table>
    <thead><tr><th>Device</th><th>IPv4</th><th>Network</th></tr></thead>
    <tbody>{network_rows}</tbody>
  </table>

  <h2>Software</h2>
  <table>
    <thead><tr><th>Tool</th><th>Path</th></tr></thead>
    <tbody>{software_rows}</tbody>
  </table>

  <footer>Refreshing in <span id="refresh-countdown">30</span>s</footer>
  <script>
    let seconds = 30;
    const countdown = document.getElementById("refresh-countdown");
    setInterval(() => {{
      seconds -= 1;
      if (seconds <= 0) {{
        window.location.reload();
        return;
      }}
      countdown.textContent = String(seconds);
    }}, 1000);
  </script>
</body>
</html>"""


def render_timer_test_page() -> str:
    try:
        roles = sorted(timer_roles())
    except HTTPException:
        roles = []
    default_role = roles[0] if roles else "pump_lights"
    role_options = "\n".join(f'<option value="{html.escape(role)}"></option>' for role in roles)
    default_payload = json.dumps(load_json_file(timer_state_path(default_role)), indent=2) if roles else "{}"
    default_get_curl = f"curl http://localhost:8000/api/timers/{default_role}"
    default_put_curl = "\n".join([
        f"curl -X PUT 'http://localhost:8000/api/timers/{default_role}?apply=false' " + chr(92),
        "  -H 'content-type: application/json' " + chr(92),
        "  --data-binary @- <<'JSON'",
        default_payload,
        "JSON",
    ])
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Timer API test</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; line-height: 1.4; }}
    fieldset {{ border: 1px solid #ccc; margin: 1rem 0 1.5rem; padding: 1rem; max-width: 980px; }}
    legend {{ font-weight: 700; }}
    label {{ display: block; margin: .6rem 0; }}
    input, textarea {{ box-sizing: border-box; padding: .35rem; }}
    textarea {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; min-height: 28rem; width: min(100%, 980px); }}
    button {{ border: 1px solid #222; border-radius: 6px; margin: .25rem .25rem .25rem 0; padding: .45rem .7rem; background: #fff; }}
    .row {{ display: flex; flex-wrap: wrap; gap: 1rem; margin: .75rem 0; }}
    .radio-row label {{ display: inline-block; margin-right: 1rem; }}
    pre {{ background: #f4f4f4; padding: 1rem; overflow: auto; }}
    #put-curl-command {{ white-space: pre-wrap; }}
  </style>
</head>
<body>
  <h1>Timer API test</h1>

  <h2>GET</h2>
  <fieldset>
    <legend>Read timer state</legend>
    <label>Role
      <input id="get-role" list="timer-roles" value="{html.escape(default_role)}">
    </label>
    <datalist id="timer-roles">{role_options}</datalist>
    <pre id="get-curl-command">{html.escape(default_get_curl)}</pre>
    <button id="get-state" type="button">GET current state</button>
    <div><span id="get-status">Ready.</span></div>
    <pre id="get-result">GET response will appear here.</pre>
  </fieldset>

  <h2>PUT</h2>
  <fieldset>
    <legend>Target</legend>
    <label>Role
      <input id="put-role" list="timer-roles" value="{html.escape(default_role)}">
    </label>
    <div class="radio-row">
      <label><input name="apply" type="radio" value="false" checked> Save only</label>
      <label><input name="apply" type="radio" value="true"> Save and reset</label>
    </div>
  </fieldset>

  <fieldset>
    <legend>Generate 5s pin test</legend>
    <label>Test pin <input id="test-pin" type="number" min="0" max="29" value="25"></label>
    <button id="generate-quick" type="button">Generate pin test</button>
  </fieldset>

  <fieldset>
    <legend>Generate pump/lights</legend>
    <div class="row">
      <label>Pump pin <input id="pump-pin" type="number" min="0" max="29" value="15"></label>
      <label>Pump on minutes <input id="pump-on" type="number" min="1" value="5"></label>
      <label>Pump off minutes <input id="pump-off" type="number" min="1" value="30"></label>
      <label>Lights pin <input id="lights-pin" type="number" min="0" max="29" value="2"></label>
      <label>Lights on <input id="lights-on" type="time" step="1" value="06:00:00"></label>
      <label>Lights off <input id="lights-off" type="time" step="1" value="18:00:00"></label>
    </div>
    <button id="generate-pump-lights" type="button">Generate pump/lights</button>
  </fieldset>

  <label>JSON payload
    <textarea id="payload">{html.escape(default_payload)}</textarea>
  </label>

  <h3>PUT curl</h3>
  <pre id="put-curl-command">{html.escape(default_put_curl)}</pre>
  <button id="put-state" type="button">PUT</button>
  <div><span id="put-status">Ready.</span></div>
  <pre id="put-result">PUT response will appear here.</pre>

  <script>
    const payload = document.getElementById("payload");
    const getRoleInput = document.getElementById("get-role");
    const putRoleInput = document.getElementById("put-role");

    function getRole() {{
      return getRoleInput.value.trim();
    }}

    function putRole() {{
      return putRoleInput.value.trim();
    }}

    function applyValue() {{
      return document.querySelector('input[name="apply"]:checked').value === "true";
    }}

    function secondsSinceMidnight() {{
      const now = new Date();
      return now.getHours() * 3600 + now.getMinutes() * 60 + now.getSeconds();
    }}

    function timeToSeconds(value) {{
      const [h, m, s] = value.split(":").map(Number);
      return h * 3600 + m * 60 + (s || 0);
    }}

    function currentTForWindow(start, stop) {{
      const startSeconds = timeToSeconds(start);
      const stopSeconds = timeToSeconds(stop);
      let onDur = (stopSeconds - startSeconds + 86400) % 86400;
      if (onDur === 0) onDur = 86400;
      let offDur = 86400 - onDur;
      if (offDur === 0) offDur = 1;
      return (secondsSinceMidnight() - startSeconds + onDur + offDur) % (onDur + offDur);
    }}

    function doubleQuote(value) {{
      return JSON.stringify(value);
    }}

    function getCurlCommand() {{
      return "curl " + doubleQuote(`${{window.location.origin}}/api/timers/${{encodeURIComponent(getRole())}}`);
    }}

    function putCurlCommand() {{
      const url = `${{window.location.origin}}/api/timers/${{encodeURIComponent(putRole())}}?apply=${{applyValue() ? "true" : "false"}}`;
      const slash = String.fromCharCode(92);
      const newline = String.fromCharCode(10);
      return [
        "curl -X PUT " + doubleQuote(url) + " " + slash,
        "  -H " + doubleQuote("content-type: application/json") + " " + slash,
        "  --data-binary @- <<'JSON'",
        payload.value,
        "JSON",
      ].join(newline);
    }}

    function updateCurl() {{
      document.getElementById("get-curl-command").textContent = getCurlCommand();
      document.getElementById("put-curl-command").textContent = putCurlCommand();
    }}

    function setPayload(state) {{
      payload.value = JSON.stringify(state, null, 2);
      document.getElementById("put-status").textContent = "Payload generated. Edit it, then PUT.";
      document.getElementById("put-result").textContent = "";
      updateCurl();
    }}

    async function getState() {{
      const getStatus = document.getElementById("get-status");
      const getResult = document.getElementById("get-result");
      getStatus.textContent = "";
      getResult.textContent = "";
      if (!window.confirm(`GET /api/timers/${{getRole()}}?`)) {{
        getStatus.textContent = "Cancelled.";
        return;
      }}
      getStatus.textContent = "Loading...";
      try {{
        const response = await fetch(`/api/timers/${{encodeURIComponent(getRole())}}`);
        const text = await response.text();
        let display = text;
        if (response.ok) {{
          const parsed = JSON.parse(text);
          display = JSON.stringify(parsed, null, 2);
          payload.value = display;
          putRoleInput.value = getRole();
          updateCurl();
        }}
        getStatus.textContent = `${{response.status}} ${{response.statusText}}`;
        getResult.textContent = display;
      }} catch (error) {{
        getStatus.textContent = "Request failed.";
        getResult.textContent = String(error);
      }}
    }}

    async function putState() {{
      const putStatus = document.getElementById("put-status");
      const putResult = document.getElementById("put-result");
      putStatus.textContent = "";
      putResult.textContent = "";
      const url = `/api/timers/${{encodeURIComponent(putRole())}}?apply=${{applyValue() ? "true" : "false"}}`;
      if (!window.confirm(`PUT ${{url}}?`)) {{
        putStatus.textContent = "Cancelled.";
        return;
      }}
      let parsed;
      try {{
        parsed = JSON.parse(payload.value);
      }} catch (error) {{
        putStatus.textContent = "Invalid JSON.";
        putResult.textContent = String(error);
        return;
      }}
      putStatus.textContent = "Saving...";
      const controller = new AbortController();
      const timeout = window.setTimeout(() => controller.abort(), 30000);
      try {{
        const response = await fetch(url, {{
          method: "PUT",
          headers: {{"content-type": "application/json"}},
          body: JSON.stringify(parsed),
          signal: controller.signal,
        }});
        const text = await response.text();
        let display = text;
        try {{
          display = JSON.stringify(JSON.parse(text), null, 2);
        }} catch (error) {{
        }}
        putStatus.textContent = `${{response.status}} ${{response.statusText}}`;
        putResult.textContent = display;
      }} catch (error) {{
        putStatus.textContent = "Request failed.";
        putResult.textContent = String(error);
      }} finally {{
        window.clearTimeout(timeout);
      }}
    }}

    document.getElementById("generate-quick").addEventListener("click", () => {{
      setPayload({{
        report_every: 10,
        events: [{{
          id: "test_pin",
          type: "gpio",
          ch: Number(document.getElementById("test-pin").value),
          current_t: 0,
          reschedule: 1,
          pattern: [{{val: 1, dur: 5}}, {{val: 0, dur: 5}}],
        }}],
      }});
    }});

    document.getElementById("generate-pump-lights").addEventListener("click", () => {{
      const lightsOn = document.getElementById("lights-on").value;
      const lightsOff = document.getElementById("lights-off").value;
      let lightsOnDur = (timeToSeconds(lightsOff) - timeToSeconds(lightsOn) + 86400) % 86400;
      if (lightsOnDur === 0) lightsOnDur = 86400;
      let lightsOffDur = 86400 - lightsOnDur;
      if (lightsOffDur === 0) lightsOffDur = 1;
      setPayload({{
        report_every: 10,
        events: [
          {{
            id: "pump",
            type: "gpio",
            ch: Number(document.getElementById("pump-pin").value),
            current_t: 0,
            reschedule: 1,
            pattern: [
              {{val: 1, dur: Number(document.getElementById("pump-on").value) * 60}},
              {{val: 0, dur: Number(document.getElementById("pump-off").value) * 60}},
            ],
          }},
          {{
            id: "lights",
            type: "gpio",
            ch: Number(document.getElementById("lights-pin").value),
            current_t: currentTForWindow(lightsOn, lightsOff),
            reschedule: 1,
            pattern: [{{val: 1, dur: lightsOnDur}}, {{val: 0, dur: lightsOffDur}}],
          }},
        ],
      }});
    }});

    document.getElementById("get-state").addEventListener("click", getState);
    document.getElementById("put-state").addEventListener("click", putState);
    getRoleInput.addEventListener("input", updateCurl);
    putRoleInput.addEventListener("input", updateCurl);
    payload.addEventListener("input", updateCurl);
    for (const item of document.querySelectorAll('input[name="apply"]')) {{
      item.addEventListener("change", updateCurl);
    }}
    updateCurl();
  </script>
</body>
</html>"""


@app.get("/api/timers/{role}")
def get_timer(role: str) -> dict[str, Any]:
    path = timer_state_path(role)
    state = load_json_file(path)
    return validate_timer_state(state)


@app.put("/api/timers/{role}")
def put_timer(role: str, state: dict[str, Any] = Body(...), apply: bool = Query(True)) -> dict[str, Any]:
    path = timer_state_path(role)
    validated = validate_timer_state(state)
    with lock_for(role_locks, role):
        atomic_write_json(path, validated)
        applied: dict[str, Any] | None = None
        if apply:
            applied = apply_timer_state(role, path)
    if applied is None:
        return {"role": role, "saved": True, "apply_requested": False, "apply_status": "skipped"}
    return {"role": role, "saved": True, "apply_requested": True, "apply_status": "ok", "pico": applied}


@app.get("/timers/test", response_class=HTMLResponse)
def timer_test_page() -> HTMLResponse:
    return HTMLResponse(render_timer_test_page())


@app.get("/runtime")
def get_runtime() -> dict[str, Any]:
    return runtime_summary()


@app.get("/", response_class=HTMLResponse)
def get_runtime_page() -> HTMLResponse:
    return HTMLResponse(render_runtime_page(runtime_summary()))
