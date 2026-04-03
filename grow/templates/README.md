# Runtime artifact templates

These tracked templates document the expected runtime shape without committing live grow data.

Use them as examples when creating summary/prediction/amendment artifacts under a real grow folder.

Expected live layout:

```text
grow/grows/<grow-id>/summaries/12h/
grow/grows/<grow-id>/summaries/daily/
grow/grows/<grow-id>/summaries/weekly/
grow/grows/<grow-id>/summaries/monthly/
grow/grows/<grow-id>/predictions/hourly/
grow/grows/<grow-id>/predictions/12h/
grow/grows/<grow-id>/predictions/daily/
grow/grows/<grow-id>/predictions/weekly/
grow/grows/<grow-id>/predictions/monthly/
grow/grows/<grow-id>/amendments/
```

All templates should stay small, concrete, and answer-first:

- what happened?
- what was expected?
- what does it mean for taste/yield?
- what changed in the model?

Cadence notes:

- weekly summarizes trend from daily summaries + selected daily pictures + amendments; it should not reread all raw pictures
- monthly summarizes lessons from weekly judgments + selected evidence and may include a small visual story / before-after set

If a judgment changed, write an additive amendment instead of overwriting the older prediction.
