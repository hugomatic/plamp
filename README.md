# plamp

Raspberry Pi web UI and Pico firmware for a small hydroponic controller.

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

Start the web server:

```bash
uv run uvicorn plamp_web.server:app --host 0.0.0.0 --port 8000
```

Open:

```text
http://<raspberry-pi-ip>:8000/
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

Reference photo:

![Pi with 3D-printed tripod and camera holder](./things/plamp_stand/doc/stand.jpg)
