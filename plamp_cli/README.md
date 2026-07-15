# Plamp CLI

Plamp currently has two command-line entry points.

## REST-backed CLI

`python -m plamp_cli` is the mature JSON-first client for `plamp-web`. The installed `plamp` command currently points here.

```bash
cd /path/to/plamp
uv run python -m plamp_cli --help
uv run python -m plamp_cli config get
uv run python -m plamp_cli controllers list
uv run python -m plamp_cli pico-scheduler list
```

Optional editable installation:

```bash
python3 -m pip install --user --no-deps --editable /path/to/plamp
```

The default API is `http://127.0.0.1:8000`. Override it with `--base-url`, `--host`/`--port`, or `PLAMP_HOST`.

### Commands

```bash
# Desired configuration
uv run python -m plamp_cli config get
uv run python -m plamp_cli config set @config.json
uv run python -m plamp_cli config controllers get
uv run python -m plamp_cli config cameras get

# Discovery and current state
uv run python -m plamp_cli controllers list
uv run python -m plamp_cli controllers get pump_lights
uv run python -m plamp_cli system status
uv run python -m plamp_cli status --path controllers.pump_lights

# Scheduler operations
uv run python -m plamp_cli pico-scheduler get pump_lights
uv run python -m plamp_cli pico-scheduler set pump_lights @state.json
uv run python -m plamp_cli pico-scheduler channels set-schedule pump_lights lights @schedule.json

# Pictures
uv run python -m plamp_cli pics list --camera-id rpicam_cam0
uv run python -m plamp_cli --pretty pics take --camera-id rpicam_cam0
uv run python -m plamp_cli pics get <image_key> --out latest.jpg
uv run python -m plamp_cli pics get <image_key> --stdout > latest.jpg
```

`status` streams `/api/status?stream=true`; repeated `--path` arguments select subtrees.

### Input and output

- Default stdout is compact JSON; use `--pretty` or `--table` where supported.
- Diagnostics go to stderr.
- JSON input accepts `@file.json` or `-` for stdin.
- `pics get --stdout` writes only image bytes.
- `pics get --out <path>` writes the file and no stdout payload.

Exit codes:

- `0`: success
- `2`: usage error
- `3`: API error
- `4`: network error
- `5`: local input error

### Remote use

Use HTTP directly:

```bash
uv run python -m plamp_cli --host sprout.local system status
```

Or run the installed CLI through SSH:

```bash
ssh localhost /home/hugo/.local/bin/plamp config get
ssh localhost /home/hugo/.local/bin/plamp pics get <image_key> --stdout > latest.jpg
```

## Direct library CLI

`python -m plamp` calls the shared library without REST. This first slice supports fresh Pico reports:

```bash
sudo systemctl stop plamp-web
uv run python -m plamp pico report pump_lights
sudo systemctl start plamp-web
```

Output is one report JSON object. `--config`, `--lock-dir`, and `--timeout` control local paths and the operation budget.

Until the web monitor migrates to the same filesystem locks, do not run direct serial commands concurrently with `plamp-web`.
