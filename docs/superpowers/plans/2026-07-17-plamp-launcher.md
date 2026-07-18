# Repository-Owned Plamp Launcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `source setup.sh` provide a working `plamp` REST CLI from any checkout without activation, uv synchronization, or Python distribution installation.

**Architecture:** Add one executable Bash launcher under `bin/` that resolves and runs its checkout's standard-library REST client. Make `setup.sh` select that launcher before checkout-local environment paths, and convert the uv project to non-package dependency management so no console script or package version is built.

**Tech Stack:** Bash, Python standard library, uv dependency management, Python `unittest`.

## Global Constraints

- `plamp` resolves to `$PLAMP_ROOT/bin/plamp` after `source setup.sh` even when `.venv` does not exist.
- The launcher executes the selected checkout's `plamp_cli/main.py` with `python3` and works from any current directory.
- Switching checkouts removes the prior checkout's `bin`, `.venv/bin`, and root paths.
- uv continues to synchronize FastAPI, pyserial, pyudev, and uvicorn dependencies but does not build or install a Plamp distribution.
- Git hashes remain the only Plamp software identity; setuptools, setuptools-scm, package entry points, and installed package versions are removed.
- Service, REST API, controller, CAD, and installer package behavior are unchanged.

---

### Task 1: Provide the checkout-owned launcher

**Files:**
- Create: `bin/plamp`
- Modify: `setup.sh`
- Modify: `tests/test_setup_sh.py`

**Interfaces:**
- Consumes: `plamp_cli/main.py`, which already supports direct-file execution.
- Produces: executable `$PLAMP_ROOT/bin/plamp` and setup PATH order `bin:.venv/bin:root`.

- [ ] **Step 1: Add failing clean-shell launcher tests**

Update `make_checkout()` to copy `setup.sh`, `bin/plamp`, and `plamp_cli`. Add a test that sources the temporary checkout with `PATH=/usr/bin:/bin`, verifies `command -v plamp` equals `<checkout>/bin/plamp`, and runs `plamp --help`. Change the checkout-switch assertion to expect:

```python
f"{second}/bin:{second}/.venv/bin:{second}:/usr/bin:/bin"
```

Run:

```bash
python3 -m unittest tests.test_setup_sh -v
```

Expected: failure because `bin/plamp` and the bin PATH entry do not exist.

- [ ] **Step 2: Add the minimal launcher and setup path handling**

Create executable `bin/plamp`:

```bash
#!/usr/bin/env bash
set -euo pipefail

launcher_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
plamp_root="$(cd -- "${launcher_dir}/.." && pwd -P)"
exec python3 "${plamp_root}/plamp_cli/main.py" "$@"
```

Update `setup.sh` to remove the old/current `$PLAMP_ROOT/bin` entries and export:

```bash
export PATH="$PLAMP_ROOT/bin:$PLAMP_ROOT/.venv/bin:$PLAMP_ROOT:$PATH"
```

- [ ] **Step 3: Run setup and CLI tests**

Run:

```bash
python3 -m unittest tests.test_setup_sh tests.test_plamp_cli -v
bash -n setup.sh bin/plamp
```

Expected: all tests pass and both Bash files parse.

### Task 2: Stop building a Plamp Python distribution

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `tests/test_package_metadata.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: uv's `package = false` project setting and existing project dependencies.
- Produces: a virtual dependency project with no build backend or console entry point.

- [ ] **Step 1: Replace the package test with a failing non-package contract**

Assert that `pyproject.toml` has no `build-system`, no `project.scripts`, no `tool.setuptools`, includes `tool.uv.package = false`, and retains the four runtime dependency declarations. Assert README operation examples use `source ./setup.sh` followed by `plamp --help` without a user-facing `uv sync` step.

Run:

```bash
python3 -m unittest tests.test_package_metadata -v
```

Expected: failure because the build backend, console entry point, and setuptools configuration remain.

- [ ] **Step 2: Convert pyproject to a non-package uv project**

Remove `[build-system]`, `[project.scripts]`, and `[tool.setuptools.packages.find]`. Retain `dynamic = ["version"]` only as the PEP 621 declaration required to keep the dependency project valid without inventing a release number. Add:

```toml
[tool.uv]
package = false
```

Update README operation examples to show `source ./setup.sh`, `plamp --help`, and normal `plamp` REST commands without mentioning uv synchronization.

- [ ] **Step 3: Regenerate and verify the virtual lock project**

Run:

```bash
UV_CACHE_DIR=/tmp/uv-cache /home/hugo/.local/bin/uv lock
UV_CACHE_DIR=/tmp/uv-cache /home/hugo/.local/bin/uv sync --project .
```

Expected: uv succeeds, `uv.lock` records Plamp as a virtual source rather than editable, `.venv/bin/plamp` is absent, and `bin/plamp --help` succeeds.

- [ ] **Step 4: Run full verification and commit**

Run:

```bash
python3 -m unittest discover -s tests -v
bash -n setup.sh bin/plamp
git diff --check
git status --short
```

Expected: all tests pass; only the launcher, setup, dependency metadata, README, tests, and this plan differ; no generated environment files are tracked.

Commit:

```bash
git add bin/plamp setup.sh pyproject.toml uv.lock README.md tests/test_setup_sh.py tests/test_package_metadata.py docs/superpowers/plans/2026-07-17-plamp-launcher.md
git commit -m "Provide checkout-owned Plamp launcher"
```
