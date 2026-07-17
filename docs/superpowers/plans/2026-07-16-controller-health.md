# Controller Health Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make controller status evidence-based and make schedule changes fail without changing desired state whenever the configured Pico is unavailable.

**Architecture:** The shared library converts a real `r` exchange into one structured `OK` or `ERROR` health result. The service combines five-second host probes with Linux USB add/remove events, publishes status through the existing controller SSE stream, and performs controller-wide schedule changes as one verified flash followed by local commit. The Pico remains silent except for command responses.

**Tech Stack:** Python 3.11, pyserial, pyudev, FastAPI, server-sent events, browser JavaScript, unittest.

## Global Constraints

- Pico firmware must not emit unsolicited reports, readiness messages, or heartbeats.
- Host health probes run every five seconds; this interval is not user-configurable in the schedule editor.
- User-facing controller health has only `OK` and `ERROR: <reason>` outcomes.
- Temporary shared-lock contention is not a controller error.
- A failed schedule operation must not change desired configuration or claim success.
- USB add/remove, health, schedule, pulse, and diagnostic behavior must remain available through shared library/service interfaces rather than browser-only logic.
- Sprout is the disconnected/reconnected hardware test target before merge.

---

### Task 1: Structured Pico health evidence

**Files:**
- Create: `plamp/pico_health.py`
- Modify: `plamp/__init__.py`
- Test: `tests/test_plamp_pico_health.py`

**Interfaces:**
- Consumes: `PicoClient.report(timeout: float) -> PicoExchange` and existing transport exceptions.
- Produces: `PicoHealth`, `PicoHealthError`, `failed_health(...) -> PicoHealth`, and `probe_pico(client, timeout=3.0) -> PicoHealth` for the service and direct clients.

- [ ] **Step 1: Write failing health-result tests**

Create tests using a fake client whose `report()` returns `PicoExchange` or raises `PicoUnavailable`, `PicoReportTimeout`, `OSError`, and `serial.SerialException`. Assert the exact public shape:

```python
result = probe_pico(client, timeout=3)
self.assertTrue(result.ok)
self.assertEqual(result.status, "OK")
self.assertEqual(result.serial, "PICO-A")
self.assertEqual(result.port, "/dev/ttyACM0")
self.assertEqual(result.report["type"], "report")
self.assertIsNone(result.error)

result = probe_pico(missing_client, timeout=3)
self.assertFalse(result.ok)
self.assertEqual(result.status, "ERROR")
self.assertEqual(result.error.kind, "unavailable")
self.assertEqual(result.error.step, "discover")
self.assertIn("not connected", result.error.message)

result = probe_pico(timeout_client, timeout=3)
self.assertEqual(result.error.step, "report")
self.assertEqual(result.error.raw_lines, (">>>", "bad json"))
```

Also assert that `LockTimeout` is re-raised instead of converted into `ERROR`.

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m unittest tests.test_plamp_pico_health -v
```

Expected: import failure because `plamp.pico_health` does not exist.

- [ ] **Step 3: Implement the minimal shared health model**

Implement immutable records and exception-to-diagnostic conversion:

```python
@dataclass(frozen=True)
class PicoHealthError:
    kind: str
    step: str
    message: str
    raw_lines: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "step": self.step, "message": self.message, "raw_lines": list(self.raw_lines)}


@dataclass(frozen=True)
class PicoHealth:
    ok: bool
    status: str
    checked_at: str
    serial: str
    port: str | None
    report: dict[str, Any] | None
    raw_lines: tuple[str, ...]
    error: PicoHealthError | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "checked_at": self.checked_at,
            "serial": self.serial,
            "port": self.port,
            "report": self.report,
            "raw_lines": list(self.raw_lines),
            "error": self.error.as_dict() if self.error else None,
        }
