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

## Port 80 with nginx

Use nginx as the public port-80 proxy while the Plamp app keeps running on
unprivileged port 8000. This keeps local development simple: you can restart
the Uvicorn process in tmux without changing the browser URL.

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

Keep the Plamp app running on port 8000:

```bash
uv run uvicorn plamp_web.server:app --host 127.0.0.1 --port 8000
```

Open:

```text
http://<raspberry-pi-ip>/
```

## Start on boot

nginx starts on boot after installation. To also start the Plamp app on boot,
install the systemd service from the repo root as the user that should run
Plamp:

```bash
deploy/systemd/install-plamp-web-service.sh
```

The installer detects the current user, repo path, and `uv` path, then writes a
machine-local `/etc/systemd/system/plamp-web.service`. It starts Uvicorn on
`127.0.0.1:8000`, so nginx can keep serving the public port-80 URL.

Check it:

```bash
sudo systemctl status plamp-web
curl http://127.0.0.1:8000/
curl http://127.0.0.1/
```

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

- `/` - main timer page
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

- [`plamp_web/`](./plamp_web/) - web server and pages
- [`pico_scheduler/`](./pico_scheduler/) - MicroPython Pico firmware
- [`grow/`](./grow/) - grow log tools
- [`things/`](./things/) - printable parts
