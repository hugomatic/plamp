# Direct Plamp Launcher Correction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the command named `plamp` execute the `plamp` module's direct CLI through its checkout's hidden virtual environment, without calling REST or exposing uv to the operator.

**Architecture:** `setup.sh` continues to select a checkout by putting `bin/` first on `PATH`. `bin/plamp` resolves that checkout, requires its `.venv/bin/python`, adds the checkout to the child process import path, and executes `python -m plamp`; `plamp_cli` remains an explicitly named REST compatibility client.

**Tech Stack:** Bash, Python 3.11, `argparse`, uv-managed virtual environment, standard-library `unittest`.

## Global Constraints

- `plamp` is the direct module CLI and works while `plamp-web` is stopped.
- `bin/plamp` must not execute `plamp_cli`, system Python, or uv.
- Operators do not activate or name the virtual environment.
- A missing checkout environment exits nonzero with one concise `./plampctl reinstall` recovery command.
- The launcher works from any current directory and preserves user arguments exactly.
- Git hashes remain the only Plamp software identity.
- The REST compatibility client remains available only as `python -m plamp_cli`.
- REST/SSE server and web behavior are unchanged in this plan.

---

### Task 1: Specify the direct launcher contract

**Files:**
- Modify: `tests/test_setup_sh.py`
- Modify: `tests/test_plamp_direct_cli.py`

**Interfaces:**
- Consumes: `setup.sh`, `bin/plamp`, and `plamp.cli.build_parser()`.
- Produces: regression tests for `-m plamp`, hidden interpreter selection, argument preservation, checkout import path, missing-environment diagnostics, and `prog="plamp"` help.

- [ ] **Step 1: Replace the REST-launcher fixture with a recording virtual-environment interpreter**

Change `make_checkout()` so it copies `setup.sh` and `bin/plamp`, creates `.venv/bin/python`, and writes an executable recording script:

```python
venv_bin = root / ".venv" / "bin"
venv_bin.mkdir(parents=True)
python = venv_bin / "python"
python.write_text(
    "#!/usr/bin/env bash\n"
    "printf 'python=%s\\n' \"$0\"\n"
    "printf 'pythonpath=%s\\n' \"${PYTHONPATH:-}\"\n"
    "printf 'arg=%s\\n' \"$@\"\n",
    encoding="utf-8",
)
python.chmod(0o755)
```

Remove the temporary checkout's `plamp_cli` copy because the recording interpreter must prove launcher wiring without executing either CLI implementation.

- [ ] **Step 2: Add launcher and missing-environment assertions**

Replace `test_setup_exposes_checkout_launcher_without_virtual_environment` with a test that sources the checkout, invokes `plamp pico report pump_lights`, and asserts:

```text
<checkout>/bin/plamp
python=<checkout>/.venv/bin/python
pythonpath=<checkout>
arg=-m
arg=plamp
arg=pico
arg=report
arg=pump_lights
```

Add a subprocess test that removes the fake interpreter, invokes `bin/plamp --help`, asserts a nonzero exit, and asserts stderr contains both `Plamp environment is missing` and `./plampctl reinstall` but contains neither `uv` nor a traceback.

- [ ] **Step 3: Assert direct CLI help owns the command name**

Add to `tests/test_plamp_direct_cli.py`:

```python
def test_help_uses_plamp_command_name(self):
    stdout = io.StringIO()
    with self.assertRaises(SystemExit) as caught:
        with contextlib.redirect_stdout(stdout):
            main(["--help"])
    self.assertEqual(caught.exception.code, 0)
    self.assertIn("usage: plamp", stdout.getvalue())
    self.assertNotIn("python -m plamp", stdout.getvalue())
```

- [ ] **Step 4: Run the tests and verify RED**

Run:

```bash
/home/hugo/.openclaw/workspace/code/plamp/.worktrees/run-main/.venv/bin/python -m unittest tests.test_setup_sh tests.test_plamp_direct_cli -v
```

Expected: launcher assertions fail because `bin/plamp` executes system `python3 plamp_cli/main.py`, the missing environment is ignored, and direct help says `python -m plamp`.

---

### Task 2: Launch the direct module through the hidden environment

**Files:**
- Modify: `bin/plamp`
- Modify: `plamp/cli.py`
- Test: `tests/test_setup_sh.py`
- Test: `tests/test_plamp_direct_cli.py`

