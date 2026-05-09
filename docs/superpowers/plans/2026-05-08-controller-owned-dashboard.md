# Controller-Owned Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move Plamp to a controller-owned config and UI model with explicit device icons, telemetry/telecommand separation, a single edit/apply flow, and a controller dashboard that matches the agreed agri-style layout.

**Architecture:** Treat `plamp_web/hardware_config.py` as the schema gate for the new controller-owned config, `plamp_web/server.py` as the source of controller telemetry and apply payloads, and `plamp_web/pages.py` as the rendering layer for the new dashboard and edit panel. Preserve existing values through a migration path, but make the new controller object the canonical runtime shape so the UI can render controllers, nested devices, controller colors, explicit device ordering, timer editor modes, timelines, and camera snapshot lanes without guessing from flat records.

**Tech Stack:** Python 3.11, FastAPI, server-rendered HTML, vanilla browser JavaScript, stdlib `unittest`, existing JSON config helpers.

---

## File Structure

- Modify `plamp_web/hardware_config.py`: extend validation to accept controller-owned `devices`, timer rows, explicit `icon` fields, explicit `display_order`, explicit timer `editor` modes, controller-level `background_color`, and controller-level `report_every` while keeping the existing id and type rules.
- Modify `plamp_web/server.py`: reshape controller state payloads, keep telemetry separate from telecommand, preserve full-controller apply behavior, and add the controller-facing health data needed by the dashboard.
- Modify `plamp_web/pages.py`: replace the current flat timer dashboard with the controller list, hostname chip, top-level health light, edit-only apply panel, 24h timelines, and camera lane.
- Modify `tests/test_hardware_config.py`: cover controller-owned config validation and migration behavior.
- Modify `tests/test_config_api.py`: cover controller payload shape, apply semantics, and the warning/edit mode behavior exposed by the API.
- Modify `tests/test_pages.py`: cover the new dashboard structure, hostname chip, edit panel placement, timeline layout, and explicit icon selection.
- Modify `tests/test_timer_schedule.py`: cover the 24h lane semantics, dotted pump pattern, and centered-now timeline assumptions if helper logic changes.
- Modify `tests/test_camera_api.py` and `tests/test_camera_capture.py` only if camera lane or camera capture alignment needs backend support.

### Task 1: Add controller-owned config validation

**Files:**
- Modify: `tests/test_hardware_config.py`
- Modify: `plamp_web/hardware_config.py`

- [ ] **Step 1: Write the failing tests**

Add tests that define the new schema shape and the migration boundary:

```python
def test_validate_controllers_accepts_controller_owned_devices_and_report_every():
    controllers = {
        "pump_n_lights": {
            "type": "pico_scheduler",
            "pico_serial": "E661TEST",
            "label": "Pump and lights",
            "background_color": "#204b33",
            "report_every": 10,
            "devices": {
                "pumpON": {"display_order": 0, "pin": 3, "type": "gpio", "icon": "pump", "editor": "cycle"},
                "lightsON": {"display_order": 1, "pin": 2, "type": "gpio", "icon": "light", "editor": "clock_window"},
            },
        }
    }
    assert validate_controllers(controllers)["pump_n_lights"]["report_every"] == 10
    assert validate_controllers(controllers)["pump_n_lights"]["background_color"] == "#204b33"
    assert validate_controllers(controllers)["pump_n_lights"]["devices"]["pumpON"]["editor"] == "cycle"
    assert validate_controllers(controllers)["pump_n_lights"]["devices"]["lightsON"]["editor"] == "clock_window"

def test_validate_devices_rejects_implicit_icon_mapping():
    with pytest.raises(ValueError):
        validate_devices({"lights": {"controller": "pump_n_lights", "pin": 2, "editor": "cycle"}}, {"pump_n_lights": {}})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `/home/hugo/.local/bin/uv run python -m unittest tests.test_hardware_config -v`

Expected: fail because the current validators still understand only the flat device/controller model.

- [ ] **Step 3: Implement the new config shape**

Update `validate_controllers()` so it preserves `type`, `pico_serial`, `label`, `background_color`, `report_every`, and the controller-owned `devices` container. Keep device `icon`, `display_order`, and `editor` explicit and reject any attempt to infer them from ids or normalize `cycle` and `clock_window` into one generic mode.

```python
def validate_controllers(value):
    controllers = _as_mapping(value, "controllers")
    normalized = {}
    for controller_id, controller_value in controllers.items():
        controller_value = _as_mapping(controller_value, f"controller {controller_id}")
        normalized[controller_id] = {
            "type": controller_value.get("type", _DEFAULT_CONTROLLER_TYPE),
            "pico_serial": controller_value.get("pico_serial"),
            "label": controller_value.get("label"),
            "background_color": controller_value.get("background_color"),
            "report_every": controller_value.get("report_every", _DEFAULT_REPORT_EVERY),
            "devices": controller_value.get("devices", {}),
        }
    return normalized

