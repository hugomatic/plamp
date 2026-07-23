# CAD Systems, Products, Models, and Manufacturing Metadata

**Date:** 2026-07-23

## Goal

Replace the current part/view/preset vocabulary with a CAD structure that matches
how humans design and manufacture complete systems:

- a **system** catalogs reusable libraries, models, profiles, and a nested product
  tree;
- a **product** combines model sets and other products into something a human
  intends to manufacture, inspect, or maintain;
- a **model** is one coherent OpenSCAD source graph;
- a **set** is the smallest selectable unit in a model and arranges one or more
  physical parts;
- a **part** is a physical component implemented as a named OpenSCAD module;
- a **feature** is reusable constructive or subtractive geometry used by parts;
  and
- an **artifact** is a generated geometry file, preview, log, manifest, README,
  or other run output.

The design keeps OpenSCAD files ordinary and directly usable. Plamp-specific
descriptions and manufacturing metadata move into adjacent JSON sidecars and a
system manifest. Native OpenSCAD parameter presets are not part of this model.

This is a pre-1.0 vocabulary and schema replacement. The implementation removes
the old names rather than carrying compatibility aliases.

## Why the Current Vocabulary Fails

The current CLI calls a root SCAD directory a `part`, although `plamp8.scad`
contains many physical parts. A current `view` may arrange several parts, such
as north and south walls. A current `preset` is actually an ordered generation
composition, while OpenSCAD already uses “preset” for saved parameter values.

The current embedded `generate.json` also mixes four responsibilities:

- the SCAD model's selectable geometry;
- human descriptions;
- grouping and orchestration;
- generation-variable defaults.

That structure cannot describe a complete Plamp installation containing the
controller enclosure, Raspberry Pi holder, and camera holder without pretending
they belong in one SCAD file.

## Terminology and Ownership

### System

A system is the top-level CAD catalog for one repository or independently
versioned design workspace. It owns:

- model names and model-sidecar paths;
- declared shared libraries;
- named printer, nozzle, material, and quality profiles;
- named products and their nesting; and
- the default product, when one exists.

Only a system may compose multiple models. A system is not itself a generated
geometry object.

### Product

A product is an ordered list of model/set references and/or nested product
references. It may contain multiple sets from one model, sets from several
models, or only one set. Allowing a one-model product is useful for replacement
parts, validation suites, and migration of current presets; the important rule
is that cross-model composition occurs only at the product layer.

Products may carry variables, slicing policy, descriptions, and reference-local
overrides. Product nesting is acyclic and preserves declared order.

Examples include:

- `complete`: enclosure, Raspberry Pi holder, and camera holder;
- `split-box`: the printable Plamp8 enclosure sets;
- `panels`: replacement top and sub-panel sets;
- `fit-and-function`: component, connector, and fastener validation sets; and
- `assembly`: illustrated non-printable assembly sets.

### Model

A model is one root SCAD file plus its local source and asset graph. The root may
`use`, `include`, or `import` other files. A model is portable as a folder and has
an optional adjacent Plamp model sidecar.

The model owns its set selector, parts, features, and canonical SCAD variable
definitions. A model does not know which other models are manufactured with it.

### Set

A set is the smallest public CAD selection. It is an ordinary top-level SCAD
Customizer variable named `set`:

```scad
set = ""; // [floor, panels, fit-and-function, assembly]
```

The assignment and its ordered Customizer choices are authoritative. Plamp reads
that declaration. The assigned empty string is the default even though it is not
repeated as a Customizer choice. A named set arranges one or more parts for one
OpenSCAD invocation. A set may contain a single part. Parts are not independently
selectable through the public Plamp CAD interface.

The empty set is valid and means normal OpenSCAD top-level behavior. A model
without a set declaration also remains generatable as one implicit empty-set
job.

One set invocation produces one primary geometry artifact. That artifact may
contain several disconnected printable pieces. Products produce several primary
geometry artifacts by expanding to several set invocations.

### Part

A part is a named OpenSCAD module representing a physical component. The normal
Plamp convention is a difference between positive and negative geometry:

```scad
module top_panel_part() {
    difference() {
        top_panel_positive();
        top_panel_negative();
    }
}
```

This is a source convention, not a parser contract. Plamp does not attempt to
infer physical parts by parsing arbitrary OpenSCAD module bodies.

### Feature and Library Feature

