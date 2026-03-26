# plamp_stand

Simple printed stand / camera mount parts for the plamp setup.

![plamp stand reference](./doc/stand.jpg)

## Files

- `plamp_stand.scad` - OpenSCAD source
- `generate.bash` - render helper
- `check_generates_stl_files_from_scad.bash` - manual smoke test

## Generate

From this directory:

```bash
bash ./generate.bash
```

If you are changing the model or generation flow, run the manual check from the repo checklist:

```bash
cd /home/hugo/.openclaw/workspace/code/plamp/things/plamp_stand
bash ./check_generates_stl_files_from_scad.bash
```

## Reference image

A local reference image may exist at:

- `./doc/stand.jpg`

If that file is missing in GitHub or another checkout, treat it as optional documentation, not as part of the generation contract.
The source of truth for this part is the SCAD file plus the generation/check scripts.
