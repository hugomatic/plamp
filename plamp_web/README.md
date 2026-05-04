# plamp_web

FastAPI web server for Plamp.

## Run

From the repo root:

```bash
uv run uvicorn plamp_web.server:app --host 0.0.0.0 --port 8000
```

Open:

```text
http://<raspberry-pi-ip>:8000/
```

## Run on boot with nginx

Use nginx as the public port-80 proxy and systemd to keep Uvicorn running on
unprivileged port 8000 after boot:

```bash
sudo apt update
sudo apt install nginx
sudo cp deploy/nginx/plamp.conf /etc/nginx/sites-available/plamp
sudo ln -sf /etc/nginx/sites-available/plamp /etc/nginx/sites-enabled/plamp
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
deploy/systemd/install-plamp-web-service.sh
```

The service installer writes `/etc/systemd/system/plamp-web.service` with the
detected user, repo path, and `uv` path. nginx remains the public port-80
service.

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

For development, stop the boot service before running Uvicorn manually:

```bash
sudo systemctl stop plamp-web
uv run uvicorn plamp_web.server:app --host 127.0.0.1 --port 8000 --reload
```

Then restore the boot-managed server:

```bash
sudo systemctl start plamp-web
```

Pages:

- `/` - timers and camera
- `/settings` - system status and Plamp config
- `/api/test` - manual API requests

## Config

Runtime config is local:

```text
data/config.json
```

Use `/settings` to edit:

- Pico controllers
- devices and their pins
- cameras
- hostname

The main page is based on this config. Extra pins reported by a Pico are ignored.

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

## Timer State

Each controller has a saved state file:

```text
data/timers/<controller-id>.json
```

Timer devices use `pin`:

```json
{
  "report_every": 10,
  "devices": [
    {
      "id": "pump",
      "type": "gpio",
      "pin": 15,
      "current_t": 0,
      "reschedule": 1,
      "pattern": [
        {"val": 1, "dur": 300},
        {"val": 0, "dur": 1800}
      ]
    }
  ]
}
```

`report_every` is configured on the controller in `data/config.json`. Timer
state files keep schedule devices; any older `report_every` value in
`data/timers/<controller>.json` is legacy and is not the source of truth for
Pico scheduler reporting cadence.

## Logs

```text
data/plamp.log
```

Recent logs:

```bash
curl 'http://localhost:8000/api/logs?lines=200'
```

## More

- [`../README.md`](../README.md)
- [`../pico_scheduler/README.md`](../pico_scheduler/README.md)
