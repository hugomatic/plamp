# Plamp CLI

`plamp` is a JSON-first command-line client for `plamp-web`.

## Quick Start

```bash
plamp --help
plamp config get
plamp timers list
plamp pics list --source grow --limit 10
```

## Smoke Test

```bash
plamp config get
plamp timers list
plamp timers get pump_lights
plamp pics list --limit 3
plamp pics take
plamp pics get grow:latest --out /tmp/latest.jpg
```

## Help

Start with:

```bash
plamp --help
plamp config --help
plamp timers --help
plamp pics --help
```

That shows the available command groups, flags, and subcommands.

## Defaults

- base URL: `http://127.0.0.1:8000`
- stdout: JSON
- stderr: diagnostics only
- JSON input: `@file.json` or `-` for stdin

## Command Reference

### Config

Commands:

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

Useful examples:

```bash
plamp config get
plamp config controllers get
plamp --pretty config devices get
plamp --table config devices get
plamp config set @config.json
plamp config cameras set @cameras.json
```

### Timers

Commands:

```bash
plamp timers list
plamp timers get pump_lights
plamp timers set pump_lights @state.json
plamp timers channels set-schedule pump_lights lights @schedule.json
```

Useful examples:

```bash
plamp timers list
plamp timers get pump_lights
plamp --table timers get pump_lights
plamp timers set pump_lights @state.json
cat schedule.json | plamp timers channels set-schedule pump_lights lights -
```

### Pictures

Commands:

```bash
plamp pics list
plamp pics take
plamp pics take --camera-id rpicam_cam0
plamp pics get grow:latest --out latest.jpg
plamp pics get grow:latest --stdout > latest.jpg
```

Useful examples:

```bash
plamp pics list --source grow --limit 10
plamp pics list --source camera_roll --offset 10 --limit 10
plamp pics take --camera-id rpicam_cam0
plamp pics get grow:latest --out latest.jpg
ssh pi.local plamp pics get grow:latest --stdout > latest.jpg
```

## Output Modes

- default: compact JSON
- `--pretty`: indented JSON
- `--table`: table output when the response shape is tabular; otherwise JSON

## Agent Contract

- Default stdout is machine-readable JSON unless `--table` is requested.
- Diagnostics go to stderr.
- `pics get` writes binary only when `--stdout` or `--out` is used.
- `pics get --stdout` writes image bytes only, with no JSON wrapper.
- `pics get --out <path>` writes the file and produces no stdout payload.
- Nested response shapes fall back to JSON even when `--table` is requested.
- Exit codes:
  - `0` success
  - `2` usage error
  - `3` API error
  - `4` network error
  - `5` local input error

## Remote Use

```bash
plamp --host pi.local timers get pump_lights
plamp --host 192.168.68.56 pics list
ssh pi.local plamp config get
ssh pi.local plamp pics get grow:latest --stdout > latest.jpg
```

## JSON Input

```bash
plamp config set @config.json
cat state.json | plamp timers set pump_lights -
```

## Testing Checklist

For a quick manual check on a Pi:

```bash
plamp config get
plamp timers list
plamp timers get pump_lights
plamp pics list --limit 3
plamp pics take
plamp pics get grow:latest --out /tmp/latest.jpg
```

## Pictures

Picture download is explicit:

- `--out <path>` writes a file
- `--stdout` writes raw image bytes to stdout
