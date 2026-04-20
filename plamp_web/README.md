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

For port 80, put nginx in front of the app and keep Uvicorn on port 8000:

```bash
sudo apt update
sudo apt install nginx
sudo cp deploy/nginx/plamp.conf /etc/nginx/sites-available/plamp
sudo ln -sf /etc/nginx/sites-available/plamp /etc/nginx/sites-enabled/plamp
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
uv run uvicorn plamp_web.server:app --host 127.0.0.1 --port 8000
```

Then open:

```text
http://<raspberry-pi-ip>/
```

To start Uvicorn automatically after reboot, run this from the repo root as the
user that should run Plamp:

```bash
deploy/systemd/install-plamp-web-service.sh
```

The installer writes `/etc/systemd/system/plamp-web.service` with the detected
user, repo path, and `uv` path. nginx remains the public port-80 service.

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

## Timer State

Each controller has a saved state file:

```text
data/timers/<controller-id>.json
```

Timer events use `pin`:

```json
{
  "report_every": 10,
  "events": [
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
