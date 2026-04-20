# Pico Scheduler Controller Type Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add explicit Pico scheduler controller typing, settings-page reporting interval editing, scheduler-only device assignment, and generated Pico state ownership.

**Architecture:** Extend `plamp_web.hardware_config` so normalized controller config includes `type` and scheduler-only `report_every`. Keep `devices` flat, but validate them against scheduler controllers only. Update `plamp_web.server` to scope timer runtime to scheduler controllers and generate the Pico `state.json` payload from controller config plus timer events before applying.

**Tech Stack:** Python 3.11, FastAPI, stdlib `unittest`, HTML string rendering in `plamp_web/pages.py`, MicroPython state JSON consumed by `pico_scheduler/main.py`.

---

## File Map

- Modify `plamp_web/hardware_config.py`: controller type constants, controller defaults, report interval validation, scheduler controller filtering, and device controller validation.
- Modify `plamp_web/server.py`: timer role filtering, monitor serial filtering, generated Pico state payload, and timer save/apply behavior.
- Modify `plamp_web/pages.py`: settings table fields, scheduler-only controller options, labels, and JavaScript collection logic.
- Modify `tests/test_hardware_config.py`: config normalization and validation tests.
- Modify `tests/test_config_api.py`: timer role scoping and generated state tests.
- Modify `tests/test_pages.py`: settings HTML and JavaScript rendering tests.
- Modify `data/config.json`: add `type: "pico_scheduler"` and `report_every` to the local checked-in sample config.
- Modify `plamp_web/README.md` and `README.md`: document controller type and report interval ownership.

---

### Task 1: Normalize Controller Type And Scheduler Report Interval

**Files:**
- Modify: `plamp_web/hardware_config.py`
- Test: `tests/test_hardware_config.py`

- [ ] **Step 1: Write failing controller validation tests**

Add these tests to `tests/test_hardware_config.py` near the existing controller tests:

```python
    def test_validate_controllers_defaults_to_pico_scheduler_type_and_report_every(self):
        self.assertEqual(
            validate_controllers({"ctrl_a": {"pico_serial": "PICO123"}}),
            {"ctrl_a": {"type": "pico_scheduler", "pico_serial": "PICO123", "report_every": 10}},
        )

    def test_validate_controllers_accepts_pico_scheduler_report_every(self):
        self.assertEqual(
            validate_controllers({"ctrl_a": {"type": "pico_scheduler", "report_every": 30}}),
            {"ctrl_a": {"type": "pico_scheduler", "report_every": 30}},
        )

    def test_validate_controllers_rejects_invalid_type_and_report_every(self):
        with self.assertRaisesRegex(ValueError, "controller ctrl_a type"):
            validate_controllers({"ctrl_a": {"type": "ph_doser"}})
        with self.assertRaisesRegex(ValueError, "report_every"):
            validate_controllers({"ctrl_a": {"type": "pico_scheduler", "report_every": 0}})
        with self.assertRaisesRegex(ValueError, "report_every"):
            validate_controllers({"ctrl_a": {"type": "pico_scheduler", "report_every": True}})
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest tests.test_hardware_config.HardwareConfigTests.test_validate_controllers_defaults_to_pico_scheduler_type_and_report_every tests.test_hardware_config.HardwareConfigTests.test_validate_controllers_accepts_pico_scheduler_report_every tests.test_hardware_config.HardwareConfigTests.test_validate_controllers_rejects_invalid_type_and_report_every
```

Expected: FAIL because `type` and `report_every` are currently unknown controller keys.

- [ ] **Step 3: Implement controller type normalization**

In `plamp_web/hardware_config.py`, add constants after `_PIN_TYPES`:

```python
_CONTROLLER_TYPES = {"pico_scheduler"}
_DEFAULT_CONTROLLER_TYPE = "pico_scheduler"
_DEFAULT_REPORT_EVERY = 10
```

Add this helper after `_optional_label`:

```python
def _required_positive_int(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{label} must be a positive integer")
    if value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value
```

Replace `validate_controllers` with:

```python
def validate_controllers(value):
    value = _as_mapping(value, "controllers")
    controllers = {}
    for controller_id, controller_value in value.items():
        if not _is_valid_id(controller_id):
            raise ValueError(f"invalid controller id: {controller_id!r}")
        controller_value = _as_mapping(controller_value, f"controller {controller_id}")
        extra_keys = set(controller_value) - {"pico_serial", "label", "type", "report_every"}
        if extra_keys:
            raise ValueError(f"controller {controller_id} has unknown keys: {sorted(extra_keys)!r}")

        controller_type = controller_value.get("type", _DEFAULT_CONTROLLER_TYPE)
        if controller_type not in _CONTROLLER_TYPES:
            raise ValueError(f"controller {controller_id} type must be one of {sorted(_CONTROLLER_TYPES)!r}")

        pico_serial = controller_value.get("pico_serial")
        if pico_serial is not None and (not isinstance(pico_serial, str) or not pico_serial):
            raise ValueError(f"controller {controller_id} pico_serial must be a non-empty string")
        label = _optional_label(controller_value, f"controller {controller_id}")

        controller = {"type": controller_type}
        if controller_type == "pico_scheduler":
            controller["report_every"] = _required_positive_int(
                controller_value.get("report_every", _DEFAULT_REPORT_EVERY),
                f"controller {controller_id} report_every",
            )
        elif "report_every" in controller_value:
            raise ValueError(f"controller {controller_id} report_every is only valid for pico_scheduler")

        if pico_serial is not None:
            controller["pico_serial"] = pico_serial
        if label:
            controller["label"] = label
        controllers[controller_id] = controller
    return controllers
```

- [ ] **Step 4: Update existing expectations for normalized controllers**

Update existing `tests/test_hardware_config.py` expected controller dictionaries so every normalized controller has `type: "pico_scheduler"` and `report_every: 10` unless the test supplies another value.

Example replacement:

```python
self.assertEqual(
    validate_controllers({"ctrl_a": {}, "ctrl_b": {"pico_serial": "PICO123"}}),
    {
        "ctrl_a": {"type": "pico_scheduler", "report_every": 10},
        "ctrl_b": {"type": "pico_scheduler", "pico_serial": "PICO123", "report_every": 10},
    },
)
```

