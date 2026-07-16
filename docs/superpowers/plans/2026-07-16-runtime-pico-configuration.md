# Runtime Pico Configuration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace schedule-time Pico reflashing with one verified, persistent, full-state runtime configuration transaction, automatically upgrading legacy firmware once when a schedule is changed.

**Architecture:** A generic scheduler firmware loads persisted state, accepts one newline-delimited JSON `configure` document, atomically stores it, applies it, and returns a full report containing firmware identity. Shared `plamp` modules own state validation, identity comparison, serial configuration, and two-file firmware upgrades; REST and direct CLI are adapters over those operations.

**Tech Stack:** Python 3.11, MicroPython, pyserial, mpremote, FastAPI, `unittest`, JSON-lines serial protocol.

## Global Constraints

- Base this stacked branch on `feature/controller-health`; do not merge or redeploy that branch until its deferred reconnect test is complete.
- Read-only reports never mutate or upgrade a Pico.
- A schedule transaction upgrades missing, incompatible, or outdated firmware automatically using the currently committed schedule.
- Legacy firmware is replaced, not supported through a compatibility command path.
- Configuration is one complete document; never patch one channel on the Pico.
- Validate before persistence, persist before applying outputs, and report after applying.
- Never blindly resend `configure` after a lost reply; request `r` and compare instead.
- Commit host desired/applied files only after a matching full report.
- Preserve raw malformed serial lines and identify the failed operation stage.
- Do not add request IDs, background upgrades, another database, or crash-recovery journaling.
- Pulse overlays must restore the latest runtime-configured base schedule.

---

### Task 1: Shared scheduler state and firmware identity

**Files:**
- Create: `plamp/scheduler_state.py`
- Modify: `plamp/pico_protocol.py`
- Modify: `plamp/__init__.py`
- Create: `tests/test_scheduler_state.py`
- Modify: `tests/test_plamp_pico_protocol.py`

**Interfaces:**
- Consumes: current compiled state shape `{report_every, devices}` and report shape `{type, content}`.
- Produces: `FirmwareIdentity`, `EXPECTED_FIRMWARE_PROTOCOL`, `normalize_scheduler_state(raw)`, `firmware_identity(report)`, and `report_matches_state(report, state)`.

- [ ] **Step 1: Write failing state and identity tests**

Create `tests/test_scheduler_state.py` with focused examples:

```python
import unittest

from plamp.scheduler_state import (
    EXPECTED_FIRMWARE_PROTOCOL,
    FirmwareIdentity,
    firmware_identity,
    normalize_scheduler_state,
    report_matches_state,
)


STATE = {
    "report_every": 5,
    "devices": [{
        "id": "lights", "type": "gpio", "pin": 2, "current_t": 7,
        "reschedule": 1,
        "pattern": [{"val": 1, "dur": 10}, {"val": 0, "dur": 20}],
    }],
}


class SchedulerStateTests(unittest.TestCase):
    def test_normalizes_complete_state_without_host_poll_setting(self):
        self.assertEqual(normalize_scheduler_state(STATE), {"devices": STATE["devices"]})

    def test_rejects_duplicate_pin_before_returning_state(self):
        raw = {"devices": [STATE["devices"][0], dict(STATE["devices"][0], id="pump")]}
        with self.assertRaisesRegex(ValueError, "duplicate pin: 2"):
            normalize_scheduler_state(raw)

    def test_reads_firmware_identity_from_report(self):
        report = {"type": "report", "content": {
            "firmware": {"name": "pico_scheduler", "revision": "abc1234", "protocol": 2},
            "devices": [],
        }}
        self.assertEqual(
            firmware_identity(report),
            FirmwareIdentity("pico_scheduler", "abc1234", EXPECTED_FIRMWARE_PROTOCOL),
        )

    def test_legacy_report_has_no_identity(self):
        self.assertIsNone(firmware_identity({"type": "report", "content": {"devices": []}}))

    def test_report_comparison_ignores_runtime_elapsed_fields(self):
        report = {"type": "report", "content": {"devices": [{
            "id": "lights", "type": "gpio", "pin": 2, "elapsed_t": 19,
            "cycle_t": 19, "current_value": 0, "reschedule": 1,
            "pattern": STATE["devices"][0]["pattern"],
        }]}}
        self.assertTrue(report_matches_state(report, STATE))
```

