# Plamp: Current Contract

Plamp is local-first hydroponics automation designed for humans and agents. Core schedules must continue with only Pico power. A Raspberry Pi adds monitoring, pictures, configuration, and remote access; Internet access is optional.

## Current System

- `plamp_web`: one FastAPI service providing REST, SSE, scheduled camera captures, Pico monitoring, and the fallback website.
- `plamp_cli`: explicitly named JSON-first REST compatibility client.
- `plamp`: shared hardware/domain library and the primary direct CLI used by the REST service and local operations.
- `pico_scheduler`: one generic, persistent, runtime-configurable MicroPython application.
- `data/`: desired configuration, generated controller state, logs, pictures, and other runtime data.

The web collector and direct CLI share per-device filesystem locks. Each transaction discovers the current tty, opens it, exchanges a complete message, and closes it.

## Configuration and State

`data/config.json` is the desired host configuration. Top-level groups are `controllers` and `cameras`.

Scheduler controllers normalize to:

```json
{
  "type": "pico_scheduler",
  "payload": {
    "pico_serial": "e66038b71387a039",
    "report_every": 10,
    "devices": []
  },
  "settings": {
    "devices": {
      "pump": {
        "pin": 15,
        "output_type": "gpio",
        "programming": "enabled",
        "visibility": "visible",
        "editor": {"kind": "cycle"}
      }
    }
  }
}
```

Controller IDs are unique. Device IDs are unique within a controller. Pins may not collide within a controller. The stable Pico USB serial identifies hardware; tty paths do not.

Observed reports describe runtime state. They do not replace desired configuration or host-only preferences.

Protocol 3 complete scheduler states require an `enabled` boolean for every base
device. Complete Pico reports include that field along with the device identity,
type, pin, schedule, phase, and current output value; partial telemetry fragments
are not a substitute for a complete report. Host configuration exposes the same
choice as semantic `programming: "enabled"` or `programming: "disabled"`.

## Interfaces

Agents should receive machine-readable JSON on stdout and diagnostics on stderr.

The primary `plamp` command calls the shared module directly and does not require the
REST service. Its hardware path includes:

```bash
plamp pico report <controller>
plamp pico pulse <controller> <pin> <seconds>
plamp pico configure <controller> <compiled-state.json>
plamp pico upgrade <controller> <compiled-state.json>
```

Inspect attached Pico serials and preview Plamp8 onboarding before authorizing any
mutation:

```bash
plamp controllers candidates
plamp controllers add plamp8 --serial <serial> --profile plamp8
plamp controllers add plamp8 --serial <serial> --profile plamp8 --provision --apply
```

`controllers candidates` enumerates Raspberry Pi USB serial/device pairs without
opening a candidate. Inspect the returned serials and pass the intended hardware
serial explicitly. The middle command obtains one complete report from only that
serial and returns a read-only JSON preview; it changes neither Pico firmware nor
host files. If the preview action is `import`, register the already provisioned
protocol 3 controller with `--apply` but without `--provision`. If the action is
`provision`, the last command is the explicit destructive authorization: it saves
the pre-provision report under
`$PLAMP_DATA_DIR/controller-backups/<controller>-<serial>-pre-provision.json`,
reflashes and resets the selected Pico, verifies the resulting protocol 3 report,
and then imports it. Confirm manual switches and connected loads are safe before
running it. `--provision` without `--apply` is rejected.

`python3 -m plamp_cli` remains an explicitly named REST compatibility client during
migration. It does not own the `plamp` command.

Primary HTTP surfaces:

- `/api/config`: persisted desired configuration
- `/api/system`: host facts and detected hardware
- `/api/status`: resolved state and telemetry, including SSE
- `/api/controllers`: controller reads and commands
- `/api/camera`: capture and image access

The web pages are replaceable REST/SSE clients, not the source of domain behavior.

## Firmware

The scheduler generator renders one generic `main.py` for a firmware source
revision. Controller identity, pins, devices, and schedules are not compiled
into it. Its build-time options are `loop_sleep_ms` (default `20`) and
`pwm_freq` (default `1000`); automatic rendering uses those defaults.

Schedule changes send and verify one complete persistent runtime state. A
legacy or outdated Pico is upgraded once during the next mutating schedule
transaction, using the committed state before applying the proposal. Read-only
reports never upgrade firmware, and ordinary schedule changes do not reset USB.

Scheduler protocol 3 persists and reports each base device's required `enabled`
state. The Pico itself enforces disabled outputs: GPIO and PWM are driven to zero,
their schedule phase does not advance, the state remains disabled after reboot,
and GPIO pulse requests are rejected. Disabling a channel with an active pulse
cancels that overlay and drives the output off immediately. Disabled base devices
remain present in complete reports with `enabled: false` and `current_value: 0`.

`pico_scheduler` is the only implemented firmware family. Dosing pumps attached
to Plamp8 use bounded GPIO pulses requested by a human, host algorithm, or
agent; the Pico ends each pulse locally and restores the configured base state.
A future pH, EC, or PPM measurement MCU requires a separate hardware-backed
protocol design rather than a placeholder family.

## Direction

The approved target is agent-first:

- one shared `plamp` library under the CLI and REST service;
- short cross-process-locked Pico and camera transactions;
- CLI usable locally or through SSH without the service;
- demand-driven full Pico reports with host-controlled polling;
- first-class MicroPython provisioning and application recovery;
- daily clock-drift detection and explicit reconciliation policy;
- a hardware-backed contract for any future measurement MCU;
- optional web apps using REST and SSE.

See [Agent-First Plamp Architecture](./superpowers/specs/2026-07-14-agent-first-plamp-architecture-design.md).

## Reliability Rules

- Do not require cloud access for schedules or recovery.
- Keep desired configuration separate from observed state.
- Do not store tty paths as hardware identity.
- Serialize access to each Pico and camera across processes.
- Prove firmware readiness with a valid protocol response, not a successful port open.
- Label planned behavior as direction until it ships.
