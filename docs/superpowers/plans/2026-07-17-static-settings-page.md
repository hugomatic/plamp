# Static Settings Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add shared static web navigation and convert `/settings` into a runtime-neutral REST client without changing settings behavior or public URLs.

**Architecture:** FastAPI serves checkout-owned HTML, CSS, and JavaScript files. A shared browser module builds navigation from `/api/controllers` and `/api/system`; the settings module builds and saves its editor from `/api/config` and `/api/system`. Python retains API/domain behavior but no longer renders the settings document.

**Tech Stack:** Plain HTML, CSS, browser JavaScript, FastAPI `FileResponse`/`StaticFiles`, Python `unittest`, Node syntax checking.

## Global Constraints

- No SPA, React, client router, bundler, Node runtime dependency, or JavaScript package toolchain.
- Browser runtime state comes only from REST/SSE; static files contain no injected host or Plamp state.
- Preserve `/`, `/settings`, `/system`, `/controllers/{controller}`, and `/api/test` URLs.
- Shared menu discovers controllers with `GET /api/controllers` and host/revision with `GET /api/system`.
- Existing settings saves continue through `PUT /api/config` and `PUT /api/config/cameras`.
- A load failure disables save actions and names the failed operation; a save failure preserves form contents.
- Deploy and smoke-test this slice on Sprout; do not update Tower.

---

### Task 1: Shared static browser shell

**Files:**
- Create: `plamp_web/static/app.css`
- Create: `plamp_web/static/app.js`
- Modify: `plamp_web/static/index.html`
- Modify: `plamp_web/server.py`
- Test: `tests/test_pages.py`
- Test: `tests/test_config_api.py`

**Interfaces:**
- Consumes: `GET /api/controllers -> {controllers: Record<string, {firmware: string}>}` and `GET /api/system -> {host: {hostname: string}, software: {git_short_commit?: string, git_commit?: string}}` (additional response fields are ignored by the shell).
- Produces: `window.PlampWeb.responseJson(response, label)`, `window.PlampWeb.loadSystem()`, `window.PlampWeb.loadControllers()`, and `window.PlampWeb.bootstrapShell({activePath, headingSuffix})`.

- [ ] **Step 1: Add failing shared-shell contracts**

Add tests that read `app.js`, `app.css`, and `index.html` and assert:

```python
def test_shared_shell_discovers_navigation_from_rest(self):
    shell = static_text("app.js")
    dashboard = static_text("index.html")
    self.assertIn('fetch("/api/controllers")', shell)
    self.assertIn('fetch("/api/system")', shell)
    self.assertIn("window.PlampWeb", shell)
    self.assertIn('<script src="/static/app.js"></script>', dashboard)
    self.assertNotIn("function renderMainNav", dashboard)

def test_static_assets_are_served(self):
    paths = {route.path for route in server.app.routes}
    self.assertIn("/static", paths)
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_pages.PageRenderTests.test_shared_shell_discovers_navigation_from_rest \
  tests.test_config_api.ConfigApiTests.test_static_assets_are_served -v
```

Expected: failure because `app.js`, `app.css`, and the `/static` mount do not exist.

- [ ] **Step 3: Implement the shared shell**

Mount `STATIC_DIR` without an HTML index fallback:

```python
from fastapi.staticfiles import StaticFiles

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
```

Create an IIFE in `app.js` with memoized REST reads and DOM-only navigation:

```javascript
(() => {
  const GITHUB = "https://github.com/hugomatic/plamp";
  let systemPromise;
  let controllersPromise;

  async function responseJson(response, label) {
    if (!response.ok) throw new Error(`${label}: ${response.status} ${response.statusText}`);
    return response.json();
  }
  function loadSystem() {
    systemPromise ||= fetch("/api/system").then((response) => responseJson(response, "system"));
    return systemPromise;
  }
  function loadControllers() {
    controllersPromise ||= fetch("/api/controllers").then((response) => responseJson(response, "controllers"));
    return controllersPromise;
  }
  function addLink(nav, href, label, activePath) {
    if (nav.childNodes.length) nav.append(" | ");
    const link = document.createElement("a");
    link.href = href;
    link.textContent = label;
    if (href === activePath) link.setAttribute("aria-current", "page");
    nav.append(link);
  }
  async function bootstrapShell({activePath = location.pathname, headingSuffix = "Plamp"} = {}) {
    const nav = document.querySelector("[data-plamp-nav]");
    const [systemResult, controllersResult] = await Promise.allSettled([loadSystem(), loadControllers()]);
    const system = systemResult.status === "fulfilled" ? systemResult.value : {};
    const controllerMap = controllersResult.status === "fulfilled" && controllersResult.value.controllers && typeof controllersResult.value.controllers === "object"
      ? controllersResult.value.controllers : {};
    const controllerIds = Object.keys(controllerMap);
    nav.replaceChildren();
    addLink(nav, "/", "Plamp", activePath);
    for (const controllerId of controllerIds) addLink(nav, `/controllers/${encodeURIComponent(controllerId)}`, controllerId, activePath);
    addLink(nav, "/settings", "Settings", activePath);
    addLink(nav, "/system", "System", activePath);
    addLink(nav, "/api/test", "API test", activePath);
    const revision = String(system?.software?.git_short_commit || system?.software?.git_commit || "unknown");
    if (revision === "unknown") nav.append(" | [rev unknown]");
    else addLink(nav, `${GITHUB}/commit/${encodeURIComponent(revision)}`, `[rev ${revision}]`, activePath);
    const hostname = String(system?.host?.hostname || "");
    document.title = hostname ? `${hostname} ${headingSuffix}` : headingSuffix;
    return {system, controllers: controllerIds};
  }
  window.PlampWeb = {bootstrapShell, loadControllers, loadSystem, responseJson};
})();
```

Add shared shell CSS, change the dashboard nav to `<nav data-plamp-nav>`, load `/static/app.css` and `/static/app.js`, delete its private navigation functions, and use `bootstrapShell()` during dashboard bootstrap. Keep its existing `/api/system` payload reuse by accepting the shell result rather than fetching system twice.

- [ ] **Step 4: Run focused tests and JavaScript syntax checks**

Run:

```bash
.venv/bin/python -m unittest tests.test_pages tests.test_config_api.ConfigApiTests.test_static_assets_are_served -v
node --check plamp_web/static/app.js
node --check <(sed -n '/<script>/,/<\/script>/p' plamp_web/static/index.html | sed '1d;$d')
```

Expected: tests pass and both Node checks exit 0.

- [ ] **Step 5: Commit the shared shell**

```bash
git add plamp_web/static/app.css plamp_web/static/app.js plamp_web/static/index.html plamp_web/server.py tests/test_pages.py tests/test_config_api.py
git commit -m "Share static Plamp web navigation"
```

### Task 2: Runtime-neutral static settings client

**Files:**
- Create: `plamp_web/static/settings.html`
- Create: `plamp_web/static/settings.js`
- Modify: `tests/test_pages.py`

**Interfaces:**
- Consumes: `PlampWeb.bootstrapShell()`, `GET /api/config`, and the `system` payload returned by the shared shell.
- Produces: `bootstrapSettings(): Promise<void>`, DOM render helpers for scheduler controllers/devices/cameras, and the existing configuration save payloads.

- [ ] **Step 1: Replace renderer-string tests with failing static contracts**

Make settings behavior tests read `settings.html` plus `settings.js`. Add explicit neutral/bootstrap assertions:

```python
def test_settings_static_client_bootstraps_only_from_rest(self):
    html = static_text("settings.html")
    script = static_text("settings.js")
    self.assertIn('data-plamp-nav', html)
    self.assertIn('fetch("/api/config")', script)
    self.assertIn("PlampWeb.bootstrapShell", script)
    self.assertNotIn("pump_lights", html)
    self.assertNotIn("abc123", html)

def test_settings_load_failure_disables_saves(self):
    script = static_text("settings.js")
    self.assertIn("setSaveDisabled(true)", script)
    self.assertIn('showLoadError("Settings setup failed:', script)
```

Retain assertions for controller/device ordering, hidden-controller preservation, camera matching, required pins, controller renames, capture-path normalization, and the exact save endpoints by checking the static script functions that now implement them.

- [ ] **Step 2: Run settings page tests and verify RED**

Run:

```bash
.venv/bin/python -m unittest tests.test_pages -v
```

Expected: failure because `settings.html` and `settings.js` do not exist.

- [ ] **Step 3: Create neutral settings markup**

