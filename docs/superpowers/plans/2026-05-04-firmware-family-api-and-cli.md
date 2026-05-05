# Firmware Family API and CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace timer-named controller APIs with controller-oriented APIs, add multi-firmware family abstraction, and add direct local firmware generate/flash/pull/show CLI workflows with JSON input.

**Architecture:** Introduce a firmware-family layer that can generate and flash firmware per family (`pico_scheduler`, `pico_doser`). Migrate server-backed controller reads/writes to `/api/controllers` while preserving legacy timer routes as compatibility aliases. Extend `plamp` with a direct local `firmware` command family and strict stdout/stderr behavior for firmware source extraction.

**Tech Stack:** Python 3, FastAPI, `unittest`, `mpremote`, argparse-based CLI

---

## File map

- `plamp_web/server.py`
  - new controller routes
  - compatibility alias routes
  - controller id validation/reserved words
- `plamp_web/hardware_config.py` (or adjacent config helpers)
  - reserved-word and global-uniqueness checks
  - controller payload normalization
- `plamp_web/pages.py`
  - migrate API references/curl examples from `/api/timers` to `/api/controllers`
- `plamp_cli/main.py`
  - server-backed `controllers` calls switch to `/api/controllers`
  - new direct `firmware` commands
- `plamp_cli/README.md`
  - direct firmware examples (`generate`, `flash`, `pull`, `show`)
- `pico_scheduler/generator.py`
  - adapt to firmware-family interface
- `pico_doser/generator.py` (new)
  - hello-world generator from JSON
- `plamp_firmware/` (new module namespace if needed)
  - family registry
  - flash/pull helpers
- tests:
  - `tests/test_config_api.py`
  - `tests/test_pages.py`
  - `tests/test_plamp_cli.py`
  - `tests/test_pico_scheduler_generator.py`
  - `tests/test_pico_doser_generator.py` (new)

### Task 1: Add controller-oriented API tests

**Files:**
- Modify: `tests/test_config_api.py`

- [ ] **Step 1: Add failing tests for new routes**
```python
def test_get_controllers_returns_flat_ids_with_firmware(self):
    payload = server.get_controllers()
    self.assertIn("controllers", payload)

def test_get_controller_returns_full_controller_payload(self):
    payload = server.get_controller("pump_n_lights")
    self.assertEqual(payload["controller"], "pump_n_lights")
    self.assertIn("firmware", payload)

def test_put_controller_replaces_full_payload(self):
    payload = {"controller": "pump_n_lights", "firmware": "pico_scheduler", "report_every": 10, "devices": []}
    out = server.put_controller("pump_n_lights", payload)
    self.assertEqual(out["controller"], "pump_n_lights")
```

- [ ] **Step 2: Run targeted tests and confirm fail**
Run: `/home/hugo/.local/bin/uv run python -m unittest tests.test_config_api -v`
Expected: route/function missing failures.

- [ ] **Step 3: Commit test-first checkpoint**
```bash
git add tests/test_config_api.py
git commit -m "Add controller API route tests"
```

### Task 2: Implement `/api/controllers` routes with compatibility aliases

**Files:**
- Modify: `plamp_web/server.py`
- Modify: config helper module used by server for controller validation

- [ ] **Step 1: Implement primary controller routes**
- `GET /api/controllers`
- `GET /api/controllers/{controller}`
- `PUT /api/controllers/{controller}`

- [ ] **Step 2: Keep legacy aliases active**
- `/api/timer-config` delegates to controller discovery shape adapter.
- `/api/timers/{role}` delegates to controller get/put for `pico_scheduler`.
- `/api/timers/{role}/channels/...` remains compatibility-only and implemented via full controller update internally.

- [ ] **Step 3: Enforce controller id constraints**
- global uniqueness across families
- reserved-word rejection (`pico_scheduler`, `pico_doser`, `controllers`, `config`, `pics`)

- [ ] **Step 4: Run targeted tests**
Run: `/home/hugo/.local/bin/uv run python -m unittest tests.test_config_api -v`
Expected: pass.

- [ ] **Step 5: Commit**
```bash
git add plamp_web/server.py plamp_web/hardware_config.py tests/test_config_api.py
git commit -m "Add controller API and timer route compatibility"
```

### Task 3: Add firmware-family abstraction and pico_doser placeholder generator

**Files:**
- Create: `pico_doser/generator.py`
- Create: `tests/test_pico_doser_generator.py`
- Modify: `pico_scheduler/generator.py`
- Create/Modify: family registry module (`plamp_firmware/registry.py` or equivalent)

- [ ] **Step 1: Add failing tests for family registry and pico_doser generation**
```python
def test_registry_lists_scheduler_and_doser(self): ...
def test_pico_doser_generator_emits_hello_world_from_json(self): ...
```

