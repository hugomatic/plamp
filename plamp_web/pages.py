from __future__ import annotations

import html
import json
import re
from datetime import datetime, timezone
from typing import Any

GITHUB_REPO_URL = "https://github.com/hugomatic/plamp"
GITHUB_NEW_ISSUE_URL = f"{GITHUB_REPO_URL}/issues/new"
MAIN_NAV = f'<nav><a href="/">Plamp</a> | <a href="/settings">Settings</a> | <a href="/system">System</a> | <a href="/api/test">API test</a> | <a href="{GITHUB_REPO_URL}">GitHub</a></nav>'
FAVICON_LINK = '<link rel="icon" href="/favicon.svg" type="image/svg+xml">'


def relative_time_label(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    now = datetime.now(parsed.tzinfo)
    delta = now - parsed
    seconds = max(0, int(delta.total_seconds()))
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        minutes = seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    if seconds < 86400:
        hours = seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = seconds // 86400
    return f"{days} day{'s' if days != 1 else ''} ago"


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
  {MAIN_NAV}
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


def render_settings_page(summary: dict[str, Any]) -> str:
    config = summary.get("config") if isinstance(summary.get("config"), dict) else {}
    if isinstance(config.get("devices"), dict):
        normalized_controllers: dict[str, dict[str, Any]] = {}
        for controller_id, controller in (config.get("controllers") or {}).items():
            if not isinstance(controller_id, str) or not isinstance(controller, dict):
                continue
            normalized_controllers[controller_id] = {
                "type": str(controller.get("type") or "pico_scheduler"),
                "config": {
                    key: value
                    for key, value in {
                        "pico_serial": controller.get("pico_serial"),
                        "label": controller.get("label"),
                    }.items()
                    if value not in {None, ""}
                },
                "settings": {"report_every": controller.get("report_every", 10)},
                "devices": {},
            }
        for device_id, device in config["devices"].items():
            if not isinstance(device_id, str) or not isinstance(device, dict):
                continue
            controller_id = device.get("controller")
            if controller_id not in normalized_controllers:
                continue
            editor = str(device.get("editor") or "cycle")
            normalized_controllers[controller_id]["devices"][device_id] = {
                "type": "scheduled_output",
                "config": {
                    key: value
                    for key, value in {
                        "pin": device.get("pin"),
                        "output_type": device.get("type", "gpio"),
                        "label": device.get("label"),
                        "visibility": "hidden" if editor == "hidden" else None,
                    }.items()
                    if value not in {None, ""}
                },
                "settings": (
                    {"programming": "disabled", "schedule": {"kind": "cycle"}}
                    if editor == "disabled"
                    else {"schedule": {"kind": "daily_window" if editor == "clock_window" else "cycle"}}
                ),
            }
        config = {"controllers": normalized_controllers, "cameras": config.get("cameras", {})}
    detected = summary.get("detected") if isinstance(summary.get("detected"), dict) else {}
    controllers = config.get("controllers") if isinstance(config.get("controllers"), dict) else {}
    configured_cameras = config.get("cameras") if isinstance(config.get("cameras"), dict) else {}
    setup_picos = detected.get("picos") if isinstance(detected.get("picos"), list) else []
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

    host = summary.get("host") if isinstance(summary.get("host"), dict) else {"hostname": "", "network": []}
    host_time = summary.get("host_time") if isinstance(summary.get("host_time"), dict) else {}
    status_picos = summary.get("picos") if isinstance(summary.get("picos"), list) and summary.get("picos") else setup_picos
    networks = host.get("network") if isinstance(host.get("network"), list) else []
    storage = summary.get("storage") if isinstance(summary.get("storage"), dict) else {}
    cameras = summary.get("cameras") if isinstance(summary.get("cameras"), dict) else {}
    rpicam_cameras = cameras.get("rpicam") if isinstance(cameras.get("rpicam"), list) else raw_detected_cameras
    tools = summary.get("tools") if isinstance(summary.get("tools"), dict) else {}
    camera_worker = summary.get("camera_worker") if isinstance(summary.get("camera_worker"), dict) else {}
    paths = summary.get("paths") if isinstance(summary.get("paths"), dict) else {}
    scheduler_controller_options = scheduler_controllers(controllers)
    peripheral_assignment_map = peripheral_assignments(scheduler_controller_options)
    scheduler_groups = scheduler_devices_by_controller(scheduler_controller_options)
    hidden_controllers = hidden_scheduler_controllers(scheduler_controller_options, scheduler_groups)

    def render_scheduler_controller_row(controller_id: str, controller: dict[str, Any], *, new_row: bool = False) -> str:
        payload = controller_payload(controller)
        settings = controller_settings(controller)
        return (
            '<tr class="controller-row{new_row_class}" data-controller-key="{controller_id}">'
            '<td><input class="controller-id" placeholder="pump_lights" value="{controller_id}"></td>'
            '<td><input class="controller-label" placeholder="Pump and lights" value="{label}"></td>'
            '<td><select class="controller-pico-serial">{pico_options_html}</select></td>'
            '<td><input class="controller-report-every" type="number" min="1" value="{report_every}"></td>'
            '<td style="display:none"><select class="controller-type">{type_options}</select></td>'
            '</tr>'.format(
                new_row_class=" new-row" if new_row else "",
                controller_id=html.escape(controller_id, quote=True),
                label=html.escape(str(settings.get("label") or ""), quote=True),
                pico_options_html=pico_options(setup_picos, str(payload.get("pico_serial") or "")),
                report_every=html.escape(str(payload.get("report_every") or controller.get("settings", {}).get("report_every") or 10), quote=True),
                type_options=controller_type_options(str(controller.get("type") or "pico_scheduler")),
            )
        )

    def render_scheduler_device_row(device_id: str, device: dict[str, Any], controller_id: str, *, new_row: bool = False) -> str:
        return (
            '<tr class="device-row{new_row_class}" data-device-id="{device_id}" data-device-controller="{controller_id}" data-device-editor-json="{editor_json}">'
            '<td><input class="device-id" placeholder="pump" value="{device_id}"></td>'
            '<td><input class="device-label" placeholder="Water pump" value="{label}"></td>'
            '<td><input class="device-pin" type="number" min="0" max="29" value="{pin}"></td>'
            '<td><select class="device-type">{type_options}</select></td>'
            '<td><select class="device-editor">{editor_options}</select></td>'
            '</tr>'.format(
                new_row_class=" new-row" if new_row else "",
                device_id=html.escape(device_id, quote=True),
                label=html.escape(str(device.get("label") or ""), quote=True),
                controller_id=html.escape(controller_id, quote=True),
                editor_json=html.escape(json.dumps(device.get("editor") or {}, separators=(",", ":")), quote=True),
                pin=html.escape(str(device.get("pin") if device.get("pin") is not None else ""), quote=True),
                type_options=pin_type_options(str(device.get("output_type") or "gpio")),
                editor_options="".join(option_tag(value, value, "disabled" if device.get("programming") == "disabled" else ("hidden" if device.get("visibility") == "hidden" else ("clock_window" if device.get("editor", {}).get("kind") == "daily_window" else "cycle"))) for value in ["cycle", "clock_window", "disabled", "hidden"]),
            )
        )

    create_scheduler_block = (
        '<div class="pico-scheduler-block pico-scheduler-new" data-controller-key="">'
        '<table><thead><tr><th>ID</th><th>Label</th><th>Assigned peripheral</th><th>Report every seconds</th></tr></thead>'
        '<tbody>{controller_row}</tbody></table>'
        '<div class="subsection-indent"><h4>Devices</h4>'
        '<table><thead><tr><th>ID</th><th>Label</th><th>Pin</th><th>Output type</th><th>Editor</th></tr></thead>'
        '<tbody>{device_rows}</tbody></table></div>'
        '</div>'.format(
            controller_row=render_scheduler_controller_row("", {}, new_row=True),
            device_rows=render_scheduler_device_row("", {}, "", new_row=True),
        )
    )

    scheduler_blocks = []
    for controller_id, controller, controller_devices in scheduler_groups:
        device_rows = [render_scheduler_device_row(device_id, device, controller_id) for device_id, device in controller_devices]
        device_rows.append(render_scheduler_device_row("", {}, controller_id, new_row=True))
        scheduler_blocks.append(
            '<div class="pico-scheduler-block" data-controller-key="{controller_id}">'
            '<table><thead><tr><th>ID</th><th>Label</th><th>Assigned peripheral</th><th>Report every seconds</th></tr></thead>'
            '<tbody>{controller_row}</tbody></table>'
            '<div class="subsection-indent"><h4>Devices</h4>'
            '<table><thead><tr><th>ID</th><th>Label</th><th>Pin</th><th>Output type</th><th>Editor</th></tr></thead>'
            '<tbody>{device_rows}</tbody></table></div>'
            '</div>'.format(
                controller_id=html.escape(controller_id, quote=True),
                controller_row=render_scheduler_controller_row(controller_id, controller),
                device_rows="".join(device_rows),
            )
        )
    scheduler_blocks.append(create_scheduler_block)

    detected_by_key = {str(item.get("key")): item for item in detected_cameras if isinstance(item, dict) and item.get("key")}
    camera_detected_keys, unmatched_detected_keys = camera_detected_matches(configured_cameras, detected_cameras)
    camera_assigned_map: dict[str, list[str]] = {}
    for camera_id, detected_key in camera_detected_keys.items():
        if detected_key:
            camera_assigned_map.setdefault(detected_key, []).append(camera_id)
    all_camera_keys = list(configured_cameras) + unmatched_detected_keys
    camera_setup_rows = []
    for camera_id in all_camera_keys:
        camera = configured_cameras.get(camera_id, {}) if isinstance(configured_cameras.get(camera_id, {}), dict) else {}
        detected_key = camera_detected_keys.get(camera_id, camera_id if camera_id in detected_by_key else "")
        detected_camera = detected_by_key.get(detected_key, {})
        autofocus_mode = str(camera.get("autofocus_mode") or "auto")
        camera_setup_rows.append(
            '<tr class="camera-row" data-camera-key="{camera_id}">'
            '<td><input class="camera-id" placeholder="rpicam_cam0" value="{camera_id}"></td>'
            '<td><input class="camera-label" placeholder="Tent camera" value="{label}"></td>'
            '<td><select class="camera-detected-key">{detected_key_options}</select></td>'
            '<td><input class="camera-capture-dir" placeholder="data/grow/grows/<grow-id>/captures" value="{capture_dir}"></td>'
            '<td><input class="camera-capture-every-seconds" type="number" min="0" value="{capture_every_seconds}"></td>'
            '<td><select class="camera-autofocus-mode">{autofocus_mode_options}</select></td>'
            '<td><input class="camera-autofocus-delay-ms" type="number" min="0" value="{autofocus_delay_ms}"></td>'
            '</tr>'.format(
                camera_id=html.escape(camera_id, quote=True),
                label=html.escape(str(camera.get("label") or ""), quote=True),
                detected_key_options=camera_peripheral_options(detected_cameras, detected_key),
                capture_dir=html.escape(str(camera.get("capture_dir") or ""), quote=True),
                capture_every_seconds=html.escape(str(camera.get("capture_every_seconds") or ""), quote=True),
                autofocus_mode_options="".join(
                    option_tag(value, value, autofocus_mode)
                    for value in ["auto", "continuous", "manual", "off"]
                ),
                autofocus_delay_ms=html.escape(str(camera.get("autofocus_delay_ms") or ""), quote=True),
            )
        )
    camera_setup_rows.append(
        '<tr class="camera-row new-row" data-camera-key="">'
        '<td><input class="camera-id" placeholder="rpicam_cam0" value=""></td>'
        '<td><input class="camera-label" placeholder="Tent camera" value=""></td>'
        '<td><select class="camera-detected-key">{detected_key_options}</select></td>'
        '<td><input class="camera-capture-dir" placeholder="data/grow/grows/<grow-id>/captures" value=""></td>'
        '<td><input class="camera-capture-every-seconds" type="number" min="0" value="0"></td>'
        '<td><select class="camera-autofocus-mode"><option value="auto" selected>auto</option><option value="continuous">continuous</option><option value="manual">manual</option><option value="off">off</option></select></td>'
        '<td><input class="camera-autofocus-delay-ms" type="number" min="0" value=""></td>'
        '</tr>'.format(detected_key_options=camera_peripheral_options(detected_cameras, ""))
    )

    pico_rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(str(item.get('port') or '-'))}</td>"
        f"<td>{html.escape(str(item.get('usb_device') or '-'))}</td>"
        f"<td>{html.escape(str(item.get('serial') or '-'))}</td>"
        f"<td>{html.escape(', '.join(peripheral_assignment_map.get(str(item.get('serial') or ''), [])) or 'Unassigned')}</td>"
        f"<td>{html.escape(str(item.get('vendor_id') or '-'))}:{html.escape(str(item.get('product_id') or '-'))}</td>"
        "</tr>"
        for item in status_picos
    ) or '<tr><td colspan="5">No peripherals found.</td></tr>'

    def camera_status_name(item: dict[str, Any]) -> str:
        connector = item.get("connector")
        if connector:
            return str(connector)
        index = item.get("index")
        if index is not None:
            return f"cam{index}"
        key = normalize_camera_key(item.get("key"))
        return key or "-"

    camera_rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(camera_status_name(item))}</td>"
        f"<td>{html.escape(camera_model_label(item))}</td>"
        f"<td>{html.escape(', '.join(camera_assigned_map.get(normalize_camera_key(item.get('key')), [])) or 'Unassigned')}</td>"
        f"<td>{html.escape(str(item.get('sensor') or '-'))}</td>"
        f"<td>{html.escape(str(item.get('lens') or '-'))}</td>"
        f"<td><code>{html.escape(str(item.get('path') or '-'))}</code></td>"
        "</tr>"
        for item in rpicam_cameras
    ) or '<tr><td colspan="6">No Raspberry Pi cameras found.</td></tr>'

    network_rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(str(item.get('device') or '-'))}</td>"
        f"<td>{html.escape(str(item.get('ipv4') or '-'))}</td>"
        f"<td>{html.escape(str(item.get('network') or '-'))}</td>"
        "</tr>"
        for item in networks
    ) or '<tr><td colspan="3">No network devices found.</td></tr>'

    software = summary.get("software") if isinstance(summary.get("software"), dict) else {}
    repo_root_path = str(software.get("path") or ".")
    repo_root_path_json = json_script_text(repo_root_path)
    git_short_commit = software.get("git_short_commit") or software.get("git_commit") or "unknown"
    git_branch = software.get("git_branch") or "unknown"
    git_commit_timestamp = software.get("git_commit_timestamp") or "unknown"
    git_commit_relative = relative_time_label(software.get("git_commit_timestamp"))
    git_commit_timestamp_display = (
        f"{git_commit_timestamp} ({git_commit_relative})" if git_commit_relative else str(git_commit_timestamp)
    )
    git_dirty = software.get("git_dirty")
    git_dirty_files = software.get("git_dirty_files") if isinstance(software.get("git_dirty_files"), list) else []
    if git_dirty is None:
        git_dirty_display = "unknown"
    elif not git_dirty:
        git_dirty_display = "no"
    else:
        dirty_preview = ", ".join(str(path) for path in git_dirty_files[:2] if path)
        if len(git_dirty_files) > 2:
            dirty_preview = f"{dirty_preview}, ..." if dirty_preview else "..."
        git_dirty_display = f"yes: {dirty_preview}" if dirty_preview else "yes"
    os_name = str(software.get("os_name") or "unknown")
    os_arch = str(software.get("os_arch") or "unknown")
    os_version = str(software.get("os_version") or "unknown")
    os_display = f"{os_name} {os_version}; arch {os_arch}"
    user_name = str(software.get("user_name") or "unknown")
    user_is_sudoer = bool(software.get("user_is_sudoer"))
    user_has_serial_access = bool(software.get("user_has_serial_access"))
    user_has_video_access = bool(software.get("user_has_video_access"))
    user_display = (
        f"{user_name}; sudoer {'yes' if user_is_sudoer else 'no'}; "
        f"serial {'yes' if user_has_serial_access else 'no'}; "
        f"video {'yes' if user_has_video_access else 'no'}"
    )
    mpremote_path = str(software.get("mpremote_path") or "not found")
    mpremote_version = str(software.get("mpremote_version") or "").strip()
    mpremote_version_suffix = mpremote_version.removeprefix("mpremote ").strip()
    mpremote_display = mpremote_path if not mpremote_version_suffix else f"{mpremote_path} version {mpremote_version_suffix}"
    pyserial_value = str(tools.get("pyserial") or "-")
    pyserial_display = pyserial_value if pyserial_value in {"-", "unknown"} else f"version {pyserial_value}"
    software_rows = (
        "<tr><td>Plamp root</td>" f"<td><code>{html.escape(str(paths.get('repo_root') or repo_root_path))}</code></td></tr>"
        "<tr><td>Plamp data</td>" f"<td><code>{html.escape(str(paths.get('data_dir') or '-'))}</code></td></tr>"
        "<tr><td>Operating system</td>" f"<td><code>{html.escape(os_display)}</code></td></tr>"
        "<tr><td>User name</td>" f"<td><code>{html.escape(user_display)}</code></td></tr>"
        "<tr><td>Git commit</td>" f"<td><code>{html.escape(str(git_short_commit))}</code></td></tr>"
        "<tr><td>Git branch</td>" f"<td><code>{html.escape(str(git_branch))}</code></td></tr>"
        "<tr><td>Git commit time</td>" f"<td><code>{html.escape(git_commit_timestamp_display)}</code></td></tr>"
        "<tr><td>Git dirty</td>" f"<td><code>{html.escape(git_dirty_display)}</code></td></tr>"
        "<tr><td>mpremote</td>" f"<td><code>{html.escape(mpremote_display)}</code></td></tr>"
        "<tr><td>pyserial</td>" f"<td><code>{html.escape(pyserial_display)}</code></td></tr>"
    )

    storage_rows = (
        "<tr>"
        f"<td><code>{html.escape(str(storage.get('path') or '-'))}</code></td>"
        f"<td>{html.escape(str(storage.get('free') or '-'))}</td>"
        f"<td>{html.escape(str(storage.get('used') or '-'))}</td>"
        f"<td>{html.escape(str(storage.get('total') or '-'))}</td>"
        "</tr>"
    )
    camera_worker_rows = (
        "<tr><td>State</td>" f"<td><code>{html.escape(str(camera_worker.get('state') or '-'))}</code></td></tr>"
        "<tr><td>Available</td>" f"<td><code>{html.escape(str(camera_worker.get('available') if 'available' in camera_worker else '-'))}</code></td></tr>"
        "<tr><td>Queue depth</td>" f"<td><code>{html.escape(str(camera_worker.get('queue_depth') or 0))}</code></td></tr>"
        "<tr><td>Last capture</td>" f"<td><code>{html.escape(str(camera_worker.get('last_capture_at') or '-'))}</code></td></tr>"
        "<tr><td>Last error</td>" f"<td><code>{html.escape(str(camera_worker.get('last_error') or '-'))}</code></td></tr>"
        "<tr><td>Scheduled cameras</td>" f"<td><code>{html.escape(', '.join(camera_worker.get('scheduled_cameras') or []) or '-')}</code></td></tr>"
    )
    hostname = str(host.get("hostname") or "")
    page_title = f"{hostname} Settings" if hostname else "Settings"

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(page_title)}</title>
  {FAVICON_LINK}
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; line-height: 1.4; }}
    nav {{ margin-bottom: 1.5rem; }}
    section {{ border-top: 1px solid #ddd; margin-top: 2rem; padding-top: 1rem; }}
    table {{ border-collapse: collapse; margin: 1rem 0 1.5rem; width: 100%; max-width: 1100px; }}
    th, td {{ border: 1px solid #ccc; padding: .45rem .6rem; text-align: left; vertical-align: top; }}
    th {{ background: #f4f4f4; }}
    input, select {{ box-sizing: border-box; max-width: 100%; padding: .35rem; }}
    button {{ border: 1px solid #222; border-radius: 6px; margin: .4rem .4rem .4rem 0; padding: .45rem .7rem; background: #fff; }}
    code {{ background: #f4f4f4; padding: .1rem .25rem; }}
    .muted, .status {{ color: #555; font-size: .9rem; }}
    .host-clock {{ color: #555; font-size: .95rem; }}
    .subsection-indent {{ margin-left: 1.5rem; max-width: 1050px; }}
  </style>
</head>
<body>
  {MAIN_NAV}
  <h1>{html.escape(page_title)}</h1>
  <p class="host-clock"><strong>Host time:</strong> {html.escape(str(host_time.get("display") or "-"))}</p>
  <p><a href="{GITHUB_NEW_ISSUE_URL}">Report an issue</a></p>

  <section aria-label="Plamp config">
    <h2>Plamp config</h2>
    <p class="muted">Configure controllers, Pico scheduler devices, and cameras.</p>
    <h3>Pico schedulers</h3>
    {''.join(scheduler_blocks)}
    <button id="save-controllers" type="button">Save controllers</button> <span id="controllers-status" class="status">Ready.</span>
    <button id="save-devices" type="button">Save devices</button> <span id="devices-status" class="status">Ready.</span>
    <h3>Cameras</h3>
    <p class="muted">Capture dir must stay inside Plamp root. Use a repo-relative path like <code>data/grow/grows/&lt;grow-id&gt;/captures</code>; absolute paths are rejected.</p>
    <p class="muted">Automatic capture uses <code>Every seconds</code>. Set it to <code>0</code> to disable scheduling for that camera.</p>
    <table><thead><tr><th>ID</th><th>Label</th><th>Assigned peripheral</th><th>Capture dir</th><th>Every seconds</th><th>Autofocus</th><th>Autofocus delay ms</th></tr></thead><tbody>{''.join(camera_setup_rows)}</tbody></table>
    <button id="save-cameras" type="button">Save cameras</button> <span id="cameras-status" class="status">Ready.</span>
  </section>

  <script id="hidden-scheduler-controllers" type="application/json">{json_script_text(hidden_controllers)}</script>
  <script>
    function cleanObject(value) {{
      const result = {{}};
      for (const [key, item] of Object.entries(value)) {{
        if (item !== "" && item !== null && item !== undefined) result[key] = item;
      }}
      return result;
    }}
    function hydrateControllerRowFromHidden(row) {{
      const key = row.querySelector(".controller-id").value.trim();
      const hiddenController = hiddenControllers[key];
      if (!key || !hiddenController || row.dataset.controllerKey) return;
      const hiddenPayload = hiddenController.payload || {{}};
      const hiddenSettings = hiddenController.settings || {{}};
      const labelInput = row.querySelector(".controller-label");
      labelInput.value = hiddenSettings.label || "";
      labelInput.defaultValue = hiddenSettings.label || "";
      const picoSerialSelect = row.querySelector(".controller-pico-serial");
      picoSerialSelect.value = hiddenPayload.pico_serial || "";
      picoSerialSelect.dataset.defaultValue = hiddenPayload.pico_serial || "";
      const reportEveryInput = row.querySelector(".controller-report-every");
      reportEveryInput.value = String((hiddenPayload.report_every ?? reportEveryInput.defaultValue) || "");
      reportEveryInput.defaultValue = String((hiddenPayload.report_every ?? reportEveryInput.defaultValue) || "");
    }}
    const hiddenControllers = JSON.parse(document.getElementById("hidden-scheduler-controllers").textContent || "{{}}");
    const repoRootPath = {repo_root_path_json};
    function normalizeCaptureDirPath(value) {{
      const raw = String(value || "").trim();
      if (!raw) return "";
      if (!raw.startsWith("/")) return raw.replace(/^\\.\\//, "");
      const root = String(repoRootPath || "").replace(/\\/$/, "");
      if (!root) return raw;
      if (raw === root) return "";
      if (raw.startsWith(root + "/")) return raw.slice(root.length + 1);
      throw new Error(`Capture dir must be inside repo root ${{root}} or be relative.`);
    }}
    for (const row of document.querySelectorAll(".controller-row.new-row")) {{
      row.querySelector(".controller-pico-serial").dataset.defaultValue = row.querySelector(".controller-pico-serial").value;
      row.querySelector(".controller-id").addEventListener("input", () => hydrateControllerRowFromHidden(row));
    }}
    function collectControllers() {{
      const result = structuredClone(hiddenControllers);
      for (const row of document.querySelectorAll(".controller-row")) {{
        const key = row.querySelector(".controller-id").value.trim();
        if (!key) continue;
        const oldKey = row.dataset.controllerKey || "";
        const picoSerialSelect = row.querySelector(".controller-pico-serial");
        const picoSerial = picoSerialSelect.value;
        const picoSerialDefault = picoSerialSelect.dataset.defaultValue || "";
        const labelInput = row.querySelector(".controller-label");
        const label = labelInput.value.trim();
        const type = row.querySelector(".controller-type").value;
        const reportEveryInput = row.querySelector(".controller-report-every");
        const reportEvery = reportEveryInput.value;
        const existingController = hiddenControllers[key] ? structuredClone(hiddenControllers[key]) : (oldKey && hiddenControllers[oldKey] ? structuredClone(hiddenControllers[oldKey]) : {{}});
        const isHiddenReuse = !row.dataset.controllerKey && Object.keys(existingController).length > 0;
        const payload = isHiddenReuse ? existingController : {{type, payload: {{}}, settings: {{}}}};
        if (oldKey && oldKey !== key) delete result[oldKey];
        payload.type = type;
        payload.payload = payload.payload || {{}};
        payload.settings = payload.settings || {{}};
        if (!isHiddenReuse || label !== labelInput.defaultValue) payload.settings.label = label;
        if (!isHiddenReuse || picoSerial !== picoSerialDefault) payload.payload.pico_serial = picoSerial;
        if (type === "pico_scheduler") {{
          if (reportEvery === "") {{
            if (!isHiddenReuse) throw new Error(`Report interval required for controller ${{key}}.`);
          }} else {{
            if (!isHiddenReuse || reportEvery !== reportEveryInput.defaultValue) payload.payload.report_every = Number(reportEvery);
          }}
        }}
        payload.settings = cleanObject(payload.settings);
        payload.payload = cleanObject(payload.payload);
        result[key] = payload;
      }}
      return result;
    }}
    function collectControllerDevices() {{
      const result = {{}};
        for (const row of document.querySelectorAll(".device-row")) {{
            const key = row.querySelector(".device-id").value.trim();
            if (!key) continue;
            const pinValue = row.querySelector(".device-pin").value;
            if (pinValue === "") throw new Error(`Pin required for device ${{key}}.`);
            const blockController = row.closest(".pico-scheduler-block")?.querySelector(".controller-row .controller-id")?.value.trim() || "";
            const controller = blockController || row.dataset.deviceController || "";
            if (!controller) throw new Error(`Controller required for device ${{key}}.`);
            result[controller] = result[controller] || {{settings: {{}}, payload: null}};
            const editor = row.querySelector(".device-editor").value;
            const existingEditor = JSON.parse(row.dataset.deviceEditorJson || "{{}}");
            const editorPayload = editor === "clock_window"
              ? (existingEditor.kind === "daily_window" && existingEditor.on_time && existingEditor.off_time ? existingEditor : {{kind: "daily_window", on_time: "06:00", off_time: "18:00"}})
              : (editor === "cycle" && existingEditor.kind === "cycle" ? existingEditor : (editor === "disabled" || editor === "hidden") && existingEditor.kind ? existingEditor : {{kind: "cycle"}});
            const semantic = cleanObject({{
              pin: Number(pinValue),
              label: row.querySelector(".device-label").value.trim(),
              display_order: Object.keys(result[controller].settings).length,
              visibility: editor === "hidden" ? "hidden" : "visible",
              programming: editor === "disabled" ? "disabled" : "enabled",
              editor: editorPayload,
              output_type: row.querySelector(".device-type").value,
            }});
            result[controller].settings[key] = semantic;
        }}
        return result;
    }}
    function collectCameras() {{
      const result = {{}};
      for (const row of document.querySelectorAll(".camera-row")) {{
        const key = row.querySelector(".camera-id").value.trim();
        if (!key) continue;
        const everySecondsRaw = row.querySelector(".camera-capture-every-seconds").value.trim();
        const autofocusDelayRaw = row.querySelector(".camera-autofocus-delay-ms").value.trim();
        result[key] = cleanObject({{
          label: row.querySelector(".camera-label").value.trim(),
          detected_key: row.querySelector(".camera-detected-key").value,
          capture_dir: normalizeCaptureDirPath(row.querySelector(".camera-capture-dir").value),
          capture_every_seconds: everySecondsRaw === "" ? null : Number(everySecondsRaw),
          autofocus_mode: row.querySelector(".camera-autofocus-mode").value,
          autofocus_delay_ms: autofocusDelayRaw === "" ? null : Number(autofocusDelayRaw),
        }});
      }}
      return result;
    }}
    function controllerRenames() {{
      const result = {{}};
      for (const row of document.querySelectorAll(".controller-row")) {{
        const oldKey = row.dataset.controllerKey || "";
        const newKey = row.querySelector(".controller-id").value.trim();
        if (oldKey && newKey && oldKey !== newKey) result[oldKey] = newKey;
      }}
      return result;
    }}
    function collectConfigWithControllerRenames() {{
      const controllers = collectControllers();
      const devicesByController = collectControllerDevices();
      const renames = controllerRenames();
      for (const [oldKey, newKey] of Object.entries(renames)) {{
        if (devicesByController[oldKey]) {{
          devicesByController[newKey] = devicesByController[oldKey];
          delete devicesByController[oldKey];
        }}
      }}
      for (const [controller, devices] of Object.entries(devicesByController)) {{
        if (!controllers[controller]) throw new Error(`Unknown controller for devices: ${{controller}}.`);
        controllers[controller].settings = controllers[controller].settings || {{}};
        controllers[controller].payload = controllers[controller].payload || {{}};
        controllers[controller].settings.devices = devices.settings;
        delete controllers[controller].payload.devices;
      }}
      return {{controllers, cameras: collectCameras()}};
    }}
    async function saveSection(statusId, url, payload) {{
      const status = document.getElementById(statusId);
      status.textContent = "Saving...";
      try {{
        const response = await fetch(url, {{method: "PUT", headers: {{"content-type": "application/json"}}, body: JSON.stringify(payload)}});
        status.textContent = response.ok ? "Saved." : `${{response.status}} ${{await response.text()}}`;
        if (response.ok) window.location.reload();
      }} catch (error) {{
        status.textContent = error.message || String(error);
      }}
    }}
    function runSave(statusId, callback) {{
      const status = document.getElementById(statusId);
      try {{
        callback();
      }} catch (error) {{
        status.textContent = error.message || String(error);
      }}
    }}
    document.getElementById("save-controllers").addEventListener("click", () => runSave("controllers-status", () => saveSection("controllers-status", "/api/config", collectConfigWithControllerRenames())));
    document.getElementById("save-devices").addEventListener("click", () => runSave("devices-status", () => saveSection("devices-status", "/api/config", collectConfigWithControllerRenames())));
    document.getElementById("save-cameras").addEventListener("click", () => runSave("cameras-status", () => saveSection("cameras-status", "/api/config/cameras", collectCameras())));
  </script>
</body>
</html>"""


def render_system_info_page(system: dict[str, Any], logs_text: str = "") -> str:
    host = system.get("host") if isinstance(system.get("host"), dict) else {}
    host_time = system.get("host_time") if isinstance(system.get("host_time"), dict) else {}
    software = system.get("software") if isinstance(system.get("software"), dict) else {}
    paths = system.get("paths") if isinstance(system.get("paths"), dict) else {}
    storage = system.get("storage") if isinstance(system.get("storage"), dict) else {}
    log_info = system.get("log") if isinstance(system.get("log"), dict) else {}
    detected = system.get("detected") if isinstance(system.get("detected"), dict) else {}
    monitors = system.get("monitors") if isinstance(system.get("monitors"), dict) else {}
    camera_worker = system.get("camera_worker") if isinstance(system.get("camera_worker"), dict) else {}
    picos = detected.get("picos") if isinstance(detected.get("picos"), list) else []
    cameras = detected.get("cameras") if isinstance(detected.get("cameras"), list) else []
    page_name = f"{host.get('hostname') or 'Plamp'} System"
    git_short_commit = software.get("git_short_commit") or software.get("git_commit") or "unknown"
    git_branch = software.get("git_branch") or "unknown"
    git_commit_timestamp = software.get("git_commit_timestamp") or "unknown"
    git_commit_relative = relative_time_label(software.get("git_commit_timestamp"))
    git_commit_timestamp_display = (
        f"{git_commit_timestamp} ({git_commit_relative})" if git_commit_relative else str(git_commit_timestamp)
    )

    git_dirty = software.get("git_dirty")
    git_dirty_files = software.get("git_dirty_files") if isinstance(software.get("git_dirty_files"), list) else []
    if git_dirty is None:
        git_dirty_display = "unknown"
    elif not git_dirty:
        git_dirty_display = "no"
    else:
        dirty_preview = ", ".join(str(path) for path in git_dirty_files[:2] if path)
        if len(git_dirty_files) > 2:
            dirty_preview = f"{dirty_preview}, ..." if dirty_preview else "..."
        git_dirty_display = f"yes: {dirty_preview}" if dirty_preview else "yes"
    os_name = str(software.get("os_name") or "unknown")
    os_arch = str(software.get("os_arch") or "unknown")
    os_version = str(software.get("os_version") or "unknown")
    os_display = f"{os_name} {os_version}; arch {os_arch}"
    user_name = str(software.get("user_name") or "unknown")
    user_is_sudoer = bool(software.get("user_is_sudoer"))
    user_has_serial_access = bool(software.get("user_has_serial_access"))
    user_has_video_access = bool(software.get("user_has_video_access"))
    user_display = (
        f"{user_name}; sudoer {'yes' if user_is_sudoer else 'no'}; "
        f"serial {'yes' if user_has_serial_access else 'no'}; "
        f"video {'yes' if user_has_video_access else 'no'}"
    )
    mpremote_path = str(software.get("mpremote_path") or "not found")
    mpremote_version = str(software.get("mpremote_version") or "").strip()
    mpremote_version_suffix = mpremote_version.removeprefix("mpremote ").strip()
    mpremote_display = mpremote_path if not mpremote_version_suffix else f"{mpremote_path} version {mpremote_version_suffix}"
    pyserial_value = str(system.get("tools", {}).get("pyserial") or "-")
    pyserial_display = pyserial_value if pyserial_value in {"-", "unknown"} else f"version {pyserial_value}"
    def camera_status_name(item: dict[str, Any]) -> str:
        connector = item.get("connector")
        if connector:
            return str(connector)
        index = item.get("index")
        if index is not None:
            return f"cam{index}"
        key = normalize_camera_key(item.get("key"))
        return key or "-"
    pico_rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(str(item.get('port') or '-'))}</td>"
        f"<td>{html.escape(str(item.get('usb_device') or '-'))}</td>"
        f"<td>{html.escape(str(item.get('serial') or '-'))}</td>"
        f"<td>{html.escape(str(item.get('vendor_id') or '-'))}:{html.escape(str(item.get('product_id') or '-'))}</td>"
        "</tr>"
        for item in picos
    ) or '<tr><td colspan="4">No peripherals found.</td></tr>'
    camera_rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(camera_status_name(item))}</td>"
        f"<td>{html.escape(camera_model_label(item))}</td>"
        f"<td>{html.escape(str(item.get('sensor') or '-'))}</td>"
        f"<td>{html.escape(str(item.get('lens') or '-'))}</td>"
        f"<td><code>{html.escape(str(item.get('path') or '-'))}</code></td>"
        "</tr>"
        for item in cameras
    ) or '<tr><td colspan="5">No Raspberry Pi cameras found.</td></tr>'
    software_rows = (
        "<tr><td>Plamp root</td>" f"<td><code>{html.escape(str(paths.get('repo_root') or software.get('path') or '-'))}</code></td></tr>"
        "<tr><td>Plamp data</td>" f"<td><code>{html.escape(str(paths.get('data_dir') or '-'))}</code></td></tr>"
        "<tr><td>Operating system</td>" f"<td><code>{html.escape(os_display)}</code></td></tr>"
        "<tr><td>User name</td>" f"<td><code>{html.escape(user_display)}</code></td></tr>"
        "<tr><td>Git commit</td>" f"<td><code>{html.escape(str(git_short_commit))}</code></td></tr>"
        "<tr><td>Git branch</td>" f"<td><code>{html.escape(str(git_branch))}</code></td></tr>"
        "<tr><td>Git commit time</td>" f"<td><code>{html.escape(git_commit_timestamp_display)}</code></td></tr>"
        "<tr><td>Git dirty</td>" f"<td><code>{html.escape(git_dirty_display)}</code></td></tr>"
        "<tr><td>mpremote</td>" f"<td><code>{html.escape(mpremote_display)}</code></td></tr>"
        "<tr><td>pyserial</td>" f"<td><code>{html.escape(pyserial_display)}</code></td></tr>"
    )
    rows = [
        ("Hostname", host.get("hostname") or ""),
        ("Host time", host_time.get("display") or ""),
        ("Detected picos", len(picos)),
        ("Detected cameras", len(cameras)),
        ("Repo root", paths.get("repo_root") or ""),
        ("Data dir", paths.get("data_dir") or ""),
        ("Log file", log_info.get("path") or ""),
    ]
    rows_html = "".join(
        f"<tr><th scope=\"row\">{html.escape(str(label))}</th><td>{html.escape(str(value))}</td></tr>"
        for label, value in rows
    )
    logs_value = html.escape(logs_text or "", quote=False)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(page_name)}</title>
  {FAVICON_LINK}
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; line-height: 1.4; }}
    nav {{ margin-bottom: 1.5rem; }}
    section {{ border-top: 1px solid #ddd; margin-top: 2rem; padding-top: 1rem; }}
    a {{ color: #174ea6; }}
    button {{ -webkit-appearance: none; appearance: none; background: #fff; border: 1px solid #222; border-radius: 6px; color: #111; font: inherit; margin: .25rem .25rem .25rem 0; padding: .45rem .7rem; }}
    .system-page {{ max-width: 1100px; }}
    .system-actions {{ display: flex; flex-wrap: wrap; gap: .5rem; }}
    .system-status {{ color: #555; min-height: 1.25rem; }}
    table {{ border-collapse: collapse; margin: 1rem 0 1.5rem; width: 100%; max-width: 1100px; }}
    th, td {{ border: 1px solid #ccc; padding: .45rem .6rem; text-align: left; vertical-align: top; }}
    th {{ background: #f4f4f4; }}
    code {{ background: #f4f4f4; padding: .1rem .25rem; }}
    .muted, .system-status {{ color: #555; font-size: .9rem; }}
    .host-clock {{ color: #555; font-size: .95rem; }}
    pre {{ background: #f8f9fa; border: 1px solid #ddd; border-radius: 6px; overflow: auto; padding: .75rem; white-space: pre-wrap; }}
    .logs-actions {{ align-items: center; display: flex; flex-wrap: wrap; gap: .5rem; }}
  </style>
</head>
<body>
  {MAIN_NAV}
  <h1>{html.escape(page_name)}</h1>
  <p class="host-clock"><strong>Host time:</strong> {html.escape(str(host_time.get("display") or "-"))}</p>
  <div class="system-page">
    <section aria-label="System summary">
      <h2>System info</h2>
      <table>
        <tbody>{rows_html}</tbody>
      </table>
    </section>
    <section aria-label="Detected hardware">
      <h2>Detected hardware</h2>
      <h3>Peripherals</h3>
      <table>
        <thead><tr><th>Port</th><th>USB Device</th><th>Serial</th><th>USB ID</th></tr></thead>
        <tbody>{pico_rows}</tbody>
      </table>
      <h3>Raspberry Pi cameras</h3>
      <table>
        <thead><tr><th>Camera</th><th>Model</th><th>Sensor</th><th>Lens</th><th>Path</th></tr></thead>
        <tbody>{camera_rows}</tbody>
      </table>
    </section>
    <section aria-label="System software">
      <h2>Software</h2>
      <p class="muted">Detected software and runtime details.</p>
      <table>
        <tbody>{software_rows}</tbody>
      </table>
    </section>
    <section aria-label="System storage">
      <h2>Storage</h2>
      <table>
        <thead><tr><th>Path</th><th>Free</th><th>Used</th><th>Total</th></tr></thead>
        <tbody><tr><td><code>{html.escape(str(storage.get("path") or "-"))}</code></td><td>{html.escape(str(storage.get("free") or "-"))}</td><td>{html.escape(str(storage.get("used") or "-"))}</td><td>{html.escape(str(storage.get("total") or "-"))}</td></tr></tbody>
      </table>
    </section>
    <section aria-label="Camera worker">
      <h2>Camera worker</h2>
      <table>
        <thead><tr><th>Field</th><th>Value</th></tr></thead>
        <tbody>
          <tr><td>State</td><td><code>{html.escape(str(camera_worker.get("state") or "-"))}</code></td></tr>
          <tr><td>Available</td><td><code>{html.escape(str(camera_worker.get("available") if "available" in camera_worker else "-"))}</code></td></tr>
          <tr><td>Queue depth</td><td><code>{html.escape(str(camera_worker.get("queue_depth") or 0))}</code></td></tr>
          <tr><td>Last capture</td><td><code>{html.escape(str(camera_worker.get("last_capture_at") or "-"))}</code></td></tr>
          <tr><td>Last error</td><td><code>{html.escape(str(camera_worker.get("last_error") or "-"))}</code></td></tr>
          <tr><td>Scheduled cameras</td><td><code>{html.escape(", ".join(camera_worker.get("scheduled_cameras") or []) or "-")}</code></td></tr>
        </tbody>
      </table>
    </section>
    <section aria-label="Controller workers">
      <h2>Controller workers</h2>
      <table>
        <thead><tr><th>Role</th><th>Serial</th><th>State</th><th>Connected</th><th>Port</th><th>Last seen</th><th>Last error</th></tr></thead>
        <tbody>
          {''.join(
              (
                  '<tr>'
                  f'<td>{html.escape(role)}</td>'
                  f'<td>{html.escape(str(worker.get("serial") or "-"))}</td>'
                  f'<td>{html.escape(str(worker.get("state") or "-"))}</td>'
                  f'<td>{html.escape("yes" if worker.get("connected") else "no")}</td>'
                  f'<td>{html.escape(str(worker.get("port") or "-"))}</td>'
                  f'<td>{html.escape(str(worker.get("last_seen") or "-"))}</td>'
                  f'<td>{html.escape(str(worker.get("last_error") or "-"))}</td>'
                  '</tr>'
              )
              for role, worker in sorted(monitors.items())
          ) or '<tr><td colspan="7">No controller workers found.</td></tr>'}
        </tbody>
      </table>
    </section>
    <section aria-label="System actions">
      <h2>Actions</h2>
      <div class="system-actions">
        <button id="system-restart" type="button">Restart</button>
        <button id="system-reinstall" type="button">Reinstall</button>
        <button id="system-upgrade" type="button">Upgrade</button>
      </div>
      <div class="system-status" id="system-action-status">Ready.</div>
    </section>
    <section aria-label="System logs">
      <h2>Logs</h2>
      <div class="logs-actions">
        <button id="system-load-logs" type="button">Load logs</button>
      </div>
      <pre id="system-logs">{logs_value}</pre>
    </section>
  </div>
  <script>
    async function runAction(path, label) {{
      const status = document.getElementById("system-action-status");
      status.textContent = `${{label}}...`;
      const response = await fetch(path, {{method: "POST"}});
      const text = await response.text();
      let parsed = null;
      try {{ parsed = JSON.parse(text); }} catch (error) {{}}
      status.textContent = response.ok ? (parsed?.message || `${{label}} complete.`) : `${{response.status}} ${{parsed?.detail || text}}`;
    }}

    async function loadLogs() {{
      const logs = document.getElementById("system-logs");
      logs.textContent = "Loading...";
      const response = await fetch("/api/logs?lines=200");
      const text = await response.text();
      if (!response.ok) {{
        logs.textContent = `${{response.status}} ${{text}}`;
        return;
      }}
      let parsed = null;
      try {{ parsed = JSON.parse(text); }} catch (error) {{}}
      logs.textContent = parsed?.content || text;
    }}

    document.getElementById("system-restart").addEventListener("click", () => runAction("/api/system/restart", "Restarting"));
    document.getElementById("system-reinstall").addEventListener("click", () => runAction("/api/system/reinstall", "Reinstalling"));
    document.getElementById("system-upgrade").addEventListener("click", () => runAction("/api/system/upgrade", "Upgrading"));
    document.getElementById("system-load-logs").addEventListener("click", loadLogs);
  </script>
</body>
</html>"""

def render_timer_dashboard_page(
    roles: list[str],
    time_format: str,
    channels_by_role: dict[str, list[dict[str, Any]]] | None = None,
    host_seconds_since_midnight: int = 0,
    camera_ids: list[str] | None = None,
    hostname: str = "",
) -> str:
    page_name = f"{hostname} Plamp" if hostname else "Plamp"
    camera_options = "".join(
        f'<option value="{html.escape(camera_id, quote=True)}">{html.escape(camera_id)}</option>'
        for camera_id in (camera_ids or [])
    )
    if not camera_options:
        camera_options = '<option value="">Default camera</option>'
    template = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>__PAGE_NAME__</title>
  __FAVICON_LINK__
  <style>
    body { font-family: system-ui, sans-serif; margin: 2rem; line-height: 1.4; }
    nav { margin-bottom: 1.5rem; }
    a { color: #174ea6; }
    button { -webkit-appearance: none; appearance: none; background: #fff; border: 1px solid #222; border-radius: 6px; color: #111; font: inherit; margin: .25rem .25rem .25rem 0; padding: .45rem .7rem; }
    input, select { box-sizing: border-box; padding: .35rem; }
    .host-clock { color: #555; font-size: .95rem; margin: -.5rem 0 1rem; }
    .status-board { display: grid; gap: 1rem; margin: 1rem 0; max-width: 980px; }
    .controller-card { border: 1px solid #bbb; border-radius: 8px; display: grid; gap: .75rem; padding: .9rem; }
    .controller-top { align-items: baseline; display: flex; gap: .75rem; justify-content: space-between; }
    .controller-name { font-size: 1.1rem; font-weight: 700; }
    .controller-devices { display: grid; gap: .75rem; }
    .controller-actions { border-top: 1px solid #ddd; margin-top: .25rem; padding-top: .65rem; }
    .timer-card { border: 1px solid #ccc; border-radius: 6px; padding: .75rem; }
    .timer-top { align-items: baseline; display: flex; gap: .75rem; justify-content: space-between; }
    .timer-name { font-weight: 700; }
    .timer-value { border-radius: 6px; padding: .15rem .45rem; }
    .timer-value.on { background: #d9f7d9; }
    .timer-value.off { background: #eee; }
    .timer-meta { color: #555; font-size: .9rem; margin: .25rem 0 .5rem; }
    .timer-bar { background: #eee; border-radius: 6px; height: .65rem; overflow: hidden; }
    .timer-fill { background: #3b7f4a; height: 100%; width: 0; }
    .timer-fill.off { background: #888; }
    .device-schedule-editor { border: 1px solid #ddd; border-radius: 6px; display: grid; gap: .65rem; padding: .65rem; }
    .camera-panel { display: grid; gap: .75rem; margin: 1rem 0 2rem; max-width: 980px; }
    .camera-actions { align-items: center; display: flex; flex-wrap: wrap; gap: .75rem; }
    .camera-viewer { max-width: min(100%, 820px); }
    .camera-viewer[hidden] { display: none; }
    .capture-list { border: 1px solid #d0d0d0; display: grid; gap: 0; max-height: 22rem; max-width: 980px; overflow-y: auto; }
    .capture-list button { background: #fff; border: 0; border-left: 4px solid transparent; border-radius: 0; display: block; margin: 0; padding: .35rem .5rem; text-align: left; width: 100%; }
    .capture-list button:nth-child(odd) { background: #fff; }
    .capture-list button:nth-child(even) { background: #f6f7f8; }
    .capture-list button:hover { background: #e9f2ff; }
    .capture-list button.selected { background: #dcecff; border-left: 4px solid #174ea6; font-weight: 700; }
    .capture-pager { align-items: center; display: flex; flex-wrap: wrap; gap: .5rem; }
    .timer-editor[hidden] { display: none; }
    .editor-row[hidden] { display: none; }
    .editor-row { align-items: end; display: flex; flex-wrap: wrap; gap: .75rem; }
    .editor-row label { display: grid; gap: .25rem; }
    .editor-row select, .editor-row input { min-width: 8rem; }
    .editor-note { color: #555; font-size: .9rem; }
    .editor-error { color: #9a3412; font-weight: 600; }
    .editor-success { color: #166534; font-weight: 600; }
  </style>
</head>
<body>
  __MAIN_NAV__
  <h1>__PAGE_NAME__</h1>
  <h2>Controllers</h2>
  <p class="host-clock">Host time: <span id="host-clock">--:--</span></p>
  <p id="timer-stream-status">Connecting...</p>
  <div id="timer-status-board" class="status-board">Waiting for timer report...</div>

  <h2>Camera</h2>
  <section class="camera-panel" aria-label="Camera captures">
    <img id="camera-viewer" class="camera-viewer" alt="Selected camera capture" hidden>
    <div class="camera-actions">
      <label>Camera <select id="camera-capture-camera">__CAMERA_OPTIONS__</select></label>
      <button id="camera-capture" type="button">Take picture</button>
      <span id="camera-capture-status">Ready.</span>
    </div>
    <label>Show
      <select id="camera-capture-filter">
        <option value="all">All cameras</option>
      </select>
    </label>
    <div id="camera-capture-list" class="capture-list">Loading captures...</div>
    <div class="capture-pager">
      <label>Page <input id="camera-capture-page" type="number" min="1" step="1" value="1"></label>
      <button id="camera-capture-go" type="button">Go</button>
      <button id="camera-capture-prev" type="button">Previous</button>
      <button id="camera-capture-next" type="button">Next</button>
      <span id="camera-capture-page-status"></span>
    </div>
  </section>

  <footer>
    <span id="refresh-status">Refreshing in <span id="refresh-countdown">30</span>s.</span>
    <button id="resume-refresh" type="button" hidden>Resume auto-refresh</button>
  </footer>

  <script>
    const clockTimeFormat = __TIME_FORMAT__;
    const timerRoles = __ROLES__;
    const timerChannels = __CHANNELS__;
    let timerHostSecondsAtLoad = __HOST_SECONDS__;
    let timerHostLoadedAt = Date.now();
    const timerStatus = document.getElementById("timer-stream-status");
    const timerBoard = document.getElementById("timer-status-board");
    const hostClock = document.getElementById("host-clock");
    const refreshCountdown = document.getElementById("refresh-countdown");
    const refreshStatus = document.getElementById("refresh-status");
    const resumeRefreshButton = document.getElementById("resume-refresh");
    const cameraCaptureButton = document.getElementById("camera-capture");
    const cameraCaptureCamera = document.getElementById("camera-capture-camera");
    const cameraCaptureStatus = document.getElementById("camera-capture-status");
    const cameraViewer = document.getElementById("camera-viewer");
    const cameraCaptureFilter = document.getElementById("camera-capture-filter");
    const cameraCaptureList = document.getElementById("camera-capture-list");
    const cameraCapturePage = document.getElementById("camera-capture-page");
    const cameraCaptureGo = document.getElementById("camera-capture-go");
    const cameraCapturePrev = document.getElementById("camera-capture-prev");
    const cameraCaptureNext = document.getElementById("camera-capture-next");
    const cameraCapturePageStatus = document.getElementById("camera-capture-page-status");
    let refreshSeconds = 30;
    const timerEventSources = new Map();
    const timerMessages = new Map();
    let cameraCaptures = [];
    let cameraCaptureHasMore = false;
    let cameraCaptureOffset = 0;
    let cameraCaptureTotal = 0;
    let cameraCaptureTotalPages = 1;
    const cameraCapturePageSize = 30;
    let selectedCameraImageUrl = "";
    let activeEditor = null;
    let pendingTimerRender = false;

    function formatChangeTime(secondsFromNow) {
      const when = new Date(Date.now() + secondsFromNow * 1000);
      if (clockTimeFormat === "24h") {
        return when.toLocaleTimeString([], {hour: "2-digit", minute: "2-digit", hour12: false});
      }
      return when.toLocaleTimeString([], {hour: "numeric", minute: "2-digit"});
    }

    function formatChangeLabel(secondsFromNow) {
      if (!Number.isFinite(Number(secondsFromNow))) return "?";
      const seconds = Math.max(0, Math.ceil(Number(secondsFromNow)));
      return formatChangeTime(seconds) + " (" + seconds + " secs)";
    }

    function secondsToClock(seconds) {
      const normalized = ((seconds % 86400) + 86400) % 86400;
      const hours = Math.floor(normalized / 3600);
      const minutes = Math.floor((normalized % 3600) / 60);
      if (clockTimeFormat === "24h") {
        return String(hours).padStart(2, "0") + ":" + String(minutes).padStart(2, "0");
      }
      const hour = hours % 12 || 12;
      const suffix = hours < 12 ? "AM" : "PM";
      return hour + ":" + String(minutes).padStart(2, "0") + " " + suffix;
    }

    function hostSecondsNow() {
      const elapsed = Math.floor((Date.now() - timerHostLoadedAt) / 1000);
      return (timerHostSecondsAtLoad + elapsed) % 86400;
    }

    function updatePageRefreshStatus() {
      refreshStatus.textContent = `Refreshing in ${refreshSeconds}s.`;
    }

    function tickPageRefresh() {
      refreshSeconds -= 1;
      if (refreshSeconds <= 0) {
        window.location.reload();
        return;
      }
      updatePageRefreshStatus();
    }

    function stopPageAutoRefresh() {
      if (!pageRefreshTimer) return;
      window.clearInterval(pageRefreshTimer);
      pageRefreshTimer = null;
      refreshStatus.textContent = "Auto-refresh paused.";
      resumeRefreshButton.hidden = false;
    }

    function startPageAutoRefresh() {
      if (pageRefreshTimer) return;
      refreshSeconds = 30;
      updatePageRefreshStatus();
      resumeRefreshButton.hidden = true;
      pageRefreshTimer = window.setInterval(tickPageRefresh, 1000);
    }

    async function refreshHostClock() {
      if (!hostClock) return;
      try {
        const response = await fetch("/api/host-time");
        const data = await response.json();
        if (response.ok && typeof data.display === "string") {
          hostClock.textContent = data.display;
          if (Number.isFinite(Number(data.seconds_since_midnight))) {
            timerHostSecondsAtLoad = Number(data.seconds_since_midnight);
            timerHostLoadedAt = Date.now();
          }
          return;
        }
      } catch (error) {
      }
      hostClock.textContent = secondsToClock(hostSecondsNow());
    }

    function currentTimerStep(event) {
      const pattern = Array.isArray(event.pattern) ? event.pattern : [];
      if (!pattern.length) return null;
      const durations = pattern.map((step) => Number(step.dur));
      if (durations.some((duration) => !Number.isFinite(duration) || duration <= 0)) return null;
      const total = durations.reduce((sum, duration) => sum + duration, 0);
      let cycleT = Number(event.cycle_t ?? event.elapsed_t ?? event.current_t ?? 0);
      if (!Number.isFinite(cycleT)) cycleT = 0;
      if (Number(event.reschedule ?? 1)) {
        cycleT = ((cycleT % total) + total) % total;
      } else {
        cycleT = Math.min(Math.max(cycleT, 0), total);
      }
      let start = 0;
      for (let index = 0; index < pattern.length; index += 1) {
        const end = start + durations[index];
        if (cycleT < end || index === pattern.length - 1) {
          return {step: pattern[index], elapsed: Math.max(0, cycleT - start), duration: durations[index], remaining: Math.max(0, end - cycleT)};
        }
        start = end;
      }
      return null;
    }

    function timerDevicesFromMessage(message) {
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
    }

    function statusNode(message) {
      if (Array.isArray(message) && message.length === 1 && message[0] && typeof message[0] === "object" && "node" in message[0]) {
        return message[0].node;
      }
      return message;
    }

    function channelForEvent(role, event, index) {
      const channels = timerChannels[role] || [];
      const eventPin = Number(event?.pin);
      if (Number.isFinite(eventPin)) {
        const byPin = channels.find((channel) => Number(channel.pin) === eventPin);
        if (byPin) return byPin;
      }
      const eventId = event.id || "pin-" + (event.pin ?? index);
      return channels.find((channel) => channel.id === eventId) || {
        role,
        id: eventId,
        name: event.id || "pin " + (event.pin ?? index),
        pin: event.pin,
        type: event.type || "gpio",
        default_editor: "cycle",
      };
    }

    function twoStepDurations(event) {
      const pattern = Array.isArray(event.pattern) ? event.pattern : [];
      if (pattern.length !== 2) return null;
      const on = Number(pattern[0].dur);
      const off = Number(pattern[1].dur);
      const onValue = Number(pattern[0].val);
      const offValue = Number(pattern[1].val);
      if (!Number.isFinite(on) || !Number.isFinite(off) || on <= 0 || off <= 0 || onValue <= 0 || offValue !== 0) return null;
      return {on, off, total: on + off};
    }

    function chooseUnit(seconds) {
      if (seconds % 3600 === 0) return {value: seconds / 3600, unit: "hours"};
      if (seconds % 60 === 0) return {value: seconds / 60, unit: "minutes"};
      return {value: seconds, unit: "seconds"};
    }

    function chooseSharedUnit(values) {
      if (values.every((value) => value % 3600 === 0)) return "hours";
      if (values.every((value) => value % 60 === 0)) return "minutes";
      return "seconds";
    }

    function unitMultiplier(unit) {
      if (unit === "hours") return 3600;
      if (unit === "minutes") return 60;
      return 1;
    }

    function secondsToTimeInput(seconds) {
      const normalized = ((seconds % 86400) + 86400) % 86400;
      const hours = Math.floor(normalized / 3600);
      const minutes = Math.floor((normalized % 3600) / 60);
      return String(hours).padStart(2, "0") + ":" + String(minutes).padStart(2, "0");
    }

    function clockValuesForEvent(event) {
      const durations = twoStepDurations(event);
      if (!durations || durations.total !== 86400) return {on: "06:00", off: "18:00"};
      const cycleT = Number(event.cycle_t ?? event.current_t ?? 0) || 0;
      const onSeconds = ((hostSecondsNow() - cycleT) % 86400 + 86400) % 86400;
      return {on: secondsToTimeInput(onSeconds), off: secondsToTimeInput(onSeconds + durations.on)};
    }

    function showEditorMessage(message, className, text) {
      message.className = "editor-message" + (className ? " " + className : "");
      message.textContent = text;
    }

    function escapeHtml(value) {
      return String(value).replace(/[&<>"']/g, (char) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      }[char]));
    }

    function captureEditorFocus() {
      const form = timerBoard.querySelector("#timer-schedule-form");
      if (!activeEditor || !form || !form.contains(document.activeElement)) return null;
      const field = document.activeElement;
      const fieldName = field?.name;
      if (!fieldName) return null;
      return {
        name: fieldName,
        selectionStart: typeof field.selectionStart === "number" ? field.selectionStart : null,
        selectionEnd: typeof field.selectionEnd === "number" ? field.selectionEnd : null,
      };
    }

    function restoreEditorFocus(focusState) {
      if (!focusState) return;
      const form = timerBoard.querySelector("#timer-schedule-form");
      const field = form?.elements?.[focusState.name];
      if (!field || typeof field.focus !== "function") return;
      field.focus();
      if (typeof field.setSelectionRange === "function" && focusState.selectionStart !== null && focusState.selectionEnd !== null) {
        field.setSelectionRange(focusState.selectionStart, focusState.selectionEnd);
      }
    }

    function flushPendingTimerRender() {
      if (!pendingTimerRender) return;
      const form = timerBoard.querySelector("#timer-schedule-form");
      if (activeEditor && form && form.contains(document.activeElement)) return;
      pendingTimerRender = false;
      renderTimerStatus();
    }

    function scheduleEditorBlock(role, channel, event) {
      const durations = twoStepDurations(event) || {on: 60, off: 60, total: 120};
      const startAtSeconds = Number(event?.cycle_t);
      const safeStartAt = Number.isFinite(startAtSeconds) && startAtSeconds >= 0 ? startAtSeconds : 0;
      const sharedUnit = chooseSharedUnit([durations.on, durations.off, safeStartAt]);
      const divisor = unitMultiplier(sharedUnit);
      const clock = clockValuesForEvent(event);
      const mode = ["cycle", "clock_window", "disabled", "hidden"].includes(channel.default_editor) ? channel.default_editor : "cycle";
      return `
        <section class="device-schedule-editor" data-channel-id="${escapeHtml(channel.id)}" data-channel-pin="${escapeHtml(channel.pin ?? "")}" data-channel-type="${escapeHtml(channel.type || "gpio")}" data-channel-order="${escapeHtml(channel.display_order ?? 0)}">
          <div class="timer-top"><strong>${escapeHtml(channel.name)}</strong><span class="editor-note">${escapeHtml(role)} / pin ${escapeHtml(channel.pin ?? "?")} / ${escapeHtml(channel.type || "gpio")}</span></div>
          <div class="editor-row">
            <label>Set as
              <select class="editor-mode" name="mode-${escapeHtml(channel.id)}">
                <option value="cycle"${mode === "cycle" ? " selected" : ""}>Cycle set</option>
                <option value="clock_window"${mode === "clock_window" ? " selected" : ""}>24h set</option>
                <option value="disabled"${mode === "disabled" ? " selected" : ""}>disabled</option>
                <option value="hidden"${mode === "hidden" ? " selected" : ""}>hidden</option>
              </select>
            </label>
          </div>
          <div class="editor-row cycle-fields">
            <label>On for <input class="editor-on-value" name="onValue-${escapeHtml(channel.id)}" type="number" min="1" step="1" value="${durations.on / divisor}"></label>
            <label>Off for <input class="editor-off-value" name="offValue-${escapeHtml(channel.id)}" type="number" min="1" step="1" value="${durations.off / divisor}"></label>
            <label>Start at <input class="editor-start-at" name="startAtSeconds-${escapeHtml(channel.id)}" type="number" min="0" step="1" value="${safeStartAt / divisor}"></label>
            <label>Unit <select class="editor-cycle-unit" name="cycleUnit-${escapeHtml(channel.id)}"><option value="seconds"${sharedUnit === "seconds" ? " selected" : ""}>seconds</option><option value="minutes"${sharedUnit === "minutes" ? " selected" : ""}>minutes</option><option value="hours"${sharedUnit === "hours" ? " selected" : ""}>hours</option></select></label>
          </div>
          <div class="editor-row clock-fields">
            <label>On at <input class="editor-on-time" name="onTime-${escapeHtml(channel.id)}" type="time" value="${clock.on}"></label>
            <label>Off at <input class="editor-off-time" name="offTime-${escapeHtml(channel.id)}" type="time" value="${clock.off}"></label>
            <span class="editor-note">Applies using the host clock.</span>
          </div>
        </section>
      `;
    }

    function openControllerScheduleEditor(role) {
      stopPageAutoRefresh();
      activeEditor = {role};
      renderTimerStatus(true);
    }

    function syncEditorMode(block) {
      const mode = block.querySelector(".editor-mode").value;
      const clock = mode === "clock_window";
      const scheduled = mode === "cycle" || clock;
      block.querySelector(".cycle-fields").hidden = !scheduled || clock;
      block.querySelector(".clock-fields").hidden = !clock;
    }

    async function submitScheduleEditor(event) {
      event.preventDefault();
      const form = event.currentTarget;
      const message = form.querySelector(".editor-message");
      showEditorMessage(message, "", "Saving...");
      try {
        let lastMessage = "";
        const role = form.dataset.role;
        const blocks = Array.from(form.querySelectorAll(".device-schedule-editor"));
        const configResponse = await fetch("/api/config");
        const configPayload = await configResponse.json();
        if (!configResponse.ok) {
          throw new Error(configPayload?.detail || `config: ${configResponse.status} ${configResponse.statusText}`);
        }
        const controllers = structuredClone(configPayload?.config?.controllers || {});
        const controller = structuredClone(controllers[role] || {});
        controller.settings = structuredClone(controller.settings || {});
        controller.settings.devices = structuredClone(controller.settings.devices || {});
        for (const block of blocks) {
          const channelId = block.dataset.channelId;
          const mode = block.querySelector(".editor-mode").value;
          const device = structuredClone(controller.settings.devices[channelId] || {});
          device.pin = Number(block.dataset.channelPin);
          device.output_type = block.dataset.channelType || "gpio";
          device.display_order = Number(block.dataset.channelOrder || 0);
          device.visibility = mode === "hidden" ? "hidden" : "visible";
          device.programming = mode === "disabled" ? "disabled" : "enabled";
          const existingEditor = structuredClone(device.editor || {});
          device.editor = mode === "clock_window"
            ? (existingEditor.kind === "daily_window" && existingEditor.on_time && existingEditor.off_time
                ? existingEditor
                : {kind: "daily_window", on_time: "06:00", off_time: "18:00"})
            : (mode === "cycle" || mode === "disabled" || mode === "hidden")
              ? (existingEditor.kind ? existingEditor : {kind: "cycle", on_seconds: 60, off_seconds: 60, start_at_seconds: 0})
              : existingEditor;
          controller.settings.devices[channelId] = device;
        }
        controllers[role] = controller;
        const saveConfigResponse = await fetch("/api/config/controllers", {
          method: "PUT",
          headers: {"content-type": "application/json"},
          body: JSON.stringify(controllers),
        });
        const saveConfigText = await saveConfigResponse.text();
        let saveConfigParsed = null;
        try { saveConfigParsed = JSON.parse(saveConfigText); } catch (error) {}
        if (!saveConfigResponse.ok) {
          throw new Error(saveConfigParsed?.detail || saveConfigText || `config save: ${saveConfigResponse.status} ${saveConfigResponse.statusText}`);
        }
        const applyConfigResponse = await fetch(`/api/controllers/${encodeURIComponent(role)}/apply`, {method: "POST"});
        const applyConfigText = await applyConfigResponse.text();
        let applyConfigParsed = null;
        try { applyConfigParsed = JSON.parse(applyConfigText); } catch (error) {}
        if (!applyConfigResponse.ok) {
          throw new Error(applyConfigParsed?.detail || applyConfigText || `apply config: ${applyConfigResponse.status} ${applyConfigResponse.statusText}`);
        }
        lastMessage = applyConfigParsed?.message || "Schedule settings saved.";
        for (const block of blocks) {
          const channelId = block.dataset.channelId;
          const mode = block.querySelector(".editor-mode").value;
          if (mode !== "cycle" && mode !== "clock_window") continue;
          const body = {mode};
          if (mode === "cycle") {
            const cycleUnit = block.querySelector(".editor-cycle-unit").value;
            const multiplier = unitMultiplier(cycleUnit);
            body.on_seconds = Number(block.querySelector(".editor-on-value").value) * multiplier;
            body.off_seconds = Number(block.querySelector(".editor-off-value").value) * multiplier;
            body.start_at_seconds = Number(block.querySelector(".editor-start-at").value) * multiplier;
          } else {
            body.on_time = block.querySelector(".editor-on-time").value;
            body.off_time = block.querySelector(".editor-off-time").value;
          }
          const response = await fetch(`/api/controllers/${encodeURIComponent(role)}/channels/${encodeURIComponent(channelId)}/schedule`, {
            method: "POST",
            headers: {"content-type": "application/json"},
            body: JSON.stringify(body),
          });
          const text = await response.text();
          let parsed = null;
          try { parsed = JSON.parse(text); } catch (error) {}
          if (!response.ok) {
            throw new Error(`${channelId}: ${parsed?.detail || text || `${response.status} ${response.statusText}`}`);
          }
          lastMessage = parsed?.message || "Schedule applied. Waiting for report...";
        }
        for (const block of blocks) {
          const channelId = block.dataset.channelId;
          const channel = (timerChannels[role] || []).find((item) => item.id === channelId);
          if (channel) channel.default_editor = block.querySelector(".editor-mode").value;
        }
        activeEditor = null;
        renderTimerStatus(true);
        showEditorMessage(message, "editor-success", lastMessage || "Schedule settings saved.");
      } catch (error) {
        showEditorMessage(message, "editor-error", String(error.message || error));
      }
    }

    function renderTimerStatus(force = false) {
      const activeForm = timerBoard.querySelector("#timer-schedule-form");
      if (!force && activeEditor && activeForm && activeForm.contains(document.activeElement)) {
        pendingTimerRender = true;
        return;
      }
      pendingTimerRender = false;
      const focusState = captureEditorFocus();
      timerBoard.replaceChildren();
      let rendered = 0;
      for (const role of timerRoles) {
        const message = timerMessages.get(role);
        const devices = timerDevicesFromMessage(message);
        const channels = timerChannels[role] || [];
        const liveByPin = new Map();
        for (const device of devices) {
          const pin = Number(device?.pin);
          if (Number.isFinite(pin)) liveByPin.set(pin, device);
        }
        const items = channels.length
          ? channels.map((channel) => ({channel, event: liveByPin.get(Number(channel.pin)), index: 0}))
          : devices.map((device, index) => ({channel: channelForEvent(role, device, index), event: device, index}));
        const isEditing = activeEditor && activeEditor.role === role;
        const controllerCard = document.createElement(isEditing ? "form" : "section");
        if (isEditing) {
          controllerCard.id = "timer-schedule-form";
          controllerCard.dataset.role = role;
        }
        controllerCard.className = "controller-card";
        const controllerTop = document.createElement("div");
        controllerTop.className = "controller-top";
        const controllerName = document.createElement("span");
        controllerName.className = "controller-name";
        controllerName.textContent = role;
        const controllerMeta = document.createElement("span");
        controllerMeta.className = "editor-note";
        controllerMeta.textContent = items.length + " device" + (items.length === 1 ? "" : "s");
        controllerTop.append(controllerName, controllerMeta);
        const devicesGrid = document.createElement("div");
        devicesGrid.className = "controller-devices";
        let configurableCount = items.length;
        for (const item of items) {
          const channel = item.channel;
          const disabled = channel.default_editor === "disabled";
          const hidden = channel.default_editor === "hidden";
          const event = item.event || {id: channel.id, pin: channel.pin, type: channel.type || "gpio"};
          const step = currentTimerStep(event);
          const value = Number(step?.step?.val ?? event.current_value ?? 0);
          const isOn = value > 0;
          const percent = step ? Math.max(0, Math.min(100, (step.elapsed / step.duration) * 100)) : 0;
          const card = document.createElement("div");
          card.className = "timer-card";
          const top = document.createElement("div");
          top.className = "timer-top";
          const name = document.createElement("span");
          name.className = "timer-name";
          name.textContent = channel.name;
          const badge = document.createElement("span");
          badge.className = "timer-value " + (isOn ? "on" : "off");
          badge.textContent = hidden ? "HIDDEN" : (disabled ? "DISABLED" : (isOn ? "ON" : "OFF"));
          top.append(name, badge);
          const meta = document.createElement("div");
          meta.className = "timer-meta";
          meta.textContent = "pin " + (channel.pin ?? event.pin ?? "?") + " | " + (channel.type || event.type || "timer") + " | value " + value + " | changes at " + (step ? formatChangeLabel(step.remaining) : "?");
          const bar = document.createElement("div");
          bar.className = "timer-bar";
          const fill = document.createElement("div");
          fill.className = "timer-fill" + (isOn ? "" : " off");
          fill.style.width = percent + "%";
          bar.append(fill);
          card.append(top, meta, bar);
          if (!hidden || isEditing) {
            devicesGrid.append(card);
            if (isEditing) {
              const editor = document.createElement("div");
              editor.innerHTML = scheduleEditorBlock(role, channel, event);
              const block = editor.firstElementChild;
              if (block) {
                card.append(block);
              }
            }
            rendered += 1;
          }
        }
        controllerCard.append(controllerTop, devicesGrid);
        if (isEditing) {
          const actions = document.createElement("div");
          actions.className = "controller-actions controller-actions-editing";
          actions.innerHTML = `
            <button type="submit">Apply schedule</button>
            <button type="button" name="cancel">Close</button>
            <span class="editor-message" aria-live="polite"></span>
          `;
          for (const block of controllerCard.querySelectorAll(".device-schedule-editor")) {
            syncEditorMode(block);
            block.querySelector(".editor-mode").addEventListener("change", () => syncEditorMode(block));
          }
          controllerCard.addEventListener("focusout", () => window.setTimeout(flushPendingTimerRender, 0));
          controllerCard.addEventListener("submit", submitScheduleEditor);
          controllerCard.append(actions);
          actions.querySelector('[name="cancel"]').addEventListener("click", () => { activeEditor = null; renderTimerStatus(true); });
        } else {
          const actions = document.createElement("div");
          actions.className = "controller-actions";
          if (configurableCount > 0) {
            const edit = document.createElement("button");
            edit.type = "button";
            edit.textContent = "Edit schedule";
            edit.addEventListener("click", () => openControllerScheduleEditor(role));
            actions.append(edit);
          } else {
            actions.textContent = "No configured device schedules.";
          }
          controllerCard.append(actions);
        }
        if (isEditing) {
          controllerCard.classList.add("controller-card-editing");
        }
        timerBoard.append(controllerCard);
      }
      restoreEditorFocus(focusState);
      if (!rendered) {
        timerBoard.textContent = timerRoles.length ? "Waiting for timer reports..." : "No timers configured in data/config.json.";
      }
    }

    function updateCameraFilters() {
      const selected = cameraCaptureFilter.value;
      const options = new Map([["all", "All cameras"]]);
      if (selected.startsWith("camera:")) {
        options.set(selected, cameraCaptureFilter.selectedOptions[0]?.textContent || selected.slice(7));
      }
      for (const capture of cameraCaptures) {
        if (capture.camera_id) {
          options.set("camera:" + capture.camera_id, capture.camera_id);
        }
      }
      cameraCaptureFilter.replaceChildren();
      for (const [value, label] of options.entries()) {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = label;
        cameraCaptureFilter.append(option);
      }
      cameraCaptureFilter.value = options.has(selected) ? selected : "all";
    }

    function cameraCaptureRequestUrl() {
      const params = new URLSearchParams({limit: String(cameraCapturePageSize), offset: String(cameraCaptureOffset)});
      const filter = cameraCaptureFilter.value;
      if (filter.startsWith("camera:")) {
        params.set("camera_id", filter.slice(7));
      }
      return `/api/camera/captures?${params.toString()}`;
    }

    function cameraCapturePostUrl() {
      const params = new URLSearchParams();
      if (cameraCaptureCamera.value) {
        params.set("camera_id", cameraCaptureCamera.value);
      }
      const query = params.toString();
      return query ? `/api/camera/captures?${query}` : "/api/camera/captures";
    }

    function pageOffset() {
      const value = Number(cameraCapturePage.value || 1);
      const page = Math.max(1, Math.floor(Number.isFinite(value) ? value : 1));
      return (page - 1) * cameraCapturePageSize;
    }

    function selectCameraCapture(capture) {
      if (!capture || typeof capture.image_url !== "string") return;
      selectedCameraImageUrl = capture.image_url;
      cameraViewer.src = capture.image_url;
      cameraViewer.hidden = false;
      for (const button of cameraCaptureList.querySelectorAll("button")) {
        button.classList.toggle("selected", button.dataset.imageUrl === selectedCameraImageUrl);
      }
    }

    function captureLabel(capture) {
      const parts = [];
      if (capture.timestamp) parts.push(new Date(capture.timestamp).toLocaleString());
      if (capture.capture_kind) parts.push(capture.capture_kind);
      if (capture.camera_id) parts.push("camera " + capture.camera_id);
      if (capture.brightness_mean !== undefined) parts.push("brightness " + capture.brightness_mean);
      return parts.join(" | ");
    }

    function renderCameraCaptures() {
      updateCameraFilters();
      const captures = cameraCaptures;
      cameraCaptureList.replaceChildren();
      if (!captures.length) {
        cameraCaptureList.textContent = cameraCaptureOffset ? "No more captures." : "No captures found.";
        cameraViewer.hidden = true;
        cameraViewer.removeAttribute("src");
        selectedCameraImageUrl = "";
        cameraCapturePrev.disabled = cameraCaptureOffset === 0;
        cameraCaptureNext.disabled = true;
        cameraCapturePage.max = String(Math.max(1, cameraCaptureTotalPages));
        cameraCapturePage.value = String(Math.max(1, Math.floor(cameraCaptureOffset / cameraCapturePageSize) + 1));
        cameraCapturePageStatus.textContent = cameraCaptureTotal ? `Page ${Math.max(1, Math.floor(cameraCaptureOffset / cameraCapturePageSize) + 1)} of ${cameraCaptureTotalPages} | Showing 0 of ${cameraCaptureTotal}` : "No captures";
        return;
      }
      for (const capture of captures) {
        const button = document.createElement("button");
        button.type = "button";
        button.dataset.imageUrl = capture.image_url || "";
        button.textContent = captureLabel(capture);
        button.addEventListener("click", () => selectCameraCapture(capture));
        cameraCaptureList.append(button);
      }
      const selected = captures.find((capture) => capture.image_url === selectedCameraImageUrl) || captures[0];
      selectCameraCapture(selected);
      cameraCapturePrev.disabled = cameraCaptureOffset === 0;
      cameraCaptureNext.disabled = !cameraCaptureHasMore;
      cameraCapturePage.max = String(Math.max(1, cameraCaptureTotalPages));
      cameraCapturePage.value = String(Math.floor(cameraCaptureOffset / cameraCapturePageSize) + 1);
      const start = cameraCaptureOffset + 1;
      const end = cameraCaptureOffset + captures.length;
      const currentPage = Math.floor(cameraCaptureOffset / cameraCapturePageSize) + 1;
      cameraCapturePageStatus.textContent = `Page ${currentPage} of ${cameraCaptureTotalPages} | Showing ${start}-${end} of ${cameraCaptureTotal}`;
    }

    async function refreshCameraCaptures() {
      cameraCaptureList.textContent = "Loading captures...";
      try {
        const response = await fetch(cameraCaptureRequestUrl());
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || `${response.status} ${response.statusText}`);
        cameraCaptures = Array.isArray(data.captures) ? data.captures : [];
        const total = Number(data.total ?? 0);
        cameraCaptureTotal = Number.isFinite(total) ? total : 0;
        cameraCaptureTotalPages = Math.max(1, Math.ceil(cameraCaptureTotal / cameraCapturePageSize));
        cameraCaptureHasMore = Boolean(data.has_more);
        renderCameraCaptures();
      } catch (error) {
        cameraCaptureList.textContent = "Could not load captures.";
        cameraCaptureStatus.textContent = String(error.message || error);
      }
    }

    async function captureCameraImage() {
      cameraCaptureButton.disabled = true;
      cameraCaptureStatus.textContent = "Capturing...";
      try {
        const response = await fetch(cameraCapturePostUrl(), {method: "POST"});
        const text = await response.text();
        let data = null;
        try { data = JSON.parse(text); } catch (error) {}
        if (!response.ok) throw new Error(data?.detail || text || `${response.status} ${response.statusText}`);
        cameraCaptureStatus.textContent = "Captured.";
        if (data && typeof data.image_url === "string") {
          selectedCameraImageUrl = data.image_url;
          cameraViewer.src = data.image_url;
          cameraViewer.hidden = false;
        }
        cameraCaptureOffset = 0;
        await refreshCameraCaptures();
      } catch (error) {
        cameraCaptureStatus.textContent = String(error.message || error);
      } finally {
        cameraCaptureButton.disabled = false;
      }
    }

    function stopTimerStreams() {
      for (const source of timerEventSources.values()) {
        source.close();
      }
      timerEventSources.clear();
      timerStatus.textContent = "Not streaming.";
    }

    function startTimerStreams() {
      stopTimerStreams();
      timerMessages.clear();
      renderTimerStatus();
      if (!timerRoles.length) {
        timerStatus.textContent = "No timers configured.";
        return;
      }
      timerStatus.textContent = `${timerRoles.length} pico board${timerRoles.length === 1 ? "" : "s"}: ${timerRoles.join(", ")}`;
      for (const role of timerRoles) {
        const source = new EventSource(`/api/status?stream=true&path=${encodeURIComponent(`controllers.${role}.telemetry`)}`);
        timerEventSources.set(role, source);
        for (const eventName of ["snapshot", "update"]) {
          source.addEventListener(eventName, (event) => {
            timerMessages.set(role, statusNode(JSON.parse(event.data)));
            renderTimerStatus();
          });
        }
        source.onerror = () => {
          if (source.readyState === EventSource.CLOSED) {
            timerStatus.textContent = "Stream disconnected.";
          }
        };
      }
    }

    cameraCaptureButton.addEventListener("click", () => {
      stopPageAutoRefresh();
      captureCameraImage();
    });
    cameraCaptureList.addEventListener("click", stopPageAutoRefresh);
    cameraCaptureFilter.addEventListener("change", () => {
      stopPageAutoRefresh();
      cameraCaptureOffset = 0;
      refreshCameraCaptures();
    });
    cameraCaptureGo.addEventListener("click", () => {
      stopPageAutoRefresh();
      cameraCaptureOffset = pageOffset();
      refreshCameraCaptures();
    });
    cameraCapturePrev.addEventListener("click", () => {
      stopPageAutoRefresh();
      cameraCaptureOffset = Math.max(0, cameraCaptureOffset - cameraCapturePageSize);
      refreshCameraCaptures();
    });
    cameraCaptureNext.addEventListener("click", () => {
      stopPageAutoRefresh();
      cameraCaptureOffset += cameraCapturePageSize;
      refreshCameraCaptures();
    });
    window.addEventListener("beforeunload", stopTimerStreams);
    refreshHostClock();
    setInterval(refreshHostClock, 30000);
    let pageRefreshTimer = window.setInterval(tickPageRefresh, 1000);
    resumeRefreshButton.addEventListener("click", startPageAutoRefresh);
    startTimerStreams();
    refreshCameraCaptures();
  </script>
</body>
</html>"""
    return (
        template.replace("__MAIN_NAV__", MAIN_NAV)
        .replace("__PAGE_NAME__", html.escape(page_name))
        .replace("__FAVICON_LINK__", FAVICON_LINK)
        .replace("__TIME_FORMAT__", json.dumps(time_format))
        .replace("__ROLES__", json.dumps(roles))
        .replace("__CHANNELS__", json.dumps(channels_by_role or {}))
        .replace("__CAMERA_OPTIONS__", camera_options)
        .replace("__HOST_SECONDS__", json.dumps(host_seconds_since_midnight))
    )


def render_api_test_page(roles: list[str], default_role: str, default_payload: str, time_format: str) -> str:
    role_options = "\n".join(f'<option value="{html.escape(role)}"></option>' for role in roles)
    default_get_curl = f"curl http://localhost:8000/api/controllers/{default_role}"
    default_stream_curl = f"curl -N 'http://localhost:8000/api/controllers/{default_role}?stream=true'"
    default_status_paths = [f"config.controllers.{default_role}", f"controllers.{default_role}.telemetry"] if default_role else []
    default_status_path_rows = "".join(
        f'<div class="row status-path-row"><label>Path <input class="status-path-input" value="{html.escape(path, quote=True)}" placeholder="controllers.{html.escape(default_role, quote=True)}.telemetry"></label><button type="button" class="remove-status-path">Remove</button></div>'
        for path in default_status_paths
    )
    default_put_curl = "\n".join([
        f"curl -X PUT 'http://localhost:8000/api/controllers/{default_role}' " + chr(92),
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
  <title>Plamp API test</title>
  {FAVICON_LINK}
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
    .helper-title {{ font-weight: 700; margin: .75rem 0 .25rem; }}
    pre {{ background: #f4f4f4; padding: 1rem; overflow: auto; }}
    #put-curl-command, #stream-curl-command {{ white-space: pre-wrap; }}
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
  {MAIN_NAV}
  <h1>Plamp API test</h1>

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
    <legend>GET /api/system</legend>
    <p>Reads host facts and detected local hardware choices.</p>
    <pre id="get-system-curl-command">curl http://localhost:8000/api/system</pre>
    <button class="copy-curl" type="button" data-copy-target="get-system-curl-command">Copy curl</button>
    <button id="get-system" type="button">Run request</button>
    <div><span id="get-system-status">Ready.</span></div>
    <pre id="get-system-result">GET response will appear here.</pre>
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
    <legend>PUT /api/config/controllers</legend>
    <p>Saves named local Pico controllers.</p>
    <pre id="put-config-controllers-curl-command">curl -X PUT http://localhost:8000/api/config/controllers -H 'content-type: application/json' --data '{{}}'</pre>
    <button class="copy-curl" type="button" data-copy-target="put-config-controllers-curl-command">Copy curl</button>
    <button id="put-config-controllers" type="button">Run request</button>
    <div><span id="put-config-controllers-status">Ready.</span></div>
    <pre id="put-config-controllers-result">PUT response will appear here.</pre>
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
    <button id="start-stream" type="button">Start stream</button>
    <button id="stop-stream" type="button">Stop stream</button>
    <div><span id="stream-status">Not streaming.</span></div>
    <div id="timer-status-board" class="status-board">Start the stream to see status.</div>
    <pre id="stream-result">Stream status updates will appear here.</pre>
  </fieldset>

  <fieldset>
    <legend>PUT /api/controllers/{{role}}</legend>
    <p>Writes controller state JSON and sends it to the Pico.</p>
    <label>Role
      <input id="put-role" list="timer-roles" value="{html.escape(default_role)}">
    </label>

    <section>
      <p class="helper-title">Helper: Generate 5s pin test</p>
      <p>Builds a small GPIO payload in the PUT JSON editor.</p>
      <label>Test pin <input id="test-pin" type="number" min="0" max="29" value="25"></label>
      <button id="generate-quick" type="button">Generate pin test</button>
    </section>

    <section>
      <p class="helper-title">Helper: Generate pump/lights</p>
      <p>Builds a pump/lights payload in the PUT JSON editor.</p>
      <div class="row">
        <label>Pump pin <input id="pump-pin" type="number" min="0" max="29" value="15"></label>
        <label>Pump on minutes <input id="pump-on" type="number" min="1" value="5"></label>
        <label>Pump off minutes <input id="pump-off" type="number" min="1" value="30"></label>
        <label>Lights pin <input id="lights-pin" type="number" min="0" max="29" value="2"></label>
        <label>Lights on <input id="lights-on" type="time" step="1" value="06:00:00"></label>
        <label>Lights off <input id="lights-off" type="time" step="1" value="18:00:00"></label>
      </div>
      <button id="generate-pump-lights" type="button">Generate pump/lights</button>
    </section>

    <label>JSON payload
      <textarea id="payload">{html.escape(default_payload)}</textarea>
    </label>
    <pre id="put-curl-command">{html.escape(default_put_curl)}</pre>
    <button class="copy-curl" type="button" data-copy-target="put-curl-command">Copy curl</button>
    <button id="put-state" type="button">Run request</button>
    <div><span id="put-status">Ready.</span></div>
    <pre id="put-result">PUT response will appear here.</pre>
  </fieldset>

  <script>
    const payload = document.getElementById("payload");
    const putRoleInput = document.getElementById("put-role");
    const statusPathList = document.getElementById("status-path-list");
    const cameraCaptureCameraIdInput = document.getElementById("camera-capture-camera-id");
    const listCapturesCameraIdInput = document.getElementById("list-captures-camera-id");
    const listCapturesLimitInput = document.getElementById("list-captures-limit");
    const listCapturesOffsetInput = document.getElementById("list-captures-offset");
    const addStatusPathButton = document.getElementById("add-status-path");
    const clockTimeFormat = {json.dumps(time_format)};
    let timerEventSource = null;
    const defaultStatusPaths = {json.dumps([f"config.controllers.{default_role}", f"controllers.{default_role}.telemetry"] if default_role else [])};

    function putRole() {{
      return putRoleInput.value.trim();
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
        <label>Path <input class="status-path-input" value="${{value || ""}}" placeholder="controllers.${{putRoleInput.value.trim() || ""}}.telemetry"></label>
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

    function putCurlCommand() {{
      const url = `${{window.location.origin}}/api/controllers/${{encodeURIComponent(putRole())}}`;
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

    function updateCurl() {{
      document.getElementById("get-status-curl-command").textContent = "curl " + doubleQuote(statusUrl(false));
      document.getElementById("stream-status-curl-command").textContent = "curl -N " + doubleQuote(statusUrl(true));
      document.getElementById("put-curl-command").textContent = putCurlCommand();
      document.getElementById("camera-capture-curl-command").textContent = cameraCaptureCurlCommand();
      document.getElementById("list-captures-curl-command").textContent = listCapturesCurlCommand();
    }}

    function setPayload(state) {{
      payload.value = JSON.stringify(state, null, 2);
      document.getElementById("put-status").textContent = "Payload generated. Edit it, then PUT.";
      document.getElementById("put-result").textContent = "";
      updateCurl();
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
      const streamBoard = document.getElementById("timer-status-board");
      const timestamp = new Date().toLocaleTimeString();
      let display = data;
      try {{
        const parsed = JSON.parse(data);
        if (streamBoard) streamBoard.textContent = JSON.stringify(parsed, null, 2);
        display = JSON.stringify(parsed, null, 2);
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
      fetch(statusUrl(true)).then(async (response) => {{
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

    async function putState() {{
      const putStatus = document.getElementById("put-status");
      const putResult = document.getElementById("put-result");
      putStatus.textContent = "";
      putResult.textContent = "";
      const url = `/api/controllers/${{encodeURIComponent(putRole())}}`;
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

    document.getElementById("generate-quick").addEventListener("click", () => {{
      setPayload({{
        report_every: 10,
        devices: [{{
          id: "test_pin",
          type: "gpio",
          pin: Number(document.getElementById("test-pin").value),
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
        devices: [
          {{
            id: "pump",
            type: "gpio",
            pin: Number(document.getElementById("pump-pin").value),
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
            pin: Number(document.getElementById("lights-pin").value),
            current_t: currentTForWindow(lightsOn, lightsOff),
            reschedule: 1,
            pattern: [{{val: 1, dur: lightsOnDur}}, {{val: 0, dur: lightsOffDur}}],
          }},
        ],
      }});
    }});

    document.getElementById("get-config").addEventListener("click", () => runConfigRequest("get"));
    document.getElementById("get-system").addEventListener("click", () => runConfigRequest("system"));
    document.getElementById("put-config").addEventListener("click", () => runConfigRequest("full"));
    document.getElementById("put-config-controllers").addEventListener("click", () => runConfigRequest("controllers"));
    document.getElementById("put-config-cameras").addEventListener("click", () => runConfigRequest("cameras"));
    document.getElementById("get-status").addEventListener("click", getStatus);
    document.getElementById("start-stream").addEventListener("click", startTimerStream);
    document.getElementById("stop-stream").addEventListener("click", stopTimerStream);
    document.getElementById("put-state").addEventListener("click", putState);
    document.getElementById("camera-capture").addEventListener("click", captureCameraImage);
    document.getElementById("list-captures").addEventListener("click", listCameraCaptures);
    cameraCaptureCameraIdInput.addEventListener("input", updateCurl);
    listCapturesCameraIdInput.addEventListener("input", updateCurl);
    listCapturesLimitInput.addEventListener("input", updateCurl);
    listCapturesOffsetInput.addEventListener("input", updateCurl);
    for (const button of document.querySelectorAll(".copy-curl")) {{
      button.addEventListener("click", copyCurlCommand);
    }}
    putRoleInput.addEventListener("input", updateCurl);
    listCapturesLimitInput.addEventListener("input", updateCurl);
    listCapturesOffsetInput.addEventListener("input", updateCurl);
    payload.addEventListener("input", updateCurl);
    updateCurl();
  </script>
</body>
</html>"""


def render_timer_test_page(roles: list[str], default_role: str, default_payload: str, time_format: str) -> str:
    return render_api_test_page(roles, default_role, default_payload, time_format)
