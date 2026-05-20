# System Info Page and Status Stream Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split host identity from live status, add a streaming `plamp status` command, and add a small system info page with restart/reinstall/upgrade/logs actions.

**Spec:** [`docs/superpowers/specs/2026-05-20-system-info-page-and-status-stream-design.md`](../specs/2026-05-20-system-info-page-and-status-stream-design.md)

**Architecture:** Treat `/api/system` as the one-shot host snapshot, `/api/status?stream=true` as the live read stream, and a new `/system` page as the human-facing operator surface. Keep the write path server-authoritative: the page calls server endpoints for restart/reinstall/upgrade, and the server republished full status snapshots after changes instead of trying to merge incremental client state.

**Tech Stack:** Python 3.11, FastAPI/StreamingResponse, argparse, plain HTML/JS, stdlib `unittest`.

---

## File Structure

- Modify `plamp_cli/http.py`: add a small SSE JSON iterator helper for `/api/status?stream=true`.
- Modify `plamp_cli/main.py`: rename the one-shot system command to `system info`, add `status` as the streaming command, and keep JSON/pretty output consistent.
- Modify `tests/test_plamp_cli_http.py` and `tests/test_plamp_cli.py`: cover SSE parsing, command dispatch, and output formatting.
- Modify `plamp_cli/README.md`: document `plamp system info` and `plamp status`.
- Modify `plamp_web/server.py`: add the status stream response, add restart/reinstall/upgrade endpoints, and serve the system page.
- Modify `plamp_web/pages.py`: add a dedicated system info page renderer and a nav link to it.
- Modify `tests/test_config_api.py` and `tests/test_pages.py`: cover the new endpoints and page content.
- Modify `plamp_web/README.md`: document the new page and action endpoints.

## Task 1: Split CLI Snapshot And Stream Commands

**Files:**
- Modify: `plamp_cli/http.py`
- Modify: `plamp_cli/main.py`
- Modify: `tests/test_plamp_cli_http.py`
- Modify: `tests/test_plamp_cli.py`
- Modify: `plamp_cli/README.md`

- [ ] **Step 1: Write the failing parser, snapshot, and stream tests**

Add these tests:

```python
# tests/test_plamp_cli_http.py
@patch("plamp_cli.http.urlopen")
def test_stream_json_events_yields_sse_json_payloads(self, urlopen):
    response = unittest.mock.MagicMock()
    response.__enter__.return_value.readline.side_effect = [
        b"event: snapshot\n",
        b'data: {"controllers": {}}\n',
        b"\n",
        b"event: status\n",
        b'data: {"controllers": {"octo_relay": {"state": "connected"}}}\n',
        b"\n",
        b"",
    ]
    urlopen.return_value = response

    events = list(stream_json_events("http://127.0.0.1:8000", "/api/status?stream=true"))
    self.assertEqual(
        events,
        [
            {"controllers": {}},
            {"controllers": {"octo_relay": {"state": "connected"}}},
        ],
    )
```

```python
# tests/test_plamp_cli.py
def test_build_parser_accepts_system_info_and_status(self):
    parser = build_parser()

    info_args = parser.parse_args(["system", "info"])
    status_args = parser.parse_args(["status", "--pretty"])

    self.assertEqual(info_args.area, "system")
    self.assertEqual(info_args.system_action, "info")
    self.assertEqual(status_args.area, "status")
    self.assertTrue(status_args.pretty)

@patch("plamp_cli.main.request_json")
def test_system_info_reads_api_system(self, request_json):
    request_json.return_value = {"hostname": "sprout", "software": {"git_branch": "main"}}
    stdout = StringIO()
    stderr = StringIO()

    code = main(["system", "info"], stdout=stdout, stderr=stderr)

    self.assertEqual(code, 0)
    request_json.assert_called_once_with("GET", "http://127.0.0.1:8000", "/api/system")
    self.assertEqual(stderr.getvalue(), "")

@patch("plamp_cli.main.stream_json_events")
def test_status_stream_writes_each_json_event(self, stream_json_events):
    stream_json_events.return_value = iter([
        {"controllers": {}},
        {"controllers": {"octo_relay": {"state": "connected"}}},
    ])
    stdout = StringIO()
    stderr = StringIO()

    code = main(["status"], stdout=stdout, stderr=stderr)

    self.assertEqual(code, 0)
    self.assertIn('"controllers": {}', stdout.getvalue())
    self.assertIn('"state": "connected"', stdout.getvalue())
    self.assertEqual(stderr.getvalue(), "")
```

Also update the old `system status` expectations so the parser rejects it and the usage hint points at `system info`.

- [ ] **Step 2: Run the CLI tests and confirm they fail**

Run:

```bash
uv run python -m unittest tests.test_plamp_cli_http tests.test_plamp_cli -v
```

