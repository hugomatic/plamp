# Settings Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the split `/config` and `/settings` admin flow with one redesigned `/settings` page that handles Plamp setup, host status, and cautious hostname control.

**Architecture:** Keep `plamp_web/hardware_config.py` as the authority for persisted config validation, extend it with optional `label` fields, and reuse the existing section-save APIs for controllers/devices/cameras. Redesign `render_settings_page()` to render the three-band admin page, move the old config form behavior into that page, add separate hostname APIs in `plamp_web/server.py`, and remove the `/config` route instead of redirecting it.

**Tech Stack:** Python 3.11, FastAPI, plain server-rendered HTML, vanilla browser JavaScript, stdlib `unittest`, existing JSON config helpers.

---

## File Structure

- Modify `plamp_web/hardware_config.py`: allow optional `label` fields on controllers, devices, and cameras while preserving existing id-based validation.
- Modify `plamp_web/pages.py`: redesign `/settings`, remove `render_config_page()`, update nav links, and add hostname confirm/apply UI.
- Modify `plamp_web/server.py`: remove `/config`, keep config section save endpoints, add host-config endpoints, and feed the combined `/settings` page with both saved config and status data.
- Modify `tests/test_hardware_config.py`: cover optional label validation and persistence.
- Modify `tests/test_pages.py`: replace old `/config` page expectations with the new three-band `/settings` page and nav.
- Modify `tests/test_config_api.py`: add route/API coverage for `/settings`, absence of `/config`, and hostname read/apply endpoints.
- Modify `data/config.json` only if the checked-in sample needs `label` examples; do not overwrite user-local runtime values during implementation.

### Task 1: Add optional labels to persisted config

**Files:**
- Modify: `tests/test_hardware_config.py`
- Modify: `plamp_web/hardware_config.py`

- [ ] **Step 1: Write the failing tests for optional labels**

Add these tests to `tests/test_hardware_config.py` near the existing validation coverage:

```python
    def test_validate_controllers_allows_optional_label(self):
        self.assertEqual(
            validate_controllers({"ctrl_a": {"pico_serial": "PICO123", "label": "Pump lights"}}),
            {"ctrl_a": {"pico_serial": "PICO123", "label": "Pump lights"}},
        )

    def test_validate_devices_allows_optional_label(self):
        self.assertEqual(
            validate_devices({"dev_1": {"controller": "ctrl_a", "pin": 3, "editor": "cycle", "label": "Main pump"}}, {"ctrl_a": {}}),
            {"dev_1": {"controller": "ctrl_a", "pin": 3, "editor": "cycle", "label": "Main pump"}},
        )

    def test_validate_cameras_allows_optional_label(self):
        self.assertEqual(validate_cameras({"cam_1": {"label": "Tent"}}), {"cam_1": {"label": "Tent"}})

    def test_validate_rejects_non_string_label(self):
        with self.assertRaisesRegex(ValueError, "label"):
            validate_controllers({"ctrl_a": {"label": 123}})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `/home/hugo/.local/bin/uv run python -m unittest tests.test_hardware_config -v`

Expected: FAIL with unknown-key errors for `label` or camera non-empty validation failures.

- [ ] **Step 3: Write the minimal implementation in `plamp_web/hardware_config.py`**

Update the validators to accept optional string labels and keep the output shape compact:

```python
def _optional_label(item: Mapping, label: str) -> str | None:
    value = item.get("label")
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise ValueError(f"{label} label must be a string")
    return value


def validate_controllers(value):
    value = _as_mapping(value, "controllers")
    controllers = {}
    for controller_id, controller_value in value.items():
        if not _is_valid_id(controller_id):
            raise ValueError(f"invalid controller id: {controller_id!r}")
        controller_value = _as_mapping(controller_value, f"controller {controller_id}")
        extra_keys = set(controller_value) - {"pico_serial", "label"}
        if extra_keys:
            raise ValueError(f"controller {controller_id} has unknown keys: {sorted(extra_keys)!r}")
        pico_serial = controller_value.get("pico_serial")
        label = _optional_label(controller_value, f"controller {controller_id}")
        controllers[controller_id] = {}
        if pico_serial is not None:
            controllers[controller_id]["pico_serial"] = pico_serial
        if label:
            controllers[controller_id]["label"] = label
    return controllers


def validate_devices(value, controllers):
    value = _as_mapping(value, "devices")
    controllers = validate_controllers(controllers)
    devices = {}
    for device_id, device_value in value.items():
        if not _is_valid_id(device_id):
            raise ValueError(f"invalid device id: {device_id!r}")
        device_value = _as_mapping(device_value, f"device {device_id}")
        extra_keys = set(device_value) - {"controller", "pin", "editor", "label"}
        if extra_keys:
            raise ValueError(f"device {device_id} has unknown keys: {sorted(extra_keys)!r}")
        controller = device_value.get("controller")
        pin = device_value.get("pin")
        editor = device_value.get("editor", "cycle")
        label = _optional_label(device_value, f"device {device_id}")
        devices[device_id] = {"controller": controller, "pin": pin, "editor": editor}
        if label:
            devices[device_id]["label"] = label
    return devices


