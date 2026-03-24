# things

## Local generation note

- `openscad` is installed on this machine and expected to be available on `PATH`
- Use it for local STL generation from scripts like `things/*/generate.bash`
- If a generator fails with `openscad: command not found`, check the shell `PATH` before assuming OpenSCAD is missing

## Basic checklist for 3D thing changes

Use this as a lightweight human checklist when changing a model or its generation scripts.

### Fast checks

- [ ] `generate.bash` still prints a sane suggested command when run with no args
- [ ] paths still make sense after file moves / renames
- [ ] script works when run from the thing directory
- [ ] output goes to a fresh non-existing directory
- [ ] any local assumptions are documented (`PATH`, tools, odd setup details)

### Manual smoke test

Run this intentionally when changing the model or generation flow. Do not treat it like a tiny always-on test.

For `things/plamp_stand`:

```bash
cd /home/hugo/.openclaw/workspace/code/plamp/things/plamp_stand
bash ./test_generate.bash
```

What it verifies:
- renders the latest `plamp_stand.scad`
- generates the STL files for `assembly`, `plate`, and `camera_clip`
- checks that the output files exist and are non-empty

Why manual:
- it depends on `openscad`
- it does real rendering work
- it is slower/heavier than a normal quick script check
