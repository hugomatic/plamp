# Plamp Current Spec

Last updated: 2026-05-05

This is the current, human-readable spec for the running Plamp system.
Historical design docs remain in `docs/superpowers/specs` and `docs/superpowers/plans`.

## 1) System Summary

Plamp is a Raspberry Pi web app and CLI that manages controller firmware state, schedules device patterns, and captures camera images.

Main parts:

- `plamp_web`: FastAPI app and HTML pages
- `plamp_cli`: agent-friendly JSON CLI
- `pico_scheduler`: generated MicroPython firmware for scheduler controllers
- `pico_doser`: placeholder firmware family/generator for future expansion

## 2) Contracts (Current)

Top-level config shape (`data/config.json`):

```json
{
  "controllers": {},
  "devices": {},
  "cameras": {}
}
```

Controller API shape:

- `GET /api/controllers`
- `GET /api/controllers/{controller}`
- `PUT /api/controllers/{controller}`

Pico scheduler command area (CLI):

- `plamp pico-scheduler list`
- `plamp pico-scheduler get <controller>`
- `plamp pico-scheduler set <controller> <payload>`

Firmware tooling area (CLI):

- `plamp firmware families`
- `plamp firmware generate ...`
- `plamp firmware flash ...`
- `plamp firmware pull --port <port>`
- `plamp firmware show --port <port>`

## 3) Image Placeholders

Use these placeholders to generate diagrams/images. Replace `[IMAGE_URL_HERE]` with your hosted image URL after generation.

### Figure A: System Architecture Overview

- Title: `Plamp System Architecture`
- Target section: `System Summary`
- Suggested output: `16:9 diagram, clean labels, light background`
- Checklist:
  - Status: `[todo|generated|inserted]`
  - Owner: `[name]`
  - Generated on: `[YYYY-MM-DD]`
  - Source prompt version: `v1`
- Prompt:

```text
Create a clear technical architecture diagram for a Raspberry Pi project named "Plamp".
Include these components and arrows:
1) Human/Agent client -> plamp_cli (command line, JSON-first)
2) Browser -> plamp_web (FastAPI + HTML pages)
3) plamp_cli -> plamp_web REST API
4) plamp_web -> data/config.json and data/timers/*.json
5) plamp_web -> Raspberry Pi camera capture pipeline
6) plamp_web / plamp_cli -> Pico via mpremote over USB serial
7) pico_scheduler firmware running on Pico
8) pico_doser firmware family placeholder
Style: minimal, engineering-focused, readable typography, no dark theme, neutral colors.
```

- URL: `[IMAGE_URL_HERE]`
- Embed:
  - `![Plamp System Architecture]([IMAGE_URL_HERE])`

### Figure B: Controller API and CLI Mapping

- Title: `Controller API and CLI Mapping`
- Target section: `Contracts (Current)`
- Suggested output: `table-style flow diagram`
- Checklist:
  - Status: `[todo|generated|inserted]`
  - Owner: `[name]`
  - Generated on: `[YYYY-MM-DD]`
  - Source prompt version: `v1`
- Prompt:

```text
Create a technical mapping diagram showing CLI commands on the left and REST endpoints on the right.
Left side groups:
- plamp controllers list/get/set
- plamp pico-scheduler list/get/set
- plamp firmware families/generate/flash/pull/show
Right side endpoints:
- GET /api/controllers
- GET /api/controllers/{controller}
- PUT /api/controllers/{controller}
- POST /api/controllers/{controller}/channels/{channel_id}/schedule
Add arrows between each CLI command and endpoint(s) it uses.
Use concise labels, white background, high legibility.
```

- URL: `[IMAGE_URL_HERE]`
- Embed:
  - `![Controller API and CLI Mapping]([IMAGE_URL_HERE])`

### Figure C: Firmware Generation and Flash Flow

- Title: `Firmware Generation and Flash Flow`
- Target section: `System Summary` and `Contracts (Current)`
- Suggested output: `step flowchart`
- Checklist:
  - Status: `[todo|generated|inserted]`
  - Owner: `[name]`
  - Generated on: `[YYYY-MM-DD]`
  - Source prompt version: `v1`
- Prompt:

```text
Create a flowchart for Plamp firmware workflow:
Input JSON payload -> plamp firmware generate -> generated main.py
Then branch:
A) inspect/show path (plamp firmware show/pull)
B) flash path (plamp firmware flash --port ...)
Include firmware families: pico_scheduler and pico_doser (placeholder).
Include a note that generated firmware embeds provenance metadata and input JSON comments.
Style: simple engineering flowchart, light background, readable labels.
```

- URL: `[IMAGE_URL_HERE]`
- Embed:
  - `![Firmware Generation and Flash Flow]([IMAGE_URL_HERE])`

## 4) How To Maintain This Spec

When contracts change:

1. Update this file first (`docs/spec-current.md`).
2. Update tests to enforce new behavior.
3. Link any new historical design docs in `docs/superpowers/specs`.

When adding a new firmware family:

1. Add controller type validation.
2. Add generator and CLI `firmware` support.
3. Document API/CLI contract changes here.
