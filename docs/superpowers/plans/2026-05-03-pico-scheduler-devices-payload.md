# Pico Scheduler Devices Payload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the Pico scheduler firmware/runtime state field from `events` to `devices`, remove the CLI `timers` alias, and make server, UI, and CLI payloads consistently use the firmware-specific `devices` model.

**Architecture:** Change the firmware input and output payloads first, then update the server’s validation and live-monitor snapshot parsing to accept `devices` and emit `devices` outward. After the server contract is green, update the schedule-editing helpers, UI consumers, and CLI command family so the whole stack speaks the same Pico scheduler vocabulary. During the branch, server parsing may temporarily accept both `events` and `devices`, but final outward behavior must only expose `devices` and `pico-scheduler`.

**Tech Stack:** Python 3.11, FastAPI, MicroPython, stdlib `unittest`, HTML string rendering in `plamp_web/pages.py`, `argparse` CLI in `plamp_cli`.

---

## File Structure

- `pico_scheduler/main.py`
  Pico firmware loader and periodic report emitter. This is where top-level firmware `events` becomes `devices`.
- `pico_scheduler/README.md`
  Firmware-facing documentation and example payloads.
- `pico_scheduler/state.json.example`
  Example Pico input payload.
- `plamp_web/server.py`
  State validation, report reduction, live monitor snapshot reading, timer endpoints, and generated Pico state.
- `plamp_web/timer_schedule.py`
  Schedule editing helpers that currently expect `state["events"]`.
- `plamp_web/pages.py`
  Dashboard and API test page JS that currently reads `content.events` and timer snapshots with `events`.
- `plamp_cli/main.py`
  CLI parser and command handlers; remove `timers` alias and use `devices`.
- `plamp_cli/README.md`
  CLI command and payload docs.
- `tests/test_config_api.py`
  Server/API contract coverage.
- `tests/test_timer_schedule.py`
  Schedule editing and runtime channel metadata tests.
- `tests/test_pages.py`
  Dashboard and page-rendering tests for live-state payloads.
- `tests/test_plamp_cli.py`
  CLI parser, payload shape, and docs tests.

### Task 1: Firmware Payload Rename

**Files:**
- Modify: `tests/test_config_api.py`
- Modify: `pico_scheduler/main.py`
- Modify: `pico_scheduler/README.md`
- Modify: `pico_scheduler/state.json.example`

- [ ] **Step 1: Write the failing firmware-facing tests**

Add tests in `tests/test_config_api.py` that lock the new firmware payload vocabulary:

```python
    def test_validate_timer_state_accepts_devices_field(self):
        state = server.validate_timer_state(
            {
                "report_every": 10,
                "devices": [
                    {
                        "type": "gpio",
                        "pin": 2,
                        "current_t": 0,
                        "reschedule": 1,
                        "pattern": [{"val": 1, "dur": 10}, {"val": 0, "dur": 20}],
                    }
                ],
            }
        )

        self.assertEqual(state["devices"][0]["pin"], 2)

    def test_timer_state_for_pico_uses_devices(self):
        state = server.timer_state_for_pico(
            "pump_lights",
            {
                "report_every": 1,
                "devices": [
                    {
                        "type": "gpio",
                        "pin": 2,
                        "current_t": 0,
                        "reschedule": 1,
                        "pattern": [{"val": 1, "dur": 10}, {"val": 0, "dur": 20}],
                    }
                ],
            },
        )

        self.assertIn("devices", state)
        self.assertNotIn("events", state)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest \
  tests.test_config_api.ConfigApiTests.test_validate_timer_state_accepts_devices_field \
  tests.test_config_api.ConfigApiTests.test_timer_state_for_pico_uses_devices -v
```

Expected: FAIL because `validate_timer_state()` and `timer_state_for_pico()` still require `events`.

- [ ] **Step 3: Write minimal firmware/server implementation**

In `plamp_web/server.py`, change the state helpers to prefer `devices` and normalize legacy `events` only as a temporary input fallback:

```python
def _raw_devices_list(raw: dict[str, Any]) -> list[Any]:
    if "devices" in raw:
        value = raw["devices"]
    else:
        value = raw.get("events")
    if not isinstance(value, list):
        raise HTTPException(status_code=422, detail="devices must be a list")
    return value
```

Then update `validate_timer_state()` and `timer_state_for_pico()` to return:

```python
return {"report_every": report_every, "devices": devices}
```

Update `pico_scheduler/main.py` similarly:

```python
devices = []
...
if "devices" not in raw:
    return error("missing top-level field: devices")
raw_devices = raw["devices"]
...
new_devices.append(device)
...
devices = new_devices
```

And in `report()` emit:

```python
print(json.dumps({"kind": "report", "content": {"devices": out}}))
```

