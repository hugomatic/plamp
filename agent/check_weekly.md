# Weekly Check

Goal: produce one weekly synthesis across the three timelines and decide next-week priorities.

## Inputs

- all daily checks since previous weekly check
- latest weekly summary in grow folder
- representative daytime images for the week
- notable runtime events (automation drift, outages, interventions)

## Required Timelines

1. `nature`
- Week-over-week growth progress.
- Harvest events and quantities.
- Major health shifts (pest/disease/stress/recovery).

2. `plamp`
- Reliability summary for lights/pump/automations.
- Camera coverage quality and missing windows.
- Important fixes or regressions.

3. `gardener`
- Weekly actions completed.
- Next-week action plan with priority and cadence.

## Update Rules

- Compare this week vs prior week, not single-day snapshots.
- Keep only high-signal events.
- Include 1 to 3 representative pictures for the week.
- End with explicit next-week risks and mitigations.

## Output Format

- One concise weekly report with sections: `nature`, `plamp`, `gardener`, `next_week`.
