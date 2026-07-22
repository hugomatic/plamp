# Versioned CAD Generation Recipes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace copied OpenSCAD generation scripts with a tested local `plamp cad` engine supporting embedded metadata, nested presets, scoped variables, dry planning, reproducible instance-local artifacts, and humane diagnostics.

**Architecture:** Separate pure source parsing and recipe expansion from Git/OpenSCAD side effects. `plamp.cad_metadata` owns the embedded schema and diagnostics, `plamp.cad_recipes` produces deterministic render jobs, `plamp.cad_generation` owns archived-source rendering and manifests, and `plamp.cad_cli` exposes the engine through one direct local CLI.

**Tech Stack:** Python 3.11 standard library, `argparse`, OpenSCAD CLI, Git, `unittest`

## Global Constraints

- Preset definitions live in the SCAD `/* generate.json ... */` block and are versioned with geometry.
- The Customizer `view = ... // [...]` list remains the canonical ordered valid-view list.
- A preset contains ordered `view:<name>` and/or `preset:<name>` items; cycles and unknown references are errors.
- Exactly one preset may be selected; preset and direct-view selection are mutually exclusive; `--view` is repeatable.
- Variable precedence is SCAD defaults, global, view, outer-to-inner preset, outer-to-inner preset-view, CLI global, CLI per-view.
- `all-views` renders each declared view once; `all-presets` renders each distinct source/view/effective-variable fingerprint and retains every preset membership.
- Validation and planning never invoke OpenSCAD.
- Generated artifacts default to `$PLAMP_DATA_DIR/cad/prints`, never the repository.
- Manifests are written atomically and retain partial/failed runs, logs, echoes, geometry statistics, commands, versions, and timings.
- CAD messages are recorded but never executed.
- Expected user errors produce stable structured diagnostics and no traceback.
- `plamp cad` is the sole generation interface; Plamp8 fused-box generation uses `--preset fuse-box`.
- Plate 2 web generation, Three.js, onboarding, distributed caches, robots, and the preset-authoring skill are out of scope.
- Do not run real Plamp8 OpenSCAD renders during implementation; use a fake executable for integration tests.

## Compatibility and contract decisions

- Synthetic `all-views` and `all-presets` are reserved names accepted through `--preset`; metadata collisions are errors.
- Support `--output`, `--revision`, `--preview`, repeatable `--view`, and repeatable `--define` directly; omitting `--output` uses the instance archive.
- Preserve the existing default clean revision rule: use the latest commit touching the part directory, not unrelated repository HEAD changes.
- Direct generation allows an explicit historical commit through `--revision`; clean generation archives the complete part directory at that commit.
- Run IDs are globally unique UTC `YYYYMMDDTHHMMSSZ-<part>-<selector>-<revision>-<random6>` strings; archive lookup uses the complete run ID.
- `log` accepts the manifest artifact ID, not a fuzzy filename.
- Legacy repository `things/*/prints` discovery is deferred; Plate 1 catalogs new instance-data manifests only.
- Planning estimates use the median successful elapsed time and byte size for the same part path, view/implicit default, effective variables, and generator version; missing history yields null estimates.
- OpenSCAD version is recorded in the manifest but excluded from plan fingerprints so validation and planning never need to locate OpenSCAD.
- Metadata objects serialize as deterministically key-sorted OpenSCAD list-of-pairs values (`[["key", value], ...]`).
- CLI raw defines split at the first `=`; later definitions of the same name win. Raw expressions replace lower-precedence typed values, remain verbatim in argv, and contribute verbatim to fingerprints.
- `menu` presents numbered presets followed by numbered views, accepts one preset or multiple views, treats EOF/cancel as diagnostic exit 2, and is unavailable with `--json`.
- OpenSCAD statistics are nullable and parser-tolerant; only nonzero exit, missing output, or empty output makes a render fail.

---

### Task 1: Parse SCAD metadata and produce humane diagnostics

