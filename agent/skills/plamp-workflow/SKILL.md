---
name: plamp-workflow
description: Use when working in the Plamp repository, choosing between plampctl and the plamp CLI, or handling local and Sprout deployment and upgrade workflows.
---

# Plamp Workflow

## Start in the selected checkout

At the repository root, select its code and instance data before using the CLI:

```bash
source ./setup.sh [DATA_DIR]
plamp --help
```

`setup.sh` puts this checkout's `bin/plamp` first on `PATH`. Agents that cannot
alter their shell may invoke `bin/plamp` directly. Do not assume a globally
installed `plamp` belongs to the checkout being inspected.

On a CAD-only workstation, a missing environment needs only the standard
library interpreter environment:

```bash
python3 -m venv "$PLAMP_ROOT/.venv"
```

Run `uv sync --project "$PLAMP_ROOT"` only when full device or web dependencies
are needed. Do not use `plampctl reinstall` to repair a workstation CLI
environment: that is a service host or appliance workflow which installs and
starts `plamp-web`.

## Choose the interface

- Use `plampctl` for host lifecycle and filesystem actions: install/reinstall,
  restart, status, logs, deployment, and upgrades.
- Use the direct `plamp` CLI for repository CAD, config, cameras, Pico reports,
  pulses, firmware/configuration, and other device operations. These commands
  do not require `plamp-web`.
- Use `python3 -m plamp_cli` only for the explicitly named REST compatibility
  client when an HTTP API check is required; it is not the `plamp` command.
- Avoid raw `curl` unless debugging HTTP behavior not exposed by the REST client.

Decision rule: machine or service changes use `plampctl`; Plamp data, devices,
and CAD use `plamp`.

## CAD routing

Use `plamp cad new` for new parts and the remaining `plamp cad` subcommands for
discovery, validation, planning, generation, and archived-run diagnostics. Read
[the OpenSCAD CAD skill](../openscad-cad/SKILL.md) before changing models.

## Verification and deployment

Run the narrowest relevant local tests first. For startup, service wiring,
state paths, or migrations, verify through `plampctl`; migrations belong in
`plampctl upgrade`. For a Sprout change, deploy/restart/upgrade with `plampctl`,
then smoke-test the running service or devices with the appropriate Plamp CLI.