```

`probe_pico()` must use an aware UTC timestamp, preserve malformed raw lines from `PicoReportTimeout`, label missing discovery as `discover`, and label serial/report failures as `report`. A report timeout with no received lines is `timeout`; a timeout containing rejected lines is `protocol`. Do not catch `LockTimeout`.

Add `failed_health(serial, *, kind, step, message, port=None, raw_lines=())` so event-driven failures and probe failures produce the identical public record without duplicating status construction in the service. Error kinds are `unavailable`, `timeout`, `serial`, and `protocol`; the service maps them to HTTP 409, 504, 502, and 502 respectively.

- [ ] **Step 4: Run focused and transport tests**

Run:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m unittest tests.test_plamp_pico_health tests.test_plamp_pico_transport -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add plamp/pico_health.py plamp/__init__.py tests/test_plamp_pico_health.py
git commit -m "Add structured Pico health evidence"
```

---

### Task 2: Linux USB serial events

**Files:**
- Create: `plamp/usb_events.py`
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Test: `tests/test_usb_events.py`

**Interfaces:**
- Consumes: Linux udev `tty` events through pyudev.
- Produces: `UsbSerialEvent(action, serial, port)` and `start_usb_serial_observer(callback) -> observer`.

- [ ] **Step 1: Write failing event-normalization tests**

Test add/remove devices with `ID_SERIAL_SHORT` and `DEVNAME`, irrelevant tty events without a USB serial, and callback delivery:

```python
event = usb_serial_event("remove", {"ID_SERIAL_SHORT": "PICO-A", "DEVNAME": "/dev/ttyACM0"})
self.assertEqual(event, UsbSerialEvent("remove", "PICO-A", "/dev/ttyACM0"))
self.assertIsNone(usb_serial_event("change", {"DEVNAME": "/dev/tty0"}))
```

Use injected context/monitor/observer factories so tests never depend on the host's actual udev stream.

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m unittest tests.test_usb_events -v
```

Expected: import failure because `plamp.usb_events` does not exist.

- [ ] **Step 3: Add pyudev and implement the observer adapter**

Add `pyudev` to project dependencies and regenerate `uv.lock`. Implement:

```python
@dataclass(frozen=True)
class UsbSerialEvent:
    action: str
    serial: str
    port: str | None


def usb_serial_event(action: str, properties: Mapping[str, Any]) -> UsbSerialEvent | None:
    serial = str(properties.get("ID_SERIAL_SHORT") or "").strip()
    if action not in {"add", "remove"} or not serial:
        return None
    port = str(properties.get("DEVNAME") or "").strip() or None
    return UsbSerialEvent(action, serial, port)
```

`start_usb_serial_observer()` must filter the udev monitor to subsystem `tty`, normalize events, call the supplied callback only for configured USB serial events, start the observer, and return it so service shutdown can stop it.

- [ ] **Step 4: Run focused tests**

Run:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m unittest tests.test_usb_events tests.test_plamp_pico_discovery -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add plamp/usb_events.py pyproject.toml uv.lock tests/test_usb_events.py
git commit -m "Observe Pico USB connection events"
```

---

### Task 3: Host-owned health monitor and SSE status

**Files:**
- Modify: `plamp_web/server.py`
- Test: `tests/test_config_api.py`

**Interfaces:**
- Consumes: `probe_pico()`, `UsbSerialEvent`, and the existing `PicoMonitor` subscriber stream.
- Produces: monitor snapshots and SSE `status` events containing `ok`, `status`, `checked_at`, `serial`, `port`, `error`, `last_report`, and `last_verified_at`.

- [ ] **Step 1: Write failing monitor tests**

Add tests proving:

```python
monitor.collect_report()
self.assertTrue(monitor.snapshot()["ok"])
self.assertEqual(monitor.snapshot()["status"], "OK")

monitor.handle_usb_event(UsbSerialEvent("remove", "PICO-A", "/dev/ttyACM0"))
self.assertFalse(monitor.snapshot()["ok"])
self.assertEqual(monitor.snapshot()["error"]["step"], "discover")

monitor.handle_usb_event(UsbSerialEvent("add", "PICO-A", "/dev/ttyACM1"))
self.assertTrue(monitor.wake_event.is_set())
```

