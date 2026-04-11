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
uv run python -c "import fastapi, uvicorn"
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

Read the current saved timer state:

```bash
curl http://localhost:8000/api/timers/pump_lights
```

Save only, without copying to the Pico or resetting it:

```bash
curl -X PUT 'http://localhost:8000/api/timers/pump_lights?apply=false' \
  -H 'content-type: application/json' \
  --data @data/timers/pump_lights.json
```

The save-only response confirms that the host file was updated and the Pico was not touched:

```json
{
  "role": "pump_lights",
  "saved": true,
  "apply_requested": false,
  "apply_status": "skipped"
}
```

Save and apply to the assigned Pico. This is the default because `current_t` is timing-sensitive:

```bash
curl -X PUT http://localhost:8000/api/timers/pump_lights \
  -H 'content-type: application/json' \
  --data @data/timers/pump_lights.json
```

The apply response uses the same fields, with `apply_requested: true`, `apply_status: "ok"`, and Pico copy/reset details when `mpremote` succeeds.

The browser test page is available at:

```text
http://localhost:8000/timers/test
```

It has separate GET and PUT sections, separate role inputs for each section, an editable JSON payload, generator groups for a quick 5-second on/off pin test and a pump/lights example, an apply radio for save-only vs save-and-reset, and generated curl commands for both GET and PUT.

GET and PUT each show their own confirmation prompt, HTTP status, and response body so the page can be used before building a real UI.

## Run The Runtime Page

During development, run with reload on port 8000:

```bash
cd /home/hugo/.openclaw/workspace/code/plamp
uv run uvicorn pico_api.server:app --host 0.0.0.0 --port 8000 --reload
```

For deployment, use port 80 through a service or reverse proxy instead of the development reload server.

Open the runtime page:

```text
http://<raspberry-pi-ip>:8000/
```

On the local network, the hostname form may also work:

```text
http://raspberrypi.local:8000/
```

On this host right now, the IP form is likely:

```text
http://192.168.68.56:8000/
```

The JSON version is available at:

```bash
curl http://localhost:8000/runtime
```

The page reports detected Pico boards, network devices, and host software paths. The JSON keeps a default-route field because it is useful when debugging which network interface and gateway the Pi is actually using, but the page keeps that detail out of the main view.
