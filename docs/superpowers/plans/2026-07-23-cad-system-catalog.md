# CAD System Catalog and Products Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace embedded view/preset metadata with clean SCAD sets, adjacent model sidecars, discoverable multi-system catalogs, nested products, complete described navigation, and selectable SCAD-and-sidecar scaffolds.

**Architecture:** `cad_model` parses the authoritative SCAD `set` declaration and optional adjacent model metadata; `cad_system` discovers and validates sibling system manifests; `cad_planning` expands direct model selections and nested products into immutable jobs. `cad_generation` executes multi-model plans without changing archive guarantees, while `cad_cli` provides complete system/model/set/product/template navigation and selection.

**Tech Stack:** Python 3.11 standard library, frozen dataclasses, `argparse`, JSON, OpenSCAD CLI, Git, `unittest`

## Global Constraints

- This is a pre-1.0 replacement: remove `part`, `view`, `preset`, embedded `generate.json`, `--view`, `--view-define`, `--preset`, `all-views`, and `all-presets`; do not add compatibility aliases.
- A system manifest is named `*.system.cad.json`; every sibling manifest directly under `<repo>/cad` is discoverable.
- `--system` accepts a unique declared system name or explicit manifest path; never merge manifests implicitly.
- Human, interactive, and JSON navigation must list every system, registered model, and authoritative set with descriptions or `(no description)`.
- The SCAD assignment `set = ""; // [named, choices]` and ordered choices are authoritative; the empty/default set is valid and listable.
- Sidecars describe and assign values but may not invent sets absent from SCAD.
- Products are ordered, acyclic lists of model/set or product references; only products compose multiple models.
- Product expansion preserves order, deduplicates identical full fingerprints, and retains every membership path.
- Direct model generation without `--set` selects the empty/default set; `--all-sets` selects every named set in SCAD order.
- `plamp cad plan` remains read-only; `generate` performs the same planning internally.
- `plamp cad new MODEL --template TEMPLATE --system SYSTEM` creates a clean SCAD-and-sidecar pair and registers it without leaving partial output after validation/write failure.
- Migrate Plamp8, iHarvest Cover, Plamp Stand, and all three scaffold SCAD files in the same release.
- Do not run full Plamp8 STL renders; use parser tests, fake OpenSCAD, and small CSG validation.

---

### Task 1: Parse clean model sets and adjacent sidecars

**Files:**
- Create: `plamp/cad_model.py`
- Create: `tests/test_cad_model.py`
- Delete after migration: `plamp/cad_metadata.py`
- Delete after migration: `tests/test_cad_metadata.py`

**Interfaces:**
- Produces `CadDiagnostic`, `CadMetadataError`, `CadSet`, `CadModel`, `parse_set_declaration()`, `load_model()`, and `diagnostics_json()`.
- `load_model(model_id, reference, repo_root)` accepts a `.cad.json` sidecar reference or a direct `.scad` reference for a sidecar-free model.
- Later tasks consume `CadModel.sets` in declaration order and never parse raw sidecar dictionaries.

- [ ] **Step 1: Write failing model parser tests**

Create tests for ordered choices, empty defaults, missing set declarations, direct SCAD models, strict sidecar keys, source containment, set-reference validation, descriptions, variables, printable state, and missing-description advisories:

```python
def test_clean_scad_and_sidecar_produce_ordered_sets(self):
    scad = self.write("things/fixture/fixture.scad", '''
set = ""; // [floor, top_panel, assembly]
if (set == "floor") floor_set();
''')
    sidecar = self.write_json("things/fixture/fixture.cad.json", {
        "schema": "plamp-cad-model/1", "name": "fixture",
        "source": "fixture.scad", "description": "Fixture",
        "sets": {
            "": {"description": "Normal output"},
            "floor": {"description": "Printable floor"},
            "assembly": {"description": "Assembly", "printable": False},
        },
    })
    model = load_model("fixture", sidecar, self.root)
    self.assertEqual(tuple(model.sets), ("", "floor", "top_panel", "assembly"))
    self.assertEqual(model.sets["floor"].description, "Printable floor")
    self.assertEqual(model.sets["top_panel"].description, "")
    self.assertEqual(model.advisories[0].code, "CAD112")

def test_sidecar_cannot_invent_a_set(self):
    with self.assertRaises(CadMetadataError) as caught:
        load_model("fixture", self.sidecar(sets={"missing": {}}), self.root)
    self.assertEqual(caught.exception.diagnostics[0].code, "CAD111")
    self.assertEqual(caught.exception.diagnostics[0].json_path, "$.sets.missing")
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `.venv/bin/python -m unittest tests.test_cad_model -v`

Expected: FAIL because `plamp.cad_model` does not exist.

- [ ] **Step 3: Implement immutable model types and strict parsing**

Implement these public shapes and preserve the existing diagnostic formatter:

```python
@dataclass(frozen=True)
class CadSet:
    name: str
    description: str = ""
    variables: Mapping[str, object] = field(default_factory=dict)
    printable: bool = True
    slicing: Mapping[str, object] = field(default_factory=dict)