Assert a successful `LockTimeout` path leaves the prior health unchanged. Assert monitor run-loop waits use exactly `5.0` seconds rather than configuration `report_every`. Assert the first SSE snapshot includes health and later USB/report changes emit `status` events.

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m unittest tests.test_config_api.ConfigApiTests.test_pico_monitor_publishes_binary_health tests.test_config_api.ConfigApiTests.test_pico_monitor_handles_usb_events tests.test_config_api.ConfigApiTests.test_pico_monitor_uses_fixed_health_interval -v
```

Expected: failures because binary health, USB handling, and the fixed interval are absent.

- [ ] **Step 3: Integrate shared health and USB events**

Add `PICO_HEALTH_INTERVAL_SECONDS = 5.0`. Replace exception-specific health mutation in `collect_report()` with `probe_pico()`, while retaining serial exchange diagnostics. Keep lock contention as a no-op. Add:

```python
def handle_usb_event(self, event: UsbSerialEvent) -> None:
    if event.serial != self.pico_serial:
        return
    if event.action == "remove":
        self.update_health(failed_health(self.pico_serial, kind="unavailable", step="discover", message="configured Pico is not connected", port=event.port))
    else:
        self.wake()
```

Start one udev observer during application startup, route events to matching monitors, and stop it during shutdown. Use the fixed interval in `PicoMonitor.run()`. Add `require_fresh_report(timeout=3.0) -> dict[str, Any]`, which performs a probe, updates and publishes health, raises HTTP 409/502/504 for an error result, and returns the valid report on success.

Publish successful heartbeat exchanges to the in-memory serial ring without INFO logging every five seconds. Continue logging failed raw lines and health transitions with their structured diagnostic fields.

- [ ] **Step 4: Run API and transport tests**

Run:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m unittest tests.test_config_api tests.test_plamp_pico_health tests.test_usb_events -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add plamp_web/server.py tests/test_config_api.py
git commit -m "Publish host-owned controller health"
```

---

### Task 4: Transactional controller-wide scheduling

**Files:**
- Modify: `plamp_web/server.py`
- Test: `tests/test_config_api.py`

**Interfaces:**
- Consumes: a proposed validated controller object and `PicoMonitor.apply()` which returns only after a valid post-flash report.
- Produces: `POST /api/controllers/{controller}/schedule`, plus corrected failure behavior for `/apply` and per-channel schedule endpoints.

- [ ] **Step 1: Replace the test that blesses offline success**

Replace `test_post_timer_channel_schedule_reports_saved_when_pico_is_offline` with tests asserting:

```python
with self.assertRaises(HTTPException) as caught:
    server.post_controller_schedule("pump_lights", proposed_controller)
self.assertEqual(caught.exception.status_code, 409)
self.assertIn("not connected", str(caught.exception.detail))
self.assertEqual(json.loads(config_file.read_text()), original_config)
self.assertEqual(json.loads(timer_file.read_text()), original_state)
```

Add a success test asserting one fresh preflight report, one flash, one post-flash report supplied by `PicoMonitor.apply()`, then one committed controller config and one committed timer state. Assert `/apply` propagates Pico HTTP errors instead of returning `success: true`.

- [ ] **Step 2: Run schedule tests and verify RED**

Run:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m unittest tests.test_config_api.ConfigApiTests.test_post_controller_schedule_rejects_offline_without_file_changes tests.test_config_api.ConfigApiTests.test_post_controller_schedule_commits_after_verified_flash tests.test_config_api.ConfigApiTests.test_post_controller_apply_propagates_pico_failure -v
```

Expected: missing endpoint and old false-success behavior.

- [ ] **Step 3: Implement one schedule transaction**

Add a controller-wide endpoint accepting the proposed controller object. Under the controller role lock:

```python
monitor = get_or_start_monitor(controller)
monitor.require_fresh_report(timeout=3.0)
current = load_raw_config()
candidate = copy.deepcopy(current)
candidate["controllers"][controller] = proposed_controller
validated_sections = config_view({"controllers": candidate["controllers"], "cameras": candidate.get("cameras", {})})
candidate.update(validated_sections)
compiled = validate_timer_state(compiled_timer_state_for_controller(controller, config=candidate, now=datetime.now().time()))
with TemporaryDirectory(dir=DATA_DIR) as temporary_dir:
    staged_state = Path(temporary_dir) / f"{controller}.json"
    atomic_write_json(staged_state, compiled)
    sent = apply_timer_state(controller, staged_state)