Create semantic containers with no configured rows or host state:

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Settings</title>
  <link rel="icon" href="/favicon.svg" type="image/svg+xml">
  <link rel="stylesheet" href="/static/app.css">
</head>
<body>
  <nav data-plamp-nav aria-label="Plamp"></nav>
  <h1 id="settings-heading">Settings</h1>
  <p id="settings-load-status" class="status">Loading settings...</p>
  <p><a href="https://github.com/hugomatic/plamp/issues/new">Report an issue</a></p>
  <section aria-label="Plamp config">
    <h2>Plamp config</h2>
    <h3>Pico schedulers</h3>
    <div id="scheduler-blocks"></div>
    <button id="save-controllers" type="button" disabled>Save controllers</button>
    <span id="controllers-status" class="status">Loading.</span>
    <button id="save-devices" type="button" disabled>Save devices</button>
    <span id="devices-status" class="status">Loading.</span>
    <h3>Cameras</h3>
    <table><thead><tr><th>ID</th><th>Label</th><th>Assigned peripheral</th><th>Capture dir</th><th>Every seconds</th><th>Autofocus</th><th>Autofocus delay ms</th></tr></thead><tbody id="camera-rows"></tbody></table>
    <button id="save-cameras" type="button" disabled>Save cameras</button>
    <span id="cameras-status" class="status">Loading.</span>
  </section>
  <script src="/static/app.js"></script>
  <script src="/static/settings.js"></script>
</body>
</html>
```

- [ ] **Step 4: Port settings presentation and collection to browser JavaScript**

Implement `settings.js` as an IIFE. Preserve object insertion order by iterating `Object.entries()` without sorting. Normalize detected camera keys with `/[^A-Za-z0-9_-]+/g` and build all DOM with `createElement`/`textContent` rather than HTML strings. Use these exact boundaries and algorithms:

- `renderSettings(config, system)` clears both row containers, walks scheduler controllers and nested `settings.devices`, appends one blank device row per visible controller, appends one blank controller block, matches configured cameras to normalized `system.detected.cameras`, and appends one blank camera row.
- `collectControllers()` begins with a structured clone of hidden scheduler controllers, applies visible controller IDs, labels, types, and Pico serials, deletes renamed keys, and preserves unedited hidden payload/settings fields.
- `collectControllerDevices()` rejects blank pins and missing controller IDs, converts pins to numbers, assigns `display_order` in DOM order, and returns nested device settings with `visibility`, `programming`, `editor`, and `output_type`.
- `collectCameras()` returns camera label, detected key, normalized capture directory, numeric capture interval, autofocus mode, and numeric autofocus delay, omitting blank optional values.
- `collectConfigWithControllerRenames()` applies the rename map to collected devices, rejects devices assigned to unknown controllers, and puts each device map at `controllers[id].settings.devices` while removing legacy `payload.devices`.
- `saveSection(statusId, url, payload)` sets `Saving...`, sends JSON with `PUT`, reloads only after a successful response, and otherwise leaves the form intact while displaying status plus response text or the thrown network error.

Use this complete bootstrap and failure boundary:

```javascript
async function bootstrapSettings() {
  try {
    const [{system}, configResponse] = await Promise.all([
      PlampWeb.bootstrapShell({activePath: "/settings", headingSuffix: "Settings"}),
      fetch("/api/config"),
    ]);
    const configPayload = await PlampWeb.responseJson(configResponse, "config");
    renderSettings(configPayload?.config || {}, system || {});
    setSaveDisabled(false);
    showLoadStatus("Ready.");
  } catch (error) {
    setSaveDisabled(true);
    showLoadError(`Settings setup failed: ${error.message || String(error)}`);
  }
}
bootstrapSettings();
```

The port must keep the current defaults: Pico scheduler type, blank new controller/device/camera rows, GPIO output, cycle editor, autofocus `auto`, capture interval `0`, and default daily window `06:00`–`18:00` when switching to a clock window.

- [ ] **Step 5: Run static behavior tests and JavaScript syntax check**

Run:

```bash
.venv/bin/python -m unittest tests.test_pages -v
node --check plamp_web/static/settings.js
```

Expected: all page tests pass and Node exits 0.

- [ ] **Step 6: Commit the static settings client**

```bash
git add plamp_web/static/settings.html plamp_web/static/settings.js tests/test_pages.py
git commit -m "Build settings as a static REST client"
```

### Task 3: Serve static settings and remove Python presentation

**Files:**
- Modify: `plamp_web/server.py`
- Modify: `plamp_web/pages.py`
- Modify: `tests/test_config_api.py`
- Modify: `tests/test_pages.py`
- Modify: `plamp_web/README.md`

**Interfaces:**
- Consumes: `STATIC_DIR / "settings.html"` and the existing REST APIs.
- Produces: `GET /settings -> FileResponse` without calling `settings_summary()` or `render_settings_page()`.

- [ ] **Step 1: Add the failing route isolation test**

```python
def test_settings_route_is_static_file(self):
    with (
        patch.object(server, "settings_summary", side_effect=AssertionError("must not render")),
        patch.object(server, "render_settings_page", side_effect=AssertionError("must not render"), create=True),
    ):
        response = server.get_settings_page()
    self.assertIsInstance(response, FileResponse)
    self.assertEqual(Path(response.path), server.STATIC_DIR / "settings.html")