def validate_devices(value, controllers):
    devices = _as_mapping(value, "devices")
    normalized = {}
    for device_id, device_value in devices.items():
        device_value = _as_mapping(device_value, f"device {device_id}")
        normalized[device_id] = {
            "controller": device_value.get("controller"),
            "display_order": device_value.get("display_order"),
            "pin": device_value.get("pin"),
            "type": device_value.get("type", "gpio"),
            "editor": device_value.get("editor", "cycle"),
            "icon": device_value.get("icon"),
            "label": device_value.get("label"),
        }
    return normalized
```

If the existing flat form is still accepted during migration, keep that behavior explicit in the validator. The canonical output should still be controller-owned.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `/home/hugo/.local/bin/uv run python -m unittest tests.test_hardware_config -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_hardware_config.py plamp_web/hardware_config.py
git commit -m "Add controller-owned config validation"
```

### Task 2: Reshape controller telemetry and apply payloads

**Files:**
- Modify: `plamp_web/server.py`
- Modify: `tests/test_config_api.py`

- [ ] **Step 1: Write the failing tests**

Add tests that pin the controller payload shape and the health signal:

```python
def test_get_controller_includes_controller_owned_devices_and_report_every(client):
    response = client.get("/api/controllers/pump_n_lights")
    assert response.status_code == 200
    payload = response.json()
    assert payload["controller"] == "pump_n_lights"
    assert payload["report_every"] == 10
    assert "devices" in payload

def test_put_controller_replaces_entire_controller_state(client):
    payload = {
        "controller": "pump_n_lights",
        "report_every": 10,
        "devices": {"pumpON": {"pin": 3, "type": "gpio", "icon": "pump", "editor": "cycle"}},
    }
    response = client.put("/api/controllers/pump_n_lights", json=payload)
    assert response.status_code == 200
    assert response.json()["success"] is True
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `/home/hugo/.local/bin/uv run python -m unittest tests.test_config_api -v`

Expected: fail because the current payload still reflects the old timer-centric state shape.

- [ ] **Step 3: Update the controller payload path**

Refactor `controller_state_payload()` and the code it uses so the returned payload is the controller-owned shape the UI expects. Keep the current full-state apply route, but make the contract explicit that the controller payload is the unit of sync.

```python
def controller_state_payload(controller: str) -> dict[str, Any]:
    payload = state_for_role(controller)
    payload["controller"] = controller
    payload["report_every"] = payload.get("report_every", 10)
    payload["devices"] = payload.get("devices", {})
    return payload
```

Make the health field derive from freshness of the periodic message rather than from any unrelated dashboard state.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `/home/hugo/.local/bin/uv run python -m unittest tests.test_config_api -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add plamp_web/server.py tests/test_config_api.py
git commit -m "Reshape controller telemetry payloads"
```

### Task 3: Rebuild the dashboard around controller cards and edit mode

**Files:**
- Modify: `plamp_web/pages.py`
- Modify: `tests/test_pages.py`

- [ ] **Step 1: Write the failing UI tests**

Add page tests that assert the controller list, hostname chip, edit-only apply panel, explicit icon picker, and timeline/camera lanes:

```python
def test_timer_dashboard_page_renders_controller_list_and_hostname_chip():
    html = render_timer_dashboard_page(
        roles=["pump_n_lights", "sprout"],
        time_format="24h",
        channels_by_role={},
        host_seconds_since_midnight=12345,
        camera_ids=["cam0"],
        hostname="tower",
    )
    assert "tower" in html
    assert "Apply all changes to Controller" in html
    assert "report every N seconds" in html
    assert "hostname-chip" in html
    assert "controller-card" in html
    assert "background-color" in html or "controller-color" in html
    assert "display_order" in html or "device-order" in html
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `/home/hugo/.local/bin/uv run python -m unittest tests.test_pages -v`

Expected: fail because the current dashboard is still the old flat timer page.

- [ ] **Step 3: Implement the new dashboard structure**

Rewrite `render_timer_dashboard_page()` so it renders:

```python
hostname_chip = f'<span class="hostname-chip">{html.escape(hostname)}</span>'
controller_card = (
    '<section class="controller-card">'
    '<header><h2>pump_n_lights</h2><span class="controller-status">OK</span></header>'
    '<div class="edit-panel" hidden><button>Apply all changes to Controller</button></div>'
    '<div class="telemetry"><div class="uptime">uptime 12h</div></div>'
    '<div class="timelines"><div class="timer-lane"></div><div class="camera-lane"></div></div>'
    '</section>'
)
```

Behavior to preserve:

- the hostname chip shows `tower`, not `tower.local`
- the edit panel appears above telemetry and collapses away when not editing
- the big `Apply all changes to Controller` button appears only in edit mode
- `Updating timer resets all` appears only inside edit mode
- device icons are user-selected in the edit UI, not auto-mapped from ids
- controller background color is user-selected in the edit UI and persisted in config
- device order is user-selected in the edit UI and persisted in config
- timer editor mode is user-selected in the edit UI and preserves `cycle`, `clock_window`, and later `events`
- the 24h timeline uses a centered-now model and can zoom without moving the now marker

- [ ] **Step 4: Run the tests to verify they pass**

Run: `/home/hugo/.local/bin/uv run python -m unittest tests.test_pages -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add plamp_web/pages.py tests/test_pages.py
git commit -m "Rebuild controller dashboard UI"
```

### Task 4: Add camera lane alignment and sequence behavior coverage

**Files:**
- Modify: `tests/test_timer_schedule.py`
- Modify: `tests/test_camera_api.py`
- Modify: `tests/test_camera_capture.py`
- Modify: `plamp_web/pages.py` only if the camera lane needs extra markup hooks

- [ ] **Step 1: Write the failing tests**
 
Camera behavior should reflect snapshots and delay rather than a generic on/off state:

```python
def test_camera_lane_renders_snapshot_and_delay_metadata():
    payload = lane_for_camera_capture("cam0", 45000)
    assert payload["camera_id"] == "cam0"
    assert payload["kind"] == "camera_capture"
    assert "delay_seconds" in payload
    assert "snapshot_url" in payload or "snapshot_path" in payload
```

Cover the agreed time-axis behavior and camera alignment:

```python
def test_centered_now_timeline_keeps_now_marker_stable():
    start, end = centered_now_window(12 * 3600, 120)
    assert end - start == 120 * 60
    assert start <= 12 * 3600 <= end

def test_camera_lane_uses_same_time_scale_as_controller_lanes():
    lane = lane_for_camera_capture("cam0", 45000)
    assert lane["camera_id"] == "cam0"
    assert lane["kind"] == "camera_capture"
    assert "delay_seconds" in lane
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `/home/hugo/.local/bin/uv run python -m unittest tests.test_timer_schedule tests.test_camera_api tests.test_camera_capture -v`

Expected: fail where the current UI and helpers do not yet expose camera-lane alignment or centered-now behavior.

- [ ] **Step 3: Implement the lane helpers and camera hooks**

Add the smallest helper functions needed for:

```python
def centered_now_window(now_seconds: int, zoom_minutes: int) -> tuple[int, int]:
    span = max(15 * 60, zoom_minutes * 60)
    start = max(0, now_seconds - span // 2)
    end = min(86400, start + span)
    if end - start < span:
        start = max(0, end - span)
    return start, end

def lane_for_camera_capture(camera_id: str, capture_time: int) -> dict[str, Any]:
    return {
        "camera_id": camera_id,
        "capture_time": capture_time,
        "kind": "camera_capture",
        "display_order": 0,
        "delay_seconds": 0,
        "snapshot_url": "",
    }
```

Keep these helpers narrow. They should support the UI without inventing a new calendar model.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `/home/hugo/.local/bin/uv run python -m unittest tests.test_timer_schedule tests.test_camera_api tests.test_camera_capture -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add plamp_web/pages.py tests/test_timer_schedule.py tests/test_camera_api.py tests/test_camera_capture.py
git commit -m "Add centered timeline and camera lane coverage"
```

### Task 5: Final integration and regression pass

**Files:**
- Modify: any files touched above only for polish or test fixes

- [ ] **Step 1: Run the full test suite**

Run: `/home/hugo/.local/bin/uv run python -m unittest discover tests`

Expected: all tests pass.

- [ ] **Step 2: Run a focused compile check**

Run: `python3 -m py_compile plamp_web/hardware_config.py plamp_web/server.py plamp_web/pages.py`

Expected: no syntax errors.

- [ ] **Step 3: Inspect the rendered page once**

Open the dashboard locally and verify the following are visible in the final UI:

```text
hostname chip
controller list
explicit icon selector
centered-now timeline
camera lane
edit-only warning and apply button
```

- [ ] **Step 4: Commit any final polish**

```bash
git add plamp_web/hardware_config.py plamp_web/server.py plamp_web/pages.py tests/test_hardware_config.py tests/test_config_api.py tests/test_pages.py tests/test_timer_schedule.py tests/test_camera_api.py tests/test_camera_capture.py
git commit -m "Finalize controller-owned dashboard"
```