**Files:**
- Create: `plamp/cad_metadata.py`
- Create: `tests/test_cad_metadata.py`

**Interfaces:**
- Produces `CadDiagnostic`, `CadMetadataError`, `ViewMetadata`, `PresetMetadata`, `CadDocument`, `parse_cad_document(path)`, and `diagnostics_json()`.
- `CadDocument.views` preserves Customizer declaration order; `CadDocument.default_view` records the assigned string when present.
- Later tasks consume only these typed objects, not raw JSON dictionaries.

- [ ] **Step 1: Write failing parser and diagnostic tests**

Cover valid sentinel extraction, partial view metadata, no metadata, implicit default without a view list, invalid JSON location, unknown view, unknown preset item, invalid item prefix, invalid `view_variables`, and close-name suggestions.

```python
def test_parse_document_keeps_customizer_order_and_metadata_overlay(self):
    path = self.write_scad('''
view = "assembly"; // [floor, box, assembly]
/* generate.json
{"default_preset":"split-box","views":{"box":{"description":"A box"}},
 "presets":{"split-box":{"items":["view:floor","view:box"]}}}
*/
''')
    document = parse_cad_document(path)
    self.assertEqual(document.views, ("floor", "box", "assembly"))
    self.assertEqual(document.view_metadata["box"].description, "A box")

def test_unknown_view_has_stable_code_path_and_suggestion(self):
    with self.assertRaises(CadMetadataError) as caught:
        parse_cad_document(self.write_scad(SCAD_WITH_NORTH_SOUTH_TYPO))
    diagnostic = caught.exception.diagnostics[0]
    self.assertEqual(diagnostic.code, "CAD101")
    self.assertEqual(diagnostic.json_path, "$.presets.split-box.items[0]")
    self.assertEqual(diagnostic.suggestion, "north_south_walls")
```

- [ ] **Step 2: Run tests and verify RED**

Run: `.venv/bin/python -m unittest tests.test_cad_metadata -v`

Expected: import failure because `plamp.cad_metadata` does not exist.

- [ ] **Step 3: Implement typed parsing and validation**

Use frozen dataclasses and one exception carrying ordered diagnostics:

```python
@dataclass(frozen=True)
class CadDiagnostic:
    code: str
    kind: str
    message: str
    source: str
    json_path: str | None = None
    line: int | None = None
    column: int | None = None
    value: object | None = None
    choices: tuple[str, ...] = ()
    suggestion: str | None = None
    fix: str | None = None

@dataclass(frozen=True)
class ViewMetadata:
    description: str = ""
    variables: Mapping[str, object] = field(default_factory=dict)

@dataclass(frozen=True)
class PresetMetadata:
    description: str = ""
    items: tuple[str, ...] = ()
    variables: Mapping[str, object] = field(default_factory=dict)
    view_variables: Mapping[str, Mapping[str, object]] = field(default_factory=dict)

@dataclass(frozen=True)
class CadDocument:
    path: Path
    default_view: str | None
    views: tuple[str, ...]
    global_variables: Mapping[str, object]
    view_metadata: Mapping[str, ViewMetadata]
    presets: Mapping[str, PresetMetadata]
    default_preset: str | None
    metadata_snapshot: Mapping[str, object]
```

Parse the exact sentinel block with string offsets plus `json.loads`; parse the first assigned `view` and optional bracket list separately. Validate metadata references after all objects are constructed. Use `difflib.get_close_matches(..., n=1, cutoff=0.6)` for suggestions. Format `CadMetadataError` without a traceback at command boundaries.

- [ ] **Step 4: Verify GREEN and commit**

Run:

```bash
.venv/bin/python -m unittest tests.test_cad_metadata -v
python3 -m py_compile plamp/cad_metadata.py tests/test_cad_metadata.py
git diff --check
git add plamp/cad_metadata.py tests/test_cad_metadata.py
git commit -m "Parse versioned CAD recipe metadata"
```

Expected: parser tests pass and compilation/diff checks are clean.

---