A feature is a reusable module that contributes constructive or subtractive
geometry, such as a countersink, nut catcher, rib, label pocket, or connector
cutout. A library feature is a feature exported for reuse across models. Private
modules that are neither parts nor reusable features are simply helpers.

Libraries may also expose functions and constants. Libraries do not own sets or
products and are not generated directly.

### Artifact, Job, Plan, and Run

- A **job** is one resolved model/set invocation with effective CAD variables and
  manufacturing advice.
- A **plan** is the deterministic ordered expansion of a model selection or
  product into jobs.
- A **run** executes a plan and owns its archived inputs and outputs.
- An **artifact** is any generated file. Geometry artifacts, logs, manifests,
  READMEs, and previews remain distinct artifact types.

Existing source archiving, fingerprints, readable run IDs, regeneration,
cataloging, and log behavior remain. Fingerprints use the new system/product/
model/set identity and effective geometry variables.

## File Layout

The default repository layout is:

```text
cad/
├── plamp.system.cad.json
├── workshop-jigs.system.cad.json
└── profiles/
    ├── bambu-x1c.json
    ├── nozzle-0.4mm.json
    ├── petg.json
    └── draft.json

things/
├── plamp8/
│   ├── plamp8.scad
│   ├── plamp8.cad.json
│   └── local-library/
├── rpi-holder/
│   ├── rpi-holder.scad
│   └── rpi-holder.cad.json
└── camera-holder/
    ├── camera-holder.scad
    └── camera-holder.cad.json
```

The names are defaults, not requirements that source folders be named
`things`. The system manifest resolves model sidecars by repository-relative
path. A sidecar resolves its root SCAD file and local paths relative to the
sidecar directory.

By default, `plamp cad` discovers every `*.system.cad.json` file directly inside
the repository's `cad/` directory. Multiple system manifests may live beside
one another and may reference the same model sidecars. Discovery is not
recursive: a manifest outside that directory is selected by explicit path rather
than being silently folded into the repository catalog.

Every system-aware command accepts `--system SYSTEM`, where `SYSTEM` is either a
unique declared system name or an explicit manifest path. An explicit path may
point outside the default `cad/` directory when normal path authorization rules
allow it. Commands record the resolved manifest path and content hash. Plamp
never combines system manifests into an implicit larger system.

When `--system` is omitted, one discovered system is selected automatically. If
several exist, an interactive terminal offers a system menu; a non-interactive
command fails with the discovered names and an exact `--system` example. A local
default system may remove the prompt, but the command prints the selected system
and the run manifest records it.

SCAD files contain no embedded `generate.json`. Model folders remain portable
because their sidecar travels with the source folder.

## Clean OpenSCAD Contract

The root SCAD file remains directly usable in OpenSCAD:

```scad
render_fn = 96;
render_text = true;
$fn = render_fn;

set = ""; // ["", floor, top_panel, sub_panel, assembly]

if (set == "floor")
    floor_set();
else if (set == "top_panel")
    top_panel_set();
else if (set == "sub_panel")
    sub_panel_set();
else if (set == "assembly")
    assembly_set();
else
    default_model();
```

The OpenSCAD Customizer exposes `set` and all normal model variables. A human can
select a set in OpenSCAD or let the empty set render normal top-level geometry.

Plamp deliberately ignores OpenSCAD native parameter preset files and does not
invoke `openscad -p ... -P ...`. Effective values are resolved by Plamp and
passed as explicit `-D NAME=VALUE` arguments. Native presets remain available to
someone using OpenSCAD independently, but they have no Plamp generation meaning.

## Model Sidecar

The adjacent sidecar provides descriptions and Plamp manufacturing metadata
without redefining geometry:

```json
{
  "schema": "plamp-cad-model/1",
  "name": "plamp8",
  "source": "plamp8.scad",
  "description": "Plamp8 controller enclosure",
  "sets": {
    "": {
      "description": "Normal OpenSCAD model output"
    },
    "floor": {
      "description": "Printable enclosure floor",
      "slicing": {
        "orientation": "as-exported",
        "supports": "forbidden"
      }
    },
    "top_panel": {
      "description": "Printable top panel",
      "slicing": {
        "orientation": "as-exported",
        "ironing": "recommended",
        "supports": "forbidden"
      }
    },
    "assembly": {
      "description": "Complete illustrated enclosure assembly",
      "printable": false
    }
  }
}
```

