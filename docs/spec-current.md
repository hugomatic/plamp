# Plamp Current Spec

Last updated: 2026-05-05

This is the canonical product and engineering spec for Plamp.
It is designed to prevent regressions, preserve proven patterns, and guide future growth.

## Canonical Quality Gate

This spec is canonical only if all are true:

- it matches current GUI, CLI, API, and firmware behavior
- each major section includes `Current System`, `How We Got Here`, and `Pattern Guard`
- historical decisions are traceable to prior specs
- behavior-critical claims are backed by tests
- changes to behavior and this spec land in the same PR

## 1) Vision: Reliable Agriculture For Everybody

### Current System

Plamp is a local-first hydroponics control platform where:

- operators use a practical web GUI
- agents and power users use a JSON-first CLI
- firmware is generated/programmed from explicit payloads

Core promise: reliable operation with understandable, modifiable internals.

### How We Got Here

- Started with practical scheduling + direct Pico control.
- Added unified settings and operational visibility.
- Evolved to controller-centric contracts and firmware-family growth.

Sources:

- `docs/superpowers/specs/2026-04-15-settings-unification-design.md`
- `docs/superpowers/specs/2026-05-04-firmware-family-api-and-cli-design.md`

### Pattern Guard

- Do not introduce opaque automation that hides controller state transitions.
- Do not make cloud services a requirement for core operation.
- Do not split GUI and CLI into different conceptual models.

## 2) System Shape and Stack

### Current System

Major components:

- `plamp_web` (FastAPI + server-rendered pages)
- `plamp_cli` (argparse, JSON-first)
- firmware families (`pico_scheduler`, `pico_doser` placeholder)
- runtime state under `data/`

Operational tooling:

- `uv`, `FastAPI`, `uvicorn`, `pyserial`, `mpremote`, `MicroPython`

### How We Got Here

- Fast iteration on Raspberry Pi favored a simple local stack.
- Hardware control required explicit serial/programming tooling.

Sources:

- `docs/superpowers/specs/2026-05-04-pico-scheduler-firmware-generator-design.md`

### Pattern Guard

- Prefer explicit local tools over hidden wrapper layers.
- Keep host orchestration simple and inspectable.

## 3) GUI Contract

### Current System

`/` main page must:

- show current controller/device runtime state
- allow schedule editing for configured scheduler devices
- show camera capture context

`/settings` must:

- be the canonical config/admin page
- keep `System status / Peripherals` read-only
- expose assignment status clearly
- keep scheduler editing in `Pico schedulers` grouped by controller
- save in combined top-level config shape

`/api/test` must:

- expose live contract examples and payloads

### How We Got Here

- Moved away from split admin surfaces to one coherent settings page.
- Kept read-only status separate from editable scheduler assignment.

Sources:

- `docs/superpowers/specs/2026-04-15-settings-unification-design.md`
- `docs/superpowers/specs/2026-04-30-pico-schedulers-settings-design.md`

### Pattern Guard

- Do not reintroduce editable controls inside `System status / Peripherals`.
- Do not split scheduler editing back into disconnected controller/device pages.
- Do not hide assignment state.

## 4) Canonical Data Model

### Current System

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

- controller IDs are global and unique
- reserved IDs are forbidden
- devices are globally keyed and reference controller IDs
- pin collisions are invalid per controller

### How We Got Here

- kept `devices` top-level to preserve stable IDs and simplify global validation
- made UI grouping a view concern, not storage structure

Sources:

- `docs/superpowers/specs/2026-04-14-config-model-simplification-design.md`
- `docs/superpowers/specs/2026-05-03-pico-scheduler-devices-payload-design.md`

### Pattern Guard

- Do not silently move to nested-per-controller storage without explicit migration spec.
- Do not add duplicate identity layers for the same device/controller concept.

## 5) API and CLI Contract

### Current System

Controller API:

- `GET /api/controllers`
- `GET /api/controllers/{controller}`
- `PUT /api/controllers/{controller}`
- `POST /api/controllers/{controller}/channels/{channel_id}/schedule`

CLI top-level sections:

- `config`, `controllers`, `pico-scheduler`, `pics`, `firmware`

CLI UX constraints:

- no-arg prints help
- missing sections/actions return actionable choices/examples

### How We Got Here

- moved from timer-centered naming toward controller-centered contracts
- kept compatibility only where needed during transition

Sources:

- `docs/superpowers/specs/2026-05-04-firmware-family-api-and-cli-design.md`
- `docs/superpowers/specs/2026-04-30-plamp-cli-design.md`

### Pattern Guard