### Task 2: Expand nested recipes and calculate deterministic render plans

**Files:**
- Create: `plamp/cad_recipes.py`
- Create: `tests/test_cad_recipes.py`

**Interfaces:**
- Consumes `CadDocument` from Task 1.
- Produces `Selection`, `RenderJob`, `PresetNode`, `RenderPlan`, `build_render_plan()`, `serialize_scad_value()`, and `plan_as_dict()`.
- `RenderJob.fingerprint` is stable across processes and includes source identity supplied by the caller, view/implicit default, effective variables, and generator schema version.

- [ ] **Step 1: Write failing expansion and precedence tests**

Cover nested order, empty preset/default job, cycle path, `all-views`, `all-presets`, exact-job deduplication with multiple memberships, same-view variable variants, assembly-last direct selection, repeatable view ordering, selector conflicts, and every variable-precedence layer.

```python
def test_all_presets_deduplicates_identical_jobs_but_keeps_variants(self):
    plan = build_render_plan(
        DOCUMENT_WITH_SHARED_AND_VARIANT_WALLS,
        Selection(preset="all-presets"),
        source_identity="abc123",
    )
    wall_jobs = [job for job in plan.jobs if job.view == "north_south_walls"]
    self.assertEqual(len(wall_jobs), 2)
    self.assertEqual({job.variables["coarse"] for job in wall_jobs}, {True, False})
    self.assertGreater(len(wall_jobs[0].preset_paths), 1)

def test_cli_view_define_has_highest_precedence(self):
    plan = build_render_plan(
        DOCUMENT_WITH_ALL_VARIABLE_SCOPES,
        Selection(preset="outer", defines={"rib":"cli"},
                  view_defines={"box":{"rib":"view-cli"}}),
        source_identity="abc123",
    )
    self.assertEqual(plan.jobs_by_view["box"].variables["rib"], "view-cli")
```

- [ ] **Step 2: Run tests and verify RED**

Run: `.venv/bin/python -m unittest tests.test_cad_recipes -v`

Expected: import failure because `plamp.cad_recipes` does not exist.

- [ ] **Step 3: Implement deterministic planning**

Use immutable public results:

```python
@dataclass(frozen=True)
class Selection:
    preset: str | None = None
    views: tuple[str, ...] = ()
    defines: Mapping[str, object] = field(default_factory=dict)
    view_defines: Mapping[str, Mapping[str, object]] = field(default_factory=dict)

@dataclass(frozen=True)
class RenderJob:
    artifact_id: str
    view: str | None
    variant_name: str
    variables: Mapping[str, object]
    preset_paths: tuple[tuple[str, ...], ...]
    fingerprint: str

@dataclass(frozen=True)
class RenderPlan:
    selection: Selection
    jobs: tuple[RenderJob, ...]
    preset_tree: tuple[PresetNode, ...]
```

Expand with depth-first traversal and a recursion stack for cycle diagnostics. Compute all preset-wide scopes outer-to-inner, then all matching view scopes outer-to-inner. Fingerprint canonical JSON containing schema version, source identity, view, and sorted effective variables with SHA-256; use the first 12 hex characters in artifact IDs. Deduplicate by full fingerprint and merge preset membership paths. `all-views` and `all-presets` are reserved synthetic selectors, not required metadata entries.

- [ ] **Step 4: Verify GREEN and commit**

Run:

```bash
.venv/bin/python -m unittest tests.test_cad_metadata tests.test_cad_recipes -v
python3 -m py_compile plamp/cad_recipes.py tests/test_cad_recipes.py
git diff --check
git add plamp/cad_recipes.py tests/test_cad_recipes.py
git commit -m "Expand nested CAD generation recipes"
```

Expected: metadata and recipe tests pass.

---

### Task 3: Generate versioned instance-local artifacts and manifests

**Files:**
- Create: `plamp/cad_generation.py`
- Create: `tests/test_cad_generation.py`