write_config_file(CONFIG_FILE, candidate)
atomic_write_json(timer_state_path(controller), compiled)
```

Do not write either authoritative file before the verified flash completes. Return `success: true` only on the complete path. Let the existing structured Pico failure propagate as non-2xx.

Refactor per-channel schedule changes to build a proposed controller and call the same transaction. Remove the `except HTTPException` block in `post_controller_apply()` that currently converts failure into success.

- [ ] **Step 4: Run schedule and config tests**

Run:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m unittest tests.test_config_api tests.test_plamp_config tests.test_hardware_config tests.test_timer_schedule -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add plamp_web/server.py tests/test_config_api.py
git commit -m "Reject unverified schedule changes"
```

---

### Task 5: Honest and fluid controller cards

**Files:**
- Modify: `plamp_web/pages.py`
- Test: `tests/test_pages.py`

**Interfaces:**
- Consumes: controller SSE `snapshot`, `report`, and `status` events; `POST /api/controllers/{controller}/schedule`; and the report command used for pre-edit verification.
- Produces: binary controller card styling, diagnostics, disabled scheduling, and local one-second timer animation.

- [ ] **Step 1: Write failing page tests**

Assert rendered JavaScript and CSS contain:

```python
self.assertIn('source.addEventListener("status"', html)
self.assertIn("controller-card-error", html)
self.assertIn("ERROR: ", html)
self.assertIn("last verified", html)
self.assertIn("/schedule", html)
self.assertNotIn("Pico poll interval (seconds)", html)
```

Add browser-logic tests at the existing source-string boundary proving `openControllerScheduleEditor()` requests a fresh report before setting `activeEditor`, disconnected cards disable their edit button, and submit performs one controller-wide schedule request rather than PUT-config followed by apply.

- [ ] **Step 2: Run page tests and verify RED**

Run:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m unittest tests.test_pages -v
```

Expected: missing status listener/card styles and old two-request schedule flow still present.

- [ ] **Step 3: Implement binary health rendering**

Maintain `timerStatuses` by controller. Handle initial snapshot health and subsequent SSE `status` events. Render:

```javascript
const health = timerStatuses.get(role);
const ok = health?.ok === true;
controllerCard.classList.toggle("controller-card-error", !ok);
edit.disabled = !ok;
status.textContent = ok
  ? `OK — verified ${formatAge(health.last_verified_at || health.checked_at)}`
  : `ERROR: ${health?.error?.message || "no valid report"}`;
```

Keep the entire unavailable card gray, mark retained report values as stale, and expose full diagnostics in a `<details>` element. Remove the report-period input from the editor.

Make editor opening asynchronous: request a fresh report first; on failure keep the editor closed and render the returned error. Submit one proposed controller object to the new schedule endpoint. A non-2xx response stays red and must never call `syncSavedEditorMetadata()`.

Retain local one-second progress animation from the latest report without creating one-second HTTP or serial polling.

- [ ] **Step 4: Run page and API tests**

Run:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m unittest tests.test_pages tests.test_config_api -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add plamp_web/pages.py tests/test_pages.py
git commit -m "Show controller health and disable offline schedules"
```

---

### Task 6: Pulse completion evidence

**Files:**
- Modify: `plamp_web/server.py`
- Test: `tests/test_config_api.py`

**Interfaces:**
- Consumes: the pulse command's immediate report and `PicoMonitor.wake()`.
- Produces: one delayed host report request after pulse duration without unsolicited Pico output.

- [ ] **Step 1: Write failing pulse follow-up tests**

