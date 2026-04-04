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
grow/grows/<grow-id>/summaries/                 # 12h/daily/weekly/monthly review artifacts
grow/grows/<grow-id>/predictions/current.json   # latest prediction belief/state
grow/grows/<grow-id>/predictions/history.jsonl  # append-only prediction changes with explicit deltas
```

Image sidecar metadata is intentionally plain JSON so later tooling can compare captures without opening the event log.

The grow loop has three actors:

- **nature**: what the plant/environment actually did
- **gardener**: what the human did or failed to do
- **system / Plamp**: what sensing/scheduling/inference/logging did or failed to do

Every cadence should answer, concretely:

1. what happened?
2. what was expected?
3. what does it mean for taste/yield?
4. what changed in the model?

Higher-frequency artifacts should prepare inputs for lower-frequency review. The handoff is explicit:

- hourly artifacts feed the 12h review
- 12h summaries feed the daily review
- daily summaries + daily selected/representative pictures + prediction history feed the weekly review
- weekly summaries + selected evidence can feed the monthly review

Weekly is for trend + model correction from curated evidence, not rereading all raw pictures.
Monthly is for lessons + selected evidence + visual story, and may include a small high-signal gallery or before/after pair.

That keeps slower layers from recomputing everything from scratch and preserves the durable-facts + current-state-plus-history judgment model.

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

Observations in that timeline should remain fixed. Prediction handling is separate: each cadence reads `predictions/current.json`, updates it if needed, and appends a `predictions/history.jsonl` entry that includes the explicit delta/change.

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
5. when prediction state changes, update `predictions/current.json` and append `predictions/history.jsonl`

## Scheduling

There is no new framework here. The intended scheduler is the host's normal scheduler.

Cron owns the hourly capture reflex. Heartbeat is the auditor/repair loop for stale data, missed windows, and confusing outputs.

Cron example:

```cron
7 * * * * cd /home/hugo/.openclaw/workspace/code/plamp && /usr/bin/python3 grow/hourly_tend.py --grow grow-thai-basil-siam-queen-2026-03-27 >> /tmp/plamp-grow-hourly.log 2>&1
```

Or systemd timer if Hugo wants a managed service later.

When writing sidecars, summaries, or prediction state/history artifacts, keep outputs answer-first and additive.

Tracked runtime artifact examples live in [`templates/`](./templates/).

## Current grow

Tracked config for the first grow:

- `grow/grows/grow-thai-basil-siam-queen-2026-03-27/grow.json`
