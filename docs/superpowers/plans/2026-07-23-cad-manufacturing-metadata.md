# CAD Manufacturing Profiles and Slicing Metadata Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic CAD-variable profiles, full value provenance, portable slicing requirements/recommendations, separate geometry/manufacturing fingerprints, and human README guidance.

**Architecture:** `cad_profiles` loads versioned system and instance-local profile overlays plus local defaults; `cad_manufacturing` normalizes and merges portable slicing directives with hard-conflict detection. `cad_planning` resolves profiles before structural product overrides, records every winning variable source, and emits both geometry and manufacturing identities for `cad_generation` to archive and explain.

**Tech Stack:** Python 3.11 standard library, frozen dataclasses, JSON, SHA-256, `argparse`, `unittest`

## Global Constraints

- This plan depends on completion of `2026-07-23-cad-system-catalog.md`.
- SCAD owns canonical variable definitions/defaults and Customizer constraints; external files only assign values.
- Low-to-high CAD precedence is SCAD source, model, set, ordered profiles, deepest product outward to selected top-level product, corresponding item at each layer, then CLI.
- Profile order is local defaults, top-level product, root-to-leaf product/items, model/set, then repeatable CLI profiles; later profiles win scalar profile conflicts.
- System and local profile IDs are separate (`system:name`, `local:name`); a short name is accepted only when unambiguous.
- `--no-default-profiles` disables instance defaults; every command prints selected profiles.
- Product/set hard manufacturing constraints cannot be weakened by profiles.
- Slicing metadata is portable advice in sidecars/manifests/READMEs; do not emit vendor profiles or 3MF.
- `required`/`forbidden` conflicts fail planning with both provenance paths.
- Slicing-only changes preserve geometry reuse but change the manufacturing fingerprint and README.
- Initial keys are orientation, supports, support style, ironing, material, layer height, perimeter/wall minimum, adhesion/brim, and ordered notes.

---

### Task 1: Load system and local profiles plus human defaults

**Files:**
- Create: `plamp/cad_profiles.py`
- Create: `tests/test_cad_profiles.py`
- Modify: `plamp/cad_system.py`
- Modify: `tests/test_cad_system.py`

**Interfaces:**
- Produces `CadProfileError`, `CadProfile`, `CadPreferences`,
  `load_system_profiles()`, `discover_local_profiles()`, `load_preferences()`,
  `resolve_profile_ids()`, and `profile_content_hash()`.
- Local profiles live at `$PLAMP_DATA_DIR/cad/profiles/*.json`; preferences live at `$PLAMP_DATA_DIR/cad/preferences.json`.
- `CadSystem.profiles` becomes `Mapping[str, CadProfile]` after loading.

- [ ] **Step 1: Write failing profile schema and resolution tests**

```python
def test_resolves_namespaces_defaults_and_explicit_profiles_in_order(self):
    system_profiles = {"draft": self.profile("draft", "quality")}
    local_profiles = {"x1c": self.profile("x1c", "printer", local=True)}
    result = resolve_profile_ids(
        system_profiles, local_profiles,
        defaults=("local:x1c",), requested=("system:draft",),
        use_defaults=True,
    )
    self.assertEqual(tuple(profile.qualified_id for profile in result),
                     ("local:x1c", "system:draft"))

def test_ambiguous_short_name_requires_qualified_id(self):
    with self.assertRaisesRegex(CadProfileError, "system:petg.*local:petg"):
        resolve_profile_ids(self.system_petg, self.local_petg,
                            defaults=(), requested=("petg",), use_defaults=True)
```

Cover strict keys/schema/kinds, finite typed CAD values, separate namespaces, stable hashes, absent preferences, malformed local files, default system/profile mappings, `--no-default-profiles`, and missing profile diagnostics.

- [ ] **Step 2: Run tests and verify RED**

Run: `.venv/bin/python -m unittest tests.test_cad_profiles -v`

Expected: FAIL because `plamp.cad_profiles` does not exist.

- [ ] **Step 3: Implement typed profile and preference loaders**

```python
@dataclass(frozen=True)
class CadProfile:
    name: str
    qualified_id: str
    kind: str
    path: Path
    cad: Mapping[str, object]
    slicing: Mapping[str, object]
    machine: Mapping[str, object]
    content_hash: str

@dataclass(frozen=True)
class CadPreferences:
    default_system: str | None = None
    default_profiles: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
```

Use schemas `plamp-cad-profile/1` and `plamp-cad-preferences/1`. Profile kinds are exactly `printer`, `nozzle`, `material`, and `quality`. Hash canonical JSON bytes with sorted keys and compact separators. Preferences use:

```json
{
  "schema": "plamp-cad-preferences/1",
  "default_system": "plamp",
  "default_profiles": {"plamp": ["local:x1c", "system:petg"]}
}
```

Missing preference/local profile directories produce empty defaults; malformed present files produce CAD diagnostics rather than being ignored.

- [ ] **Step 4: Verify GREEN and commit**

Run:

```bash
.venv/bin/python -m unittest tests.test_cad_profiles tests.test_cad_system -v
python3 -m py_compile plamp/cad_profiles.py tests/test_cad_profiles.py
git diff --check
git add plamp/cad_profiles.py plamp/cad_system.py tests/test_cad_profiles.py tests/test_cad_system.py
git commit -m "Load CAD manufacturing profiles"
```

---

### Task 2: Parse SCAD defaults and resolve variable provenance

**Files:**
- Modify: `plamp/cad_model.py`
- Modify: `plamp/cad_values.py`
- Modify: `plamp/cad_planning.py`
- Modify: `tests/test_cad_model.py`
- Modify: `tests/test_cad_planning.py`

**Interfaces:**
- `CadModel.source_defaults` contains supported top-level literal Customizer assignments before the first module/function body.
- Produces `VariableLayer`, `ResolvedVariable`, and `resolve_variables()` and
  replaces Plan 1's winner-only `VariableSource` values.
- `RenderJob.variable_sources` records the ordered contributors and winner for every externally resolved variable.

- [ ] **Step 1: Write failing default parser and precedence tests**

```python
def test_parses_supported_customizer_literal_defaults(self):
    model = self.load_source('''
render_fn = 96; // [12:4:128]
render_text = true;
label = "normal";
offset = [1, 2, 3];
set = ""; // [floor]
module floor_set() { cube(1); }
''')
    self.assertEqual(model.source_defaults, {
        "render_fn": 96, "render_text": True,
        "label": "normal", "offset": [1, 2, 3], "set": "",
    })

def test_exact_precedence_and_provenance(self):
    job = self.plan_every_layer().jobs[0]
    self.assertEqual(job.variables["clearance"], 0.45)
    resolved = job.variable_sources["clearance"]
    self.assertEqual(tuple(layer.kind for layer in resolved.layers),
        ("scad", "model", "set", "profile", "product", "item", "cli"))
    self.assertEqual(resolved.winner.kind, "cli")
```

Cover booleans, strings, finite numbers, vectors, `undef`, unsupported expressions remaining source-owned/unresolved, typed values replacing lower raw values and vice versa, root-to-leaf profile order, deepest-to-outer product order, item locality, and CLI finality.

- [ ] **Step 2: Run tests and verify RED**

Run: `.venv/bin/python -m unittest tests.test_cad_model tests.test_cad_planning -v`

Expected: missing `source_defaults` and profile/provenance failures.

- [ ] **Step 3: Implement literal parsing and a single layer resolver**

```python
@dataclass(frozen=True)
class VariableLayer:
    kind: str
    source_id: str
    value: object | None = None
    raw_expression: str | None = None

@dataclass(frozen=True)
class ResolvedVariable:
    name: str
    layers: tuple[VariableLayer, ...]

    @property
    def winner(self) -> VariableLayer:
        return self.layers[-1]

def resolve_variables(layers: Sequence[tuple[str, str, Mapping[str, object], Mapping[str, str]]]):
    typed: dict[str, object] = {}
    raw: dict[str, str] = {}
    history: dict[str, list[VariableLayer]] = {}
    for kind, source_id, typed_values, raw_values in layers:
        for name, value in typed_values.items():
            typed[name] = value
            raw.pop(name, None)
            history.setdefault(name, []).append(
                VariableLayer(kind, source_id, value=value)
            )
        for name, expression in raw_values.items():
            raw[name] = expression
            typed.pop(name, None)
            history.setdefault(name, []).append(
                VariableLayer(kind, source_id, raw_expression=expression)
            )
    provenance = {
        name: ResolvedVariable(name, tuple(assignments))
        for name, assignments in history.items()
    }
    return typed, raw, provenance
```

Keep the history when typed/raw forms replace each other. Parse only literal
assignments with a small tokenizer; never evaluate Python or arbitrary SCAD
expressions. Exclude `set` from emitted overrides because the job selector owns
it.

- [ ] **Step 4: Verify GREEN and commit**

Run:

```bash
.venv/bin/python -m unittest tests.test_cad_model tests.test_cad_profiles tests.test_cad_planning -v
python3 -m py_compile plamp/cad_model.py plamp/cad_values.py plamp/cad_planning.py
git diff --check
git add plamp/cad_model.py plamp/cad_values.py plamp/cad_planning.py tests/test_cad_model.py tests/test_cad_planning.py
git commit -m "Resolve CAD variables with provenance"
```

---

### Task 3: Normalize and merge portable slicing directives

**Files:**
- Create: `plamp/cad_manufacturing.py`
- Create: `tests/test_cad_manufacturing.py`
- Modify: `plamp/cad_model.py`
- Modify: `plamp/cad_system.py`

**Interfaces:**
- Produces `ManufacturingConflict`, `DirectiveSource`, `SlicingDirective`,
  `ManufacturingPolicy`, `normalize_slicing()`, `merge_manufacturing()`, and
  `manufacturing_fingerprint()`.
- Plain `required`/`forbidden` recommendation values normalize as hard requirements; `recommended`/`discouraged`/`optional` normalize as preferences.
- Scalar directives default to preference strength unless represented as
  `{"value": "as-exported", "strength": "required"}` (or the corresponding
  typed scalar value).

- [ ] **Step 1: Write failing normalization/conflict tests**

```python
def test_profile_cannot_weaken_product_support_requirement(self):
    policy = merge_manufacturing((
        self.layer("product:box", {"supports": "required"}),
        self.layer("profile:draft", {"supports": "discouraged"}),
    ))
    self.assertEqual(policy.directives["supports"].value, "required")
    self.assertEqual(policy.directives["supports"].source.id, "product:box")

def test_conflicting_hard_requirements_report_both_sources(self):
    with self.assertRaises(ManufacturingConflict) as caught:
        merge_manufacturing((
            self.layer("set:top", {"supports": "forbidden"}),
            self.layer("product:complete", {"supports": "required"}),
        ))
    self.assertEqual(caught.exception.sources, ("set:top", "product:complete"))
```

Cover all portable keys, allowed vocabularies, explicit strength objects, ordered notes, later preference wins, hard-over-preference behavior, numeric layer height/perimeter validation, unknown keys, and stable manufacturing hashes.

- [ ] **Step 2: Run tests and verify RED**

Run: `.venv/bin/python -m unittest tests.test_cad_manufacturing -v`

Expected: FAIL because `plamp.cad_manufacturing` does not exist.

- [ ] **Step 3: Implement directive normalization and merging**

```python
@dataclass(frozen=True)
class SlicingDirective:
    key: str
    value: object
    strength: str  # "requirement" or "preference"
    source: DirectiveSource

@dataclass(frozen=True)
class ManufacturingPolicy:
    directives: Mapping[str, SlicingDirective]
    notes: tuple[tuple[str, str], ...]
    fingerprint: str
```

Normalize `supports` and `ironing` vocabularies, `orientation`, `support_style`, `material`, positive `layer_height`, positive integer `minimum_perimeters`, `adhesion`, and string-note arrays. During merge, two unequal requirements for one key raise `ManufacturingConflict`; a requirement always survives a preference; otherwise the later preference wins. Keep all notes in layer order with source IDs.

- [ ] **Step 4: Verify GREEN and commit**

Run:

```bash
.venv/bin/python -m unittest tests.test_cad_manufacturing tests.test_cad_model tests.test_cad_system -v
python3 -m py_compile plamp/cad_manufacturing.py
git diff --check
git add plamp/cad_manufacturing.py plamp/cad_model.py plamp/cad_system.py tests/test_cad_manufacturing.py
git commit -m "Merge portable CAD slicing guidance"
```

---

### Task 4: Integrate profiles and manufacturing policy into planning

**Files:**
- Modify: `plamp/cad_planning.py`
- Modify: `tests/test_cad_planning.py`
- Modify: `plamp/cad_cli.py`
- Modify: `tests/test_cad_cli.py`

**Interfaces:**
- `CadSelection` adds `profiles: tuple[str, ...]` and `use_default_profiles: bool`.
- `RenderJob` adds `profiles`, `manufacturing`, `geometry_fingerprint`, and
  `manufacturing_fingerprint`; remove the old `fingerprint` field and update all
  callers in this task.
- CLI adds repeatable `--profile` and `--no-default-profiles` to plan/generate/menu.

- [ ] **Step 1: Write failing integrated planning/CLI tests**

