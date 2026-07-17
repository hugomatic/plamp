# Single Scheduler Firmware Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the unused `pico_doser` public footprint and document the one generic scheduler firmware accurately.

**Architecture:** Keep `pico_scheduler` as the only implemented firmware family. Dosing uses bounded GPIO pulses on Plamp8; future measurement-MCU firmware is deferred until it has a real contract.

**Tech Stack:** Python 3.11, argparse, FastAPI, `unittest`, Markdown.

## Global Constraints

- Do not add a replacement placeholder firmware family.
- Existing `pico_doser` configuration must fail validation.
- Keep scheduler runtime configuration and pulse safety unchanged.
- Historical design records remain, but are marked superseded.

---

### Task 1: Remove the doser runtime and public surface

**Files:**
- Delete: `pico_doser/__init__.py`
- Delete: `pico_doser/generator.py`
- Modify: `plamp/hardware_config.py`
- Modify: `plamp_cli/main.py`
- Modify: `tests/test_hardware_config.py`
- Modify: `tests/test_config_api.py`
- Modify: `tests/test_plamp_cli.py`

**Interfaces:**
- Consumes: controller configuration and `plamp firmware` CLI requests.
- Produces: one accepted/listed family, `pico_scheduler`; explicit rejection of `pico_doser`.

- [ ] Update tests so controller validation rejects `pico_doser`, firmware-family listing returns only `pico_scheduler`, and unsupported generation fails without importing a doser package.
- [ ] Run `UV_CACHE_DIR=/tmp/uv-cache uv run python -m unittest tests.test_hardware_config tests.test_config_api tests.test_plamp_cli -v` and verify the old implementation fails the new expectations.
- [ ] Delete the package and remove doser branches, accepted types, reserved names, and doser-only generic-controller fixtures.
- [ ] Run the focused command again and require all tests to pass.

### Task 2: Correct the current contract and historical status

**Files:**
- Modify: `docs/spec-current.md`
- Modify: `pico_scheduler/README.md`
- Modify: `docs/superpowers/specs/2026-05-04-firmware-family-api-and-cli-design.md`
- Modify: `docs/superpowers/plans/2026-05-04-firmware-family-api-and-cli.md`

**Interfaces:**
- Consumes: the shipped runtime configuration and pulse behavior.
- Produces: documentation that distinguishes generic firmware, runtime state, maintenance upgrades, and future measurement hardware.

- [ ] Replace controller-specific generation and schedule-time flashing claims with the generic runtime firmware contract and build-time option defaults.
- [ ] Mark the May multi-family documents superseded without rewriting their historical contents.
- [ ] Verify no active code or current documentation contains `pico_doser` with `rg -n "pico_doser" plamp plamp_cli plamp_web pico_scheduler README.md docs/spec-current.md tests`.
- [ ] Run `python3 -m py_compile plamp/*.py pico_scheduler/*.py plamp_cli/*.py plamp_web/*.py tests/*.py`.
- [ ] Run `UV_CACHE_DIR=/tmp/uv-cache uv run python -m unittest discover -s tests -q`, `git diff --check`, and inspect `git status --short`.
- [ ] Commit and push the cleanup on `feature/runtime-pico-config`.

