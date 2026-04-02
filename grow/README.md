# Grow loop

Minimal filesystem-first grow tending tools.

This is app/repo code, not an OpenClaw skill.

The current operating model is documented in [`OPERATING_MODEL.md`](./OPERATING_MODEL.md).

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
grow/grows/<grow-id>/summaries/                 # optional daily/weekly/monthly review artifacts
grow/grows/<grow-id>/predictions/               # durable prediction artifacts by cadence
grow/grows/<grow-id>/amendments/               # later judgment improvements, never history rewrites
```

Image sidecar metadata is intentionally plain JSON so later tooling can compare captures without opening the event log.

Higher-frequency artifacts should prepare inputs for lower-frequency review. Hourly capture sidecars and event records feed 12-hour, daily, weekly, and monthly summaries instead of each slower layer recomputing everything from scratch.

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

Observations in that timeline should remain fixed. Predictions and later amendments belong in their own artifacts so old facts stay intact while judgments improve.

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

Cron owns the hourly capture reflex. Heartbeat is useful as an auditor/repair loop that notices missed runs, stale data, or confusing outputs, but heartbeat is not the primary scheduler.

Cron example:

```cron
7 * * * * cd /home/hugo/.openclaw/workspace/code/plamp && /usr/bin/python3 grow/hourly_tend.py --grow grow-thai-basil-siam-queen-2026-03-27 >> /tmp/plamp-grow-hourly.log 2>&1
```

Or systemd timer if Hugo wants a managed service later.

When writing sidecars, summaries, or logs, prefer concise answers/results over plumbing dumps when possible.

Tracked runtime artifact examples live in [`templates/`](./templates/).

## Current grow

Tracked config for the first grow:

- `grow/grows/grow-thai-basil-siam-queen-2026-03-27/grow.json`