def validate_cameras(value):
    value = _as_mapping(value, "cameras")
    cameras = {}
    for camera_id, camera_value in value.items():
        if not _is_valid_id(camera_id):
            raise ValueError(f"invalid camera id: {camera_id!r}")
        camera_value = _as_mapping(camera_value, f"camera {camera_id}")
        extra_keys = set(camera_value) - {"label"}
        if extra_keys:
            raise ValueError(f"camera {camera_id} has unknown keys: {sorted(extra_keys)!r}")
        label = _optional_label(camera_value, f"camera {camera_id}")
        cameras[camera_id] = {}
        if label:
            cameras[camera_id]["label"] = label
    return cameras
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `/home/hugo/.local/bin/uv run python -m unittest tests.test_hardware_config -v`

Expected: PASS for all `HardwareConfigTests`.

- [ ] **Step 5: Commit**

```bash
git add tests/test_hardware_config.py plamp_web/hardware_config.py
git commit -m "Add optional config labels"
```

### Task 2: Redesign `/settings` as the only admin page

**Files:**
- Modify: `tests/test_pages.py`
- Modify: `plamp_web/pages.py`

- [ ] **Step 1: Write the failing page-render tests for the new `/settings` layout**

Replace the old Config-page assertions with settings-page coverage like this:

```python
    def test_settings_page_includes_plamp_setup_system_status_and_device_control(self):
        html = render_settings_page(
            {
                "config": {
                    "controllers": {"pump_lights": {"pico_serial": "abc", "label": "Pump lights"}},
                    "devices": {"pump": {"controller": "pump_lights", "pin": 2, "editor": "cycle", "label": "Main pump"}},
                    "cameras": {"rpicam_cam0": {"label": "Tent cam"}},
                },
                "detected": {"picos": [{"serial": "abc", "port": "/dev/ttyACM0"}], "cameras": [{"key": "rpicam:cam0", "model": "imx708", "lens": "wide"}]},
                "host": {"hostname": "plamp", "network": []},
                "picos": [],
                "software": {"git_short_commit": "abc123", "git_branch": "main", "git_dirty": False},
                "storage": {"path": "/tmp", "free": "1 GB", "used": "1 GB", "total": "2 GB"},
            }
        )

        self.assertIn("Plamp setup", html)
        self.assertIn("System status", html)
        self.assertIn("Device control", html)
        self.assertIn("<th>Label</th>", html)
        self.assertIn("Peripherals", html)
        self.assertIn('href="/settings"', html)
        self.assertNotIn('href="/config"', html)

    def test_settings_page_includes_hostname_confirm_apply_controls(self):
        html = render_settings_page(
            {
                "config": {"controllers": {}, "devices": {}, "cameras": {}},
                "detected": {"picos": [], "cameras": []},
                "host": {"hostname": "plamp", "network": []},
                "picos": [],
                "software": {"git_short_commit": "abc123", "git_branch": "main", "git_dirty": False},
                "storage": {"path": "/tmp", "free": "1 GB", "used": "1 GB", "total": "2 GB"},
            }
        )

        self.assertIn('id="hostname-input"', html)
        self.assertIn('id="hostname-confirm"', html)
        self.assertIn('id="hostname-status"', html)
        self.assertIn('/api/host-config/hostname', html)
```

Also update `test_timer_dashboard_page_links_to_config` to expect settings nav instead:

```python
        self.assertIn('<a href="/settings">Settings</a>', html)
        self.assertNotIn('href="/config"', html)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `/home/hugo/.local/bin/uv run python -m unittest tests.test_pages -v`

Expected: FAIL because `render_settings_page()` still renders only host status and the dashboard still links to `/config`.

- [ ] **Step 3: Implement the new settings page in `plamp_web/pages.py`**

Reshape `render_settings_page()` to take the combined payload and render the three bands, and remove `render_config_page()` entirely. Keep the existing form-save JS pattern, but attach it to the new sections.

Implement `render_settings_page(summary)` so it reads `summary["config"]` and `summary["detected"]`, then renders these concrete pieces:

```python
def collect_controller_payload(row):
    return {
        "pico_serial": row.querySelector(".controller-pico-serial").value,
        "label": row.querySelector(".controller-label").value.trim(),
    }


def collect_device_payload(row):
    return {
        "controller": row.querySelector(".device-controller").value,
        "pin": Number(row.querySelector(".device-pin").value),
        "editor": row.querySelector(".device-editor").value,
        "label": row.querySelector(".device-label").value.trim(),
    }


