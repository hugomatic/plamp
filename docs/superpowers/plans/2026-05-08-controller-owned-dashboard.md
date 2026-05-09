# Controller-Owned Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the finished controller-owned config and dashboard design from `docs/superpowers/specs/2026-05-08-controller-owned-timers-agri-dashboard-design.md`.

**Architecture:** `config.json` becomes the authority for user-editable intent: `appearance.host_color`, controller-owned devices, per-device timer settings, and top-level cameras with optional timeline metadata. Runtime telemetry, health, uptime, hostname, snapshots, and capture lists stay runtime-only and are joined into the dashboard by the server/page layer.

**Tech Stack:** Python 3.11, FastAPI, server-rendered HTML, vanilla JavaScript, stdlib `unittest`, existing JSON config helpers.

---

## File Structure

- Modify `plamp_web/hardware_config.py`: validate the new canonical config shape, migrate old flat `devices`, and preserve timer editor modes.
- Modify `plamp_web/timer_schedule.py`: read timer metadata from controller-owned devices while preserving legacy compatibility during migration.
- Modify `plamp_web/server.py`: load migrated config, expose controller-owned payloads, and keep full-controller apply semantics.
- Modify `plamp_web/pages.py`: render the hostname chip, controller cards, edit panel, timer lanes, and per-camera snapshot sections.
- Modify `tests/test_hardware_config.py`: cover new config validation and migration.
- Modify `tests/test_timer_schedule.py`: cover controller-owned device metadata and editor modes.
- Modify `tests/test_config_api.py`: cover controller payload/apply behavior.
- Modify `tests/test_pages.py`: cover dashboard structure and edit-only controls.
- Modify camera tests only if backend helpers are added for per-camera timeline payloads.

### Task 1: Canonical config and migration

**Files:**
- Modify: `tests/test_hardware_config.py`
- Modify: `plamp_web/hardware_config.py`

- [ ] **Step 1: Write failing config tests**

Add tests for the new shape and old-shape migration:

```python
def test_config_view_accepts_controller_owned_devices(self):
    config = {
        "appearance": {"host_color": "#204b33"},
        "controllers": {
            "pump_n_lights": {
                "type": "pico_scheduler",
                "pico_serial": "e66038b71387a039",
                "report_every": 10,
                "devices": {
                    "pump": {
                        "display_order": 0,
                        "pin": 3,
                        "type": "gpio",
                        "icon": "pump",
                        "visibility": "visible",
                        "programming": "enabled",
                        "timer": {
                            "editor": "cycle",
                            "schedule": {"mode": "cycle", "on_seconds": 90, "off_seconds": 810, "start_at_seconds": 0},
                        },
                    }
                },
            }
        },
        "cameras": {},
    }
    self.assertEqual(config_view(config)["appearance"]["host_color"], "#204b33")
    self.assertEqual(config_view(config)["controllers"]["pump_n_lights"]["devices"]["pump"]["timer"]["editor"], "cycle")

def test_config_view_migrates_flat_devices_into_controllers(self):
    config = {
        "controllers": {"pump_n_lights": {"type": "pico_scheduler", "report_every": 10}},
        "devices": {"lights": {"controller": "pump_n_lights", "pin": 2, "type": "gpio", "editor": "clock_window"}},
        "cameras": {},
    }
    migrated = config_view(config)
    device = migrated["controllers"]["pump_n_lights"]["devices"]["lights"]
    self.assertEqual(device["pin"], 2)
    self.assertEqual(device["timer"]["editor"], "clock_window")
    self.assertNotIn("devices", migrated)
```

- [ ] **Step 2: Run the tests to verify failure**

Run: `/home/hugo/.local/bin/uv run python -m unittest tests.test_hardware_config -v`

Expected: fail because `appearance` and controller-owned devices are not yet accepted.

- [ ] **Step 3: Implement config validation and migration**

Update `config_view()` so it accepts the canonical shape and migrates the old flat shape:

```python
def config_view(config):
    config = _as_mapping(config, "config")
    controllers = validate_controllers(config.get("controllers", {}))
    cameras = validate_cameras(config.get("cameras", {}))
    appearance = validate_appearance(config.get("appearance", {}))
    if "devices" in config:
        controllers = migrate_flat_devices_into_controllers(controllers, config.get("devices", {}))
    return {"appearance": appearance, "controllers": controllers, "cameras": cameras}
```

Use `icon: "other"` for missing/unknown icons. Move old `editor: "disabled"` to `programming: "disabled"` and `visibility: "visible"`. Move old `editor: "hidden"` to `programming: "disabled"` and `visibility: "hidden"`.

- [ ] **Step 4: Run the tests to verify pass**

Run: `/home/hugo/.local/bin/uv run python -m unittest tests.test_hardware_config -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add plamp_web/hardware_config.py tests/test_hardware_config.py
git commit -m "Add controller-owned config migration"
```

### Task 2: Timer metadata from controller-owned devices

**Files:**
- Modify: `tests/test_timer_schedule.py`
- Modify: `plamp_web/timer_schedule.py`

- [ ] **Step 1: Write failing timer metadata tests**

Add a test that uses the new controller-owned shape:

```python
def test_channel_metadata_reads_controller_owned_devices(self):
    config = {
        "controllers": {
            "pump_n_lights": {
                "devices": {
                    "pump": {
                        "display_order": 0,
                        "pin": 3,
                        "type": "gpio",
                        "icon": "pump",
                        "visibility": "visible",
                        "programming": "enabled",
                        "timer": {"editor": "cycle", "schedule": {"mode": "cycle", "on_seconds": 90, "off_seconds": 810}},
                    }
                }
            }
        },
        "cameras": {},
    }
    self.assertEqual(
        channel_metadata_for_role("pump_n_lights", config, {"devices": []}),
        [{"role": "pump_n_lights", "id": "pump", "name": "pump", "pin": 3, "type": "gpio", "default_editor": "cycle"}],
    )
```

