# Fresh Report Handshake Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a scheduler apply reconnect, transmit `r` successfully, and deliver the resulting valid report to the dashboard immediately instead of waiting for the periodic report interval.

**Architecture:** `PicoMonitor` keeps an apply command pending through reset and reconnection; it completes the command only after writing `r`. Valid reports receive a monotonic sequence in `handle_line()` and are published on the controller's existing event-driven SSE stream. The dashboard consumes that controller stream directly, so the first valid post-`r` report updates the cards without status polling or reconstructed state.

**Tech Stack:** Python 3, FastAPI, pyserial, server-sent events, browser JavaScript, `unittest`.

## Global Constraints

- Do not add fixed sleeps, telemetry polling, protocol request IDs, or a second flash.
- Malformed serial input must not advance the report sequence.
- Apply must not report success before reconnect and successful `r` transmission.
- Pico reports remain authoritative for current ON/OFF state and runtime progress.
- Preserve unrelated untracked diagnostic files in the workspace.

---

### Task 1: Complete apply only after reconnect and `r`

**Files:**
- Modify: `plamp_web/server.py` (`ApplyCommand`, `PicoMonitor.handle_line`, `PicoMonitor.handle_apply`, `PicoMonitor.run`)
- Test: `tests/test_config_api.py`

**Interfaces:**
- Consumes: `PicoMonitor.open_serial()`, `PicoMonitor.record_serial()`, and the existing single-threaded command queue.
- Produces: `PicoMonitor.report_sequence: int`; report events containing `report_sequence`; an `ApplyCommand` that is completed only after `r` is written on the reconnected serial connection.

- [ ] **Step 1: Write failing monitor tests**

Add focused tests that construct a `PicoMonitor` without starting its thread and use fake serial connections:

```python
class FakeSerial:
    def __init__(self, port="/dev/ttyACM0"):
        self.port = port
        self.is_open = True
        self.writes = []

    def write(self, value):
        self.writes.append(value)

    def flush(self):
        pass

    def close(self):
        self.is_open = False


def test_pico_monitor_apply_does_not_complete_before_reconnect_and_report_request(self):
    monitor = server.PicoMonitor("pump_lights", "abc")
    command = server.ApplyCommand(Path("/tmp/main.py"))
    old_conn = FakeSerial()

    with (
        patch.object(monitor, "find_port", return_value="/dev/ttyACM0"),
        patch.object(server.shutil, "which", return_value="/usr/bin/mpremote"),
        patch.object(server, "interrupt_pico_program"),
        patch.object(server, "run_command", return_value=(0, "", "")),
    ):
        pending = monitor.handle_apply(command, old_conn)

    self.assertIs(pending, command)
    self.assertFalse(command.done.is_set())


def test_pico_monitor_finishes_pending_apply_after_writing_report_request(self):
    monitor = server.PicoMonitor("pump_lights", "abc")
    command = server.ApplyCommand(Path("/tmp/main.py"))
    conn = FakeSerial()

    monitor.finish_apply_after_reconnect(command, conn)

    self.assertEqual(conn.writes, [b"r\n"])
    self.assertTrue(command.done.is_set())
    self.assertEqual(command.result["report_sequence"], 0)
    self.assertEqual(monitor.serial_log()[-1]["text"], "r")


def test_pico_monitor_only_sequences_valid_reports(self):
    monitor = server.PicoMonitor("pump_lights", "abc")
    subscriber = monitor.subscribe()

    monitor.handle_line(b"not json\n")
    self.assertEqual(monitor.report_sequence, 0)

    monitor.handle_line(b'{"type":"report","content":{"devices":[]}}\n')
    event = subscriber.get_nowait()
    while event["event"] != "report":
        event = subscriber.get_nowait()
    self.assertEqual(monitor.report_sequence, 1)
    self.assertEqual(event["data"]["report_sequence"], 1)
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
UV_CACHE_DIR=/tmp/uv-cache /home/hugo/.local/bin/uv run python -m unittest \
  tests.test_config_api.ConfigApiTests.test_pico_monitor_apply_does_not_complete_before_reconnect_and_report_request \
  tests.test_config_api.ConfigApiTests.test_pico_monitor_finishes_pending_apply_after_writing_report_request \
  tests.test_config_api.ConfigApiTests.test_pico_monitor_only_sequences_valid_reports -v
```

Expected: failures because `handle_apply` currently sets `done`, `finish_apply_after_reconnect` does not exist, and reports have no sequence.

- [ ] **Step 3: Implement the pending apply lifecycle**

In `PicoMonitor.__init__`, initialize `self.report_sequence = 0`. Change `handle_apply` to finish the copy/reset work, publish reconnecting status, and return the still-pending `ApplyCommand`; remove its `command.done.set()` success path and fixed `time.sleep(0.5)` reconnect attempt.

Add this boundary:

```python
def finish_apply_after_reconnect(self, command: ApplyCommand, conn: serial.Serial) -> None:
    requested_after = self.report_sequence
    try:
        conn.write(b"r\n")
        conn.flush()
    except (OSError, serial.SerialException) as exc:
        command.error_status = 502
        command.error_detail = str(exc)
        self.record_serial("err", str(exc))
    else:
        self.record_serial("tx", "r")
        command.result = {
            "role": self.role,
            "port": getattr(conn, "port", None),
            "serial": self.pico_serial,
            "report_sequence": requested_after,
        }
    finally:
        command.done.set()
```

