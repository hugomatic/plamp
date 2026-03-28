# Grow loop

Minimal filesystem-first grow tending tools.

This is app/repo code, not an OpenClaw skill.

## Canonical grow layout

Each grow lives under:

```text
grow/grows/<grow-id>/
```

Tracked files:

```text
grow/grows/<grow-id>/grow.json        # canonical grow config / identity
```

Runtime files created by the tending tools:

```text
grow/grows/<grow-id>/events.jsonl               # append-only event log
grow/grows/<grow-id>/captures/YYYY-MM-DD/       # hourly images + sidecar metadata
grow/grows/<grow-id>/captures/YYYY-MM-DD/*.jpg
grow/grows/<grow-id>/captures/YYYY-MM-DD/*.json
```

Image sidecar metadata is intentionally plain JSON so later tooling can compare captures without opening the event log.

Each capture sidecar stores:

- `timestamp`
- `grow_id`
- `image_path`
- `camera_command`
- `camera_script`
- `brightness_mean`
- `previous_capture` summary when one exists
- `comparison` summary for light-state inference
- `ai_compare` payload with current/previous image paths and a ready-to-use prompt

`events.jsonl` is the human/audit timeline. One JSON object per line.

## Direct tools

Run from the repo root:

### Append an event

```bash
python3 grow/log_event.py --grow grow-thai-basil-siam-queen-2026-03-27 --kind note --message "Seeds started in Root Riot cubes"
```

### Capture one photo into the grow folder

```bash
python3 grow/capture_photo.py --grow grow-thai-basil-siam-queen-2026-03-27
```

### Compare the latest capture against the previous one

```bash
python3 grow/compare_light.py --grow grow-thai-basil-siam-queen-2026-03-27
```

### Run one hourly tending pass

This composes the direct tools above:

```bash
python3 grow/hourly_tend.py --grow grow-thai-basil-siam-queen-2026-03-27
```

What it does:

1. capture a photo into the grow folder
2. write image sidecar metadata
3. compare current vs previous capture for likely light state change
4. append structured events to `events.jsonl`

## Scheduling

There is no new framework here. The intended scheduler is the host's normal scheduler.

Cron example:

```cron
7 * * * * cd /home/hugo/.openclaw/workspace/code/plamp && /usr/bin/python3 grow/hourly_tend.py --grow grow-thai-basil-siam-queen-2026-03-27 >> /tmp/plamp-grow-hourly.log 2>&1
```

Or systemd timer if Hugo wants a managed service later.

## Current grow

Tracked config for the first grow:

- `grow/grows/grow-thai-basil-siam-queen-2026-03-27/grow.json`