The sidecar is optional. Without one, Plamp lists the Customizer set names and
generates them without descriptions or structured recommendations.

When a sidecar exists:

- its source path must remain inside the model folder;
- every sidecar set must exist in the authoritative SCAD set choices, including
  `""` when described;
- every declared SCAD set need not have metadata, but validation reports missing
  descriptions as an advisory diagnostic;
- unknown metadata keys fail schema validation; and
- the sidecar may assign model and set defaults but may not introduce a set that
  the SCAD source cannot select.

Model- and set-level `variables`, when present, are Plamp generation overrides.
They do not redefine a variable or its canonical SCAD default. A sidecar should
omit assignments that merely repeat the source value.

Canonical set descriptions live only in the model sidecar. Product entries may
add contextual notes but do not redefine them.

## System and Product Manifest

The system manifest catalogs models, libraries, profiles, and products:

```json
{
  "schema": "plamp-cad-system/1",
  "name": "plamp",
  "description": "Plamp hydroponics automation hardware",
  "models": {
    "plamp8": "things/plamp8/plamp8.cad.json",
    "rpi-holder": "things/rpi-holder/rpi-holder.cad.json",
    "camera-holder": "things/camera-holder/camera-holder.cad.json"
  },
  "libraries": {
    "BOSL2": {
      "path": "vendor/BOSL2",
      "license": "BSD-2-Clause"
    }
  },
  "profiles": {
    "bambu-x1c": "cad/profiles/bambu-x1c.json",
    "nozzle-0.4mm": "cad/profiles/nozzle-0.4mm.json",
    "petg": "cad/profiles/petg.json",
    "draft": "cad/profiles/draft.json"
  },
  "default_product": "complete",
  "products": {
    "component-floorplans": {
      "description": "Component mounting footprint tests",
      "items": [
        {"model": "plamp8", "set": "relay_footprint"},
        {"model": "plamp8", "set": "psu_footprint"},
        {"model": "plamp8", "set": "converter_footprint"}
      ]
    },
    "top-panel-fit": {
      "description": "Top-panel connector fit tests",
      "items": [
        {"model": "plamp8", "set": "ac_duplex_panel"},
        {"model": "plamp8", "set": "dc_connector_panel"},
        {"model": "plamp8", "set": "usb_c_panel"},
        {"model": "plamp8", "set": "c13_panel"}
      ]
    },
    "corner-coupons": {
      "description": "Panel and wall corner fastener tests",
      "items": [
        {"model": "plamp8", "set": "panel_corner_fastener_test"},
        {"model": "plamp8", "set": "corner_coupon"},
        {"model": "plamp8", "set": "wall_corner_fastener_assembly"}
      ]
    },
    "split-box": {
      "description": "Printable Plamp8 enclosure as separate pieces",
      "items": [
        {"model": "plamp8", "set": "floor"},
        {"model": "plamp8", "set": "north_south_walls"},
        {"model": "plamp8", "set": "east_west_walls"},
        {"model": "plamp8", "set": "top_panel"},
        {"model": "plamp8", "set": "sub_panel"}
      ]
    },
    "fit-and-function": {
      "description": "Component, connector, and fastener validation",
      "items": [
        {"product": "component-floorplans"},
        {"product": "top-panel-fit"},
        {"product": "corner-coupons"}
      ]
    },
    "complete": {
      "description": "Complete Plamp hardware",
      "items": [
        {"product": "split-box"},
        {"model": "rpi-holder", "set": "standard"},
        {"model": "camera-holder", "set": "wall-mount"}
      ]
    }
  }
}
```

This manifest example shows the intended end state after the Raspberry Pi and
camera holder models exist. The initial repository manifest must list only model
paths that are present and valid; it may use `split-box` as its default product
until `complete` can resolve. Missing future models are not represented by
placeholders that weaken validation.

A product item contains exactly one of `product` or `model` plus `set`. It may
also contain:

- `description` or `note` for product-local context;
- `variant` when the same set appears with different effective values;
- `variables` for that reference;
- `slicing` requirements or recommendations; and
- `profiles` to add profiles for that subtree.

Sibling items that directly reference the same model/set with different item
assignments must provide distinct `variant` labels. The label is part of the
human artifact identity and product path, but not the geometry fingerprint;
identical geometry can still be reused across variants.

Product expansion:

- preserves item order;
- permits arbitrary practical nesting depth;
- rejects cycles with the complete product path;
- permits repeated model/set references with different variables;
- deduplicates identical resolved geometry jobs by complete fingerprint while
  retaining every product-membership path; and
- does not require a product to span more than one model.

## Variable Definitions and Assignments

The SCAD source owns variable definitions, canonical values, Customizer widgets,
and allowed-value comments:

```scad
wall_t = 2.4;          // [1.6:0.2:4]
hole_clearance = 0.25; // [0:0.05:0.8]
render_fn = 96;        // [12:4:128]
```

External files assign values; they do not duplicate a complete variable schema.
Plamp passes only resolved assignments as `-D` expressions. The system records
typed values and preserves explicitly authorized raw OpenSCAD expressions using
the existing raw-define contract.

For one leaf job, low-to-high precedence is:

1. SCAD source defaults;
2. model-sidecar variables;
3. set-sidecar variables;
4. selected profiles in declared and command-line order;
5. product layers from the deepest product outward to the explicitly selected
   top-level product; and
6. explicit CLI overrides.

A product layer applies the product's own `variables`, then the variables on the
item by which its parent selected that product or leaf set. Therefore an item
override is local to that item and wins over variables declared directly on the
same product. As resolution moves outward, the parent product and its item
override may intentionally replace a child value. This makes the selected
top-level product the final structural authority before the CLI.

For example, if `complete` includes `split-box`, and `split-box` includes the
`top_panel` set, the job resolves in this order:

```text
SCAD -> model -> top_panel set -> profiles
     -> split-box -> split-box's top_panel item
     -> complete -> complete's split-box item -> CLI
```

Product policy therefore overrides reusable model/set/profile defaults, and a
reference-local value overrides its containing product for that subtree. The
manifest records each contributing layer and the winning value with provenance.

No separate `configuration` object exists. A configuration would merely be
another variable container; products, scoped assignments, and profiles already
provide the required structure.

## Orthogonal Manufacturing Profiles

Profiles describe how and where geometry is manufactured rather than what the
product contains. The initial profile kinds are:

- `printer`: build volume and printer-specific calibration;
- `nozzle`: nozzle diameter and nozzle-dependent limits;
- `material`: shrinkage, fit compensation, and material guidance; and
- `quality`: draft/production geometry quality and slicing preferences.

Profiles are composable ordered overlays. They may contribute CAD values and
slicing metadata:

```json
{
  "schema": "plamp-cad-profile/1",
  "name": "petg",
  "kind": "material",
  "cad": {
    "hole_clearance": 0.35,
    "press_fit_clearance": 0.20
  },
  "slicing": {
    "material": "PETG",
    "ironing": "discouraged"
  }
}
```

Profile names and content hashes are part of run provenance. Profile CAD values
affect geometry fingerprints. Slicing-only changes do not invalidate an existing
geometry artifact; they change the manufacturing metadata fingerprint and
generated README.

The profile list for a leaf job is assembled in this order: configured local
defaults, profiles on the selected top-level product, profiles encountered on
product and item references while walking from root to leaf, profiles on the
model/set selection, and explicit command-line profiles. This establishes a
deterministic list before the variable precedence rules apply it.

System profiles may be versioned in the repository. Instance-local profiles and
the human's default printer/material selection live under `PLAMP_DATA_DIR` and
are not committed. System and local profile IDs occupy separate namespaces,
such as `system:petg` and `local:my-petg`, so workstation data cannot silently
shadow a versioned profile.

A normal human command uses configured local default profiles and prints which
ones were selected. Each repeated `--profile` appends after those defaults;
later profiles win scalar conflicts. `--no-default-profiles` disables the local
defaults for a fully explicit run. CLI variable overrides remain final.

Profiles should use separate `cad`, `slicing`, and `machine` namespaces where
possible. A profile does not silently weaken a hard product/set manufacturing
constraint.

## Slicing and Manufacturing Metadata

Slicing metadata starts as portable structured advice, not slicer automation.
The canonical data is stored in sidecars, products, profiles, and run manifests.
Every run renders the resolved advice into its human README.

Initial portable keys include:

- `orientation`: `as-exported` or a human instruction;
- `supports`: `required`, `recommended`, `optional`, `discouraged`, or
  `forbidden`;
- `support_style`: portable advice such as `build-plate-only`;
- `ironing`: the same recommendation vocabulary;
- `material`;
- `layer_height` or maximum layer height;
- minimum wall/perimeter count;
- brim/adhesion advice; and
- free-form ordered notes.

