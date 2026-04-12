# pico_api

Minimal FastAPI host app for the Pico scheduler.

This is host-only code. The MicroPython firmware stays in `../pico_scheduler/`, and the API reads host runtime information while leaving the Pico serial port alone.

## Setup

Install `uv` on the Raspberry Pi if it is not already available. The standalone Linux installer from Astral is:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

After installation, restart the shell or reload your shell profile so the new `uv` binary is on `PATH`, then check it:

```bash
command -v uv
uv --version
```

From the repo root, `uv run` will install the Python requirements from `pyproject.toml` into uv's managed environment.

```bash
cd /home/hugo/.openclaw/workspace/code/plamp
uv run python -c "import fastapi, serial, uvicorn"
```

## Timer API

Timer roles are configured in `../data/config.json`. The app creates `../data/`, `../data/timers/`, and an empty config file if they do not exist. The `data/` directory is local runtime data and is ignored by git. Each role maps to a Pico serial number:

```json
{
  "timers": [
    {
      "role": "pump_lights",
      "pico_serial": "e66038b71387a039"
    }
  ]
}
```

Each timer role has a scheduler state file under `../data/timers/`. For example, `../data/timers/pump_lights.json` is the state file for the `pump_lights` Pico role. Event IDs such as `pump` and `lights` identify the timer on that board, while `ch` identifies the GPIO pin on that board.

Read the timer state:

```bash
curl http://localhost:8000/api/timers/pump_lights
```

Stream timer state changes for that role:

```bash
curl -N 'http://localhost:8000/api/timers/pump_lights?stream=true'
```

Each timer role gets one background monitor thread at server startup. The monitor owns the Pico serial connection, keeps the timer state current from Pico reports, emits stream events to connected HTTP clients, and temporarily closes serial before copying state and resetting the Pico. Reported timer state uses `elapsed_t` for total elapsed seconds, `cycle_t` for the current pattern-cycle offset, and `current_value` for the output value.

Write a new timer state. PUT always saves the host state file, copies it to the Pico, and resets the timer:

```bash
curl -X PUT http://localhost:8000/api/timers/pump_lights \
  -H 'content-type: application/json' \
  --data @data/timers/pump_lights.json
```

A successful PUT returns a short success message. If the Pico is disconnected or `mpremote` fails, the response explains which step failed and the monitor keeps retrying the serial connection by Pico serial.

The browser test page is available at:

```text
http://localhost:8000/timers/test
```

It has separate GET and PUT sections, separate role inputs for each section, an editable JSON payload, generator groups for a quick 5-second on/off pin test and a pump/lights example, and generated curl commands for both GET and PUT.

GET and PUT each show their own confirmation prompt, HTTP status, and response body so the page can be used before building a real UI. PUT always copies state to the Pico and resets it.

## Run The Runtime Page

During development, run with reload on port 8000:

```bash
cd /home/hugo/.openclaw/workspace/code/plamp
uv run uvicorn pico_api.server:app --host 0.0.0.0 --port 8000 --reload
```

For deployment, use port 80 through a service or reverse proxy instead of the development reload server.

Open the runtime page:

```text
http://<hostname>:8000/
```

Or use the Pi IP address directly:

```text
http://<raspberry-pi-ip>:8000/
```

The JSON version is available at:

```bash
curl http://localhost:8000/runtime
```

The app log is written under local runtime data and rotated when it reaches 1 MB:

```text
data/plamp.log
data/plamp.log.1
```

Read recent log lines through the API:

```bash
curl 'http://localhost:8000/api/logs?lines=200'
```

The page reports detected Pico boards, network devices, monitor state, log path, and host software paths. The JSON keeps a default-route field because it is useful when debugging which network interface and gateway the Pi is actually using, but the page keeps that detail out of the main view.