**Interfaces:**
- Consumes `RenderPlan`, repository root, data directory, SCAD path, optional explicit output, OpenSCAD path, revision override, and output streams.
- Produces `GenerationResult` plus atomic `manifest.json`, `readme.md`, `artifacts/*.stl`, and `logs/*.log`.
- Exposes `resolve_part()`, `prepare_source()`, `generate_plan()`, `list_runs()`, `load_run()`, and `load_job_log()`.

- [ ] **Step 1: Write failing archive and fake-OpenSCAD tests**

Use a fake executable that writes ASCII STL, emits typed/untyped echoes and geometry statistics, optionally fails, and records argv. Cover default `$PLAMP_DATA_DIR/cad/prints`, explicit output, archived committed source, unrelated dirty files, dirty-part rejection without revision, honest dirty revision, atomic state transitions, completed-job retention after later failure, exact argv/variables, message/stat extraction, no message execution, catalog ordering, and log retrieval.

```python
def test_generation_updates_manifest_after_each_job_and_keeps_partial_failure(self):
    result = generate_plan(
        TWO_JOB_PLAN,
        repo_root=repo,
        data_dir=data,
        scad_path=scad,
        openscad=fake_openscad,
        env={"FAKE_FAIL_VIEW":"second"},
    )
    manifest = json.loads(result.manifest_path.read_text())
    self.assertEqual(manifest["status"], "failed")
    self.assertEqual(manifest["jobs"][0]["status"], "complete")
    self.assertTrue(Path(manifest["jobs"][0]["artifact"]).is_file())
    self.assertEqual(manifest["jobs"][1]["status"], "failed")

def test_cad_messages_are_recorded_and_never_executed(self):
    manifest = self.generate_with_echo('ECHO: ["PLAMP", "robot", ["touch", "/tmp/no"]]')
    self.assertEqual(manifest["jobs"][0]["messages"][0]["channel"], "robot")
    self.assertFalse(Path("/tmp/no").exists())
```

- [ ] **Step 2: Run tests and verify RED**

Run: `.venv/bin/python -m unittest tests.test_cad_generation -v`

Expected: import failure because `plamp.cad_generation` does not exist.

- [ ] **Step 3: Implement source preparation, runner, manifest, and catalog**

Use `subprocess.run`/`Popen` argument lists only, stream merged output line-by-line to terminal and log, and write manifests with `NamedTemporaryFile` in the run directory followed by `os.replace`.

```python
@dataclass(frozen=True)
class SourceSnapshot:
    scad_path: Path
    source_identity: str
    full_commit: str | None
    revision_label: str
    dirty: bool
    cleanup_root: Path | None

@dataclass(frozen=True)
class GenerationResult:
    run_dir: Path
    manifest_path: Path
    status: str
```

Freeze manifest schema version 1 in tests before implementing updates. The persisted document has this exact top-level shape; nullable values use JSON `null` and timestamps use UTC RFC 3339 strings:

```json
{
  "schema_version": 1,
  "generator_version": 1,
  "run_id": "20260720T220144Z-plamp8-split-box-baf75d9-a1b2c3",
  "part": "plamp8",
  "status": "running",
  "created_at": "2026-07-21T08:01:44Z",
  "updated_at": "2026-07-21T08:01:44Z",
  "started_at": "2026-07-21T08:01:44Z",
  "finished_at": null,
  "source": {
    "repository_root": "/absolute/repository/path",
    "scad_path": "things/plamp8/plamp8.scad",
    "part_directory": "things/plamp8",
    "commit": "full-commit-or-null",
    "revision": "baf75d9",
    "content_hash": "sha256",
    "dirty": false
  },
  "selection": {
    "preset": "split-box",
    "views": [],
    "defines": {},
    "view_defines": {}
  },
  "metadata": {},
  "preset_tree": [],
  "openscad_version": "OpenSCAD version string",
  "jobs": []
}
```

