# Plamp8 Controller Provisioning and Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an explicitly authorized Plamp8 provisioning/import workflow with correct channel IDs, Pico-enforced disabled outputs, a clear web UX, and a first-class direct CLI.

**Architecture:** Extend the existing complete scheduler state with one required `enabled` Boolean and enforce it in the generic Pico firmware. Add one focused `plamp.controller_add` operation that previews or applies either read-only import or Plamp8 provisioning followed by import; direct CLI and REST are thin adapters over it. Keep complete reports, the existing upgrade primitive, and the current static pages.

**Tech Stack:** Python 3.11, MicroPython, pyserial, mpremote, FastAPI, vanilla HTML/JavaScript, OpenSCAD, JSON-lines serial protocol, `unittest`.

## Global Constraints

- Start from approved spec commit `df2854f` or from `main` after that spec is merged.
- Do not communicate with an unassigned Pico until the user explicitly invokes add/import inspection.
- Import may request a report but must not send a mutating command or change an output.
- Firmware/output mutation requires both `--provision` and `--apply` in the direct CLI and an explicit web confirmation.
- Use the exact Plamp8 mapping: GP21 `ph_up` disabled, GP20 `ph_down` disabled, GP19 `agitator` disabled, GP18 `nutrients` disabled, GP17 `pump` enabled, GP16 `fan` enabled, GP15 `lights_1` enabled, GP14 `lights_2` enabled.
- Disabled means Pico-enforced logical `0`, no schedule advancement, continued full reporting, persistence across reboot, and pulse rejection.
- The scheduler accepts only `gpio`; PWM state, configuration, reports, firmware paths, and UI options are rejected or removed without migration.
- Device IDs are lowercase snake case and are the only channel names; user-facing text replaces underscores with spaces and uppercases the first character.
- Remove only scheduled-device labels. Controller and camera labels remain.
- The Settings heading is exactly **Plamp Pico relay controllers**; `pico_scheduler` remains a diagnostics/protocol name.
- Keep complete reports. Do not add delta reports, checksums, plan files, confirmation tokens, automatic probing, arbitrary historical protocol support, or a general provisioning framework.
- Do not flash or reset the installed Plamp8 during implementation or automated verification. Hardware provisioning is a separately authorized final checkpoint.
- Use `apply_patch` for edits. Preserve the unrelated `.cache/` directory and all user changes.

---

### Task 1: Required enabled state in host contracts

**Files:**
- Modify: `plamp/scheduler_state.py`
- Modify: `plamp/hardware_config.py`
- Modify: `plamp_web/timer_schedule.py`
- Modify: `tests/test_scheduler_state.py`
- Modify: `tests/test_hardware_config.py`
- Modify: `tests/test_timer_schedule.py`
- Modify: `tests/test_plamp_pico_transport.py`
- Modify: `tests/test_pico_commands.py`
- Modify: `tests/test_plamp_pico_scheduler.py`
- Modify: `tests/test_plamp_direct_cli.py`
- Modify: `tests/test_config_api.py`

**Interfaces:**
- Consumes: semantic channel `programming` (`enabled` or `disabled`), complete scheduler device state, and optional fresh live devices keyed by pin.
- Produces: protocol 3 normalized devices with required `enabled: bool`; `compile_controller_state(channels, *, report_every, now=None, live_devices=None)` emits that field and preserves live phase when the compiled pattern is unchanged; `report_matches_state(...)` verifies it.

- [ ] **Step 1: Write failing host-contract tests**

Update the shared fixture and add these assertions:

```python
STATE = {
    "report_every": 5,
    "devices": [{
        "id": "lights", "type": "gpio", "pin": 2, "enabled": True,
        "current_t": 7, "reschedule": 1,
        "pattern": [{"val": 1, "dur": 10}, {"val": 0, "dur": 20}],
    }],
}

def test_rejects_device_without_enabled(self):
    device = dict(STATE["devices"][0])
    del device["enabled"]
    with self.assertRaisesRegex(ValueError, "enabled must be a boolean"):
        normalize_scheduler_state({"devices": [device]})

def test_report_comparison_includes_enabled(self):
    report = {"type": "report", "content": {"devices": [
        dict(STATE["devices"][0], enabled=False, elapsed_t=7, cycle_t=7, current_value=0)
    ]}}
    self.assertFalse(report_matches_state(report, STATE))
```

In `tests/test_timer_schedule.py`, add one enabled and one disabled semantic channel and assert the exact compiled fields:

```python
self.assertTrue(state["devices"][0]["enabled"])
self.assertFalse(state["devices"][1]["enabled"])
self.assertEqual(state["devices"][1]["pattern"], [
    {"val": 1, "dur": 1}, {"val": 0, "dur": 1},
])
```

Add a phase-preservation test:

```python
state = compile_controller_state(
    channels, report_every=10,
    live_devices=[{
        "id": "old_name", "pin": 3, "type": "gpio", "enabled": True,
        "cycle_t": 247, "current_value": 1,
        "pattern": [{"val": 1, "dur": 300}, {"val": 0, "dur": 2400}],
    }],
)
self.assertEqual(state["devices"][0]["id"], "pump")
self.assertEqual(state["devices"][0]["current_t"], 247)
```

In `tests/test_hardware_config.py`, assert compiled payload devices include `enabled`, with disabled semantic devices compiling to `False` while retaining their pattern.

- [ ] **Step 2: Run the focused tests and verify RED**

```bash
UV_CACHE_DIR=/tmp/uv-cache /home/hugo/.local/bin/uv run python -m unittest \
  tests.test_scheduler_state tests.test_hardware_config tests.test_timer_schedule -v
```

Expected: failures because `enabled` is unknown or absent and disabled semantic channels still compile like ordinary enabled devices.

- [ ] **Step 3: Implement the minimal shared state changes**

In `plamp/scheduler_state.py`, set protocol 3, require the Boolean, copy it into normalized output, and compare it:

```python
EXPECTED_FIRMWARE_PROTOCOL = 3

allowed = {"id", "type", "pin", "enabled", "current_t", "reschedule", "pattern"}
required = {"type", "pin", "enabled", "current_t", "reschedule", "pattern"}
if set(source) - allowed or not required <= set(source):
    raise ValueError(f"device {index} has invalid fields")
enabled = source["enabled"]
if not isinstance(enabled, bool):
    raise ValueError(f"device {index} enabled must be a boolean")
item = {
    "type": device_type,
    "pin": pin,
    "enabled": enabled,
    "current_t": current_t,
    "reschedule": reschedule,
    "pattern": pattern,
}
```

Change the comparison tuple to:

```python
fields = ("id", "type", "pin", "enabled", "reschedule", "pattern")
```

In `plamp_web/timer_schedule.py`, add the field in `_new_channel_device(...)`:

```python
"enabled": channel.get("programming", "enabled") != "disabled",
```

Support exact event patterns without inventing a daily window:

```python
elif kind == "events":
    device["pattern"] = list(editor.get("events", []))
    device["current_t"] = _as_int(editor.get("start_at_seconds", 0), "start_at_seconds")
```

Add `live_devices: list[dict[str, Any]] | None = None` to
`compile_controller_state`. After compiling each channel, match a live device by
pin; when its normalized pattern equals the compiled pattern, replace
`current_t` with non-negative `cycle_t` (falling back to `elapsed_t`). This
preserves phase across an ID-only or enabled-only edit without inferring a
schedule kind.

In `plamp/hardware_config.py`, include `enabled` in compiled and validated payload devices:

```python
output = {
    "pin": device["pin"],
    "type": device.get("output_type", "gpio"),
    "enabled": device.get("programming", "enabled") != "disabled",
}
```

Allow `start_at_seconds` on `events` editors and preserve it when present. Update `_validate_payload_device` to require `enabled: bool` and return it.

- [ ] **Step 4: Update existing scheduler fixtures mechanically**

Use `rg` to find complete device-state literals and add `enabled: True` where they describe active devices:

```bash
rg -n '"current_t"|"reschedule"' tests plamp --glob '*.py'
```

Do not add `enabled` to telemetry-only fragments that intentionally omit complete scheduler fields. Do not default missing complete-state values in production code.

- [ ] **Step 5: Run focused and shared scheduler tests**

```bash
UV_CACHE_DIR=/tmp/uv-cache /home/hugo/.local/bin/uv run python -m unittest \
  tests.test_scheduler_state tests.test_hardware_config tests.test_timer_schedule \
  tests.test_plamp_pico_transport tests.test_pico_commands tests.test_plamp_pico_scheduler -v
```

Expected: all selected tests pass with protocol 3 fixtures.

- [ ] **Step 6: Commit**

```bash
git add plamp/scheduler_state.py plamp/hardware_config.py plamp_web/timer_schedule.py \
  tests/test_scheduler_state.py tests/test_hardware_config.py tests/test_timer_schedule.py \
  tests/test_plamp_pico_transport.py tests/test_pico_commands.py tests/test_plamp_pico_scheduler.py \
  tests/test_plamp_direct_cli.py tests/test_config_api.py
git commit -m "Require enabled scheduler state"
```

---

### Task 2: Pico-enforced disabled outputs

**Files:**
- Modify: `pico_scheduler/src/generator.py`
- Modify: `pico_scheduler/src/templates/base.py.tmpl`
- Modify: `tests/test_pico_scheduler_generator.py`
- Modify: `tests/test_pico_scheduler_runtime.py`

**Interfaces:**
- Consumes: Task 1 complete state with required `enabled`.
- Produces: protocol 3 firmware that persists and reports `enabled`, holds disabled outputs at zero, freezes their phase, and rejects pulses.

- [ ] **Step 1: Make firmware test helpers explicit**

