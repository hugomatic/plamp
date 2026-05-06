# Plamp Current Spec

Last updated: 2026-05-05

This is the canonical spec for how Plamp works now, why it was built this way, and where it can grow next.

## Canonical Quality Gate

This spec is considered canonical only when all checks below are true:

- reflects current behavior in GUI, CLI, API, and firmware generation paths
- uses normative language (`must`, `should`) for contract-critical behavior
- links major decisions to historical design docs in `Traceability`
- is backed by automated tests for contract-level behavior
- is updated in the same PR as behavior changes (no deferred doc sync)
- is readable by humans in under 15 minutes and actionable for agents in under 5 minutes

## Seed -> Now -> Next

### Seed

Plamp started as a practical hydroponics controller: reliable pump/light timing, local control on a Raspberry Pi, and direct Pico programming without cloud dependencies.

### Now

Plamp is a local-first system with three equal control surfaces:

- GUI (`/`, `/settings`, `/api/test`) for daily operation and setup
- CLI (`plamp`) for scripted/agentic workflows
- firmware generators for controller families (`pico_scheduler`, `pico_doser` placeholder)

Core rule: GUI and CLI must manipulate the same model, not competing models.

### Next

Plamp is positioned to support multiple firmware families, direct firmware experimentation, and richer device domains (for example dosing) without rewriting the control plane.

## Design Principles

- Single source of truth: host config lives in `data/config.json`.
- Contracts before convenience: explicit payloads, explicit validation, test-backed behavior.
- Human + agent parity: anything important in UI must be operable through CLI/API.
- Local robustness over cloud abstraction.
- Incremental extensibility: new firmware families are additive.

## System Overview

Main components:

- `plamp_web` (FastAPI app + server-rendered pages)
- `plamp_cli` (argparse, JSON-first I/O)
- `pico_scheduler` generator/runtime family
- `pico_doser` placeholder family
- runtime data under `data/` (config, controller states, captures)

Operational toolchain (brief):

- `uv` for environment/command execution
- `FastAPI` + `uvicorn` for web runtime
- `pyserial` and `mpremote` for Pico communication/programming
- `MicroPython` on Pico targets

## GUI Behavior (Normative)

### `/` Main Dashboard

Must:

- show current scheduler/device state
- allow per-device schedule editing for configured scheduler controllers
- show capture controls and latest image context

Should:

- preserve editing context across refresh cycles

### `/settings`

Must:

- be the canonical admin/config page
- keep `System status / Peripherals` read-only
- show assignment visibility in status
- provide editable scheduler/controller assignment in `Pico schedulers`
- persist the combined config shape (`controllers`, `devices`, `cameras`)

### `/api/test`

Must:

- expose live route examples and payload patterns for current contracts

## Canonical Data Model

Host config shape:

```json
{
  "controllers": {
    "pump_lights": {
      "type": "pico_scheduler",
      "pico_serial": "e66038b71387a039",
      "report_every": 10
    }
  },
  "devices": {
    "pump": {
      "controller": "pump_lights",
      "pin": 3,
      "editor": "cycle"
    }
  },
  "cameras": {}
}
```

Invariants:

- controller IDs are globally unique
- reserved IDs are forbidden
- each device references exactly one controller
- pin collisions are invalid within a controller
- scheduler-specific device semantics (`editor`, `pin`, type rules) are validated

Why `devices` is top-level:

- keeps IDs stable and global
- simplifies global listing/validation and rename handling
- keeps GUI grouping a presentation choice, not a storage constraint

## API Contract (Current Truth)

Primary controller routes:

- `GET /api/controllers`
- `GET /api/controllers/{controller}`
- `PUT /api/controllers/{controller}`
- `POST /api/controllers/{controller}/channels/{channel_id}/schedule`

Contract expectations:

- discovery route is lightweight and firmware-aware
- controller route returns full controller payload
- put route replaces full controller payload
- scheduler stream behavior is controller-type constrained
- error details should be actionable (which controller/field failed and why)

Detailed interactive examples live in `/api/test`.

## CLI Contract (Current Truth)

Top-level command sections:

- `config`
- `controllers`
- `pico-scheduler`
- `pics`
- `firmware`

Behavior expectations:

- `plamp` with no args prints help
- missing top-level section returns a choices hint
- nested missing/invalid actions should return examples
- JSON input works via inline JSON, `@file`, or stdin marker where applicable

## Firmware Families and Programming

Families:

- `pico_scheduler` (active scheduling firmware family)
- `pico_doser` (placeholder for upcoming dosing workflows)

Generator expectations:

- generated `main.py` is inspectable and deterministic from payload
- generated source includes provenance metadata and input JSON comments
- optional family-specific code appears only when required by payload

