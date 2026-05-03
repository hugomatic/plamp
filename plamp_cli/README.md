# Plamp CLI

`plamp` is a JSON-first command-line client for `plamp-web`.

## Defaults

- base URL: `http://127.0.0.1:8000`
- stdout: JSON
- stderr: diagnostics only

## Remote Use

```bash
plamp --host pi.local timers get pump_lights
ssh pi.local plamp config get
ssh pi.local plamp pics get grow:latest --stdout > latest.jpg
```

## JSON Input

```bash
plamp config set @config.json
cat state.json | plamp timers set pump_lights -
```

## Pictures

```bash
plamp pics list --source grow
plamp pics take --camera-id rpicam_cam0
plamp pics get grow:latest --out latest.jpg
plamp pics get grow:latest --stdout > latest.jpg
```

## Exit Codes

- `0` success
- `2` usage error
- `3` API error
- `4` network error
- `5` local input error