@dataclass(frozen=True)
class CadModel:
    model_id: str
    name: str
    description: str
    source_path: Path
    sidecar_path: Path | None
    default_set: str
    sets: Mapping[str, CadSet]
    variables: Mapping[str, object]
    metadata_snapshot: Mapping[str, object]
    advisories: tuple[CadDiagnostic, ...] = ()

def parse_set_declaration(source: str, path: Path) -> tuple[str, tuple[str, ...]]:
    match = SET_ASSIGNMENT.search(source)
    if match is None:
        return "", ()
    default = json.loads(f'"{match.group("value")}"')
    choices = tuple(
        item.strip() for item in match.group("choices").split(",") if item.strip()
    )
    return default, choices
```

Construct the public ordered set mapping as `("", *choices)` when the assigned default is empty, otherwise preserve choices and require the assigned default to occur in them. Reject unknown JSON keys, non-finite numbers, unsafe names, escaped source paths, and sidecar set keys absent from that mapping. A direct `.scad` reference creates one implicit empty set with `(no description)` advisory metadata.

- [ ] **Step 4: Verify GREEN and commit**

Run:

```bash
.venv/bin/python -m unittest tests.test_cad_model -v
python3 -m py_compile plamp/cad_model.py tests/test_cad_model.py
git diff --check
git add plamp/cad_model.py tests/test_cad_model.py
git commit -m "Parse clean CAD model metadata"
```

Expected: all model parser tests pass.

---

### Task 2: Discover and validate multiple system manifests

**Files:**
- Create: `plamp/cad_system.py`
- Create: `tests/test_cad_system.py`

**Interfaces:**
- Consumes `load_model()` from Task 1.
- Produces `SystemCandidate`, `CadProductItem`, `CadProduct`, `CadSystem`, `discover_systems()`, `select_system()`, and `load_system()`.
- A candidate remains listable when invalid; generation requires a valid loaded `CadSystem`.

- [ ] **Step 1: Write failing discovery and validation tests**

```python
def test_discovers_all_sibling_system_files_and_keeps_invalid_rows(self):
    self.system("cad/plamp.system.cad.json", name="plamp")
    self.system("cad/jigs.system.cad.json", name="jigs")
    self.write("cad/broken.system.cad.json", "{")
    self.system("cad/nested/ignored.system.cad.json", name="ignored")
    rows = discover_systems(self.root)
    self.assertEqual(tuple(row.path.name for row in rows), (
        "broken.system.cad.json", "jigs.system.cad.json", "plamp.system.cad.json"))
    self.assertEqual(rows[0].status, "invalid")

def test_selects_by_unique_name_or_explicit_path(self):
    candidates = discover_systems(self.root)
    self.assertEqual(select_system(candidates, "plamp").name, "plamp")
    self.assertEqual(select_system(candidates, str(self.jigs_path)).name, "jigs")
```

Also cover duplicate declared names, strict schema keys, missing model/product/profile/library paths, exactly-one-of product item references, missing set references, invalid variants, unknown products, and full cycle paths.

- [ ] **Step 2: Run tests and verify RED**

Run: `.venv/bin/python -m unittest tests.test_cad_system -v`

Expected: FAIL because `plamp.cad_system` does not exist.

- [ ] **Step 3: Implement system catalog types and selection**

```python
@dataclass(frozen=True)
class SystemCandidate:
    path: Path
    name: str
    description: str
    default_product: str | None
    status: str
    diagnostics: tuple[CadDiagnostic, ...] = ()

@dataclass(frozen=True)
class CadProductItem:
    product: str | None = None
    model: str | None = None
    set_name: str | None = None
    variant: str | None = None
    description: str = ""
    variables: Mapping[str, object] = field(default_factory=dict)
    profiles: tuple[str, ...] = ()
    slicing: Mapping[str, object] = field(default_factory=dict)

