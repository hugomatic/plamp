# Shared Configuration File Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the direct CLI and web service one small, validated JSON configuration boundary selected by an explicit Plamp runtime context.

**Architecture:** `plamp.context` resolves the active checkout and instance paths. `plamp.config` owns validated JSON reads and atomic replacement; the existing hardware schema moves below the web layer so both adapters can use it. Shell activation and systemd expose the same context without owning application behavior.

**Tech Stack:** Python 3.11, argparse, unittest, Bash, FastAPI, systemd

## Global Constraints

- Configuration is always `$PLAMP_DATA_DIR/config.json`.
- `PLAMP_DATA_DIR` defaults to `$PLAMP_ROOT/data`; the running package supplies the default root.
- Do not add `PLAMP_CONFIG`, `--config`, `--data-dir`, a database, config-write locks, or persisted applied state.
- Hardware locks remain independent of the selected instance data directory.
- Do not run OpenSCAD.

---

### Task 1: Runtime context and shell activation

**Files:**
- Create: `plamp/context.py`
- Create: `setup.sh`
- Create: `tests/test_plamp_context.py`
- Create: `tests/test_setup_sh.py`

**Interfaces:**
- Produces: `RuntimeContext(root: Path, data_dir: Path, config_file: Path)` and `resolve_context(env=None, package_root=None)`.
- Produces: sourceable `setup.sh [DATA_DIR]` that exports `PLAMP_ROOT` and `PLAMP_DATA_DIR` and replaces prior Plamp PATH entries.

- [ ] **Step 1: Write failing context tests**

Test package-root defaults, explicit absolute/relative environment values, and `config_file == data_dir / "config.json"`.

- [ ] **Step 2: Run the context tests and verify missing-module failure**

Run: `/home/hugo/.local/bin/uv run python -m unittest tests.test_plamp_context -v`

- [ ] **Step 3: Implement the immutable context**

```python
@dataclass(frozen=True)
class RuntimeContext:
    root: Path
    data_dir: Path

    @property
    def config_file(self) -> Path:
        return self.data_dir / "config.json"


def resolve_context(*, env=None, package_root=None) -> RuntimeContext:
    values = os.environ if env is None else env
    default_root = Path(__file__).resolve().parents[1] if package_root is None else Path(package_root)
    root = Path(values.get("PLAMP_ROOT", default_root)).expanduser().resolve()
    data_dir = Path(values.get("PLAMP_DATA_DIR", root / "data")).expanduser().resolve()
    return RuntimeContext(root=root, data_dir=data_dir)
```

- [ ] **Step 4: Write and verify setup tests**

Run Bash in a clean environment, source checkout A then checkout B, and assert only B's root and `.venv/bin` remain ahead of the original PATH. Assert the default and explicit data directories are absolute.

- [ ] **Step 5: Implement `setup.sh`**

Use `BASH_SOURCE[0]` for the new root; remove exact old-root components from PATH, export the two context variables, prepend the new components once, run `hash -r`, and print both resolved paths. Do not invoke Git, uv, services, or `cd`.

- [ ] **Step 6: Run both test modules and commit**

```bash
/home/hugo/.local/bin/uv run python -m unittest tests.test_plamp_context tests.test_setup_sh -v
git add plamp/context.py setup.sh tests/test_plamp_context.py tests/test_setup_sh.py
git commit -m "Add Plamp runtime activation context"
```

### Task 2: Shared validated configuration and direct CLI

**Files:**
- Move: `plamp_web/hardware_config.py` to `plamp/hardware_config.py`
- Create: `plamp_web/hardware_config.py` compatibility re-export
- Modify: `plamp/config.py`
- Modify: `plamp/cli.py`
- Modify: `tests/test_plamp_direct_cli.py`
- Create: `tests/test_plamp_config.py`

**Interfaces:**
- Consumes: `resolve_context()` and existing `config_view(raw)` schema validation.
- Produces: `load_config(path)`, `save_config(path, raw)`, CLI `context`, `config get`, and `config write FILE`.