Inject a timer factory and assert a successful five-second pulse schedules exactly one daemon callback after 5.1 seconds, whose callback wakes the matching monitor. The 100 ms bound exceeds the generated firmware's 20 ms loop interval so the report observes pulse removal rather than the final pre-removal tick. Assert rejected pulses schedule nothing.

```python
response = server.post_controller_channel_pulse("sprouter", "pump", {"seconds": 5})
timer_factory.assert_called_once()
self.assertEqual(timer_factory.call_args.args[0], 5.1)
timer_factory.call_args.args[1]()
monitor.wake.assert_called_once_with()
```

- [ ] **Step 2: Run pulse tests and verify RED**

Run:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m unittest tests.test_config_api.ConfigApiTests.test_pulse_schedules_completion_report tests.test_config_api.ConfigApiTests.test_rejected_pulse_schedules_no_report -v
```

Expected: no delayed report scheduling exists.

- [ ] **Step 3: Implement delayed host verification**

After a successful pulse response has been handled, create a daemon timer for the pulse duration plus 100 ms whose callback calls `monitor.wake()`. Keep the Pico firmware unchanged. The next monitor probe supplies the completion report and SSE update.

- [ ] **Step 4: Run pulse, monitor, and firmware-generator tests**

Run:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m unittest tests.test_config_api tests.test_pico_scheduler_generator -v
```

Expected: all tests pass and generated firmware remains silent outside command responses.

- [ ] **Step 5: Commit**

```bash
git add plamp_web/server.py tests/test_config_api.py
git commit -m "Verify Pico state after pulses"
```

---

### Task 7: Documentation, API examples, and hardware verification

**Files:**
- Modify: `plamp_web/README.md`
- Modify: `pico_scheduler/README.md`
- Modify: `plamp_web/pages.py`
- Test: `tests/test_pages.py`

**Interfaces:**
- Consumes: final REST/SSE contracts from Tasks 3–6.
- Produces: concise architecture documentation and runnable examples on the API test page.

- [ ] **Step 1: Write failing documentation/page assertions**

Assert the API test page names and demonstrates controller health, controller-wide scheduling, report, pulse, and SSE status usage. Assert old copy describing offline schedule saving or configurable schedule polling is absent.

- [ ] **Step 2: Run the page tests and verify RED**

Run:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m unittest tests.test_pages -v
```

Expected: health and controller-wide schedule examples are missing.

- [ ] **Step 3: Update concise documentation and examples**

Document these rules verbatim in substance:

```text
The Pico is silent until commanded. The host owns five-second health reports.
USB events provide immediate presence changes. OK requires a valid report.
Schedules are committed only after a verified flash; failures leave desired state unchanged.
```

Add test-page request buttons for current health/status stream and controller-wide schedule. Keep raw request and response bodies visible for agent use and diagnostics.

- [ ] **Step 4: Run full verification**

Run:

```bash
python3 -m py_compile plamp/*.py plamp_web/*.py tests/*.py
UV_CACHE_DIR=/tmp/uv-cache uv run python -m unittest discover -s tests -v
git diff --check
```

Expected: compilation succeeds, all tests pass, and diff check is clean.

- [ ] **Step 5: Commit**

```bash
git add plamp_web/README.md pico_scheduler/README.md plamp_web/pages.py tests/test_pages.py
git commit -m "Document controller health contract"
```

- [ ] **Step 6: Deploy branch to Sprout and verify disconnected state**

Use `plampctl remote-install` or `plampctl upgrade feature/controller-health`, then verify through `plampctl status` and `plamp-cli`. With USB unplugged, confirm the entire card is gray, reports `ERROR: not connected`, schedule editing cannot open, API scheduling returns non-2xx, and config/timer file hashes remain unchanged.

- [ ] **Step 7: Verify reconnect and operations on Sprout**

Reconnect USB and confirm the udev add event triggers an immediate valid report and restores `OK` without reloading. Apply one schedule and confirm one flash plus valid report before config commit. Pulse a safe off channel and confirm immediate and completion reports. Inspect verbose diagnostics and journal output to confirm successful five-second heartbeats do not spam INFO logs.