Example README output:

```text
top_panel

Recommended slicing:
- Use the exported orientation.
- Enable ironing.
- Do not generate supports.
- Keep the engraved face upward.
```

Requirements and preferences are distinct. Conflicting hard requirements fail
planning with provenance rather than silently choosing one. Printer profiles may
refine recommendations but cannot weaken `required` or `forbidden` constraints.

The first implementation does not emit BambuStudio, PrusaSlicer, Cura, or 3MF
settings. Later adapters may translate portable metadata into slicer-specific
profiles. Core metadata must not begin with vendor field names.

When parts inside one set need incompatible object-specific slicing policy, the
model should expose separate sets/artifacts, or a later multi-object 3MF design
must preserve object identity. A plain STL containing disconnected shells is not
treated as sufficient object-level policy transport.

## Libraries and Reproducible Dependency Staging

OpenSCAD source-code dependencies use `use <...>` and `include <...>`; geometry
assets use `import(...)`. Generation must stage both kinds. OpenSCAD resolves
non-absolute library references relative to the calling SCAD file, then declared
library paths, user/built-in library locations, and installation locations.
Relying on the workstation's unresolved library search path would make archived
runs non-reproducible.

The current generator already archives the complete local model folder. The new
dependency flow is:

1. Resolve the selected model source at the requested Git revision or explicitly
   labelled dirty working tree.
2. Ask OpenSCAD to produce its make-style dependency file with `-d` for a cheap
   dependency-discovery pass using the source environment.
3. Resolve and classify every transitive source and imported asset.
4. Keep model-local files through the existing complete-folder snapshot.
5. Archive repository-local dependencies from the same Git revision, never from
   the unrelated current working tree.
6. Copy declared external/shared and referenced OpenSCAD installation libraries
   into the run staging directory while preserving each library root and
   internal relative paths.
7. Copy external imported assets into deterministic staged roots.
8. Invoke the actual render with a sanitized `OPENSCADPATH` containing only the
   staged library roots. The render must not consult live user or installation
   library directories.
9. Produce and compare a second dependency file from the staged render. Any
   unresolved, escaped, or newly host-resolved dependency fails the job.

The staged archive records for each dependency:

- logical library or asset name;
- classification: model-local, repository-local, declared shared, built-in, or
  imported asset;
- archive-relative path;
- content hash;
- Git origin/revision when known;
- license metadata when declared; and
- the OpenSCAD version and effective sanitized library path.

Absolute paths outside approved roots, unsafe symlinks, missing dependencies,
cycles that OpenSCAD cannot resolve, and undeclared shared libraries fail with
actionable diagnostics.

A shared library such as BOSL2 can be declared once by the system and then used
by models for illustrated screws, nuts, washers, threads, and other assembly
context. The first implementation enables deterministic library use; converting
existing Plamp8 hand-written fastener illustrations to BOSL2 is separate CAD
work and is not required by this migration.

## CLI Contract

The human-facing discovery commands become:

```bash
plamp cad systems
plamp cad models --system plamp
plamp cad sets plamp8 --system plamp
plamp cad products --system plamp
plamp cad profiles --system plamp
plamp cad libraries --system plamp
plamp cad templates
```

`systems` lists every discovered system with its declared name, description,
manifest path, and default product. `models` lists every model registered by the
selected system with its model ID, description, sidecar path, and root SCAD
path. `sets MODEL` lists every authoritative SCAD set for that model, including
the empty/default set, with its description, printable status, and source model.
Descriptions appear in the default human output as well as interactive and JSON
output. No system, model, or set may be reachable for generation while absent
from the corresponding navigation command.

Stable navigation IDs are the declared system name, the model key inside that
system, and the SCAD set value. Invalid discovered manifests or broken catalog
entries remain visible with an invalid status and diagnostic instead of
silently disappearing; they cannot be selected for generation until repaired.
A valid entry without an optional description displays `(no description)` and
produces the existing advisory diagnostic rather than leaving an unlabeled row.

All discovery commands support the same human-readable and `--json` forms. JSON
rows contain explicit `kind`, stable ID, parent system/model IDs, description,
and source path so callers can navigate without parsing display text.

The simplest planning and generation commands use the system's declared default
product:

```bash
plamp cad plan
plamp cad generate
plamp cad generate --system plamp
```