Expected: failures for missing `stream_json_events`, missing `status` command dispatch, and the old `system status` shape.

- [ ] **Step 3: Implement the SSE helper and command split**

Add a new helper in `plamp_cli/http.py`:

```python
def stream_json_events(base_url: str, path: str):
    request = Request(f"{base_url}{path}", method="GET", headers={"Accept": "text/event-stream"})
    try:
        with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            data_lines: list[str] = []
            for raw_line in response:
                line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                if not line:
                    if data_lines:
                        yield json.loads("\n".join(data_lines))
                        data_lines = []
                    continue
                if line.startswith("data:"):
                    data_lines.append(line[5:].lstrip())
    except HTTPError as exc:
        detail = _clean_error_detail(exc.read(), str(exc.reason))
        raise ApiError(exc.code, detail) from exc
    except URLError as exc:
        raise NetworkError(str(exc.reason)) from exc
```

Update `plamp_cli/main.py` to:

```python
_AREAS = ("config", "controllers", "system", "status", "pico-scheduler", "pics", "firmware")

system_info = system_subparsers.add_parser("info")
system_info.set_defaults(system_action="info")

status = subparsers.add_parser("status")
status.set_defaults(area="status")

def _handle_system(args: argparse.Namespace, base_url: str) -> object:
    if args.system_action == "info":
        return request_json("GET", base_url, "/api/system")
    raise ValueError(f"unsupported system action: {args.system_action}")

def _handle_status(args: argparse.Namespace, base_url: str) -> object:
    return stream_json_events(base_url, "/api/status?stream=true")
```

Make `main()` write each streamed event with `format_json_output(event, pretty=args.pretty)` and reject the old `system status` subcommand.

- [ ] **Step 4: Rerun the CLI tests**

Run:

```bash
uv run python -m unittest tests.test_plamp_cli_http tests.test_plamp_cli -v
```

Expected: pass.

- [ ] **Step 5: Commit the CLI split**

```bash
git add plamp_cli/http.py plamp_cli/main.py tests/test_plamp_cli_http.py tests/test_plamp_cli.py plamp_cli/README.md
git commit -m "Split system info and status stream commands"
```

## Task 2: Add Status Streaming And Operator Endpoints

**Files:**
- Modify: `plamp_web/server.py`
- Modify: `tests/test_config_api.py`
- Modify: `plamp_web/README.md`

- [ ] **Step 1: Write the failing API tests**

Add direct server tests for the new behavior:

```python
from fastapi.responses import StreamingResponse

def test_get_status_stream_returns_streaming_response(self):
    response = server.get_status(stream=True)
    self.assertIsInstance(response, StreamingResponse)

@patch.object(server, "run_plampctl_action")
def test_post_system_restart_invokes_plampctl_restart(self, run_plampctl_action):
    run_plampctl_action.return_value = {"message": "restarted"}

    result = server.post_system_restart()

    self.assertEqual(result["message"], "restarted")
    run_plampctl_action.assert_called_once_with("restart")

@patch.object(server, "run_plampctl_action")
def test_post_system_upgrade_invokes_plampctl_upgrade(self, run_plampctl_action):
    run_plampctl_action.return_value = {"message": "upgraded"}

    result = server.post_system_upgrade()

    self.assertEqual(result["message"], "upgraded")
    run_plampctl_action.assert_called_once_with("upgrade")
```

Add a stream test that asserts the first SSE payload is a snapshot and that the route exists:

```python
def test_status_stream_emits_snapshot_event(self):
    response = server.get_status(stream=True)
    self.assertEqual(response.media_type, "text/event-stream")
```

- [ ] **Step 2: Run the API tests and confirm they fail**

Run:

```bash
uv run python -m unittest tests.test_config_api -v
```

Expected: failures for missing `run_plampctl_action`, missing system action endpoints, or missing `stream=true` support.

- [ ] **Step 3: Implement the server helpers and endpoints**

Add a small command runner in `plamp_web/server.py`:

```python
def run_plampctl_action(*args: str) -> dict[str, Any]:
    completed = subprocess.run(
        [str(REPO_ROOT / "plampctl"), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise HTTPException(status_code=500, detail=(completed.stderr or completed.stdout or "plampctl failed").strip())
    return json.loads(completed.stdout or "{}")
```

Add the operator endpoints:

```python
@app.post("/api/system/restart")
def post_system_restart() -> dict[str, Any]:
    return run_plampctl_action("restart")

@app.post("/api/system/reinstall")
def post_system_reinstall() -> dict[str, Any]:
    return run_plampctl_action("reinstall")

@app.post("/api/system/upgrade")
def post_system_upgrade() -> dict[str, Any]:
    return run_plampctl_action("upgrade")
```

Add streaming support to `/api/status`:

```python
@app.get("/api/status")
def get_status(stream: bool = False) -> Any:
    if stream:
        return stream_status()
    return status_response()
```

Implement `stream_status()` with `StreamingResponse`, `sse_message()`, a small subscriber queue, and a snapshot event on connect. Reuse the existing `queue`/`StreamingResponse` pattern from `stream_timer_events()`, but publish full `status_response()` payloads.

- [ ] **Step 4: Rerun the API tests**

Run:

```bash
uv run python -m unittest tests.test_config_api -v
```

Expected: pass.

- [ ] **Step 5: Commit the server work**

```bash
git add plamp_web/server.py tests/test_config_api.py plamp_web/README.md
git commit -m "Add status stream and system actions"
```

## Task 3: Add The System Info Page

**Files:**
- Modify: `plamp_web/pages.py`
- Modify: `tests/test_pages.py`
- Modify: `plamp_web/README.md`

- [ ] **Step 1: Write the failing page tests**

Add a renderer test for the new page:

```python
def test_system_info_page_shows_actions_and_no_hostname_editor(self):
    html = render_system_info_page(
        {
            "system": {
                "hostname": "sprout",
                "software": {"git_branch": "main", "git_short_commit": "6e2cf82"},
                "host": {"hostname": "sprout"},
            },
            "logs": "plamp-web started",
        }
    )

    self.assertIn("<h2>System info</h2>", html)
    self.assertIn("Restart", html)
    self.assertIn("Reinstall", html)
    self.assertIn("Upgrade", html)
    self.assertIn("Logs", html)
    self.assertNotIn('id="hostname-input"', html)
```

Add a navigation test so the new page is linked everywhere the shared nav appears:

```python
def test_pages_use_same_nav_with_system_link(self):
    expected = '<nav><a href="/">Plamp</a> | <a href="/settings">Settings</a> | <a href="/system">System</a> | <a href="/api/test">API test</a> | <a href="https://github.com/hugomatic/plamp">GitHub</a></nav>'
    html = render_system_info_page({"system": {"hostname": "sprout"}, "logs": ""})
    self.assertIn(expected, html)
```

- [ ] **Step 2: Run the page tests and confirm they fail**

Run:

```bash
uv run python -m unittest tests.test_pages -v
```

Expected: failures because `render_system_info_page` and the `/system` nav entry do not exist yet.

- [ ] **Step 3: Implement the page renderer and route**

Add a new renderer in `plamp_web/pages.py`:

```python
def render_system_info_page(system: dict[str, Any], logs_text: str = "") -> str:
    hostname = str(system.get("hostname") or "")
    page_title = f"{hostname} System" if hostname else "System"
    logs_block = html.escape(logs_text or "")
    return f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>{html.escape(page_title)}</title></head>
<body>
  {MAIN_NAV}
  <h1>{html.escape(page_title)}</h1>
  <pre>{logs_block}</pre>
</body>
</html>"""
```

The page should:

- reuse the existing shared nav pattern
- show host/software/hardware rows from the system snapshot
- render four buttons: `Restart`, `Reinstall`, `Upgrade`, `Logs`
- use `fetch("/api/system/restart")`, `fetch("/api/system/reinstall")`, `fetch("/api/system/upgrade")`, and `fetch("/api/logs?lines=200")`
- show any action error inline without removing the snapshot from the page
- not include the hostname editor from the current settings page

Add a dedicated route in `plamp_web/server.py`:

```python
@app.get("/system", response_class=HTMLResponse)
def get_system_page() -> str:
    return render_system_info_page(system_response(), read_log_tail(200))
```

Update the shared nav constant so every page has a `System` link.

- [ ] **Step 4: Rerun the page tests**

Run:

```bash
uv run python -m unittest tests.test_pages -v
```

Expected: pass.

- [ ] **Step 5: Commit the page work**

```bash
git add plamp_web/pages.py tests/test_pages.py plamp_web/README.md
git commit -m "Add system info page"
```

## Task 4: Final Verification And Docs

**Files:**
- Modify: `plamp_cli/README.md`
- Modify: `plamp_web/README.md`

- [ ] **Step 1: Update the command and page docs**

Make sure the docs describe:

- `plamp system info` as the snapshot command
- `plamp status` as the streaming command
- `/system` as the system info page
- `Restart`, `Reinstall`, `Upgrade`, and `Logs` as the only controls on that page

- [ ] **Step 2: Run the focused test set**

Run:

```bash
uv run python -m unittest tests.test_plamp_cli_http tests.test_plamp_cli tests.test_config_api tests.test_pages -v
```

Expected: pass.

- [ ] **Step 3: Commit the docs**

```bash
git add plamp_cli/README.md plamp_web/README.md
git commit -m "Document system info page and status stream"
```
