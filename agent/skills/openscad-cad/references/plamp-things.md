# Plamp `things/` CAD Conventions

Use this reference only in the plamp repository's CAD tree.

## Navigation and generation

Systems compose models and products. Each model has one SCAD source and an
adjacent `.cad.json` sidecar; its ordered sets are selected by the SCAD `set`
variable. Products are ordered selections from one or more models.

```bash
plamp cad systems --json
plamp cad models --system plamp --json
plamp cad sets plamp8 --system plamp --json
plamp cad products --system plamp --json
plamp cad validate plamp8 --system plamp --json
plamp cad generate --system plamp --product split-box --json
```

Generate directly for normal work. Use `plan` when an advanced preview of exact
jobs, variables, fingerprints, and product paths is useful; it never invokes
OpenSCAD.

Direct model generation accepts repeatable `--set`, `--all-sets`, `--define
NAME=EXPR`, and `--set-define SET:NAME=EXPR`. CLI expressions are archived
verbatim. With no explicit selection, the system's default product is used.

When more than one system is present, noninteractive commands require
`--system NAME_OR_PATH`. Human interactive navigation offers a numbered choice.

## Model contract

A model SCAD root declares its canonical ordered set list with the OpenSCAD
Customizer syntax:

```scad
set = ""; // [floor, top_panel, assembly]
revision_string = "dev";

if (set == "floor")
    floor_set();
else if (set == "top_panel")
    top_panel_set();
else if (set == "assembly")
    assembly_set();
else
    default_model();
```

Descriptions, printable flags, variables, profiles, and slicing advice live in
the adjacent model sidecar. Product composition lives in a system manifest, not
inside SCAD. Keep printable and assembly modules distinct.

Create and register a paired SCAD/sidecar model with a described template:

```bash
plamp cad templates --json
plamp cad new pump-bracket --system plamp --template flat_plate
```

## Managed runs and source

With no explicit output, generation creates a managed run beneath
`$PLAMP_DATA_DIR/cad/prints/<system>/`. Its manifest records the system and
selection, model source hashes and revisions, product paths, effective values
and provenance, exact OpenSCAD commands, logs, statistics, and artifacts.
Generated meshes use `artifacts/<ARTIFACT_ID>--<REVISION>.stl` inside the run.

```bash
plamp cad runs --json
plamp cad show RUN_ID --json
plamp cad log RUN_ID ARTIFACT_ID --json
```

Clean generation renders archived Git snapshots. Planning may inspect a dirty
model without a revision. Generation requires an honest label such as
`--revision fit-test-1` for dirty source, then archives that working source and
engraves the label. Dirt elsewhere in the repository is irrelevant.

Run archives are instance data. Do not commit generated STL files, manifests,
logs, or archived sources.

## Verification

- Confirm every requested artifact is non-empty and every job has the expected
  status.
- Read complete logs for warnings, errors, missing includes, and geometry
  statistics.
- Verify the archived source and manifest identities.
- Apply the core skill's FDM or laser-cutting checks to the resulting geometry.