They print the selected product before doing work. If the system has no default
product, the interactive terminal offers the product menu and a non-interactive
invocation fails with a command showing how to select `--product`.

Direct model generation is the advanced path:

```bash
plamp cad plan plamp8 --set top_panel
plamp cad generate plamp8 --set top_panel
plamp cad generate plamp8 --system plamp
```

Omitting `--set` selects the model's empty/default set. Product generation is
explicit:

```bash
plamp cad plan --product complete
plamp cad generate --product complete
plamp cad generate --product fit-and-function --profile draft
```

Profile IDs may be written without their namespace when exactly one profile with
that short name is visible. Ambiguity is an error that lists the qualified IDs.

`plan` remains the read-only expansion and validation surface. `generate`
performs the same planning internally before rendering; humans do not need to
run `plan` first.

The interactive menu starts with system selection when necessary, then lists
that system's models and products in separate sections. Selecting a model opens
its complete set list. Descriptions and stable IDs are shown at every level;
back-navigation never discards the selected system. Human output remains the
default, with `--json` for machines.

The migration removes:

- `plamp cad views` in favor of `plamp cad sets`;
- `--view` and `--view-define` in favor of `--set` and `--set-define`;
- `--preset` and all synthetic presets;
- `plamp cad new --list-templates` in favor of `plamp cad templates`;
- the embedded `generate.json` block; and
- the public word `part` for root models.

There are no compatibility aliases before 1.0. Diagnostics show the replacement
command when detecting an obsolete invocation.

## CAD Scaffolding and Template Selection

`plamp cad new` always supports explicit template selection:

```bash
plamp cad templates
plamp cad new pump-bracket --template flat_plate --system plamp
```

`templates` lists every available scaffold template with its stable name,
description, source SCAD path, and the files it will create. The initial names
remain `cad`, `flat_plate`, and `positive_negative`. Template descriptions live
in adjacent template sidecars, not embedded SCAD JSON.

When `--template` is omitted in an interactive terminal, `new` presents the
described template list with `cad` marked as the recommended default; pressing
Enter selects it. A non-interactive invocation uses `cad` and prints that choice.
An unknown template fails before mutation and lists the available names plus the
exact `plamp cad templates` command.

Each template is a SCAD-and-sidecar pair. Scaffolding substitutes the new model
identifier in both files—for example, `flat_plate.scad` plus
`flat_plate.cad.json` produces `<model>/<model>.scad` plus
`<model>/<model>.cad.json`. The selected template name and created paths are
reported in human and JSON creation output.

New models are registered in the selected system so they immediately appear in
`plamp cad models` and their sets appear in `plamp cad sets MODEL`. `--system`
uses the same name/path resolution as generation; one system is automatic and
multiple systems trigger the normal interactive choice or non-interactive
diagnostic. Creating the model folder, sidecar, and system entry is atomic: a
validation or write failure leaves none of them partially published.

## Plamp8 Migration

The existing Plamp8 root becomes model `plamp8`. Its current `view` Customizer
variable becomes `set`, preserving the individual ordered selector values as
sets. The adjacent `plamp8.cad.json` receives their descriptions and slicing
guidance.

Current presets migrate into system products:

| Current preset | New product |
| --- | --- |
| `split-box` | `split-box` |
| `fuse-box` | `fuse-box` |
| `panels` | `panels` |
| `assembly` | `assembly` |
| `component-floorplans` | `component-floorplans` |
| `top-panel-fit` | `top-panel-fit` |
| `corner-coupons` | `corner-coupons` |
| `test-fit` | `fit-and-function` |

`fit-and-function` nests the three validation products. Products may initially
reference only the Plamp8 model; later the complete Plamp system product adds
the Raspberry Pi holder and camera holder models without changing Plamp8 SCAD.

The former synthetic `all-views` behavior becomes the direct-model option
`--all-sets`, which expands every named set in SCAD order and excludes the empty
default set unless it is the model's only set. There is no `all-products`
operation: products may overlap and nest, so generating all of them would create
surprising duplicates. A human selects a product explicitly.

## Repository-Wide SCAD Migration

The vocabulary replacement is atomic across the repository. It does not migrate
only Plamp8 while leaving other root models or scaffolds on `view`, embedded
`generate.json`, and preset semantics.

The current migration inventory is:

| SCAD source | Classification | Required migration |
| --- | --- | --- |
| `things/plamp8/plamp8.scad` | model root | `view` to `set`; sidecar; current presets to products |
| `things/iharvest_cover/iharvest_cover.scad` | model root | `view` to `set`; sidecar; all-views preset removed |
| `things/plamp_stand/plamp_stand.scad` | model root | `view` to `set`; sidecar; all-views preset removed |
| `things/3d_template/cad.scad` | scaffold root | emit `set`; emit a sidecar; no embedded JSON |
| `things/3d_template/scad/flat_plate.scad` | scaffold variant | emit `set`; emit sidecar metadata when selected |
| `things/3d_template/scad/positive_negative.scad` | scaffold variant | emit `set`; emit sidecar metadata when selected |

Every repository `.scad` file is classified during implementation as one of:

- a model root, which must use the new set contract and be registered in the
  system catalog;
- a scaffold root or variant, which must generate a compliant model and sidecar;
  or
- a library/helper source, which must not embed model selection or product
  metadata.

Validation and tests scan the repository so a future committed SCAD file cannot
quietly reintroduce `view`, embedded `generate.json`, or Plamp preset metadata.
Library/helper files do not need a `set` variable because they are not directly
generated.

## Validation and Diagnostics

Validation is layered and read-only:

### Model validation

- root SCAD exists and stays inside the model folder;
- set declaration is parseable and ordered;
- set names are unique and safe;
- sidecar schema is valid;
- sidecar set keys reference declared SCAD sets;
- SCAD remains usable without the sidecar; and
- variables serialize as valid OpenSCAD values.

### System validation

- discovered system filenames match `*.system.cad.json`;
- each manifest's declared name is non-empty and unique within its discovery
  directory;
- model, profile, and library paths are repository-relative or explicitly
  authorized external sources;
- names are unique within their namespaces;
- product references resolve;
- product nesting is acyclic;
- model/set references exist;
- profile kinds and content are valid;
- hard manufacturing constraints do not conflict; and
- every expanded job has a stable distinguishable artifact identity.

### Generation validation

- source revision and dirty-label rules remain honest;
- dependencies resolve and stage without escape;
- staged dependency closure matches discovery closure;
- printable sets produce non-empty geometry;
- non-printable sets are not accidentally exported as manufacturing STL;
- OpenSCAD warnings/errors and geometry statistics remain archived; and
- final manifests contain complete value, profile, dependency, and product-path
  provenance.

Diagnostics retain stable codes, concise human text, structured JSON, source
locations, offending values, available choices, close-name suggestions, and a
concrete corrective command when possible.

## Prior Art and Deliberate Differences

The vocabulary borrows familiar boundaries without copying another CAD
application's object model:

- SolidWorks separates physical parts, assemblies, and reusable features. Plamp
  keeps those meanings, but calls a manufacturing selection a set and keeps
  variable overlays outside the part hierarchy.
- FreeCAD distinguishes documents, bodies/parts, and assemblies. Plamp's model
  similarly owns one coherent source graph, while products handle composition
  across model graphs.
- Blender distinguishes source objects from collections, scenes, and linked
  libraries. Plamp borrows explicit library provenance and nested composition,
  but avoids `collection` because it says nothing about manufacturing intent.
