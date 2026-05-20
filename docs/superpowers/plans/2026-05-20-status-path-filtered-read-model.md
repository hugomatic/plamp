# Status Path Filtered Read Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `/api/status` the read surface for config plus live status, keep `/api/system` separate for host info, and update the UI and CLI to filter status reads by path.

**Architecture:** The server will return a unified status tree containing the config tree plus live controller/status nodes, and will filter that tree by dotted path on request. The browser and CLI will stop reading controller data from `/api/controllers/{role}` and will instead request filtered slices from `/api/status`, while `system` remains a separate `/api/system` snapshot and `/system` page.

**Tech Stack:** Python 3.11, FastAPI, Server-Sent Events, argparse, unittest.

---

### Task 1: Filtered status model in the server

**Files:**
- Modify: `plamp_web/server.py`
- Test: `tests/test_config_api.py`

- [ ] **Step 1: Write the failing tests**

Add tests that exercise the new read model directly:

```python
def test_get_status_returns_config_plus_live_status(self):
    with patch.object(server, "load_config", return_value={"controllers": {"pump_lights": {}}}), \
         patch.object(server, "controller_status_tree", return_value={"pump_lights": {"telemetry": {"connected": True}}}):
        data = server.get_status()

    self.assertEqual(data["config"]["controllers"]["pump_lights"], {})
    self.assertEqual(data["controllers"]["pump_lights"]["telemetry"]["connected"], True)


def test_get_status_with_path_filters_returns_ordered_nodes(self):
    with patch.object(server, "load_config", return_value={"controllers": {"pump_lights": {"label": "Pump"}}}), \
         patch.object(server, "controller_status_tree", return_value={"pump_lights": {"telemetry": {"connected": True}}}):
        data = server.get_status(path=["config.controllers.pump_lights", "controllers.pump_lights"])

    self.assertEqual(data, [
        {"path": "config.controllers.pump_lights", "node": {"label": "Pump"}},
        {"path": "controllers.pump_lights", "node": {"telemetry": {"connected": True}}},
    ])


def test_get_status_stream_uses_the_same_path_filters(self):
    response = server.get_status(stream=True, path=["config.controllers.pump_lights"])
    self.assertIsInstance(response, StreamingResponse)
    self.assertEqual(response.media_type, "text/event-stream")
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `uv run python -m unittest tests.test_config_api -v`

Expected: failures for the new filtered `get_status(...)` assertions and the new stream-path assertions.

- [ ] **Step 3: Implement the filtered read helpers**

Add a unified status tree and path filtering helpers in `plamp_web/server.py`:

```python
def status_response() -> dict[str, Any]:
    config = load_config()
    return {
        "config": config,
        "controllers": controller_status_tree(config),
        "monitors": monitor_summaries(),
        "camera_worker": camera_worker_summary(),
    }


def select_status_nodes(status: dict[str, Any], paths: list[str] | None) -> object:
    if not paths:
        return status
    return [select_status_node(status, path) for path in paths]


def select_status_node(status: dict[str, Any], path: str) -> dict[str, Any]:
    parts = [part for part in path.split(".") if part]
    current: Any = status
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            raise HTTPException(status_code=404, detail=f"unknown status path: {path}")
        current = current[part]
    return {"path": path, "node": current}
```

Wire `GET /api/status` to accept repeated `path` query params and return the filtered array when paths are supplied. Keep `/api/system` separate and leave `system_response()` untouched.

For streaming, keep the per-client filter list and emit only when the filtered payload changes. A simple polling loop is fine as long as the server compares the filtered snapshot and only yields when it changes.

- [ ] **Step 4: Run the server tests again**

Run: `uv run python -m unittest tests.test_config_api -v`

Expected: the new filtered status tests pass.

- [ ] **Step 5: Commit**

```bash
git add plamp_web/server.py tests/test_config_api.py
git commit -m "Add filtered status read model"
```

### Task 2: Status filtering in the CLI

**Files:**
- Modify: `plamp_cli/http.py`
- Modify: `plamp_cli/main.py`
- Test: `tests/test_plamp_cli_http.py`
- Test: `tests/test_plamp_cli.py`
- Update: `plamp_cli/README.md`

- [ ] **Step 1: Write the failing tests**

Add coverage for repeated `path=` query args and filtered status output:

```python
from unittest.mock import MagicMock, patch

def test_request_json_encodes_repeated_query_keys(self):
    with patch("plamp_cli.http.urlopen") as urlopen:
        response = MagicMock()
        response.read.return_value = b"{}"
        response.__enter__.return_value = response
        urlopen.return_value = response

        request_json(
            "GET",
            "http://127.0.0.1:8000",
            "/api/status",
            query={"path": ["config.controllers.pump_lights", "controllers.pump_lights"]},
        )

    request = urlopen.call_args.args[0]
    self.assertIn("path=config.controllers.pump_lights", request.full_url)
    self.assertIn("path=controllers.pump_lights", request.full_url)


def test_status_stream_supports_path_filters(self):
    code = main(["status", "--path", "config.controllers.pump_lights"], stdout=stdout, stderr=stderr)
    self.assertEqual(code, 0)
    self.assertIn("/api/status?stream=true&path=config.controllers.pump_lights", stdout.getvalue())
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `uv run python -m unittest tests.test_plamp_cli_http tests.test_plamp_cli -v`

