# Plamp

Local-first hydroponics automation for Raspberry Pi and MicroPython Picos. Picos run lights and pumps independently; the Pi adds configuration, monitoring, pictures, agents, and a fallback web UI.

![Plamp running with basil tray, touchscreen UI, and camera](./docs/images/plamp-live-setup.jpg)

## Install

On a Raspberry Pi:

```bash
curl -fsSL https://raw.githubusercontent.com/hugomatic/plamp/main/deploy/bootstrap/install-plamp.sh | bash
```

This installs Plamp and starts `plamp-web` on `127.0.0.1:8000`. Useful options:

```bash
# Public port 80 through nginx
curl -fsSL https://raw.githubusercontent.com/hugomatic/plamp/main/deploy/bootstrap/install-plamp.sh | bash -s -- --public

# Update OS packages during installation
curl -fsSL https://raw.githubusercontent.com/hugomatic/plamp/main/deploy/bootstrap/install-plamp.sh | bash -s -- --update-os

# Install somewhere else
curl -fsSL https://raw.githubusercontent.com/hugomatic/plamp/main/deploy/bootstrap/install-plamp.sh | bash -s -- --plamp-dir ~/code/plamp
```

The installer labels required runtime dependencies separately from the tools
included for humans and agents. See [Host tools](./docs/host-tools.md).

Host lifecycle commands use `plampctl`:

```bash
systemctl is-active plamp-web
./plampctl restart
./plampctl upgrade
```

## Operate Plamp

Select this checkout, then use the `plamp` module's direct CLI:

```bash
source ./setup.sh
plamp context
plamp config get
plamp pico report pump_lights
plamp pico pulse pump_lights 21 5
plamp pico configure pump_lights compiled-state.json
plamp pico upgrade pump_lights compiled-state.json
plamp camera capture rpicam_cam0
```

Use `-` instead of `compiled-state.json` to read the complete compiled scheduler state from stdin. Configure sends that state through the shared locked Pico protocol. Upgrade renders the current generic scheduler firmware, seeds both state slots, resets once, and verifies the reconnected report. These commands work while the service is running or stopped and do not contact `plamp-web`. Remote agents can use either the REST CLI or direct CLI over SSH.

During migration, the explicitly named REST compatibility client remains available as
`python3 -m plamp_cli`; it is not the command named `plamp`.

`setup.sh [DATA_DIR]` selects the checkout and instance for the current shell. It exports `PLAMP_ROOT` and `PLAMP_DATA_DIR`, and makes the checkout-owned `bin/plamp` launcher available without installing Plamp as a Python package. Without an argument, data defaults to `$PLAMP_ROOT/data`. Source another checkout's setup script to switch versions without leaving its executable paths behind.

See the direct CLI with `plamp --help`, or the
[REST compatibility reference](./plamp_cli/README.md).

## Generate printable CAD

The direct CLI validates and plans repository CAD before running OpenSCAD. For
the Plamp8 fused enclosure workflow:

```bash
plamp cad views plamp8
plamp cad validate plamp8
plamp cad plan plamp8 --preset fuse-box
plamp cad generate plamp8 --preset fuse-box
plamp cad runs plamp8
plamp cad show RUN_ID
```

Use `plan` before `generate`: planning expands the selected recipe and reports
the exact jobs without rendering. Generation can take several minutes per job
on a Raspberry Pi. Generated STL files, archived source, manifests, and
OpenSCAD logs are instance data under `$PLAMP_DATA_DIR/cad/prints`, not source
files to commit. See [Host tools](./docs/host-tools.md#openscad-on-a-pi) for the
metadata format, selector behavior, archive layout, and legacy script options.

## Web and API

Open `http://<raspberry-pi-ip>/` after a public install, or port `8000` otherwise.

- `/`: live controller state, schedule editing, and pictures
- `/settings`: hardware and configuration
- `/api/test`: executable API examples
- `/api/config`: desired configuration
- `/api/system`: host and detected hardware
- `/api/status`: resolved state and telemetry

The browser receives live updates through SSE. See [web service notes](./plamp_web/README.md).

## Configuration

Runtime configuration lives in `$PLAMP_DATA_DIR/config.json`; generated scheduler state lives beside it in `$PLAMP_DATA_DIR/timers/`. Both are local runtime data. The web system page shows the effective root and data paths.

Controllers contain desired device behavior, display settings, and a stable Pico USB serial. `/dev/ttyACM*` paths are rediscovered. See the [current contract](./docs/spec-current.md) for the normalized shape.

## Development

```bash
uv run python -m unittest discover -s tests -v
uv run uvicorn plamp_web.server:app --host 127.0.0.1 --port 8000 --reload
```

Stop the boot service before running a development server, then restore it afterward.

## Repository

- [`docs/spec-current.md`](./docs/spec-current.md): current contract and direction
- [`plamp/`](./plamp/): direct library and CLI
- [`plamp_cli/`](./plamp_cli/): REST-backed CLI
- [`plamp_web/`](./plamp_web/): REST, SSE, scheduled reports/pictures, and fallback UI
- [`pico_scheduler/`](./pico_scheduler/): generated MicroPython scheduler firmware
- [`things/`](./things/): printable parts
