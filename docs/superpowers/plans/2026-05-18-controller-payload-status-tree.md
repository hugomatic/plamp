# Controller Payload And Status Tree Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current controller config shape with `payload/settings/telemetry`, move detected hardware to `/api/system`, and make `/api/status` the only live-state endpoint.

**Architecture:** Keep `plamp_web/hardware_config.py` as the source of truth for persisted controller validation and migration. Reuse the existing Pico scheduler state shape as the controller `payload`, keep semantic device meaning in `settings.devices`, and expose raw live reports under controller `telemetry` only in `/api/status`. Split API envelopes in `plamp_web/server.py`, then update page/CLI/docs consumers to use the new contracts.

**Tech Stack:** Python, FastAPI, unittest, static HTML/JS renderers, existing Pico scheduler JSON payloads.

---

## File Map

- `plamp_web/hardware_config.py`
  Persisted config validation, normalized controller shape, scheduler device joins, migration from the old nested device model.
- `plamp_web/server.py`
  `/api/config`, new `/api/system`, new `/api/status`, removed `/runtime`, controller payload/status assembly.
- `plamp_web/timer_schedule.py`
  Join semantic device ids from `settings.devices` to firmware payload devices by `pin`.
- `plamp_web/pages.py`
  Config/settings page serialization and browser-side editing of `payload` versus `settings.devices`.
- `plamp_cli/main.py`
  Config command expectations for `/api/config`.
- `tests/test_config_api.py`
  API contracts, migration, payload generation, status telemetry.
- `tests/test_pages.py`
  Page rendering and config editor behavior with the new controller shape.
- `tests/test_timer_schedule.py`
  Pin-based semantic joins and editor round-trip behavior.
- `tests/test_plamp_cli.py`
  CLI output against the new `/api/config` response.
- `plamp_web/README.md`, `plamp_cli/README.md`
  Public examples and endpoint naming.

### Task 1: Move Persisted Controllers To `payload/settings`

**Files:**
- Modify: `plamp_web/hardware_config.py`
- Test: `tests/test_config_api.py`

- [ ] **Step 1: Write failing config-shape tests**

Add tests that assert normalized scheduler controllers use:

```python
{
    "type": "pico_scheduler",
    "payload": {
        "pico_serial": "abc",
        "report_every": 10,
        "devices": [
            {"pin": 3, "type": "gpio", "pattern": [{"val": 1, "dur": 90}, {"val": 0, "dur": 810}]}
        ],
    },
    "settings": {
        "devices": {
            "pump": {
                "pin": 3,
                "label": "Pump",
                "icon": "pump",
                "display_order": 0,
                "visibility": "visible",
                "programming": "enabled",
                "editor": {
                    "kind": "cycle",
                    "on_seconds": 90,
                    "off_seconds": 810,
                    "start_at_seconds": 0,
                },
            }
        }
    },
}
```

Also add a migration test that feeds the current `config/settings/devices` shape and expects the normalized `payload/settings` shape above.

- [ ] **Step 2: Run the targeted tests and confirm failure**

Run:

```bash
python3 -m unittest tests.test_config_api.ConfigApiTests.test_scheduler_controller_normalizes_to_payload_and_settings tests.test_config_api.ConfigApiTests.test_legacy_scheduler_controller_migrates_to_payload_and_settings -v
```

Expected: both tests fail because controllers still expose `config`, `settings.report_every`, and sibling `devices`.

- [ ] **Step 3: Implement the new validator shape**

In `plamp_web/hardware_config.py`:

```python
def validate_controllers(value):
    ...
    extra_keys = set(controller_value) - {"type", "payload", "settings", "config", "devices"}
    ...
    payload_input = _as_mapping(controller_value.get("payload", {}), ...)
    legacy_config = _as_mapping(controller_value.get("config", {}), ...)
    legacy_settings = _as_mapping(controller_value.get("settings", {}), ...)
    semantic_devices_input = settings.get("devices", controller_value.get("devices", {}))
```

