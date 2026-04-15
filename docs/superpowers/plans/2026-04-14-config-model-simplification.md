# Config Model Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make persisted config user-editable only, drive `/` from config instead of duplicated timer config, and keep runtime Pico state as an overlay for configured pins.

**Architecture:** Keep `plamp_web/hardware_config.py` as the single place for config validation and runtime shaping. Replace top-level `timers` and nested `hardware` config storage with three top-level sections: `controllers`, `devices`, and `cameras`. Keep live detection and timer state in `plamp_web/server.py`, but derive visible roles and devices from config and only use Pico reports for runtime values on configured pins.

**Tech Stack:** Python 3.11, FastAPI, plain server-rendered HTML, vanilla browser JavaScript, stdlib `unittest`, existing JSON config helpers.

---

## File Structure

- Modify `plamp_web/hardware_config.py`: validate the new top-level config model, keep optional controller-to-Pico assignment, and provide runtime helpers for controllers and devices.
- Modify `plamp_web/server.py`: load the new config shape, update config endpoints, derive monitor startup and `/` data from config, and stop projecting persisted `timers` config.
- Modify `plamp_web/timer_schedule.py`: build editable device metadata from config devices plus live state instead of `role_config["channels"]`.
- Modify `plamp_web/pages.py`: simplify the Config page fields to match the new model and use device-focused wording.
- Modify `tests/test_hardware_config.py`: replace hardware/timer projection tests with top-level config validation and delete tests.
- Modify `tests/test_config_api.py`: verify top-level config writes and no `timers` projection.
- Modify `tests/test_timer_schedule.py`: verify runtime device metadata comes from config devices keyed by controller and pin.
- Modify `tests/test_pages.py`: verify the Config page shows ids, pins, editor fields, and no stale name/type/default-editor wording.
- Modify `plamp_web/README.md`: document the new config shape and the fact that `/` is config-driven.
- Modify `data/config.json`: update the checked-in sample config to the new top-level shape.

### Task 1: Replace the persisted config model in `hardware_config.py`

**Files:**
- Modify: `plamp_web/hardware_config.py`
- Modify: `tests/test_hardware_config.py`

- [ ] **Step 1: Write the failing tests for the new top-level config model**

Update `tests/test_hardware_config.py` to remove `timers`/`hardware` expectations and assert the new persisted shape:

```python
import unittest

from plamp_web.hardware_config import apply_config_section, config_view, runtime_controller_serials


class HardwareConfigTests(unittest.TestCase):
    def test_config_view_returns_top_level_sections(self):
        config = {
            "controllers": {"pump_lights": {"pico_serial": "e66038b71387a039"}},
            "devices": {"pump": {"controller": "pump_lights", "pin": 2, "editor": "cycle"}},
            "cameras": {"cam0": {}},
            "timers": [{"role": "old"}],
            "hardware": {"controllers": {"legacy": {}}},
        }

        self.assertEqual(
            config_view(config),
            {
                "controllers": {"pump_lights": {"pico_serial": "e66038b71387a039"}},
                "devices": {"pump": {"controller": "pump_lights", "pin": 2, "editor": "cycle"}},
                "cameras": {"cam0": {}},
            },
        )

    def test_apply_devices_accepts_id_controller_pin_and_editor(self):
        updated = apply_config_section(
            {"controllers": {"pump_lights": {}}, "devices": {}, "cameras": {}},
            "devices",
            {"pump": {"controller": "pump_lights", "pin": 2, "editor": "cycle"}},
        )

        self.assertEqual(updated["devices"]["pump"], {"controller": "pump_lights", "pin": 2, "editor": "cycle"})
        self.assertNotIn("timers", updated)

    def test_apply_devices_rejects_unknown_controller(self):
        with self.assertRaisesRegex(ValueError, "unknown controller"):
            apply_config_section(
                {"controllers": {}, "devices": {}, "cameras": {}},
                "devices",
                {"pump": {"controller": "missing", "pin": 2, "editor": "cycle"}},
            )

    def test_apply_controllers_accepts_optional_pico_serial(self):
        updated = apply_config_section(
            {"controllers": {}, "devices": {}, "cameras": {}},
            "controllers",
            {"pump_lights": {"pico_serial": "e66038b71387a039"}},
        )

        self.assertEqual(runtime_controller_serials(updated), {"pump_lights": "e66038b71387a039"})

    def test_apply_controllers_rejects_delete_with_attached_devices(self):
        with self.assertRaisesRegex(ValueError, "references missing controller"):
            apply_config_section(
                {
                    "controllers": {},
                    "devices": {"pump": {"controller": "pump_lights", "pin": 2, "editor": "cycle"}},
                    "cameras": {},
                },
                "devices",
                {"pump": {"controller": "pump_lights", "pin": 2, "editor": "cycle"}},
            )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `/home/hugo/.local/bin/uv run python -m unittest tests.test_hardware_config -v`

Expected: FAIL with import errors for `apply_config_section` or assertion failures around `hardware` / `timers`.

- [ ] **Step 3: Implement the new config helpers**

Replace the legacy hardware/timer projection helpers in `plamp_web/hardware_config.py` with top-level config validation:

```python
from __future__ import annotations

