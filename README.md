# plamp

Raspberry Pi web UI and Pico firmware for a small hydroponic controller.

![Pi with 3D-printed tripod and camera holder](./things/plamp_stand/doc/stand.jpg)

## Install

Install `uv` on the Raspberry Pi:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Reload your shell, then check it:

```bash
uv --version
```

Clone this repo and enter it:

```bash
git clone https://github.com/hugomatic/plamp.git
cd plamp
```

Install Python requirements:

```bash
uv run python -c "import fastapi, serial, uvicorn"
```

## Run

Start the development web server:

```bash
uv run uvicorn plamp_web.server:app --host 0.0.0.0 --port 8000
```

Open:

```text
http://<raspberry-pi-ip>:8000/
```

## Run on boot with nginx

Use nginx as the public port-80 proxy and systemd to keep the Plamp app running
on unprivileged port 8000 after boot:

```text
browser -> nginx :80 -> plamp-web.service :8000
```

Install nginx:

```bash
sudo apt update
sudo apt install nginx
```

Install the Plamp nginx site from the repo root:

```bash
sudo cp deploy/nginx/plamp.conf /etc/nginx/sites-available/plamp
sudo ln -sf /etc/nginx/sites-available/plamp /etc/nginx/sites-enabled/plamp
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

Install the Plamp systemd service from the repo root as the user that should run
Plamp:

```bash
deploy/systemd/install-plamp-web-service.sh
```

The service installer detects the current user, repo path, and `uv` path, then
writes a machine-local `/etc/systemd/system/plamp-web.service`. nginx and
systemd will both start after reboot.

Check it:

```bash
sudo systemctl status plamp-web
curl http://127.0.0.1:8000/
curl http://127.0.0.1/
```

Open:

```text
http://<raspberry-pi-ip>/
```

## CLI

Plamp includes a JSON-first CLI:

```bash
plamp config get
plamp controllers list
plamp pico-scheduler list
plamp pics list
```

See [`plamp_cli/README.md`](./plamp_cli/README.md) for remote usage, JSON input
rules, and picture download examples.

For development, stop the boot service before running Uvicorn manually:

```bash
sudo systemctl stop plamp-web
uv run uvicorn plamp_web.server:app --host 127.0.0.1 --port 8000 --reload
```

Then restore the boot-managed server:

```bash
sudo systemctl start plamp-web
```

Useful pages:

- `/` - main Pico scheduler page
- `/settings` - system status and Plamp config
- `/api/test` - API test page

## Configure

Use `/settings` to configure:

- Pico controllers
- devices such as lights, pumps, and fans
- Raspberry Pi cameras
- hostname

Runtime config is stored in:

```text
data/config.json
```

Controller config includes the scheduler firmware type and reporting interval:

```json
{
  "controllers": {
    "pump_lights": {
      "type": "pico_scheduler",
      "pico_serial": "e66038b71387a039",
      "report_every": 10
    }
  }
}
```

`report_every` is configured on the controller in `data/config.json`. Pico
scheduler state files keep device state; any older `report_every` value in
legacy Pico scheduler state is not the source of truth for reporting cadence.

`data/` is local runtime data and is ignored by git.

## Pico Firmware

The Pico firmware is in:

```text
pico_scheduler/
```

Install `mpremote` on the Raspberry Pi:

```bash
python3 -m pip install --user mpremote
```

Copy firmware and state to the Pico:

```bash
cd pico_scheduler
mpremote cp main.py :main.py
mpremote cp state.json :state.json
mpremote reset
```

More detail:

- [`pico_scheduler/README.md`](./pico_scheduler/README.md)
- [`plamp_web/README.md`](./plamp_web/README.md)

## Repo Map

- [`docs/spec-current.md`](./docs/spec-current.md) - current architecture and contracts spec
- [`plamp_web/`](./plamp_web/) - web server and pages
- [`pico_scheduler/`](./pico_scheduler/) - MicroPython Pico firmware
- [`grow/`](./grow/) - grow log tools
- [`things/`](./things/) - printable parts
