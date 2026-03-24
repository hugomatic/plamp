# CHECKLIST

Use this as a lightweight checklist for changes in this repo. Not every item applies every time.

## General

- [ ] The thing still works from the directory where a human would normally run it.
- [ ] Paths still make sense after file moves or renames.
- [ ] Commands and examples in docs still match reality.
- [ ] Output locations are sensible and safe.
- [ ] Scripts that create output use a fresh non-existing target directory when that is the expected contract.
- [ ] Local assumptions are documented (`PATH`, tools, machine-specific setup, odd gotchas).
- [ ] Required host-side tools are actually available from a normal shell (`command -v ...`), not just installed somewhere.
- [ ] If a change is expensive to validate, there is still a clear manual check for it.

## Script / generation changes

- [ ] `generate.bash` (or equivalent) still prints a sane suggested command when run with no args.
- [ ] The suggested command actually works when copied and run.
- [ ] Generated files are easy to find afterward.
- [ ] Logs or generated readme output are useful enough for a human to inspect failures.

## Example manual check: `things/plamp_stand`

Run this intentionally when changing the model or generation flow:

```bash
cd /home/hugo/.openclaw/workspace/code/plamp/things/plamp_stand
bash ./check_generates_stl_files_from_scad.bash
```

What it checks:
- renders the latest `plamp_stand.scad`
- generates STL files for `assembly`, `plate`, and `camera_clip`
- verifies the generated files and `readme.md` exist and are non-empty

Why this is manual:
- it depends on `openscad`
- it does real rendering work
- it is slower/heavier than a quick script sanity check
