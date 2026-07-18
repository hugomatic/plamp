# Static System Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Serve `/system` as a runtime-neutral static client that reads system facts and logs through REST and preserves the existing service actions.

**Architecture:** `system.html` contains only neutral loading rows and controls. `system.js` reuses the shared shell's memoized `PlampWeb.loadSystem()`, renders every System section with DOM nodes and `textContent`, lazily loads `/api/logs`, and posts the existing service actions. FastAPI serves the file directly and no longer reads system state or logs while producing HTML.

**Tech Stack:** Plain HTML/CSS/browser JavaScript, FastAPI `FileResponse`, REST, Python `unittest`, Node syntax checking.

## Global Constraints

- Keep `/system` and all existing System REST endpoints stable.
- Inject no hostname, time, Git identity, hardware, storage, worker, monitor, log, or action result into HTML.
- Reuse `/static/app.js` for navigation, hostname, revision, and the memoized `/api/system` request.
- Load logs only after the user presses `Load logs`.
- Show an action as complete only when the server returns a successful response; a dropped or failed request remains explicitly unconfirmed.
- Do not add a framework, client router, bundler, Node dependency, or API bootstrap blob.
- Deploy to Sprout and verify before Tower; Tower remains untouched.

---

### Task 1: Build the neutral System document and REST client

**Files:**
- Create: `plamp_web/static/system.html`
- Create: `plamp_web/static/system.js`
- Modify: `tests/test_pages.py`

**Interfaces:**
- Consumes: `PlampWeb.bootstrapShell()`, `PlampWeb.loadSystem()`, `PlampWeb.responseJson()`, `GET /api/logs?lines=200`, and `POST /api/system/{restart,reinstall,upgrade}`.
- Produces: `renderSystem(system)`, `loadLogs()`, `runAction(path, label)`, and DOM render helpers scoped inside `system.js`.

- [ ] Add failing static-client tests that read `system.html` and `system.js`. Require shared navigation/assets; neutral rows for System info, Hardware, Software, Storage, Camera worker, Controller workers, Actions, and Logs; `PlampWeb.loadSystem()`; lazy `/api/logs?lines=200`; all three action URLs; and an explicit `result unconfirmed` failure message. Reject concrete hostnames, Git hashes, hardware paths, and injected log text in the document.
- [ ] Run `python -m unittest tests.test_pages.PageRenderTests.test_system_static_client_uses_rest_without_injected_state tests.test_pages.PageRenderTests.test_system_static_client_preserves_actions_and_lazy_logs -v`; expect failure because the static files do not exist.
- [ ] Create `system.html` with the established shared navigation, neutral heading/status, table headings from the current System page, disabled action buttons, a `Load logs` button, and `Logs not loaded.`. Load `/static/app.css`, `/static/app.js`, and `/static/system.js`.
- [ ] Implement DOM helpers that replace table bodies safely with `textContent`. Render `host`, `host_time`, `software`, `tools`, `paths`, `storage`, `detected.picos`, `detected.cameras`, `camera_worker`, and sorted `monitors` from the `/api/system` response. Preserve the current field labels and empty-table messages.
- [ ] Preserve the existing display rules: camera name prefers `connector`, then `cam{index}`, then normalized `key`; model prefers `model`, then `sensor`; Git dirty shows `unknown`, `no`, or `yes: file, file, ...`; commit time includes a browser-computed relative age; group/access booleans render as yes/no; missing values render as `-` or `unknown` according to the current page.
- [ ] Implement `loadLogs()` so no request occurs during bootstrap. On click, fetch `/api/logs?lines=200`, show returned `content`, and leave an operation-specific visible error on failure.
- [ ] Implement `runAction(path, label)` with one in-flight action at a time. A successful JSON response displays only the confirmed server `message` (or `Request accepted.`); a non-2xx response displays its detail; a network interruption displays `{label} result unconfirmed: <error>` and never claims completion.
- [ ] Bootstrap with `Promise.all([PlampWeb.bootstrapShell({activePath: "/system", headingSuffix: "System"}), PlampWeb.loadSystem()])`, render only after the system response succeeds, enable controls afterward, and leave controls disabled with `System setup failed: ...` after a failed load.
- [ ] Run the focused page tests and `node --check plamp_web/static/system.js`; expect all pass.
- [ ] Commit with `git commit -m "Build System as a static REST client"`.

### Task 2: Serve the static System page and remove Python rendering

**Files:**
- Modify: `plamp_web/server.py`
- Modify: `plamp_web/pages.py`
- Modify: `tests/test_config_api.py`
- Modify: `tests/test_pages.py`
- Modify: `plamp_web/README.md`

**Interfaces:**
- Consumes: `STATIC_DIR / "system.html"`.
- Produces: `GET /system -> FileResponse` without `system_response()`, `read_log_tail()`, role discovery, or Python HTML rendering.

- [ ] Add a failing route-isolation test that patches `system_response`, `read_log_tail`, and `configured_timer_roles` to raise, calls `get_system_page()`, and requires a `FileResponse` whose path is `system.html`.
- [ ] Run that test and confirm it fails because the current route reads system state and logs and calls `render_system_info_page`.
- [ ] Change `/system` to `FileResponse(STATIC_DIR / "system.html", media_type="text/html")`; remove the server import of `render_system_info_page`.
- [ ] Delete `render_system_info_page` and its now-unused `relative_time_label` helper. Replace renderer-coupled tests with static document/script contracts while retaining API tests for `/api/system`, `/api/logs`, restart, reinstall, and upgrade.
- [ ] Update `plamp_web/README.md` to identify `/system` as a static REST client whose logs are loaded on demand.
- [ ] Run focused tests, `python3 -m py_compile plamp_web/server.py plamp_web/pages.py tests/test_pages.py tests/test_config_api.py`, `node --check plamp_web/static/system.js`, `git diff --check`, and an `rg` scan proving `render_system_info_page` is absent.
- [ ] Run the full suite with `.venv/bin/python -m unittest discover -s tests -v`; expect zero failures.
- [ ] Commit with `git commit -m "Serve the System page as a static client"`.

### Task 3: Integrate and prove the System slice on Sprout

**Files:**
- No source changes unless verification finds a defect.

**Interfaces:**
- Consumes: the completed feature branch and `plampctl` workflow.
- Produces: pushed `main` and a verified Sprout System page; Tower remains unchanged.

- [ ] Fast-forward the clean `run-main` worktree, rerun the full suite there, and push `main`.
- [ ] Run `ssh hugo@sprout.local 'cd ~/plamp && ./plampctl upgrade main'`.
- [ ] Verify `/system` contains neutral markup, `system.js` returns 200, `/api/system` returns the expected sections, no `/api/logs` request is required to load the page, and an explicit log request returns valid JSON.
- [ ] Load `http://sprout.local/system`; visually confirm all tables, lazy logs, and action controls. Do not invoke restart, reinstall, or upgrade solely for page smoke testing.
- [ ] Confirm `plampctl status` reports the deployed revision, active service, clean Git state, and HTTP readiness; scan recent logs for application tracebacks.