```python
def test_slicing_only_profile_preserves_geometry_fingerprint(self):
    plain = self.plan(profiles=()).jobs[0]
    ironing = self.plan(profiles=("system:ironing",)).jobs[0]
    self.assertEqual(plain.geometry_fingerprint, ironing.geometry_fingerprint)
    self.assertNotEqual(plain.manufacturing_fingerprint,
                        ironing.manufacturing_fingerprint)

def test_cli_prints_resolved_profiles_and_support_advice(self):
    output = self.run_text(["cad", "plan", "box", "--set", "top",
                            "--profile", "draft"])
    self.assertIn("Profiles: system:draft", output)
    self.assertIn("Supports: forbidden", output)
```

Cover default profile insertion/removal, product/item profile order, ambiguous short IDs, profile CAD values before products, hard conflicts as CAD2xx planning errors, JSON provenance, and fingerprint separation.

Also update `_selected_system()` to consult
`load_preferences(context.data_dir).default_system` after an explicit `--system`
and before one-system/interactive resolution. An invalid configured default must
name the preferences file and show the `plamp cad systems` choices.

- [ ] **Step 2: Run tests and verify RED**

Run: `.venv/bin/python -m unittest tests.test_cad_planning tests.test_cad_cli -v`

Expected: missing selection fields/options and fingerprint failures.

- [ ] **Step 3: Resolve the exact leaf-layer order**

For every expanded leaf, build profiles in this order:

```python
profile_ids = (
    default_profile_ids
    + selected_product_profiles
    + root_to_leaf_product_and_item_profiles
    + model_and_set_profile_ids
    + selection.profiles
)
```

Then apply variable layers as SCAD, model, set, ordered profiles, deepest product/item outward, CLI. Merge manufacturing in provenance order but mark product/set hard directives so later profile preferences cannot weaken them. Geometry hash includes selected profile hashes only when their `cad` namespace contributes an effective value; manufacturing hash includes every selected profile hash and resolved slicing policy.

- [ ] **Step 4: Add CLI options and verify GREEN**

Run:

```bash
.venv/bin/python -m unittest tests.test_cad_profiles tests.test_cad_manufacturing tests.test_cad_planning tests.test_cad_cli -v
python3 -m py_compile plamp/cad_planning.py plamp/cad_cli.py
git diff --check
git add plamp/cad_planning.py plamp/cad_cli.py tests/test_cad_planning.py tests/test_cad_cli.py
git commit -m "Apply profiles to CAD plans"
```

---

### Task 5: Archive provenance and render human manufacturing READMEs

**Files:**
- Modify: `plamp/cad_generation.py`
- Modify: `tests/test_cad_generation.py`
- Create: `plamp/cad_readme.py`
- Create: `tests/test_cad_readme.py`

**Interfaces:**
- `render_run_readme(manifest) -> str` is pure and deterministic.
- Job manifests record variable layers/winner, profile IDs/kinds/hashes, resolved manufacturing policy, geometry fingerprint, and manufacturing fingerprint.
- Duplicate geometry may be reused only when the archived artifact matches the geometry fingerprint; README/manifest are regenerated for changed manufacturing metadata.

- [ ] **Step 1: Write failing manifest/reuse/README tests**

```python
def test_readme_leads_with_artifacts_and_plain_slicing_guidance(self):
    text = render_run_readme(self.manifest(ironing="recommended",
                                           supports="forbidden"))
    self.assertIn("Enable ironing", text)
    self.assertIn("Do not generate supports", text)
    self.assertLess(text.index("Artifacts"), text.index("Variable provenance"))

def test_slicing_change_reuses_stl_but_rewrites_metadata(self):
    first = self.generate(profile="plain")
    second = self.generate(profile="ironing")
    self.assertEqual(self.openscad_calls, 1)
    self.assertNotEqual(first.manufacturing_fingerprint,
                        second.manufacturing_fingerprint)
```

Also cover orientation, support style, material, layer height, perimeter/adhesion advice, ordered notes, requirement wording, missing advice, full provenance JSON, and artifact checksum/help commands.

- [ ] **Step 2: Run tests and verify RED**

Run: `.venv/bin/python -m unittest tests.test_cad_readme tests.test_cad_generation -v`

Expected: missing renderer and old manifest schema failures.

- [ ] **Step 3: Implement pure README rendering and manifest fields**