- [ ] **Step 1: Write failing config tests**

Cover valid canonical reads, malformed JSON, schema rejection, atomic successful replacement, unchanged destination after rejection, and removal of temporary files.

- [ ] **Step 2: Run tests and verify missing APIs**

Run: `/home/hugo/.local/bin/uv run python -m unittest tests.test_plamp_config -v`

- [ ] **Step 3: Put schema validation below the web adapter**

Move the pure hardware configuration module to `plamp.hardware_config`; leave `plamp_web.hardware_config` as `from plamp.hardware_config import *` so existing imports remain compatible.

- [ ] **Step 4: Implement validated read and atomic save**

`load_config` parses JSON and returns `config_view(raw)`. `save_config` validates before creating a unique temporary sibling, writes indented JSON plus newline, flushes and `fsync`s, calls `os.replace`, and unlinks the temporary file on failure.

- [ ] **Step 5: Write failing CLI tests**

Replace `--config` uses with `PLAMP_ROOT`/`PLAMP_DATA_DIR`. Test stable JSON from `context` and `config get`, stdin/file input for `config write`, unchanged config after invalid input, and existing report/pulse/camera behavior.

- [ ] **Step 6: Implement CLI context and config commands**

Resolve context once in `main`; add `context`, `config get`, and `config write FILE`; route hardware operations through `context.config_file`. Keep diagnostics on stderr and stable JSON on stdout.

- [ ] **Step 7: Run focused tests and commit**

```bash
/home/hugo/.local/bin/uv run python -m unittest tests.test_plamp_config tests.test_plamp_direct_cli -v
git add plamp plamp_web/hardware_config.py tests/test_plamp_config.py tests/test_plamp_direct_cli.py
git commit -m "Share validated Plamp configuration"
```

### Task 3: Web and service context

**Files:**
- Modify: `plamp_web/server.py`
- Modify: `plamp_web/camera_capture.py`
- Modify: `plamp_web/pages.py`
- Modify: `deploy/systemd/install-plamp-web-service.sh`
- Modify: `plampctl`
- Modify: `tests/test_config_api.py`
- Modify: `tests/test_pages.py`
- Modify: `tests/test_systemd_installer.py`
- Modify: `tests/test_plampctl.py`

**Interfaces:**
- Consumes: `resolve_context`, `load_config`, and `save_config`.
- Produces: one effective context in web runtime, visible environment names on the system page, and explicit systemd context.

- [ ] **Step 1: Write failing web/service tests**

Assert web paths follow a supplied context, config writes call shared persistence, the system page labels `PLAMP_ROOT` and `PLAMP_DATA_DIR`, and the generated unit sets both variables explicitly.

- [ ] **Step 2: Run focused tests and verify failures**

```bash
/home/hugo/.local/bin/uv run python -m unittest tests.test_config_api tests.test_pages tests.test_systemd_installer tests.test_plampctl -v
```

- [ ] **Step 3: Wire web paths and persistence**

Resolve context at module startup, derive config/log/timer/camera paths from it, and replace local JSON persistence calls for `config.json` with `plamp.config` calls. Preserve endpoint payloads and reconciliation behavior.

- [ ] **Step 4: Expose context and install it explicitly**

Add `PLAMP_ROOT` and `PLAMP_DATA_DIR` labels to the existing path tables. Have `plampctl`/the installer write absolute environment values into the systemd unit while keeping the checkout as `WorkingDirectory`.

- [ ] **Step 5: Run focused and full verification**

```bash
/home/hugo/.local/bin/uv run python -m unittest tests.test_config_api tests.test_pages tests.test_systemd_installer tests.test_plampctl -v
/home/hugo/.local/bin/uv run python -m unittest discover -s tests -v
git diff --check
```

- [ ] **Step 6: Commit and push**

```bash
git add plamp_web deploy/systemd plampctl tests
git commit -m "Use shared Plamp context in web service"
git push
```