**Interfaces:**
- Consumes: checkout `.venv/bin/python` created by `plampctl` installation or upgrade and `plamp.__main__`.
- Produces: `bin/plamp [ARGS...] -> .venv/bin/python -m plamp [ARGS...]` with `PYTHONPATH` rooted at the selected checkout.

- [ ] **Step 1: Implement the launcher**

Replace the launcher body after root resolution with:

```bash
python_bin="${plamp_root}/.venv/bin/python"
if [[ ! -x "${python_bin}" ]]; then
  printf 'Plamp environment is missing: %s\n' "${python_bin}" >&2
  printf 'Run: %s/plampctl reinstall\n' "${plamp_root}" >&2
  exit 1
fi

if [[ -n "${PYTHONPATH:-}" ]]; then
  export PYTHONPATH="${plamp_root}:${PYTHONPATH}"
else
  export PYTHONPATH="${plamp_root}"
fi

exec "${python_bin}" -m plamp "$@"
```

- [ ] **Step 2: Give the direct parser the public command name**

Change:

```python
argparse.ArgumentParser(prog="python -m plamp")
```

to:

```python
argparse.ArgumentParser(prog="plamp")
```

- [ ] **Step 3: Run the focused tests and verify GREEN**

Run:

```bash
/home/hugo/.openclaw/workspace/code/plamp/.worktrees/run-main/.venv/bin/python -m unittest tests.test_setup_sh tests.test_plamp_direct_cli -v
bash -n setup.sh bin/plamp
```

Expected: all focused tests pass and both Bash files parse successfully.

- [ ] **Step 4: Commit the executable correction**

```bash
git add bin/plamp plamp/cli.py tests/test_setup_sh.py tests/test_plamp_direct_cli.py
git commit -m "Launch the direct Plamp module"
```

---

### Task 3: Correct operator and compatibility documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/spec-current.md`
- Modify: `plamp_cli/README.md`
- Modify: `tests/test_plamp_cli.py`
- Modify: `tests/test_package_metadata.py`

**Interfaces:**
- Consumes: public `plamp` direct commands and explicit `python -m plamp_cli` compatibility invocation.
- Produces: documentation that never describes `plamp` as REST-backed and never exposes uv for ordinary direct CLI operation.

- [ ] **Step 1: Add failing documentation assertions**

Update tests to require the root README operation section to contain:

```text
source ./setup.sh
plamp context
plamp config get
plamp pico report pump_lights
```

and reject `JSON-first REST CLI`, `uv run python -m plamp`, and REST-only commands under the `plamp` name. Update the compatibility README assertion to require `python -m plamp_cli` in its SSH example and reject `/home/hugo/.local/bin/plamp`.

- [ ] **Step 2: Run documentation tests and verify RED**

Run:

```bash
/home/hugo/.openclaw/workspace/code/plamp/.worktrees/run-main/.venv/bin/python -m unittest tests.test_package_metadata tests.test_plamp_cli.PlampCliDocsTests -v
```

Expected: failures identify the old REST-backed `plamp` examples and installed-command SSH example.

- [ ] **Step 3: Correct the documentation**

Make the root README's primary operation block use only direct commands through `plamp`. Describe `python -m plamp_cli` as migration-only REST compatibility tooling in a separate paragraph. Update `docs/spec-current.md` and `plamp_cli/README.md` to preserve the same naming boundary.

- [ ] **Step 4: Run documentation tests and verify GREEN**

Run:

```bash
/home/hugo/.openclaw/workspace/code/plamp/.worktrees/run-main/.venv/bin/python -m unittest tests.test_package_metadata tests.test_plamp_cli.PlampCliDocsTests -v
```

Expected: all documentation contract tests pass.

- [ ] **Step 5: Run full verification**

Run:

```bash
/home/hugo/.openclaw/workspace/code/plamp/.worktrees/run-main/.venv/bin/python -m unittest discover -s tests -v
bash -n setup.sh bin/plamp plampctl
git diff --check
git status --short
```

Expected: 462 or more tests pass, Bash syntax and whitespace checks succeed, and only planned files differ.

- [ ] **Step 6: Commit documentation and tests**

```bash
git add README.md docs/spec-current.md plamp_cli/README.md tests/test_plamp_cli.py tests/test_package_metadata.py
git commit -m "Document Plamp as the direct CLI"
```
