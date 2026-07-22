# Plamp `things/` CAD Conventions

Use this reference only in the plamp repository's `things/` CAD tree.

## Contents

- [Installed Workflow](#installed-workflow)
- [Create a New Part](#create-a-new-part)
- [SCAD View and Generation Contract](#scad-view-and-generation-contract)
- [Managed Runs, Revisions, and Source](#managed-runs-revisions-and-source)
- [Exact Plamp8 Split-Box Example](#exact-plamp8-split-box-example)
- [Archive Verification](#archive-verification)

## Installed Workflow

A part name such as `plamp8` resolves to `things/plamp8/plamp8.scad`. Repository-relative paths work, as do absolute SCAD paths that remain inside the repository. Use the installed interface directly:

| Need | Command |
|---|---|
| Discover views and presets | `plamp cad views PART --json` |
| Validate metadata and references | `plamp cad validate PART --json` |
| Expand jobs without OpenSCAD | `plamp cad plan PART [selection] --json` |
| Render and archive jobs | `plamp cad generate PART [selection] --json` |
| List archived runs | `plamp cad runs [PART] --json` |
| Read a run manifest | `plamp cad show RUN_ID --json` |
| Read one artifact's complete log | `plamp cad log RUN_ID ARTIFACT_ID --json` |

Run `plan` before `generate`. It performs source selection and recipe expansion but never invokes OpenSCAD. Prefer `--json` for agents.

## Create a New Part

Create parts from the repository root. The generated source is
`things/PART/PART.scad` and already contains the required named-module, view,
metadata, and BOM structure:

```bash
plamp cad new --list-templates --json
plamp cad new PART --template TEMPLATE --json
plamp cad validate PART --json
plamp cad plan PART --json
plamp cad generate PART --json
```

Omit `--template` to use the default `cad` template. The command refuses unsafe
names, normalized sibling collisions, and any pre-existing destination.

## SCAD View and Generation Contract

The OpenSCAD Customizer declaration is the canonical ordered view list; its assigned value is the document's default view:

```scad
view = "assembly"; // [floor, walls, top_panel, assembly]
revision_string = "dev";
```

Keep printable and assembly modules distinct. Use descriptive positive and negative modules, then dispatch the declared views explicitly.

Optionally embed generation metadata in the same SCAD file:

```scad
/* generate.json
{
  "default_preset": "split-box",
  "global_variables": {"render_fn": 96},
  "views": {
    "floor": {"description": "Printable floor", "variables": {"vents": true}},
    "walls": {"description": "Printable wall plate"},
    "top_panel": {"description": "Printable top panel"},
    "assembly": {"description": "Complete assembly"}
  },
  "presets": {
    "shell": {
      "items": ["view:floor", "view:walls"],
      "variables": {"wall_t": 3},
      "view_variables": {"walls": {"brim_tabs": true}}
    },
    "split-box": {
      "items": ["preset:shell", "view:top_panel"]
    }
  }
}
*/
```

- Treat `views` as metadata keyed by names already present in the canonical Customizer list. Each entry may provide `description` and `variables`.
- Define named presets with ordered `items`. Use `view:NAME` for a view and `preset:NAME` for a nested preset. A preset may also provide `description`, `variables`, and per-view `view_variables`.
- Use `--preset NAME` for one recipe or repeat `--view NAME` for selected views.
- Use synthetic `--preset all-views` to expand the canonical view list and `--preset all-presets` to expand every named preset. These two reserved selectors must not appear as embedded preset names.
- With no explicit selection, use `default_preset` when present. Otherwise render one job using the SCAD document's assigned default view.
- Parts without metadata remain supported: the Customizer list supplies view discovery and the assigned view supplies the implicit default.
- Run `validate` before rendering. It catches malformed JSON, unknown views or presets, reserved names, invalid metadata shapes, and preset cycles.

Variables use this exact later-wins order:

1. SCAD defaults
2. `global_variables`
3. selected view `variables`
4. outer-to-inner preset `variables`
5. outer-to-inner matching preset `view_variables`
6. repeatable CLI `--define NAME=EXPR` / `-D NAME=EXPR`
7. repeatable CLI `--view-define VIEW:NAME=EXPR`

CLI expressions are archived verbatim. Use them only for intentional OpenSCAD expressions.

## Managed Runs, Revisions, and Source

With no explicit output, `generate` creates:

```text
$PLAMP_DATA_DIR/cad/prints/<part>/<RUN_ID>/
├── manifest.json
├── readme.md
├── source/
├── artifacts/<ARTIFACT_ID>.stl
└── logs/<ARTIFACT_ID>.log
```

The versioned manifest records source identity, metadata and selection snapshots, preset expansion, effective typed and raw variables, exact OpenSCAD commands, job state, timings, sizes, echoes, typed `PLAMP` messages, warnings, errors, and geometry statistics. The per-artifact log retains complete OpenSCAD output.

Use these exact diagnostics commands, replacing identifiers with values returned by `generate`, `runs`, or `show`:

```bash
plamp cad runs PART --json
plamp cad show RUN_ID --json
plamp cad log RUN_ID ARTIFACT_ID --json
```

Read `jobs[].artifact_id` from the manifest returned by `show` before requesting a log.

For clean source, generation renders an archived Git snapshot of the entire part directory so relative `use` and `include` paths remain reproducible. Without `--revision`, it archives the latest commit touching the part. If `--revision` resolves to a Git commit, it archives that historical part snapshot and engraves the supplied revision. If `--revision` is a non-Git label, it engraves that label while archiving the latest commit touching the part. The manifest records both the archived commit and engraved revision.

Planning may inspect a dirty part without a revision label. Generation refuses dirty part source until supplied an honest label such as `--revision fit-test-1`; it then copies the current part directory into the run's source snapshot, records it as dirty, and engraves the label. Dirtiness elsewhere in the repository does not make the part dirty.

Run archives are instance data, not source. Do not add generated STL, manifest, log, or archived-source output to Git.

## Exact Plamp8 Split-Box Example

This sequence covers discovery, validation, a dry plan that does not require OpenSCAD, managed generation, and archived diagnostics:

```bash
plamp cad views plamp8 --json
plamp cad validate plamp8 --json
plamp cad plan plamp8 --preset split-box --json
plamp cad generate plamp8 --preset split-box --json
plamp cad runs plamp8 --json
plamp cad show RUN_ID --json
plamp cad log RUN_ID ARTIFACT_ID --json
```

Plamp8 declares `split-box` as its default preset. It expands, in order, `floor`, `north_south_walls`, `east_west_walls`, `top_panel`, and `sub_panel`. Replace `RUN_ID` with the generated/listed run and `ARTIFACT_ID` with one `jobs[].artifact_id` from `show`. On dirty Plamp8 source, add the same honest `--revision LABEL` to `plan` when documenting intent and to `generate` when rendering.

## Archive Verification

- For a successful run, verify every job is complete with its expected non-empty artifact. For failed or partial runs, correlate artifacts with each job status; failed or queued jobs may have none. Always verify the archived source snapshot.
- Read each complete artifact log, not only console summaries; investigate missing includes, warnings, errors, empty geometry, and unexpected statistics.
- Apply the core skill's FDM or laser-cutting verification to the resulting geometry.