@dataclass(frozen=True)
class CadProduct:
    name: str
    description: str
    items: tuple[CadProductItem, ...]
    variables: Mapping[str, object] = field(default_factory=dict)
    profiles: tuple[str, ...] = ()
    slicing: Mapping[str, object] = field(default_factory=dict)

@dataclass(frozen=True)
class CadSystem:
    name: str
    description: str
    path: Path
    models: Mapping[str, CadModel]
    products: Mapping[str, CadProduct]
    default_product: str | None
    libraries: Mapping[str, object]
    profiles: Mapping[str, Path]
    metadata_snapshot: Mapping[str, object]
```

`discover_systems(repo_root)` scans only `repo_root/cad/*.system.cad.json`, sorts by filename, and catches parse errors into invalid candidates. `select_system()` accepts a declared name or path and raises a `CadMetadataError` containing discovered choices on zero/ambiguous matches. `load_system()` resolves repository-relative paths, loads every model, validates product references and sibling variants, and performs DFS cycle detection with the complete path.

- [ ] **Step 4: Verify GREEN and commit**

Run:

```bash
.venv/bin/python -m unittest tests.test_cad_model tests.test_cad_system -v
python3 -m py_compile plamp/cad_system.py tests/test_cad_system.py
git diff --check
git add plamp/cad_system.py tests/test_cad_system.py
git commit -m "Add multi-system CAD catalogs"
```

---

### Task 3: Expand direct sets and nested products into render jobs

**Files:**
- Create: `plamp/cad_planning.py`
- Create: `plamp/cad_values.py`
- Create: `tests/test_cad_planning.py`
- Modify: `plamp/cad_generation.py` (import serialization from `cad_values`)

**Interfaces:**
- Consumes `CadSystem`, `CadModel`, and source identities keyed by model ID.
- Produces `CadSelection`, `VariableSource`, `RenderJob`, `RenderPlan`, `build_render_plan()`, `plan_as_dict()`, and `serialize_scad_value()`.
- `RenderJob` identifies `model_id`, `set_name`, `product_paths`, and effective typed/raw variables.

- [ ] **Step 1: Write failing direct/product planning tests**

```python
def test_nested_product_order_deduplication_and_memberships(self):
    plan = build_render_plan(
        self.system_with_nested_products(),
        CadSelection(product="complete"),
        source_identities={"box": "box123", "holder": "holder456"},
    )
    self.assertEqual(
        tuple((job.model_id, job.set_name) for job in plan.jobs),
        (("box", "floor"), ("box", "top"), ("holder", "standard")),
    )
    self.assertEqual(plan.jobs[0].product_paths, (("complete", "split-box"),))

def test_variable_precedence_runs_deepest_product_outward_then_cli(self):
    plan = build_render_plan(
        self.layered_system(),
        CadSelection(product="complete", defines={"clearance": 0.4}),
        source_identities={"box": "abc"},
    )
    job = plan.jobs[0]
    self.assertEqual(job.variables["clearance"], 0.4)
    self.assertEqual(job.variable_sources["clearance"].kind, "cli")
```

Cover empty/default direct selection, `--all-sets` named-order behavior, unknown set/product diagnostics, repeated variants, cycle defense, product/item precedence, raw define precedence, stable SHA-256 fingerprints, distinct human artifact IDs, and JSON shape.

- [ ] **Step 2: Run tests and verify RED**

Run: `.venv/bin/python -m unittest tests.test_cad_planning -v`

Expected: FAIL because `plamp.cad_planning` does not exist.

- [ ] **Step 3: Implement immutable plan expansion**

```python
@dataclass(frozen=True)
class CadSelection:
    product: str | None = None
    model: str | None = None
    sets: tuple[str, ...] = ()
    all_sets: bool = False
    defines: Mapping[str, object] = field(default_factory=dict)
    set_defines: Mapping[str, Mapping[str, object]] = field(default_factory=dict)
    raw_defines: tuple[str, ...] = ()

@dataclass(frozen=True)
class VariableSource:
    kind: str
    source_id: str

@dataclass(frozen=True)
class RenderJob:
    artifact_id: str
    model_id: str
    set_name: str
    variant_name: str
    variables: Mapping[str, object]
    raw_defines: Mapping[str, str]
    variable_sources: Mapping[str, VariableSource]
    product_paths: tuple[tuple[str, ...], ...]
    fingerprint: str

@dataclass(frozen=True)
class RenderPlan:
    system_name: str
    system_path: Path
    selection: CadSelection
    jobs: tuple[RenderJob, ...]
```

Move deterministic OpenSCAD serialization and raw-define parsing into `cad_values.py`. Expand products depth-first in item order. For each leaf apply model variables, set variables, then product layers from deepest outward, applying each product followed by its relevant item, and CLI last. Fingerprint canonical JSON containing schema version, system manifest hash, source identity, model, set, variables, and raw expressions. Deduplicate by full fingerprint while appending every product path.

- [ ] **Step 4: Adapt the generation import and verify GREEN**

Replace the existing `serialize_scad_value` import from `plamp.cad_recipes` with
`from plamp.cad_values import serialize_scad_value`; do not otherwise change
generation yet. Keep the old recipe module until Task 8 so each intermediate
commit remains importable.

Run:

```bash
.venv/bin/python -m unittest tests.test_cad_model tests.test_cad_system tests.test_cad_planning tests.test_cad_generation -v
python3 -m py_compile plamp/cad_planning.py plamp/cad_values.py
git diff --check
git add plamp/cad_planning.py plamp/cad_values.py plamp/cad_generation.py tests/test_cad_planning.py
git commit -m "Plan nested CAD products"
```

---

### Task 4: Add complete system, model, set, and product CLI navigation

**Files:**
- Modify: `plamp/cad_cli.py`
- Modify: `tests/test_cad_cli.py`

**Interfaces:**
- Consumes catalog discovery/selection and `plan_as_dict()`.
- Produces actions `systems`, `models`, `sets`, `products`, `profiles`, `libraries`, and `templates` plus shared `--system NAME_OR_PATH` selection.
- This task adds read-only catalog navigation without changing the existing
  plan/generate execution path; Task 5 performs that atomic CLI/generator swap.

- [ ] **Step 1: Replace parser-contract tests first**

```python
def test_help_adds_complete_catalog_navigation(self):
    help_text = self.cad_help()
    for command in ("systems", "models", "sets", "products", "profiles",
                    "libraries", "templates", "new", "plan", "generate"):
        self.assertIn(command, help_text)

def test_navigation_lists_descriptions_and_parent_ids_in_json(self):
    value = self.run_json(["cad", "sets", "fixture", "--system", "alpha"])
    self.assertEqual(value[0], {
        "kind": "set", "id": "", "system": "alpha", "model": "fixture",
        "description": "Normal output", "printable": True,
        "source": "things/fixture/fixture.scad",
    })
```

Cover invalid candidates remaining visible, `(no description)`, one-system
auto-selection, multi-system interactive choice, noninteractive CAD200 error
with exact `--system`, explicit path, and system/model/set back-navigation in the
catalog browser.

- [ ] **Step 2: Run CLI tests and verify RED**

Run: `.venv/bin/python -m unittest tests.test_cad_cli -v`

Expected: failures showing old commands and missing catalog actions.

- [ ] **Step 3: Implement shared system resolution and described emitters**

Use one resolver for every system-aware action:

```python
def _selected_system(args, context, stdin, stdout, deps) -> CadSystem:
    candidates = deps["discover_systems"](context.root)
    selector = getattr(args, "system", None)
    if selector is not None or len(candidates) == 1:
        return deps["load_system"](context.root, selector or candidates[0].path)
    if not _interactive(stdin, args):
        raise CadSelectionError(_system_choice_message(candidates))
    return deps["load_system"](
        context.root, _choose_numbered("System", candidates, stdin, stdout).path
    )
```

Make human output include ID and description columns without requiring a table
switch. Emit `(no description)` explicitly. JSON emits arrays of rows with
`kind`, stable ID, parents, description, status, diagnostic, and path. Keep the
legacy execution parser isolated and unchanged until Task 5; do not route new
catalog actions through it.

- [ ] **Step 4: Verify GREEN and commit**

Run:

```bash
.venv/bin/python -m unittest tests.test_cad_cli tests.test_cad_model tests.test_cad_system tests.test_cad_planning -v
python3 -m py_compile plamp/cad_cli.py tests/test_cad_cli.py
git diff --check
git add plamp/cad_cli.py tests/test_cad_cli.py
git commit -m "Navigate CAD systems models and sets"
```

---

### Task 5: Execute multi-model set plans and preserve archive behavior

**Files:**
- Modify: `plamp/cad_generation.py`
- Modify: `tests/test_cad_generation.py`
- Modify: `plamp/cad_cli.py`
- Modify: `tests/test_cad_cli.py`

**Interfaces:**
- `prepare_source()` continues to return one `SourceSnapshot` per model.
- `generate_plan()` now consumes `models: Mapping[str, CadModel]` and `snapshots: Mapping[str, SourceSnapshot]` instead of one SCAD path/snapshot.
- OpenSCAD receives `-D set="<name>"`; empty set is passed explicitly as `set=""` for reproducible argv.
- Atomically switches `validate`, `plan`, `menu`, and `generate` to model/set/
  product selection and removes `views`, `--view`, `--view-define`, `--preset`,
  and synthetic preset handling.

- [ ] **Step 1: Write failing multi-model generation tests**

```python
def test_product_jobs_render_their_own_archived_model_sources(self):
    result = generate_plan(
        TWO_MODEL_PLAN, repo_root=self.repo, data_dir=self.data,
        models=self.models, snapshots=self.snapshots,
        openscad=self.fake, stdout=io.StringIO(),
    )
    commands = json.loads(result.manifest_path.read_text())["jobs"]
    self.assertIn("set=\"floor\"", commands[0]["command"])
    self.assertTrue(commands[0]["command"][-1].endswith("box/box.scad"))
    self.assertTrue(commands[1]["command"][-1].endswith("holder/holder.scad"))
```

Cover one snapshot per distinct model, historical/dirty rules per model folder, source hashes keyed by model ID, system path/hash and product paths in manifests, readable product/direct selectors in run IDs, duplicate-run identity, regeneration, failed later jobs, and existing run/log lookup.

Add CLI tests proving optional positional model, mutually exclusive `--product`,
repeatable `--set`, `--all-sets`, `--define`, `--set-define`, default product,
interactive menu back-navigation, and exact replacement diagnostics for every
removed command/option.

- [ ] **Step 2: Run generation tests and verify RED**

Run: `.venv/bin/python -m unittest tests.test_cad_generation tests.test_cad_cli -v`

Expected: signature and manifest-shape failures.

- [ ] **Step 3: Implement multi-model snapshots and set argv**

```python
def _command(openscad, output, source, revision, job):
    command = [str(openscad), "-o", str(output), "-D",
               f"revision_string={serialize_scad_value(revision)}", "-D",
               f"set={serialize_scad_value(job.set_name)}"]
    # append typed/raw variables, export format, and this job's staged source
    return command
```

Copy each distinct snapshot once under `source/<model-id>/`, map every job to that archived root, and record `system`, `selection`, `models`, and `product_paths` in the manifest. Keep geometry fingerprints independent from human variant names. Preserve the existing atomic manifests, partial failures, run collision warning/regeneration prompt, logs, statistics, and source cleanup.

- [ ] **Step 4: Wire CLI snapshot planning and verify GREEN**

The CLI must prepare all selected models before final plan fingerprints and pass the same snapshots to generation; cleanup every snapshot in `finally`.

Run:

```bash
.venv/bin/python -m unittest tests.test_cad_generation tests.test_cad_cli -v
python3 -m py_compile plamp/cad_generation.py plamp/cad_cli.py
git diff --check
git add plamp/cad_generation.py plamp/cad_cli.py tests/test_cad_generation.py tests/test_cad_cli.py
git commit -m "Generate multi-model CAD products"
```

---

### Task 6: Scaffold selectable SCAD-and-sidecar templates into a system

**Files:**
- Modify: `plamp/cad_scaffold.py`
- Modify: `tests/test_cad_scaffold.py`
- Modify: `plamp/cad_cli.py`
- Modify: `tests/test_cad_cli.py`
- Create: `things/3d_template/cad.cad.json`
- Create: `things/3d_template/scad/flat_plate.cad.json`
- Create: `things/3d_template/scad/positive_negative.cad.json`
- Modify: `things/3d_template/cad.scad`
- Modify: `things/3d_template/scad/flat_plate.scad`
- Modify: `things/3d_template/scad/positive_negative.scad`

**Interfaces:**
- `CadTemplate` adds `sidecar_path` and `description`.
- `CreatedModel` replaces `CreatedPart` and exposes `model_id`, `template`, `directory`, `scad_path`, and `sidecar_path`.
- `create_model(repo_root, system, model_id, template_name)` creates both files and updates the selected system manifest with rollback on failure.
- `new --list-templates` is removed now that the described `templates` action is
  available; `new` retains explicit `--template` selection.

- [ ] **Step 1: Write failing paired-template and transaction tests**

```python
def test_templates_have_descriptions_and_generate_two_clean_files(self):
    template = discover_templates(REPO_ROOT)[0]
    self.assertTrue(template.description)
    created = create_model(self.root, self.system, "pump-bracket", "flat_plate")
    self.assertTrue(created.scad_path.is_file())
    self.assertTrue(created.sidecar_path.is_file())
    self.assertNotIn("generate.json", created.scad_path.read_text())
    self.assertIn("pump-bracket", json.loads(created.sidecar_path.read_text())["name"])

def test_manifest_replace_failure_rolls_back_published_model(self):
    with mock.patch("plamp.cad_scaffold._replace_system_manifest",
                    side_effect=OSError("disk full")):
        with self.assertRaises(OSError):
            create_model(self.root, self.system, "pump", "cad")
    self.assertFalse((self.root / "things/pump").exists())
    self.assertEqual(self.system_path.read_bytes(), self.original_manifest)
```

Also cover `templates` human/JSON descriptions, explicit `--template`, interactive default menu, noninteractive `cad` default, unknown template diagnostics, duplicate model IDs, unsafe paths/symlinks, SCAD/sidecar substitution, and immediate model/set navigation.

- [ ] **Step 2: Run scaffold tests and verify RED**

Run: `.venv/bin/python -m unittest tests.test_cad_scaffold tests.test_cad_cli -v`

Expected: failures for missing sidecars/descriptions and old `CreatedPart` API.

- [ ] **Step 3: Implement paired discovery, validation, staging, and rollback**

```python
@dataclass(frozen=True)
class CadTemplate:
    name: str
    path: Path
    sidecar_path: Path
    description: str
    device: int | None = None
    inode: int | None = None

@dataclass(frozen=True)
class CreatedModel:
    model_id: str
    template: str
    directory: Path
    scad_path: Path
    sidecar_path: Path
```

Read template SCAD and sidecar without following replacement symlinks, substitute `__PLAMP_PART__`/model name in both, validate with `load_model()`, and stage them in the existing no-replace directory. Under an exclusive lock beside the system manifest: validate a new manifest containing the model entry, publish the model directory, atomically replace the manifest, and on any caught write failure remove the new directory and restore the original manifest bytes.

In the same task, migrate each template from `view`/embedded metadata to the
clean `set` selector before paired discovery is enabled, so the task's commit is
internally valid.

- [ ] **Step 4: Wire `templates` and `new`, verify GREEN, and commit**

Run:

```bash
.venv/bin/python -m unittest tests.test_cad_scaffold tests.test_cad_cli tests.test_cad_model tests.test_cad_system -v
python3 -m py_compile plamp/cad_scaffold.py
git diff --check
git add plamp/cad_scaffold.py plamp/cad_cli.py tests/test_cad_scaffold.py tests/test_cad_cli.py things/3d_template
git commit -m "Scaffold CAD models from described templates"
```

---

### Task 7: Migrate every repository SCAD model and define system products

**Files:**
- Create: `cad/plamp.system.cad.json`
- Create: `things/plamp8/plamp8.cad.json`
- Create: `things/iharvest_cover/iharvest_cover.cad.json`
- Create: `things/plamp_stand/plamp_stand.cad.json`
- Modify: `things/plamp8/plamp8.scad`
- Modify: `things/iharvest_cover/iharvest_cover.scad`
- Modify: `things/plamp_stand/plamp_stand.scad`
- Modify: `tests/test_things_cad_scripts.py`
- Modify: `tests/test_cad_model.py`
- Modify: `tests/test_cad_system.py`

**Interfaces:**
- The system registers all current real models and initially defaults to `split-box` until absent Raspberry Pi/camera holder models exist.
- Existing Plamp8 presets become system products; `test-fit` is renamed `fit-and-function`.

- [ ] **Step 1: Replace repository-contract tests first**

```python
def test_every_repository_scad_is_clean_or_a_library(self):
    roots = tuple(REPO_ROOT.glob("things/**/*.scad"))
    for path in roots:
        source = path.read_text(encoding="utf-8")
        self.assertNotIn("generate.json", source, path)
        self.assertNotRegex(source, r"(?m)^\s*view\s*=", path)

