# Pulse Safety Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make pulses reject already-on outputs and preserve live schedule transitions.

**Architecture:** The API provides an immediate telemetry-based conflict response; firmware remains authoritative by checking the physical GPIO state. Generated-firmware execution tests prove the overlay semantics.

**Tech Stack:** Python, MicroPython-compatible generated firmware, FastAPI, `unittest`.

## Global Constraints

- Do not flash hardware merely to change or test this behavior locally.
- Do not restore a pre-pulse snapshot.

---

### Task 1: Firmware pulse invariants

**Files:** Modify `pico_scheduler/templates/base.py.tmpl`; test `tests/test_pico_generator.py`.

- [ ] Add failing generated-firmware execution tests for already-on rejection and an off-to-on schedule transition during pulse expiry.
- [ ] Add the physical-output guard without changing the overlay-removal algorithm.
- [ ] Run the generator tests.

### Task 2: API conflict warning

**Files:** Modify `plamp_web/server.py`; test `tests/test_config_api.py`.

- [ ] Add a failing test that a reported-on channel returns HTTP 409 and sends no command.
- [ ] Implement a focused latest-report lookup before queueing the pulse.
- [ ] Run focused and tracked test suites, commit, push, and deploy to Sprout and Tower.
