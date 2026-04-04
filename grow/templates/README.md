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

All templates should stay small, concrete, and answer-first:

- what happened?
- what was expected?
- what does it mean for taste/yield?
- what changed in the model?

Cadence notes:

- every cadence reads `predictions/current.json`, updates it if needed, then appends one `predictions/history.jsonl` entry
- history entries must include the explicit delta/change so the prediction path can be reconstructed later
- weekly summarizes trend from daily summaries + selected daily pictures + prediction history; it should not reread all raw pictures
- monthly summarizes lessons from weekly judgments + selected evidence and may include a small visual story / before-after set
