from __future__ import annotations

import html
import json
import re
from typing import Any

GITHUB_REPO_URL = "https://github.com/hugomatic/plamp"
GITHUB_NEW_ISSUE_URL = f"{GITHUB_REPO_URL}/issues/new"
MAIN_NAV = f'<nav><a href="/">Plamp</a> | <a href="/settings">Settings</a> | <a href="/api/test">API test</a> | <a href="{GITHUB_REPO_URL}">GitHub</a></nav>'


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
        serial = str(controller.get("pico_serial") or "")
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


def pin_type_options(selected: str | None) -> str:
    return "".join(option_tag(value, value, selected or "gpio") for value in ["gpio", "pwm"])


def scheduler_devices_by_controller(controllers: dict[str, Any], devices: dict[str, Any]) -> list[tuple[str, dict[str, Any], list[tuple[str, dict[str, Any]]]]]:
    grouped_devices: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for device_id, device in devices.items():
        if not isinstance(device, dict):
            continue
        controller_id = str(device.get("controller") or "")
        grouped_devices.setdefault(controller_id, []).append((device_id, device))

    groups: list[tuple[str, dict[str, Any], list[tuple[str, dict[str, Any]]]]] = []
    for controller_id, controller in controllers.items():
        if not isinstance(controller, dict):
            continue
        controller_devices = grouped_devices.get(controller_id, [])
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
    devices = config.get("devices") if isinstance(config.get("devices"), dict) else {}
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
                pico_options_html=pico_options(picos, str(controller.get("pico_serial") or "")),
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
                pin=html.escape(str(device.get("pin") if device.get("pin") is not None else ""), quote=True),
                type_options=pin_type_options(str(device.get("type") or "gpio")),
                editor_options="".join(option_tag(value, value, str(device.get("editor") or "cycle")) for value in ["cycle", "clock_window"]),
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
            editor_options="".join(option_tag(value, value, "cycle") for value in ["cycle", "clock_window"]),
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
        result[key] = picoSerial ? {{pico_serial: picoSerial}} : {{}};
      }}
      return result;
    }}
    function collectDevices() {{
      const result = {{}};
      for (const row of document.querySelectorAll(".device-row")) {{
        const key = row.querySelector(".device-id").value.trim();
        if (!key) continue;
        const pinValue = row.querySelector(".device-pin").value;
        result[key] = {{controller: row.querySelector(".device-controller").value, pin: pinValue === "" ? null : Number(pinValue), type: row.querySelector(".device-type").value, editor: row.querySelector(".device-editor").value}};
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
    async function saveSection(statusId, url, payload) {{
      const status = document.getElementById(statusId);
      status.textContent = "Saving...";
      const response = await fetch(url, {{method: "PUT", headers: {{"content-type": "application/json"}}, body: JSON.stringify(payload)}});
      status.textContent = response.ok ? "Saved." : `${{response.status}} ${{await response.text()}}`;
    }}
    document.getElementById("save-controllers").addEventListener("click", () => saveSection("controllers-status", "/api/config/controllers", collectControllers()));
    document.getElementById("save-devices").addEventListener("click", () => saveSection("devices-status", "/api/config/devices", collectDevices()));
    document.getElementById("save-cameras").addEventListener("click", () => saveSection("cameras-status", "/api/config/cameras", collectCameras()));
  </script>
</body>
</html>"""


def render_settings_page(summary: dict[str, Any]) -> str:
    config = summary.get("config") if isinstance(summary.get("config"), dict) else {}
    detected = summary.get("detected") if isinstance(summary.get("detected"), dict) else {}
    controllers = config.get("controllers") if isinstance(config.get("controllers"), dict) else {}
    devices = config.get("devices") if isinstance(config.get("devices"), dict) else {}
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
    scheduler_controller_options = scheduler_controllers(controllers)
    peripheral_assignment_map = peripheral_assignments(scheduler_controller_options)
    scheduler_groups = scheduler_devices_by_controller(scheduler_controller_options, devices)
    hidden_controllers = hidden_scheduler_controllers(scheduler_controller_options, scheduler_groups)

    def render_scheduler_controller_row(controller_id: str, controller: dict[str, Any], *, new_row: bool = False) -> str:
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
                label=html.escape(str(controller.get("label") or ""), quote=True),
                pico_options_html=pico_options(setup_picos, str(controller.get("pico_serial") or "")),
                report_every=html.escape(str(controller.get("report_every") or 10), quote=True),
                type_options=controller_type_options(str(controller.get("type") or "pico_scheduler")),
            )
        )

    def render_scheduler_device_row(device_id: str, device: dict[str, Any], controller_id: str, *, new_row: bool = False) -> str:
        return (
            '<tr class="device-row{new_row_class}" data-device-id="{device_id}" data-device-controller="{controller_id}">'
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
                pin=html.escape(str(device.get("pin") if device.get("pin") is not None else ""), quote=True),
                type_options=pin_type_options(str(device.get("type") or "gpio")),
                editor_options="".join(option_tag(value, value, str(device.get("editor") or "cycle")) for value in ["cycle", "clock_window"]),
            )
        )

    create_scheduler_block = (
        '<div class="pico-scheduler-block pico-scheduler-new" data-controller-key="">'
        '<table><thead><tr><th>ID</th><th>Label</th><th>Assigned peripheral</th><th>Report every seconds</th></tr></thead>'
        '<tbody>{controller_row}</tbody></table>'
        '<h4>Devices</h4>'
        '<table><thead><tr><th>ID</th><th>Label</th><th>Pin</th><th>Output type</th><th>Editor</th></tr></thead>'
        '<tbody>{device_rows}</tbody></table>'
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
            '<h4>Devices</h4>'
            '<table><thead><tr><th>ID</th><th>Label</th><th>Pin</th><th>Output type</th><th>Editor</th></tr></thead>'
            '<tbody>{device_rows}</tbody></table>'
            '</div>'.format(
                controller_id=html.escape(controller_id, quote=True),
                controller_row=render_scheduler_controller_row(controller_id, controller),
                device_rows="".join(device_rows),
            )
        )
    scheduler_blocks.append(create_scheduler_block)

    detected_by_key = {str(item.get("key")): item for item in detected_cameras if isinstance(item, dict) and item.get("key")}
    camera_detected_keys, unmatched_detected_keys = camera_detected_matches(configured_cameras, detected_cameras)
    all_camera_keys = list(configured_cameras) + unmatched_detected_keys
    camera_setup_rows = []
    for camera_id in all_camera_keys:
        camera = configured_cameras.get(camera_id, {}) if isinstance(configured_cameras.get(camera_id, {}), dict) else {}
        detected_key = camera_detected_keys.get(camera_id, camera_id if camera_id in detected_by_key else "")
        detected_camera = detected_by_key.get(detected_key, {})
        detail = " ".join(part for part in [camera_model_label(detected_camera), str(detected_camera.get("lens") or "")] if part and part != "-")
        camera_setup_rows.append(
            '<tr class="camera-row" data-camera-key="{camera_id}" data-camera-detected-key="{detected_key}">'
            '<td><input class="camera-id" placeholder="rpicam_cam0" value="{camera_id}"></td>'
            '<td><input class="camera-label" placeholder="Tent camera" value="{label}"></td>'
            '<td class="muted">{detail}</td>'
            '</tr>'.format(
                camera_id=html.escape(camera_id, quote=True),
                detected_key=html.escape(detected_key, quote=True),
                label=html.escape(str(camera.get("label") or ""), quote=True),
                detail=html.escape(f"Detected: {detail}" if detail else "Configured"),
            )
        )
    camera_setup_rows.append(
        '<tr class="camera-row new-row" data-camera-key="" data-camera-detected-key="">'
        '<td><input class="camera-id" placeholder="rpicam_cam0" value=""></td>'
        '<td><input class="camera-label" placeholder="Tent camera" value=""></td>'
        '<td class="muted">Add a camera id to save it.</td>'
        '</tr>'
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
        f"<td>{html.escape(str(item.get('sensor') or '-'))}</td>"
        f"<td>{html.escape(str(item.get('lens') or '-'))}</td>"
        f"<td><code>{html.escape(str(item.get('path') or '-'))}</code></td>"
        "</tr>"
        for item in rpicam_cameras
    ) or '<tr><td colspan="5">No Raspberry Pi cameras found.</td></tr>'

    network_rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(str(item.get('device') or '-'))}</td>"
        f"<td>{html.escape(str(item.get('ipv4') or '-'))}</td>"
        f"<td>{html.escape(str(item.get('network') or '-'))}</td>"
        "</tr>"
        for item in networks
    ) or '<tr><td colspan="3">No network devices found.</td></tr>'

    software = summary.get("software") if isinstance(summary.get("software"), dict) else {}
    git_short_commit = software.get("git_short_commit") or software.get("git_commit") or "unknown"
    git_branch = software.get("git_branch") or "unknown"
    git_commit_timestamp = software.get("git_commit_timestamp") or "unknown"
    git_dirty = software.get("git_dirty")
    git_dirty_display = "unknown" if git_dirty is None else ("yes" if git_dirty else "no")
    software_rows = (
        "<tr><td>Git commit</td>" f"<td><code>{html.escape(str(git_short_commit))}</code></td></tr>"
        "<tr><td>Git branch</td>" f"<td><code>{html.escape(str(git_branch))}</code></td></tr>"
        "<tr><td>Git commit time</td>" f"<td><code>{html.escape(str(git_commit_timestamp))}</code></td></tr>"
        "<tr><td>Git dirty</td>" f"<td><code>{html.escape(git_dirty_display)}</code></td></tr>"
        "<tr><td>mpremote</td>" f"<td><code>{html.escape(str(tools.get('mpremote') or 'not found'))}</code></td></tr>"
        "<tr><td>pyserial</td>" f"<td><code>{html.escape(str(tools.get('pyserial') or '-'))}</code></td></tr>"
    )

    storage_rows = (
        "<tr>"
        f"<td><code>{html.escape(str(storage.get('path') or '-'))}</code></td>"
        f"<td>{html.escape(str(storage.get('free') or '-'))}</td>"
        f"<td>{html.escape(str(storage.get('used') or '-'))}</td>"
        f"<td>{html.escape(str(storage.get('total') or '-'))}</td>"
        "</tr>"
    )
    hostname = str(host.get("hostname") or "")

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Plamp settings</title>
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
  </style>
</head>
<body>
  {MAIN_NAV}
  <h1>Settings</h1>
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
    <table><thead><tr><th>ID</th><th>Label</th><th>Detected</th></tr></thead><tbody>{''.join(camera_setup_rows)}</tbody></table>
    <button id="save-cameras" type="button">Save cameras</button> <span id="cameras-status" class="status">Ready.</span>
  </section>

  <section aria-label="System status">
    <h2>System status</h2>
    <p class="muted">Detected hardware and host status.</p>
    <h3>Peripherals</h3>
    <table><thead><tr><th>Port</th><th>USB Device</th><th>Serial</th><th>Assigned</th><th>USB ID</th></tr></thead><tbody>{pico_rows}</tbody></table>
    <h3>Raspberry Pi cameras</h3>
    <table><thead><tr><th>Camera</th><th>Model</th><th>Sensor</th><th>Lens</th><th>Path</th></tr></thead><tbody>{camera_rows}</tbody></table>
    <h3>Network</h3>
    <p><strong>Hostname:</strong> {html.escape(hostname)}</p>
    <table><thead><tr><th>Device</th><th>IPv4</th><th>Network</th></tr></thead><tbody>{network_rows}</tbody></table>
    <h3>Software</h3>
    <table><thead><tr><th>Tool</th><th>Path</th></tr></thead><tbody>{software_rows}</tbody></table>
    <h2>Storage</h2>
    <table><thead><tr><th>Path</th><th>Free</th><th>Used</th><th>Total</th></tr></thead><tbody>{storage_rows}</tbody></table>
  </section>

  <section aria-label="Device control">
    <h2>Device control</h2>
    <p class="muted">Changes here may require reconnecting to the device.</p>
    <label>Hostname <input id="hostname-input" value="{html.escape(hostname, quote=True)}"></label>
    <button id="hostname-confirm" type="button">Apply hostname</button>
    <span id="hostname-status" class="status">Ready.</span>
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
      const labelInput = row.querySelector(".controller-label");
      labelInput.value = hiddenController.label || "";
      labelInput.defaultValue = hiddenController.label || "";
      const picoSerialSelect = row.querySelector(".controller-pico-serial");
      picoSerialSelect.value = hiddenController.pico_serial || "";
      picoSerialSelect.dataset.defaultValue = hiddenController.pico_serial || "";
      const reportEveryInput = row.querySelector(".controller-report-every");
      reportEveryInput.value = String(hiddenController.report_every ?? reportEveryInput.defaultValue || "");
      reportEveryInput.defaultValue = String(hiddenController.report_every ?? reportEveryInput.defaultValue || "");
    }}
    const hiddenControllers = JSON.parse(document.getElementById("hidden-scheduler-controllers").textContent || "{{}}");
    for (const row of document.querySelectorAll(".controller-row.new-row")) {{
      row.querySelector(".controller-pico-serial").dataset.defaultValue = row.querySelector(".controller-pico-serial").value;
      row.querySelector(".controller-id").addEventListener("input", () => hydrateControllerRowFromHidden(row));
    }}
    function collectControllers() {{
      const result = structuredClone(hiddenControllers);
      for (const row of document.querySelectorAll(".controller-row")) {{
        const key = row.querySelector(".controller-id").value.trim();
        if (!key) continue;
        const picoSerialSelect = row.querySelector(".controller-pico-serial");
        const picoSerial = picoSerialSelect.value;
        const picoSerialDefault = picoSerialSelect.dataset.defaultValue || "";
        const labelInput = row.querySelector(".controller-label");
        const label = labelInput.value.trim();
        const type = row.querySelector(".controller-type").value;
        const reportEveryInput = row.querySelector(".controller-report-every");
        const reportEvery = reportEveryInput.value;
        const existingController = hiddenControllers[key] ? structuredClone(hiddenControllers[key]) : {{}};
        const isHiddenReuse = !row.dataset.controllerKey && Object.keys(existingController).length > 0;
        const payload = isHiddenReuse ? existingController : {{type}};
        payload.type = type;
        if (!isHiddenReuse || label !== labelInput.defaultValue) payload.label = label;
        if (!isHiddenReuse || picoSerial !== picoSerialDefault) payload.pico_serial = picoSerial;
        if (type === "pico_scheduler") {{
          if (reportEvery === "") {{
            if (!isHiddenReuse) throw new Error(`Report interval required for controller ${{key}}.`);
          }} else {{
            if (!isHiddenReuse || reportEvery !== reportEveryInput.defaultValue) payload.report_every = Number(reportEvery);
          }}
        }}
        result[key] = cleanObject(payload);
      }}
      return result;
    }}
    function collectDevices() {{
      const result = {{}};
        for (const row of document.querySelectorAll(".device-row")) {{
            const key = row.querySelector(".device-id").value.trim();
            if (!key) continue;
            const pinValue = row.querySelector(".device-pin").value;
            if (pinValue === "") throw new Error(`Pin required for device ${{key}}.`);
            const blockController = row.closest(".pico-scheduler-block")?.querySelector(".controller-row .controller-id")?.value.trim() || "";
            result[key] = cleanObject({{controller: blockController || row.dataset.deviceController || "", pin: Number(pinValue), type: row.querySelector(".device-type").value, editor: row.querySelector(".device-editor").value, label: row.querySelector(".device-label").value.trim()}});
        }}
        return result;
    }}
    function collectCameras() {{
      const result = {{}};
      for (const row of document.querySelectorAll(".camera-row")) {{
        const key = row.querySelector(".camera-id").value.trim();
        if (!key) continue;
        result[key] = cleanObject({{label: row.querySelector(".camera-label").value.trim(), detected_key: row.dataset.cameraDetectedKey || ""}});
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
    function collectDevicesWithControllerRenames() {{
      const devices = collectDevices();
      const renames = controllerRenames();
      for (const device of Object.values(devices)) {{
        if (renames[device.controller]) device.controller = renames[device.controller];
      }}
      return devices;
    }}
    function collectConfigWithControllerRenames() {{
      return {{controllers: collectControllers(), devices: collectDevicesWithControllerRenames(), cameras: collectCameras()}};
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
    document.getElementById("hostname-confirm").addEventListener("click", async () => {{
      const hostname = document.getElementById("hostname-input").value.trim();
      if (!window.confirm(`Apply hostname "${{hostname}}"? You may need to reconnect.`)) return;
      const status = document.getElementById("hostname-status");
      status.textContent = "Applying...";
      const response = await fetch("/api/host-config/hostname", {{method: "POST", headers: {{"content-type": "application/json"}}, body: JSON.stringify({{hostname}})}});
      const text = await response.text();
      let parsed = null;
      try {{ parsed = JSON.parse(text); }} catch (error) {{}}
      status.textContent = response.ok ? (parsed?.message || "Hostname updated; reconnect or reboot may be required.") : `${{response.status}} ${{parsed?.detail || text}}`;
    }});
  </script>
</body>
</html>"""

def render_timer_dashboard_page(
    roles: list[str],
    time_format: str,
    channels_by_role: dict[str, list[dict[str, Any]]] | None = None,
    host_seconds_since_midnight: int = 0,
    camera_ids: list[str] | None = None,
) -> str:
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
  <title>Plamp</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 2rem; line-height: 1.4; }
    nav { margin-bottom: 1.5rem; }
    a { color: #174ea6; }
    button { border: 1px solid #222; border-radius: 6px; margin: .25rem .25rem .25rem 0; padding: .45rem .7rem; background: #fff; }
    input, select { box-sizing: border-box; padding: .35rem; }
    .host-clock { color: #555; font-size: .95rem; margin: -.5rem 0 1rem; }
    .status-board { display: grid; gap: .75rem; margin: 1rem 0; max-width: 980px; }
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
    .timer-actions { margin-top: .65rem; }
    .timer-editor { border: 1px solid #ccc; border-radius: 6px; display: grid; gap: .65rem; margin: 1rem 0; max-width: 980px; padding: .75rem; }
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
  <h1>Plamp</h1>
  <h2>Timers</h2>
  <p class="host-clock">Host time: <span id="host-clock">--:--</span></p>
  <p id="timer-stream-status">Connecting...</p>
  <div id="timer-status-board" class="status-board">Waiting for timer report...</div>
  <div id="timer-editor-panel" class="timer-editor" hidden></div>

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
        <option value="all">All</option>
        <option value="camera_roll">Camera roll</option>
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
    const timerEditorPanel = document.getElementById("timer-editor-panel");
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
        message?.report?.content?.devices,
        message?.last_report?.content?.devices,
        message?.content?.devices,
        message?.devices,
      ];
      return candidates.find((devices) => Array.isArray(devices)) || [];
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
      if (!activeEditor || !timerEditorPanel.contains(document.activeElement)) return null;
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
      const form = timerEditorPanel.querySelector("#timer-schedule-form");
      const field = form?.elements?.[focusState.name];
      if (!field || typeof field.focus !== "function") return;
      field.focus();
      if (typeof field.setSelectionRange === "function" && focusState.selectionStart !== null && focusState.selectionEnd !== null) {
        field.setSelectionRange(focusState.selectionStart, focusState.selectionEnd);
      }
    }

    function flushPendingTimerRender() {
      if (!pendingTimerRender) return;
      if (activeEditor && timerEditorPanel.contains(document.activeElement)) return;
      pendingTimerRender = false;
      renderTimerStatus();
    }

    function openScheduleEditor(role, channel, event) {
      const durations = twoStepDurations(event) || {on: 60, off: 60, total: 120};
      const onUnit = chooseUnit(durations.on);
      const offUnit = chooseUnit(durations.off);
      const clock = clockValuesForEvent(event);
      stopPageAutoRefresh();
      activeEditor = {role, channelId: channel.id};
      timerEditorPanel.hidden = false;
      timerEditorPanel.dataset.role = role;
      timerEditorPanel.dataset.channelId = channel.id;
      timerEditorPanel.innerHTML = `
        <form id="timer-schedule-form">
          <div class="timer-top"><strong>Edit ${escapeHtml(channel.name)}</strong><span class="editor-note">${escapeHtml(role)} / pin ${escapeHtml(channel.pin ?? "?")} / ${escapeHtml(channel.type || "gpio")}</span></div>
          <div class="editor-row">
            <label>Set as
              <select name="mode">
                <option value="cycle">Cycle set</option>
                <option value="clock_window">24h set</option>
              </select>
            </label>
          </div>
          <div class="editor-row cycle-fields">
            <label>On for <input name="onValue" type="number" min="1" step="1" value="${onUnit.value}"></label>
            <label>Unit <select name="onUnit"><option value="seconds">seconds</option><option value="minutes">minutes</option><option value="hours">hours</option></select></label>
            <label>Off for <input name="offValue" type="number" min="1" step="1" value="${offUnit.value}"></label>
            <label>Unit <select name="offUnit"><option value="seconds">seconds</option><option value="minutes">minutes</option><option value="hours">hours</option></select></label>
            <label>Start at <input name="startAtSeconds" type="number" min="0" step="1" value="0"></label>
            <span class="editor-note">Seconds into the cycle. Use a value near the end of a step to test the next change.</span>
          </div>
          <div class="editor-row clock-fields">
            <label>On at <input name="onTime" type="time" value="${clock.on}"></label>
            <label>Off at <input name="offTime" type="time" value="${clock.off}"></label>
            <span class="editor-note">Applies using the host clock.</span>
          </div>
          <div class="editor-row">
            <button type="submit">Apply schedule</button>
            <button type="button" name="cancel">Close</button>
            <span class="editor-message" aria-live="polite"></span>
          </div>
        </form>
      `;
      const form = document.getElementById("timer-schedule-form");
      form.elements.mode.value = channel.default_editor === "clock_window" ? "clock_window" : "cycle";
      form.elements.onUnit.value = onUnit.unit;
      form.elements.offUnit.value = offUnit.unit;
      syncEditorMode(form);
      form.elements.mode.addEventListener("change", () => syncEditorMode(form));
      form.addEventListener("focusout", () => window.setTimeout(flushPendingTimerRender, 0));
      form.elements.cancel.addEventListener("click", () => { activeEditor = null; timerEditorPanel.hidden = true; renderTimerStatus(); });
      renderTimerStatus();
      form.addEventListener("submit", submitScheduleEditor);
    }

    function syncEditorMode(form) {
      const clock = form.elements.mode.value === "clock_window";
      form.querySelector(".cycle-fields").hidden = clock;
      form.querySelector(".clock-fields").hidden = !clock;
    }

    async function submitScheduleEditor(event) {
      event.preventDefault();
      const form = event.currentTarget;
      const message = form.querySelector(".editor-message");
      showEditorMessage(message, "", "Saving...");
      const mode = form.elements.mode.value;
      const body = {mode};
      if (mode === "cycle") {
        body.on_seconds = Number(form.elements.onValue.value) * unitMultiplier(form.elements.onUnit.value);
        body.off_seconds = Number(form.elements.offValue.value) * unitMultiplier(form.elements.offUnit.value);
        body.start_at_seconds = Number(form.elements.startAtSeconds.value);
      } else {
        body.on_time = form.elements.onTime.value;
        body.off_time = form.elements.offTime.value;
      }
      try {
        const response = await fetch(`/api/controllers/${encodeURIComponent(timerEditorPanel.dataset.role)}/channels/${encodeURIComponent(timerEditorPanel.dataset.channelId)}/schedule`, {
          method: "POST",
          headers: {"content-type": "application/json"},
          body: JSON.stringify(body),
        });
        const text = await response.text();
        let parsed = null;
        try { parsed = JSON.parse(text); } catch (error) {}
        if (!response.ok) {
          throw new Error(parsed?.detail || text || `${response.status} ${response.statusText}`);
        }
        showEditorMessage(message, "editor-success", parsed?.message || "Schedule applied. Waiting for report...");
      } catch (error) {
        showEditorMessage(message, "editor-error", String(error.message || error));
      }
    }

    function renderTimerStatus() {
      if (activeEditor && timerEditorPanel.contains(document.activeElement)) {
        pendingTimerRender = true;
        return;
      }
      pendingTimerRender = false;
      const focusState = captureEditorFocus();
      timerBoard.replaceChildren();
      let rendered = 0;
      let editorPlaced = false;
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
        for (const item of items) {
          const channel = item.channel;
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
          name.textContent = role + " / " + channel.name;
          const badge = document.createElement("span");
          badge.className = "timer-value " + (isOn ? "on" : "off");
          badge.textContent = isOn ? "ON" : "OFF";
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
          const actions = document.createElement("div");
          actions.className = "timer-actions";
          const edit = document.createElement("button");
          edit.type = "button";
          edit.textContent = "Edit schedule";
          edit.addEventListener("click", () => openScheduleEditor(role, channel, event));
          actions.append(edit);
          card.append(top, meta, bar, actions);
          timerBoard.append(card);
          if (activeEditor && activeEditor.role === role && activeEditor.channelId === channel.id) {
            timerBoard.append(timerEditorPanel);
            timerEditorPanel.hidden = false;
            editorPlaced = true;
          }
          rendered += 1;
        }
      }
      if (!editorPlaced) {
        timerEditorPanel.hidden = true;
      }
      restoreEditorFocus(focusState);
      if (!rendered) {
        timerBoard.textContent = timerRoles.length ? "Waiting for timer reports..." : "No timers configured in data/config.json.";
      }
    }

    function updateCameraFilters() {
      const selected = cameraCaptureFilter.value;
      const options = new Map([["all", "All"], ["camera_roll", "Camera roll"]]);
      if (selected.startsWith("grow:")) {
        options.set(selected, cameraCaptureFilter.selectedOptions[0]?.textContent || selected.slice(5));
      }
      for (const capture of cameraCaptures) {
        if (capture.grow_id) {
          options.set("grow:" + capture.grow_id, capture.grow_name || capture.grow_id);
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
      if (filter === "camera_roll") {
        params.set("source", "camera_roll");
      } else if (filter.startsWith("grow:")) {
        params.set("source", "grow");
        params.set("grow_id", filter.slice(5));
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
      parts.push(capture.grow_name || (capture.source === "camera_roll" ? "Camera roll" : "Grow capture"));
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
        const source = new EventSource(`/api/controllers/${encodeURIComponent(role)}?stream=true`);
        timerEventSources.set(role, source);
        for (const eventName of ["snapshot", "status", "report"]) {
          source.addEventListener(eventName, (event) => {
            timerMessages.set(role, JSON.parse(event.data));
            renderTimerStatus();
          });
        }
        source.onerror = () => { timerStatus.textContent = "Stream error or reconnecting..."; };
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
        template.replace("__MAIN_NAV__", MAIN_NAV).replace("__TIME_FORMAT__", json.dumps(time_format))
        .replace("__ROLES__", json.dumps(roles))
        .replace("__CHANNELS__", json.dumps(channels_by_role or {}))
        .replace("__CAMERA_OPTIONS__", camera_options)
        .replace("__HOST_SECONDS__", json.dumps(host_seconds_since_midnight))
    )


def render_api_test_page(roles: list[str], default_role: str, default_payload: str, time_format: str) -> str:
    role_options = "\n".join(f'<option value="{html.escape(role)}"></option>' for role in roles)
    default_get_curl = f"curl http://localhost:8000/api/controllers/{default_role}"
    default_stream_curl = f"curl -N 'http://localhost:8000/api/controllers/{default_role}?stream=true'"
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
    <p>Captures a new image and returns capture metadata.</p>
    <pre id="camera-capture-curl-command">curl -X POST http://localhost:8000/api/camera/captures</pre>
    <button class="copy-curl" type="button" data-copy-target="camera-capture-curl-command">Copy curl</button>
    <button id="camera-capture" type="button">Run request</button>
    <div><span id="camera-capture-status">Ready.</span></div>
    <pre id="camera-capture-result">POST response will appear here.</pre>
    <img id="camera-capture-preview" alt="Latest camera capture preview" hidden>
  </fieldset>

  <fieldset>
    <legend>GET /api/camera/captures</legend>
    <p>Lists captures newest first. Options: limit and offset.</p>
    <div class="row">
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
    <p>Reads configured meaning plus detected local hardware choices.</p>
    <pre id="get-config-curl-command">curl http://localhost:8000/api/config</pre>
    <button class="copy-curl" type="button" data-copy-target="get-config-curl-command">Copy curl</button>
    <button id="get-config" type="button">Run request</button>
    <div><span id="get-config-status">Ready.</span></div>
    <pre id="get-config-result">GET response will appear here.</pre>
  </fieldset>
  <fieldset>
    <legend>PUT /api/config</legend>
    <p>Saves controllers, devices, and cameras together.</p>
    <pre id="put-config-curl-command">curl -X PUT http://localhost:8000/api/config -H 'content-type: application/json' --data '{{"controllers":{{}},"devices":{{}},"cameras":{{}}}}'</pre>
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
    <legend>PUT /api/config/devices</legend>
    <p>Saves device mappings to controllers and pins.</p>
    <pre id="put-config-devices-curl-command">curl -X PUT http://localhost:8000/api/config/devices -H 'content-type: application/json' --data '{{}}'</pre>
    <button class="copy-curl" type="button" data-copy-target="put-config-devices-curl-command">Copy curl</button>
    <button id="put-config-devices" type="button">Run request</button>
    <div><span id="put-config-devices-status">Ready.</span></div>
    <pre id="put-config-devices-result">PUT response will appear here.</pre>
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

  <h2>Timers</h2>

  <fieldset>
    <legend>GET /api/controllers/{{role}}</legend>
    <p>Reads the current timer state for one role.</p>
    <label>Role
      <input id="get-role" list="timer-roles" value="{html.escape(default_role)}">
    </label>
    <datalist id="timer-roles">{role_options}</datalist>
    <pre id="get-curl-command">{html.escape(default_get_curl)}</pre>
    <button class="copy-curl" type="button" data-copy-target="get-curl-command">Copy curl</button>
    <button id="get-state" type="button">Run request</button>
    <div><span id="get-status">Ready.</span></div>
    <pre id="get-result">GET response will appear here.</pre>
  </fieldset>

  <fieldset>
    <legend>GET /api/controllers/{{role}}?stream=true</legend>
    <p>Streams timer device updates with server-sent events.</p>
    <pre id="stream-curl-command">{html.escape(default_stream_curl)}</pre>
    <button class="copy-curl" type="button" data-copy-target="stream-curl-command">Copy curl</button>
    <button id="start-stream" type="button">Start stream</button>
    <button id="stop-stream" type="button">Stop stream</button>
    <div><span id="stream-status">Not streaming.</span></div>
    <div id="timer-status-board" class="status-board">Start the stream to see timer status.</div>
    <pre id="stream-result">Stream device updates will appear here.</pre>
  </fieldset>

  <fieldset>
    <legend>PUT /api/controllers/{{role}}</legend>
    <p>Writes timer state JSON and sends it to the Pico.</p>
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
    const getRoleInput = document.getElementById("get-role");
    const putRoleInput = document.getElementById("put-role");
    const listCapturesLimitInput = document.getElementById("list-captures-limit");
    const listCapturesOffsetInput = document.getElementById("list-captures-offset");
    const clockTimeFormat = {json.dumps(time_format)};
    let timerEventSource = null;

    function getRole() {{
      return getRoleInput.value.trim();
    }}

    function putRole() {{
      return putRoleInput.value.trim();
    }}

    function listCapturesLimit() {{
      const value = Number(listCapturesLimitInput.value);
      return Number.isFinite(value) ? Math.max(0, Math.min(200, Math.floor(value))) : 10;
    }}

    function listCapturesOffset() {{
      const value = Number(listCapturesOffsetInput.value);
      return Number.isFinite(value) ? Math.max(0, Math.floor(value)) : 0;
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
      return "curl " + doubleQuote(`${{window.location.origin}}/api/controllers/${{encodeURIComponent(getRole())}}`);
    }}

    function streamCurlCommand() {{
      return "curl -N " + doubleQuote(`${{window.location.origin}}/api/controllers/${{encodeURIComponent(getRole())}}?stream=true`);
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
      return "curl -X POST " + doubleQuote(`${{window.location.origin}}/api/camera/captures`);
    }}

    function listCapturesCurlCommand() {{
      return "curl " + doubleQuote(`${{window.location.origin}}/api/camera/captures?limit=${{listCapturesLimit()}}&offset=${{listCapturesOffset()}}`);
    }}

    function updateCurl() {{
      document.getElementById("get-curl-command").textContent = getCurlCommand();
      document.getElementById("stream-curl-command").textContent = streamCurlCommand();
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
        full: {{method: "PUT", url: "/api/config", statusId: "put-config-status", resultId: "put-config-result", section: null}},
        controllers: {{method: "PUT", url: "/api/config/controllers", statusId: "put-config-controllers-status", resultId: "put-config-controllers-result", section: "controllers"}},
        devices: {{method: "PUT", url: "/api/config/devices", statusId: "put-config-devices-status", resultId: "put-config-devices-result", section: "devices"}},
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

    async function getState() {{
      const getStatus = document.getElementById("get-status");
      const getResult = document.getElementById("get-result");
      getStatus.textContent = "";
      getResult.textContent = "";
      if (!window.confirm(`GET /api/controllers/${{getRole()}}?`)) {{
        getStatus.textContent = "Cancelled.";
        return;
      }}
      getStatus.textContent = "Loading...";
      try {{
        const response = await fetch(`/api/controllers/${{encodeURIComponent(getRole())}}`);
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
        renderTimerStatus(parsed);
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
      const role = getRole();
      const streamStatus = document.getElementById("stream-status");
      const streamResult = document.getElementById("stream-result");
      streamResult.textContent = "";
      streamStatus.textContent = `Connecting to /api/controllers/${{role}}?stream=true...`;
      timerEventSource = new EventSource(`/api/controllers/${{encodeURIComponent(role)}}?stream=true`);
      timerEventSource.onopen = () => {{
        streamStatus.textContent = `Streaming ${{role}}.`;
      }};
      for (const eventName of ["snapshot", "status", "report", "error", "keepalive"]) {{
        timerEventSource.addEventListener(eventName, (event) => appendStreamEvent(eventName, event.data));
      }}
      timerEventSource.onerror = () => {{
        streamStatus.textContent = "Stream error or reconnecting...";
      }};
    }}

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
        const response = await fetch(`/api/camera/captures?limit=${{listCapturesLimit()}}&offset=${{listCapturesOffset()}}`);
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
        const response = await fetch("/api/camera/captures", {{method: "POST"}});
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
    document.getElementById("put-config").addEventListener("click", () => runConfigRequest("full"));
    document.getElementById("put-config-controllers").addEventListener("click", () => runConfigRequest("controllers"));
    document.getElementById("put-config-devices").addEventListener("click", () => runConfigRequest("devices"));
    document.getElementById("put-config-cameras").addEventListener("click", () => runConfigRequest("cameras"));
    document.getElementById("get-state").addEventListener("click", getState);
    document.getElementById("start-stream").addEventListener("click", startTimerStream);
    document.getElementById("stop-stream").addEventListener("click", stopTimerStream);
    document.getElementById("put-state").addEventListener("click", putState);
    document.getElementById("camera-capture").addEventListener("click", captureCameraImage);
    document.getElementById("list-captures").addEventListener("click", listCameraCaptures);
    for (const button of document.querySelectorAll(".copy-curl")) {{
      button.addEventListener("click", copyCurlCommand);
    }}
    getRoleInput.addEventListener("input", updateCurl);
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
