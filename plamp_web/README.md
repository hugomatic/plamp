# Plamp Web Service

`plamp-web` is the current FastAPI service for REST, SSE, Pico monitoring, scheduled camera captures, and the fallback website.

## Run

```bash
uv run uvicorn plamp_web.server:app --host 127.0.0.1 --port 8000
```

Production installation is handled by the root bootstrap script or:

```bash
deploy/systemd/install-plamp-web-service.sh
```

With nginx enabled, the public path is `browser -> nginx :80 -> plamp-web :8000`.

Pages:

- `/` - main Pico scheduler page and camera
- `/settings` - hardware, host status, and configuration
- `/api/test` - executable API examples

## Responsibilities

- Read and validate `data/config.json`.
- Poll Pico telemetry through short shared transactions and publish SSE updates.
- Generate and apply scheduler firmware.
- Schedule and capture pictures.
- Expose REST operations used by the browser and `plamp_cli`.

The service, direct CLI, flashing, and camera captures use the shared library locks. The service closes each Pico serial connection after its response and does not permanently own hardware.

## Configuration

Desired configuration lives in `data/config.json`. Scheduler controllers use `payload` for generated state and `settings.devices` for semantic device configuration:

```json
{
  "controllers": {
    "pump_lights": {
      "type": "pico_scheduler",
      "payload": {
        "pico_serial": "e66038b71387a039",
        "report_every": 10,
        "devices": []
      },
      "settings": {
        "devices": {
          "pump": {
            "pin": 15,
            "output_type": "gpio",
            "editor": {"kind": "cycle"}
          }
        }
      }
    }
  }
}
```

## Pico Scheduler State

Generated controller state is stored at `data/timers/<controller-id>.json`. These state files keep device state. For compatibility, `controllers.<id>.payload.report_every` stores the host Pico polling interval; it is not copied into firmware.

API split:

- `/api/config`: desired configuration
- `/api/system`: host facts and detected hardware
- `/api/status`: resolved state and SSE telemetry
- `/api/controllers`: controller state and commands
- `/api/camera`: captures and images

## Logs

Application logs are written to `data/plamp.log` and exposed through:

```bash
curl 'http://localhost:8000/api/logs?lines=200'
```
