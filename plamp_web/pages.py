from __future__ import annotations

import html
import json
import re
from typing import Any

GITHUB_REPO_URL = "https://github.com/hugomatic/plamp"
GITHUB_NEW_ISSUE_URL = f"{GITHUB_REPO_URL}/issues/new"
FAVICON_LINK = '<link rel="icon" href="/favicon.svg" type="image/svg+xml">'
APP_REVISION = "unknown"


def set_app_revision(revision: str | None) -> None:
    global APP_REVISION
    APP_REVISION = revision or "unknown"


def main_nav(controller_ids: list[str] | None = None, revision: str | None = None) -> str:
    links = ['<a href="/">Plamp</a>']
    for controller_id in controller_ids or []:
        links.append(
            '<a href="/controllers/{href}">{label}</a>'.format(
                href=html.escape(controller_id, quote=True),
                label=html.escape(controller_id),
            )
        )
    links.extend([
        '<a href="/settings">Settings</a>',
        '<a href="/system">System</a>',
        '<a href="/api/test">API test</a>',
    ])
    revision = revision or APP_REVISION
    revision_text = html.escape(revision)
    if revision == "unknown":
        links.append(f"[rev {revision_text}]")
    else:
        revision_href = html.escape(revision, quote=True)
        links.append(f'<a href="{GITHUB_REPO_URL}/commit/{revision_href}">[rev {revision_text}]</a>')
    return "<nav>" + " | ".join(links) + "</nav>"



def normalize_camera_key(value: Any) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", str(value or "").strip())


def camera_model_label(item: dict[str, Any]) -> str:
    raw_model = str(item.get("model") or "")
    sensor = str(item.get("sensor") or raw_model.split("_", 1)[0]).lower()
    lens = str(item.get("lens") or "").lower()
    raw_lower = raw_model.lower()
    wide = "wide" in lens or "wide" in raw_lower
    model_by_sensor = {
        "imx708": "Camera Module 3 Wide" if wide else "Camera Module 3",
        "imx219": "Camera Module 2",
        "ov5647": "Camera Module 1",
        "imx477": "HQ Camera",
        "imx296": "Global Shutter Camera",
    }
    return model_by_sensor.get(sensor, raw_model or "-")


def camera_detected_matches(configured_cameras: dict[str, Any], detected_cameras: list[dict[str, Any]]) -> tuple[dict[str, str], list[str]]:
    detected_by_key = {str(item.get("key")): item for item in detected_cameras if isinstance(item, dict) and item.get("key")}
    unmatched_detected_keys = list(detected_by_key)
    matches: dict[str, str] = {}

    for camera_id, camera in configured_cameras.items():
        camera = camera if isinstance(camera, dict) else {}
        detected_key = normalize_camera_key(camera.get("detected_key"))
        if detected_key and detected_key in detected_by_key:
            matches[camera_id] = detected_key
        elif camera_id in detected_by_key:
            matches[camera_id] = camera_id
        else:
            continue
        if matches[camera_id] in unmatched_detected_keys:
            unmatched_detected_keys.remove(matches[camera_id])

    for camera_id in configured_cameras:
        if camera_id in matches or not unmatched_detected_keys:
            continue
        matches[camera_id] = unmatched_detected_keys.pop(0)

    return matches, unmatched_detected_keys


def option_tag(value: str, label: str, selected: str | None) -> str:
    selected_attr = " selected" if value == selected else ""
    return f'<option value="{html.escape(value)}"{selected_attr}>{html.escape(label)}</option>'


def controller_options(controllers: dict[str, Any], selected: str | None) -> str:
    return "\n".join(option_tag(key, key, selected) for key in controllers)


def controller_type_options(selected: str | None) -> str:
    selected = selected or "pico_scheduler"
    return option_tag("pico_scheduler", "pico_scheduler", selected)


def scheduler_controllers(controllers: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in controllers.items()
        if isinstance(value, dict) and str(value.get("type") or "pico_scheduler") == "pico_scheduler"
    }


def peripheral_assignments(controllers: dict[str, Any]) -> dict[str, list[str]]:
    assignments: dict[str, list[str]] = {}
    for controller_id, controller in controllers.items():
        if not isinstance(controller, dict):
            continue
        serial = str(controller.get("config", {}).get("pico_serial") or "")
        if not serial:
            continue
        assignments.setdefault(serial, []).append(controller_id)
    return assignments


def pico_options(picos: list[dict[str, Any]], selected: str | None) -> str:
    options = [option_tag("", "Unassigned", selected)]
    seen = set()
    for pico in picos:
        serial = str(pico.get("serial") or "")
        if not serial:
            continue
        seen.add(serial)
        label = f"{serial} {pico.get('port') or ''}".strip()
        options.append(option_tag(serial, label, selected))
    if selected and selected not in seen:
        options.append(option_tag(selected, f"{selected} (not detected)", selected))
    return "\n".join(options)


def camera_peripheral_options(detected_cameras: list[dict[str, Any]], selected: str | None) -> str:
    options = [option_tag("", "Unassigned", selected)]
    seen: set[str] = set()
    for item in detected_cameras:
        if not isinstance(item, dict):
            continue
        detected_key = normalize_camera_key(item.get("key"))
        if not detected_key:
            continue
        seen.add(detected_key)
        model = camera_model_label(item)
        lens = str(item.get("lens") or "").strip()
        label = f"{detected_key} | {model}" if not lens else f"{detected_key} | {model} | {lens}"
        options.append(option_tag(detected_key, label, selected))
    if selected and selected not in seen:
        options.append(option_tag(selected, f"{selected} (not detected)", selected))
    return "\n".join(options)


def pin_type_options(selected: str | None) -> str:
    return "".join(option_tag(value, value, selected or "gpio") for value in ["gpio", "pwm"])


def controller_payload(controller: dict[str, Any]) -> dict[str, Any]:
    payload = controller.get("payload") if isinstance(controller.get("payload"), dict) else {}
    config = controller.get("config") if isinstance(controller.get("config"), dict) else {}
    if payload:
        return payload
    return {key: value for key, value in {"pico_serial": config.get("pico_serial")}.items() if value not in (None, "")}


def controller_settings(controller: dict[str, Any]) -> dict[str, Any]:
    settings = controller.get("settings") if isinstance(controller.get("settings"), dict) else {}
    config = controller.get("config") if isinstance(controller.get("config"), dict) else {}
    result = dict(settings)
    if "label" not in result and config.get("label"):
        result["label"] = config.get("label")
    return result