Update firmware docs/examples to show `devices`, not `events`.

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest \
  tests.test_config_api.ConfigApiTests.test_validate_timer_state_accepts_devices_field \
  tests.test_config_api.ConfigApiTests.test_timer_state_for_pico_uses_devices -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_config_api.py pico_scheduler/main.py pico_scheduler/README.md pico_scheduler/state.json.example plamp_web/server.py
git commit -m "Rename pico scheduler events to devices"
```

### Task 2: Server Snapshot And Monitor Contract

**Files:**
- Modify: `tests/test_config_api.py`
- Modify: `plamp_web/server.py`

- [ ] **Step 1: Write the failing snapshot and report tests**

Add tests covering live reports and snapshot state:

```python
    def test_latest_timer_state_reads_devices_from_last_report(self):
        monitor = Mock()
        monitor.snapshot.return_value = {
            "last_report": {
                "kind": "report",
                "content": {
                    "devices": [
                        {
                            "pin": 2,
                            "type": "gpio",
                            "elapsed_t": 5,
                            "cycle_t": 5,
                            "reschedule": 1,
                            "pattern": [{"val": 1, "dur": 10}, {"val": 0, "dur": 20}],
                            "current_value": 1,
                        }
                    ]
                },
            }
        }

        with patch.object(server, "get_or_start_monitor", return_value=monitor):
            latest = server.latest_timer_state("pump_lights")

        self.assertEqual(latest["devices"][0]["pin"], 2)

    def test_get_timer_returns_devices_not_events(self):
        with patch.object(server, "state_for_role", return_value={"report_every": 10, "devices": []}):
            payload = server.get_timer("pump_lights")

        self.assertEqual(payload, {"report_every": 10, "devices": []})
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest \
  tests.test_config_api.ConfigApiTests.test_latest_timer_state_reads_devices_from_last_report \
  tests.test_config_api.ConfigApiTests.test_get_timer_returns_devices_not_events -v
```

Expected: FAIL because the live report parser still reads `content["events"]`.

- [ ] **Step 3: Write minimal implementation**

Update `plamp_web/server.py`:

- `reduce_report()` should read and rewrite `content["devices"]`
- `state_with_current_values()` should enrich `state["devices"]`
- `latest_timer_state()` should read `content["devices"]`
- `live_events_for_role()` should become a device-list helper, for example:

```python
def live_devices_for_role(role: str) -> list[dict[str, Any]]:
    latest = latest_timer_state(role)
    devices = latest.get("devices") if isinstance(latest, dict) else None
    return devices if isinstance(devices, list) else []
```

Use that helper anywhere schedule patching needs current live device state.

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest \
  tests.test_config_api.ConfigApiTests.test_latest_timer_state_reads_devices_from_last_report \
  tests.test_config_api.ConfigApiTests.test_get_timer_returns_devices_not_events -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_config_api.py plamp_web/server.py
git commit -m "Use devices in pico scheduler snapshots"
```

### Task 3: Schedule Editing Helpers

**Files:**
- Modify: `tests/test_timer_schedule.py`
- Modify: `tests/test_config_api.py`
- Modify: `plamp_web/timer_schedule.py`
- Modify: `plamp_web/server.py`

- [ ] **Step 1: Write the failing schedule-editing tests**

Update representative tests in `tests/test_timer_schedule.py` and `tests/test_config_api.py` so state fixtures use `devices`:

```python
        state = {
            "report_every": 1,
            "devices": [
                {
                    "type": "gpio",
                    "pin": 3,
                    "current_t": 4,
                    "reschedule": 1,
                    "pattern": [{"val": 1, "dur": 10}, {"val": 0, "dur": 50}],
                }
            ],
        }
```

and assert updated state also writes `devices`.

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest \
  tests.test_timer_schedule \
  tests.test_config_api.ConfigApiTests.test_post_timer_channel_schedule_creates_state_when_timer_file_is_missing \
  tests.test_config_api.ConfigApiTests.test_post_timer_channel_schedule_replaces_invalid_timer_file -v
```

Expected: FAIL because timer schedule helpers still read and write `state["events"]`.

- [ ] **Step 3: Write minimal implementation**

Update `plamp_web/timer_schedule.py`:

- `_events_by_pin()` -> `_devices_by_pin()`
- read `state.get("devices")`
- `patch_channel_schedule()` updates `updated["devices"]`
- keep per-device item shape unchanged except for the container rename

Update `plamp_web/server.py` callers to use the renamed live-device helper and ensure schedule responses return:

```python
"state": state_with_current_values(validated)
```

where that validated state now contains `devices`.

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest \
  tests.test_timer_schedule \
  tests.test_config_api.ConfigApiTests.test_post_timer_channel_schedule_creates_state_when_timer_file_is_missing \
  tests.test_config_api.ConfigApiTests.test_post_timer_channel_schedule_replaces_invalid_timer_file -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_timer_schedule.py tests/test_config_api.py plamp_web/timer_schedule.py plamp_web/server.py
git commit -m "Rename scheduler state events to devices"
```

