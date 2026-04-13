# Config Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local Config page and API that maps detected Pico/camera hardware to user meaning while keeping existing timer APIs working.

**Architecture:** Add focused pure helpers for hardware config validation/projection and Raspberry Pi camera detection, then wire them into FastAPI endpoints and a server-rendered `/config` page. Settings remains status-oriented and gets detected camera facts; Config owns user-maintained controller/device/camera mappings and section-level saves.

**Tech Stack:** Python 3.11, FastAPI, plain server-rendered HTML, vanilla browser JavaScript, stdlib `unittest`, `rpicam-hello`/`libcamera-hello` command parsing, existing JSON config helpers.

---

## File Structure

- Create `plamp_web/hardware_config.py`: Pure functions for normalizing `hardware` config, initializing from legacy `timers`, validating section updates, and projecting `pico_scheduler` controller/device mappings back into legacy `timers` entries.
- Create `plamp_web/camera_inventory.py`: Pure parser for `rpicam-hello --list-cameras` output plus command runner with `libcamera-hello` fallback.
- Modify `plamp_web/server.py`: Import new helpers, add `GET /api/config`, `PUT /api/config/controllers`, `PUT /api/config/devices`, `PUT /api/config/cameras`, add `GET /config`, include detected Raspberry Pi cameras in `settings_summary()`.
- Modify `plamp_web/pages.py`: Add `render_config_page(...)`, link Config from Settings navigation, and show detected camera model/lens in Settings.
- Create `tests/test_hardware_config.py`: Pure unit tests for config normalization, validation, and timer compatibility projection.
- Create `tests/test_camera_inventory.py`: Pure unit tests for camera parser and command fallback behavior.
- Create `tests/test_config_api.py`: API tests for config GET and section PUT endpoints.
- Modify `tests/test_pages.py`: Page render tests for Settings camera summary and Config page sections/save controls.
- Modify `plamp_web/README.md`: Document the Config page, `hardware` config shape, camera detection behavior, and `timers` compatibility.

## Task 1: Add Hardware Config Helpers

**Files:**
- Create: `plamp_web/hardware_config.py`
- Create: `tests/test_hardware_config.py`

- [ ] **Step 1: Write failing tests for hardware config initialization, validation, and timer projection**

Create `tests/test_hardware_config.py`:

```python
import copy
import unittest

from plamp_web.hardware_config import (
    apply_hardware_section,
    hardware_config_from_timers,
    hardware_view,
    project_timers_from_hardware,
)


class HardwareConfigTests(unittest.TestCase):
    def test_hardware_config_from_timers_initializes_controller_and_devices(self):
        config = {
            "timers": [
                {
                    "role": "pump_lights",
                    "pico_serial": "e66038b71387a039",
                    "channels": [
                        {"id": "pump", "name": "Pump", "pin": 3, "type": "gpio", "default_editor": "cycle"},
                        {"id": "lights", "name": "Lights", "pin": 2, "type": "gpio", "default_editor": "clock_window"},
                    ],
                }
            ]
        }

        self.assertEqual(
            hardware_config_from_timers(config),
            {
                "controllers": {
                    "pico:e66038b71387a039": {"name": "pump_lights", "type": "pico_scheduler"}
                },
                "devices": {
                    "pump": {"name": "Pump", "type": "gpio", "controller": "pico:e66038b71387a039", "pin": 3, "default_editor": "cycle"},
                    "lights": {"name": "Lights", "type": "gpio", "controller": "pico:e66038b71387a039", "pin": 2, "default_editor": "clock_window"},
                },
                "cameras": {},
            },
        )

    def test_hardware_view_prefers_existing_hardware(self):
        config = {"timers": [], "hardware": {"controllers": {"pico:abc": {"name": "pump_lights", "type": "pico_scheduler"}}, "devices": {}, "cameras": {}}}

        self.assertEqual(hardware_view(config), config["hardware"])

    def test_apply_devices_rejects_unknown_controller(self):
        config = {"hardware": {"controllers": {}, "devices": {}, "cameras": {}}}

        with self.assertRaises(ValueError) as cm:
            apply_hardware_section(config, "devices", {"pump": {"name": "Pump", "type": "gpio", "controller": "pico:missing", "pin": 3}})

        self.assertIn("unknown controller", str(cm.exception))

    def test_apply_cameras_rejects_unknown_ir_filter(self):
        config = {"hardware": {"controllers": {}, "devices": {}, "cameras": {}}}

        with self.assertRaises(ValueError) as cm:
            apply_hardware_section(config, "cameras", {"rpicam:0": {"name": "Tent", "ir_filter": "magic"}})

        self.assertIn("ir_filter", str(cm.exception))

    def test_project_timers_from_hardware_preserves_runtime_compatibility(self):
        config = {
            "timers": [{"role": "old", "pico_serial": "oldserial"}],
            "hardware": {
                "controllers": {"pico:e66038b71387a039": {"name": "pump_lights", "type": "pico_scheduler"}},
                "devices": {
                    "pump": {"name": "Pump", "type": "gpio", "controller": "pico:e66038b71387a039", "pin": 3, "default_editor": "cycle"},
                    "lights": {"name": "Lights", "type": "gpio", "controller": "pico:e66038b71387a039", "pin": 2, "default_editor": "clock_window"},
                },
                "cameras": {},
            },
        }

        projected = project_timers_from_hardware(copy.deepcopy(config))

        self.assertEqual(
            projected["timers"],
            [
                {
                    "role": "pump_lights",
                    "pico_serial": "e66038b71387a039",
                    "channels": [
                        {"id": "lights", "name": "Lights", "pin": 2, "type": "gpio", "default_editor": "clock_window"},
                        {"id": "pump", "name": "Pump", "pin": 3, "type": "gpio", "default_editor": "cycle"},
                    ],
                }
            ],
        )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `/home/hugo/.local/bin/uv run python -m unittest tests.test_hardware_config -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'plamp_web.hardware_config'`.

- [ ] **Step 3: Implement minimal hardware config helpers**

Create `plamp_web/hardware_config.py`:

```python
from __future__ import annotations