def scheduler_devices_by_controller(controllers: dict[str, Any]) -> list[tuple[str, dict[str, Any], list[tuple[str, dict[str, Any]]]]]:
    groups: list[tuple[str, dict[str, Any], list[tuple[str, dict[str, Any]]]]] = []
    for controller_id, controller in controllers.items():
        if not isinstance(controller, dict):
            continue
        settings = controller_settings(controller)
        devices = settings.get("devices") if isinstance(settings.get("devices"), dict) else {}
        legacy_devices = controller.get("devices") if isinstance(controller.get("devices"), dict) else {}
        payload = controller_payload(controller)
        payload_devices = payload.get("devices") if isinstance(payload.get("devices"), list) else []
        payload_by_pin = {
            item.get("pin"): item
            for item in payload_devices
            if isinstance(item, dict) and isinstance(item.get("pin"), int)
        }
        controller_devices = []
        for device_id, device in (devices or legacy_devices).items():
            if not isinstance(device, dict):
                continue
            if "config" in device or "settings" in device:
                config = device.get("config") if isinstance(device.get("config"), dict) else {}
                device_settings = device.get("settings") if isinstance(device.get("settings"), dict) else {}
                schedule = device_settings.get("schedule") if isinstance(device_settings.get("schedule"), dict) else {}
                enriched = {
                    "pin": config.get("pin"),
                    "label": config.get("label"),
                    "output_type": config.get("output_type", "gpio"),
                    "visibility": config.get("visibility", "visible"),
                    "programming": device_settings.get("programming", "enabled"),
                    "editor": schedule,
                }
            else:
                enriched = dict(device)
            payload_device = payload_by_pin.get(enriched.get("pin"))
            if isinstance(payload_device, dict) and "output_type" not in enriched:
                enriched["output_type"] = payload_device.get("type", "gpio")
            controller_devices.append((device_id, enriched))
        controller_devices.sort(
            key=lambda item: (
                item[1].get("display_order") if isinstance(item[1].get("display_order"), int) else len(controller_devices),
                item[0],
            )
        )
        if controller_devices:
            groups.append((controller_id, controller, controller_devices))
    return groups


def hidden_scheduler_controllers(
    controllers: dict[str, Any],
    scheduler_groups: list[tuple[str, dict[str, Any], list[tuple[str, dict[str, Any]]]]],
) -> dict[str, Any]:
    visible_controller_ids = {controller_id for controller_id, _, _ in scheduler_groups}
    return {
        controller_id: controller
        for controller_id, controller in controllers.items()
        if isinstance(controller, dict) and controller_id not in visible_controller_ids and str(controller.get("type") or "pico_scheduler") == "pico_scheduler"
    }


def json_script_text(value: Any) -> str:
    return json.dumps(value).replace("</", "<\\/")