Change the runtime helper to require the state explicitly:

```python
def gpio(pin=2, value=1, current_t=0, *, enabled=True):
    return {
        "id": "lights",
        "type": "gpio",
        "pin": pin,
        "enabled": enabled,
        "current_t": current_t,
        "reschedule": 1,
        "pattern": [{"val": value, "dur": 10}],
    }
```

Remove obsolete positive-PWM fixtures; keep explicit GPIO-only rejection coverage.

- [ ] **Step 2: Write failing disabled-runtime tests**

Add independent tests covering configuration, ticking, reporting, boot, pulse, and active overlays:

```python
def test_disabled_gpio_is_off_and_phase_does_not_advance(self):
    firmware = self.harness()
    firmware.call("handle_message", {
        "type": "configure",
        "content": {"devices": [gpio(value=1, current_t=4, enabled=False)]},
    })
    self.assertEqual(firmware.pins[2].value(), 0)
    firmware.call("tick", 5)
    firmware.call("apply")
    self.assertEqual(firmware.runtime.devices[0]["elapsed_t"], 4)
    self.assertEqual(firmware.pins[2].value(), 0)
    reported = firmware.messages()[-1]["content"]["devices"][0]
    self.assertFalse(reported["enabled"])
    self.assertEqual(reported["current_value"], 0)

def test_disabled_gpio_rejects_pulse(self):
    firmware = self.harness()
    firmware.call("handle_message", {
        "type": "configure",
        "content": {"devices": [gpio(value=0, enabled=False)]},
    })
    firmware.call("handle_command", "p 2 5")
    self.assertEqual(firmware.pins[2].value(), 0)
    self.assertIn("disabled", firmware.messages()[-1]["content"])

def test_disabling_pin_cancels_active_pulse_and_turns_it_off(self):
    firmware = self.harness()
    firmware.call("handle_message", {
        "type": "configure", "content": {"devices": [gpio(value=0)]},
    })
    firmware.call("handle_command", "p 2 5")
    firmware.call("handle_message", {
        "type": "configure",
        "content": {"devices": [gpio(value=1, current_t=3, enabled=False)]},
    })
    self.assertEqual(len(firmware.runtime.devices), 1)
    self.assertEqual(firmware.pins[2].value(), 0)
```

Add boot-from-disabled-GPIO state assertions.

- [ ] **Step 3: Run firmware tests and verify RED**

```bash
UV_CACHE_DIR=/tmp/uv-cache /home/hugo/.local/bin/uv run python -m unittest \
  tests.test_pico_scheduler_generator tests.test_pico_scheduler_runtime -v
```

Expected: failures because firmware protocol remains 2 and runtime normalization rejects or ignores `enabled`.

- [ ] **Step 4: Implement required firmware behavior**

In `generator.py`, emit protocol 3:

```python
firmware_protocol=3,
```

In the template, require and preserve `enabled` in `normalize_state`, `build_outputs`, and `report_item`. Use this output rule in `apply()`:

```python
if not device.get("overlay") and not device["enabled"]:
    value = 0
else:
    cycle_t = device["elapsed_t"] % device["total_t"] if device["reschedule"] else device["elapsed_t"]
    elapsed = 0
    value = device["pattern"][-1]["val"]
    for step in device["pattern"]:
        elapsed += step["dur"]
        if cycle_t < elapsed:
            value = step["val"]
            break
```

Freeze disabled base devices in `tick(dt)`:

```python
if not device.get("overlay") and not device["enabled"]:
    continue
device["elapsed_t"] += dt
```

In `replace_devices`, retain an overlay only when its replacement base exists and is enabled. Rebind retained overlays to the replacement output. Let `apply()` immediately drive a newly disabled replacement to zero.

Reject a disabled base before checking whether it is already on:

```python
if not device["enabled"]:
    error("pulse pin is disabled")
    return
```

Overlay dictionaries do not need an `enabled` field because they are transient and are never normalized or reported as base configuration.

- [ ] **Step 5: Run firmware and transport verification**

```bash
UV_CACHE_DIR=/tmp/uv-cache /home/hugo/.local/bin/uv run python -m unittest \
  tests.test_pico_scheduler_generator tests.test_pico_scheduler_runtime \
  tests.test_scheduler_state tests.test_plamp_pico_transport -v
```

Expected: all selected tests pass and generated identity is protocol 3.

- [ ] **Step 6: Commit**

```bash
git add pico_scheduler/src/generator.py pico_scheduler/src/templates/base.py.tmpl \
  tests/test_pico_scheduler_generator.py tests/test_pico_scheduler_runtime.py
git commit -m "Enforce disabled outputs in Pico firmware"
```

---

### Task 3: Plamp8 profile, imported configuration, and channel names

**Files:**
- Create: `plamp/controller_add.py`
- Modify: `plamp/hardware_config.py`
- Modify: `plamp_web/timer_schedule.py`
- Modify: `things/plamp8/plamp8.scad`
- Create: `tests/test_controller_add.py`
- Modify: `tests/test_hardware_config.py`
- Modify: `tests/test_timer_schedule.py`