import copy
import re
from typing import Any

CONTROLLER_TYPES = {"pico_scheduler", "food_dispenser", "ph_dispenser"}
DEVICE_TYPES = {"gpio"}
DEFAULT_EDITORS = {"cycle", "clock_window"}
IR_FILTERS = {"unknown", "normal", "noir"}
ROLE_RE = re.compile(r"^[A-Za-z0-9_-]+$")
DEVICE_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def pico_key(serial: str) -> str:
    return f"pico:{serial}"


def serial_from_pico_key(key: str) -> str:
    if not key.startswith("pico:") or len(key) <= len("pico:"):
        raise ValueError(f"invalid Pico controller key: {key}")
    return key.split(":", 1)[1]


def empty_hardware() -> dict[str, Any]:
    return {"controllers": {}, "devices": {}, "cameras": {}}


def hardware_config_from_timers(config: dict[str, Any]) -> dict[str, Any]:
    hardware = empty_hardware()
    for timer in config.get("timers", []):
        if not isinstance(timer, dict):
            continue
        role = timer.get("role")
        serial = timer.get("pico_serial")
        if not isinstance(role, str) or not isinstance(serial, str) or not role or not serial:
            continue
        controller_key = pico_key(serial)
        hardware["controllers"][controller_key] = {"name": role, "type": "pico_scheduler"}
        for channel in timer.get("channels", []):
            if not isinstance(channel, dict):
                continue
            device_id = channel.get("id")
            pin = channel.get("pin")
            if not isinstance(device_id, str) or not isinstance(pin, int):
                continue
            hardware["devices"][device_id] = {
                "name": str(channel.get("name") or device_id),
                "type": str(channel.get("type") or "gpio"),
                "controller": controller_key,
                "pin": pin,
                "default_editor": str(channel.get("default_editor") or "cycle"),
            }
    return hardware


def hardware_view(config: dict[str, Any]) -> dict[str, Any]:
    hardware = config.get("hardware")
    if isinstance(hardware, dict):
        return {
            "controllers": dict(hardware.get("controllers") or {}),
            "devices": dict(hardware.get("devices") or {}),
            "cameras": dict(hardware.get("cameras") or {}),
        }
    return hardware_config_from_timers(config)