def test_plamp_system_catalog_has_migrated_products(self):
    system = load_system(REPO_ROOT, "plamp")
    self.assertEqual(tuple(system.models), ("plamp8", "iharvest_cover", "plamp_stand"))
    self.assertIn("fit-and-function", system.products)
    self.assertNotIn("test-fit", system.products)
```

Retain all existing geometry/dimension assertions, changing only selector variable/name expectations. Add exact set order and non-empty description assertions for each model and template.

- [ ] **Step 2: Run repository tests and verify RED**

Run: `.venv/bin/python -m unittest tests.test_things_cad_scripts tests.test_cad_model tests.test_cad_system -v`

Expected: failures on legacy `view` and embedded metadata.

- [ ] **Step 3: Migrate SCAD selectors and sidecars**

For each root replace the selector only, leaving geometry modules untouched:

```scad
set = ""; // [floor, top_panel, sub_panel, assembly]

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

Move every description into the adjacent sidecar. Build `plamp.system.cad.json` with `split-box`, `fuse-box`, `panels`, `assembly`, `component-floorplans`, `top-panel-fit`, `corner-coupons`, and nested `fit-and-function`. Do not add nonexistent holder model placeholders.

- [ ] **Step 4: Verify parser/system tests and targeted OpenSCAD syntax**