**Interfaces:**
- Consumes: a fresh complete report from protocol 2 or 3 and profile ID `plamp8`.
- Produces: `display_device_id(device_id: str) -> str`, `preview_controller_add(controller_id, pico_serial, report, expected_identity) -> dict`, `provisioned_plamp8_state(report) -> dict`, and `controller_config_from_report(pico_serial, report) -> dict`.

- [ ] **Step 1: Write the pure profile and conversion tests**

Create `tests/test_controller_add.py` with a report fixture whose pins are 21 through 14 and prototype IDs are `one` through `eight`. Assert the exact profile result:

```python
EXPECTED = [
    (21, "ph_up", False),
    (20, "ph_down", False),
    (19, "agitator", False),
    (18, "nutrients", False),
    (17, "pump", True),
    (16, "fan", True),
    (15, "lights_1", True),
    (14, "lights_2", True),
]

state = provisioned_plamp8_state(protocol_2_report())
self.assertEqual(
    [(item["pin"], item["id"], item["enabled"]) for item in state["devices"]],
    EXPECTED,
)
self.assertEqual(
    [item["pattern"] for item in state["devices"]],
    [item["pattern"] for item in protocol_2_report()["content"]["devices"]],
)
self.assertEqual(display_device_id("lights_1"), "Lights 1")
self.assertEqual(display_device_id("ph_up"), "Ph up")
```

Add cases for duplicate/missing profile pins, unsupported firmware family, a compatible protocol 3 report that previews `action: "import"`, and a protocol 2 report that previews `action: "provision"`.

Assert `controller_config_from_report(...)` maps `enabled` to semantic `programming`, preserves output type and pattern, uses a cycle editor only for a two-step positive/off pattern, and otherwise uses an `events` editor with captured phase.

- [ ] **Step 2: Run the pure tests and verify RED**

```bash
UV_CACHE_DIR=/tmp/uv-cache /home/hugo/.local/bin/uv run python -m unittest tests.test_controller_add -v
```

Expected: import failure because `plamp.controller_add` does not exist.

- [ ] **Step 3: Implement the one profile and pure transformations**

Create these immutable declarations in `plamp/controller_add.py`:

```python
from dataclasses import dataclass
from typing import Any

from plamp.scheduler_state import FirmwareIdentity, normalize_scheduler_state


@dataclass(frozen=True)
class ProfileChannel:
    pin: int
    device_id: str
    enabled: bool


PLAMP8_CHANNELS = (
    ProfileChannel(21, "ph_up", False),
    ProfileChannel(20, "ph_down", False),
    ProfileChannel(19, "agitator", False),
    ProfileChannel(18, "nutrients", False),
    ProfileChannel(17, "pump", True),
    ProfileChannel(16, "fan", True),
    ProfileChannel(15, "lights_1", True),
    ProfileChannel(14, "lights_2", True),
)


def display_device_id(device_id: str) -> str:
    text = device_id.replace("_", " ")
    return text[:1].upper() + text[1:]
```

`provisioned_plamp8_state(report)` must validate exactly eight unique profile pins, preserve `type`, `pattern`, `reschedule`, and captured `cycle_t`/`elapsed_t`, replace IDs by pin, add profile `enabled`, and return `normalize_scheduler_state({"devices": devices})`.

`controller_config_from_report(...)` must return only the existing normalized controller shape:

```python
{
    "type": "pico_scheduler",
    "payload": {"pico_serial": pico_serial, "report_every": 10},
    "settings": {"devices": semantic_devices},
}
```

Each semantic device contains `pin`, `output_type`, `display_order`, `visibility: "visible"`, `programming`, and `editor`; it contains no `label`.

`preview_controller_add(...)` returns a compact JSON-ready dictionary with `controller`, `serial`, `profile`, `action`, observed/expected identity, `requires_reset`, and ordered `before`/`after` channel rows. Do not create a generic profile registry; reject any profile other than `plamp8`.

- [ ] **Step 4: Remove scheduled-device labels and humanize display**

In `plamp/hardware_config.py`, continue accepting an incoming `label` key so an existing config can be read, but do not copy it into normalized semantic devices. Remove device-label propagation from legacy conversion.

In `plamp_web/timer_schedule.py`, use the shared display function:

```python
"name": display_device_id(device_id),
```

Update tests so `pump` is displayed as `Pump`, `ph_up` as `Ph up`, and normalized device configuration omits an incoming scheduled-device label.

- [ ] **Step 5: Correct the two stale CAD names directly**

Use the `openscad-cad` skill for this step. Change only the AC label strings:

```scad
ac_devices = ["Pump", "Lights 1", "Fan", "Lights 2"];
```

Keep `ac_details` and every floor/panel dimension unchanged. Do not add a parser, generator, or CAD contract test.