Power-user/agent workflow:

1. prepare payload JSON
2. `plamp firmware generate ...`
3. optional `plamp firmware show`/`pull`
4. `plamp firmware flash --port ...`
5. verify on-device behavior/report cadence

## Human Operator Playbook

Morning check:

- open `/`
- verify recent captures and device state
- if stale state/captures, check `/settings` system status and peripheral assignment

Change schedule safely:

- edit target device schedule in `/`
- verify controller/device mapping in `/settings`
- confirm runtime behavior update

Diagnose “no new images”:

- inspect `/` capture list timestamps
- inspect settings/software/runtime status
- run CLI image list/get for cross-check

## Agent Playbook (Token-Efficient)

Read order:

1. this file sections: `Canonical Data Model`, `API Contract`, `CLI Contract`
2. `plamp_cli/README.md` for command details
3. tests that define the targeted behavior

Safe change sequence:

1. read current payload/state
2. produce minimal patch
3. run targeted tests
4. run full suite when contract-level changes are involved
5. report exact command outputs for verification

## Operations

Expected runtime shape:

- `plamp-web` systemd service for steady operation
- optional nginx fronting for port 80

Operational checks:

- `systemctl status plamp-web`
- settings software section (branch/commit/timestamp)
- confirm working tree cleanliness before deploy-sensitive actions

## Traceability (Where Decisions Came From)

- settings unification and admin-page intent:
  - `docs/superpowers/specs/2026-04-15-settings-unification-design.md`
- grouped pico scheduler UX and assignment model:
  - `docs/superpowers/specs/2026-04-30-pico-schedulers-settings-design.md`
- controller/family API + CLI evolution direction:
  - `docs/superpowers/specs/2026-05-04-firmware-family-api-and-cli-design.md`
- firmware generation constraints:
  - `docs/superpowers/specs/2026-05-04-pico-scheduler-firmware-generator-design.md`

## Image Placeholders (Generation Blocks)

Global style constraints:

- avoid generic arrow-only SVG output
- use hierarchy, boundaries, callouts, and realistic labels
- keep light theme, high readability, GitHub-friendly aspect ratios

### Figure A: System Architecture Board

- Title: `Plamp System Architecture`
- Checklist:
  - Status: `[todo|generated|inserted]`
  - Owner: `[name]`
  - Generated on: `[YYYY-MM-DD]`
- Prompt:

```text
Create a polished architecture board for "Plamp" (Raspberry Pi hydroponics control).
Use a structured layout: operators (browser + terminal agents), Raspberry Pi host boundary (plamp_web, plamp_cli, config/state, camera pipeline), Pico boundary (pico_scheduler active, pico_doser placeholder), and outputs (dashboard state, captures, firmware artifacts).
Include real labels: /settings, /api/test, controllers, devices, cameras, report_every, Assigned peripheral, mpremote.
Avoid simple arrow-only diagram style. Use grouped containers, numbering, and short callouts.
```

- URL: `[IMAGE_URL_HERE]`
- Embed: `![Plamp System Architecture]([IMAGE_URL_HERE])`

### Figure B: GUI Workflow Map

- Title: `Plamp GUI Structure`
- Checklist:
  - Status: `[todo|generated|inserted]`
  - Owner: `[name]`
  - Generated on: `[YYYY-MM-DD]`
- Prompt:

```text
Create a GUI workflow map for Plamp showing "/", "/settings", and "/api/test".
In /settings depict: read-only System status/Peripherals, editable Pico schedulers grouped by controller, assignment + report_every fields.
Add three operator journeys: morning check, change pump cycle, diagnose offline peripheral.
Use card-based layout and concise annotation notes; avoid generic flowchart look.
```

- URL: `[IMAGE_URL_HERE]`
- Embed: `![Plamp GUI Structure]([IMAGE_URL_HERE])`

### Figure C: CLI/API Contract Matrix

- Title: `Controller API and CLI Mapping`
- Checklist:
  - Status: `[todo|generated|inserted]`
  - Owner: `[name]`
  - Generated on: `[YYYY-MM-DD]`
- Prompt:

```text
Create a command-to-contract matrix for Plamp.
Left: operator intents and representative plamp commands.
Right: REST routes (/api/controllers, /api/controllers/{controller}, PUT controller, channel schedule route).
Highlight actionable error examples (unknown controller, missing command section).
Use lane/table visual structure with strong hierarchy, not a plain arrow chart.
```

- URL: `[IMAGE_URL_HERE]`
- Embed: `![Controller API and CLI Mapping]([IMAGE_URL_HERE])`

## Maintenance Rules

When behavior changes:

1. update this file
2. update tests
3. update user docs if CLI/UI contract changed
4. ship in one PR