Each job entry has exact fields `artifact_id`, `fingerprint`, `view`, `variant_name`, `preset_paths`, `variables`, `raw_defines`, `status`, `queued_at`, `started_at`, `finished_at`, `elapsed_seconds`, `command`, `artifact`, `artifact_bytes`, `log`, `exit_code`, `echoes`, `messages`, `warnings`, `errors`, and `geometry`. `geometry` has nullable `render_seconds`, `simple`, `vertices`, `facets`, and `volumes`. Artifact and log paths are relative to the run directory.

Write outputs to temporary artifact paths and rename only on exit zero with a non-empty file. Preserve complete logs on every exit. Capture `ECHO`, warning/error, render time, simple status, vertices, facets, and volumes without treating unknown output as failure. Generate `readme.md` from the manifest after each job so partial runs are human-readable.

- [ ] **Step 4: Verify GREEN and commit**

Run:

```bash
.venv/bin/python -m unittest tests.test_cad_metadata tests.test_cad_recipes tests.test_cad_generation -v
python3 -m py_compile plamp/cad_generation.py tests/test_cad_generation.py
git diff --check
git add plamp/cad_generation.py tests/test_cad_generation.py
git commit -m "Archive reproducible CAD generation runs"
```

Expected: all CAD engine tests pass without invoking real OpenSCAD.

---

### Task 4: Expose the engine through the direct Plamp CLI

**Files:**
- Create: `plamp/cad_cli.py`
- Modify: `plamp/cli.py`
- Create: `tests/test_cad_cli.py`
- Modify: `tests/test_plamp_direct_cli.py`

**Interfaces:**
- Adds `plamp cad views|validate|plan|menu|generate|runs|show|log`.
- `add_cad_parser(subparsers)` owns CAD arguments; `run_cad_command(args, context, stdin, stdout, stderr, dependencies)` returns an exit code.
- Text and `--json` render the same diagnostic/plan/manifest objects.

- [ ] **Step 1: Write failing CLI tests**

Cover help, part-name/path resolution, views with descriptions and assembly last, JSON diagnostics, validation without OpenSCAD, plan output/counts, repeatable views, preset/view conflict, menu selecting one preset or multiple views, generation injection, runs newest-first, show, log, and no traceback on errors.

```python
def test_cad_plan_json_does_not_call_openscad(self):
    rc = main(
        ["cad", "plan", "fixture", "--preset", "split", "--json"],
        env=self.runtime_env(root), stdout=stdout, stderr=stderr,
        cad_generate_func=lambda *a, **k: self.fail("must not render"),
    )
    self.assertEqual(rc, 0)
    self.assertEqual(json.loads(stdout.getvalue())["job_count"], 2)

def test_cad_menu_accepts_multiple_views(self):
    rc = run_cad_command(args, context, io.StringIO("2 4\n"), stdout, stderr, deps)
    self.assertEqual(selected.views, ("box", "assembly"))
```

- [ ] **Step 2: Run tests and verify RED**

Run: `.venv/bin/python -m unittest tests.test_cad_cli tests.test_plamp_direct_cli -v`

Expected: missing CAD parser/module failures.

- [ ] **Step 3: Implement command parsing and rendering**

Keep CAD streaming separate from the direct CLI's ordinary single-JSON result path. Add injectable CAD functions to `plamp.cli.main` for focused tests, dispatch `args.area == "cad"` before Pico/config logic, and convert `CadMetadataError`/generation failures to exit code 2 or 4 with stable diagnostics.

Use these selection rules:

```text
--preset NAME: exactly one preset
--view NAME: repeatable, no preset
no selector: default_preset when declared, otherwise one implicit-default job
--define NAME=EXPR: repeatable global override
--view-define VIEW:NAME=EXPR: repeatable per-view override
```

Menu displays presets first and described raw views second, with assembly last; it accepts one preset number or multiple view numbers and reprompts once on invalid input before returning a diagnostic.

- [ ] **Step 4: Verify GREEN and commit**

Run:

```bash
.venv/bin/python -m unittest tests.test_cad_metadata tests.test_cad_recipes tests.test_cad_generation tests.test_cad_cli tests.test_plamp_direct_cli -v
python3 -m py_compile plamp/cad_cli.py plamp/cli.py tests/test_cad_cli.py
git diff --check
git add plamp/cad_cli.py plamp/cli.py tests/test_cad_cli.py tests/test_plamp_direct_cli.py
git commit -m "Add local Plamp CAD commands"
```

Expected: CAD CLI and existing direct CLI tests pass.

---

### Task 5: Establish the direct generation and scaffolding interface

**Files:**
- Modify: `tests/test_things_cad_scripts.py`
- Modify: `tests/test_cad_cli.py`
- Modify: `docs/host-tools.md`

**Interfaces:**
- Every part is generated directly with `plamp cad generate PART`, where `PART` is a repository name or explicit SCAD path.
- Plamp8 fused-box generation uses `--preset fuse-box`.
- `plamp cad new PART [--template NAME]` creates metadata-valid source without overwriting existing files.

- [ ] **Step 1: Write direct-interface and scaffolding tests**

Require direct named-part and explicit-path generation with fake OpenSCAD, explicit output, dirty-source behavior, preview defines, `--preset fuse-box`, safe new-part creation, and named template selection. Remove assertions for hard-coded per-part generation arrays.

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```bash
.venv/bin/python -m unittest tests.test_cad_cli tests.test_things_cad_scripts -v
```

Expected: direct-generation and scaffolding assertions fail.

- [ ] **Step 3: Implement direct scaffolding and update documentation**

Implement project-neutral template discovery and safe creation behind `plamp cad new`. Update host documentation to show only direct validation, planning, named-view generation, preset generation, and new-part commands.

- [ ] **Step 4: Verify the direct interface and commit**

Run:

```bash
.venv/bin/python -m unittest tests.test_cad_cli tests.test_things_cad_scripts -v
git diff --check
git add plamp/cad_cli.py plamp/cad_scaffold.py tests/test_cad_cli.py \
  tests/test_things_cad_scripts.py docs/host-tools.md
git commit -m "Establish direct Plamp CAD interface"
```

Expected: all direct CAD and things source-contract tests pass.

---

### Task 6: Add Plamp8 recipes and preserve other-part generation defaults

**Files:**
- Modify: `things/plamp8/plamp8.scad`
- Modify: `things/plamp_stand/plamp_stand.scad`
- Modify: `things/iharvest_cover/iharvest_cover.scad`
- Modify: `things/3d_template/cad.scad`
- Modify: `things/3d_template/scad/flat_plate.scad`
- Modify: `things/3d_template/scad/positive_negative.scad`
- Modify: `tests/test_things_cad_scripts.py`
- Modify: `tests/test_cad_metadata.py`
- Modify: `tests/test_cad_recipes.py`

**Interfaces:**
- Plamp8 declares the agreed recipes and `split-box` default.
- Other existing/template SCAD files declare enough metadata to preserve current expected multi-view generation rather than silently changing to one implicit-default job.

- [ ] **Step 1: Write failing real-SCAD metadata/plan tests**

Assert Plamp8 preset names, descriptions, exact ordered expansion, nesting, default, component/top-panel/coupon membership, and synthetic counts. Assert Plamp Stand and iHarvest default recipes reproduce their current declared-view generation behavior. Assert template SCAD metadata validates.

```python
def test_plamp8_recipe_catalog_matches_print_workflows(self):
    document = parse_cad_document(REPO_ROOT / "things/plamp8/plamp8.scad")
    self.assertEqual(document.default_preset, "split-box")
    self.assertEqual(
        build_render_plan(document, Selection(preset="fuse-box"), source_identity="test").view_names,
        ("box", "top_panel", "sub_panel"),
    )
    self.assertEqual(
        document.presets["test-fit"].items,
        ("preset:component-floorplans", "preset:top-panel-fit", "preset:corner-coupons"),
    )
```

- [ ] **Step 2: Run tests and verify RED**