- [ ] **Step 6: Run pure, config, timer, and CAD syntax checks**

```bash
UV_CACHE_DIR=/tmp/uv-cache /home/hugo/.local/bin/uv run python -m unittest \
  tests.test_controller_add tests.test_hardware_config tests.test_timer_schedule -v
openscad -o /tmp/plamp8-profile-check.stl \
  -D 'view="top_panel"' things/plamp8/plamp8.scad
```

Expected: unit tests pass and OpenSCAD exits 0. Do not retain `/tmp/plamp8-profile-check.stl` as a repository artifact.

- [ ] **Step 7: Commit**

```bash
git add plamp/controller_add.py plamp/hardware_config.py plamp_web/timer_schedule.py \
  things/plamp8/plamp8.scad tests/test_controller_add.py \
  tests/test_hardware_config.py tests/test_timer_schedule.py
git commit -m "Add canonical Plamp8 controller profile"
```

---

### Task 4: One add-controller operation and direct agent CLI

**Files:**
- Modify: `plamp/controller_add.py`
- Modify: `plamp/config.py`
- Modify: `plamp/cli.py`
- Modify: `plamp/__init__.py`
- Modify: `tests/test_controller_add.py`
- Modify: `tests/test_plamp_config.py`
- Modify: `tests/test_plamp_direct_cli.py`

**Interfaces:**
- Consumes: Task 3 preview/conversion helpers, existing `request_report(...)`, `upgrade_scheduler(...)`, `load_config(...)`, and stable Pico serial enumeration.
- Produces: `add_controller(controller_id, pico_serial, profile_id, *, apply, allow_provision, config_file, data_dir, repo_root, lock_dir, timeout, ...) -> dict`; direct `plamp controllers candidates` and `plamp controllers add` commands.

- [ ] **Step 1: Write failing add-operation tests**

Add tests with injected report and upgrade functions:

```python
result = add_controller(
    "plamp8", "PICO-A", "plamp8",
    apply=False, allow_provision=False,
    config_file=config_file, data_dir=data_dir, repo_root=root,
    lock_dir=data_dir / "locks", timeout=3,
    report_func=lambda *args, **kwargs: protocol_3_report(),
    upgrade_func=lambda *args, **kwargs: self.fail("preview must not upgrade"),
)
self.assertEqual(result["action"], "import")
self.assertFalse(result["hardware_changed"])
self.assertEqual(json.loads(config_file.read_text()), original_config)
```

Cover these cases independently:

- preview reads exactly once and changes neither hardware nor host files;
- compatible `apply=True` imports without calling upgrade;
- protocol 2 plus `apply=True, allow_provision=False` fails before mutation;
- protocol 2 plus both flags writes recovery evidence, calls upgrade with the exact mapped state, verifies the returned protocol 3 report, then imports;
- upgrade failure leaves host config unchanged and retains recovery evidence;
- an existing empty `plamp8` with the same serial is filled rather than duplicated;
- an existing non-empty controller or a serial assigned to another controller is rejected;
- exact imported runtime state is atomically saved to `data/timers/plamp8.json`;
- host config is committed only after report verification.

- [ ] **Step 2: Write failing direct CLI tests**

In `tests/test_plamp_direct_cli.py`, inject focused operations and assert:

```python
rc = main(
    ["controllers", "add", "plamp8", "--serial", "PICO-A", "--profile", "plamp8"],
    env=self.runtime_env(root), stdout=stdout, stderr=stderr,
    add_controller_func=fake_add,
)
self.assertEqual(rc, 0)
self.assertFalse(calls[0]["apply"])
self.assertFalse(calls[0]["allow_provision"])
self.assertEqual(stderr.getvalue(), "")
self.assertEqual(json.loads(stdout.getvalue())["action"], "provision")
```

Add cases for `--apply`, `--provision --apply`, rejecting `--provision` without `--apply`, compact JSON stdout, no prompt, and `controllers candidates` using only injected discovery.

- [ ] **Step 3: Run operation and CLI tests and verify RED**

```bash
UV_CACHE_DIR=/tmp/uv-cache /home/hugo/.local/bin/uv run python -m unittest \
  tests.test_controller_add tests.test_plamp_config tests.test_plamp_direct_cli -v
```

Expected: missing add operation and CLI parser failures.

- [ ] **Step 4: Add one reusable atomic JSON writer**

In `plamp/config.py`, extract the existing temporary-file/fsync/replace body without changing `save_config` behavior:

```python
def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", text=True,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(value, output, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
```

Make `save_config` validate and call this helper.

- [ ] **Step 5: Implement the single operation**

Add this public signature to `plamp/controller_add.py`:

```python
def add_controller(
    controller_id: str,
    pico_serial: str,
    profile_id: str,
    *,
    apply: bool,
    allow_provision: bool,
    config_file: Path,
    data_dir: Path,
    repo_root: Path,
    lock_dir: Path,
    timeout: float,
    report_func: Callable[..., dict[str, Any]] = request_report,
    upgrade_func: Callable[..., dict[str, Any]] = upgrade_scheduler,
) -> dict[str, Any]:
```

