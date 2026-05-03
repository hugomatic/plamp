# Plamp CLI Design

## Goal

Add a dedicated CLI for Plamp that can:

- get and set config
- list and get timer state
- update timer state and channel schedules
- list captured pictures
- fetch picture bytes
- trigger a picture capture

The CLI should be:

- agent friendly by default
- short enough for human use
- usable locally or against remote Plamp hosts
- documented clearly enough to be invoked directly as a tool and wrapped later as a Codex skill if needed

## Product Shape

The CLI executable is:

```text
plamp
```

The implementation lives in its own folder so it remains separate from the web UI package:

```text
plamp_cli/
```

Expected contents:

- `plamp_cli/__init__.py`
- `plamp_cli/__main__.py`
- `plamp_cli/main.py`
- `plamp_cli/http.py`
- `plamp_cli/io.py`
- `plamp_cli/README.md`

The CLI uses `argparse`.

## Transport Model

### Primary Mode

The CLI is an HTTP client for the existing `plamp-web` API.

Default target:

```text
http://127.0.0.1:8000
```

Remote use is supported through flags or environment variables:

- `--host`
- `--port`
- `--base-url`
- `PLAMP_HOST`
- `PLAMP_PORT`
- `PLAMP_BASE_URL`

### SSH Use

The CLI does not implement SSH as a second transport backend in v1.

Instead, it must be safe to run remotely over SSH:

```bash
ssh pi.local plamp config get
ssh pi.local plamp pics get <image_key> --stdout > latest.jpg
```

Reason:

- one protocol boundary is simpler than dual HTTP and SSH backends
- serial ownership stays with the long-lived server process
- agents can use direct HTTP or `ssh host plamp ...` without changing CLI semantics

## Output Contract

### Default

Default stdout is machine-readable JSON.

This is the default because the primary use case is agent automation.

### Human Modes

Add explicit output options:

- `--pretty`
- `--table`

Rules:

- these are presentation layers over the same response data
- default remains JSON
- binary commands ignore `--pretty` and `--table`

### Errors

Rules:

- errors print concise diagnostics to stderr
- commands return non-zero exit codes
- stdout should stay clean unless intentionally returning structured error JSON in a future extension

Suggested exit codes:

- `0` success
- `2` usage or argument error
- `3` API error response
- `4` network or connection error
- `5` local input or file error

## Command Surface

### Config

```bash
plamp config get
plamp config set @config.json
plamp config controllers get
plamp config controllers set @controllers.json
plamp config devices get
plamp config devices set @devices.json
plamp config cameras get
plamp config cameras set @cameras.json
```

Mappings:

- `config get` -> `GET /api/config`
- `config set` -> `PUT /api/config`
- section `get` can read `GET /api/config` and return the requested sub-object
- section `set` -> `PUT /api/config/<section>`

### Timers

```bash
plamp timers list
plamp timers get <role>
plamp timers set <role> @state.json
plamp timers channels set-schedule <role> <channel_id> @schedule.json
```

Mappings:

- `timers list` -> `GET /api/timer-config`
- `timers get <role>` -> `GET /api/timers/{role}`
- `timers set <role>` -> `PUT /api/timers/{role}`
- `timers channels set-schedule` -> `POST /api/timers/{role}/channels/{channel_id}/schedule`

### Pictures

Use the short noun `pics` to reduce typing.

```bash
plamp pics list
plamp pics list --source grow
plamp pics list --source camera_roll --limit 10 --offset 20
plamp pics take
plamp pics take --camera-id rpicam_cam0
plamp pics get <image_key> --out latest.jpg
plamp pics get <image_key> --stdout
```

Mappings:

- `pics list` -> `GET /api/camera/captures`
- `pics take` -> `POST /api/camera/captures`
- `pics get <image_key>` -> `GET /api/camera/images/{image_key}`

## Input Model

For JSON payload commands:

- `@file.json` reads JSON from a file
- `-` reads JSON from stdin

V1 does not need inline JSON arguments.

Reason:

- keeps parsing simple
- reduces quoting mistakes for humans and agents
- works well with generated files and shell pipelines

## Binary Output Rules

Picture bytes are only written when explicitly requested:

- `--out <path>`
- `--stdout`

Rules:

- default `pics get` should not dump binary bytes accidentally
- when `--stdout` is used, stdout must contain image bytes only
- any status or diagnostic output must go to stderr
- the fetched bytes should be streamed as served by the API, currently JPEG

This makes the command safe for:

```bash
ssh pi.local plamp pics get <image_key> --stdout > latest.jpg
```

## Agent-Facing Documentation

The CLI should ship with a dedicated markdown document:

```text
plamp_cli/README.md
```

This document is part of the product, not an afterthought.

It should include:

- command overview
- transport defaults
- output contract
- JSON input rules
- binary output rules
- remote usage guidance
- examples that agents can copy directly
- error behavior and exit codes

The examples should be terse and realistic.

## Tool vs Skill

The CLI itself is the tool.

In v1, the required agent integration is:

- stable JSON-first behavior
- concise command names
- a strong markdown contract with examples

A separate Codex skill is optional, not required for the CLI to be useful.

If added later, the skill should:

- explain when to use `plamp`
- point to `plamp_cli/README.md`
- keep model-specific prompting thin

That keeps the durable contract in the CLI docs instead of burying behavior inside one assistant environment.

## Packaging

Update `pyproject.toml` to expose a console script:

```toml
[project.scripts]
plamp = "plamp_cli.main:main"
```

V1 should avoid new dependencies unless clearly justified.

Preferred approach:

- use `argparse`
- use the Python standard library for JSON, HTTP, and file handling if practical

If the standard library creates excessive code or poor error handling, a small HTTP dependency can be considered, but that is not the default recommendation.

## Architecture

The CLI should stay as a client of the running web service.

Do not make the website shell out to the CLI.

Reason:

- the web server owns long-lived monitor state
- the web server already owns serial interactions and timer application
- subprocess boundaries would create a second internal protocol and more failure modes

Shared business logic can still be refactored under the hood, but the CLI should consume the supported HTTP surface.

## Non-Goals

This slice does not:

- add direct serial access to the CLI
- add an SSH transport backend
- bypass the web server to edit runtime files directly
- add service management, log inspection, or doctor commands
- push firmware

## Risks and Edge Cases

### API Availability

If the web service is down, the CLI will fail rather than silently switching to file edits.

That is intentional for v1.

### Section Reads

`config controllers get`, `config devices get`, and `config cameras get` are convenience views over `GET /api/config`.

They should return only the requested section on stdout even though the server returns the larger payload.

### Timer State vs Timer Config

The CLI should keep these concepts distinct:

- `timers list` is discovery and summary
- `timers get` is per-role timer state
- config editing remains under `config`

### Picture Identity

`pics get` should take the `image_key` returned by picture listing APIs, not raw repo paths.

This keeps local and remote usage consistent.

## Testing

Implementation should add tests for:

- argument parsing
- target URL resolution from flags and environment
- JSON file and stdin payload loading
- request mapping for config, timer, and picture commands
- error exit codes
- `pics get --stdout` keeping stdout binary-clean
- `pics get --out` writing fetched bytes correctly
- `--pretty` and `--table` preserving the underlying data

Use focused unit tests around HTTP request building and I/O behavior.

## Recommendation

Build the CLI as a small HTTP-first package in `plamp_cli/`, ship it with `argparse`, and treat `plamp_cli/README.md` as the agent-facing contract. Do not build a second SSH backend or make the web app depend on the CLI.
