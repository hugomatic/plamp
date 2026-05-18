# Config Tree Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace flat top-level devices with controller-owned typed instances while preserving current scheduler behavior through adapters and updating every user-facing surface to the new hard-break config shape.

**Architecture:** `config.json` becomes the persisted source for typed controller/device instances with `config` and `settings` sections. The web app compiles that tree into the existing Pico scheduler firmware payload shape so firmware execution stays stable while validation, APIs, CLI, pages, and docs all speak the new tree.

**Tech Stack:** Python, FastAPI, server-rendered HTML/JS, `unittest`, Pico scheduler JSON payloads.

---

### Task 1: Persisted Config Model

**Files:**
- Modify: `plamp_web/hardware_config.py`
- Modify: `tests/test_hardware_config.py`
- Modify: `data/config.json`

- [ ] Write failing tests for nested controller devices, required instance types, `config`/`settings`, `daily_window`, and rejection of top-level `devices`.
- [ ] Implement validation helpers for controller/device instance nodes and update config section application around `controllers` + `cameras`.
- [ ] Update checked-in sample config to the new canonical tree.
- [ ] Run `python3 -m unittest tests.test_hardware_config -v`.

### Task 2: Runtime And Firmware Adapters

**Files:**
- Modify: `plamp_web/timer_schedule.py`
- Modify: `plamp_web/server.py`
- Modify: `tests/test_timer_schedule.py`
- Modify: `tests/test_config_api.py`
- Modify: `tests/test_pico_scheduler_generator.py`

- [ ] Write failing tests showing channel metadata and generated scheduler payloads come from nested devices and controller `settings.report_every`.
- [ ] Update runtime readers and payload compilation to consume the nested tree while still emitting Pico payloads with top-level `report_every` and `devices`.
- [ ] Keep telemetry/state file parsing unchanged unless adapter tests require changes.
- [ ] Run focused runtime/API/generator tests.

### Task 3: Settings UI And API Test Page

**Files:**
- Modify: `plamp_web/pages.py`
- Modify: `tests/test_pages.py`

- [ ] Update settings-page tests to expect nested device forms and schedule-kind/programming fields.
- [ ] Update API test page examples so no sample payload contains top-level `devices`.
- [ ] Refactor settings page collection/rendering code to edit one controller subtree at a time and save the new shape.
- [ ] Run `python3 -m unittest tests.test_pages -v`.

### Task 4: CLI And Documentation

**Files:**
- Modify: `plamp_cli/main.py`
- Modify: `plamp_cli/README.md`
- Modify: `plamp_web/README.md`
- Modify: `README.md`
- Modify: `pico_scheduler/README.md`
- Modify: `tests/test_plamp_cli.py`
- Modify: `tests/test_plamp_cli_http.py`

- [ ] Update CLI section vocabulary and examples for `controllers` + `cameras`; remove `config devices` as a top-level section.
- [ ] Update help text and README config examples to the new tree while documenting that Pico payloads remain flat firmware state.
- [ ] Update CLI tests and run them.

### Task 5: Verification

**Files:**
- Modify as needed from prior tasks.

- [ ] Run `python3 -m unittest discover -s tests -v`.
- [ ] Search for stale top-level config references such as `config["devices"]`, `/api/config/devices`, and legacy README examples; remove only config-tree leftovers, not Pico firmware payload references.
- [ ] Review the final diff against the spec and commit the completed migration.
