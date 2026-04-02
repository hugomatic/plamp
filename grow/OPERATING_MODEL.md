# Grow operating model

This is the intended operating model for the grow loop.

Keep it filesystem-first and boring:

- cron owns the hourly capture reflex
- heartbeat is an auditor/repair loop, not the primary scheduler
- higher-frequency layers prepare cleaner inputs for lower-frequency layers
- lower-frequency layers make slower, better judgments without rewriting old facts

## Cadence layers

Each layer should answer the same four questions in a different time horizon:

1. what do we observe?
2. what prediction or judgment should be reviewed or amended?
3. what does this mean for the current taste/yield path?
4. is the system doing its duty reliably?

### Hourly

Primary owner: cron + direct scripts.

Purpose:

- observation: capture the current scene and basic machine-readable sidecar facts
- prediction review/update: check whether the latest expectation still looks plausible enough to keep watching
- goal impact: flag obvious drift that could hurt taste/yield later
- reliability / duty verification: confirm the camera, light-state inference, and scheduled capture reflex are still alive

Outputs:

- append-only event entries in `events.jsonl`
- capture image + sidecar JSON
- optional lightweight prediction review note when the latest expectation needs follow-up

Notes:

- this is the primary sensing loop
- keep the output answer-first: what happened, what changed, what looks wrong
- do not bury the result inside plumbing-heavy logs when a short result record will do

### Every 12 hours

Purpose:

- observation: compare day/night windows or the most recent half-day run
- prediction review/update: amend short-horizon expectations such as light schedule confidence, visible vigor, or likely next checks
- goal impact: note whether the plant still appears on the intended taste/yield path
- reliability / duty verification: detect partial failure patterns that hourly runs may miss (repeated unclear comparisons, stale sidecars, missing windows)

Outputs:

- half-day summary or review artifact
- amendment records that point at earlier predictions when judgment improves

### Daily

Purpose:

- observation: compress the last 24 hours into a human-reviewable summary
- prediction review/update: issue or amend daily expectations for growth, water, pruning, or investigation needs
- goal impact: state whether the grow is moving toward the current taste/yield goal
- reliability / duty verification: verify that the hourly reflex actually happened enough times and produced usable evidence

Outputs:

- daily summary artifact
- prediction snapshot and/or amendment artifact
- explicit open questions for the next day

### Weekly

Purpose:

- observation: compare across several days, not just adjacent captures
- prediction review/update: revisit trend-level judgments with more evidence
- goal impact: decide whether the current approach still serves the intended crop outcome
- reliability / duty verification: review recurring misses, weak sensors, noisy logs, or operational debt

Outputs:

- weekly summary artifact
- updated trend judgments
- reliability punch list if the system is wasting operator time

### Monthly

Purpose:

- observation: inspect stage transitions and long-horizon progress
- prediction review/update: retire, confirm, or amend longer-range predictions
- goal impact: assess whether the operating strategy is producing the desired taste/yield tradeoff
- reliability / duty verification: decide whether the loop itself should change

Outputs:

- monthly review artifact
- strategy-level amendments
- operating-model changes if the loop is not earning its keep

## Data model: observations, predictions, amendments

Facts and judgments should not be treated the same.

### Observations are durable facts

Examples:

- a captured image path
- a brightness measurement
- a timestamp
- a human note about what they saw

These should stay fixed once written, except for narrowly-scoped repair records when something was malformed.

### Predictions are durable artifacts

A prediction is a record of what the system or operator believed at that time.

Examples:

- "the light should turn on within the next two hourly captures"
- "seedlings likely need thinning within 5 days"
- "the current path favors yield more than flavor"

Predictions should be written as their own artifacts, not folded back into old observations.

Recommended fields:

- `prediction_id`
- `created_at`
- `grow_id`
- `scope` (`hourly`, `12h`, `daily`, `weekly`, `monthly`)
- `question`
- `prediction`
- `basis` (what evidence supported it)
- `target_window`
- `status` (`open`, `confirmed`, `missed`, `superseded`)

### Amendments do not overwrite history

When judgment improves later, write an amendment that points at the earlier prediction.

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
- old observations stay fixed
- old predictions stay visible as historical judgment
- newer amendments explain why thinking changed

This keeps the trail honest: reality happened once, but interpretation can improve.

## Suggested runtime layout

Tracked docs define the contract; runtime artifacts live inside each grow folder.

```text
grow/grows/<grow-id>/
  grow.json
  events.jsonl
  captures/YYYY-MM-DD/
  summaries/
    daily/YYYY-MM-DD.json
    weekly/YYYY-Www.json
    monthly/YYYY-MM.json
  predictions/
    hourly/*.json
    daily/*.json
    weekly/*.json
    monthly/*.json
  amendments/
    *.json
```

The repo should only track examples/templates when needed. Live grow runtime data can remain ignored.

## Logging preference

When a sidecar or summary exists to answer the real question, prefer writing that answer directly.

Good:

- `light_state=off and capture gap looks normal`
- `daily summary says vigor improved but yield path still unclear`

Less good:

- large plumbing dumps without a short conclusion

Unix/tool-first still applies: small tools, plain files, obvious outputs.