def render_config_page(config: dict[str, Any], detected: dict[str, Any]) -> str:
    controllers = config.get("controllers") if isinstance(config.get("controllers"), dict) else {}
    devices = {
        device_id: {**device, "controller": controller_id}
        for controller_id, controller in controllers.items()
        if isinstance(controller, dict)
        for device_id, device in (controller.get("devices") or {}).items()
        if isinstance(device_id, str) and isinstance(device, dict)
    }
    cameras = config.get("cameras") if isinstance(config.get("cameras"), dict) else {}
    picos = detected.get("picos") if isinstance(detected.get("picos"), list) else []
    raw_detected_cameras = detected.get("cameras") if isinstance(detected.get("cameras"), list) else []
    detected_cameras = []
    for item in raw_detected_cameras:
        if not isinstance(item, dict):
            continue
        normalized = dict(item)
        key = normalize_camera_key(item.get("key"))
        if key:
            normalized["key"] = key
        detected_cameras.append(normalized)

    controller_rows = []
    for controller_id in controllers:
        controller = controllers.get(controller_id, {})
        if not isinstance(controller, dict):
            continue
        controller_rows.append(
            '<tr class="controller-row" data-controller-key="{controller_id}">'
            '<td><input class="controller-id" placeholder="pump_lights" value="{controller_id}"></td>'
            '<td><select class="controller-pico-serial">{pico_options_html}</select></td>'
            '</tr>'.format(
                controller_id=html.escape(controller_id, quote=True),
                pico_options_html=pico_options(picos, str(controller.get("config", {}).get("pico_serial") or "")),
            )
        )
    controller_rows.append(
        '<tr class="controller-row new-row" data-controller-key="">'
        '<td><input class="controller-id" placeholder="pump_lights" value=""></td>'
        '<td><select class="controller-pico-serial">{pico_options_html}</select></td>'
        '</tr>'.format(pico_options_html=pico_options(picos, ""))
    )

    device_rows = []
    for device_id in devices:
        device = devices.get(device_id, {})
        if not isinstance(device, dict):
            continue
        device_rows.append(
            '<tr class="device-row" data-device-id="{device_id}">'
            '<td><input class="device-id" placeholder="pump" value="{device_id}"></td>'
            '<td><select class="device-controller">{controller_options_html}</select></td>'
            '<td><input class="device-pin" type="number" min="0" max="29" value="{pin}"></td>'
            '<td><select class="device-type">{type_options}</select></td>'
            '<td><select class="device-editor">{editor_options}</select></td>'
            '</tr>'.format(
                device_id=html.escape(device_id, quote=True),
                controller_options_html=controller_options(controllers, str(device.get("controller") or "")),
                pin=html.escape(str(device.get("config", {}).get("pin") if device.get("config", {}).get("pin") is not None else ""), quote=True),
                type_options=pin_type_options(str(device.get("config", {}).get("output_type") or "gpio")),
                editor_options="".join(option_tag(value, value, "disabled" if device.get("settings", {}).get("programming") == "disabled" else ("clock_window" if device.get("settings", {}).get("schedule", {}).get("kind") == "daily_window" else "cycle")) for value in ["cycle", "clock_window", "disabled", "hidden"]),
            )
        )
    device_rows.append(
        '<tr class="device-row new-row" data-device-id="">'
        '<td><input class="device-id" placeholder="pump" value=""></td>'
        '<td><select class="device-controller">{controller_options_html}</select></td>'
        '<td><input class="device-pin" type="number" min="0" max="29" value=""></td>'
        '<td><select class="device-type">{type_options}</select></td>'
        '<td><select class="device-editor">{editor_options}</select></td>'
        '</tr>'.format(
            controller_options_html=controller_options(controllers, ""),
            type_options=pin_type_options("gpio"),
            editor_options="".join(option_tag(value, value, "cycle") for value in ["cycle", "clock_window", "disabled", "hidden"]),
        )
    )

    detected_camera_keys = [
        str(item.get("key"))
        for item in detected_cameras
        if isinstance(item, dict) and item.get("key")
    ]
    all_camera_keys = sorted(set(cameras) | set(detected_camera_keys))
    camera_rows = []
    for camera_id in all_camera_keys:
        detected_camera = next(
            (item for item in detected_cameras if isinstance(item, dict) and str(item.get("key")) == camera_id),
            {},
        )
        detail = " ".join(part for part in [camera_model_label(detected_camera), str(detected_camera.get("lens") or "")] if part and part != "-")
        camera_rows.append(
            '<tr class="camera-row" data-camera-key="{camera_id}">'
            '<td><input class="camera-id" placeholder="rpicam_cam0" value="{camera_id}"></td>'
            '<td class="muted">{detail}</td>'
            '</tr>'.format(
                camera_id=html.escape(camera_id, quote=True),
                detail=html.escape(f"Detected: {detail}" if detail else "Configured"),
            )
        )
    camera_rows.append(
        '<tr class="camera-row new-row" data-camera-key="" data-camera-detected-key="">'
        '<td><input class="camera-id" placeholder="rpicam_cam0" value=""></td>'
        '<td class="muted">Add a camera id to save it.</td>'
        '</tr>'
    )

    controller_rows_html = "\n".join(controller_rows)
    device_rows_html = "\n".join(device_rows)
    camera_rows_html = "\n".join(camera_rows)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Plamp config</title>
  {FAVICON_LINK}
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; line-height: 1.4; }}
    table {{ border-collapse: collapse; margin: 1rem 0 2rem; width: 100%; max-width: 1100px; }}
    th, td {{ border: 1px solid #ccc; padding: .45rem .6rem; text-align: left; vertical-align: top; }}
    th {{ background: #f4f4f4; }}
    input, select {{ box-sizing: border-box; max-width: 100%; padding: .35rem; }}
    button {{ border: 1px solid #222; border-radius: 6px; margin: .4rem .4rem .4rem 0; padding: .45rem .7rem; background: #fff; }}
    code {{ background: #f4f4f4; padding: .1rem .25rem; }}
    .muted, .status {{ color: #555; font-size: .9rem; }}
  </style>
</head>
<body>
  {main_nav()}
  <h1>Plamp config</h1>
  <h2>Controllers</h2>
  <table><thead><tr><th>ID</th><th>Assigned Pico</th></tr></thead><tbody>{controller_rows_html}</tbody></table>
  <button id="save-controllers" type="button">Save controllers</button> <span id="controllers-status" class="status">Ready.</span>
  <h2>Devices</h2>
  <table><thead><tr><th>ID</th><th>Controller</th><th>Pin</th><th>Type</th><th>Editor</th></tr></thead><tbody>{device_rows_html}</tbody></table>
  <button id="save-devices" type="button">Save devices</button> <span id="devices-status" class="status">Ready.</span>
  <h2>Cameras</h2>
  <table><thead><tr><th>ID</th><th>Detected</th></tr></thead><tbody>{camera_rows_html}</tbody></table>
  <button id="save-cameras" type="button">Save cameras</button> <span id="cameras-status" class="status">Ready.</span>
  <script>
    function collectControllers() {{
      const result = {{}};
      for (const row of document.querySelectorAll(".controller-row")) {{
        const key = row.querySelector(".controller-id").value.trim();
        if (!key) continue;
        const picoSerial = row.querySelector(".controller-pico-serial").value;
        result[key] = {{type: "pico_scheduler", config: picoSerial ? {{pico_serial: picoSerial}} : {{}}, settings: {{report_every: 10}}, devices: {{}}}};
      }}
      return result;
    }}
    function collectDevices() {{
      const result = {{}};
      for (const row of document.querySelectorAll(".device-row")) {{
        const key = row.querySelector(".device-id").value.trim();
        if (!key) continue;
        const pinValue = row.querySelector(".device-pin").value;
        const controller = row.querySelector(".device-controller").value;
        if (!controller) continue;
        const editor = row.querySelector(".device-editor").value;
        const settings = editor === "disabled"
          ? {{programming: "disabled", schedule: {{kind: "cycle"}}}}
          : editor === "clock_window"
            ? {{schedule: {{kind: "daily_window", on_time: "06:00", off_time: "18:00"}}}}
            : {{schedule: {{kind: "cycle"}}}};
        result[key] = {{controller, type: "scheduled_output", config: {{pin: pinValue === "" ? null : Number(pinValue), output_type: row.querySelector(".device-type").value, visibility: editor === "hidden" ? "hidden" : "visible"}}, settings}};
      }}
      return result;
    }}
    function collectCameras() {{
      const result = {{}};
      for (const row of document.querySelectorAll(".camera-row")) {{
        const key = row.querySelector(".camera-id").value.trim();
        if (!key) continue;
        result[key] = {{}};
      }}
      return result;
    }}
    function collectConfig() {{
      const controllers = collectControllers();
      for (const [deviceId, device] of Object.entries(collectDevices())) {{
        const controller = controllers[device.controller];
        if (!controller) continue;
        const payload = {{...device}};
        delete payload.controller;
        controller.devices[deviceId] = payload;
      }}
      return {{controllers, cameras: collectCameras()}};
    }}
    async function saveSection(statusId, url, payload) {{
      const status = document.getElementById(statusId);
      status.textContent = "Saving...";
      const response = await fetch(url, {{method: "PUT", headers: {{"content-type": "application/json"}}, body: JSON.stringify(payload)}});
      status.textContent = response.ok ? "Saved." : `${{response.status}} ${{await response.text()}}`;
    }}
    document.getElementById("save-controllers").addEventListener("click", () => saveSection("controllers-status", "/api/config", collectConfig()));
    document.getElementById("save-devices").addEventListener("click", () => saveSection("devices-status", "/api/config", collectConfig()));
    document.getElementById("save-cameras").addEventListener("click", () => saveSection("cameras-status", "/api/config/cameras", collectCameras()));
  </script>
</body>
</html>"""


def render_api_test_page(roles: list[str], default_role: str, default_payload: str, time_format: str, hostname: str = "", controller_ids: list[str] | None = None) -> str:
    page_title = f"{hostname} API test" if hostname else "Plamp API test"
    role_options = "\n".join(f'<option value="{html.escape(role)}"></option>' for role in roles)
    default_get_curl = f"curl http://localhost:8000/api/controllers/{default_role}"
    default_stream_curl = f"curl -N 'http://localhost:8000/api/controllers/{default_role}?stream=true'"
    default_status_paths = [f"config.controllers.{default_role}", f"controllers.{default_role}.telemetry"] if default_role else []
    default_status_path_rows = "".join(
        f'<div class="row status-path-row"><label>Path <input class="status-path-input" value="{html.escape(path, quote=True)}" placeholder="controllers.{html.escape(default_role, quote=True)}.telemetry"></label><button type="button" class="remove-status-path">Remove</button></div>'
        for path in default_status_paths
    )
    cycle_schedule_example = html.escape(json.dumps({"mode": "cycle", "on_seconds": 300, "off_seconds": 2400, "start_at_seconds": 0}, separators=(",", ":")))
    clock_schedule_example = html.escape(json.dumps({"mode": "clock_window", "on_time": "06:00", "off_time": "23:00"}, separators=(",", ":")))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(page_title)}</title>
  {FAVICON_LINK}
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; line-height: 1.4; }}
    fieldset {{ border: 1px solid #ccc; margin: 1rem 0 1.5rem; padding: 1rem; max-width: 980px; }}
    legend {{ font-weight: 700; }}
    label {{ display: block; margin: .6rem 0; }}
    input, textarea {{ box-sizing: border-box; padding: .35rem; }}
    textarea {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; min-height: 28rem; width: min(100%, 980px); }}
    textarea.compact-json {{ min-height: 12rem; }}
    button {{ border: 1px solid #222; border-radius: 6px; margin: .25rem .25rem .25rem 0; padding: .45rem .7rem; background: #fff; }}
    .row {{ display: flex; flex-wrap: wrap; gap: 1rem; margin: .75rem 0; }}
    .radio-row label {{ display: inline-block; margin-right: 1rem; }}
    .helper-title {{ font-weight: 700; margin: .75rem 0 .25rem; }}
    pre {{ background: #f4f4f4; padding: 1rem; overflow: auto; }}
    #stream-curl-command {{ white-space: pre-wrap; }}
    #camera-capture-preview {{ display: block; margin-top: 1rem; max-width: min(100%, 720px); }}
    #camera-capture-preview[hidden] {{ display: none; }}
    #stream-result {{ max-height: 18rem; white-space: pre-wrap; }}
    .status-board {{ display: grid; gap: .75rem; margin: .75rem 0; max-width: 980px; }}
    .timer-card {{ border: 1px solid #ccc; border-radius: 6px; padding: .75rem; }}
    .timer-top {{ align-items: baseline; display: flex; gap: .75rem; justify-content: space-between; }}
    .timer-name {{ font-weight: 700; }}
    .timer-value {{ border-radius: 6px; padding: .15rem .45rem; }}
    .timer-value.on {{ background: #d9f7d9; }}
    .timer-value.off {{ background: #eee; }}
    .timer-meta {{ color: #555; font-size: .9rem; margin: .25rem 0 .5rem; }}
    .timer-bar {{ background: #eee; border-radius: 6px; height: .65rem; overflow: hidden; }}
    .timer-fill {{ background: #3b7f4a; height: 100%; width: 0; }}
    .timer-fill.off {{ background: #888; }}
  </style>
</head>
<body>
  {main_nav(controller_ids)}
  <h1>{html.escape(page_title)}</h1>
  <p>This page is the human-friendly API guide. For machine-readable integration, use <a href="/openapi.json"><code>/openapi.json</code></a>. For interactive FastAPI docs, use <a href="/docs"><code>/docs</code></a>.</p>
  <datalist id="timer-roles">{role_options}</datalist>

  <h2>Camera</h2>
  <fieldset>
    <legend>POST /api/camera/captures</legend>
    <p>Captures a new image and returns capture metadata. Uses the in-process Picamera2 worker.</p>
    <label>Camera ID (optional) <input id="camera-capture-camera-id" placeholder="rpicam_cam0"></label>
    <pre id="camera-capture-curl-command">curl -X POST http://localhost:8000/api/camera/captures</pre>
    <button class="copy-curl" type="button" data-copy-target="camera-capture-curl-command">Copy curl</button>
    <button id="camera-capture" type="button">Run request</button>
    <div><span id="camera-capture-status">Ready.</span></div>
    <pre id="camera-capture-result">POST response will appear here.</pre>
    <img id="camera-capture-preview" alt="Latest camera capture preview" hidden>
  </fieldset>

  <fieldset>
    <legend>GET /api/camera/captures</legend>
    <p>Lists captures newest first. Options: camera_id, limit and offset.</p>
    <div class="row">
      <label>Camera ID <input id="list-captures-camera-id" placeholder="rpicam_cam0"></label>
      <label>Limit <input id="list-captures-limit" type="number" min="0" max="200" step="1" value="10"></label>
      <label>Offset <input id="list-captures-offset" type="number" min="0" step="1" value="0"></label>
    </div>
    <pre id="list-captures-curl-command">curl http://localhost:8000/api/camera/captures?limit=10&amp;offset=0</pre>
    <button class="copy-curl" type="button" data-copy-target="list-captures-curl-command">Copy curl</button>
    <button id="list-captures" type="button">Run request</button>
    <div><span id="list-captures-status">Ready.</span></div>
    <pre id="list-captures-result">GET response will appear here.</pre>
  </fieldset>

  <h2>Config</h2>
  <fieldset>
    <legend>GET /api/config</legend>
    <p>Reads persisted desired config only.</p>
    <pre id="get-config-curl-command">curl http://localhost:8000/api/config</pre>
    <button class="copy-curl" type="button" data-copy-target="get-config-curl-command">Copy curl</button>
    <button id="get-config" type="button">Run request</button>
    <div><span id="get-config-status">Ready.</span></div>
    <pre id="get-config-result">GET response will appear here.</pre>
  </fieldset>
  <fieldset>
    <legend>PUT /api/config</legend>
    <p>Saves controllers and cameras together. Scheduler devices live inside each controller.</p>
    <pre id="put-config-curl-command">curl -X PUT http://localhost:8000/api/config -H 'content-type: application/json' --data '{{"controllers":{{}},"cameras":{{}}}}'</pre>
    <button class="copy-curl" type="button" data-copy-target="put-config-curl-command">Copy curl</button>
    <button id="put-config" type="button">Run request</button>
    <div><span id="put-config-status">Ready.</span></div>
    <pre id="put-config-result">PUT response will appear here.</pre>
  </fieldset>
  <fieldset>
    <legend>PUT /api/config/cameras</legend>
    <p>Saves camera names and user-confirmed IR filter values.</p>
    <pre id="put-config-cameras-curl-command">curl -X PUT http://localhost:8000/api/config/cameras -H 'content-type: application/json' --data '{{}}'</pre>
    <button class="copy-curl" type="button" data-copy-target="put-config-cameras-curl-command">Copy curl</button>
    <button id="put-config-cameras" type="button">Run request</button>
    <div><span id="put-config-cameras-status">Ready.</span></div>
    <pre id="put-config-cameras-result">PUT response will appear here.</pre>
  </fieldset>
  <fieldset>
    <legend>PUT /api/config/controllers</legend>
    <p>Saves named local Pico controllers.</p>
    <pre id="put-config-controllers-curl-command">curl -X PUT http://localhost:8000/api/config/controllers -H 'content-type: application/json' --data '{{}}'</pre>
    <button class="copy-curl" type="button" data-copy-target="put-config-controllers-curl-command">Copy curl</button>
    <button id="put-config-controllers" type="button">Run request</button>
    <div><span id="put-config-controllers-status">Ready.</span></div>
    <pre id="put-config-controllers-result">PUT response will appear here.</pre>
  </fieldset>
  <fieldset>
    <legend>GET /api/system</legend>
    <p>Reads host facts and detected local hardware choices.</p>
    <pre id="get-system-curl-command">curl http://localhost:8000/api/system</pre>
    <button class="copy-curl" type="button" data-copy-target="get-system-curl-command">Copy curl</button>
    <button id="get-system" type="button">Run request</button>
    <div><span id="get-system-status">Ready.</span></div>
    <pre id="get-system-result">GET response will appear here.</pre>
  </fieldset>

  <h2>Status</h2>

  <fieldset>
    <legend>Status paths</legend>
    <p>These paths are shared by the filtered GET and streaming GET views below.</p>
    <div id="status-path-list">{default_status_path_rows}</div>
    <button id="add-status-path" type="button">Add path</button>
  </fieldset>

  <fieldset>
    <legend>GET /api/status</legend>
    <p>Reads filtered status nodes for one or more paths. Leave the list empty to read the full status tree.</p>
    <pre id="get-status-curl-command">curl http://localhost:8000/api/status</pre>
    <button class="copy-curl" type="button" data-copy-target="get-status-curl-command">Copy curl</button>
    <button id="get-status" type="button">Run request</button>
    <div><span id="get-status-status">Ready.</span></div>
    <pre id="get-status-result">GET response will appear here.</pre>
  </fieldset>

  <fieldset>
    <legend>GET /api/status?stream=true</legend>
    <p>Streams filtered status updates with server-sent events.</p>
    <pre id="stream-status-curl-command">curl -N http://localhost:8000/api/status?stream=true</pre>
    <button class="copy-curl" type="button" data-copy-target="stream-status-curl-command">Copy curl</button>
    <label><input id="stream-pretty" type="checkbox" checked> Pretty JSON</label>
    <button id="start-stream" type="button">Start stream</button>
    <button id="stop-stream" type="button">Stop stream</button>
    <div><span id="stream-status">Not streaming.</span></div>
    <div id="timer-status-board" class="status-board">Start the stream to see status.</div>
    <pre id="stream-result">Stream status updates will appear here.</pre>
  </fieldset>

  <h2>Pico scheduler</h2>
  <p>The Pico is silent until commanded; the host requests a report every five seconds. Schedules are committed only after a verified Pico apply, so failure leaves desired config unchanged.</p>
  <fieldset>
    <legend>GET /api/controllers/{{controller}}</legend>
    <p>Reads the controller's current API view, including the latest reported Pico state.</p>
    <pre id="scheduler-get-curl-command">curl http://localhost:8000/api/controllers/{html.escape(default_role)}</pre>
    <button class="copy-curl" type="button" data-copy-target="scheduler-get-curl-command">Copy curl</button>
    <button class="scheduler-request" type="button" data-method="GET" data-path="/api/controllers/{html.escape(default_role)}" data-status="scheduler-get-status" data-result="scheduler-get-result">Run request</button>
    <div><span id="scheduler-get-status">Ready.</span></div>
    <pre id="scheduler-get-result">GET response will appear here.</pre>
  </fieldset>
  <fieldset>
    <legend>GET /api/controllers/{{controller}}?stream=true</legend>
    <p>Streams <code>snapshot</code>, <code>status</code>, <code>report</code>, and <code>error</code> events. <code>OK</code> requires a valid report.</p>
    <pre id="controller-stream-curl-command">{html.escape(default_stream_curl)}</pre>
    <button class="copy-curl" type="button" data-copy-target="controller-stream-curl-command">Copy curl</button>
    <button id="controller-stream-start" type="button">Start stream</button>
    <button id="controller-stream-stop" type="button">Stop stream</button>
    <div><span id="controller-stream-status">Not streaming.</span></div>
    <pre id="controller-stream-result">Controller health events will appear here.</pre>
  </fieldset>
  <fieldset>
    <legend>POST /api/controllers/{{controller}}/schedule</legend>
    <p>Loads one controller from desired config, upgrades firmware only when needed, applies its complete schedule, then commits config and applied state. The response includes <code>firmware_upgraded</code> and the verified firmware identity.</p>
    <button id="scheduler-schedule-load" type="button">Load current controller</button>
    <label>Request body
      <textarea id="scheduler-schedule-payload" class="compact-json">{{}}</textarea>
    </label>
    <pre id="scheduler-schedule-request">{{}}</pre>
    <button id="scheduler-schedule-request-button" type="button">Run request</button>
    <div><span id="scheduler-schedule-status">Ready.</span></div>
    <pre id="scheduler-schedule-result">POST response will appear here.</pre>
  </fieldset>
  <fieldset>
    <legend>POST /api/controllers/{{controller}}/apply</legend>
    <p><strong>Recovery:</strong> reapplies the current desired controller config through the same verified transaction. Normal schedule changes use the schedule endpoint above.</p>
    <pre id="scheduler-apply-curl-command">curl -X POST http://localhost:8000/api/controllers/{html.escape(default_role)}/apply</pre>
    <button class="copy-curl" type="button" data-copy-target="scheduler-apply-curl-command">Copy curl</button>
    <button class="scheduler-request" type="button" data-method="POST" data-path="/api/controllers/{html.escape(default_role)}/apply" data-status="scheduler-apply-status" data-result="scheduler-apply-result">Run request</button>
    <div><span id="scheduler-apply-status">Ready.</span></div>
    <pre id="scheduler-apply-result">POST response will appear here.</pre>
  </fieldset>
  <fieldset>
    <legend>POST /api/controllers/{{controller}}/commands/report</legend>
    <p>Sends <code>r</code> and returns only after a fresh report is received.</p>
    <pre id="scheduler-report-curl-command">curl -X POST http://localhost:8000/api/controllers/{html.escape(default_role)}/commands/report</pre>
    <button class="copy-curl" type="button" data-copy-target="scheduler-report-curl-command">Copy curl</button>
    <button class="scheduler-request" type="button" data-method="POST" data-path="/api/controllers/{html.escape(default_role)}/commands/report" data-status="scheduler-report-status" data-result="scheduler-report-result">Run request</button>
    <div><span id="scheduler-report-status">Ready.</span></div>
    <pre id="scheduler-report-result">POST response will appear here.</pre>
  </fieldset>
  <fieldset>
    <legend>POST /api/controllers/{{controller}}/channels/{{channel}}/schedule</legend>
    <p>Compatibility endpoint for changing one channel. It updates desired config, recompiles all channels, and performs one controller apply.</p>
    <p class="helper-title">Cycle example</p>
    <pre id="scheduler-cycle-curl-command">curl -X POST http://localhost:8000/api/controllers/{html.escape(default_role)}/channels/pump/schedule -H 'content-type: application/json' --data '{cycle_schedule_example}'</pre>
    <button class="copy-curl" type="button" data-copy-target="scheduler-cycle-curl-command">Copy curl</button>
    <p class="helper-title">Daily-window example</p>
    <pre id="scheduler-clock-curl-command">curl -X POST http://localhost:8000/api/controllers/{html.escape(default_role)}/channels/lights/schedule -H 'content-type: application/json' --data '{clock_schedule_example}'</pre>
    <button class="copy-curl" type="button" data-copy-target="scheduler-clock-curl-command">Copy curl</button>
  </fieldset>

  <fieldset>
    <legend>POST /api/controllers/{{controller}}/pins/{{pin}}/pulse</legend>
    <p>Requests a short GPIO pulse on a configured Pico scheduler pin.</p>
    <div class="row">
      <label>Controller <input id="pulse-controller" list="timer-roles" value="{html.escape(default_role)}"></label>
      <label>Pin <input id="pulse-pin" type="number" min="0" max="29" step="1" value="21"></label>
      <label>Seconds <input id="pulse-seconds" type="number" min="1" step="1" value="5"></label>
    </div>
    <pre id="pulse-curl-command">curl -X POST http://localhost:8000/api/controllers/{html.escape(default_role)}/pins/21/pulse -H 'content-type: application/json' --data '{{"seconds":5}}'</pre>
    <button class="copy-curl" type="button" data-copy-target="pulse-curl-command">Copy curl</button>
    <button id="pulse-request" type="button">Run request</button>
    <div><span id="pulse-status">Ready.</span></div>
    <pre id="pulse-result">POST response will appear here.</pre>
  </fieldset>

  <script>
    const statusPathList = document.getElementById("status-path-list");
    const cameraCaptureCameraIdInput = document.getElementById("camera-capture-camera-id");
    const listCapturesCameraIdInput = document.getElementById("list-captures-camera-id");
    const listCapturesLimitInput = document.getElementById("list-captures-limit");
    const listCapturesOffsetInput = document.getElementById("list-captures-offset");
    const addStatusPathButton = document.getElementById("add-status-path");
    const streamPrettyInput = document.getElementById("stream-pretty");
    const pulseControllerInput = document.getElementById("pulse-controller");
    const pulsePinInput = document.getElementById("pulse-pin");
    const pulseSecondsInput = document.getElementById("pulse-seconds");
    const schedulerController = {json.dumps(default_role)};
    const schedulerSchedulePayload = document.getElementById("scheduler-schedule-payload");
    const clockTimeFormat = {json.dumps(time_format)};
    let timerEventSource = null;
    let controllerEventSource = null;
    const defaultStatusPaths = {json.dumps([f"config.controllers.{default_role}", f"controllers.{default_role}.telemetry"] if default_role else [])};

    function pulseController() {{
      return pulseControllerInput.value.trim();
    }}

    function pulsePin() {{
      const value = Number(pulsePinInput.value);
      return Number.isFinite(value) ? Math.max(0, Math.min(29, Math.floor(value))) : 0;
    }}

    function pulseSeconds() {{
      const value = Number(pulseSecondsInput.value);
      return Number.isFinite(value) ? Math.max(1, Math.floor(value)) : 5;
    }}

    function bindStatusPathRow(row) {{
      row.querySelector(".status-path-input").addEventListener("input", updateCurl);
      row.querySelector(".remove-status-path").addEventListener("click", () => {{
        row.remove();
        if (!statusPathList.children.length) addStatusPath("");
        updateCurl();
      }});
    }}

    function statusPaths() {{
      return Array.from(statusPathList.querySelectorAll(".status-path-input"))
        .map((input) => input.value.trim())
        .filter((path) => path);
    }}

    function statusPathRow(value) {{
      const row = document.createElement("div");
      row.className = "row status-path-row";
      row.innerHTML = `
        <label>Path <input class="status-path-input" value="${{value || ""}}" placeholder="controllers.${{schedulerController}}.telemetry"></label>
        <button type="button" class="remove-status-path">Remove</button>
      `;
      bindStatusPathRow(row);
      return row;
    }}

    function addStatusPath(value) {{
      statusPathList.append(statusPathRow(value));
      updateCurl();
    }}

    function statusUrl(stream) {{
      const params = new URLSearchParams();
      if (stream) params.set("stream", "true");
      for (const path of statusPaths()) {{
        params.append("path", path);
      }}
      const query = params.toString();
      return `${{window.location.origin}}/api/status${{query ? "?" + query : ""}}`;
    }}

    function listCapturesLimit() {{
      const value = Number(listCapturesLimitInput.value);
      return Number.isFinite(value) ? Math.max(0, Math.min(200, Math.floor(value))) : 10;
    }}

    function listCapturesOffset() {{
      const value = Number(listCapturesOffsetInput.value);
      return Number.isFinite(value) ? Math.max(0, Math.floor(value)) : 0;
    }}

    function listCapturesCameraId() {{
      return listCapturesCameraIdInput.value.trim();
    }}

    function captureCameraId() {{
      return cameraCaptureCameraIdInput.value.trim();
    }}

    function doubleQuote(value) {{
      return JSON.stringify(value);
    }}

    function cameraCaptureCurlCommand() {{
      const cameraId = captureCameraId();
      if (!cameraId) {{
        return "curl -X POST " + doubleQuote(`${{window.location.origin}}/api/camera/captures`);
      }}
      const query = new URLSearchParams({{camera_id: cameraId}});
      return "curl -X POST " + doubleQuote(`${{window.location.origin}}/api/camera/captures?${{query.toString()}}`);
    }}

    function listCapturesCurlCommand() {{
      const params = new URLSearchParams({{limit: String(listCapturesLimit()), offset: String(listCapturesOffset())}});
      const cameraId = listCapturesCameraId();
      if (cameraId) params.set("camera_id", cameraId);
      return "curl " + doubleQuote(`${{window.location.origin}}/api/camera/captures?${{params.toString()}}`);
    }}

    function pulseUrl() {{
      return `/api/controllers/${{encodeURIComponent(pulseController())}}/pins/${{encodeURIComponent(pulsePin())}}/pulse`;
    }}

    function pulseCurlCommand() {{
      return [
        "curl -X POST " + doubleQuote(`${{window.location.origin}}${{pulseUrl()}}`),
        "  -H " + doubleQuote("content-type: application/json"),
        "  --data " + doubleQuote(JSON.stringify({{seconds: pulseSeconds()}})),
      ].join(" ");
    }}

    function updateCurl() {{
      document.getElementById("get-status-curl-command").textContent = "curl " + doubleQuote(statusUrl(false));
      document.getElementById("stream-status-curl-command").textContent = "curl -N " + doubleQuote(statusUrl(true));
      document.getElementById("camera-capture-curl-command").textContent = cameraCaptureCurlCommand();
      document.getElementById("list-captures-curl-command").textContent = listCapturesCurlCommand();
      document.getElementById("pulse-curl-command").textContent = pulseCurlCommand();
      document.getElementById("scheduler-schedule-request").textContent = schedulerSchedulePayload.value;
    }}

    async function copyCurlCommand(event) {{
      const target = document.getElementById(event.currentTarget.dataset.copyTarget);
      if (!target) return;
      await navigator.clipboard.writeText(target.textContent);
      event.currentTarget.textContent = "Copied";
      window.setTimeout(() => {{ event.currentTarget.textContent = "Copy curl"; }}, 1200);
    }}

    function prettyResponseText(text) {{
      try {{
        return JSON.stringify(JSON.parse(text), null, 2);
      }} catch (error) {{
        return text;
      }}
    }}

    async function runConfigRequest(kind) {{
      const specs = {{
        get: {{method: "GET", url: "/api/config", statusId: "get-config-status", resultId: "get-config-result"}},
        system: {{method: "GET", url: "/api/system", statusId: "get-system-status", resultId: "get-system-result"}},
        status: {{method: "GET", url: "/api/status", statusId: "get-status-status", resultId: "get-status-result"}},
        full: {{method: "PUT", url: "/api/config", statusId: "put-config-status", resultId: "put-config-result", section: null}},
        controllers: {{method: "PUT", url: "/api/config/controllers", statusId: "put-config-controllers-status", resultId: "put-config-controllers-result", section: "controllers"}},
        cameras: {{method: "PUT", url: "/api/config/cameras", statusId: "put-config-cameras-status", resultId: "put-config-cameras-result", section: "cameras"}},
      }};
      const spec = specs[kind];
      const status = document.getElementById(spec.statusId);
      const result = document.getElementById(spec.resultId);
      status.textContent = spec.method === "GET" ? "Loading..." : "Saving current config...";
      result.textContent = "";
      try {{
        let options = {{method: spec.method}};
        if (spec.method === "PUT") {{
          if (!window.confirm(`PUT ${{spec.url}} with current config?`)) {{
            status.textContent = "Cancelled.";
            return;
          }}
          const currentResponse = await fetch("/api/config");
          const currentText = await currentResponse.text();
          if (!currentResponse.ok) {{
            status.textContent = `${{currentResponse.status}} ${{currentResponse.statusText}}`;
            result.textContent = prettyResponseText(currentText);
            return;
          }}
          const currentConfig = JSON.parse(currentText).config || {{}};
          const body = spec.section ? currentConfig[spec.section] || {{}} : currentConfig;
          options = {{method: "PUT", headers: {{"content-type": "application/json"}}, body: JSON.stringify(body)}};
        }}
        const response = await fetch(spec.url, options);
        const text = await response.text();
        status.textContent = `${{response.status}} ${{response.statusText}}`;
        result.textContent = prettyResponseText(text);
      }} catch (error) {{
        status.textContent = "Request failed.";
        result.textContent = String(error);
      }}
    }}

    async function runSchedulerRequest(event) {{
      const button = event.currentTarget;
      const status = document.getElementById(button.dataset.status);
      const result = document.getElementById(button.dataset.result);
      status.textContent = "Sending...";
      result.textContent = "";
      try {{
        const response = await fetch(button.dataset.path, {{method: button.dataset.method}});
        const text = await response.text();
        status.textContent = `${{response.status}} ${{response.statusText}}`;
        result.textContent = prettyResponseText(text);
      }} catch (error) {{
        status.textContent = "Request failed.";
        result.textContent = String(error);
      }}
    }}

    async function loadControllerSchedule() {{
      const status = document.getElementById("scheduler-schedule-status");
      const result = document.getElementById("scheduler-schedule-result");
      status.textContent = "Loading current config...";
      result.textContent = "";
      try {{
        const response = await fetch("/api/config");
        const text = await response.text();
        const parsed = JSON.parse(text);
        if (!response.ok) throw new Error(parsed?.detail || text);
        const controller = parsed?.config?.controllers?.[schedulerController];
        if (!controller) throw new Error(`unknown controller: ${{schedulerController}}`);
        schedulerSchedulePayload.value = JSON.stringify(controller, null, 2);
        updateCurl();
        status.textContent = "Current controller loaded.";
      }} catch (error) {{
        status.textContent = "Request failed.";
        result.textContent = String(error.message || error);
      }}
    }}

    async function runControllerSchedule() {{
      const status = document.getElementById("scheduler-schedule-status");
      const result = document.getElementById("scheduler-schedule-result");
      let body;
      try {{
        body = JSON.parse(schedulerSchedulePayload.value);
      }} catch (error) {{
        status.textContent = "Invalid JSON.";
        result.textContent = String(error);
        return;
      }}
      if (!window.confirm(`Apply and commit the complete ${{schedulerController}} schedule?`)) return;
      status.textContent = "Applying and verifying...";
      result.textContent = "";
      try {{
        const response = await fetch(`/api/controllers/${{encodeURIComponent(schedulerController)}}/schedule`, {{
          method: "POST",
          headers: {{"content-type": "application/json"}},
          body: JSON.stringify(body),
        }});
        const text = await response.text();
        status.textContent = `${{response.status}} ${{response.statusText}}`;
        result.textContent = prettyResponseText(text);
      }} catch (error) {{
        status.textContent = "Request failed.";
        result.textContent = String(error);
      }}
    }}

    function stopControllerStream() {{
      if (controllerEventSource) {{
        controllerEventSource.close();
        controllerEventSource = null;
      }}
      document.getElementById("controller-stream-status").textContent = "Not streaming.";
    }}

    function startControllerStream() {{
      stopControllerStream();
      const status = document.getElementById("controller-stream-status");
      const result = document.getElementById("controller-stream-result");
      result.textContent = "";
      controllerEventSource = new EventSource(`/api/controllers/${{encodeURIComponent(schedulerController)}}?stream=true`);
      controllerEventSource.onopen = () => {{ status.textContent = "Streaming controller health."; }};
      for (const eventName of ["snapshot", "status", "report", "error"]) {{
        controllerEventSource.addEventListener(eventName, (event) => {{
          const timestamp = new Date().toLocaleTimeString();
          result.textContent += `[${{timestamp}}] ${{eventName}}\n${{prettyResponseText(event.data)}}\n\n`;
          result.scrollTop = result.scrollHeight;
        }});
      }}
      controllerEventSource.onerror = () => {{ status.textContent = "Stream disconnected or reconnecting."; }};
    }}

    async function getStatus() {{
      const getStatus = document.getElementById("get-status");
      const getResult = document.getElementById("get-status-result");
      getStatus.textContent = "";
      getResult.textContent = "";
      const url = statusUrl(false);
      if (!window.confirm(`GET ${{url}}?`)) {{
        getStatus.textContent = "Cancelled.";
        return;
      }}
      getStatus.textContent = "Loading...";
      try {{
        const response = await fetch(url);
        const text = await response.text();
        getStatus.textContent = `${{response.status}} ${{response.statusText}}`;
        if (response.ok) {{
          const parsed = JSON.parse(text);
          getResult.textContent = JSON.stringify(parsed, null, 2);
          updateCurl();
        }} else {{
          let detail = text;
          try {{
            const parsed = JSON.parse(text);
            detail = parsed?.detail || text;
          }} catch (error) {{}}
          getResult.textContent = `Error: ${{detail || response.statusText}}`;
        }}
      }} catch (error) {{
        getStatus.textContent = "Request failed.";
        getResult.textContent = String(error);
      }}
    }}

    function formatChangeTime(secondsFromNow) {{
      const when = new Date(Date.now() + secondsFromNow * 1000);
      if (clockTimeFormat === "24h") {{
        return when.toLocaleTimeString([], {{hour: "2-digit", minute: "2-digit", hour12: false}});
      }}
      return when.toLocaleTimeString([], {{hour: "numeric", minute: "2-digit"}});
    }}

    function currentTimerStep(event) {{
      const pattern = Array.isArray(event.pattern) ? event.pattern : [];
      if (!pattern.length) return null;
      const durations = pattern.map((step) => Number(step.dur));
      if (durations.some((duration) => !Number.isFinite(duration) || duration <= 0)) return null;
      const total = durations.reduce((sum, duration) => sum + duration, 0);
      let cycleT = Number(event.cycle_t ?? event.elapsed_t ?? event.current_t ?? 0);
      if (!Number.isFinite(cycleT)) cycleT = 0;
      if (Number(event.reschedule ?? 1)) {{
        cycleT = ((cycleT % total) + total) % total;
      }} else {{
        cycleT = Math.min(Math.max(cycleT, 0), total);
      }}
      let start = 0;
      for (let index = 0; index < pattern.length; index += 1) {{
        const end = start + durations[index];
        if (cycleT < end || index === pattern.length - 1) {{
          return {{step: pattern[index], elapsed: Math.max(0, cycleT - start), duration: durations[index], remaining: Math.max(0, end - cycleT)}};
        }}
        start = end;
      }}
      return null;
    }}

    function timerDevicesFromMessage(message) {{
      const candidates = [
        message?.telemetry?.last_report?.content?.devices,
        message?.telemetry?.report?.content?.devices,
        message?.telemetry?.content?.devices,
        message?.telemetry?.devices,
        message?.report?.content?.devices,
        message?.last_report?.content?.devices,
        message?.content?.devices,
        message?.devices,
      ];
      return candidates.find((devices) => Array.isArray(devices)) || [];
    }}

    function renderTimerStatus(message) {{
      const devices = timerDevicesFromMessage(message);
      const board = document.getElementById("timer-status-board");
      if (!devices.length) return;
      board.replaceChildren();
      for (const [index, device] of devices.entries()) {{
        const step = currentTimerStep(device);
        const value = Number(step?.step?.val ?? device.current_value ?? 0);
        const isOn = value > 0;
        const percent = step ? Math.max(0, Math.min(100, (step.elapsed / step.duration) * 100)) : 0;

        const card = document.createElement("div");
        card.className = "timer-card";

        const top = document.createElement("div");
        top.className = "timer-top";
        const name = document.createElement("span");
        name.className = "timer-name";
        name.textContent = device.id || "pin " + (device.pin ?? index);
        const badge = document.createElement("span");
        badge.className = "timer-value " + (isOn ? "on" : "off");
        badge.textContent = isOn ? "ON" : "OFF";
        top.append(name, badge);

        const meta = document.createElement("div");
        meta.className = "timer-meta";
        meta.textContent = "pin " + (device.pin ?? "?") + " | " + (device.type || "timer") + " | value " + value + " | changes at " + (step ? formatChangeLabel(step.remaining) : "?");

        const bar = document.createElement("div");
        bar.className = "timer-bar";
        const fill = document.createElement("div");
        fill.className = "timer-fill" + (isOn ? "" : " off");
        fill.style.width = percent + "%";
        bar.append(fill);

        card.append(top, meta, bar);
        board.append(card);
      }}
    }}

    function appendStreamEvent(eventName, data) {{
      const streamResult = document.getElementById("stream-result");
      const timestamp = new Date().toLocaleTimeString();
      let display = data;
      try {{
        const parsed = JSON.parse(data);
        display = JSON.stringify(parsed, null, streamPrettyInput.checked ? 2 : 0);
      }} catch (error) {{
      }}
      streamResult.textContent += `[${{timestamp}}] ${{eventName}}\n${{display}}\n\n`;
      if (streamResult.textContent.length > 20000) {{
        streamResult.textContent = streamResult.textContent.slice(-20000);
      }}
      streamResult.scrollTop = streamResult.scrollHeight;
    }}

    function stopTimerStream() {{
      if (timerEventSource) {{
        timerEventSource.close();
        timerEventSource = null;
      }}
      document.getElementById("stream-status").textContent = "Not streaming.";
    }}

    function startTimerStream() {{
      stopTimerStream();
      const streamStatus = document.getElementById("stream-status");
      const streamResult = document.getElementById("stream-result");
      streamResult.textContent = "";
      streamStatus.textContent = `Connecting to ${{statusUrl(true)}}...`;
      fetch(statusUrl(false)).then(async (response) => {{
        const probeText = await response.text();
        if (!response.ok) {{
          streamStatus.textContent = `${{response.status}} ${{response.statusText}}`;
          streamResult.textContent = `Error: ${{probeText}}`;
          return;
        }}
        timerEventSource = new EventSource(statusUrl(true));
        timerEventSource.onopen = () => {{
          streamStatus.textContent = "Streaming filtered status.";
        }};
        for (const eventName of ["snapshot", "update"]) {{
          timerEventSource.addEventListener(eventName, (event) => appendStreamEvent(eventName, event.data));
        }}
        timerEventSource.onerror = () => {{
          if (timerEventSource && timerEventSource.readyState === EventSource.CLOSED) {{
            streamStatus.textContent = "Stream disconnected.";
          }}
        }};
      }}).catch((error) => {{
        streamStatus.textContent = "Request failed.";
        streamResult.textContent = String(error);
      }});
    }}

    addStatusPathButton.addEventListener("click", () => addStatusPath(""));
    for (const row of Array.from(statusPathList.querySelectorAll(".status-path-row"))) {{
      bindStatusPathRow(row);
    }}
    if (!statusPathList.children.length) {{
      if (defaultStatusPaths.length) {{
        for (const path of defaultStatusPaths) {{
          addStatusPath(path);
        }}
      }} else {{
        addStatusPath("");
      }}
    }}
    updateCurl();

    async function listCameraCaptures() {{
      const status = document.getElementById("list-captures-status");
      const result = document.getElementById("list-captures-result");
      status.textContent = "Loading...";
      result.textContent = "";
      try {{
        const params = new URLSearchParams({{limit: String(listCapturesLimit()), offset: String(listCapturesOffset())}});
        const cameraId = listCapturesCameraId();
        if (cameraId) params.set("camera_id", cameraId);
        const response = await fetch(`/api/camera/captures?${{params.toString()}}`);
        const text = await response.text();
        let display = text;
        try {{
          display = JSON.stringify(JSON.parse(text), null, 2);
        }} catch (error) {{
        }}
        status.textContent = `${{response.status}} ${{response.statusText}}`;
        result.textContent = display;
      }} catch (error) {{
        status.textContent = "Request failed.";
        result.textContent = String(error);
      }}
    }}

    async function captureCameraImage() {{
      const status = document.getElementById("camera-capture-status");
      const result = document.getElementById("camera-capture-result");
      const preview = document.getElementById("camera-capture-preview");
      status.textContent = "Capturing...";
      result.textContent = "";
      preview.hidden = true;
      preview.removeAttribute("src");
      try {{
        const params = new URLSearchParams();
        const cameraId = captureCameraId();
        if (cameraId) params.set("camera_id", cameraId);
        const query = params.toString();
        const url = query ? `/api/camera/captures?${{query}}` : "/api/camera/captures";
        const response = await fetch(url, {{method: "POST"}});
        const text = await response.text();
        let display = text;
        let parsed = null;
        try {{
          parsed = JSON.parse(text);
          display = JSON.stringify(parsed, null, 2);
        }} catch (error) {{
        }}
        status.textContent = `${{response.status}} ${{response.statusText}}`;
        result.textContent = display;
        if (response.ok && parsed && typeof parsed.image_url === "string") {{
          preview.src = parsed.image_url;
          preview.hidden = false;
        }}
      }} catch (error) {{
        status.textContent = "Request failed.";
        result.textContent = String(error);
      }}
    }}

    async function pulsePinRequest() {{
      const status = document.getElementById("pulse-status");
      const result = document.getElementById("pulse-result");
      const url = pulseUrl();
      status.textContent = "";
      result.textContent = "";
      if (!window.confirm(`POST ${{url}} for ${{pulseSeconds()}} seconds?`)) {{
        status.textContent = "Cancelled.";
        return;
      }}
      status.textContent = "Sending...";
      try {{
        const response = await fetch(pulseUrl(), {{
          method: "POST",
          headers: {{"content-type": "application/json"}},
          body: JSON.stringify({{seconds: pulseSeconds()}}),
        }});
        const text = await response.text();
        status.textContent = `${{response.status}} ${{response.statusText}}`;
        result.textContent = prettyResponseText(text);
      }} catch (error) {{
        status.textContent = "Request failed.";
        result.textContent = String(error);
      }}
    }}

    document.getElementById("get-config").addEventListener("click", () => runConfigRequest("get"));
    document.getElementById("get-system").addEventListener("click", () => runConfigRequest("system"));
    document.getElementById("put-config").addEventListener("click", () => runConfigRequest("full"));
    document.getElementById("put-config-controllers").addEventListener("click", () => runConfigRequest("controllers"));
    document.getElementById("put-config-cameras").addEventListener("click", () => runConfigRequest("cameras"));
    document.getElementById("get-status").addEventListener("click", getStatus);
    document.getElementById("start-stream").addEventListener("click", startTimerStream);
    document.getElementById("stop-stream").addEventListener("click", stopTimerStream);
    document.getElementById("camera-capture").addEventListener("click", captureCameraImage);
    document.getElementById("list-captures").addEventListener("click", listCameraCaptures);
    document.getElementById("pulse-request").addEventListener("click", pulsePinRequest);
    document.getElementById("controller-stream-start").addEventListener("click", startControllerStream);
    document.getElementById("controller-stream-stop").addEventListener("click", stopControllerStream);
    document.getElementById("scheduler-schedule-load").addEventListener("click", loadControllerSchedule);
    document.getElementById("scheduler-schedule-request-button").addEventListener("click", runControllerSchedule);
    for (const button of document.querySelectorAll(".scheduler-request")) {{
      button.addEventListener("click", runSchedulerRequest);
    }}
    cameraCaptureCameraIdInput.addEventListener("input", updateCurl);
    listCapturesCameraIdInput.addEventListener("input", updateCurl);
    listCapturesLimitInput.addEventListener("input", updateCurl);
    listCapturesOffsetInput.addEventListener("input", updateCurl);
    pulseControllerInput.addEventListener("input", updateCurl);
    pulsePinInput.addEventListener("input", updateCurl);
    pulseSecondsInput.addEventListener("input", updateCurl);
    for (const button of document.querySelectorAll(".copy-curl")) {{
      button.addEventListener("click", copyCurlCommand);
    }}
    listCapturesLimitInput.addEventListener("input", updateCurl);
    listCapturesOffsetInput.addEventListener("input", updateCurl);
    schedulerSchedulePayload.addEventListener("input", updateCurl);
    window.addEventListener("beforeunload", () => {{ stopTimerStream(); stopControllerStream(); }});
    updateCurl();
  </script>
</body>
</html>"""


def render_timer_test_page(roles: list[str], default_role: str, default_payload: str, time_format: str) -> str:
    return render_api_test_page(roles, default_role, default_payload, time_format)