def validate_controllers(controllers: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(controllers, dict):
        raise ValueError("controllers must be an object")
    result = {}
    seen_names = set()
    for key, item in controllers.items():
        if not isinstance(key, str) or not key.startswith("pico:"):
            raise ValueError("controller keys must be pico:<serial>")
        if not isinstance(item, dict):
            raise ValueError(f"controller {key} must be an object")
        name = item.get("name")
        controller_type = item.get("type")
        if not isinstance(name, str) or not name or not ROLE_RE.match(name):
            raise ValueError(f"controller {key} has invalid name")
        if name in seen_names:
            raise ValueError(f"duplicate controller name: {name}")
        if controller_type not in CONTROLLER_TYPES:
            raise ValueError(f"controller {key} has unsupported type")
        seen_names.add(name)
        result[key] = {"name": name, "type": controller_type}
    return result


def validate_devices(devices: Any, controllers: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if not isinstance(devices, dict):
        raise ValueError("devices must be an object")
    result = {}
    for key, item in devices.items():
        if not isinstance(key, str) or not DEVICE_ID_RE.match(key):
            raise ValueError("device ids must use letters, numbers, underscore, or dash")
        if not isinstance(item, dict):
            raise ValueError(f"device {key} must be an object")
        name = item.get("name")
        device_type = item.get("type")
        controller = item.get("controller")
        pin = item.get("pin")
        default_editor = item.get("default_editor", "cycle")
        if not isinstance(name, str) or not name:
            raise ValueError(f"device {key} has invalid name")
        if device_type not in DEVICE_TYPES:
            raise ValueError(f"device {key} has unsupported type")
        if controller not in controllers:
            raise ValueError(f"device {key} references unknown controller")
        if not isinstance(pin, int) or pin < 0 or pin > 29:
            raise ValueError(f"device {key} has invalid pin")
        if default_editor not in DEFAULT_EDITORS:
            raise ValueError(f"device {key} has unsupported default_editor")
        result[key] = {"name": name, "type": device_type, "controller": controller, "pin": pin, "default_editor": default_editor}
    return result


def validate_cameras(cameras: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(cameras, dict):
        raise ValueError("cameras must be an object")
    result = {}
    for key, item in cameras.items():
        if not isinstance(key, str) or not key.startswith("rpicam:"):
            raise ValueError("camera keys must be rpicam:<index>")
        if not isinstance(item, dict):
            raise ValueError(f"camera {key} must be an object")
        name = item.get("name")
        ir_filter = item.get("ir_filter", "unknown")
        if not isinstance(name, str) or not name:
            raise ValueError(f"camera {key} has invalid name")
        if ir_filter not in IR_FILTERS:
            raise ValueError(f"camera {key} has unsupported ir_filter")
        result[key] = {"name": name, "ir_filter": ir_filter}
    return result


def apply_hardware_section(config: dict[str, Any], section: str, value: Any) -> dict[str, Any]:
    updated = copy.deepcopy(config)
    hardware = hardware_view(updated)
    if section == "controllers":
        hardware["controllers"] = validate_controllers(value)
        hardware["devices"] = validate_devices(hardware.get("devices", {}), hardware["controllers"])
    elif section == "devices":
        hardware["devices"] = validate_devices(value, hardware.get("controllers", {}))
    elif section == "cameras":
        hardware["cameras"] = validate_cameras(value)
    else:
        raise ValueError(f"unknown hardware section: {section}")
    updated["hardware"] = hardware
    return project_timers_from_hardware(updated)


def project_timers_from_hardware(config: dict[str, Any]) -> dict[str, Any]:
    hardware = hardware_view(config)
    timers = []
    for controller_key, controller in sorted(hardware.get("controllers", {}).items(), key=lambda item: item[1]["name"]):
        if controller.get("type") != "pico_scheduler":
            continue
        channels = []
        for device_id, device in sorted(hardware.get("devices", {}).items()):
            if device.get("controller") != controller_key:
                continue
            channels.append({"id": device_id, "name": device["name"], "pin": device["pin"], "type": device["type"], "default_editor": device["default_editor"]})
        timers.append({"role": controller["name"], "pico_serial": serial_from_pico_key(controller_key), "channels": channels})
    result = copy.deepcopy(config)
    result["hardware"] = hardware
    result["timers"] = timers
    return result
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `/home/hugo/.local/bin/uv run python -m unittest tests.test_hardware_config -v`

Expected: all tests in `tests.test_hardware_config` pass.

- [ ] **Step 5: Commit**

```bash
git add plamp_web/hardware_config.py tests/test_hardware_config.py
git commit -m "Add hardware config helpers"
```

## Task 2: Add Raspberry Pi Camera Detection

**Files:**
- Create: `plamp_web/camera_inventory.py`
- Create: `tests/test_camera_inventory.py`
- Modify: `plamp_web/server.py`
- Modify: `plamp_web/pages.py`
- Modify: `tests/test_pages.py`

- [ ] **Step 1: Write failing parser and settings tests**

Create `tests/test_camera_inventory.py`:

```python
import subprocess
import unittest
from unittest.mock import patch

from plamp_web.camera_inventory import camera_key, detect_rpicam_cameras, parse_rpicam_list_cameras


RPICAM_OUTPUT = """
Available cameras
-----------------
0 : imx708_wide [4608x2592 10-bit RGGB] (/base/soc/i2c0mux/i2c@1/imx708@1a)
    Modes: 'SRGGB10_CSI2P' : 1536x864 [120.13 fps - (0, 0)/4608x2592 crop]
1 : ov5647 [2592x1944 10-bit GBRG] (/base/soc/i2c0mux/i2c@2/ov5647@36)
"""


class CameraInventoryTests(unittest.TestCase):
    def test_parse_rpicam_list_cameras_detects_sensor_and_wide_lens(self):
        self.assertEqual(
            parse_rpicam_list_cameras(RPICAM_OUTPUT),
            [
                {"key": "rpicam:0", "index": 0, "sensor": "imx708", "model": "imx708_wide", "lens": "wide", "path": "/base/soc/i2c0mux/i2c@1/imx708@1a"},
                {"key": "rpicam:1", "index": 1, "sensor": "ov5647", "model": "ov5647", "lens": "normal", "path": "/base/soc/i2c0mux/i2c@2/ov5647@36"},
            ],
        )

    def test_camera_key_uses_rpicam_index(self):
        self.assertEqual(camera_key(2), "rpicam:2")

    def test_detect_rpicam_cameras_falls_back_to_libcamera_hello(self):
        calls = []

        def fake_check_output(command, **kwargs):
            calls.append(command)
            if command[0] == "rpicam-hello":
                raise FileNotFoundError("missing")
            return RPICAM_OUTPUT

        with patch("plamp_web.camera_inventory.subprocess.check_output", side_effect=fake_check_output):
            cameras = detect_rpicam_cameras()

        self.assertEqual([call[0] for call in calls], ["rpicam-hello", "libcamera-hello"])
        self.assertEqual(cameras[0]["key"], "rpicam:0")
```

Add to `tests/test_pages.py`:

```python
    def test_settings_page_includes_detected_raspberry_pi_cameras(self):
        html = render_settings_page({
            "host_time": {"display": "1:23 PM"},
            "host": {"hostname": "plamp", "network": []},
            "picos": [],
            "tools": {"mpremote": None, "pyserial": "3.5"},
            "software": {"git_short_commit": "d5883da", "git_branch": "main", "git_dirty": False},
            "cameras": {"rpicam": [{"key": "rpicam:0", "index": 0, "sensor": "imx708", "model": "imx708_wide", "lens": "wide", "path": "/base/imx708@1a"}]},
            "storage": {"path": "/tmp", "free": "42.0 GB", "used": "10.0 GB", "total": "52.0 GB"},
        })

        self.assertIn("Raspberry Pi cameras", html)
        self.assertIn("rpicam:0", html)
        self.assertIn("imx708_wide", html)
        self.assertIn("wide", html)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `/home/hugo/.local/bin/uv run python -m unittest tests.test_camera_inventory tests.test_pages.PageRenderTests.test_settings_page_includes_detected_raspberry_pi_cameras -v`

Expected: FAIL because `plamp_web.camera_inventory` and Settings camera rendering do not exist.

- [ ] **Step 3: Implement camera inventory helper**

Create `plamp_web/camera_inventory.py`:

```python
from __future__ import annotations

import re
import subprocess
from typing import Any

CAMERA_RE = re.compile(r"^\s*(\d+)\s*:\s*([^\s\[]+)\s*\[[^\]]*\]\s*\(([^)]+)\)")


def camera_key(index: int) -> str:
    return f"rpicam:{index}"


def sensor_from_model(model: str) -> str:
    return model.split("_", 1)[0]


def lens_from_model(model: str) -> str:
    return "wide" if "wide" in model.lower() else "normal"


def parse_rpicam_list_cameras(output: str) -> list[dict[str, Any]]:
    cameras = []
    for line in output.splitlines():
        match = CAMERA_RE.match(line)
        if not match:
            continue
        index = int(match.group(1))
        model = match.group(2)
        cameras.append({
            "key": camera_key(index),
            "index": index,
            "sensor": sensor_from_model(model),
            "model": model,
            "lens": lens_from_model(model),
            "path": match.group(3),
        })
    return cameras


def detect_rpicam_cameras() -> list[dict[str, Any]]:
    for command in (["rpicam-hello", "--list-cameras"], ["libcamera-hello", "--list-cameras"]):
        try:
            output = subprocess.check_output(command, text=True, stderr=subprocess.STDOUT, timeout=5)
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            continue
        return parse_rpicam_list_cameras(output)
    return []
```

- [ ] **Step 4: Add settings camera summary and rendering**

Modify `plamp_web/server.py`:

```python
from plamp_web import camera_capture, camera_inventory
```

Add to `settings_summary()`:

```python
"cameras": {
    "rpicam": camera_inventory.detect_rpicam_cameras(),
},
```

Modify `plamp_web/pages.py` inside `render_settings_page` to build rows:

```python
    cameras = summary.get("cameras") if isinstance(summary.get("cameras"), dict) else {}
    rpicam_cameras = cameras.get("rpicam") if isinstance(cameras.get("rpicam"), list) else []
    camera_rows = "\n".join(
        "<tr>"
        f"<td><code>{html.escape(str(item.get('key') or '-'))}</code></td>"
        f"<td>{html.escape(str(item.get('model') or '-'))}</td>"
        f"<td>{html.escape(str(item.get('sensor') or '-'))}</td>"
        f"<td>{html.escape(str(item.get('lens') or '-'))}</td>"
        f"<td><code>{html.escape(str(item.get('path') or '-'))}</code></td>"
        "</tr>"
        for item in rpicam_cameras
    ) or '<tr><td colspan="5">No Raspberry Pi cameras found.</td></tr>'
```

Insert after the Picos table:

```html
  <h2>Raspberry Pi cameras</h2>
  <table>
    <thead><tr><th>Key</th><th>Model</th><th>Sensor</th><th>Lens</th><th>Path</th></tr></thead>
    <tbody>{camera_rows}</tbody>
  </table>
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `/home/hugo/.local/bin/uv run python -m unittest tests.test_camera_inventory tests.test_pages -v`

Expected: all listed tests pass.

- [ ] **Step 6: Commit**

```bash
git add plamp_web/camera_inventory.py plamp_web/server.py plamp_web/pages.py tests/test_camera_inventory.py tests/test_pages.py
git commit -m "Add Raspberry Pi camera inventory"
```

## Task 3: Add Config API Endpoints

**Files:**
- Modify: `plamp_web/server.py`
- Create: `tests/test_config_api.py`

- [ ] **Step 1: Write failing API tests**

Create `tests/test_config_api.py`:

```python
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

import plamp_web.server as server


class ConfigApiTests(unittest.TestCase):
    def make_config(self, root: Path, data: dict) -> Path:
        path = root / "data" / "config.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_get_config_returns_config_and_detected_hardware_separately(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = self.make_config(root, {"timers": [{"role": "pump_lights", "pico_serial": "abc", "channels": []}]})
            with (
                patch.object(server, "CONFIG_FILE", config_file),
                patch.object(server, "enumerate_picos", return_value=[{"serial": "abc", "port": "/dev/ttyACM0"}]),
                patch.object(server.camera_inventory, "detect_rpicam_cameras", return_value=[{"key": "rpicam:0", "index": 0, "model": "imx708_wide", "sensor": "imx708", "lens": "wide"}]),
            ):
                data = server.get_config()

        self.assertIn("config", data)
        self.assertIn("detected", data)
        self.assertEqual(data["config"]["controllers"]["pico:abc"]["name"], "pump_lights")
        self.assertEqual(data["detected"]["picos"][0]["serial"], "abc")
        self.assertEqual(data["detected"]["cameras"][0]["key"], "rpicam:0")

    def test_put_config_devices_updates_hardware_and_timers_projection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = self.make_config(root, {"timers": [], "hardware": {"controllers": {"pico:abc": {"name": "pump_lights", "type": "pico_scheduler"}}, "devices": {}, "cameras": {}}})
            with patch.object(server, "CONFIG_FILE", config_file):
                data = server.put_config_devices({"pump": {"name": "Pump", "type": "gpio", "controller": "pico:abc", "pin": 3, "default_editor": "cycle"}})

            saved = json.loads(config_file.read_text(encoding="utf-8"))

        self.assertEqual(data["config"]["devices"]["pump"]["pin"], 3)
        self.assertEqual(saved["timers"][0]["channels"][0]["id"], "pump")

    def test_put_config_devices_rejects_unknown_controller(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = self.make_config(root, {"timers": [], "hardware": {"controllers": {}, "devices": {}, "cameras": {}}})
            with patch.object(server, "CONFIG_FILE", config_file):
                with self.assertRaises(HTTPException) as cm:
                    server.put_config_devices({"pump": {"name": "Pump", "type": "gpio", "controller": "pico:missing", "pin": 3}})

        self.assertEqual(cm.exception.status_code, 422)
        self.assertIn("unknown controller", cm.exception.detail)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `/home/hugo/.local/bin/uv run python -m unittest tests.test_config_api -v`

Expected: FAIL because `get_config` and section PUT functions do not exist.

- [ ] **Step 3: Implement API helpers and endpoints**

Modify `plamp_web/server.py` imports:

```python
from plamp_web import camera_capture, camera_inventory
from plamp_web.hardware_config import apply_hardware_section, hardware_view
```

Add helper:

```python
def config_response() -> dict[str, Any]:
    config = load_config()
    return {
        "config": hardware_view(config),
        "detected": {
            "picos": enumerate_picos(),
            "cameras": camera_inventory.detect_rpicam_cameras(),
        },
    }
```

Add endpoints near `/api/timer-config`:

```python
@app.get("/api/config")
def get_config() -> dict[str, Any]:
    return config_response()


def put_config_section(section: str, value: dict[str, Any]) -> dict[str, Any]:
    with config_lock:
        config = load_config()
        try:
            updated = apply_hardware_section(config, section, value)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        atomic_write_json(CONFIG_FILE, updated)
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/home/hugo/.local/bin/uv run python -m unittest tests.test_hardware_config tests.test_config_api -v`

Expected: all listed tests pass.

- [ ] **Step 5: Commit**

```bash
git add plamp_web/server.py tests/test_config_api.py
git commit -m "Add config API endpoints"
```

## Task 4: Add Config Page Renderer

**Files:**
- Modify: `plamp_web/pages.py`
- Modify: `plamp_web/server.py`
- Modify: `tests/test_pages.py`

- [ ] **Step 1: Write failing page-render tests**

Add to `tests/test_pages.py` imports:

```python
from plamp_web.pages import render_api_test_page, render_config_page, render_settings_page, render_timer_dashboard_page
```

Add tests:

```python
    def test_config_page_includes_form_rows_for_controllers_devices_and_cameras(self):
        html = render_config_page(
            {
                "controllers": {"pico:abc": {"name": "pump_lights", "type": "pico_scheduler"}},
                "devices": {"pump": {"name": "Pump", "type": "gpio", "controller": "pico:abc", "pin": 3, "default_editor": "cycle"}},
                "cameras": {"rpicam:0": {"name": "Tent camera", "ir_filter": "unknown"}},
            },
            {"picos": [{"serial": "abc", "port": "/dev/ttyACM0"}], "cameras": [{"key": "rpicam:0", "model": "imx708_wide", "sensor": "imx708", "lens": "wide"}]},
        )

        self.assertIn("<title>Plamp config</title>", html)
        self.assertIn("<h2>Controllers</h2>", html)
        self.assertIn('data-controller-key="pico:abc"', html)
        self.assertIn('value="pump_lights"', html)
        self.assertIn("pico_scheduler", html)
        self.assertIn("<h2>Devices</h2>", html)
        self.assertIn('data-device-id="pump"', html)
        self.assertIn('value="Pump"', html)
        self.assertIn('value="3"', html)
        self.assertIn("<h2>Cameras</h2>", html)
        self.assertIn('data-camera-key="rpicam:0"', html)
        self.assertIn("imx708_wide", html)
        self.assertIn("Save controllers", html)
        self.assertIn("Save devices", html)
        self.assertIn("Save cameras", html)
        self.assertNotIn("<textarea", html)

    def test_config_page_posts_section_updates_from_forms(self):
        html = render_config_page({"controllers": {}, "devices": {}, "cameras": {}}, {"picos": [], "cameras": []})

        self.assertIn("collectControllers()", html)
        self.assertIn("collectDevices()", html)
        self.assertIn("collectCameras()", html)
        self.assertIn('fetch("/api/config/controllers"', html)
        self.assertIn('fetch("/api/config/devices"', html)
        self.assertIn('fetch("/api/config/cameras"', html)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `/home/hugo/.local/bin/uv run python -m unittest tests.test_pages.PageRenderTests.test_config_page_includes_form_rows_for_controllers_devices_and_cameras tests.test_pages.PageRenderTests.test_config_page_posts_section_updates_from_forms -v`

Expected: FAIL because `render_config_page` does not exist.

- [ ] **Step 3: Implement server-rendered form rows, not JSON textareas**

Add helper functions to `plamp_web/pages.py` before `render_settings_page`:

```python
def option_tag(value: str, label: str, selected: str | None) -> str:
    selected_attr = " selected" if value == selected else ""
    return f'<option value="{html.escape(value)}"{selected_attr}>{html.escape(label)}</option>'


def controller_options(controllers: dict[str, Any], selected: str | None) -> str:
    return "\n".join(
        option_tag(key, str(item.get("name") or key), selected)
        for key, item in controllers.items()
        if isinstance(item, dict)
    )
```

Add `render_config_page(config, detected)` with this structure:

```python
def render_config_page(config: dict[str, Any], detected: dict[str, Any]) -> str:
    controllers = config.get("controllers") if isinstance(config.get("controllers"), dict) else {}
    devices = config.get("devices") if isinstance(config.get("devices"), dict) else {}
    cameras = config.get("cameras") if isinstance(config.get("cameras"), dict) else {}
    picos = detected.get("picos") if isinstance(detected.get("picos"), list) else []
    detected_cameras = detected.get("cameras") if isinstance(detected.get("cameras"), list) else []
    detected_controller_keys = {f"pico:{item.get('serial')}": item for item in picos if isinstance(item, dict) and item.get("serial")}
    all_controller_keys = sorted(set(controllers) | set(detected_controller_keys))
    detected_camera_keys = {str(item.get("key")): item for item in detected_cameras if isinstance(item, dict) and item.get("key")}
    all_camera_keys = sorted(set(cameras) | set(detected_camera_keys))

    controller_rows = "\n".join(
        '<tr class="controller-row" data-controller-key="{key}">' \
        '<td><code>{key_label}</code><div class="muted">{detected}</div></td>' \
        '<td><input class="controller-name" value="{name}"></td>' \
        '<td><select class="controller-type">{type_options}</select></td>' \
        '</tr>'.format(
            key=html.escape(key),
            key_label=html.escape(key),
            detected=html.escape(str(detected_controller_keys.get(key, {}).get("port") or "configured")),
            name=html.escape(str(controllers.get(key, {}).get("name") or ""), quote=True),
            type_options="".join(option_tag(value, value, str(controllers.get(key, {}).get("type") or "pico_scheduler")) for value in ["pico_scheduler", "food_dispenser", "ph_dispenser"]),
        )
        for key in all_controller_keys
    ) or '<tr><td colspan="3">No detected or configured controllers.</td></tr>'

    device_rows = "\n".join(
        '<tr class="device-row" data-device-id="{device_id}">' \
        '<td><input class="device-id" value="{device_id}"></td>' \
        '<td><input class="device-name" value="{name}"></td>' \
        '<td><select class="device-type"><option value="gpio" selected>gpio</option></select></td>' \
        '<td><select class="device-controller">{controller_options_html}</select></td>' \
        '<td><input class="device-pin" type="number" min="0" max="29" value="{pin}"></td>' \
        '<td><select class="device-editor">{editor_options}</select></td>' \
        '</tr>'.format(
            device_id=html.escape(device_id, quote=True),
            name=html.escape(str(device.get("name") or ""), quote=True),
            controller_options_html=controller_options(controllers, str(device.get("controller") or "")),
            pin=html.escape(str(device.get("pin") if device.get("pin") is not None else ""), quote=True),
            editor_options="".join(option_tag(value, value, str(device.get("default_editor") or "cycle")) for value in ["cycle", "clock_window"]),
        )
        for device_id, device in devices.items()
        if isinstance(device, dict)
    ) or '<tr><td colspan="6">No configured devices.</td></tr>'

    camera_rows = "\n".join(
        '<tr class="camera-row" data-camera-key="{key}">' \
        '<td><code>{key_label}</code><div class="muted">{detected}</div></td>' \
        '<td><input class="camera-name" value="{name}"></td>' \
        '<td><select class="camera-ir-filter">{ir_options}</select></td>' \
        '</tr>'.format(
            key=html.escape(key, quote=True),
            key_label=html.escape(key),
            detected=html.escape(" ".join(str(detected_camera_keys.get(key, {}).get(field) or "") for field in ["model", "lens"]).strip() or "configured"),
            name=html.escape(str(cameras.get(key, {}).get("name") or ""), quote=True),
            ir_options="".join(option_tag(value, value, str(cameras.get(key, {}).get("ir_filter") or "unknown")) for value in ["unknown", "normal", "noir"]),
        )
        for key in all_camera_keys
    ) or '<tr><td colspan="3">No detected or configured cameras.</td></tr>'

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
  <nav><a href="/">Plamp</a> | <a href="/settings">Settings</a></nav>
  <h1>Plamp config</h1>
  <h2>Controllers</h2>
  <table><thead><tr><th>Detected key</th><th>Name</th><th>Type</th></tr></thead><tbody>{controller_rows}</tbody></table>
  <button id="save-controllers" type="button">Save controllers</button> <span id="controllers-status" class="status">Ready.</span>
  <h2>Devices</h2>
  <table><thead><tr><th>ID</th><th>Name</th><th>Type</th><th>Controller</th><th>Pin</th><th>Default editor</th></tr></thead><tbody>{device_rows}</tbody></table>
  <button id="save-devices" type="button">Save devices</button> <span id="devices-status" class="status">Ready.</span>
  <h2>Cameras</h2>
  <table><thead><tr><th>Detected key</th><th>Name</th><th>IR filter</th></tr></thead><tbody>{camera_rows}</tbody></table>
  <button id="save-cameras" type="button">Save cameras</button> <span id="cameras-status" class="status">Ready.</span>
  <script>
    function collectControllers() {{
      const result = {{}};
      for (const row of document.querySelectorAll(".controller-row")) {{
        const name = row.querySelector(".controller-name").value.trim();
        if (!name) continue;
        result[row.dataset.controllerKey] = {{name, type: row.querySelector(".controller-type").value}};
      }}
      return result;
    }}
    function collectDevices() {{
      const result = {{}};
      for (const row of document.querySelectorAll(".device-row")) {{
        const id = row.querySelector(".device-id").value.trim();
        if (!id) continue;
        result[id] = {{name: row.querySelector(".device-name").value.trim(), type: row.querySelector(".device-type").value, controller: row.querySelector(".device-controller").value, pin: Number(row.querySelector(".device-pin").value), default_editor: row.querySelector(".device-editor").value}};
      }}
      return result;
    }}
    function collectCameras() {{
      const result = {{}};
      for (const row of document.querySelectorAll(".camera-row")) {{
        const name = row.querySelector(".camera-name").value.trim();
        if (!name) continue;
        result[row.dataset.cameraKey] = {{name, ir_filter: row.querySelector(".camera-ir-filter").value}};
      }}
      return result;
    }}
    async function saveSection(name, payload) {{
      const status = document.getElementById(`${{name}}-status`);
      status.textContent = "Saving...";
      const response = await fetch(`/api/config/${{name}}`, {{method: "PUT", headers: {{"content-type": "application/json"}}, body: JSON.stringify(payload)}});
      status.textContent = response.ok ? "Saved." : `${{response.status}} ${{await response.text()}}`;
    }}
    document.getElementById("save-controllers").addEventListener("click", () => saveSection("controllers", collectControllers()));
    document.getElementById("save-devices").addEventListener("click", () => saveSection("devices", collectDevices()));
    document.getElementById("save-cameras").addEventListener("click", () => saveSection("cameras", collectCameras()));
  </script>
</body>
</html>"""
```

- [ ] **Step 4: Add `/config` endpoint and nav links**

Modify `plamp_web/server.py` import:

```python
from plamp_web.pages import render_api_test_page, render_config_page, render_settings_page, render_timer_dashboard_page
```

Add endpoint near settings routes:

```python
@app.get("/config", response_class=HTMLResponse)
def get_config_page() -> HTMLResponse:
    data = config_response()
    return HTMLResponse(render_config_page(data["config"], data["detected"]))
```

Modify the Settings nav in `render_settings_page`:

```html
<nav><a href="/">Plamp</a> | <a href="/config">Config</a> | <a href="/api/test">API test</a> | <a href="/settings.json">Settings JSON</a></nav>
```

- [ ] **Step 5: Run page tests**

Run: `/home/hugo/.local/bin/uv run python -m unittest tests.test_pages -v`

Expected: all page tests pass.

- [ ] **Step 6: Commit**

```bash
git add plamp_web/pages.py plamp_web/server.py tests/test_pages.py
git commit -m "Add config page"
```

## Task 5: Add API Test Page Coverage for Config API

**Files:**
- Modify: `plamp_web/pages.py`
- Modify: `tests/test_pages.py`

- [ ] **Step 1: Write failing render test for config API docs**

Add to `tests/test_pages.py`:

```python
    def test_api_test_page_includes_config_routes(self):
        html = render_api_test_page(["pump_lights"], "pump_lights", "{}", "12h")

        for route in [
            "GET /api/config",
            "PUT /api/config/controllers",
            "PUT /api/config/devices",
            "PUT /api/config/cameras",
        ]:
            self.assertIn(f"<legend>{route}</legend>", html)
        self.assertIn('data-copy-target="get-config-curl-command"', html)
        self.assertIn('data-copy-target="put-config-devices-curl-command"', html)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `/home/hugo/.local/bin/uv run python -m unittest tests.test_pages.PageRenderTests.test_api_test_page_includes_config_routes -v`

Expected: FAIL because Config API docs are not on the API test page.

- [ ] **Step 3: Add Config route cards to API test page**

Modify `render_api_test_page` in `plamp_web/pages.py` after the camera section and before timers:

```html
  <h2>Config</h2>
  <fieldset>
    <legend>GET /api/config</legend>
    <p>Reads configured meaning plus detected local hardware choices.</p>
    <pre id="get-config-curl-command">curl http://localhost:8000/api/config</pre>
    <button class="copy-curl" type="button" data-copy-target="get-config-curl-command">Copy curl</button>
  </fieldset>
  <fieldset>
    <legend>PUT /api/config/controllers</legend>
    <p>Saves named local Pico controllers.</p>
    <pre id="put-config-controllers-curl-command">curl -X PUT http://localhost:8000/api/config/controllers -H 'content-type: application/json' --data '{}'</pre>
    <button class="copy-curl" type="button" data-copy-target="put-config-controllers-curl-command">Copy curl</button>
  </fieldset>
  <fieldset>
    <legend>PUT /api/config/devices</legend>
    <p>Saves device mappings to controllers and pins.</p>
    <pre id="put-config-devices-curl-command">curl -X PUT http://localhost:8000/api/config/devices -H 'content-type: application/json' --data '{}'</pre>
    <button class="copy-curl" type="button" data-copy-target="put-config-devices-curl-command">Copy curl</button>
  </fieldset>
  <fieldset>
    <legend>PUT /api/config/cameras</legend>
    <p>Saves camera names and user-confirmed IR filter values.</p>
    <pre id="put-config-cameras-curl-command">curl -X PUT http://localhost:8000/api/config/cameras -H 'content-type: application/json' --data '{}'</pre>
    <button class="copy-curl" type="button" data-copy-target="put-config-cameras-curl-command">Copy curl</button>
  </fieldset>
```

- [ ] **Step 4: Run the focused test**

Run: `/home/hugo/.local/bin/uv run python -m unittest tests.test_pages.PageRenderTests.test_api_test_page_includes_config_routes -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add plamp_web/pages.py tests/test_pages.py
git commit -m "Document config API in test page"
```

## Task 6: Document and Verify End to End

**Files:**
- Modify: `plamp_web/README.md`

- [ ] **Step 1: Update README with concrete config shape**

Add a section after the existing timer config documentation:

````markdown
## Config page

Open the local config editor:

```text
http://localhost:8000/config
```

Settings reports detected local hardware and software status. Config stores user-maintained meaning for that hardware. The first supported local hardware mappings are Pico controllers, Pico `gpio` devices, and Raspberry Pi cameras detected through `rpicam-hello --list-cameras`.

Example `data/config.json` shape:

```json
{
  "timers": [
    {
      "role": "pump_lights",
      "pico_serial": "e66038b71387a039",
      "channels": [
        {"id": "pump", "name": "Pump", "pin": 3, "type": "gpio", "default_editor": "cycle"}
      ]
    }
  ],
  "hardware": {
    "controllers": {
      "pico:e66038b71387a039": {"name": "pump_lights", "type": "pico_scheduler"}
    },
    "devices": {
      "pump": {"name": "Pump", "type": "gpio", "controller": "pico:e66038b71387a039", "pin": 3, "default_editor": "cycle"}
    },
    "cameras": {
      "rpicam:0": {"name": "Tent camera", "ir_filter": "unknown"}
    }
  }
}
```

The `timers` section remains the runtime compatibility projection used by existing timer APIs. The Pico runtime state files under `data/timers/<role>.json` remain separate and are still what gets sent to the Pico.
````

- [ ] **Step 2: Run full verification**

Run:

```bash
python -m py_compile plamp_web/server.py plamp_web/pages.py plamp_web/hardware_config.py plamp_web/camera_inventory.py tests/test_hardware_config.py tests/test_camera_inventory.py tests/test_config_api.py tests/test_pages.py
/home/hugo/.local/bin/uv run python -m unittest discover -s tests -v
```

Expected: compile command exits 0; unittest reports all tests OK.

- [ ] **Step 3: Run a live smoke check if the dev server is running**

Run:

```bash
curl -sS http://127.0.0.1:8000/api/config | python3 -m json.tool | head -n 80
curl -sS http://127.0.0.1:8000/config | grep -n "Plamp config\|Controllers\|Devices\|Cameras"
```

Expected: `/api/config` returns `config` and `detected` objects; `/config` HTML contains the three section headings.

- [ ] **Step 4: Commit docs and any final fixes**

```bash
git add plamp_web/README.md
git commit -m "Document config editor"
```

If Task 6 required code fixes, include those files in the same commit with a message that names the fix.

- [ ] **Step 5: Final status**

Run:

```bash
git status --short --branch
git log --oneline --decorate -5
```

Expected: branch is clean and contains the config editor commits.
