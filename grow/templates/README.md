# Runtime artifact templates

These tracked templates document the expected runtime shape without committing live grow data.

Use them as examples when creating summary or prediction artifacts under a real grow folder.

Expected live layout:

```text
grow/grows/<grow-id>/summaries/12h/
grow/grows/<grow-id>/summaries/daily/
grow/grows/<grow-id>/summaries/weekly/
grow/grows/<grow-id>/summaries/monthly/
grow/grows/<grow-id>/predictions/current.json
grow/grows/<grow-id>/predictions/history.jsonl
```

Tracked examples in this folder:

- `prediction.example.json`
- `predictions.current.example.json`
- `predictions.history.example.jsonl`

All templates should stay small, concrete, and answer-first:

- what happened?
- what was expected?
- what does it mean for taste/yield?
- what changed in the model?

Cadence notes:

- hourly / 12h / daily / weekly checks should leave or update prediction artifacts, not just prose: each cadence reads `predictions/current.json`, updates it if needed, then appends one `predictions/history.jsonl` entry
- history entries must include the explicit delta/change so the prediction path can be reconstructed later
- gardener interventions are especially important to surface because they are the weakest automation link; current state and summaries should make actions like move to tower, add food, or change water obvious
- weekly summarizes trend from daily summaries + selected daily pictures + prediction history; it should not reread all raw pictures
- monthly summarizes lessons from weekly judgments + selected evidence and may include a small visual story / before-after set