```python
def render_run_readme(manifest: Mapping[str, object]) -> str:
    lines = [f"# CAD run {manifest['run_id']}", "", "## Artifacts", ""]
    lines.extend(("| Artifact | Model / set | Status |", "| --- | --- | --- |"))
    jobs = manifest.get("jobs", [])
    for job in jobs:
        lines.append(
            f"| {job['artifact_id']} | {job['model']} / "
            f"{job['set'] or '(default)'} | {job['status']} |"
        )
    for job in jobs:
        lines.extend(("", f"## {job['artifact_id']}", "", "Recommended slicing:", ""))
        directives = job.get("manufacturing", {}).get("directives", {})
        if directives.get("orientation", {}).get("value") == "as-exported":
            lines.append("- Use the exported orientation.")
        if directives.get("ironing", {}).get("value") == "recommended":
            lines.append("- Enable ironing.")
        if directives.get("supports", {}).get("value") == "forbidden":
            lines.append("- Do not generate supports.")
        for source_id, note in job.get("manufacturing", {}).get("notes", []):
            lines.append(f"- {note} ({source_id})")
    lines.extend((
        "", "## Inspection", "",
        "- Open `manifest.json` for profiles and variable provenance.",
        "- Open `logs/` for OpenSCAD output.",
        "- Open `source/` for the archived source.",
    ))
    return "\n".join(lines) + "\n"
```

Replace the inline `_write_readme()` composition with this pure renderer. Add a geometry-artifact lookup keyed by model/source identity plus `geometry_fingerprint`; hard-link or copy the prior STL into the new run while still creating fresh logs/manifest/README entries that state the reused run/artifact. Do not reuse failed or missing artifacts.

Include `manufacturing_fingerprint` in the complete run identity. A changed
slicing recommendation therefore creates a distinct run (and cannot trigger the
same-data regeneration prompt) while reusing the matching geometry artifact.

- [ ] **Step 4: Verify GREEN and commit**

Run:

```bash
.venv/bin/python -m unittest tests.test_cad_readme tests.test_cad_generation tests.test_cad_planning -v
python3 -m py_compile plamp/cad_readme.py plamp/cad_generation.py
git diff --check
git add plamp/cad_readme.py plamp/cad_generation.py tests/test_cad_readme.py tests/test_cad_generation.py
git commit -m "Archive CAD manufacturing guidance"
```

---

### Task 6: Add initial versioned profiles/guidance, document, and verify

**Files:**
- Create: `cad/profiles/draft.json`
- Modify: `cad/plamp.system.cad.json`
- Modify: `things/plamp8/plamp8.cad.json`
- Modify: `things/iharvest_cover/iharvest_cover.cad.json`
- Modify: `things/plamp_stand/plamp_stand.cad.json`
- Modify: `docs/host-tools.md`
- Modify: `tests/test_things_cad_scripts.py`
- Modify: `tests/test_cad_profiles.py`

**Interfaces:**
- `system:draft` sets only geometry quality (`render_fn`, `render_text`) and portable draft advice; it contains no guessed printer calibration.
- Existing printable sets receive verified orientation/support/ironing guidance; non-printable assembly sets remain `printable: false`.

- [ ] **Step 1: Write failing repository metadata tests**

```python
def test_plamp8_top_panel_recommends_ironing_without_supports(self):
    model = load_model("plamp8", PLAMP8_SIDECAR, REPO_ROOT)
    policy = normalize_slicing(model.sets["top_panel"].slicing,
                               source_id="set:plamp8/top_panel")
    self.assertEqual(policy["ironing"].value, "recommended")
    self.assertEqual(policy["supports"].value, "forbidden")
```

Add tests for draft profile schema, assembly non-printability, and docs covering profiles, local defaults, `--no-default-profiles`, and README advice.

- [ ] **Step 2: Add only known manufacturing guidance**

Use metadata already established by current print workflows. Do not invent printer dimensions, material shrinkage, support requirements, or layer heights. Put workstation-specific adjustments in documented local-profile examples under `$PLAMP_DATA_DIR`, not committed JSON.

- [ ] **Step 3: Run focused and full verification**

Run:

```bash
.venv/bin/python -m unittest tests.test_cad_profiles tests.test_cad_manufacturing tests.test_cad_planning tests.test_cad_readme tests.test_cad_generation tests.test_cad_cli tests.test_things_cad_scripts -v
.venv/bin/python -m unittest discover -s tests -v
python3 -m py_compile plamp/cad_*.py tests/test_cad_*.py
git diff --check
git status --short
```

Expected: all tests pass and only this slice's intended files are changed.

- [ ] **Step 4: Commit the completed manufacturing slice**

```bash
git add cad/profiles cad/plamp.system.cad.json things/*/*.cad.json docs/host-tools.md tests
git commit -m "Add CAD manufacturing profiles and guidance"
```