- [ ] **Step 2: Run the tests to verify failure**

Run: `/home/hugo/.local/bin/uv run python -m unittest tests.test_timer_schedule -v`

Expected: fail because `channel_metadata_for_role()` still reads flat `config["devices"]`.

- [ ] **Step 3: Implement controller-owned metadata lookup**

Read devices from `config["controllers"][role]["devices"]` first. Keep flat lookup only as migration compatibility:

```python
def devices_for_role(role: str, config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    controllers = config.get("controllers", {})
    controller = controllers.get(role, {}) if isinstance(controllers, dict) else {}
    devices = controller.get("devices", {}) if isinstance(controller, dict) else {}
    if isinstance(devices, dict) and devices:
        return devices
    return {
        device_id: device
        for device_id, device in config.get("devices", {}).items()
        if isinstance(device, dict) and device.get("controller") == role
    }
```

- [ ] **Step 4: Run the tests to verify pass**

Run: `/home/hugo/.local/bin/uv run python -m unittest tests.test_timer_schedule -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add plamp_web/timer_schedule.py tests/test_timer_schedule.py
git commit -m "Read timer metadata from controller devices"
```

### Task 3: Controller payload and full apply

**Files:**
- Modify: `tests/test_config_api.py`
- Modify: `plamp_web/server.py`

- [ ] **Step 1: Write failing controller payload tests**

Add tests that assert the controller payload includes config context and keeps apply as full-state:

```python
def test_controller_payload_includes_owned_devices(client):
    response = client.get("/api/controllers/pump_n_lights")
    self.assertEqual(response.status_code, 200)
    payload = response.json()
    self.assertEqual(payload["controller"], "pump_n_lights")
    self.assertIn("devices", payload)

def test_controller_put_applies_full_controller_state(client):
    payload = {"controller": "pump_n_lights", "report_every": 10, "devices": []}
    response = client.put("/api/controllers/pump_n_lights", json=payload)
    self.assertEqual(response.status_code, 200)
    self.assertTrue(response.json()["success"])
```

- [ ] **Step 2: Run the tests to verify failure**

Run: `/home/hugo/.local/bin/uv run python -m unittest tests.test_config_api -v`

Expected: fail where the payload does not yet include controller-owned config context.

- [ ] **Step 3: Implement payload join**

Join controller config with telemetry in `controller_state_payload()` without persisting telemetry:

```python
def controller_state_payload(controller: str) -> dict[str, Any]:
    config_controller = controllers_index()[controller]
    payload = state_for_role(controller)
    payload["controller"] = controller
    payload["report_every"] = config_controller.get("report_every", payload.get("report_every", 10))
    payload["configured_devices"] = config_controller.get("devices", {})
    return payload
```

- [ ] **Step 4: Run the tests to verify pass**

Run: `/home/hugo/.local/bin/uv run python -m unittest tests.test_config_api -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add plamp_web/server.py tests/test_config_api.py
git commit -m "Expose controller-owned payload context"
```

### Task 4: Dashboard layout and edit panel

**Files:**
- Modify: `tests/test_pages.py`
- Modify: `plamp_web/pages.py`

- [ ] **Step 1: Write failing page tests**

Assert the page exposes the agreed structure:

```python
def test_timer_dashboard_renders_controller_owned_layout(self):
    html = render_timer_dashboard_page(
        roles=["pump_n_lights"],
        time_format="24h",
        channels_by_role={},
        host_seconds_since_midnight=12 * 3600,
        camera_ids=["rpicam_cam0"],
        hostname="tower",
    )
    self.assertIn("hostname-chip", html)
    self.assertIn("controller-card", html)
    self.assertIn("Apply all changes to Controller", html)
    self.assertIn("edit-panel", html)
    self.assertIn("camera-section", html)
```

- [ ] **Step 2: Run the tests to verify failure**

Run: `/home/hugo/.local/bin/uv run python -m unittest tests.test_pages -v`

Expected: fail because the old dashboard does not have these classes.

- [ ] **Step 3: Implement the dashboard structure**

Render:

- hostname chip using OS hostname and `appearance.host_color`
- top-level health light
- controller card list
- edit panel above telemetry and hidden by default
- timer lanes ordered by device `display_order`
- camera sections with snapshot preview, lane, delay, and capture list

- [ ] **Step 4: Run the tests to verify pass**

Run: `/home/hugo/.local/bin/uv run python -m unittest tests.test_pages -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add plamp_web/pages.py tests/test_pages.py
git commit -m "Render controller-owned dashboard"
```

### Task 5: Final verification

**Files:**
- Modify only files touched by earlier tasks if verification exposes issues.

- [ ] **Step 1: Run focused suites**

Run: `/home/hugo/.local/bin/uv run python -m unittest tests.test_hardware_config tests.test_timer_schedule tests.test_config_api tests.test_pages -v`

Expected: PASS.

- [ ] **Step 2: Run full suite**

Run: `/home/hugo/.local/bin/uv run python -m unittest discover tests`

Expected: PASS.

- [ ] **Step 3: Compile touched modules**

Run: `python3 -m py_compile plamp_web/hardware_config.py plamp_web/timer_schedule.py plamp_web/server.py plamp_web/pages.py`

Expected: no syntax errors.
