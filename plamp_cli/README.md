# Plamp CLI

`plamp` is a JSON-first command-line client for `plamp-web`.

## Install

Use the repo root, not `plamp_cli/`:

```bash
cd /home/hugo/.openclaw/workspace/code/plamp
```

Recommended for testing and agent use:

```bash
uv run python -m plamp_cli --help
```

Optional shell install if you want a normal `plamp` command in `PATH`:

```bash
python3 -m pip install --user --no-deps --editable /home/hugo/.openclaw/workspace/code/plamp
```

After a `--user` install:

```bash
~/.local/bin/plamp --help
```

## Run

Recommended:

```bash
uv run python -m plamp_cli --help
```

Also supported:

```bash
~/.local/bin/plamp --help
```

Default API target:

```text
http://127.0.0.1:8000
```

## Help

Use:

```bash
uv run python -m plamp_cli --help
uv run python -m plamp_cli config --help
uv run python -m plamp_cli controllers --help
uv run python -m plamp_cli pico-scheduler --help
uv run python -m plamp_cli pics --help
```

## Quick Start

```bash
uv run python -m plamp_cli config get
uv run python -m plamp_cli controllers list
uv run python -m plamp_cli pico-scheduler list
uv run python -m plamp_cli pics list --source grow --limit 10
```

## Smoke Test

1. Read config:

```bash
uv run python -m plamp_cli --pretty config get
```

Expected shape:

```json
{
  "config": {
    "controllers": { "...": {} },
    "devices": { "...": {} },
    "cameras": { "...": {} }
  },
  "detected": {
    "picos": [],
    "cameras": []
  }
}
```

2. List controller families:

```bash
uv run python -m plamp_cli --pretty controllers list
```

Expected shape:

```json
{
  "controllers": {
    "pico_scheduler": {
      "ids": ["pump_lights"]
    }
  }
}
```

3. List Pico scheduler controllers:

```bash
uv run python -m plamp_cli --pretty pico-scheduler list
```

Expected shape:

```json
{
  "ids": ["pump_lights"]
}
```

4. Read one Pico scheduler state:

```bash
uv run python -m plamp_cli --pretty pico-scheduler get pump_lights
```

Expected shape:

```json
{
  "report_every": 10,
  "devices": []
}
```

5. List a few pictures and copy one `image_key`:

```bash
uv run python -m plamp_cli --pretty pics list --limit 3
```

Expected shape:

```json
{
  "captures": [
    {
      "image_key": "...",
      "image_url": "/api/camera/images/..."
    }
  ],
  "limit": 3,
  "offset": 0,
  "has_more": false,
  "total": 0
}
```

6. Trigger one capture:

```bash
uv run python -m plamp_cli --pretty pics take
```

Expected shape:

```json
{
  "capture_id": "...",
  "image_url": "/api/camera/captures/.../image"
}
```

7. Download one real image using the `image_key` from step 5:

```bash
uv run python -m plamp_cli pics get <image_key> --out /tmp/latest.jpg
ls -lh /tmp/latest.jpg
```

Expected result:

```text
/tmp/latest.jpg exists and is non-empty
```

## Defaults

- base URL: `http://127.0.0.1:8000`
- stdout: JSON
- stderr: diagnostics only
- JSON input: `@file.json` or `-` for stdin

## Command Reference

### Config

Commands:

```bash
uv run python -m plamp_cli config get
uv run python -m plamp_cli config set @config.json
uv run python -m plamp_cli config controllers get
uv run python -m plamp_cli config controllers set @controllers.json
uv run python -m plamp_cli config devices get
uv run python -m plamp_cli config devices set @devices.json
uv run python -m plamp_cli config cameras get
uv run python -m plamp_cli config cameras set @cameras.json
```

Examples:

```bash
uv run python -m plamp_cli config get
uv run python -m plamp_cli config controllers get
uv run python -m plamp_cli --pretty config devices get
uv run python -m plamp_cli --table config devices get
uv run python -m plamp_cli config set @config.json
```

### Controllers

Commands:

```bash
uv run python -m plamp_cli controllers list
```

Examples:

```bash
uv run python -m plamp_cli controllers list
uv run python -m plamp_cli --pretty controllers list
```

### Pico Scheduler

Commands:

```bash
uv run python -m plamp_cli pico-scheduler list
uv run python -m plamp_cli pico-scheduler get pump_lights
uv run python -m plamp_cli pico-scheduler set pump_lights @state.json
uv run python -m plamp_cli pico-scheduler channels set-schedule pump_lights lights @schedule.json
```

Examples:

```bash
uv run python -m plamp_cli pico-scheduler list
uv run python -m plamp_cli pico-scheduler get pump_lights
uv run python -m plamp_cli --table pico-scheduler get pump_lights
cat schedule.json | uv run python -m plamp_cli pico-scheduler channels set-schedule pump_lights lights -
```

### Pictures

Commands:

```bash
uv run python -m plamp_cli pics list
uv run python -m plamp_cli pics take
uv run python -m plamp_cli pics take --camera-id rpicam_cam0
uv run python -m plamp_cli pics get <image_key> --out latest.jpg
uv run python -m plamp_cli pics get <image_key> --stdout > latest.jpg
```

Examples:

```bash
uv run python -m plamp_cli pics list --source grow --limit 10
uv run python -m plamp_cli pics list --source camera_roll --offset 10 --limit 10
uv run python -m plamp_cli pics take --camera-id rpicam_cam0
# get a real image_key from `pics list`, then:
uv run python -m plamp_cli pics get <image_key> --out latest.jpg
ssh localhost /home/hugo/.local/bin/plamp pics get <image_key> --stdout > latest.jpg
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
- `pics get` expects a real `image_key` returned by `pics list`.
- Nested response shapes fall back to JSON even when `--table` is requested.
- Exit codes:
  - `0` success
  - `2` usage error
  - `3` API error
  - `4` network error
  - `5` local input error

## Remote Use

```bash
uv run python -m plamp_cli --host 127.0.0.1 pico-scheduler get pump_lights
uv run python -m plamp_cli --host 192.168.68.56 pics list
ssh localhost /home/hugo/.local/bin/plamp config get
ssh localhost /home/hugo/.local/bin/plamp pics get <image_key> --stdout > latest.jpg
```

You can also set a default host:

```bash
export PLAMP_HOST=127.0.0.1
uv run python -m plamp_cli pico-scheduler list
```

## JSON Input

```bash
uv run python -m plamp_cli config set @config.json
cat state.json | uv run python -m plamp_cli pico-scheduler set pump_lights -
```

## Pictures

Picture download is explicit:

- `--out <path>` writes a file
- `--stdout` writes raw image bytes to stdout
