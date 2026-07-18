# Plamp CLI

Plamp currently has a primary direct CLI and an explicitly named REST compatibility
client.

## REST-backed CLI

`python3 -m plamp_cli` is the JSON-first compatibility client for `plamp-web` during
migration. The command named `plamp` does not point here.

```bash
cd /path/to/plamp
python3 -m plamp_cli --help
python3 -m plamp_cli config get
python3 -m plamp_cli controllers list
python3 -m plamp_cli pico-scheduler list
```

The default API is `http://127.0.0.1:8000`. Override it with `--base-url`, `--host`/`--port`, or `PLAMP_HOST`.

### Commands

```bash
# Desired configuration
python3 -m plamp_cli config get
python3 -m plamp_cli config set @config.json
python3 -m plamp_cli config controllers get
python3 -m plamp_cli config cameras get

# Discovery and current state
python3 -m plamp_cli controllers list
python3 -m plamp_cli controllers get pump_lights
python3 -m plamp_cli system status
python3 -m plamp_cli status --path controllers.pump_lights

# Scheduler operations
python3 -m plamp_cli pico-scheduler get pump_lights
python3 -m plamp_cli pico-scheduler set pump_lights @state.json
python3 -m plamp_cli pico-scheduler channels set-schedule pump_lights lights @schedule.json

# Pictures
python3 -m plamp_cli pics list --camera-id rpicam_cam0
python3 -m plamp_cli --pretty pics take --camera-id rpicam_cam0
python3 -m plamp_cli pics get <image_key> --out latest.jpg
python3 -m plamp_cli pics get <image_key> --stdout > latest.jpg
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
python3 -m plamp_cli --host sprout.local system status
```

Or run the compatibility client explicitly through SSH:

```bash
ssh localhost 'cd /path/to/plamp && python3 -m plamp_cli config get'
ssh localhost 'cd /path/to/plamp && python3 -m plamp_cli pics get <image_key> --stdout' > latest.jpg
```

## Direct library CLI

The command named `plamp` calls the shared library without REST and shares the same
per-device filesystem locks as `plamp-web`:

```bash
source ./setup.sh
plamp pico report pump_lights
plamp pico pulse pump_lights 21 5
plamp pico configure pump_lights compiled-state.json
plamp pico upgrade pump_lights compiled-state.json
plamp camera capture rpicam_cam0
```

Commands emit JSON on stdout and diagnostics on stderr. `PLAMP_ROOT` and
`PLAMP_DATA_DIR` select local paths; `--lock-dir` and `--timeout` control hardware
locking and operation budgets. Direct hardware commands may run while the service is
active because access is serialized through shared locks.