### Task 4: Dashboard And Page Consumers

**Files:**
- Modify: `tests/test_pages.py`
- Modify: `plamp_web/pages.py`

- [ ] **Step 1: Write the failing UI tests**

Change page tests that seed runtime state or stream payloads so they use `devices`:

```python
        state = {
            "report_every": 10,
            "devices": [
                {
                    "pin": 2,
                    "type": "gpio",
                    "current_t": 0,
                    "reschedule": 1,
                    "pattern": [{"val": 1, "dur": 10}, {"val": 0, "dur": 20}],
                    "current_value": 1,
                }
            ],
        }
```

Also assert the rendered JS reads `message?.report?.content?.devices` instead of `events`.

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest tests.test_pages -v
```

Expected: FAIL because page JS still reads `events`.

- [ ] **Step 3: Write minimal implementation**

Update `plamp_web/pages.py`:

- replace stream lookups like `message?.report?.content?.events` with `devices`
- replace snapshot state lookups to use `devices`
- keep UI labels as devices/channels where already user-facing, but do not reintroduce `events`

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest tests.test_pages -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_pages.py plamp_web/pages.py
git commit -m "Use devices in pico scheduler page state"
```

### Task 5: CLI Command Family And Payload Contract

**Files:**
- Modify: `tests/test_plamp_cli.py`
- Modify: `plamp_cli/main.py`
- Modify: `plamp_cli/README.md`
- Modify: `README.md`

- [ ] **Step 1: Write the failing CLI tests**

Update `tests/test_plamp_cli.py`:

```python
    def test_pico_scheduler_get_returns_devices_state(self, request_json):
        request_json.return_value = {"report_every": 10, "devices": []}
        stdout = StringIO()
        stderr = StringIO()

        code = main(["pico-scheduler", "get", "pump_lights"], stdout=stdout, stderr=stderr)

        self.assertEqual(code, 0)
        self.assertEqual(stdout.getvalue(), '{"devices": [], "report_every": 10}\n')

    def test_help_does_not_list_timers_alias(self):
        result = subprocess.run(
            ["/usr/bin/python3", "plamp_cli/main.py", "--help"],
            cwd=Path(__file__).resolve().parents[1],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("{config,controllers,pico-scheduler,pics}", result.stdout)
        self.assertNotIn("timers", result.stdout)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest tests.test_plamp_cli -v
```

Expected: FAIL because the CLI still supports and documents `timers`.

- [ ] **Step 3: Write minimal implementation**

Update `plamp_cli/main.py`:

- remove `timers` parser and alias handling
- keep only `controllers` and `pico-scheduler`
- ensure `pico-scheduler get/set` pass through `devices` state payloads

Update docs:

- `plamp_cli/README.md`
- top-level `README.md`

Remove remaining `timers` examples and use `pico-scheduler` only.

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest tests.test_plamp_cli -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_plamp_cli.py plamp_cli/main.py plamp_cli/README.md README.md
git commit -m "Remove timers alias from plamp CLI"
```

### Task 6: Full Verification

**Files:**
- No code changes expected

- [ ] **Step 1: Run focused firmware/server/UI/CLI suites**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest \
  tests.test_config_api \
  tests.test_timer_schedule \
  tests.test_pages \
  tests.test_plamp_cli -v
```

Expected: PASS.

- [ ] **Step 2: Run the full test suite**

Run:

```bash
/home/hugo/.local/bin/uv run python -m unittest discover -s tests
```

Expected: `OK`

- [ ] **Step 3: Inspect for stale `events` or `timers` leaks**

Run:

```bash
grep -RIn "\bevents\b\|\btimers\b" pico_scheduler plamp_web plamp_cli tests README.md docs/superpowers/specs/2026-05-03-pico-scheduler-devices-payload-design.md
```

Expected:

- remaining `events` only where intentionally transport-level or in legacy-transition input fallback code
- no CLI-facing `timers` command examples

- [ ] **Step 4: Commit any last doc/test cleanup**

```bash
git add pico_scheduler plamp_web plamp_cli tests README.md
git commit -m "Polish pico scheduler devices payload rollout"
```

## Self-Review

- Spec coverage:
  - firmware input/output rename: Task 1
  - live report and snapshot parsing: Task 2
  - schedule editing: Task 3
  - UI consumption: Task 4
  - CLI family and docs: Task 5
  - verification and stale-name scan: Task 6
- Placeholder scan:
  - no TBD/TODO markers
  - each task has concrete files, code, commands, and expected results
- Type consistency:
  - plan consistently uses `devices`, `pico-scheduler`, and pin-based firmware identity
  - `events` appears only as a legacy input fallback or transport-level concept
