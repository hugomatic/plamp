# Daily Check

Goal: produce one daily update that extends three timelines and one cheap visual summary.

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
- Generate or refresh the labeled stack image for the latest daily check using:
  `python /home/hugo/.openclaw/workspace/code/plamp/scripts/grow_overlay_compare.py --grow-dir <grow-dir> --anchor <best current picture>`
- Prefer the best current daylight picture as the anchor.
- Save the stack under `<grow-dir>/summaries/overlays/<daily-date>/stack-month-week-today.jpg`.

## Output Format

- One concise report with sections: `nature`, `plamp`, `gardener`.
- Include picture paths or URLs under each relevant section.
- Ensure the stack image exists alongside the daily check so routine status replies can send just:
  - the latest stack picture
  - the latest daily check markdown
