# plamp_stand

Simple printed stand / camera mount parts for the plamp setup.

![plamp stand reference](./doc/stand.jpg)

## Files

- `plamp_stand.scad` - OpenSCAD source
- `check_generates_stl_files_from_scad.bash` - manual smoke test

## Generate

From the repository root after `source ./setup.sh`:

```bash
plamp cad validate plamp_stand
plamp cad plan plamp_stand --preset all-views-default
plamp cad generate plamp_stand --preset all-views-default
```

If you are changing the model or generation flow, run the manual check from the repo checklist:

```bash
cd /path/to/plamp/things/plamp_stand
bash ./check_generates_stl_files_from_scad.bash
```

## Reference image

A local reference image may exist at:

- `./doc/stand.jpg`

If that file is missing in GitHub or another checkout, treat it as optional documentation, not as part of the generation contract.
The source of truth for this part is the SCAD file and its embedded generation metadata.
