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

### Hourly

Owner: cron + direct scripts.

- observe: capture the scene and sidecar facts
- compare: check against the latest short-horizon expectation
- update: write an event and, if needed, a small prediction/amendment
- reliability: confirm the reflex is alive

### Every 12 hours

- observe: compare the last half-day window (day/night, drift, repeated uncertainty)
- compare: review whether recent behavior matched the short-horizon model
- update: amend confidence, next checks, or immediate concerns
- reliability: detect partial failures hourly runs may miss

### Daily

- observe: compress the last 24 hours into a readable summary
- compare: review daily expectations for growth, water, pruning, and light behavior
- update: issue/amend next-day judgments and questions
- reliability: verify hourly evidence was good enough to trust

### Weekly

- observe: compare several days of trend, not just adjacent captures
- compare: review whether the week matched the trend model
- update: amend trend judgments and operator priorities
- reliability: identify recurring misses, blind spots, or debt

### Monthly

- observe: review stage transition and long-horizon progress
- compare: review whether the strategy matched the desired crop path
- update: amend strategy-level predictions or operating assumptions
- reliability: decide whether the loop itself needs changes

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