Keep a `pending_apply: ApplyCommand | None` local in `run()`. After reset, retain the command. On the normal connection path, call `finish_apply_after_reconnect(pending_apply, conn)` and clear it. If `open_serial()` has not found the reset Pico yet, leave the command pending and use the monitor's existing reconnect wake/backoff path; do not add another sleep.

In `handle_line()`, increment only after `json.loads()` succeeds and `reduce_report()` returns a dictionary whose type is `report`. Add the sequence to both `summary` and the published report event:

```python
self.report_sequence += 1
self.summary["report_sequence"] = self.report_sequence
self.publish("report", {
    "role": self.role,
    "serial": self.pico_serial,
    "received_at": now,
    "report_sequence": self.report_sequence,
    "report": reduced,
})
```

- [ ] **Step 4: Run monitor tests and the config API suite**

Run:

```bash
UV_CACHE_DIR=/tmp/uv-cache /home/hugo/.local/bin/uv run python -m unittest tests.test_config_api -v
```

Expected: all config API tests pass; apply tests prove completion occurs after `r` transmission.

- [ ] **Step 5: Commit**

```bash
git add plamp_web/server.py tests/test_config_api.py
git commit -m "Complete Pico apply after report request"
```

---

### Task 2: Consume immediate controller reports in the dashboard

**Files:**
- Modify: `plamp_web/pages.py` (`startTimerStreams` in `render_timer_dashboard_page`)
- Test: `tests/test_pages.py`

**Interfaces:**
- Consumes: `GET /api/controllers/{controller}?stream=true`, whose `report` events contain `{role, received_at, report_sequence, report}`.
- Produces: dashboard cards updated directly from each monitor event, without the one-second filtered-status polling stream.

- [ ] **Step 1: Write the failing dashboard stream test**

Replace the old filtered-status assertions with the direct controller stream contract:

```python
def test_timer_dashboard_uses_event_driven_controller_reports(self):
    html = render_timer_dashboard_page(["pump_lights"], "12h", {"pump_lights": []}, 0)

    self.assertIn(
        'const source = new EventSource(`/api/controllers/${encodeURIComponent(role)}?stream=true`);',
        html,
    )
    self.assertIn('for (const eventName of ["snapshot", "report"]) {', html)
    self.assertIn('timerMessages.set(role, JSON.parse(event.data));', html)
    self.assertNotIn("/api/status?stream=true&path=", html)
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```bash
UV_CACHE_DIR=/tmp/uv-cache /home/hugo/.local/bin/uv run python -m unittest \
  tests.test_pages.PageRenderTests.test_timer_dashboard_uses_event_driven_controller_reports -v
```

Expected: failure because the dashboard still opens the filtered status stream.

- [ ] **Step 3: Switch the dashboard to the existing monitor SSE endpoint**

Change `startTimerStreams()` to open:

```javascript
const source = new EventSource(`/api/controllers/${encodeURIComponent(role)}?stream=true`);
```

Listen for `snapshot` and `report`. Store the parsed event object directly in `timerMessages`; `timerDevicesFromMessage()` already supports snapshot `last_report` and report-event `report.content.devices` shapes. Do not replace device telemetry with intermediate `status` events, which do not contain devices. Render immediately after each snapshot or report:

```javascript
for (const eventName of ["snapshot", "report"]) {
  source.addEventListener(eventName, (event) => {
    timerMessages.set(role, JSON.parse(event.data));
    renderTimerStatus();
  });
}
```

- [ ] **Step 4: Run page tests**

Run:

```bash
UV_CACHE_DIR=/tmp/uv-cache /home/hugo/.local/bin/uv run python -m unittest tests.test_pages -v
```

Expected: all page tests pass, with obsolete filtered-status expectations removed only where replaced by the direct controller stream.

- [ ] **Step 5: Commit**

```bash
git add plamp_web/pages.py tests/test_pages.py
git commit -m "Stream fresh Pico reports to dashboard"
```

---

### Task 3: Verify, push, deploy, and observe one real apply

**Files:**
- Verify only: `plamp_web/server.py`, `plamp_web/pages.py`, relevant tests and spec.

**Interfaces:**
- Consumes: Tasks 1 and 2.
- Produces: pushed `main`, restarted `plamp-web`, and timestamp evidence that `r` transmission precedes the first fresh report without waiting for `report_every`.

- [ ] **Step 1: Run the focused regression suite**

```bash
UV_CACHE_DIR=/tmp/uv-cache /home/hugo/.local/bin/uv run python -m unittest \
  tests.test_timer_schedule tests.test_config_api tests.test_pages tests.test_plamp_cli -v
python3 -m py_compile plamp_web/server.py plamp_web/pages.py
git diff --check
```

Expected: all tests pass, compilation succeeds, and `git diff --check` prints nothing.

- [ ] **Step 2: Push main**

```bash
git push origin main
```

Expected: GitHub `main` advances to the implementation commit.

- [ ] **Step 3: Deploy with plampctl**

Because tracked `HEAD` already equals pushed `origin/main` and unrelated untracked files must remain untouched:

```bash
./plampctl restart
```

Expected: `plamp-web.service` is active and running.

- [ ] **Step 4: Smoke-test the service**

```bash
python3 -m plamp_cli --base-url http://127.0.0.1:8000 --table system status
```

Expected: branch `main`, implementation commit, and a successful response.

- [ ] **Step 5: Observe the next user-authorized schedule apply**

Read `/api/controllers/pump_n_lights/serial-log` after an apply and verify ordered evidence:

```text
tx r
rx {"type":"report", ...}
```

The valid report must arrive before the next ten-second periodic boundary. Do not change schedule values solely for this verification unless the user authorizes that state change.