- OpenSCAD remains the geometry engine and its
  [Customizer](https://en.wikibooks.org/wiki/OpenSCAD_User_Manual/Customizer)
  remains the canonical variable/set declaration surface. Plamp adds
  orchestration and provenance; it does not try to turn OpenSCAD modules into an
  inferred feature tree.

The terms `system`, `product`, `model`, `set`, `part`, and `feature` are therefore
domain choices, not aliases for one application's internal classes.

## Manifest and README Provenance

Each job manifest adds:

- system identity, resolved manifest path, and manifest hash;
- selected top-level product or direct model selection;
- complete nested product membership paths;
- model and set identity;
- model-sidecar and source hashes;
- resolved CAD variables with source-layer provenance;
- selected profile names, kinds, and hashes;
- resolved slicing/manufacturing metadata;
- dependency inventory and hashes;
- geometry fingerprint;
- manufacturing-metadata fingerprint; and
- artifact types and paths.

The generated README leads with what the human selected, where artifacts are,
and the resolved slicing recommendations. It also includes commands to inspect
the manifest, logs, source archive, and checksums.

## Testing

Unit and integration tests cover:

- discovery and listing of one or several sibling system manifests;
- system selection by unique name and explicit path;
- interactive choice and non-interactive ambiguity diagnostics when no system is
  selected;
- complete system-to-model-to-set navigation in human and JSON output;
- descriptions at every navigation level, including explicit missing-description
  display and diagnostics;
- template discovery with descriptions and explicit/default template selection;
- atomic creation of a clean SCAD-and-sidecar pair and registration in the
  selected system;
- parsing ordered named and empty SCAD sets;
- clean SCAD operation without a sidecar;
- model-sidecar validation and missing-description advisories;
- product expansion, nesting, order, cycle diagnostics, and deduplication;
- one-model and cross-model products;
- variable precedence with nested products, item overrides, profiles, and CLI;
- profile ordering and provenance;
- hard slicing-constraint conflicts;
- README rendering for ironing, support, orientation, and notes;
- geometry reuse when only slicing advice changes;
- local, repository, shared, nested, and imported-asset dependency staging;
- historical revision staging from one consistent commit;
- rejection of host-only undeclared libraries and unsafe dependency paths;
- sanitized `OPENSCADPATH` during the actual render;
- Plamp8 view-to-set and preset-to-product migration;
- iHarvest Cover, Plamp Stand, and all 3D scaffolds migrated to the new contract;
- repository-wide rejection of legacy embedded CAD metadata in SCAD sources;
- removal of obsolete CLI names without compatibility aliases;
- unchanged archive/regeneration behavior; and
- scaffolded models with clean SCAD plus adjacent sidecars.

Fake OpenSCAD tests exercise dependency files and generated argv without slow
geometry. Targeted real OpenSCAD validation uses CSG or small sets. Full STL
renders remain a workstation/manual gate when OpenSCAD is too slow locally.

## Implementation Sequence

Implementation is split into three reviewable, sequential slices:

1. **Vocabulary and catalog:** add the system/model-sidecar schemas, set parsing,
   product expansion, CLI replacements, scaffolding changes, and the atomic
   repository-wide SCAD migration. This slice removes the legacy contract; it
   does not ship a mixed mode.
2. **Manufacturing intent:** add profile resolution, variable provenance,
   slicing constraints/recommendations, metadata fingerprints, and generated
   README guidance.
3. **Portable dependencies:** add OpenSCAD dependency discovery, declared shared
   libraries, deterministic staging, sanitized rendering, and dependency
   manifests.

Each slice preserves deterministic planning and run archives and must pass its
own schema, CLI, migration, and integration tests. The implementation plan may
divide these slices into smaller tasks, but must not reorder them in a way that
leaves committed SCAD sources incompatible with the active CLI.

## Non-Goals

This design does not initially:

- parse part or feature module bodies into a semantic CAD tree;
- generate slicer-vendor project files;
- split disconnected STL shells into named parts;
- create multi-object 3MF output;
- download undeclared libraries during an ordinary generation;
- automatically replace Plamp8 fastener geometry with BOSL2;
- support native OpenSCAD parameter presets in Plamp generation;
- add asynchronous web generation; or
- preserve the old part/view/preset CLI vocabulary.

## Acceptance Criteria

The design is implemented when:

- a clean SCAD model can expose named and empty sets without embedded Plamp JSON;
- an adjacent model sidecar supplies set descriptions and manufacturing advice;
- a system manifest composes nested products across multiple models;
- multiple sibling system manifests are discoverable and individually
  selectable with `--system` by name or path;
- every selectable system, model, and set appears in complete CLI and interactive
  navigation with a visible description or missing-description marker, including
  the empty/default set;
- `plamp cad new` lists described templates and accepts `--template`, then
  creates and registers a valid model/sidecar pair in the selected system;
- model sets remain directly selectable from OpenSCAD and `plamp cad`;
- product, model, set, profile, item, and CLI values resolve deterministically;
- printer/material profiles can override reusable set defaults without modifying
  SCAD;
- slicing recommendations appear in structured manifests and human READMEs;
- local and shared OpenSCAD dependencies are staged into self-contained run
  archives and rendered without undeclared host-library fallback;
- Plamp8's current views and presets migrate to sets and products, including the
  `fit-and-function` product;
- every repository model and 3D scaffold is migrated in the same release, while
  helper/library SCAD files are explicitly classified and remain metadata-free;
- old CLI terminology is removed cleanly before 1.0; and
- existing reproducible generation, fingerprints, archives, regeneration, and
  diagnostics continue under the new vocabulary.