- [ ] **Step 5: Run hardware config tests**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest tests.test_hardware_config -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add plamp_web/hardware_config.py tests/test_hardware_config.py
git commit -m "Add Pico scheduler controller config fields"
```

---

### Task 2: Validate Scheduler Devices Against Scheduler Controllers

**Files:**
- Modify: `plamp_web/hardware_config.py`
- Test: `tests/test_hardware_config.py`

- [ ] **Step 1: Write failing scheduler-device validation tests**

Add these tests to `tests/test_hardware_config.py`:

```python
    def test_validate_devices_requires_pico_scheduler_controller(self):
        import plamp_web.hardware_config as hardware_config

        controllers = {"timer": {"type": "pico_scheduler"}, "future": {"type": "future_controller"}}
        original_types = hardware_config._CONTROLLER_TYPES
        try:
            hardware_config._CONTROLLER_TYPES = {"pico_scheduler", "future_controller"}
            with self.assertRaisesRegex(ValueError, "pico_scheduler"):
                validate_devices({"pump": {"controller": "future", "pin": 3}}, controllers)
        finally:
            hardware_config._CONTROLLER_TYPES = original_types

    def test_scheduler_controller_ids_returns_only_pico_scheduler_controllers(self):
        from plamp_web.hardware_config import scheduler_controller_ids

        self.assertEqual(
            scheduler_controller_ids(
                {
                    "timer": {"type": "pico_scheduler"},
                    "legacy": {},
                    "future": {"type": "future_controller"},
                }
            ),
            {"timer", "legacy"},
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest tests.test_hardware_config.HardwareConfigTests.test_validate_devices_requires_pico_scheduler_controller tests.test_hardware_config.HardwareConfigTests.test_scheduler_controller_ids_returns_only_pico_scheduler_controllers
```

Expected: FAIL because `scheduler_controller_ids` does not exist and non-scheduler types are not filtered.

- [ ] **Step 3: Add scheduler controller helpers**

In `plamp_web/hardware_config.py`, add these functions after `validate_controllers`:

```python
def controller_type(controller: Mapping) -> str:
    value = controller.get("type", _DEFAULT_CONTROLLER_TYPE)
    return str(value)


def scheduler_controller_ids(controllers) -> set[str]:
    controllers = _as_mapping(controllers, "controllers")
    return {
        controller_id
        for controller_id, controller_value in controllers.items()
        if isinstance(controller_id, str)
        and isinstance(controller_value, Mapping)
        and controller_type(controller_value) == "pico_scheduler"
    }
```

Update `validate_devices` after `controllers = validate_controllers(controllers)`:

```python
    scheduler_controllers = scheduler_controller_ids(controllers)
```

Replace the unknown-controller check with:

```python
        if controller not in controllers:
            raise ValueError(f"device {device_id} references unknown controller: {controller!r}")
        if controller not in scheduler_controllers:
            raise ValueError(f"device {device_id} controller must reference a pico_scheduler controller: {controller!r}")
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest tests.test_hardware_config -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add plamp_web/hardware_config.py tests/test_hardware_config.py
git commit -m "Restrict timer devices to scheduler controllers"
```

---

### Task 3: Scope Timer Runtime To Pico Scheduler Controllers

**Files:**
- Modify: `plamp_web/server.py`
- Test: `tests/test_config_api.py`

- [ ] **Step 1: Write failing timer role scoping tests**

Add this test to `tests/test_config_api.py` near `test_get_timer_config_reflects_config_device_changes_immediately`:

```python
    def test_timer_runtime_excludes_non_scheduler_controllers(self):
        config = {
            "controllers": {
                "timer": {"type": "pico_scheduler", "pico_serial": "TIMER", "report_every": 10},
                "future": {"type": "future_controller", "pico_serial": "FUTURE"},
            },
            "devices": {},
            "cameras": {},
        }
        with patch.object(server, "load_config", return_value=config):
            roles = server.configured_timer_roles()
            serials = server.configured_monitor_serials()
            timer_config = server.get_timer_config()

        self.assertEqual(roles, ["timer"])
        self.assertEqual(serials, {"timer": "TIMER"})
        self.assertEqual(timer_config["roles"], ["timer"])
        self.assertNotIn("future", timer_config["channels"])
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest tests.test_config_api.ConfigApiTests.test_timer_runtime_excludes_non_scheduler_controllers
```

Expected: FAIL because non-scheduler controllers are still included by timer runtime discovery.

- [ ] **Step 3: Import scheduler helpers**

Update the import in `plamp_web/server.py`:

```python
from plamp_web.hardware_config import apply_config_section, config_view, empty_config, scheduler_controller_ids
```

- [ ] **Step 4: Add scheduler controller filtering in timer roles**

Replace `timer_roles` in `plamp_web/server.py` with:

```python
def timer_roles() -> dict[str, dict[str, Any]]:
    config = load_config()
    controllers = config.get("controllers", {})
    if not isinstance(controllers, dict):
        raise HTTPException(status_code=500, detail="config controllers must be an object")
    scheduler_ids = scheduler_controller_ids(controllers)
    return {role: controllers[role] for role in controllers if role in scheduler_ids}
```

Replace the role discovery in `configured_timer_channels`:

```python
        roles = list(timer_roles())
```

- [ ] **Step 5: Run config API tests**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest tests.test_config_api -v
```

Expected: PASS after test expectations are updated for normalized controller defaults.

- [ ] **Step 6: Commit**

```bash
git add plamp_web/server.py tests/test_config_api.py
git commit -m "Scope timer runtime to scheduler controllers"
```

---

### Task 4: Generate Pico Scheduler State From Controller Config

**Files:**
- Modify: `plamp_web/server.py`
- Test: `tests/test_config_api.py`

- [ ] **Step 1: Write failing generated-state test**

Add this test to `tests/test_config_api.py` near the Pico apply tests:

```python
    def test_apply_timer_state_generates_report_every_from_controller_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = self.make_config(
                root,
                {
                    "controllers": {"pump_lights": {"type": "pico_scheduler", "pico_serial": "abc", "report_every": 42}},
                    "devices": {"pump": {"controller": "pump_lights", "pin": 2, "editor": "cycle"}},
                    "cameras": {},
                },
            )
            timer_path = root / "data" / "timers" / "pump_lights.json"
            timer_path.parent.mkdir(parents=True)
            timer_path.write_text(
                json.dumps(
                    {
                        "report_every": 1,
                        "events": [
                            {"id": "pump", "type": "gpio", "pin": 2, "current_t": 0, "reschedule": 1, "pattern": [{"val": 1, "dur": 10}, {"val": 0, "dur": 20}]}
                        ],
                    }
                ),
                encoding="utf-8",
            )
            applied_payloads = []

            class FakeMonitor:
                def apply(self, path):
                    applied_payloads.append(json.loads(Path(path).read_text(encoding="utf-8")))
                    return {"ok": True}

            with (
                patch.object(server, "CONFIG_FILE", config_file),
                patch.object(server, "get_or_start_monitor", return_value=FakeMonitor()),
            ):
                response = server.apply_timer_state("pump_lights", timer_path)

        self.assertEqual(response, {"ok": True})
        self.assertEqual(applied_payloads[0]["report_every"], 42)
        self.assertEqual(applied_payloads[0]["events"][0]["id"], "pump")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest tests.test_config_api.ConfigApiTests.test_apply_timer_state_generates_report_every_from_controller_config
```

Expected: FAIL because `apply_timer_state` currently passes the timer file through unchanged.

- [ ] **Step 3: Implement generated state helpers**

In `plamp_web/server.py`, add `import tempfile` with the other imports.

Add this helper near `validate_timer_state`:

```python
def timer_state_for_pico(role: str, raw_state: Any) -> dict[str, Any]:
    state = validate_timer_state(raw_state)
    role_config = timer_role(role)
    report_every = require_int(role_config.get("report_every", 10), "report_every must be an integer")
    if report_every <= 0:
        raise HTTPException(status_code=422, detail="report_every must be > 0")
    return {"report_every": report_every, "events": state["events"]}
```

Replace `apply_timer_state` with:

```python
def apply_timer_state(role: str, path: Path) -> dict[str, Any]:
    generated = timer_state_for_pico(role, load_json_file(path))
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as temp:
        temp_path = Path(temp.name)
        json.dump(generated, temp, indent=2)
        temp.write("\n")
    try:
        return get_or_start_monitor(role).apply(temp_path)
    finally:
        try:
            temp_path.unlink()
        except OSError:
            pass
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest tests.test_config_api.ConfigApiTests.test_apply_timer_state_generates_report_every_from_controller_config tests.test_config_api.ConfigApiTests.test_post_timer_channel_schedule_creates_state_when_timer_file_is_missing tests.test_config_api.ConfigApiTests.test_post_timer_channel_schedule_replaces_invalid_timer_file -v
```

Expected: PASS. Existing saved timer files may still contain `report_every: 1`; the generated apply payload must use controller config.

- [ ] **Step 5: Run full config API tests**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest tests.test_config_api -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add plamp_web/server.py tests/test_config_api.py
git commit -m "Generate scheduler Pico state from config"
```

---

### Task 5: Update Settings Page For Controller Type And Scheduler Devices

**Files:**
- Modify: `plamp_web/pages.py`
- Test: `tests/test_pages.py`

- [ ] **Step 1: Write failing settings page render tests**

Add these tests to `tests/test_pages.py`:

```python
    def test_settings_page_edits_controller_type_and_report_interval(self):
        html = render_settings_page(
            {
                "config": {
                    "controllers": {
                        "pump_lights": {
                            "type": "pico_scheduler",
                            "pico_serial": "abc",
                            "report_every": 15,
                            "label": "Pump lights",
                        }
                    },
                    "devices": {},
                    "cameras": {},
                },
                "detected": {"picos": [{"serial": "abc", "port": "/dev/ttyACM0"}], "cameras": []},
                "host": {"hostname": "plamp", "network": []},
                "picos": [],
                "software": {},
                "storage": {"path": "/tmp", "free": "1 GB", "used": "1 GB", "total": "2 GB"},
            }
        )

        self.assertIn("<th>Type</th>", html)
        self.assertIn("<th>Report every seconds</th>", html)
        self.assertIn('class="controller-type"', html)
        self.assertIn('class="controller-report-every"', html)
        self.assertIn('value="15"', html)
        self.assertIn("report_every: Number(reportEvery)", html)

    def test_settings_page_labels_scheduler_devices_and_uses_output_type(self):
        html = render_settings_page(
            {
                "config": {
                    "controllers": {"pump_lights": {"type": "pico_scheduler", "report_every": 10}},
                    "devices": {"pump": {"controller": "pump_lights", "pin": 3, "type": "gpio", "editor": "cycle"}},
                    "cameras": {},
                },
                "detected": {"picos": [], "cameras": []},
                "host": {"hostname": "plamp", "network": []},
                "picos": [],
                "software": {},
                "storage": {"path": "/tmp", "free": "1 GB", "used": "1 GB", "total": "2 GB"},
            }
        )

        self.assertIn("<h3>Pico scheduler devices</h3>", html)
        self.assertIn("<th>Output type</th>", html)
        self.assertNotIn("<h3>Devices</h3>", html)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest tests.test_pages.PageRenderTests.test_settings_page_edits_controller_type_and_report_interval tests.test_pages.PageRenderTests.test_settings_page_labels_scheduler_devices_and_uses_output_type
```

Expected: FAIL because these fields and labels are not rendered.

- [ ] **Step 3: Add page helper functions**

In `plamp_web/pages.py`, add these helpers near `controller_options`:

```python
def controller_type_options(selected: str | None) -> str:
    selected = selected or "pico_scheduler"
    return option_tag("pico_scheduler", "pico_scheduler", selected)


def scheduler_controllers(controllers: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in controllers.items()
        if isinstance(value, dict) and str(value.get("type") or "pico_scheduler") == "pico_scheduler"
    }
```

- [ ] **Step 4: Update controller rows**

In `render_settings_page`, define:

```python
    scheduler_controller_options = scheduler_controllers(controllers)
```

Replace existing controller row HTML so it includes type and report interval:

```python
            '<tr class="controller-row" data-controller-key="{controller_id}">'
            '<td><input class="controller-id" placeholder="pump_lights" value="{controller_id}"></td>'
            '<td><input class="controller-label" placeholder="Pump and lights" value="{label}"></td>'
            '<td><select class="controller-type">{type_options}</select></td>'
            '<td><select class="controller-pico-serial">{pico_options_html}</select></td>'
            '<td><input class="controller-report-every" type="number" min="1" value="{report_every}"></td>'
            '</tr>'.format(
                controller_id=html.escape(controller_id, quote=True),
                label=html.escape(str(controller.get("label") or ""), quote=True),
                type_options=controller_type_options(str(controller.get("type") or "pico_scheduler")),
                pico_options_html=pico_options(setup_picos, str(controller.get("pico_serial") or "")),
                report_every=html.escape(str(controller.get("report_every") or 10), quote=True),
            )
```

Update the new controller row similarly with default type `pico_scheduler` and report interval `10`.

- [ ] **Step 5: Update settings table labels and JavaScript collection**

Change the controller table header to:

```html
<table><thead><tr><th>ID</th><th>Label</th><th>Type</th><th>Assigned peripheral</th><th>Report every seconds</th></tr></thead><tbody>{''.join(controller_rows)}</tbody></table>
```

Change the device section header and table header to:

```html
<h3>Pico scheduler devices</h3>
<table><thead><tr><th>ID</th><th>Label</th><th>Controller</th><th>Pin</th><th>Output type</th><th>Editor</th></tr></thead><tbody>{''.join(device_rows)}</tbody></table>
```

Update device controller options to use `scheduler_controller_options`:

```python
controller_options_html=controller_options(scheduler_controller_options, str(device.get("controller") or "")),
```

Update `collectControllers()`:

```javascript
        const picoSerial = row.querySelector(".controller-pico-serial").value;
        const type = row.querySelector(".controller-type").value;
        const reportEvery = row.querySelector(".controller-report-every").value;
        const payload = {pico_serial: picoSerial, label: row.querySelector(".controller-label").value.trim(), type};
        if (type === "pico_scheduler") {
          if (reportEvery === "") throw new Error(`Report interval required for controller ${key}.`);
          payload.report_every = Number(reportEvery);
        }
        result[key] = cleanObject(payload);
```

- [ ] **Step 6: Run page tests**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest tests.test_pages -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add plamp_web/pages.py tests/test_pages.py
git commit -m "Expose scheduler controller settings"
```

---

### Task 6: Update Samples, Docs, And Full Verification

**Files:**
- Modify: `data/config.json`
- Modify: `README.md`
- Modify: `plamp_web/README.md`
- Test: full suite and compile checks

- [ ] **Step 1: Update sample config**

Modify `data/config.json` so the existing controller includes:

```json
"type": "pico_scheduler",
"report_every": 10
```

For the current file, the controller should become:

```json
"pump_n_lights": {
  "type": "pico_scheduler",
  "pico_serial": "e66038b71387a039",
  "report_every": 10
}
```

- [ ] **Step 2: Update docs**

In `README.md` and `plamp_web/README.md`, update the config example for controllers to include:

```json
"controllers": {
  "pump_lights": {
    "type": "pico_scheduler",
    "pico_serial": "e66038b71387a039",
    "report_every": 10
  }
}
```

Add this text near the timer state description:

```markdown
`report_every` is configured on the controller in `data/config.json`. Timer state files keep schedule events; any older `report_every` value in `data/timers/<controller>.json` is legacy and is not the source of truth for Pico scheduler reporting cadence.
```

- [ ] **Step 3: Run Python compile checks**

Run:

```bash
/home/hugo/.local/bin/uv run python -m py_compile plamp_web/hardware_config.py plamp_web/server.py plamp_web/pages.py
```

Expected: command exits 0.

- [ ] **Step 4: Run full test suite**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest discover -v
```

Expected: PASS.

- [ ] **Step 5: Review git diff**

Run:

```bash
git diff --stat
git diff -- plamp_web/hardware_config.py plamp_web/server.py plamp_web/pages.py
```

Expected: changes are limited to controller type/report interval support and docs/sample updates.

- [ ] **Step 6: Commit**

```bash
git add data/config.json README.md plamp_web/README.md
git commit -m "Document scheduler controller settings"
```

---

## Self-Review Notes

- Spec coverage: controller `type`, scheduler-only `report_every`, flat `devices`, settings labels, timer runtime scoping, generated Pico state ownership, validation, and tests are each covered by tasks.
- Placeholder scan: no task uses placeholder implementation language; future controller types remain explicitly non-goal/future work.
- Type consistency: controller `type` uses `pico_scheduler`; device output `type` remains `gpio`/`pwm`; reporting interval key is consistently `report_every`.
