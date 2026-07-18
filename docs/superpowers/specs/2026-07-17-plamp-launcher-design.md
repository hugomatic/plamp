# Plamp Launcher Design

## Problem

`setup.sh` prepends `.venv/bin`, but a checkout that has not been synchronized
after the CLI packaging change has no `plamp` executable. The user sees a valid
Plamp context followed by `plamp: command not found`. Installing a Python
distribution solely to create that command also introduces meaningless package
version metadata alongside Plamp's real Git identity.

## Design

- Add one executable repository launcher at `bin/plamp`.
- The launcher resolves its checkout and executes that checkout's
  `plamp_cli/main.py` with `python3`. The REST CLI uses only the Python standard
  library, so it needs neither activation nor uv synchronization.
- `setup.sh` prepends `$PLAMP_ROOT/bin`, then `.venv/bin`, then `$PLAMP_ROOT`.
  Switching checkouts removes all three paths belonging to the prior checkout.
- Mark the uv project as non-package and remove the build backend, setuptools-scm,
  console-script entry point, and setuptools package discovery. uv continues to
  install the service and direct-library dependencies declared by the project.
- Plamp software identity remains the Git hash reported by the application and
  control tools. No Python package version replaces or supplements it.

## Verification

From a clean Bash environment with no virtual environment activation, source a
temporary checkout's `setup.sh`, assert `command -v plamp` resolves to its
`bin/plamp`, and run `plamp --help`. Source a second checkout and verify every
path and launcher switches cleanly. Verify `uv sync` creates dependencies but
does not install a `plamp` distribution, then run the full test suite.