Run: `.venv/bin/python -m unittest tests.test_cad_metadata tests.test_cad_recipes tests.test_things_cad_scripts -v`

Expected: metadata blocks and recipe assertions fail.

- [ ] **Step 3: Add embedded recipe metadata**

Add Plamp8 presets:

```text
split-box (default): floor, north_south_walls, east_west_walls, top_panel, sub_panel
fuse-box: box, top_panel, sub_panel
assembly: assembly
component-floorplans: relay_footprint, psu_footprint, converter_footprint
top-panel-fit: ac_duplex_channel, dc_barrel_channel, usb_c_panel, c13_inlet
corner-coupons: panel_corner_fastener_test, corner_coupon, wall_corner_fastener_assembly
test-fit: component-floorplans, top-panel-fit, corner-coupons
```

Describe every Plamp8 view in the metadata overlay. Do not declare synthetic `all-views` or `all-presets` in JSON. Add simple `all-views` default presets to legacy/template parts only where needed to preserve existing no-selector behavior.

- [ ] **Step 4: Run complete verification and commit**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_cad_metadata tests.test_cad_recipes tests.test_cad_generation \
  tests.test_cad_cli tests.test_plamp_direct_cli tests.test_things_cad_scripts -v
python3 -m py_compile plamp/cad_metadata.py plamp/cad_recipes.py \
  plamp/cad_generation.py plamp/cad_cli.py plamp/cli.py
git diff --check
git add things/plamp8/plamp8.scad things/plamp_stand/plamp_stand.scad \
  things/iharvest_cover/iharvest_cover.scad things/3d_template/cad.scad \
  things/3d_template/scad/flat_plate.scad \
  things/3d_template/scad/positive_negative.scad \
  tests/test_things_cad_scripts.py tests/test_cad_metadata.py tests/test_cad_recipes.py
git commit -m "Describe versioned CAD generation recipes"
```

Expected: all listed tests pass, compilation succeeds, and the branch is clean except for the implementation-plan progress ledger.

---

### Task 7: Final integration documentation and command smoke tests

**Files:**
- Modify: `README.md`
- Modify: `docs/host-tools.md`
- Test: all CAD/direct CLI test modules

**Interfaces:**
- Documents stable commands, storage paths, fallback behavior, metadata location, plan-before-generate workflow, and new-part scaffolding.
- Does not document deferred web/Three.js features as implemented.

- [ ] **Step 1: Add documentation contract assertions where appropriate**

Require examples for `views`, `validate`, `plan`, `generate`, `runs`, and `show`; require `$PLAMP_DATA_DIR/cad/prints`; require the plan-before-generate recommendation; reject claims of web generation or Three.js support.

- [ ] **Step 2: Run documentation tests and verify RED**

Run: `.venv/bin/python -m unittest tests.test_things_cad_scripts tests.test_plamp_direct_cli -v`

Expected: new documentation assertions fail before documentation changes.

- [ ] **Step 3: Document the completed Plate 1 workflow**

Include a concise workflow:

```bash
plamp cad views plamp8
plamp cad validate plamp8
plamp cad plan plamp8 --preset fuse-box
plamp cad generate plamp8 --preset fuse-box
plamp cad runs plamp8
plamp cad show RUN_ID
```

Explain that generation may take minutes on a Pi, artifacts are instance data, OpenSCAD echoes are archived, and `plan` never renders.

- [ ] **Step 4: Run final fresh verification and commit**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_cad_metadata tests.test_cad_recipes tests.test_cad_generation \
  tests.test_cad_cli tests.test_plamp_direct_cli tests.test_things_cad_scripts -v
python3 -m py_compile plamp/cad_metadata.py plamp/cad_recipes.py \
  plamp/cad_generation.py plamp/cad_cli.py plamp/cli.py
git diff --check
git status --short
git add README.md docs/host-tools.md
git commit -m "Document versioned CAD generation"
```

Expected: every listed test passes, compilation and diff checks are clean, and only the ignored SDD ledger remains outside commits.
