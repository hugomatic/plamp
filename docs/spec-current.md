# Plamp Current Spec

Last updated: 2026-05-05

This document is the canonical current-state spec for Plamp. It is intentionally practical: product behavior first, then interfaces, then implementation notes. Historical design docs still live in `docs/superpowers/specs` and `docs/superpowers/plans`.

## 1) Product Overview

Plamp is a Raspberry Pi hydroponic control system with:

- a local web GUI for daily operation and configuration
- a JSON-first CLI for automation and agent workflows
- Pico firmware generation/programming flows for controller behavior
- integrated camera capture and timeline review

Primary user goals:

- keep pumps/lights schedules reliable
- inspect and change schedules quickly from web or CLI
- monitor current controller state
- capture and review grow images
- evolve firmware families without rewriting the whole app

## 2) Design Approach

Plamp follows these design rules:

- Single source of truth: host config in `data/config.json`.
- Contract-first: API and CLI payloads are explicit and test-backed.
- Human + agent parity: everything in GUI should be scriptable via CLI/API.
- Progressive complexity: basic usage should be simple; advanced workflows stay available.
- Firmware-family extensibility: new families (for example `pico_doser`) should integrate without breaking existing scheduler workflows.

Non-goals:

- not a cloud-first architecture
- not a highly normalized enterprise schema
- not dependent on external managed services for core operation

## 3) System Architecture

Main components:

- `plamp_web` (FastAPI + server-rendered pages)
- `plamp_cli` (argparse, JSON input/output, agent-friendly)
- firmware generators (`pico_scheduler`, `pico_doser`)
- runtime data (`data/config.json`, `data/timers/*.json`, captured image metadata/files)

Data/control flow:

1. Human uses browser or CLI.
2. Web/CLI read and mutate host config/state through shared contracts.
3. For Pico-backed controllers, state updates can trigger firmware/state sync to device.
4. Periodic reports and camera captures feed monitoring and dashboards.

## 4) GUI Specification

### Main page (`/`)

Purpose:

- show active scheduler/device state at a glance
- allow schedule edits for configured scheduler devices
- expose capture controls and latest image context

Behavior:

- reads runtime status and configured devices
- updates view periodically
- preserves editor context during refresh where possible
- schedule edits apply to the targeted controller/channel only

### Settings page (`/settings`)

Purpose:

- configure controllers, devices, cameras, hostname, and software/runtime context

Behavior:

- “System status / Peripherals” is read-only for assignment status visibility
- “Pico schedulers” is the editable area for assignment and scheduler-specific config
- supports grouped scheduler sections per controller
- persists combined config in current top-level shape (`controllers`, `devices`, `cameras`)

### API test page (`/api/test`)

Purpose:

- make API contracts discoverable and testable from the browser
- provide copyable examples for debugging/integration

Behavior:

- displays route examples aligned with current contracts
- includes timer/controller stream and payload examples

## 5) Configuration and Data Model

Canonical host config shape:

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

Controller rules:

- each controller has an ID key and a firmware family (`type`)
- reserved IDs are blocked (routing/system keywords)
- controller IDs are unique

Device rules:

- each device maps to one controller
- pin uniqueness is enforced per controller
- editor/type semantics are validated

## 6) API Contract (Current)

Core controller routes:

- `GET /api/controllers`
- `GET /api/controllers/{controller}`
- `PUT /api/controllers/{controller}`

Scheduler channel mutation route:

- `POST /api/controllers/{controller}/channels/{channel_id}/schedule`

Legacy compatibility:

- legacy timer routes may still exist for transition, but new development targets controller routes.

Streaming:

- stream mode is supported for scheduler controllers only.

Error principles:

- 4xx for validation and unknown resource errors
- details should be actionable (controller name, expected choices)

## 7) CLI Contract (Current)

Top-level command sections:

- `config`
- `controllers`
- `pico-scheduler`
- `pics`
- `firmware`

