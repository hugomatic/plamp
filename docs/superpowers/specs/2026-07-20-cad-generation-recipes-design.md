# Versioned CAD Generation Recipes Design

## Goal

Replace the duplicated per-part OpenSCAD generation logic with one local Plamp CAD engine that understands self-describing SCAD files, versioned render recipes, nested presets, scoped variables, reproducible artifacts, and humane diagnostics.

This is Plate 1 of the broader CAD archive and digital-twin direction. It delivers the reusable engine, CLI, artifact manifests, and Plamp8 migration. It does not add asynchronous web generation, Three.js, revision-bundle distribution, hardware onboarding, or robot execution.

## User-facing entry points

The local direct CLI gains a `cad` area:

```text
plamp cad views PART
plamp cad validate PART
plamp cad plan PART [--preset NAME | --view NAME ...]
plamp cad menu PART
plamp cad generate PART [--preset NAME | --view NAME ...]
plamp cad runs [PART]
plamp cad show RUN
plamp cad log RUN ARTIFACT
```

`PART` accepts either an in-repository part name such as `plamp8`, resolving to `things/plamp8/plamp8.scad`, or an explicit SCAD path.

Existing `things/<part>/generate.bash` commands remain executable compatibility wrappers over the same Python implementation. New projects created from `things/3d_template` receive the same thin wrapper. No generation behavior is duplicated in Bash.

The HTTP-oriented `plamp_cli` does not own CAD generation. CAD requires local Git, filesystem, OpenSCAD, and instance-data access, so it belongs to the direct local `plamp` command.

## Canonical view discovery

The OpenSCAD Customizer declaration remains the authoritative ordered list of selectable views:

```scad
view = "assembly"; // [floor, box, top_panel, sub_panel, assembly]
```

The generator always attempts to parse this declaration, including when presets are present. It supplies individual menu choices and validates metadata references.

Fallbacks are intentionally useful:

- With a declared view list, individual view selection and validation are available.
- With only a default `view` assignment, default generation is available but menus explain that no selectable list was declared.
- With neither, default generation still runs once without a `view` override.
- Metadata view keys may describe declared views but do not replace a parseable Customizer list.

## Embedded metadata

SCAD files may include one optional JSON block inside an exact sentinel comment:

```scad
/* generate.json
{
  "default_preset": "split-box",
  "global_variables": {
    "$fn": 64
  },
  "views": {
    "box": {
      "description": "Fused walls-and-floor printable box",
      "variables": {
        "box_coarse_vents": true
      }
    },
    "assembly": {
      "description": "Complete illustrated assembly"
    }
  },
  "presets": {
    "split-box": {
      "description": "Enclosure printed as separate floor and walls",
      "items": [
        "view:floor",
        "view:north_south_walls",
        "view:east_west_walls",
        "view:top_panel",
        "view:sub_panel"
      ]
    },
    "assembly": {
      "description": "Complete illustrated assembly",
      "items": ["view:assembly"]
    }
  }
}
*/
```

The Python standard library extracts the text between `/* generate.json` and the next `*/`, then parses it with `json.loads`. Parse failures report the SCAD path plus JSON-relative line and column. No regular expression attempts to parse nested JSON.

Metadata is optional. A SCAD without metadata remains generatable and browsable through its declared views or implicit default job.

## Views, presets, and render jobs

A view is an OpenSCAD selector value. A preset is an ordered, versioned build recipe containing views and/or other presets.

Preset items use explicit namespaces because a preset and view may share a name:

```json
{
  "items": [
    "view:floor",
    "preset:corner-coupons",
    "view:assembly"
  ]
}
```

Expansion rules:

- Preserve declared item order.
- Permit nested presets to any practical depth.
- Reject unknown view and preset references.
- Detect cycles and report the complete path, such as `all -> tests -> coupons -> all`.
- Move direct `assembly` view selections last; preset authors control preset order explicitly.
- A preset with no `items` produces one job without overriding `view`, allowing variables to configure the SCAD default.

Two synthetic selectors have different meanings:

- `all-views` generates every declared SCAD view once using global and per-view defaults, without preset context.
- `all-presets` expands every declared preset and generates every distinct configured artifact variant.

For `all-presets`, jobs are deduplicated by the complete generation fingerprint rather than by view name. The same view and effective variables render once and retain all preset memberships. The same view with different variables renders as separate variants.

## Variable scopes and precedence

Metadata supports:

- top-level `global_variables`;
- `views.<name>.variables`;
- `presets.<name>.variables` applied to every descendant job; and
- `presets.<name>.view_variables.<view>` applied to matching descendant views.

Runtime selection supports repeatable `--view`, global repeatable `--define`, and per-view repeatable `--view-define`. Exactly one preset may be selected, and preset selection is mutually exclusive with direct view selection.

Effective values resolve from lowest to highest precedence:

```text
SCAD source defaults
global_variables
view variables
outer-to-inner preset variables
outer-to-inner preset view_variables
CLI --define
CLI --view-define
```

JSON strings become quoted OpenSCAD strings; booleans, numbers, lists, and objects are serialized deterministically into valid OpenSCAD expressions. Existing raw `--define NAME=EXPRESSION` remains available for expert CLI use.

## Planning before rendering

`plamp cad validate` parses and validates without invoking OpenSCAD.

`plamp cad plan` expands the selected recipe without invoking OpenSCAD and reports:

- the nested preset tree;
- preset and view descriptions;
- unique render-job count;
- jobs shared by multiple preset paths;
- every view variant and its effective variables;
- artifact names and fingerprints; and
- estimated duration and output size when comparable archived jobs exist.