The function obtains one fresh report and preview. If `apply` is false, return the preview. If the preview requires provisioning and `allow_provision` is false, raise `ConfigError("controller requires explicit --provision")`.

Before upgrade, atomically write the fresh report to:

```python
data_dir / "controller-backups" / f"{controller_id}-{pico_serial}-pre-provision.json"
```

Call existing `upgrade_scheduler(...)` with `provisioned_plamp8_state(report)`. Verify the returned identity and report by recomputing a preview and requiring `action == "import"`. For direct import, use the original compatible fresh report. Under the shared config lock, merge `controller_config_from_report(...)`, atomically save config, and atomically save normalized reported state to `data_dir / "timers" / f"{controller_id}.json"`.

Use `exclusive_lock(lock_dir / "config.lock", timeout=timeout)` around the
load/merge/write portion. Keep the Pico operation outside that config critical
section so a slow reset does not block unrelated configuration reads.

Return the preview fields plus:

```python
{
    "hardware_changed": action == "provision",
    "host_config_changed": True,
    "reset": action == "provision",
    "verified": True,
    "recovery_path": recovery_path_or_none,
}
```

Do not add a generic action dispatcher, profile registry, plan persistence, or background worker.

- [ ] **Step 6: Add the direct CLI adapter**

Extend `plamp/cli.py` with one `controllers` area:

```python
controllers = areas.add_parser("controllers")
controller_actions = controllers.add_subparsers(dest="action", required=True)
controller_actions.add_parser("candidates")
add = controller_actions.add_parser("add")
add.add_argument("controller")
add.add_argument("--serial", required=True)
add.add_argument("--profile", choices=("plamp8",), required=True)
add.add_argument("--apply", action="store_true")
add.add_argument("--provision", action="store_true")
```

Reject `--provision` without `--apply` before calling hardware. `candidates` serializes `discover_picos()` as dictionaries. `add` calls the shared function with context paths and flags. Keep the existing compact sorted JSON output and error handling.

- [ ] **Step 7: Run operation, CLI, and existing direct hardware tests**

```bash
UV_CACHE_DIR=/tmp/uv-cache /home/hugo/.local/bin/uv run python -m unittest \
  tests.test_controller_add tests.test_plamp_config tests.test_plamp_direct_cli \
  tests.test_pico_commands tests.test_plamp_pico_discovery -v
```

Expected: all selected tests pass; no test touches real serial hardware.

- [ ] **Step 8: Commit**

```bash
git add plamp/controller_add.py plamp/config.py plamp/cli.py plamp/__init__.py \
  tests/test_controller_add.py tests/test_plamp_config.py tests/test_plamp_direct_cli.py
git commit -m "Add explicit Plamp8 controller workflow"
```

---

### Task 5: Thin REST endpoint and conventional web UX

**Files:**
- Modify: `plamp_web/server.py`
- Modify: `plamp_web/static/settings.html`
- Modify: `plamp_web/static/settings.js`
- Modify: `plamp_web/static/controller.html`
- Modify: `plamp_web/static/controller.js`
- Modify: `tests/test_config_api.py`
- Modify: `tests/test_pages.py`

**Interfaces:**
- Consumes: Task 4 `add_controller(...)`, `/api/system` candidate metadata, and existing controller telemetry containing `last_report`.
- Produces: `POST /api/controllers/{controller}/add`; Settings candidate/add preview; controller-page configured/observed/empty/unavailable states.

- [ ] **Step 1: Write failing REST adapter tests**

Add API tests that patch the shared operation and prove exact flag/path forwarding:

```python
with patch.object(server, "add_controller", return_value={"action": "import"}) as add:
    result = server.post_controller_add("plamp8", {
        "serial": "PICO-A", "profile": "plamp8",
        "apply": False, "provision": False,
    })
self.assertEqual(result, {"action": "import"})
self.assertEqual(add.call_args.args[:3], ("plamp8", "PICO-A", "plamp8"))
self.assertFalse(add.call_args.kwargs["apply"])
self.assertFalse(add.call_args.kwargs["allow_provision"])
```

Add validation cases for missing serial, unsupported profile, `provision` without `apply`, and shared-operation errors preserving a clear HTTP detail without creating a monitor first.

Add a schedule-transaction regression test in which a fresh report has
`cycle_t: 247`, the proposed controller only renames the channel or changes
`programming`, and the state passed to `apply_scheduler_state` retains
`current_t: 247` and the unchanged pattern.

- [ ] **Step 2: Write failing static-page contract tests**

In `tests/test_pages.py`, assert exact user-facing behavior:

```python
self.assertIn("Plamp Pico relay controllers", settings_html)
self.assertNotIn("Pico schedulers", settings_html)
self.assertNotIn('class="device-label"', settings_script)
self.assertNotIn("<th>Label</th><th>Pin</th>", settings_script)
self.assertIn("Add/import controller", settings_script)
self.assertIn("Upgrade, provision, and import", settings_script)
self.assertIn("N channels found on controller", controller_script)
self.assertIn("Controller reports 0 channels", controller_script)
self.assertIn("Unable to read controller configuration", controller_script)
self.assertNotIn("No configured pins.", controller_script)
```

Also assert zero-device configured controllers are rendered rather than moved into `hiddenControllers`, observed devices do not create usable pulse buttons, and disabled configured devices do not create usable pulse buttons.

- [ ] **Step 3: Run REST/page tests and verify RED**

```bash
UV_CACHE_DIR=/tmp/uv-cache /home/hugo/.local/bin/uv run python -m unittest \
  tests.test_config_api tests.test_pages -v
```

Expected: missing endpoint and old Settings/controller copy failures.

- [ ] **Step 4: Add the thin REST adapter**

Add one request model or strict dictionary validator and endpoint:

```python
@app.post("/api/controllers/{controller}/add")
def post_controller_add(controller: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    serial = payload.get("serial")
    profile = payload.get("profile")
    apply = payload.get("apply", False)
    provision = payload.get("provision", False)
    if not isinstance(serial, str) or not serial:
        raise HTTPException(status_code=422, detail="serial must be a non-empty string")
    if profile != "plamp8":
        raise HTTPException(status_code=422, detail="profile must be plamp8")
    if not isinstance(apply, bool) or not isinstance(provision, bool):
        raise HTTPException(status_code=422, detail="apply and provision must be booleans")
    if provision and not apply:
        raise HTTPException(status_code=422, detail="provision requires apply")
    return add_controller(
        controller, serial, profile,
        apply=apply, allow_provision=provision,
        config_file=CONFIG_FILE, data_dir=DATA_DIR, repo_root=REPO_ROOT,
        lock_dir=RUNTIME_CONTEXT.lock_dir, timeout=60.0 if provision else 3.0,
    )
```

Map known configuration/compatibility errors to 409 or 422 and hardware errors through the existing structured scheduler failure conventions. Do not duplicate mapping or firmware logic in `server.py`.

- [ ] **Step 5: Simplify Settings and add explicit preview/apply**

In `settings.html`, change the copy to:

```html
<p class="muted">Configure Plamp Pico relay controllers, channels, and cameras.</p>
<h3>Plamp Pico relay controllers</h3>
```

In `settings.js`:

- remove scheduled-device label input, collection, and table header;
- retain controller and camera labels;
- call devices **Channels**;
- render controllers even when their device list is empty;
- show each unassigned detected serial with **Add/import controller**;
- on click, POST `{serial, profile: "plamp8", apply: false, provision: false}`;
- render the returned before/after rows in one inline preview region;
- label the confirmation button **Import** for action `import` and **Upgrade, provision, and import** for action `provision`;
- POST again with `apply: true` and `provision: action === "provision"` only after explicit confirmation;
- show bounded progress, render returned error text, and navigate to `/controllers/{id}` only after verified success.

Change **Save devices** so each existing configured controller is submitted to
its existing verified `POST /api/controllers/{id}/schedule` transaction instead
of writing `/api/config` directly. Keep **Save controllers** host-only. The
server obtains a fresh report before compiling that channel-only metadata
change and passes its devices to Task 1 `compile_controller_state(...,
live_devices=...)`, preserving phase for every unchanged pattern. A disabled
edit therefore reaches and is verified by the Pico; an ID-only edit does not
reset an unchanged schedule.

Use ordinary DOM elements and one preview region. Do not add a framework, wizard router, plan token, or background job.

- [ ] **Step 6: Show observed channels correctly on controller pages**

In `controller.js`, add these pure extractors:

```javascript
function observedDevices(node) {
  const devices = node?.telemetry?.last_report?.content?.devices;
  return Array.isArray(devices) ? devices : [];
}

function displayDeviceId(id) {
  const text = String(id || "").replaceAll("_", " ");
  return text ? text[0].toUpperCase() + text.slice(1) : "";
}
```

Render one of four states:

- configured devices: heading **Configured channels** and configured rows;
- no configured devices plus observed rows: **N channels found on controller**, observed rows, and applicable add preview button;
- fresh report with empty devices: **Controller reports 0 channels**;
- no fresh valid report: **Unable to read controller configuration** plus health error.

Remove the redundant Name/Channel distinction: show derived display name, raw ID, pin, type, and enabled/programming status. Only configured, enabled GPIO rows receive a **Use** pulse button. A disabled row shows **Disabled** and cannot populate or submit pulse controls.

On SSE reports, refresh observed rows when the controller is not yet configured. Keep raw diagnostics and serial logs available.

- [ ] **Step 7: Run REST and page tests**