import copy
import re
from typing import Any

CONTROLLER_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")
DEVICE_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")
CAMERA_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")
EDITORS = {"cycle", "clock_window"}


def empty_config() -> dict[str, Any]:
    return {"controllers": {}, "devices": {}, "cameras": {}}


def config_view(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "controllers": dict(config.get("controllers") or {}),
        "devices": dict(config.get("devices") or {}),
        "cameras": dict(config.get("cameras") or {}),
    }


def validate_controllers(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict):
        raise ValueError("controllers must be an object")
    result: dict[str, dict[str, Any]] = {}
    for controller_id, item in value.items():
        if not isinstance(controller_id, str) or not CONTROLLER_ID_RE.match(controller_id):
            raise ValueError("controller ids must use letters, numbers, underscore, or dash")
        if item is None:
            item = {}
        if not isinstance(item, dict):
            raise ValueError(f"controller {controller_id} must be an object")
        pico_serial = item.get("pico_serial")
        if pico_serial is not None and (not isinstance(pico_serial, str) or not pico_serial):
            raise ValueError(f"controller {controller_id} has invalid pico_serial")
        result[controller_id] = {"pico_serial": pico_serial} if pico_serial else {}
    return result


def validate_devices(value: Any, controllers: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict):
        raise ValueError("devices must be an object")
    result: dict[str, dict[str, Any]] = {}
    for device_id, item in value.items():
        if not isinstance(device_id, str) or not DEVICE_ID_RE.match(device_id):
            raise ValueError("device ids must use letters, numbers, underscore, or dash")
        if not isinstance(item, dict):
            raise ValueError(f"device {device_id} must be an object")
        controller_id = item.get("controller")
        pin = item.get("pin")
        editor = item.get("editor", "cycle")
        if controller_id not in controllers:
            raise ValueError(f"device {device_id} references unknown controller")
        if not isinstance(pin, int) or pin < 0 or pin > 29:
            raise ValueError(f"device {device_id} has invalid pin")
        if editor not in EDITORS:
            raise ValueError(f"device {device_id} has unsupported editor")
        result[device_id] = {"controller": controller_id, "pin": pin, "editor": editor}
    return result


def validate_cameras(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict):
        raise ValueError("cameras must be an object")
    result: dict[str, dict[str, Any]] = {}
    for camera_id, item in value.items():
        if not isinstance(camera_id, str) or not CAMERA_ID_RE.match(camera_id):
            raise ValueError("camera ids must use letters, numbers, underscore, or dash")
        if item is None:
            item = {}
        if not isinstance(item, dict):
            raise ValueError(f"camera {camera_id} must be an object")
        result[camera_id] = {}
    return result