- Do not introduce competing route families for the same resource.
- Do not hide required payload fields behind implicit server defaults.
- Do not degrade CLI errors into parser-internal jargon only.

## 6) Firmware Families and Growth

### Current System

Families:

- `pico_scheduler` (active)
- `pico_doser` (placeholder)

Workflow:

1. payload JSON
2. generate firmware source
3. optional show/pull
4. flash to selected port
5. verify runtime reports

### How We Got Here

- retained JSON as first-class contract
- moved toward family-based generators to avoid hard-coding one firmware forever

Sources:

- `docs/superpowers/specs/2026-05-04-pico-scheduler-firmware-generator-design.md`
- `docs/superpowers/specs/2026-05-04-firmware-family-api-and-cli-design.md`

### Pattern Guard

- Do not couple all future firmware to scheduler-specific assumptions.
- Do not generate code that cannot be inspected or diffed.

## 7) Human and Agent Playbooks

### Current System

Human operators:

- morning status check
- safe schedule edits
- stale-capture diagnosis

Agents:

- read contracts first
- patch minimally
- verify with targeted tests, then full suite for contract changes

### How We Got Here

- real operations required fast diagnosis and low-friction automation
- repeated regressions showed need for explicit anti-regression workflow

### Pattern Guard

- Do not skip verification on contract changes.
- Do not ship behavior changes without spec updates.

## 8) Inspiring Image Placeholders (Not Diagrams)

These images should communicate mission and values, not architecture drawings.
Replace `[IMAGE_URL_HERE]` after generation.

### Image A: Open Agriculture For Everyone

- Title: `Reliable Agriculture For Everybody`
- Intent: accessible, open, learnable food-growing technology
- Prompt:

```text
Create an inspiring documentary-style image about open hydroponics technology for everyone.
Scene: diverse people (different ages/backgrounds) learning around a small indoor grow setup powered by open hardware on a simple bench.
Mood: optimistic, practical, empowering, not corporate.
Visual cues: transparent components, hand-written notes, Raspberry Pi + Pico visible, healthy basil growth, daylight.
Style: realistic photography aesthetic, warm natural light, high detail, no infographic arrows, no abstract tech wallpaper.
```

- URL: `[IMAGE_URL_HERE]`
- Embed: `![Reliable Agriculture For Everybody]([IMAGE_URL_HERE])`

### Image B: Learn, Modify, Improve

- Title: `Learnable And Modifiable System`
- Intent: show that users can understand and improve the system
- Prompt:

```text
Create an inspiring image showing a maker-friendly hydroponics workstation where the system is clearly understandable and modifiable.
Include: laptop with readable code editor, small web dashboard on screen, labeled wires/components, notebook with schedule ideas, and a person actively adjusting setup.
Theme: transparency over black-box automation.
Style: realistic, clean, daylight, human-centered, no diagrams, no arrows.
```

- URL: `[IMAGE_URL_HERE]`
- Embed: `![Learnable And Modifiable System]([IMAGE_URL_HERE])`

### Image C: Reliability In Daily Life

- Title: `Reliable Daily Operation`
- Intent: dependable routine and confidence
- Prompt:

```text
Create an image of a calm daily routine around a small indoor garden using open automation.
Show a person doing a quick morning check while healthy plants grow consistently.
Include subtle signs of reliability: timestamped notes, stable indicators, tidy setup, repeated healthy growth stage.
Style: realistic lifestyle photography, bright morning daylight, grounded and practical, no technical diagrams.
```

- URL: `[IMAGE_URL_HERE]`
- Embed: `![Reliable Daily Operation]([IMAGE_URL_HERE])`

## 9) Traceability Index

- Settings unification:
  - `docs/superpowers/specs/2026-04-15-settings-unification-design.md`
- Scheduler-focused settings grouping:
  - `docs/superpowers/specs/2026-04-30-pico-schedulers-settings-design.md`
- Config model simplification:
  - `docs/superpowers/specs/2026-04-14-config-model-simplification-design.md`
- Devices payload evolution:
  - `docs/superpowers/specs/2026-05-03-pico-scheduler-devices-payload-design.md`
- Firmware family/API/CLI direction:
  - `docs/superpowers/specs/2026-05-04-firmware-family-api-and-cli-design.md`
- Pico scheduler generator direction:
  - `docs/superpowers/specs/2026-05-04-pico-scheduler-firmware-generator-design.md`
- CLI design:
  - `docs/superpowers/specs/2026-04-30-plamp-cli-design.md`

## Maintenance Rules

When behavior changes:

1. update this file first
2. update tests
3. update user docs if contract changed
4. ship in one PR
