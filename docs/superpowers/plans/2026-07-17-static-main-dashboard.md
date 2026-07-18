# Static Main Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Serve the main dashboard as a checkout-owned static HTML client whose runtime state comes exclusively from REST and SSE.

**Architecture:** Move the existing dashboard HTML, CSS, and JavaScript unchanged into `plamp_web/static/index.html`, then replace its six injected values with a browser bootstrap over existing APIs. FastAPI serves the file but does not render or inject dashboard state; the existing REST/SSE contract and UI behavior remain unchanged.

**Tech Stack:** Static HTML/CSS/JavaScript, FastAPI `FileResponse`, REST, SSE `EventSource`, Python `unittest`.

## Global Constraints

- The browser obtains controller roles/channels/time format from `GET /api/timer-config`.
- The browser obtains host clock data from `GET /api/host-time`.
- The browser obtains camera IDs from `GET /api/config`.
- The browser obtains hostname and Git revision from `GET /api/system`.
- Existing controller SSE, schedule editing, camera capture/gallery, stale-state freezing, and auto-refresh behavior remain unchanged.
- The root route performs no controller discovery, config loading, clock lookup, camera lookup, hostname lookup, or Python page rendering.
- The static page contains no configured controller IDs, camera IDs, hostname, host seconds, or revision at rest.
- REST/SSE server behavior outside `GET /` is unchanged.
- CORS and separate-service hosting are subsequent work.

---

### Task 1: Specify the static boundary

**Files:**
- Modify: `tests/test_pages.py`
- Modify: `tests/test_config_api.py`

**Interfaces:**
- Consumes: `plamp_web/static/index.html` and `plamp_web.server.get_timer_dashboard_page()`.
- Produces: tests proving the file is runtime-neutral, bootstraps through four existing APIs, and is returned without invoking Python rendering.

- [ ] **Step 1: Add failing static-file contract tests**

Add a helper that reads `plamp_web/static/index.html`. Assert the file exists and contains all four bootstrap fetches:

```javascript
fetch("/api/timer-config")
fetch("/api/host-time")
fetch("/api/config")
fetch("/api/system")
```

Assert it initializes mutable `timerRoles`, `timerChannels`, `clockTimeFormat`, and `timerHostSecondsAtLoad`, populates navigation and camera selectors with DOM methods, and starts streams only after bootstrap succeeds.

- [ ] **Step 2: Add a failing root-route isolation test**

Patch `plamp_web.server.render_timer_dashboard_page`, `configured_timer_roles`, `configured_timer_channels`, `configured_time_format`, `configured_camera_ids`, and `seconds_since_midnight` to raise if called. Invoke `get_timer_dashboard_page()` and assert it returns a `FileResponse` whose path is `STATIC_DIR / "index.html"`.

- [ ] **Step 3: Run focused tests and verify RED**

```bash
/home/hugo/.openclaw/workspace/code/plamp/.worktrees/run-main/.venv/bin/python -m unittest tests.test_pages tests.test_config_api.ConfigApiTests.test_timer_dashboard_root_is_static_file -v
```

Expected: failure because the static dashboard does not exist and the root route still renders with six server-side values.

---

### Task 2: Move the existing dashboard into a static asset

**Files:**
- Create: `plamp_web/static/index.html`
- Modify: `plamp_web/pages.py`
- Modify: `tests/test_pages.py`

**Interfaces:**
- Consumes: the exact HTML template currently returned by `render_timer_dashboard_page`.
- Produces: one runtime-neutral static document preserving the dashboard DOM, CSS, and JavaScript behavior.

- [ ] **Step 1: Render one neutral migration copy**

Use the existing renderer once with empty values (`roles=[]`, `time_format="12h"`, `channels={}`, `host_seconds=0`, `camera_ids=[]`, `hostname=""`) to create `plamp_web/static/index.html`. This is a mechanical source migration, not runtime generation.

- [ ] **Step 2: Replace injected constants with mutable bootstrap state**

Use these initial values in the static script:

```javascript
let clockTimeFormat = "12h";
let timerRoles = [];
let timerChannels = {};
let timerHostSecondsAtLoad = 0;
let timerHostLoadedAt = Date.now();
```

Give the nav and heading stable IDs, leave the camera select with only `Default camera`, and remove all revision/controller links from the stored file.

- [ ] **Step 3: Remove the obsolete Python dashboard renderer**

Delete `render_timer_dashboard_page` from `plamp_web/pages.py`. Update page tests to read the static file instead of calling the renderer. Tests that formerly asserted injected hostname, camera options, controller links, or initial values must instead assert the corresponding DOM bootstrap functions.

- [ ] **Step 4: Run page tests**

```bash
/home/hugo/.openclaw/workspace/code/plamp/.worktrees/run-main/.venv/bin/python -m unittest tests.test_pages -v
```

Expected: all page behavior tests pass against the static asset.

---

### Task 3: Bootstrap exclusively through REST and serve the file

**Files:**
- Modify: `plamp_web/static/index.html`
- Modify: `plamp_web/server.py`
- Modify: `tests/test_pages.py`
- Modify: `tests/test_config_api.py`

**Interfaces:**
- Consumes: JSON from `/api/timer-config`, `/api/host-time`, `/api/config`, and `/api/system`.
- Produces: `bootstrapDashboard(): Promise<void>` and `GET / -> FileResponse(STATIC_DIR / "index.html")`.

- [ ] **Step 1: Add the browser bootstrap**

Implement `fetchJson(url)`, `renderMainNav(controllerIds, revision)`, `populateCameraSelectors(cameraIds)`, and `bootstrapDashboard()`. The bootstrap concurrently fetches the four APIs, validates `response.ok`, assigns timer state, resets the host-load timestamp, sets `<title>` and `<h1>` from `system.host.hostname`, renders nav links using DOM nodes/text content, populates camera options, then calls `refreshHostClock()`, `startTimerStreams()`, and `refreshCameraCaptures()`.

On failure, set `timer-stream-status` to `Dashboard setup failed: <message>` and do not start SSE.

- [ ] **Step 2: Serve the static file**

Remove the dashboard renderer import and replace the root route with:

```python
@app.get("/", response_class=FileResponse)
def get_timer_dashboard_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html", media_type="text/html")
```

- [ ] **Step 3: Run focused static-dashboard verification**

```bash
/home/hugo/.openclaw/workspace/code/plamp/.worktrees/run-main/.venv/bin/python -m unittest tests.test_pages tests.test_config_api -v
python3 -m py_compile plamp_web/server.py plamp_web/pages.py tests/test_pages.py tests/test_config_api.py
```

Expected: all focused tests pass and Python compilation succeeds.

- [ ] **Step 4: Run the full suite and static scan**

```bash
/home/hugo/.openclaw/workspace/code/plamp/.worktrees/run-main/.venv/bin/python -m unittest discover -s tests -v
rg -n 'render_timer_dashboard_page|__ROLES__|__CHANNELS__|__HOST_SECONDS__|__CAMERA_OPTIONS__|__PAGE_NAME__' plamp_web tests
git diff --check
```

Expected: 464 or more tests pass; the scan finds no removed renderer or server placeholder; whitespace checks pass.

- [ ] **Step 5: Commit**

```bash
git add plamp_web/static/index.html plamp_web/pages.py plamp_web/server.py tests/test_pages.py tests/test_config_api.py docs/superpowers/plans/2026-07-17-static-main-dashboard.md
git commit -m "Serve the main dashboard as a static client"
```