```bash
UV_CACHE_DIR=/tmp/uv-cache /home/hugo/.local/bin/uv run python -m unittest \
  tests.test_config_api tests.test_pages tests.test_timer_schedule -v
```

Expected: all selected tests pass.

- [ ] **Step 8: Commit**

```bash
git add plamp_web/server.py plamp_web/static/settings.html \
  plamp_web/static/settings.js plamp_web/static/controller.html \
  plamp_web/static/controller.js tests/test_config_api.py tests/test_pages.py
git commit -m "Add Plamp8 controller import UX"
```

---

### Task 6: Documentation, full verification, and hardware handoff

**Files:**
- Modify: `docs/spec-current.md`
- Modify: `plamp_cli/README.md`
- Modify: `README.md` only if it contains the Settings terminology or direct CLI command summary
- Test: complete repository test suite

**Interfaces:**
- Consumes: Tasks 1–5 completed behavior.
- Produces: current contract and operator/agent commands that match the shipped implementation.

- [ ] **Step 1: Update current documentation**

Document protocol 3 `enabled`, Pico-enforced disabled behavior, complete reports, explicit serial inspection, and the three direct CLI examples:

```bash
plamp controllers candidates
plamp controllers add plamp8 --serial <serial> --profile plamp8
plamp controllers add plamp8 --serial <serial> --profile plamp8 --provision --apply
```

State that the middle command is read-only preview, the last command reflashes/resets, and importing an already provisioned controller uses `--apply` without `--provision`.

- [ ] **Step 2: Run formatting and complete automated tests**

```bash
git diff --check
UV_CACHE_DIR=/tmp/uv-cache /home/hugo/.local/bin/uv run python -m unittest discover -s tests -v
```

Expected: `git diff --check` exits 0 and the complete suite reports zero failures and errors.

- [ ] **Step 3: Run non-mutating CLI smoke tests on Tower**

These commands must not use `--apply` or `--provision`:

```bash
bin/plamp controllers candidates
bin/plamp controllers add plamp8 \
  --serial 9d480174e373e801 --profile plamp8
bin/plamp pico report plamp8
```

Expected: candidates contains serial `9d480174e373e801`; add returns a JSON preview without changing host files; report remains valid. Record observed action and firmware identity. Do not proceed to hardware mutation.

- [ ] **Step 4: Review the implementation diff**

```bash
git diff --stat origin/main...HEAD
git diff --check origin/main...HEAD
git status --short
```

Expected: only planned files and the pre-existing untracked `.cache/` appear; no generated STL, firmware staging file, runtime config, timer state, or controller backup is committed.

- [ ] **Step 5: Commit documentation**

```bash
git add docs/spec-current.md plamp_cli/README.md README.md
git commit -m "Document Plamp8 controller provisioning"
```

If `README.md` did not require a change, omit it from `git add` rather than creating a cosmetic edit.

- [ ] **Step 6: Stop for explicit live-hardware authorization**

Report the automated test totals, preview JSON, expected firmware transition, exact four pins that will be forced off, recovery-evidence destination, and the command that would mutate hardware:

```bash
bin/plamp --timeout 60 controllers add plamp8 \
  --serial 9d480174e373e801 --profile plamp8 --provision --apply
```

Do not run it until the user explicitly approves that live action after confirming manual switch and connected-load safety.

- [ ] **Step 7: After separate authorization, verify the live transaction**

Run the exact authorized command once. Then verify read-only:

```bash
bin/plamp pico report plamp8
bin/plamp config get
```

Require protocol 3, IDs/pins matching the canonical table, GP21–GP18 `enabled: false` with `current_value: 0`, GP17/GP16/GP15/GP14 enabled with preserved patterns, and the imported `plamp8` host controller. If any verification fails, report the stage and recovery path; do not retry provisioning automatically.

---

## Final acceptance checklist

- [ ] Random attached Picos are enumerated but never opened automatically.
- [ ] Preview is read-only in web and direct CLI.
- [ ] Provisioning requires explicit mutation authorization.
- [ ] Complete reports require and include `enabled`.
- [ ] Disabled GPIO channels remain off, frozen, reported, reboot-safe, and unpulseable.
- [ ] Plamp8 IDs, pins, and initial enabled states exactly match the approved table.
- [ ] Existing enabled schedules are preserved by pin during provisioning.
- [ ] Import fills the existing empty `plamp8` controller and sends no mutating command.
- [ ] Settings says **Plamp Pico relay controllers** and has no scheduled-device label field.
- [ ] Dashboard/controller display derives names from lowercase snake-case IDs.
- [ ] Controller pages distinguish configured, observed, clean, and unavailable states.
- [ ] `Lights 1` and `Lights 2` replace stale CAD text without dimensional changes.
- [ ] Direct CLI works without `plamp-web`, emits JSON on stdout, and has no interactive prompt.
- [ ] Complete automated suite passes before any live Pico mutation.