Expected: failures for repeated query encoding and status path handling.

- [ ] **Step 3: Implement the CLI query builder**

Update `plamp_cli/http.py` so query strings support repeated keys:

```python
def _build_query_string(query: dict[str, Any] | None) -> str:
    if not query:
        return ""
    return f"?{urlencode(query, doseq=True)}"
```

Use that helper from `request_json(...)`. Keep `stream_json_events(...)` accepting a full path string so callers can pass `/api/status?stream=true&path=...` directly.

In `plamp_cli/main.py`, route controller read commands through `/api/status` instead of `/api/controllers/{role}`:

```python
def _handle_controllers(args: argparse.Namespace, base_url: str) -> object:
    if args.controllers_action == "get":
        return request_json("GET", base_url, "/api/status", query={"path": [f"config.controllers.{args.controller}", f"controllers.{args.controller}"]})
```

Keep `plamp system info` on `/api/system`, and make `plamp status` use `/api/status?stream=true` with optional `--path` filters added to the query string.

- [ ] **Step 4: Update the README and rerun tests**

Document the new read model in `plamp_cli/README.md`, then run:

`uv run python -m unittest tests.test_plamp_cli_http tests.test_plamp_cli -v`

- [ ] **Step 5: Commit**

```bash
git add plamp_cli/http.py plamp_cli/main.py plamp_cli/README.md tests/test_plamp_cli_http.py tests/test_plamp_cli.py
git commit -m "Route CLI reads through status"
```

### Task 3: Update the web pages and navigation

**Files:**
- Modify: `plamp_web/pages.py`
- Test: `tests/test_pages.py`

- [ ] **Step 1: Write the failing page tests**

Add assertions for the new page behavior:

```python
def test_settings_page_no_longer_renders_system_status(self):
    html = render_settings_page(summary)
    self.assertNotIn("System status", html)
    self.assertNotIn("hostname-status", html)


def test_timer_dashboard_uses_status_filters_instead_of_controller_get(self):
    html = render_timer_dashboard_page(["pump_lights"], "12h", {"pump_lights": []}, 0)
    self.assertIn("/api/status?stream=true&path=config.controllers", html)
    self.assertIn("/api/status?stream=true&path=controllers", html)


def test_api_test_page_can_add_multiple_status_paths(self):
    html = render_api_test_page(["pump_lights"], "pump_lights", "{}", "12h")
    self.assertIn("Add path", html)
    self.assertIn("Start stream", html)
    self.assertIn("/api/status", html)
```

- [ ] **Step 2: Run the page tests and confirm they fail**

Run: `uv run python -m unittest tests.test_pages -v`

Expected: failures for the missing status-filter UI and the lingering system block in settings.

- [ ] **Step 3: Implement the page changes**

Update `plamp_web/pages.py` so:

```python
MAIN_NAV = f'<nav><a href="/">Plamp</a> | <a href="/settings">Settings</a> | <a href="/system">System</a> | <a href="/api/test">API test</a> | <a href="{GITHUB_REPO_URL}">GitHub</a></nav>'
```

Then:

- remove the system info block from `render_settings_page(...)`
- keep `render_system_info_page(...)` on `/system` and continue to fetch its data from `/api/system`
- change `render_timer_dashboard_page(...)` to fetch controller config and controller telemetry from filtered `/api/status` requests instead of `/api/controllers/{role}` reads
- update `render_api_test_page(...)` so the GET section accepts multiple `path=` inputs and can run either a one-shot filtered request or a filtered SSE stream

The test page should make the filter list explicit so the user can see the exact paths being sent.

- [ ] **Step 4: Rerun the page tests**

Run: `uv run python -m unittest tests.test_pages -v`

Expected: the settings page no longer exposes system status, the system page still has the top menu, and the test API page exercises multi-path status reads and streaming.

- [ ] **Step 5: Commit**

```bash
git add plamp_web/pages.py tests/test_pages.py
git commit -m "Move UI reads to filtered status"
```

### Task 4: End-to-end verification and docs

**Files:**
- Modify: `tests/test_config_api.py`
- Modify: `tests/test_pages.py`
- Modify: `tests/test_plamp_cli_http.py`
- Modify: `tests/test_plamp_cli.py`
- Modify: `plamp_cli/README.md`

- [ ] **Step 1: Run the focused suite**

Run:

`uv run python -m unittest tests.test_config_api tests.test_pages tests.test_plamp_cli_http tests.test_plamp_cli -v`

Expected: all tests pass with the new status-filtered read model.

- [ ] **Step 2: Check for lingering controller GET reads**

Run:

`grep -R -n "/api/controllers/{role}\|GET /api/controllers/\|EventSource(/api/controllers" plamp_web plamp_cli tests`

Expected: only write paths or intentional legacy assertions remain.

- [ ] **Step 3: Commit the finished implementation**

```bash
git add plamp_web/pages.py plamp_web/server.py plamp_cli/http.py plamp_cli/main.py plamp_cli/README.md tests/test_config_api.py tests/test_pages.py tests/test_plamp_cli_http.py tests/test_plamp_cli.py
git commit -m "Route reads through filtered status"
```