Normalize Pico scheduler controllers so:

```python
controller = {
    "type": "pico_scheduler",
    "payload": {
        "report_every": ...,
        "devices": compiled_payload_devices,
    },
    "settings": {"devices": semantic_devices},
}
```

Preserve old values while migrating:

- `config.pico_serial -> payload.pico_serial`
- `settings.report_every -> payload.report_every`
- old device `config.pin/output_type` plus `settings.schedule` compile into `payload.devices`
- old device human values move into `settings.devices.<id>`

- [ ] **Step 4: Update scheduler lookup helpers**

Change:

```python
def runtime_controller_serials(config):
    return {
        controller_id: controller_value["payload"]["pico_serial"]
        ...
    }

def scheduler_devices_for_controller(config, controller_id: str) -> dict:
    controller = config_view(config)["controllers"].get(controller_id, {})
    return controller.get("settings", {}).get("devices", {})
```

- [ ] **Step 5: Re-run targeted tests**

Run:

```bash
python3 -m unittest tests.test_config_api.ConfigApiTests.test_scheduler_controller_normalizes_to_payload_and_settings tests.test_config_api.ConfigApiTests.test_legacy_scheduler_controller_migrates_to_payload_and_settings -v
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add plamp_web/hardware_config.py tests/test_config_api.py
git commit -m "Move controller config to payload and settings"
```

### Task 2: Split Config, System, And Status APIs

**Files:**
- Modify: `plamp_web/server.py`
- Test: `tests/test_config_api.py`

- [ ] **Step 1: Write failing API tests**

Add tests asserting:

```python
GET /api/config  -> {"config": ...}  # no "detected"
GET /api/system  -> {"detected": {"picos": [...], "cameras": [...]}, ...host/system fields...}
GET /api/status  -> {"config": ..., "controllers": {"pump_n_lights": {"telemetry": ...}}, ...}
GET /runtime     -> 404
```

For telemetry, patch the live controller report and assert the raw report is embedded unchanged at:

```python
status["controllers"]["pump_n_lights"]["telemetry"]
```

- [ ] **Step 2: Run the targeted tests and confirm failure**

Run:

```bash
python3 -m unittest tests.test_config_api.ConfigApiTests.test_config_response_excludes_detected tests.test_config_api.ConfigApiTests.test_system_response_contains_detected_hardware tests.test_config_api.ConfigApiTests.test_status_response_contains_controller_telemetry tests.test_config_api.ConfigApiTests.test_runtime_route_is_removed -v
```

Expected: fail because `/api/system` and `/api/status` do not exist, `/api/config` still includes `detected`, and `/runtime` still exists.

- [ ] **Step 3: Split the response builders**

In `plamp_web/server.py`, replace `config_response()` with:

```python
def config_response() -> dict[str, Any]:
    return {"config": load_config()}

def system_response() -> dict[str, Any]:
    return {
        "detected": {
            "picos": enumerate_picos(),
            "cameras": normalized_detected_cameras(hardware_inventory.detect_rpicam_cameras()),
        },
        ...
    }

def status_response() -> dict[str, Any]:
    config = load_config()
    return {
        "config": config,
        "controllers": controller_status_tree(config),
        ...
    }
```

Move host, software, storage, monitor, firmware, and camera-worker facts from `settings_summary()` into `system_response()` or `status_response()` according to whether they are static/system facts or live state.

- [ ] **Step 4: Add the new routes and remove `/runtime`**

Add:

```python
@app.get("/api/system")
def get_system() -> dict[str, Any]:
    return system_response()

@app.get("/api/status")
def get_status() -> dict[str, Any]:
    return status_response()
```

Delete:

```python
@app.get("/runtime")
def get_runtime() -> dict[str, Any]:
    ...
```

- [ ] **Step 5: Add controller telemetry assembly**

Implement a helper that reads the current controller report without decomposing it:

```python
def controller_status_tree(config: dict[str, Any]) -> dict[str, Any]:
    controllers = {}
    for controller_id, controller in config.get("controllers", {}).items():
        item = dict(controller)
        item["telemetry"] = latest_controller_telemetry(controller_id)
        controllers[controller_id] = item
    return controllers
```

For `pico_scheduler`, use the current latest report/state helper already used by live monitor code. Keep the raw report shape.

- [ ] **Step 6: Re-run targeted tests**

Run the same command from Step 2.

Expected: pass.

- [ ] **Step 7: Commit**

```bash
git add plamp_web/server.py tests/test_config_api.py
git commit -m "Split config system and status APIs"
```

### Task 3: Join Semantic Devices To Payload Devices By Pin

**Files:**
- Modify: `plamp_web/timer_schedule.py`
- Modify: `plamp_web/server.py`
- Test: `tests/test_timer_schedule.py`
- Test: `tests/test_config_api.py`

- [ ] **Step 1: Write failing join tests**

Add tests proving that:

- `settings.devices.pump.pin == 3` joins to `payload.devices[*].pin == 3`
- payload devices do not need `id`
- posting a schedule update for semantic device id `pump` rewrites the matching payload device by pin
- `controller_state_payload()` reads `report_every` from `payload.report_every`

- [ ] **Step 2: Run the targeted tests and confirm failure**

Run:

```bash
python3 -m unittest tests.test_timer_schedule.TimerScheduleTests.test_channel_metadata_joins_settings_devices_to_payload_by_pin tests.test_timer_schedule.TimerScheduleTests.test_patch_channel_schedule_updates_payload_device_by_pin tests.test_config_api.ConfigApiTests.test_controller_state_payload_uses_payload_report_every -v
```

Expected: fail because helpers still expect sibling `devices` and `settings.report_every`.

- [ ] **Step 3: Update metadata and patching helpers**

In `plamp_web/timer_schedule.py`, build channel metadata from:

```python
semantic_devices = scheduler_devices_for_controller(config, role)
payload_devices = state.get("devices", [])
```

Match each semantic device to firmware state by `pin`, not by embedded firmware `id`.

- [ ] **Step 4: Update controller report cadence lookup**

In `plamp_web/server.py`, change:

```python
timer_role(controller).get("settings", {}).get("report_every", 10)
```

to:

```python
timer_role(controller).get("payload", {}).get("report_every", 10)
```

- [ ] **Step 5: Re-run targeted tests**

Run the same command from Step 2.

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add plamp_web/timer_schedule.py plamp_web/server.py tests/test_timer_schedule.py tests/test_config_api.py
git commit -m "Join scheduler settings to payload by pin"
```

### Task 4: Update Config And Settings Pages

**Files:**
- Modify: `plamp_web/pages.py`
- Test: `tests/test_pages.py`

- [ ] **Step 1: Write failing page tests**

Add tests asserting rendered config/editor JS:

- reads `controller.payload.pico_serial`
- reads/writes `controller.payload.report_every`
- stores semantic device rows under `controller.settings.devices`
- does not emit `controller.devices`
- settings page accepts separate config/system/status structures

- [ ] **Step 2: Run the targeted page tests**

Run:

```bash
python3 -m unittest tests.test_pages.PagesTests.test_config_page_serializes_payload_and_settings_devices tests.test_pages.PagesTests.test_config_page_writes_report_every_into_payload tests.test_pages.PagesTests.test_settings_page_reads_split_system_and_status_inputs -v
```

Expected: fail because page rendering still assumes `config/settings/devices`.

- [ ] **Step 3: Update browser-side config serialization**

In `plamp_web/pages.py`, update generated controller objects from:

```javascript
{type: "pico_scheduler", config: {...}, settings: {report_every: 10}, devices: {}}
```

to:

```javascript
{type: "pico_scheduler", payload: {pico_serial: picoSerial, report_every: 10, devices: []}, settings: {devices: {}}}
```

Move human device form output under `settings.devices`.

- [ ] **Step 4: Update settings-page inputs**

Have page renderers accept the split endpoint structure:

- persisted tree from config
- detected hardware from system
- telemetry/status from status

Keep the user-visible UI behavior the same.

- [ ] **Step 5: Re-run targeted tests**

Run the same command from Step 2.

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add plamp_web/pages.py tests/test_pages.py
git commit -m "Update pages for payload settings controller shape"
```

