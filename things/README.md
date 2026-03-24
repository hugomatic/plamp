# things

## Local generation note

- `openscad` is installed on this machine and expected to be available on `PATH`
- Use it for local STL generation from scripts like `things/*/generate.bash`
- If a generator fails with `openscad: command not found`, check the shell `PATH` before assuming OpenSCAD is missing

## Basic checklist

Use this as a lightweight human checklist for changes in this repo. Not every item applies every time.

### General checks

- [ ] the thing still works from the directory where a human would normally run it
- [ ] paths still make sense after file moves / renames
- [ ] commands and examples in docs still match reality
- [ ] output locations are sensible and safe
- [ ] scripts that create output use a fresh non-existing target directory when that is the expected contract
- [ ] local assumptions are documented (`PATH`, tools, machine-specific setup, odd gotchas)
- [ ] if a change is expensive to validate, there is still a clear manual smoke test

### Script / generation checks

- [ ] `generate.bash` (or equivalent script) still prints a sane suggested command when run with no args
- [ ] the suggested command actually works when copied and run
- [ ] generated files are easy to find afterward
- [ ] logs or readme output are useful enough for a human to inspect failures

### Manual smoke tests

Keep heavier tests available, but do not run them all the time.

Example: `things/plamp_stand`

```bash
cd /home/hugo/.openclaw/workspace/code/plamp/things/plamp_stand
bash ./test_generate.bash
```

What that specific smoke test verifies:
- renders the latest `plamp_stand.scad`
- generates the STL files for `assembly`, `plate`, and `camera_clip`
- checks that the output files exist and are non-empty

Why manual:
- it depends on `openscad`
- it does real rendering work
- it is slower/heavier than a normal quick script check