def collect_camera_payload(row):
    return {
        "label": row.querySelector(".camera-label").value.trim(),
    }
```

And make the HTML include these concrete markers:

```html
<nav><a href="/">Plamp</a> | <a href="/settings">&#9881; Settings</a> | <a href="/api/test">API test</a></nav>
<h1>Settings</h1>
<section aria-label="Plamp setup"><h2>Plamp setup</h2><p class="muted">Configure controllers, devices, and cameras.</p></section>
<section aria-label="System status"><h2>System status</h2><p class="muted">Detected hardware and host status.</p></section>
<section aria-label="Device control"><h2>Device control</h2><p class="muted">Changes here may require reconnecting to the device.</p></section>
<input id="hostname-input" value="plamp">
<button id="hostname-confirm" type="button">Apply hostname</button>
<span id="hostname-status">Ready.</span>
```

Also update `render_timer_dashboard_page()` nav to link only to `/settings`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `/home/hugo/.local/bin/uv run python -m unittest tests.test_pages -v`

Expected: PASS for the updated `PageRenderTests`.

- [ ] **Step 5: Commit**

```bash
git add tests/test_pages.py plamp_web/pages.py
git commit -m "Redesign settings page"
```

### Task 3: Wire the combined settings payload and remove `/config`

**Files:**
- Modify: `tests/test_config_api.py`
- Modify: `plamp_web/server.py`

- [ ] **Step 1: Write the failing API tests for `/settings` and `/config` removal**

Add tests like these to `tests/test_config_api.py`:

```python
    def test_get_settings_page_uses_combined_settings_payload(self):
        with patch.object(server, "settings_summary", return_value={
            "config": {"controllers": {}, "devices": {}, "cameras": {}},
            "detected": {"picos": [], "cameras": []},
            "host": {"hostname": "plamp", "network": []},
            "picos": [],
            "software": {"git_short_commit": "abc123", "git_branch": "main", "git_dirty": False},
            "storage": {"path": "/tmp", "free": "1 GB", "used": "1 GB", "total": "2 GB"},
        }):
            response = server.get_settings_page()

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Plamp setup", response.body)

    def test_config_route_is_removed(self):
        routes = {route.path for route in server.app.routes}
        self.assertNotIn("/config", routes)
```

Add one more test to assert `settings_summary()` carries config and detected values together:

```python
    def test_settings_summary_includes_config_and_detected(self):
        with (
            patch.object(server, "CONFIG_FILE", config_file),
            patch.object(server, "enumerate_picos", return_value=[]),
            patch.object(server.hardware_inventory, "detect_rpicam_cameras", return_value=[]),
        ):
            summary = server.settings_summary()

        self.assertIn("config", summary)
        self.assertIn("detected", summary)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `/home/hugo/.local/bin/uv run python -m unittest tests.test_config_api -v`

Expected: FAIL because `settings_summary()` does not yet include config/detected and `/config` still exists.

- [ ] **Step 3: Implement the server changes in `plamp_web/server.py`**

Refactor `settings_summary()` to add the saved config and detected hardware, keep `config_response()` only if still needed by tests, and remove the `/config` route.

Target change:

```python
def settings_summary() -> dict[str, Any]:
    config_data = config_response()
    return {
        "config": config_data["config"],
        "detected": config_data["detected"],
        "host_time": host_time_summary(),
        "host": host_summary(),
        "picos": enumerate_picos(),
        "software": software_summary(),
        "storage": storage_summary(),
        "cameras": camera_status_summary(),
        "tools": tool_summary(),
    }


@app.get("/settings", response_class=HTMLResponse)
def get_settings_page() -> HTMLResponse:
    return HTMLResponse(render_settings_page(settings_summary()))
```

Delete the `/config` handler entirely and update any route-dependent helpers or nav assumptions that still mention it.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `/home/hugo/.local/bin/uv run python -m unittest tests.test_config_api tests.test_pages -v`

Expected: PASS for the new settings-route tests and no `/config` references.

- [ ] **Step 5: Commit**

```bash
git add tests/test_config_api.py tests/test_pages.py plamp_web/server.py plamp_web/pages.py
git commit -m "Serve combined settings page"
```

### Task 4: Add hostname read/apply APIs and connect the Device control UI

**Files:**
- Modify: `tests/test_config_api.py`
- Modify: `plamp_web/server.py`
- Modify: `plamp_web/pages.py`

- [ ] **Step 1: Write the failing tests for hostname APIs**

Add these tests to `tests/test_config_api.py`:

```python
    def test_get_host_config_returns_hostname(self):
        with patch.object(server, "settings_summary", return_value={"host": {"hostname": "plamp", "network": []}}):
            data = server.get_host_config()

        self.assertEqual(data, {"hostname": "plamp"})

    def test_post_host_config_hostname_rejects_invalid_value(self):
        with self.assertRaises(HTTPException) as cm:
            server.post_host_config_hostname({"hostname": "bad host name"})

        self.assertEqual(cm.exception.status_code, 422)

    def test_post_host_config_hostname_applies_value(self):
        with patch.object(server, "apply_hostname", return_value={"hostname": "plamp-kiosk", "message": "hostname updated; reconnect may be required"}):
            data = server.post_host_config_hostname({"hostname": "plamp-kiosk"})

        self.assertTrue(data["success"])
        self.assertIn("reconnect", data["message"])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `/home/hugo/.local/bin/uv run python -m unittest tests.test_config_api -v`

Expected: FAIL because the host-config endpoints and `apply_hostname()` helper do not exist yet.

- [ ] **Step 3: Implement the hostname APIs and UI wiring**

In `plamp_web/server.py`, add a small hostname validator and route pair:

```python
_HOSTNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,62}$")


def validate_hostname(value: object) -> str:
    if not isinstance(value, str) or not _HOSTNAME_RE.fullmatch(value):
        raise ValueError("hostname must use letters, numbers, and dashes")
    return value


def apply_hostname(hostname: str) -> dict[str, Any]:
    completed = subprocess.run(["hostnamectl", "set-hostname", hostname], capture_output=True, text=True)
    if completed.returncode != 0:
        raise HTTPException(status_code=409, detail=completed.stderr.strip() or "hostname update failed")
    return {"hostname": hostname, "message": "hostname updated; reconnect or reboot may be required"}


@app.get("/api/host-config")
def get_host_config() -> dict[str, Any]:
    return {"hostname": settings_summary()["host"].get("hostname", "")}


@app.post("/api/host-config/hostname")
def post_host_config_hostname(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    try:
        hostname = validate_hostname(payload.get("hostname"))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    result = apply_hostname(hostname)
    return {"success": True, **result}
```

In `plamp_web/pages.py`, wire the Device-control form submit handler to `POST /api/host-config/hostname` only after an explicit confirm click:

```javascript
const hostnameInput = document.getElementById("hostname-input");
const hostnameConfirm = document.getElementById("hostname-confirm");
const hostnameStatus = document.getElementById("hostname-status");

hostnameConfirm.addEventListener("click", async () => {
  const hostname = hostnameInput.value.trim();
  if (!window.confirm(`Apply hostname "${hostname}"? You may need to reconnect.`)) return;
  hostnameStatus.textContent = "Applying...";
  const response = await fetch("/api/host-config/hostname", {
    method: "POST",
    headers: {"content-type": "application/json"},
    body: JSON.stringify({hostname}),
  });
  const text = await response.text();
  hostnameStatus.textContent = response.ok ? JSON.parse(text).message : `${response.status} ${text}`;
});
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `/home/hugo/.local/bin/uv run python -m unittest tests.test_config_api tests.test_pages -v`

Expected: PASS for hostname route coverage and Device-control render checks.

- [ ] **Step 5: Commit**

```bash
git add tests/test_config_api.py tests/test_pages.py plamp_web/server.py plamp_web/pages.py
git commit -m "Add hostname device control"
```

### Task 5: Full verification and checked-in sample cleanup

**Files:**
- Modify: `data/config.json` only if needed for checked-in sample labels
- Modify: any touched files from earlier tasks if the full suite reveals integration issues

- [ ] **Step 1: Add one sample label to the checked-in config only if the page looks empty without it**

If needed, keep the sample minimal:

```json
{
  "controllers": {
    "pump_lights": {
      "pico_serial": "e66038b71387a039",
      "label": "Pump and lights"
    }
  }
}
```

Skip this step if it would overwrite user-local runtime data or if the sample is already adequate.

- [ ] **Step 2: Run the full relevant suite**

Run: `/home/hugo/.local/bin/uv run python -m unittest tests.test_pages tests.test_config_api tests.test_timer_schedule tests.test_hardware_config -v`

Expected: PASS with `OK`.

- [ ] **Step 3: Start the local server and smoke-check the new page**

Run: `/home/hugo/.local/bin/uv run uvicorn plamp_web.server:app --host 0.0.0.0 --port 8000`

Expected: server starts cleanly and `http://127.0.0.1:8000/settings` shows `Plamp setup`, `System status`, and `Device control`.

- [ ] **Step 4: Verify there are no `/config` links left in the served HTML**

Run: `curl -sS http://127.0.0.1:8000/ | grep -n '/config'`

Expected: no output.

- [ ] **Step 5: Commit the final integration changes**

```bash
git add plamp_web/hardware_config.py plamp_web/pages.py plamp_web/server.py tests/test_hardware_config.py tests/test_pages.py tests/test_config_api.py
git commit -m "Complete settings redesign"
```