### Task 5: Update CLI, API Test Page, And Docs

**Files:**
- Modify: `plamp_cli/main.py`
- Modify: `plamp_cli/README.md`
- Modify: `plamp_web/README.md`
- Modify: `plamp_web/pages.py`
- Test: `tests/test_plamp_cli.py`
- Test: `tests/test_pages.py`

- [ ] **Step 1: Write failing CLI/docs surface tests**

Add assertions that:

- CLI config output expects `{"config": ...}` only
- API test page links/examples mention `/api/config`, `/api/system`, `/api/status`
- docs examples use `payload/settings.devices`
- docs no longer mention `/runtime`

- [ ] **Step 2: Run targeted tests**

Run:

```bash
python3 -m unittest tests.test_plamp_cli.PlampCliTests.test_config_get_prints_config_only tests.test_pages.PagesTests.test_api_test_page_mentions_config_system_and_status -v
```

Expected: fail because old response/docs remain.

- [ ] **Step 3: Update CLI response handling**

Keep the CLI fetching `/api/config`, but update test fixtures and any assumptions about `detected` being present in that response.

- [ ] **Step 4: Update docs and API test copy**

Document:

```text
/api/config
/api/system
/api/status
```

Replace controller examples with:

```json
{
  "payload": {"pico_serial": "...", "report_every": 10, "devices": []},
  "settings": {"devices": {}}
}
```

Remove `/runtime` mentions.

- [ ] **Step 5: Re-run targeted tests**

Run the same command from Step 2.

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add plamp_cli/main.py plamp_cli/README.md plamp_web/README.md plamp_web/pages.py tests/test_plamp_cli.py tests/test_pages.py
git commit -m "Document payload status API contracts"
```

### Task 6: Full Regression And Live Migration Check

**Files:**
- Modify only if regressions are found.

- [ ] **Step 1: Run the full Python test suite**

Run:

```bash
python3 -m unittest
```

Expected: all tests pass.

- [ ] **Step 2: Inspect persisted config migration manually**

Run:

```bash
python3 -m json.tool data/config.json
```

Expected controller shape:

```json
"pump_n_lights": {
  "type": "pico_scheduler",
  "payload": {
    "pico_serial": "...",
    "report_every": 10,
    "devices": [...]
  },
  "settings": {
    "devices": {...}
  }
}
```

- [ ] **Step 3: Verify the running API manually**

Run:

```bash
curl -sS http://127.0.0.1:8000/api/config | python3 -m json.tool
curl -sS http://127.0.0.1:8000/api/system | python3 -m json.tool
curl -sS http://127.0.0.1:8000/api/status | python3 -m json.tool
curl -i http://127.0.0.1:8000/runtime
```

Expected:

- config response has no `detected`
- system response has detected hardware
- status response has controller telemetry
- `/runtime` returns `404`

- [ ] **Step 4: Commit any final fixes**

```bash
git add <changed files>
git commit -m "Finish controller payload status migration"
```

## Self-Review

- Spec coverage:
  - `/api/config`, `/api/system`, `/api/status`, and removed `/runtime`: Task 2
  - `payload/settings/telemetry` controller shape: Tasks 1-3
  - semantic device ids mapped to firmware pins: Tasks 1 and 3
  - raw controller telemetry only: Task 2
  - UI, CLI, docs updates: Tasks 4-5
  - migration and verification: Tasks 1 and 6
- Placeholder scan: no `TBD`, `TODO`, “implement later”, or vague “add tests” steps remain.
- Type consistency:
  - `payload.devices` is firmware-native list
  - `settings.devices` is semantic map keyed by device id
  - telemetry is attached only in status responses, not persisted config