Run:

```bash
.venv/bin/python -m unittest tests.test_things_cad_scripts tests.test_cad_model tests.test_cad_system tests.test_cad_planning -v
plamp cad validate plamp8 --system plamp --json
plamp cad plan --product fit-and-function --system plamp --json
git diff --check
```

Expected: tests pass; validation returns valid JSON; planning lists jobs without invoking OpenSCAD.

- [ ] **Step 5: Commit the atomic repository migration**

```bash
git add cad/plamp.system.cad.json things tests/test_things_cad_scripts.py tests/test_cad_model.py tests/test_cad_system.py
git commit -m "Migrate repository CAD models to sets"
```

---

### Task 8: Update documentation, remove legacy modules, and run the full gate

**Files:**
- Modify: `docs/host-tools.md`
- Delete: `plamp/cad_metadata.py`
- Delete: `tests/test_cad_metadata.py`
- Delete: `plamp/cad_recipes.py`
- Delete: `tests/test_cad_recipes.py`

**Interfaces:**
- Human docs lead with `systems`, `models`, `sets`, `products`, `templates`, direct `generate`, and `--system`/`--template` examples.
- Obsolete terminology appears only in migration/history documentation.

- [ ] **Step 1: Write/update documentation assertions**

```python
def test_cad_documentation_uses_system_model_set_product_vocabulary(self):
    text = (REPO_ROOT / "docs/host-tools.md").read_text()
    for command in ("plamp cad systems", "plamp cad models", "plamp cad sets",
                    "plamp cad products", "plamp cad templates", "--template"):
        self.assertIn(command, text)
    self.assertNotIn("plamp cad views", text)
    self.assertNotIn("--preset", text)
```

- [ ] **Step 2: Update human and agent documentation**

Document the no-argument default-product path first, then discovery, explicit
system selection, direct model/set generation, all sets, template scaffolding,
run inspection, and noninteractive ambiguity behavior. Updating the external
OpenSCAD skill is a separate repository task and is not part of this plan.

- [ ] **Step 3: Run focused and full verification**

Run:

```bash
.venv/bin/python -m unittest tests.test_cad_model tests.test_cad_system tests.test_cad_planning tests.test_cad_scaffold tests.test_cad_generation tests.test_cad_cli tests.test_things_cad_scripts -v
.venv/bin/python -m unittest discover -s tests -v
python3 -m py_compile plamp/cad_*.py tests/test_cad_*.py
rg -n 'generate\.json|^\s*view\s*=|--preset|--view' things plamp docs/host-tools.md
git diff --check
git status --short
```

Expected: all tests pass; the legacy scan has no source/CLI hits (historical spec/plan files are excluded); only intentional task changes are present.

- [ ] **Step 4: Commit the final slice**

```bash
git add docs/host-tools.md
git rm plamp/cad_metadata.py tests/test_cad_metadata.py plamp/cad_recipes.py tests/test_cad_recipes.py
git commit -m "Document CAD system product workflow"
```