```

- [ ] **Step 2: Run the route test and verify RED**

Run:

```bash
.venv/bin/python -m unittest tests.test_config_api.ConfigApiTests.test_settings_route_is_static_file -v
```

Expected: failure because the route still invokes the Python renderer.

- [ ] **Step 3: Switch the route and delete obsolete renderer code**

Use:

```python
@app.get("/settings", response_class=FileResponse)
def get_settings_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "settings.html", media_type="text/html")
```

Remove the `render_settings_page` import and function. Remove Python presentation helpers only when `rg` proves no remaining renderer uses them. Keep domain/config helpers used by REST responses. Document that `/` and `/settings` are static clients while the other pages remain Python-rendered.

- [ ] **Step 4: Run focused and full verification**

Run:

```bash
.venv/bin/python -m unittest tests.test_pages tests.test_config_api -v
.venv/bin/python -m unittest discover -s tests -v
python3 -m py_compile plamp_web/server.py plamp_web/pages.py tests/test_pages.py tests/test_config_api.py
node --check plamp_web/static/app.js
node --check plamp_web/static/settings.js
git diff --check
rg -n 'render_settings_page|settings_summary\(\).*get_settings_page' plamp_web tests
```

Expected: 0 failures, syntax checks exit 0, clean diff check, and no settings renderer reference.

- [ ] **Step 5: Commit the route boundary**

```bash
git add plamp_web/server.py plamp_web/pages.py plamp_web/README.md tests/test_pages.py tests/test_config_api.py
git commit -m "Serve settings as a static client"
```

### Task 4: Integrate and prove the slice on Sprout

**Files:**
- No source changes unless verification reveals a defect.

**Interfaces:**
- Consumes: the completed branch and `plampctl` deployment workflow.
- Produces: `main` containing the slice and a verified Sprout deployment; Tower remains unchanged.

- [ ] **Step 1: Review and integrate the branch into `main`**

Verify the branch is clean, review `git diff origin/main...HEAD`, merge it into the clean `run-main` worktree, and push `main` only after the full suite passes there.

- [ ] **Step 2: Upgrade Sprout through its control tool**

Run:

```bash
ssh hugo@sprout.local 'cd ~/plamp && ./plampctl upgrade main'
```

Expected: fast-forward, dependency sync, restart, and HTTP readiness success.

- [ ] **Step 3: Smoke-test the live static boundary**

Verify on Sprout:

```bash
curl -fsS http://127.0.0.1:8000/settings -o /tmp/plamp-settings.html
grep -q 'src="/static/settings.js"' /tmp/plamp-settings.html
grep -q 'data-plamp-nav' /tmp/plamp-settings.html
curl -fsS http://127.0.0.1:8000/static/settings.js -o /tmp/plamp-settings.js
curl -fsS http://127.0.0.1:8000/api/config -o /tmp/plamp-config.json
curl -fsS http://127.0.0.1:8000/api/system -o /tmp/plamp-system.json
```

Then load `http://sprout.local/settings` in a browser and confirm the controller,
device, and camera fields match Sprout's current configuration. Do not perform a
live save solely for the smoke test.

- [ ] **Step 4: Check service truth after browser load**

Run `./plampctl status` and inspect recent `./plampctl logs --lines 60` on Sprout.
Expected: service active, HTTP ready, deployed revision equals `main`, settings
assets/APIs return 200, and no application traceback appears.
