# Plamp: Current Contract

Plamp is local-first hydroponics automation designed for humans and agents. Core schedules must continue with only Pico power. A Raspberry Pi adds monitoring, pictures, configuration, and remote access; Internet access is optional.

## Current System

- `plamp_web`: one FastAPI service providing REST, SSE, scheduled camera captures, Pico monitoring, and the fallback website.
- `plamp_cli`: JSON-first REST client installed as `plamp`.
- `plamp`: emerging shared library and direct CLI; the first direct operation is `python -m plamp pico report`.
- `pico_scheduler`: host-generated MicroPython firmware.
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

## Interfaces

Agents should receive machine-readable JSON on stdout and diagnostics on stderr.

Current REST-backed operations use `python -m plamp_cli` or the installed `plamp` command. The direct path uses:

```bash
python -m plamp pico report <controller>
```

Primary HTTP surfaces:

- `/api/config`: persisted desired configuration
- `/api/system`: host facts and detected hardware
- `/api/status`: resolved state and telemetry, including SSE
- `/api/controllers`: controller reads and commands
- `/api/camera`: capture and image access

The web pages are replaceable REST/SSE clients, not the source of domain behavior.

## Firmware

The host validates scheduler state, generates controller-specific `main.py`, copies it with `mpremote`, resets the Pico, and reads reports over USB serial. Current schedule changes still regenerate and flash application code.

Provisioning MicroPython on a blank Pico, upgrading application code, and changing runtime configuration are distinct operations in the target design.

## Direction

The approved target is agent-first:

- one shared `plamp` library under the CLI and REST service;
- short cross-process-locked Pico and camera transactions;
- CLI usable locally or through SSH without the service;
- demand-driven full Pico reports with host-controlled polling;
- runtime schedule updates without reflashing;
- first-class MicroPython provisioning and application recovery;
- optional web apps using REST and SSE.

See [Agent-First Plamp Architecture](./superpowers/specs/2026-07-14-agent-first-plamp-architecture-design.md).

## Reliability Rules

- Do not require cloud access for schedules or recovery.
- Keep desired configuration separate from observed state.
- Do not store tty paths as hardware identity.
- Serialize access to each Pico and camera across processes.
- Prove firmware readiness with a valid protocol response, not a successful port open.
- Label planned behavior as direction until it ships.
