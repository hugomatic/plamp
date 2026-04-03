# Grow operating model

Keep it filesystem-first and boring:

- cron owns the hourly capture reflex
- heartbeat audits/repairs the reflex; it is not the primary scheduler
- slower layers reuse artifacts from faster layers
- observations stay fixed; judgments improve through additive predictions/amendments

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

### Hourly

Owner: cron + direct scripts.

- **ingest:** current capture, previous capture/sidecar when present, latest open hourly or 12h prediction, grow config, and any recent gardener note already on disk
- **process / judgment:** capture the scene, compare against the previous hour and current short-horizon expectation, classify obvious deviations, and decide whether the miss looks like nature, gardener, system, or still-unclear
- **output artifacts:** append-only event record, capture sidecar, comparison summary, and only when warranted a small hourly prediction or additive amendment
- **feeds next slower layer:** provides the raw evidence and unresolved exceptions that the 12h review rolls up
- **reliability:** confirm the reflex is alive

### Every 12 hours

- **ingest:** hourly events/capture sidecars/comparisons for the last half-day, open hourly predictions and amendments, and any gardener notes in that window
- **process / judgment:** review the half-day as a window (day/night, drift, repeated uncertainty, missed captures), decide whether the short-horizon model held, and tighten or lower confidence in immediate concerns
- **output artifacts:** one 12h summary plus any new 12h prediction or additive amendment needed to carry uncertainty forward
- **feeds next slower layer:** hands the daily layer a compact judgment about window quality, immediate plant behavior, and whether evidence is trustworthy enough to summarize
- **reliability:** detect partial failures hourly runs may miss

### Daily

- **ingest:** the last 24 hours of hourly artifacts, both 12h summaries, open daily predictions/amendments, and relevant gardener actions for water, pruning, feeding, or environment changes
- **process / judgment:** compress the day into a readable operational story, judge whether daily expectations for growth, water, pruning, and light behavior were met, and decide what needs attention tomorrow
- **output artifacts:** one daily summary plus any next-day prediction or additive amendment, including explicit open questions when evidence is weak
- **feeds next slower layer:** gives the weekly layer day-sized judgments instead of forcing it to recompute from every hourly capture
- **reliability:** verify hourly evidence was good enough to trust

### Weekly

- **ingest:** daily summaries, daily selected/representative pictures, relevant 12h summaries for anomalies, open weekly predictions/amendments, and the week’s material gardener interventions
- **process / judgment:** compare several days of trend, correct the trend model from curated evidence, and decide which deviations are recurring, structural, or still ambiguous
- **output artifacts:** one weekly summary plus any additive trend prediction/amendment and a short operator-priority list for the coming week
- **image policy:** do **not** reread all raw hourly pictures at weekly scope; weekly works from daily summaries + curated daily evidence + prediction amendments
- **feeds next slower layer:** provides the monthly layer with trend judgments, recurring failure modes, selected evidence, and whether the crop path still looks viable
- **reliability:** identify recurring misses, blind spots, or debt

### Monthly

- **ingest:** weekly summaries, selected daily exceptions, open monthly predictions/amendments, any stage-change or strategy-change notes from the gardener, and a small high-signal image gallery when it helps
- **process / judgment:** review stage transition and long-horizon progress, extract lessons, and build the visual story from selected evidence instead of brute-force image review
- **output artifacts:** one monthly summary plus any additive strategy-level prediction/amendment, explicit loop-change recommendations when needed, and optionally a small before/after or high-signal gallery
- **feeds next slower layer:** this is the slowest review layer; it resets strategic expectations that future weekly/daily/hourly judgments should inherit
- **reliability:** decide whether the loop itself needs changes

## Predictions and amendments

Facts and judgments are different artifacts.

### Observations are durable facts

Examples:

- image path
- timestamp
- brightness measurement
- gardener note

Do not rewrite old observations except for narrow repair records.

### Predictions are durable judgment records

A prediction records what nature, the gardener, or the system was expected to do in a target window.

Recommended fields:

- `prediction_id`
- `created_at`
- `grow_id`
- `scope` (`hourly`, `12h`, `daily`, `weekly`, `monthly`)
- `question`
- `prediction`
- `basis`
- `target_window`
- `status` (`open`, `confirmed`, `missed`, `superseded`)

### Amendments are additive

Amendments never overwrite prior predictions. They point at the earlier judgment and explain what changed.

Recommended fields:

- `amendment_id`
- `created_at`
- `grow_id`
- `prediction_id`
- `amends_prediction_id` or `amends_amendment_id`
- `reason`
- `updated_judgment`
- `basis`
- `status`

Rules:

- do not rewrite the old prediction in place
- keep old predictions visible as historical judgment
- add newer amendments when confidence, attribution, or expectation changes
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
    hourly/*.json
    12h/*.json
    daily/*.json
    weekly/*.json
    monthly/*.json
  amendments/
    *.json
```

## Logging preference

Prefer answer-first outputs over plumbing dumps:

- what happened
- what was expected
- taste/yield meaning
- model change

Unix/tool-first still applies: small tools, plain files, obvious outputs.