Usability expectations:

- `plamp` with no args prints help
- missing top-level section errors list available sections
- missing nested actions should provide choices and examples

Core examples:

```bash
uv run plamp --pretty controllers list
uv run plamp --pretty pico-scheduler get pump_lights
uv run plamp --pretty config get
uv run plamp --pretty firmware families
```

## 8) Firmware Generation and Programming

Current families:

- `pico_scheduler`: active scheduling firmware family
- `pico_doser`: placeholder family for future dosing workflows

Generator principles:

- generated firmware should be simple and inspectable
- generated source embeds provenance metadata and input JSON comments
- family-specific code should be emitted only when needed by input

Programming flow:

1. prepare JSON payload
2. `plamp firmware generate ...`
3. optional `plamp firmware show/pull`
4. `plamp firmware flash --port ...`

## 9) Operations and Runtime

Deployment shape:

- systemd service runs web app
- optional nginx proxy on port 80
- local-first operation expected

Operational checks:

- service status via `systemctl status plamp-web`
- software identity visible in settings (branch, commit, timestamp)
- runtime data stays outside git-tracked source files

## 10) Testing and Change Control

Required for behavior-changing work:

1. update this current spec
2. update/add automated tests
3. run test suite
4. ship via branch + PR

Spec drift policy:

- if code and spec diverge, update one immediately in the same change set.

## 11) Image Placeholders (Generation Blocks)

Use these placeholders to generate diagrams/images. Replace `[IMAGE_URL_HERE]` with a hosted URL after selection.

Global style constraints for all figures:

- avoid plain arrow-only SVG look
- show context blocks with hierarchy, boundaries, and callouts
- include short realistic labels from this project (`/settings`, `Assigned peripheral`, `report_every`, `pico_scheduler`)
- prefer a "technical product doc" aesthetic over generic flowchart defaults
- light background, high contrast text, presentation-ready in GitHub markdown

### Figure A: System Architecture Overview

- Title: `Plamp System Architecture`
- Target section: `System Architecture`
- Suggested output: `16:9 diagram, clean labels, light background`
- Checklist:
  - Status: `[todo|generated|inserted]`
  - Owner: `[name]`
  - Generated on: `[YYYY-MM-DD]`
  - Source prompt version: `v1`
- Prompt:

```text
Create a polished architecture board for the Raspberry Pi hydroponics project "Plamp" that looks like a real product-engineering document, not a generic flowchart.

Layout:
- Left column: operators (Human in browser, Agent in terminal)
- Center: Raspberry Pi host boundary containing plamp_web, plamp_cli, config/state files, camera capture service
- Right: USB-connected Pico controllers boundary (pico_scheduler active, pico_doser placeholder)
- Bottom strip: operational outputs (dashboard state, captures timeline, firmware artifacts)

Required labels from the real project:
- "/settings", "/api/test", "controllers", "devices", "cameras", "report_every", "Assigned peripheral", "mpremote"

Visual requirements:
- use grouped containers, legend, and numbered data/control paths
- use iconography for browser/terminal/pi/pico/camera/storage
- avoid single-line arrows floating on white space
- keep light theme and high readability
```

- URL: `[IMAGE_URL_HERE]`
- Embed: `![Plamp System Architecture]([IMAGE_URL_HERE])`

### Figure B: GUI Information Architecture

- Title: `Plamp GUI Structure`
- Target section: `GUI Specification`
- Suggested output: `screen-map style diagram`
- Checklist:
  - Status: `[todo|generated|inserted]`
  - Owner: `[name]`
  - Generated on: `[YYYY-MM-DD]`
  - Source prompt version: `v1`
- Prompt:

```text
Create a UX information architecture map for Plamp that communicates operator workflow at a glance.

Primary pages:
1) "/" dashboard: runtime state, per-device schedule editing, camera snapshot/review
2) "/settings": Plamp setup + system status + device control
3) "/api/test": route playground and payload examples

In "/settings", explicitly depict:
- read-only "System status / Peripherals" with assignment visibility
- editable "Pico schedulers" grouped by controller
- per-controller fields: ID, label, assigned peripheral, report every seconds

Show realistic user journeys:
- "morning check" path
- "change pump cycle" path
- "diagnose offline peripheral" path

Style requirements:
- use page cards with key widgets, not just boxes and arrows
- include small annotation notes for design intent
- clean light technical style, presentation-ready
```

- URL: `[IMAGE_URL_HERE]`
- Embed: `![Plamp GUI Structure]([IMAGE_URL_HERE])`

### Figure C: Controller API and CLI Mapping

- Title: `Controller API and CLI Mapping`
- Target section: `API Contract` and `CLI Contract`
- Suggested output: `table-style flow diagram`
- Checklist:
  - Status: `[todo|generated|inserted]`
  - Owner: `[name]`
  - Generated on: `[YYYY-MM-DD]`
  - Source prompt version: `v1`
- Prompt:

```text
Create a command-to-contract matrix diagram for Plamp that looks like API documentation art, not a basic flowchart.

Left panel (CLI intents):
- discover controllers
- inspect controller state
- replace controller payload
- set pico-scheduler channel schedule
- firmware local operations (families/generate/flash/pull/show)

Middle panel (exact commands examples):
- plamp controllers list
- plamp controllers get pump_lights
- plamp controllers set pump_lights @payload.json
- plamp pico-scheduler channels set-schedule pump_lights pump @schedule.json
- plamp firmware flash --firmware pico_scheduler --controller pump_lights @payload.json --port /dev/ttyACM0

Right panel (REST contracts):
- GET /api/controllers
- GET /api/controllers/{controller}
- PUT /api/controllers/{controller}
- POST /api/controllers/{controller}/channels/{channel_id}/schedule

Requirements:
- include error-handling callouts (unknown controller, missing top-level section)
- highlight legacy timer route as "transition/legacy"
- use table-like lanes and connectors with visual hierarchy
- light theme, high legibility
```

- URL: `[IMAGE_URL_HERE]`
- Embed: `![Controller API and CLI Mapping]([IMAGE_URL_HERE])`

### Figure D: Firmware Generation and Flash Flow

- Title: `Firmware Generation and Flash Flow`
- Target section: `Firmware Generation and Programming`
- Suggested output: `step flowchart`
- Checklist:
  - Status: `[todo|generated|inserted]`
  - Owner: `[name]`
  - Generated on: `[YYYY-MM-DD]`
  - Source prompt version: `v1`
- Prompt:

```text
Create an engineering workflow diagram for "JSON -> firmware -> Pico" in Plamp, optimized for power users and agents.

Show two explicit lanes:
- Server-backed lane (controller payload from API)
- Local power-user lane (payload from file/stdin)

Core stages:
1) validate JSON contract
2) select firmware family (pico_scheduler or pico_doser placeholder)
3) generate main.py with embedded provenance comment block
4) optional inspect path (show/pull)
5) flash via mpremote to selected port
6) verify by reading back firmware and checking report output cadence

Requirements:
- include concrete labels: "generator path", "input JSON comment", "report_every", "type: report"
- depict decision nodes and verification checkpoints
- avoid generic swimlane template look; use custom component styling and concise annotations
- light background, print-friendly
```

- URL: `[IMAGE_URL_HERE]`
- Embed: `![Firmware Generation and Flash Flow]([IMAGE_URL_HERE])`

## 12) Spec Maintenance Procedure

When behavior changes:

1. update this file
2. update tests
3. update user docs (`README`, CLI docs) if interface changed
4. ship in one PR

When adding a new firmware family:

1. add controller type validation and constraints
2. add generator entry points and CLI workflows
3. define API/CLI contract changes in this spec
4. document programming and observability expectations