The plan makes expensive expansion visible before a Raspberry Pi starts rendering many walls. Future web generation must display the same plan before confirmation.

## Version identity

Preset definitions live in the SCAD and are versioned by Git with the geometry they describe. Each run records:

- full source commit and repository-relative SCAD path;
- engraved revision string;
- source content hash;
- embedded metadata snapshot;
- originally selected preset or views;
- fully expanded preset graph;
- effective variables for every job;
- generator version and manifest schema version; and
- OpenSCAD version.

Committed generation continues using an archived source snapshot so later working-tree changes cannot affect the run. Dirty CLI generation requires an explicit honest revision label and records the dirty source content hash. Web generation in the later archive plate will use committed source only unless separately designed otherwise.

## Instance-local artifact archive

New generated data belongs under:

```text
$PLAMP_DATA_DIR/cad/prints/<part>/<run-id>/
```

It is instance data, never automatically added to Git. Existing `things/*/prints/` runs may be recognized as legacy read-only artifacts, but new default generation does not write there.

A run contains:

```text
manifest.json
readme.md
artifacts/<human-variant-name>--<fingerprint>.stl
logs/<human-variant-name>--<fingerprint>.log
```

Preset membership is logical data in the manifest rather than duplicated physical directories. One artifact may belong to several nested preset paths. A one-view preset still produces one STL inside its run archive.

The artifact fingerprint includes source identity, view or implicit-default selection, effective variables, and generator identity. Human-readable variant names distinguish repeated views; the short fingerprint guarantees uniqueness.

The manifest is created before OpenSCAD starts and updated atomically after each state change. Run and job states are `queued`, `running`, `complete`, `failed`, or `interrupted`. Temporary STL names become final only after a successful OpenSCAD exit. Partial and failed runs retain completed artifacts and logs.

## OpenSCAD output and CAD messages

OpenSCAD output streams live to the terminal and into the per-job log. The manifest preserves:

- the exact argv without shell reconstruction;
- start, finish, and elapsed times;
- exit status;
- every `ECHO:` line in order;
- warnings and errors;
- cache and geometry statistics;
- manifold/simple status, vertices, facets, and volumes when reported; and
- output filename and byte size.

Ordinary echoes remain unstructured messages. A generic typed convention may add consumers without making BOM assumptions:

```scad
echo("PLAMP", "bom", ["M3x25", 8, "corner screws"]);
echo("PLAMP", "measure", ["top_stack_h", 25, "mm"]);
echo("PLAMP", "note", ["print_orientation", "floor_down"]);
echo("PLAMP", "robot", ["fixture", x, y, z]);
```

The generator records messages but never executes them. Future BOM, Three.js, onboarding, or explicitly authorized robot consumers interpret their own channels. Unknown channels remain preserved.

## Humane and agent-friendly diagnostics

All validation surfaces share structured diagnostic objects rendered as concise CLI text, JSON, and later web messages. Expected input errors never expose raw Python tracebacks.

Each diagnostic includes a stable code, kind, message, source path, JSON path or SCAD line when available, offending value, relevant declared choices, and a suggested correction or command.

Examples include:

- unknown views and presets with close-name suggestions;
- missing or incomplete Customizer view declarations;
- invalid JSON with accurate line and column;
- cycles with complete expansion paths;
- invalid variable values and conflicting variants;
- unavailable OpenSCAD;
- dirty unversioned source;
- interrupted or failed renders; and
- empty geometry or missing output files.

Context determines severity. A missing view declaration is valid for implicit-default generation, but selecting `--view box` explains that the SCAD exposes no selectable view list and shows the declaration syntax to add.

`--json` exposes the same diagnostics and planning results for agents and scripts. The engine never silently edits SCAD metadata; it supplies explicit fixes.

## Plamp8 recipe migration

Plamp8 receives these initial presets:

- `split-box` (default): `floor`, `north_south_walls`, `east_west_walls`, `top_panel`, `sub_panel`;
- `fuse-box`: `box`, `top_panel`, `sub_panel`;
- `assembly`: the single `assembly` view;
- `component-floorplans`: relay, PSU, and converter footprint views;
- `top-panel-fit`: AC duplex, DC channel, USB-C, and C13 fit-panel views;
- `corner-coupons`: panel fastener test, corner coupon, and wall-corner fastener assembly views;
- `test-fit`: nested component-floorplans, top-panel-fit, and corner-coupons presets;
- synthetic `all-views`; and
- synthetic `all-presets`.

The existing Plamp8 `--box` wrapper option remains a compatibility alias for `--preset fuse-box` during migration.

Other existing part generators move to the shared engine while preserving their current view availability and special variable defaults. Tests cover template-generated wrappers so new projects do not regress into copied generator logic.

## Preset-authoring skill

After the schema and CLI stabilize, create and validate an `authoring-cad-presets` skill. It will guide agents through view discovery, nested recipe design, naming and descriptions, variable scopes, typed echoes, `plamp cad validate`, and mandatory dry planning before expensive generation.

The skill is deferred until the real commands exist so it documents an executable contract rather than a speculative API.

## Explicitly deferred plates

Plate 2 adds the asynchronous Plamp web archive, persistent single-worker queue, Generate button, live status, and artifact browsing over these manifests.

Plate 3 adds revision-addressed hardware bundles, cache distribution, Three.js models and 2D HUD, USB/Pico discovery, peripheral onboarding, scheduling guidance, and any separately authorized physical-machine consumers.

Neither deferred plate changes the Plate 1 manifest and diagnostic contracts without a versioned schema migration.