Extend protocol tests to require `content.firmware` to be an object when present while continuing to accept legacy reports where it is absent.

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m unittest \
  tests.test_scheduler_state tests.test_plamp_pico_protocol -v
```

Expected: import failure because `plamp.scheduler_state` does not exist.

- [ ] **Step 3: Implement strict normalization and comparison**

Implement this public boundary in `plamp/scheduler_state.py`:

```python
from dataclasses import dataclass
from typing import Any

EXPECTED_FIRMWARE_PROTOCOL = 2


@dataclass(frozen=True)
class FirmwareIdentity:
    name: str
    revision: str
    protocol: int


def _integer(value: Any, label: str, *, minimum: int, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{label} must be an integer >= {minimum}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{label} must be <= {maximum}")
    return value


def normalize_scheduler_state(raw: Any) -> dict[str, Any]:
    """Return only Pico-owned state or raise ValueError before side effects."""
    if not isinstance(raw, dict) or set(raw) - {"devices", "report_every"}:
        raise ValueError("scheduler state must contain only devices and report_every")
    if not isinstance(raw.get("devices"), list):
        raise ValueError("devices must be a list")
    normalized, ids, pins = [], set(), set()
    for index, source in enumerate(raw["devices"]):
        if not isinstance(source, dict):
            raise ValueError(f"device {index} must be an object")
        allowed = {"id", "type", "pin", "current_t", "reschedule", "pattern"}
        if set(source) - allowed or not {"type", "pin", "current_t", "reschedule", "pattern"} <= set(source):
            raise ValueError(f"device {index} has invalid fields")
        device_type = source["type"]
        if device_type not in {"gpio", "pwm"}:
            raise ValueError(f"device {index} has unsupported type: {device_type}")
        pin = _integer(source["pin"], f"device {index} pin", minimum=0, maximum=29)
        if pin in pins:
            raise ValueError(f"duplicate pin: {pin}")
        pins.add(pin)
        device_id = source.get("id")
        if device_id is not None:
            if not isinstance(device_id, str) or not device_id:
                raise ValueError(f"device {index} id must be a non-empty string")
            if device_id in ids:
                raise ValueError(f"duplicate device id: {device_id}")
            ids.add(device_id)
        current_t = _integer(source["current_t"], f"device {index} current_t", minimum=0)
        reschedule = _integer(source["reschedule"], f"device {index} reschedule", minimum=0, maximum=1)
        if not isinstance(source["pattern"], list) or not source["pattern"]:
            raise ValueError(f"device {index} pattern must be a non-empty list")
        pattern = []
        for step_index, source_step in enumerate(source["pattern"]):
            if not isinstance(source_step, dict) or set(source_step) != {"val", "dur"}:
                raise ValueError(f"device {index} pattern {step_index} must contain val and dur")
            maximum = 1 if device_type == "gpio" else 65535
            value = _integer(source_step["val"], f"device {index} pattern {step_index} val", minimum=0, maximum=maximum)
            duration = _integer(source_step["dur"], f"device {index} pattern {step_index} dur", minimum=1)
            pattern.append({"val": value, "dur": duration})
        item = {"type": device_type, "pin": pin, "current_t": current_t,
                "reschedule": reschedule, "pattern": pattern}
        if device_id is not None:
            item["id"] = device_id
        normalized.append(item)
    return {"devices": normalized}


def firmware_identity(report: Any) -> FirmwareIdentity | None:
    """Return identity for a valid new report; return None for a legacy report."""
    content = report.get("content") if isinstance(report, dict) else None
    raw = content.get("firmware") if isinstance(content, dict) else None
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("report firmware must be an object")
    name, revision, protocol = raw.get("name"), raw.get("revision"), raw.get("protocol")
    if not isinstance(name, str) or not isinstance(revision, str):
        raise ValueError("report firmware name and revision must be strings")
    protocol = _integer(protocol, "report firmware protocol", minimum=1)
    return FirmwareIdentity(name, revision, protocol)


def report_matches_state(report: Any, state: Any) -> bool:
    """Compare normalized id/type/pin/reschedule/pattern fields in stable order."""
    expected = normalize_scheduler_state(state)["devices"]
    content = report.get("content") if isinstance(report, dict) else None
    devices = content.get("devices") if isinstance(content, dict) else None
    if not isinstance(devices, list) or len(devices) != len(expected):
        return False
    fields = ("id", "type", "pin", "reschedule", "pattern")
    observed = [{key: item.get(key) for key in fields if key in item}
                for item in devices if isinstance(item, dict)]
    static_expected = [{key: item[key] for key in fields if key in item}
                       for item in expected]
    return observed == static_expected
```

Do not copy the large validator into a second layer. In Task 5, `plamp_web.server.validate_timer_state()` will delegate to this function and add `report_every` only to its host response.

- [ ] **Step 4: Run focused tests**

Run the Step 2 command. Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add plamp/scheduler_state.py plamp/pico_protocol.py plamp/__init__.py \
  tests/test_scheduler_state.py tests/test_plamp_pico_protocol.py
git commit -m "Add shared scheduler state contract"
```

---

### Task 2: Generic persistent Pico firmware

**Files:**
- Modify: `pico_scheduler/generator.py`
- Modify: `pico_scheduler/templates/base.py.tmpl`
- Delete: `pico_scheduler/templates/gpio_device.py.tmpl`
- Delete: `pico_scheduler/templates/pwm_device.py.tmpl`
- Modify: `tests/test_pico_scheduler_generator.py`
- Create: `tests/test_pico_scheduler_runtime.py`

**Interfaces:**
- Consumes: `firmware_revision: str`, `GeneratorOptions`, and generation-numbered `/plamp_state_a.json` and `/plamp_state_b.json` files created by the host or firmware.
- Produces: schedule-independent `generate_main_py(firmware_revision, options) -> str`; report identity; runtime `configure` command.

- [ ] **Step 1: Write failing generator contract tests**

Replace schedule-embedded expectations with:

```python
text = generate_main_py(firmware_revision="abc1234", options=GeneratorOptions())
self.assertIn('FIRMWARE_REVISION = "abc1234"', text)
self.assertIn("FIRMWARE_PROTOCOL = 2", text)
self.assertIn('STATE_PATHS = ("/plamp_state_a.json", "/plamp_state_b.json")', text)
self.assertIn('message["type"] == "configure"', text)
self.assertNotIn("Pin(15, Pin.OUT)", text)
self.assertNotIn("Generator input:", text)
```

Add a second call with the same revision but different host context and assert byte-for-byte equality. The generic application must not accept controller ID, generated time, or schedule state as inputs.

- [ ] **Step 2: Write failing runtime behavior tests**

Create a small generated-firmware harness in `tests/test_pico_scheduler_runtime.py` that supplies fake `machine.Pin`, `machine.PWM`, `select.poll`, stdin, and a temporary state path before executing the generated source with `__name__="pico_test"`.

Prove these behaviors independently:

```python
runtime.handle_message({"type": "configure", "content": valid_state})
self.assertEqual(json.loads(state_path.read_text()), valid_state)
self.assertEqual(fake_pin.value(), 1)
self.assertEqual(json.loads(output.lines[-1])["type"], "report")

before = state_path.read_text()
runtime.handle_message({"type": "configure", "content": duplicate_pin_state})
self.assertEqual(state_path.read_text(), before)
self.assertEqual(json.loads(output.lines[-1])["type"], "error")
```

Patch the helpers in another test to record call order and assert `persist`, then `build_outputs`, then `replace_devices`, then `apply`, then `report`. Test boot with two valid generations (newest wins), a torn newest generation (older valid state wins), no state, GPIO/PWM replacement, command length overflow, pulse rejection while already on, and pulse completion restoration to the configured base device.

- [ ] **Step 3: Run generator/runtime tests and verify RED**

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m unittest \
  tests.test_pico_scheduler_generator tests.test_pico_scheduler_runtime -v
```

Expected: failures because firmware is still schedule-generated and has no configure handler.

- [ ] **Step 4: Implement the generic firmware**

Change the generator boundary to:

```python
def generate_main_py(*, firmware_revision: str, options: GeneratorOptions) -> str:
    return _template("base.py.tmpl").format(
        firmware_revision=json.dumps(firmware_revision),
        firmware_protocol=2,
        loop_sleep_ms=options.loop_sleep_ms,
        pwm_freq=options.pwm_freq,
    ).rstrip() + "\n"
```

In the template:

- Load and validate both `STATE_PATHS` at boot, choosing the valid document with the highest non-negative integer `generation`; use generation 0 with no devices if neither file is valid.
- Validate received JSON without mutating active devices.
- Build replacement Pin/PWM objects only after persistence succeeds, but before swapping `devices`; a persistence error therefore cannot disturb current outputs.
- Persist `{generation: active_generation + 1, devices: normalized_devices}` to the inactive state path, flush/close, call `os.sync()`, and only then make it the active in-memory generation. Never truncate the currently active slot.
- Parse both existing `r`/`p PIN SECONDS` text commands and a JSON `configure` message.
- Raise the command-buffer cap from 80 bytes to an explicit `MAX_COMMAND_BYTES = 16384`; overflow clears the buffer and emits one error.
- Include `{name, revision, protocol}` in every report.
- Keep the firmware silent except for requested reports, configure results, pulse start reports, and errors.

- [ ] **Step 5: Run focused tests**

Run the Step 3 command. Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add pico_scheduler/generator.py pico_scheduler/templates \
  tests/test_pico_scheduler_generator.py tests/test_pico_scheduler_runtime.py
git commit -m "Make Pico scheduler runtime configurable"
```

---

### Task 3: Verified serial configuration with lost-reply recovery

**Files:**
- Modify: `plamp/pico_transport.py`
- Modify: `plamp/__init__.py`
- Modify: `tests/test_plamp_pico_transport.py`

**Interfaces:**
- Consumes: normalized state from Task 1 and an already locked `PicoOperation`.
- Produces: `PicoOperation.configure(state) -> PicoExchange` and `PicoClient.configure(state, timeout) -> PicoExchange`.

- [ ] **Step 1: Write failing configure tests**

Add tests proving the exact wire document and recovery behavior:

```python
state = {"devices": [{
    "id": "lights", "type": "gpio", "pin": 2, "current_t": 0,
    "reschedule": 1, "pattern": [{"val": 1, "dur": 10}],
}]}
report = b'{"type":"report","content":{"devices":[{"id":"lights","type":"gpio","pin":2,"elapsed_t":0,"cycle_t":0,"current_value":1,"reschedule":1,"pattern":[{"val":1,"dur":10}]}]}}\n'
result = PicoClient("PICO-A", lock_dir=Path(tmp), serial_factory=factory,
                    port_finder=lambda _: "/dev/ttyACM0").configure(state, timeout=.2)
self.assertEqual(json.loads(first.writes[0].strip()), {"type": "configure", "content": state})
self.assertEqual(result.message["type"], "report")
```

For lost reply, let the first serial connection time out after writing configure and the second return a matching `r` report. Assert writes are exactly one configure and one `r`, never two configure documents. Add cases where the recovery report differs and where the Pico returns structured `type=error`; both raise `PicoCommandError` with raw evidence retained.

- [ ] **Step 2: Run focused tests and verify RED**

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m unittest \
  tests.test_plamp_pico_transport.PicoTransportTests.test_configure_writes_one_json_document \
  tests.test_plamp_pico_transport.PicoTransportTests.test_configure_recovers_lost_reply_with_report \
  tests.test_plamp_pico_transport.PicoTransportTests.test_configure_rejects_mismatched_recovery_report -v
```

Expected: `PicoClient` has no `configure` method.

- [ ] **Step 3: Implement configure under one lock and deadline**

Add an exchange helper that accepts an object without string reconstruction:

```python
def configure(self, state: dict[str, Any]) -> PicoExchange:
    command = json.dumps(
        {"type": "configure", "content": normalize_scheduler_state(state)},
        separators=(",", ":"),
    )
    try:
        # Reserve half the remaining operation budget for a proof report.
        response_timeout = min(0.5, self.remaining() / 2)
        result = self.exchange(
            command,
            accepted_types={"report", "error"},
            timeout=response_timeout,
        )
    except PicoReportTimeout as first:
        result = self.report()
        result = PicoExchange(result.message, result.port, first.raw_lines + result.raw_lines)
    if result.message.get("type") == "error":
        raise PicoCommandError(_error_message(result.message), raw_lines=result.raw_lines)
    if not report_matches_state(result.message, state):
        raise PicoCommandError("Pico report does not match configured state", raw_lines=result.raw_lines)
    return result
```

Keep the whole configure/recovery flow inside one `PicoClient.operation()` so another CLI or service process cannot interleave. Extend `PicoCommandError` to expose `raw_lines` without changing its concise string.

- [ ] **Step 4: Run transport tests**

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m unittest tests.test_plamp_pico_transport -v
```

Expected: all transport tests pass.

- [ ] **Step 5: Commit**

```bash
git add plamp/pico_transport.py plamp/__init__.py tests/test_plamp_pico_transport.py
git commit -m "Configure Pico state through serial"
```

---

### Task 4: Two-file firmware upgrade and revision selection

**Files:**
- Create: `plamp/pico_firmware.py`
- Modify: `plamp/pico_transport.py`
- Modify: `plamp/__init__.py`
- Create: `tests/test_pico_firmware.py`
- Modify: `tests/test_plamp_pico_transport.py`

**Interfaces:**
- Consumes: repo root, generic generated `main.py`, current normalized state, mpremote runner, and a locked operation.
- Produces: `firmware_revision(repo_root)`, `render_scheduler_firmware(repo_root)`, and `PicoOperation.upgrade_scheduler(main_path, state_path, expected, command_runner, interrupter, mpremote)`.

- [ ] **Step 1: Write failing revision tests**

Use an injected Git runner rather than creating commits in tests:

```python
self.assertEqual(
    firmware_revision(Path("/repo"), git_runner=lambda args, cwd: "abc1234\n"),
    "abc1234",
)
self.assertEqual(calls, [(["git", "log", "-1", "--format=%h", "--", "pico_scheduler"], Path("/repo"))])
```

Add a failure case that returns `unknown` only for a source archive without Git metadata; production schedule transactions must reject `unknown` as non-upgradable rather than claiming current firmware.

- [ ] **Step 2: Write failing two-file upgrade tests**

Extend the fake mpremote test to assert this exact order while holding one process lock:

```text
interrupt current port
mpremote connect PORT resume cp STATE :plamp_state_a.json
mpremote connect PORT resume cp STATE :plamp_state_b.json
mpremote connect PORT resume cp MAIN :main.py
mpremote connect PORT reset
rediscover
r
```

Both remote state slots receive the same validated generation-1 seed, so an older slot can never outrank the migration state. The final report must contain the expected identity and devices matching the copied current state. Test each failed copy/reset stage and an identity mismatch after reconnect; `PicoFlashError.step` must be `state-a`, `state-b`, `firmware`, `reset`, or `verify`.

- [ ] **Step 3: Run focused tests and verify RED**

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m unittest \
  tests.test_pico_firmware \
  tests.test_plamp_pico_transport.PicoTransportTests.test_scheduler_upgrade_copies_state_before_firmware \
  tests.test_plamp_pico_transport.PicoTransportTests.test_scheduler_upgrade_rejects_wrong_identity -v
```

Expected: modules/methods are absent.

- [ ] **Step 4: Implement firmware rendering and upgrade**

Expose:

```python
def run_git(args: list[str], cwd: Path) -> str:
    return subprocess.check_output(args, cwd=cwd, text=True, stderr=subprocess.DEVNULL).strip()


def firmware_revision(repo_root: Path, *, git_runner=run_git) -> str:
    try:
        value = git_runner(
            ["git", "log", "-1", "--format=%h", "--", "pico_scheduler"],
            repo_root,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return value or "unknown"

def render_scheduler_firmware(repo_root: Path) -> tuple[str, str]:
    revision = firmware_revision(repo_root)
    return revision, generate_main_py(
        firmware_revision=revision,
        options=GeneratorOptions(),
    )
```

Refactor `flash_main()` through the new operation-level upgrade method rather than keeping two divergent reconnect loops. Serialize normalized current state to one local `plamp_state_seed.json` generation-1 document with no `report_every`, then copy that seed to both remote slots.

- [ ] **Step 5: Run focused and legacy flash tests**

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m unittest \
  tests.test_pico_firmware tests.test_plamp_pico_transport -v
```

Expected: all tests pass, including existing reconnect timing and raw-line retention.

- [ ] **Step 6: Commit**

```bash
git add plamp/pico_firmware.py plamp/pico_transport.py plamp/__init__.py \
  tests/test_pico_firmware.py tests/test_plamp_pico_transport.py
git commit -m "Upgrade generic Pico scheduler firmware"
```

---

### Task 5: Shared ensure-and-configure transaction

**Files:**
- Create: `plamp/pico_scheduler.py`
- Modify: `plamp/__init__.py`
- Create: `tests/test_plamp_pico_scheduler.py`

**Interfaces:**
- Consumes: `PicoClient`, current committed compiled state, proposed compiled state, expected firmware revision, and injected upgrade dependencies.
- Produces: `apply_scheduler_state(client, current_state, proposed_state, expected, upgrade, timeout) -> SchedulerApplyResult`, used unchanged by REST and direct CLI.

- [ ] **Step 1: Write failing orchestration tests**

Use a fake client operation recording `report`, `upgrade_scheduler`, and `configure`:

```python
result = apply_scheduler_state(
    client=fake_client,
    current_state=current,
    proposed_state=proposed,
    expected=FirmwareIdentity("pico_scheduler", "newrev", 2),
    upgrade=upgrade,
    timeout=60,
)
self.assertEqual(fake_operation.calls, ["report", "upgrade", "configure"])
self.assertTrue(result.upgraded)
self.assertEqual(result.report, proposed_report)
```

Add current-firmware case (`report`, `configure` only), legacy report case, protocol mismatch, revision mismatch, upgrade failure (configure never called), configure mismatch, and one-operation-lock assertion.

- [ ] **Step 2: Run tests and verify RED**

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m unittest tests.test_plamp_pico_scheduler -v
```

Expected: import failure because the orchestration module is absent.

- [ ] **Step 3: Implement the narrow orchestration boundary**

```python
@dataclass(frozen=True)
class SchedulerApplyResult:
    report: dict[str, Any]
    port: str
    upgraded: bool
    previous_identity: FirmwareIdentity | None
    identity: FirmwareIdentity
    raw_lines: tuple[bytes, ...]


def apply_scheduler_state(*, client: PicoClient, current_state: dict[str, Any],
                          proposed_state: dict[str, Any], expected: FirmwareIdentity,
                          upgrade: Callable[[PicoOperation, dict[str, Any], FirmwareIdentity], PicoExchange],
                          timeout: float) -> SchedulerApplyResult:
    with client.operation(timeout=timeout) as operation:
        before = operation.report()
        raw_lines = list(before.raw_lines)
        previous = firmware_identity(before.message)
        upgraded = previous != expected
        if upgraded:
            active = upgrade(operation, current_state, expected)
            raw_lines.extend(active.raw_lines)
        else:
            active = before
        if firmware_identity(active.message) != expected:
            raise PicoCommandError("Pico firmware identity does not match expected firmware")
        configured = operation.configure(proposed_state)
        raw_lines.extend(configured.raw_lines)
        identity = firmware_identity(configured.message)
        if identity != expected:
            raise PicoCommandError("Pico firmware changed during configuration")
        return SchedulerApplyResult(
            report=configured.message,
            port=configured.port,
            upgraded=upgraded,
            previous_identity=previous,
            identity=identity,
            raw_lines=tuple(raw_lines),
        )
```

Do not perform file writes, FastAPI conversion, or logging here. Preserve raw lines from report, upgrade, configure, and recovery in order.

- [ ] **Step 4: Run focused tests**

Run the Step 2 command. Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add plamp/pico_scheduler.py plamp/__init__.py tests/test_plamp_pico_scheduler.py
git commit -m "Orchestrate verified scheduler configuration"
```

---

### Task 6: Replace REST schedule flashing with shared transaction

**Files:**
- Modify: `plamp_web/server.py`
- Modify: `tests/test_config_api.py`
- Modify: `tests/test_pages.py`

**Interfaces:**
- Consumes: `apply_scheduler_state()` from Task 5 and existing semantic `compile_controller_state()`.
- Produces: unchanged `POST /api/controllers/{controller}/schedule` public request shape with runtime configuration response and SSE health/report updates.

- [ ] **Step 1: Write failing REST transaction tests**

Replace the flash-centric schedule assertions with:

```python
with (
    patch.object(server, "apply_scheduler_state", return_value=result) as apply,
    patch.object(server, "write_config_file") as write_config,
    patch.object(server, "atomic_write_json") as write_state,
):
    response = server.post_controller_schedule("pump_lights", proposed)

apply.assert_called_once()
self.assertFalse(response["firmware_upgraded"])
self.assertEqual(response["message"], "schedule verified, saved, and applied")
self.assertLess(apply.call_args_list[0], write_config.call_args_list[0])
```

Use an ordered mock recorder rather than comparing unrelated mock objects. Prove host files are untouched on report, upgrade, configure, and verification errors. Prove legacy firmware invokes upgrade exactly once, the proposed schedule is not used as migration state, successful runtime changes never invoke `mpremote`, and per-channel compatibility endpoint delegates to the same controller transaction.

Add a monitor/status test proving a valid legacy or different-revision report remains health `OK` but exposes:

```json
{"firmware":{"current":false,"expected":{"name":"pico_scheduler","revision":"newrev","protocol":2},"observed":null}}
```

A matching report sets `current` true. Neither report path invokes upgrade; only the schedule transaction does.

- [ ] **Step 2: Run selected tests and verify RED**

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m unittest \
  tests.test_config_api.ConfigApiTests.test_controller_schedule_uses_runtime_configuration \
  tests.test_config_api.ConfigApiTests.test_controller_schedule_upgrades_current_state_before_proposal \
  tests.test_config_api.ConfigApiTests.test_controller_schedule_failure_leaves_files_unchanged -v
```

Expected: failures because the endpoint still calls `apply_timer_state()`/flash.

- [ ] **Step 3: Delegate host validation to the shared state validator**

Keep the HTTP compatibility wrapper but remove its duplicate device validator:

```python
def validate_timer_state(raw: Any) -> dict[str, Any]:
    report_every = require_int(raw.get("report_every", 1), "report_every must be an integer")
    if report_every <= 0:
        raise HTTPException(status_code=422, detail="report_every must be > 0")
    try:
        pico_state = normalize_scheduler_state(raw)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"report_every": report_every, "devices": pico_state["devices"]}
```

`report_every` remains readable as legacy host configuration during this slice but never enters firmware or controls five-second health polling. Do not restore its settings-page control.

- [ ] **Step 4: Replace flash-and-commit with configure-and-commit**

Within the existing controller/config locks:

1. Compile current committed semantic configuration at the current host time.
2. Compile the proposed semantic configuration at the same captured host time.
3. Render/stage generic firmware and current state only for the injected upgrade callback.
4. Call `apply_scheduler_state()` once.
5. Record the returned exchange through `PicoMonitor` so SSE and health update immediately.
6. Atomically replace staged host config and applied state.

Map library exceptions once at the adapter boundary: unavailable `409`, validation `422`, serial/upgrade/protocol `502`, and exhausted report budget `504`, always including structured health/raw-line evidence.

- [ ] **Step 5: Update UI/API example wording**

Keep the schedule request body unchanged. Change success copy from “verified flash” to “verified Pico apply”; show `firmware_upgraded` and returned firmware identity. Do not add a second browser request or wait.

- [ ] **Step 6: Run REST and page suites**

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m unittest \
  tests.test_config_api tests.test_pages tests.test_timer_schedule -v
```

Expected: all tests pass and no schedule test expects ordinary flashing.

- [ ] **Step 7: Commit**

```bash
git add plamp_web/server.py tests/test_config_api.py tests/test_pages.py
git commit -m "Apply schedules without reflashing Pico"
```

---

### Task 7: Direct CLI configure and upgrade adapters

**Files:**
- Modify: `plamp/cli.py`
- Modify: `tests/test_plamp_direct_cli.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: Task 3 configure and Task 4 upgrade operations, resolved `PLAMP_ROOT`/`PLAMP_DATA_DIR`, and compiled state JSON supplied by the caller.
- Produces: `plamp pico configure CONTROLLER STATE.json` and `plamp pico upgrade CONTROLLER STATE.json`.

- [ ] **Step 1: Write failing CLI tests**

```python
rc = main(
    ["pico", "configure", "tower", str(state_file)],
    env=self.runtime_env(root), stdout=stdout, stderr=stderr,
    configure_func=fake_configure,
)
self.assertEqual(rc, 0)
self.assertEqual(calls[0][0], "PICO-A")
self.assertEqual(calls[0][1], json.loads(state_file.read_text()))
```

Add stdin `-`, invalid JSON exit 2, hardware failure exit 4, upgrade success including old/new identity, and help text. Neither command may contact `plamp-web`.

- [ ] **Step 2: Run direct CLI tests and verify RED**

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m unittest tests.test_plamp_direct_cli -v
```

Expected: argparse rejects `configure` and `upgrade`.

- [ ] **Step 3: Add thin direct CLI adapters**

Add subparsers:

```python
configure = actions.add_parser("configure")
configure.add_argument("controller")
configure.add_argument("state_file")
upgrade = actions.add_parser("upgrade")
upgrade.add_argument("controller")
upgrade.add_argument("state_file")
```

Read/parse the state exactly like `config write`, normalize it before hardware access, call the injected library function, print stable sorted JSON, and keep diagnostics on stderr. The direct CLI must not import `plamp_web.server`.

- [ ] **Step 4: Run CLI tests**

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m unittest \
  tests.test_plamp_direct_cli tests.test_plamp_cli -v
```

Expected: all direct and REST-backed compatibility CLI tests pass.

- [ ] **Step 5: Commit**

```bash
git add plamp/cli.py tests/test_plamp_direct_cli.py README.md
git commit -m "Expose direct Pico configuration commands"
```

---

### Task 8: Documentation, full verification, and deferred hardware gate

**Files:**
- Modify: `docs/spec-current.md`
- Modify: `pico_scheduler/README.md`
- Modify: `plamp_web/README.md`
- Modify: `plamp_cli/README.md`
- Test: all test files changed above

**Interfaces:**
- Consumes: completed Tasks 1–7.
- Produces: accurate public architecture, verified branch, and a repeatable non-production hardware checklist.

- [ ] **Step 1: Update current-behavior documentation**

State plainly:

```text
Reports are demand-driven. Each report identifies Pico firmware and protocol.
Schedule changes send and verify one complete persisted runtime state.
Legacy or outdated firmware is upgraded once during the next schedule change.
Read-only health polling never upgrades firmware.
MicroPython provisioning remains a separate future operation.
```

Remove claims that every schedule change generates/flashes `main.py`. Keep migration direction items only for work that remains future.

- [ ] **Step 2: Run focused verification**

```bash
python3 -m py_compile plamp/*.py pico_scheduler/*.py plamp_web/*.py tests/*.py
UV_CACHE_DIR=/tmp/uv-cache uv run python -m unittest \
  tests.test_scheduler_state \
  tests.test_pico_scheduler_generator \
  tests.test_pico_scheduler_runtime \
  tests.test_plamp_pico_protocol \
  tests.test_plamp_pico_transport \
  tests.test_pico_firmware \
  tests.test_plamp_pico_scheduler \
  tests.test_config_api \
  tests.test_pages \
  tests.test_plamp_direct_cli -v
```

Expected: all focused tests pass.

- [ ] **Step 3: Run full verification**

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m unittest discover -s tests -q
git diff --check
git status --short
```

Expected: full suite passes, diff check prints nothing, and only intended documentation changes remain before commit.

- [ ] **Step 4: Commit and push the verified branch**

```bash
git add docs/spec-current.md pico_scheduler/README.md plamp_web/README.md plamp_cli/README.md
git commit -m "Document runtime Pico configuration"
git push origin feature/runtime-pico-config
```

- [ ] **Step 5: Stop at the physical hardware gate**

Do not deploy automatically while the user is away from the non-production machine. Record the exact branch revision and wait.

When hardware is available, use `plampctl` to deploy and `plamp-cli`/direct `plamp` for API/hardware operations. Capture evidence for:

1. Legacy firmware upgrade preserves the currently active schedule.
2. USB remove/add occurs once for migration and not for later schedules.
3. A second schedule change completes with one configure write and matching report.
4. Power-cycle reloads the persisted program and stored phase; the report and UI do not claim that a daily schedule remains aligned to wall time.
5. Invalid state leaves the previous output schedule active.
6. Pulse completion restores the runtime-configured base schedule.
7. Five-second successful health reports remain quiet at INFO.

Only after this evidence passes should the stacked controller-health and runtime-config branches be considered for merge and production deployment.