- [ ] **Step 2: Implement family registry**
- register `pico_scheduler`
- register `pico_doser`
- expose lookup/list interface for CLI and server use

- [ ] **Step 3: Implement `pico_doser` hello-world generator**
- input JSON required
- emits deterministic MicroPython with minimal `type: report`/`type: error` output
- includes provenance block with input JSON

- [ ] **Step 4: Run tests**
Run: `/home/hugo/.local/bin/uv run python -m unittest tests.test_pico_scheduler_generator tests.test_pico_doser_generator -v`

- [ ] **Step 5: Commit**
```bash
git add pico_scheduler/generator.py pico_doser/generator.py plamp_firmware tests/test_pico_scheduler_generator.py tests/test_pico_doser_generator.py
git commit -m "Add firmware family registry and pico doser placeholder generator"
```

### Task 4: Add direct local `plamp firmware` commands

**Files:**
- Modify: `plamp_cli/main.py`
- Modify: `tests/test_plamp_cli.py`

- [ ] **Step 1: Add failing CLI tests for new commands**
- `plamp firmware families`
- `plamp firmware generate ... @file.json --out ...`
- `plamp firmware flash ... @file.json --port ...`
- `plamp firmware pull --port ...` (stdout)
- `plamp firmware pull --port ... --out ...`
- `plamp firmware show --port ...`

- [ ] **Step 2: Implement parser and handlers**
- add `firmware` command family
- JSON input required for generate/flash
- local-only path (no HTTP dependency for these commands)

- [ ] **Step 3: Implement stdout/stderr contract**
- `pull` firmware source to stdout by default
- `--out` writes file
- `show` writes display output to stdout
- diagnostics/errors only to stderr

- [ ] **Step 4: Run CLI tests**
Run: `/home/hugo/.local/bin/uv run python -m unittest tests.test_plamp_cli -v`

- [ ] **Step 5: Commit**
```bash
git add plamp_cli/main.py tests/test_plamp_cli.py
git commit -m "Add direct firmware generate flash pull show commands"
```

### Task 5: Migrate server-backed CLI and web/API docs to controllers paths

**Files:**
- Modify: `plamp_cli/main.py`
- Modify: `plamp_cli/README.md`
- Modify: `plamp_web/pages.py`
- Modify: `tests/test_pages.py`
- Modify: `tests/test_plamp_cli.py`

- [ ] **Step 1: Switch CLI controllers list/get/set to `/api/controllers`**
- remove reliance on `/api/timer-config` and `/api/timers` in normal path

- [ ] **Step 2: Update API test page and curl snippets**
- prefer `/api/controllers` endpoints
- keep old timer examples only in explicit legacy section if needed

- [ ] **Step 3: Update docs examples**
- add firmware pull redirection examples
- add pico_doser placeholder usage examples

- [ ] **Step 4: Run page/CLI tests**
Run:
- `/home/hugo/.local/bin/uv run python -m unittest tests.test_pages -v`
- `/home/hugo/.local/bin/uv run python -m unittest tests.test_plamp_cli -v`

- [ ] **Step 5: Commit**
```bash
git add plamp_cli/main.py plamp_cli/README.md plamp_web/pages.py tests/test_pages.py tests/test_plamp_cli.py
git commit -m "Move CLI and UI examples to controllers API paths"
```

### Task 6: Full verification and live smoke

**Files:**
- Modify any touched files if fixes required

- [ ] **Step 1: Full automated tests**
Run: `/home/hugo/.local/bin/uv run python -m unittest discover -s tests`
Expected: `OK`.

- [ ] **Step 2: Live server smoke on branch**
- restart `plamp-web` from branch checkout
- verify `/runtime` loads
- verify controller routes respond

- [ ] **Step 3: Firmware direct-mode smoke**
- `plamp firmware families`
- `plamp firmware generate` for `pico_scheduler` and `pico_doser`
- `plamp firmware pull --port ... > /tmp/main.py` (or mocked test environment if hardware unavailable)

- [ ] **Step 4: Commit final fixes**
```bash
git add .
git commit -m "Finalize firmware family API and CLI migration"
```

## Self-review checklist

- Spec coverage:
  - controller API flattening covered (Tasks 1-2)
  - reserved ids covered (Task 2)
  - firmware-family abstraction covered (Task 3)
  - direct local CLI commands covered (Task 4)
  - pull/show stdout contract covered (Task 4)
  - docs and UI migration covered (Task 5)
  - full verification and live smoke covered (Task 6)
- Placeholder scan:
  - no `TODO`/`TBD` steps
- Type consistency:
  - `controller`, `firmware`, `devices` vocabulary consistent