def apply_config_section(config: dict[str, Any], section: str, value: Any) -> dict[str, Any]:
    updated = copy.deepcopy(config_view(config))
    if section == "controllers":
        updated["controllers"] = validate_controllers(value)
        updated["devices"] = validate_devices(updated["devices"], updated["controllers"])
    elif section == "devices":
        updated["devices"] = validate_devices(value, updated["controllers"])
    elif section == "cameras":
        updated["cameras"] = validate_cameras(value)
    else:
        raise ValueError(f"unknown config section: {section}")
    return updated


def runtime_controller_serials(config: dict[str, Any]) -> dict[str, str]:
    return {
        controller_id: str(item["pico_serial"])
        for controller_id, item in config_view(config)["controllers"].items()
        if isinstance(item, dict) and item.get("pico_serial")
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `/home/hugo/.local/bin/uv run python -m unittest tests.test_hardware_config -v`

Expected: PASS for all `HardwareConfigTests`.

- [ ] **Step 5: Commit**

```bash
git add plamp_web/hardware_config.py tests/test_hardware_config.py
git commit -m "Simplify persisted config model"
```

### Task 2: Update config loading, config API, and Config page fields

**Files:**
- Modify: `plamp_web/server.py`
- Modify: `plamp_web/pages.py`
- Modify: `tests/test_config_api.py`
- Modify: `tests/test_pages.py`
- Modify: `data/config.json`

- [ ] **Step 1: Write the failing API and page tests**

Update `tests/test_config_api.py` and `tests/test_pages.py` for the new top-level config shape and simpler form fields:

```python
class ConfigApiTests(unittest.TestCase):
    def test_get_config_returns_top_level_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = self.make_config(
                root,
                {
                    "controllers": {"pump_lights": {"pico_serial": "abc"}},
                    "devices": {"pump": {"controller": "pump_lights", "pin": 2, "editor": "cycle"}},
                    "cameras": {"cam0": {}},
                },
            )
            with (
                patch.object(server, "CONFIG_FILE", config_file),
                patch.object(server, "enumerate_picos", return_value=[{"serial": "abc", "port": "/dev/ttyACM0"}]),
                patch.object(server.hardware_inventory, "detect_rpicam_cameras", return_value=[{"key": "cam0", "model": "imx708_wide"}]),
            ):
                data = server.get_config()

        self.assertEqual(data["config"]["devices"]["pump"]["pin"], 2)
        self.assertNotIn("timers", json.loads(config_file.read_text(encoding="utf-8")))

    def test_put_config_devices_writes_top_level_devices_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = self.make_config(root, {"controllers": {"pump_lights": {}}, "devices": {}, "cameras": {}})
            with patch.object(server, "CONFIG_FILE", config_file):
                server.put_config_devices({"pump": {"controller": "pump_lights", "pin": 3, "editor": "cycle"}})

            saved = json.loads(config_file.read_text(encoding="utf-8"))

        self.assertEqual(saved["devices"]["pump"], {"controller": "pump_lights", "pin": 3, "editor": "cycle"})
        self.assertNotIn("timers", saved)
```

```python
class PageRenderTests(unittest.TestCase):
    def test_config_page_uses_id_pin_and_editor_fields(self):
        html = render_config_page(
            {
                "controllers": {"pump_lights": {"pico_serial": "e66038b71387a039"}},
                "devices": {"pump": {"controller": "pump_lights", "pin": 3, "editor": "cycle"}},
                "cameras": {"cam0": {}},
            },
            {"picos": [{"serial": "e66038b71387a039", "port": "/dev/ttyACM0"}], "cameras": [{"key": "cam0", "model": "imx708_wide"}]},
        )

        self.assertIn("<th>ID</th>", html)
        self.assertIn("<th>Pin</th>", html)
        self.assertIn("<th>Editor</th>", html)
        self.assertNotIn("Default editor", html)
        self.assertNotIn("<th>Name</th>", html)
        self.assertNotIn("<th>Type</th>", html)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `/home/hugo/.local/bin/uv run python -m unittest tests.test_config_api tests.test_pages -v`

Expected: FAIL because `server.py` still expects `timers` / `hardware`, and `render_config_page()` still renders name/type/default-editor fields.

- [ ] **Step 3: Implement the config API and page changes**

In `plamp_web/server.py`, switch config storage and default config creation to the new top-level sections:

```python
from plamp_web.hardware_config import apply_config_section, config_view, runtime_controller_serials


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    TIMERS_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_FILE.exists():
        atomic_write_json(CONFIG_FILE, {"controllers": {}, "devices": {}, "cameras": {}})


def load_config() -> dict[str, Any]:
    ensure_data_dir()
    data = load_json_file(CONFIG_FILE)
    if not isinstance(data, dict):
        raise HTTPException(status_code=500, detail="config.json must be an object")
    config = config_view(data)
    for section in ["controllers", "devices", "cameras"]:
        if not isinstance(config[section], dict):
            raise HTTPException(status_code=500, detail=f"config.json {section} must be an object")
    return config


def config_response() -> dict[str, Any]:
    config = load_config()
    return {
        "config": config,
        "detected": {
            "picos": enumerate_picos(),
            "cameras": hardware_inventory.detect_rpicam_cameras(),
        },
    }


def put_config_section(section: str, value: dict[str, Any]) -> dict[str, Any]:
    with config_lock:
        config = load_config()
        try:
            updated = apply_config_section(config, section, value)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        atomic_write_json(CONFIG_FILE, updated)
    return config_response()
```

In `plamp_web/pages.py`, simplify the Config page fields and payload collection:

```python
def controller_options(controllers: dict[str, Any], selected: str | None) -> str:
    return "\n".join(option_tag(controller_id, controller_id, selected) for controller_id in sorted(controllers))


def render_config_page(config: dict[str, Any], detected: dict[str, Any]) -> str:
    controllers = config.get("controllers") if isinstance(config.get("controllers"), dict) else {}
    devices = config.get("devices") if isinstance(config.get("devices"), dict) else {}
    cameras = config.get("cameras") if isinstance(config.get("cameras"), dict) else {}
    picos = detected.get("picos") if isinstance(detected.get("picos"), list) else []

    controller_rows = "\n".join(
        '<tr class="controller-row" data-controller-id="{controller_id}">' 
        '<td><input class="controller-id" value="{controller_id}"></td>'
        '<td><select class="controller-pico-serial">{pico_options_html}</select></td>'
        '</tr>'.format(
            controller_id=html.escape(controller_id, quote=True),
            pico_options_html=pico_options(picos, str(item.get("pico_serial") or "")),
        )
        for controller_id, item in controllers.items()
    )

    device_rows = "\n".join(
        '<tr class="device-row" data-device-id="{device_id}">' 
        '<td><input class="device-id" value="{device_id}"></td>'
        '<td><select class="device-controller">{controller_options_html}</select></td>'
        '<td><input class="device-pin" type="number" min="0" max="29" value="{pin}"></td>'
        '<td><select class="device-editor">{editor_options}</select></td>'
        '</tr>'.format(
            device_id=html.escape(device_id, quote=True),
            controller_options_html=controller_options(controllers, str(device.get("controller") or "")),
            pin=html.escape(str(device.get("pin") if device.get("pin") is not None else ""), quote=True),
            editor_options="".join(option_tag(value, value, str(device.get("editor") or "cycle")) for value in ["cycle", "clock_window"]),
        )
        for device_id, device in devices.items()
        if isinstance(device, dict)
    )

    def collectControllers() {
      const result = {};
      for (const row of document.querySelectorAll(".controller-row")) {
        const id = row.querySelector(".controller-id").value.trim();
        if (!id) continue;
        const picoSerial = row.querySelector(".controller-pico-serial").value || null;
        result[id] = picoSerial ? {pico_serial: picoSerial} : {};
      }
      return result;
    }

    def collectDevices() {
      const result = {};
      for (const row of document.querySelectorAll(".device-row")) {
        const id = row.querySelector(".device-id").value.trim();
        if (!id) continue;
        result[id] = {
          controller: row.querySelector(".device-controller").value,
          pin: Number(row.querySelector(".device-pin").value),
          editor: row.querySelector(".device-editor").value,
        };
      }
      return result;
    }
```

Update `data/config.json` to the checked-in sample:

```json
{
  "controllers": {
    "pump_lights": {
      "pico_serial": "e66038b71387a039"
    }
  },
  "devices": {
    "pump": {
      "controller": "pump_lights",
      "pin": 2,
      "editor": "cycle"
    },
    "lights": {
      "controller": "pump_lights",
      "pin": 3,
      "editor": "clock_window"
    }
  },
  "cameras": {
    "cam0": {}
  }
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `/home/hugo/.local/bin/uv run python -m unittest tests.test_config_api tests.test_pages -v`

Expected: PASS for the config API and page render tests.

- [ ] **Step 5: Commit**

```bash
git add plamp_web/server.py plamp_web/pages.py tests/test_config_api.py tests/test_pages.py data/config.json
git commit -m "Update config API and page for simplified model"
```

### Task 3: Drive `/` and schedule editing from configured devices

**Files:**
- Modify: `plamp_web/server.py`
- Modify: `plamp_web/timer_schedule.py`
- Modify: `tests/test_timer_schedule.py`
- Modify: `tests/test_config_api.py`

- [ ] **Step 1: Write the failing runtime tests**

Update `tests/test_timer_schedule.py` so device metadata is built from config devices grouped by controller id instead of `role_config["channels"]`:

```python
class TimerScheduleTests(unittest.TestCase):
    def test_channel_metadata_uses_configured_devices_for_controller(self):
        config = {
            "devices": {
                "lamp": {"controller": "sprouter", "pin": 2, "editor": "clock_window"},
                "fan": {"controller": "sprouter", "pin": 3, "editor": "cycle"},
                "pump": {"controller": "other", "pin": 4, "editor": "cycle"},
            }
        }
        state = {"events": [{"id": "lamp", "type": "gpio", "ch": 2}, {"id": "fan", "type": "gpio", "ch": 3}]}

        self.assertEqual(
            channel_metadata_for_role("sprouter", config, state),
            [
                {"role": "sprouter", "id": "fan", "pin": 3, "type": "gpio", "editor": "cycle"},
                {"role": "sprouter", "id": "lamp", "pin": 2, "type": "gpio", "editor": "clock_window"},
            ],
        )

    def test_channel_metadata_ignores_unconfigured_pins(self):
        config = {"devices": {"lamp": {"controller": "sprouter", "pin": 2, "editor": "clock_window"}}}
        state = {"events": [{"id": "lamp", "type": "gpio", "ch": 2}, {"id": "fan", "type": "gpio", "ch": 3}]}

        self.assertEqual(
            channel_metadata_for_role("sprouter", config, state),
            [{"role": "sprouter", "id": "lamp", "pin": 2, "type": "gpio", "editor": "clock_window"}],
        )
```

Add one server-level regression in `tests/test_config_api.py` so config changes affect `/` inputs immediately:

```python
def test_get_timer_config_uses_devices_from_top_level_config(self):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        config_file = self.make_config(
            root,
            {
                "controllers": {"pump_lights": {}},
                "devices": {"pump": {"controller": "pump_lights", "pin": 2, "editor": "cycle"}},
                "cameras": {},
            },
        )
        timers_dir = root / "data" / "timers"
        timers_dir.mkdir(parents=True)
        (timers_dir / "pump_lights.json").write_text(json.dumps({"report_every": 1, "events": [{"id": "pump", "type": "gpio", "ch": 2, "current_t": 0, "reschedule": 1, "pattern": [{"val": 1, "dur": 10}, {"val": 0, "dur": 20}]}]}), encoding="utf-8")
        with (
            patch.object(server, "CONFIG_FILE", config_file),
            patch.object(server, "TIMERS_DIR", timers_dir),
            patch.object(server, "latest_timer_state", return_value=None),
        ):
            data = server.get_timer_config()

    self.assertEqual(data["roles"], ["pump_lights"])
    self.assertEqual(data["channels"]["pump_lights"][0]["id"], "pump")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `/home/hugo/.local/bin/uv run python -m unittest tests.test_timer_schedule tests.test_config_api -v`

Expected: FAIL because `configured_timer_roles()`, `configured_timer_channels()`, and `channel_metadata_for_role()` still expect `timers` and `channels`.

- [ ] **Step 3: Implement config-driven runtime joins**

In `plamp_web/server.py`, derive roles and monitor serials from the simplified config:

```python
from plamp_web.hardware_config import config_view, runtime_controller_serials


def configured_timer_roles() -> list[str]:
    try:
        return sorted(load_config()["controllers"])
    except HTTPException:
        return []


def controller_serial(role: str) -> str:
    serials = runtime_controller_serials(load_config())
    serial = serials.get(role)
    if not serial:
        raise HTTPException(status_code=409, detail=f"controller {role} has no assigned pico_serial")
    return serial


def get_or_start_monitor(role: str) -> PicoMonitor:
    pico_serial = controller_serial(role)
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
        serials = runtime_controller_serials(load_config())
    except HTTPException:
        return
    for role in sorted(serials):
        get_or_start_monitor(role)
```

In `plamp_web/timer_schedule.py`, build device metadata from top-level devices and overlay only configured pins:

```python
def channel_metadata_for_role(role: str, config: dict[str, Any], state: dict[str, Any] | None) -> list[dict[str, Any]]:
    devices = config.get("devices") if isinstance(config, dict) else None
    if isinstance(devices, dict):
        result: list[dict[str, Any]] = []
        events = state.get("events", []) if isinstance(state, dict) else []
        event_by_pin = {
            int(event.get("ch")): event
            for event in events
            if isinstance(event, dict) and event.get("ch") is not None
        }
        for device_id in sorted(devices):
            device = devices[device_id]
            if not isinstance(device, dict) or device.get("controller") != role:
                continue
            pin = _as_int(device.get("pin"), f"device {device_id} pin")
            event = event_by_pin.get(pin, {})
            result.append(
                {
                    "role": role,
                    "id": device_id,
                    "pin": pin,
                    "type": str(event.get("type") or "gpio"),
                    "editor": str(device.get("editor") or "cycle"),
                }
            )
        return result
    return []
```

Also update `configured_timer_channels()` in `plamp_web/server.py` to pass the full config object to `channel_metadata_for_role()` instead of a legacy `role_config` item.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `/home/hugo/.local/bin/uv run python -m unittest tests.test_timer_schedule tests.test_config_api -v`

Expected: PASS for the runtime join and config-to-main-page regression tests.

- [ ] **Step 5: Commit**

```bash
git add plamp_web/server.py plamp_web/timer_schedule.py tests/test_timer_schedule.py tests/test_config_api.py
git commit -m "Drive timer runtime from configured devices"
```

### Task 4: Update docs and run the focused verification set

**Files:**
- Modify: `plamp_web/README.md`
- Modify: `docs/superpowers/plans/2026-04-14-config-model-simplification.md`

- [x] **Step 1: Write the failing documentation assertions as a checklist in the README diff**

Update the config section in `plamp_web/README.md` so it documents the new top-level config shape and the main-page behavior:

```markdown
Example `data/config.json` shape:

```json
{
  "controllers": {
    "pump_lights": {
      "pico_serial": "e66038b71387a039"
    }
  },
  "devices": {
    "pump": {
      "controller": "pump_lights",
      "pin": 2,
      "editor": "cycle"
    }
  },
  "cameras": {
    "cam0": {}
  }
}
```

`/` is driven by configured controllers and devices. Pico reports only provide live state for configured pins; extra reported pins are ignored.
```

- [x] **Step 2: Run the focused verification set before the final commit**

Run: `/home/hugo/.local/bin/uv run python -m unittest tests.test_hardware_config tests.test_config_api tests.test_timer_schedule tests.test_pages -v`

Expected: PASS across all four test modules.

- [x] **Step 3: Commit**

```bash
git add plamp_web/README.md docs/superpowers/plans/2026-04-14-config-model-simplification.md
git commit -m "Document simplified config-driven runtime"
```
