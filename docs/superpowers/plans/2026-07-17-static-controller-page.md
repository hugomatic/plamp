# Static Controller Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Serve every `/controllers/{controller}` URL with one runtime-neutral static diagnostics client using REST and SSE.

**Architecture:** The static page derives the controller ID from `location.pathname`. It loads the complete configured and observed controller node through filtered `/api/status`, loads the serial log through the controller REST endpoint, sends existing report/pulse commands, and listens to the existing controller SSE stream. FastAPI only returns the same `controller.html` file for every valid URL shape.

**Tech Stack:** Plain HTML/CSS/browser JavaScript, FastAPI `FileResponse`, REST, SSE `EventSource`, Python `unittest`, Node syntax checking.

## Global Constraints

- No server-injected controller ID, channels, telemetry, serial lines, hostname, or revision.
- Preserve `/controllers/{controller}` and all existing command/API URLs.
- Pin state comes only from valid reports; disconnects do not animate or predict state.
- Unknown or unavailable controllers produce a visible API-derived error.
- Shared navigation remains in `/static/app.js`.
- Deploy to Sprout and verify before Tower; Tower remains untouched.

---

### Task 1: Build the neutral controller document and REST/SSE client

**Files:**
- Create: `plamp_web/static/controller.html`
- Create: `plamp_web/static/controller.js`
- Modify: `tests/test_pages.py`

**Interfaces:**
- Consumes: `GET /api/status?path=controllers.<id>`, `GET /api/controllers/<id>/serial-log`, `POST /api/controllers/<id>/commands/report`, `POST /api/controllers/<id>/pins/<pin>/pulse`, and `GET /api/controllers/<id>?stream=true`.
- Produces: `controllerIdFromPath()`, `refreshDiagnostics()`, `refreshLog()`, `renderController(node)`, `postCommand(url, body)`, and `startControllerStream()`.

- [ ] Add failing tests asserting that `controller.html` is neutral and loads shared/controller assets, while `controller.js` derives the ID with `decodeURIComponent`, uses filtered status plus serial-log REST, preserves report/pulse confirmation, creates one `EventSource`, freezes displayed report state on stream error, and exposes refresh buttons.
- [ ] Run the focused tests and confirm failure because the static files do not exist.
- [ ] Create `controller.html` with neutral loading rows for Status, Commands, Configured pins, Diagnostics, and Serial log. Include no example ID or pin value other than the pulse-duration default of five seconds.
- [ ] Implement `controller.js` using DOM construction and `textContent`. Parse only the pathname segment after `/controllers/`; reject a missing or extra segment. Build the filtered status URL with `URLSearchParams({path: "controllers." + controller})`.
- [ ] In `renderController(node)`, render selected telemetry facts (`state`, `connected`, `port`, `serial`, `last_seen`, `last_error`), configured devices from `node.settings.devices` in `display_order`, and the full telemetry JSON. Use configured `pin`, `label`, `output_type`, `visibility`, and `programming` for the pin table.
- [ ] Start SSE only after the initial REST snapshot succeeds. Accept `snapshot`, `report`, and `status` events; update diagnostics/status only from parsed event payloads. On error, retain the last rendered values and mark the stream disconnected/stale.
- [ ] Preserve report, pulse, log-refresh, and diagnostics-refresh behavior. A successful command refreshes the serial log. Pulse validates pin `0..29`, positive integer seconds, and requires browser confirmation naming the configured channel when available.
- [ ] Run `tests.test_pages` and `node --check plamp_web/static/controller.js`; expect all pass.
- [ ] Commit with `git commit -m "Build controller diagnostics as a static client"`.

### Task 2: Serve the static controller and remove Python rendering

**Files:**
- Modify: `plamp_web/server.py`
- Modify: `plamp_web/pages.py`
- Modify: `tests/test_config_api.py`
- Modify: `tests/test_pages.py`
- Modify: `plamp_web/README.md`

**Interfaces:**
- Consumes: `STATIC_DIR / "controller.html"`.
- Produces: `GET /controllers/{controller} -> FileResponse` without monitor startup, config reads, or HTML rendering.

- [ ] Add a failing route-isolation test that patches `get_or_start_monitor` and `configured_timer_channels` to raise, calls `get_controller_page("pump_lights")`, and expects a `FileResponse` whose path is `controller.html`.
- [ ] Run the test and confirm it fails because the route starts a monitor and renders HTML.
- [ ] Change the route to return `FileResponse(STATIC_DIR / "controller.html", media_type="text/html")`; remove `render_controller_page` from the server import.
- [ ] Delete the obsolete Python controller renderer and replace renderer-coupled tests with static REST/SSE/command contracts. Retain API tests for snapshot, stream, serial log, report, and pulse behavior.
- [ ] Update the web README to mark `/controllers/{controller}` static.
- [ ] Run focused tests, the full suite, Python compilation, both relevant Node checks, `git diff --check`, and an `rg` scan proving `render_controller_page` is absent.
- [ ] Commit with `git commit -m "Serve controller diagnostics as a static client"`.

### Task 3: Integrate and prove the controller slice on Sprout

**Files:**
- No source changes unless verification finds a defect.

**Interfaces:**
- Consumes: the completed feature branch and `plampctl` workflow.
- Produces: pushed `main` and a verified Sprout controller page; Tower remains unchanged.

- [ ] Fast-forward the clean `run-main` worktree, rerun the full suite there, and push `main`.
- [ ] Run `ssh hugo@sprout.local 'cd ~/plamp && ./plampctl upgrade main'`.
- [ ] Verify `/controllers/octo_relay` contains only neutral markup, shared/controller assets return 200, filtered controller status and serial log return valid JSON, and the controller SSE emits an initial event.
- [ ] Load `http://sprout.local/controllers/octo_relay`; visually confirm status, configured pins, diagnostics refresh, and serial-log refresh. Do not pulse hardware solely for smoke testing.
- [ ] Confirm `plampctl status` is healthy and recent logs contain no application traceback.
