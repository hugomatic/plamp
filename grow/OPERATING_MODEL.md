# Grow operating model

Keep it filesystem-first and boring:

- cron owns the hourly capture reflex
- heartbeat audits/repairs the reflex; it is not the primary scheduler
- slower layers reuse artifacts from faster layers
- observations stay fixed; judgments improve through append-only prediction history

## Roles

Every deviation should be attributed, when possible, to one of:

- **nature**: the plant/environment did something real
- **gardener**: a human action or omission changed the path
- **system / Plamp**: sensing, scheduling, inference, or logging failed

If evidence is insufficient, say so and ask the gardener.

## Cadence model

Every layer answers the same four questions:

1. what happened?
2. what was expected?
3. what does it mean for taste/yield?
4. what changed in the model?

Faster layers prepare inputs for slower layers. Cron owns the hourly reflex; heartbeat audits and repairs stale or confusing situations instead of becoming a second scheduler.

Every cadence that touches predictions follows the same write pattern:

1. read `predictions/current.json`
2. update the current belief/state if the judgment changed
3. append one entry to `predictions/history.jsonl`

History entries must include the explicit delta/change from the previous state so the prediction evolution can be reconstructed later.

### Hourly

Owner: cron + direct scripts.

- **ingest:** current capture, previous capture/sidecar when present, `predictions/current.json` when present, grow config, and any recent gardener note already on disk
- **process / judgment:** capture the scene, compare against the previous hour and current short-horizon expectation, classify obvious deviations, and decide whether the miss looks like nature, gardener, system, or still-unclear
- **output artifacts:** append-only event record, capture sidecar, comparison summary, and when needed an updated `predictions/current.json` plus one appended `predictions/history.jsonl` entry with the delta
- **feeds next slower layer:** provides the raw evidence and unresolved exceptions that the 12h review rolls up
- **reliability:** confirm the reflex is alive

### Every 12 hours

- **ingest:** hourly events/capture sidecars/comparisons for the last half-day, `predictions/current.json`, and any gardener notes in that window
- **process / judgment:** review the half-day as a window (day/night, drift, repeated uncertainty, missed captures), decide whether the short-horizon model held, and tighten or lower confidence in immediate concerns
- **output artifacts:** one 12h summary plus any updated prediction state in `predictions/current.json` and one appended history entry with the explicit delta
- **feeds next slower layer:** hands the daily layer a compact judgment about window quality, immediate plant behavior, and whether evidence is trustworthy enough to summarize
- **reliability:** detect partial failures hourly runs may miss

### Daily

- **ingest:** the last 24 hours of hourly artifacts, both 12h summaries, `predictions/current.json`, and relevant gardener actions for water, pruning, feeding, or environment changes
- **process / judgment:** compress the day into a readable operational story, judge whether daily expectations for growth, water, pruning, and light behavior were met, and decide what needs attention tomorrow
- **output artifacts:** one daily summary plus any updated prediction state in `predictions/current.json` and one appended history entry with explicit delta, including open questions when evidence is weak
- **feeds next slower layer:** gives the weekly layer day-sized judgments instead of forcing it to recompute from every hourly capture
- **reliability:** verify hourly evidence was good enough to trust

### Weekly

- **ingest:** daily summaries, daily selected/representative pictures, relevant 12h summaries for anomalies, `predictions/current.json`, and the week’s material gardener interventions
- **process / judgment:** compare several days of trend, correct the trend model from curated evidence, and decide which deviations are recurring, structural, or still ambiguous
- **output artifacts:** one weekly summary plus any updated trend state in `predictions/current.json`, one appended history entry with explicit delta, and a short operator-priority list for the coming week
- **image policy:** do **not** reread all raw hourly pictures at weekly scope; weekly works from daily summaries + curated daily evidence + prediction history
- **feeds next slower layer:** provides the monthly layer with trend judgments, recurring failure modes, selected evidence, and whether the crop path still looks viable
- **reliability:** identify recurring misses, blind spots, or debt

### Monthly

- **ingest:** weekly summaries, selected daily exceptions, `predictions/current.json`, any stage-change or strategy-change notes from the gardener, and a small high-signal image gallery when it helps
- **process / judgment:** review stage transition and long-horizon progress, extract lessons, and build the visual story from selected evidence instead of brute-force image review
- **output artifacts:** one monthly summary plus any updated strategy state in `predictions/current.json`, one appended history entry with explicit delta, explicit loop-change recommendations when needed, and optionally a small before/after or high-signal gallery
- **feeds next slower layer:** this is the slowest review layer; it resets strategic expectations that future weekly/daily/hourly judgments should inherit
- **reliability:** decide whether the loop itself needs changes

## Predictions

Facts and judgments are different artifacts.

### Observations are durable facts

Examples:

- image path
- timestamp
- brightness measurement
- gardener note

Do not rewrite old observations except for narrow repair records.

### Prediction state lives in one current file

`predictions/current.json` stores the latest belief/state the next cadence should inherit.

Recommended fields:

- `grow_id`
- `updated_at`
- `scope`
- `question`
- `current_state`
- `basis`
- `target_window`
- `expected_actor`
- `taste_yield_relevance`
- `status`

### Prediction history is append-only

`predictions/history.jsonl` records each prediction change as one line.

Recommended fields per entry:

- `history_id`
- `created_at`
- `grow_id`
- `scope`
- `question`
- `delta`
- `previous_state_summary`
- `new_state_summary`
- `reason`
- `basis`
- `attribution`
- `status`

Rules:

- each cadence reads `predictions/current.json` before judging
- only `predictions/current.json` holds the latest state
- never rewrite or delete old `predictions/history.jsonl` entries
- every history entry must state the explicit delta/change
- explicitly note whether the deviation looks like nature, gardener, system, or still-unclear

## Suggested runtime layout

```text
grow/grows/<grow-id>/
  grow.json
  events.jsonl
  captures/YYYY-MM-DD/
  summaries/
    12h/
    daily/YYYY-MM-DD.json
    weekly/YYYY-Www.json
    monthly/YYYY-MM.json
  predictions/
    current.json
    history.jsonl
```

## Logging preference

Prefer answer-first outputs over plumbing dumps:

- what happened
- what was expected
- taste/yield meaning
- model change

Unix/tool-first still applies: small tools, plain files, obvious outputs.
