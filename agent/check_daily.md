# Daily Check

Goal: produce one daily update that extends three timelines.

## Inputs

- latest grow summaries (`grow/grows/<latest>/summaries/daily` and `weekly`)
- latest captures (prefer daylight, clear, unobstructed)
- recent runtime context (lights, pump, automations, camera continuity)

## Required Timelines

1. `nature`
- Grow cycle stage.
- Harvest date and quantity facts/estimates.
- Notable biology events (pest, stress, disease, recovery).

2. `plamp`
- Lights/pump/automations status.
- Picture cadence and gaps.
- Any drift, outages, or corrections.

3. `gardener`
- What to do next (trim, harvest, inspect, add/remove/adjust).
- Timing and priority.

## Update Rules

- Start from the previous daily check and revise each timeline.
- Add only meaningful new events since the last check.
- Keep claims evidence-based and conservative.
- Include exactly 1 to 3 relevant pictures (daytime preferred).

## Output Format

- One concise report with sections: `nature`, `plamp`, `gardener`.
- Include picture paths or URLs under each relevant section.
