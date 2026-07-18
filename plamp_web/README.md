# Plamp Web Service

`plamp-web` provides REST, SSE, Pico monitoring, scheduled camera capture, and the fallback website. Agents and other web apps use the same API.

## Run

```bash
uv run uvicorn plamp_web.server:app --host 127.0.0.1 --port 8000
```

Production installation and service control belong to `plampctl`. With nginx enabled, requests follow `browser or agent -> nginx :80 -> plamp-web :8000`.

Useful pages:

- `/` - static main Pico scheduler and camera client; it loads all runtime state through REST and SSE
- `/settings` — static hardware and configuration client; it loads and saves through REST
- `/controllers/{controller}` — static controller diagnostics and command client using REST and SSE
- `/system` — static host diagnostics and service-action client; logs load on demand through REST
- `/api/test` — runnable API examples
- `/openapi.json` — machine-readable API

## Controller contract

- The Pico is silent until commanded.
- The host requests a report every five seconds. Linux USB events provide immediate add/remove evidence.
- A controller is `OK` only after a valid report. Otherwise it is `ERROR` with the failed step, serial, port, timestamps, and received raw lines.
- Successful periodic reports update SSE and the in-memory serial log without writing an INFO line every five seconds.
- Serial connections are short transactions protected by shared locks; the service does not permanently own the port.

Schedule changes are one controller-wide transaction:

1. Read and validate a proposed controller.
2. Obtain a fresh report from the configured Pico.
3. Compile every configured channel and stage config plus applied state.
4. Flash once and wait for the Pico's valid post-flash report.
5. Commit both local files.

Any failure before step 5 returns an error and leaves desired config and applied state unchanged. There is no offline queue or automatic reconnect apply.

## Pico Scheduler State

Desired configuration is `data/config.json`. Semantic schedules live under `controllers.<id>.settings.devices`; generated state files keep device state in `data/timers/<controller-id>.json`.

The main API groups are:

- `/api/config` — desired configuration
- `/api/status` — combined state and SSE
- `/api/controllers` — controller health, schedule, report, pulse, and low-level apply operations
- `/api/camera` — captures and images
- `/api/system` — host facts and detected hardware

Application diagnostics are stored in `data/plamp.log` and exposed by `/api/logs` and the controller serial-log endpoint.
