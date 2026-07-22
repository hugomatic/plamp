# Single CAD Interface and Repo Skill Installation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `plamp cad` the sole CAD generation interface and ship one canonical, safely installable agent knowledge tree containing everything a Plamp kit buyer's agent needs to set up, operate, maintain, and troubleshoot the system.

**Architecture:** Keep the existing Python CAD parser, recipe engine, renderer, metadata, and CLI behavior unchanged while deleting every alternate CAD entry point and mention. Move operating documentation into focused skills under `agent/`, retain old documentation paths as minimal forwarding pages, and expose a root `AGENTS.md` router. Install skills through a stdlib-only, registry-managed symlink tool that plans before writing, protects unrelated state, and integrates with bootstrap/upgrade only after explicit opt-in.

**Tech Stack:** Python 3.11 standard library, Bash, Git, OpenSCAD CLI contract, `unittest`

## Global Constraints

- `plamp cad` is the only documented and tracked CAD generation interface.
- Delete the legacy generator file from each of `things/3d_template/`, `things/iharvest_cover/`, `things/plamp8/`, and `things/plamp_stand/`.
- No tracked filename or text contains either retired shell entry-point name; final `git grep` gates use `generate[.]bash` and `template[.]bash`, each with expected exit status 1.
- Preserve all current `plamp cad` behavior, metadata, source snapshots, recipes, revision handling, explicit output support, manifests, and archives.
- `plamp cad new PART [--template NAME]` is the sole part scaffolder; it discovers templates from repository convention rather than hard-coded project names and creates one metadata-valid `<PART>.scad` without overwriting anything.
- Convert the Plamp Stand manual render check to direct `plamp cad`; do not run real Plamp8 renders.
- OpenSCAD integration tests use only a fake executable.
- Repository `agent/skills/*/SKILL.md` directories are authoritative; installation creates direct links under `${CODEX_HOME:-$HOME/.codex}/skills`.
- Canonical kit-agent skills are `plamp-workflow`, `plamp-setup`, `plamp-operate`, `plamp-pico`, `plamp-troubleshoot`, and `openscad-cad`.
- Agent-facing operating documents move into those skills' `references/` directories; their current public Markdown paths become minimal title-plus-link forwarding pages so GitHub, raw downloads, Windows, and archives remain usable without duplicated operating prose.
- Keep `agent/check_alive.bash`, `agent/check_daily.md`, and `agent/check_weekly.md canonical in place. Keep executable scripts, source/API truth, `CHECKLIST.md`, and `docs/superpowers/**` out of installed skill references except for the required stale CAD-name cleanup.
- Root `AGENTS.md` is a relative symlink to canonical `agent/AGENTS.md`. Root `README.md` remains the concise human landing page and links to canonical agent material rather than duplicating operating procedures.
- Skill installation never reads, creates, replaces, or removes `.system`, and preserves unrelated local skills such as `plamp-workflow`.
- Skill installation is idempotent, plans all changes before writing, and must refuse an unknown stale/mismatched destination; explicit migration backs up content and never deletes it.
- `setup.sh` never mutates Codex state. Bootstrap installs agent skills only with `--install-agent-skills`; `plampctl upgrade` synchronizes only an existing Plamp-managed registry.
- Use `apply_patch` for textual tracked edits and explicit `ln -s` only for required symlinks. Commit and push after each reviewed task.

## File map

- `plamp/cad_scaffold.py`: project-neutral template discovery and atomic safe part creation.
- `plamp/cad_cli.py`: `cad new`, template listing, humane text, and structured JSON command boundary.
- `tests/test_things_cad_scripts.py`: protect template output, repository-wide absence, metadata preservation, and fake-OpenSCAD direct generation.
- `things/plamp_stand/check_generates_stl_files_from_scad.bash`: retain the manual STL smoke check while invoking `plamp cad generate` directly.
- `README.md`: concise human landing page linking to canonical `agent/` references.
- `agent/AGENTS.md`, `agent/README.md`: canonical automatic agent router and browser-facing knowledge index.
- `agent/skills/{plamp-workflow,plamp-setup,plamp-operate,plamp-pico,plamp-troubleshoot,openscad-cad}`: focused canonical skills and operating references.
- `docs/spec-current.md`, `docs/host-tools.md`, `plamp_cli/README.md`, `plamp_web/README.md`, `pico_scheduler/README.md`, `things/README.md`, and `things/plamp_stand/README.md`: compatibility forwarding pages containing only a title and canonical link.
- `agent/skills/openscad-cad/SKILL.md`, `agent/skills/openscad-cad/references/plamp-things.md`: authoritative agent workflow with no alternate interface.
- Historical plan/spec files listed in Task 5: accurate archival wording and direct commands, with no stale entry-point references.
- `agent/install-skills`: safe, idempotent registry-managed discovery/linking of every immediate repository skill directory containing `SKILL.md`.
- `tests/test_agent_docs.py`: canonical-document, forwarding-page, root-agent-symlink, skill-schema, and Markdown-link contract.
- `tests/test_agent_skills.py`: isolated installer tests using temporary repositories/checkouts and Codex-home paths.

---

### Task 1: Fix named, race-safe `plamp cad new` scaffolding

**Starting point:** Commit `8c13b09` added the command and discovery surface, but its byte-for-byte copy contract failed review. This fix wave implements the approved `docs/superpowers/specs/2026-07-21-named-cad-scaffold-design.md` and replaces those obsolete copy assertions with named-template substitution.

**Files:**
- Modify: `plamp/cad_scaffold.py`
- Modify: `plamp/cad_cli.py`
- Modify: `things/3d_template/cad.scad`
- Modify: `things/3d_template/scad/flat_plate.scad`
- Modify: `things/3d_template/scad/positive_negative.scad`
- Modify: `tests/test_cad_scaffold.py`
- Modify: `tests/test_cad_cli.py`

**Interfaces:**
- Preserve `discover_templates(repo_root: Path) -> tuple[CadTemplate, ...]`, `create_part(repo_root: Path, part_name: str, template_name: str) -> CreatedPart`, `plamp cad new PART [--template NAME] [--json]`, and `plamp cad new --list-templates [--json]`.
- Derive the OpenSCAD identifier with `part_identifier = part_name.replace("-", "_")`; require `[A-Za-z_][A-Za-z0-9_]*`, while the directory and exact `<PART>.scad` filename retain the requested spelling.
- Every selectable template uses only the reserved token `__PLAMP_PART__` for the part-named view/module stem; creation replaces every exact occurrence and performs no other rewriting.
- Selection/contract errors remain CAD200 `invalid_selection` with exit 2. Unanticipated `OSError`/I/O failures are CAD400 `operation_failed` with exit 4.

- [ ] **Step 1: Replace the obsolete copy test with failing named-output tests**

Delete `test_success_copies_exact_bytes_to_exact_part_scad_path`. Add tests for both `pump_bracket` and `pump-bracket`; the latter must create `things/pump-bracket/pump-bracket.scad` while both generate identifier `pump_bracket`. Parse the result and assert:

```python
self.assertEqual(document.default_view, "pump_bracket")
self.assertEqual(document.views, ("pump_bracket", "assembly"))
self.assertEqual(
    document.presets[document.default_preset].items,
    ("view:pump_bracket", "view:assembly"),
)
```

Assert metadata contains entries for both views and at least one preset. Assert exact declarations `module pump_bracket_positive()`, `module pump_bracket_negative()`, and `module pump_bracket()`; no `module part(`, `module part_positive(`, or `module part_negative(` remains. Assert the part view and assembly path each call `pump_bracket()`.

- [ ] **Step 2: Add failing geometry and BOM template-contract tests**

For all three selectable repository templates, require the reserved token in the default view, both declared view choices, both metadata view keys, both default-preset items, the positive/negative/composed module declarations, and both dispatch paths. After generation, isolate each named module body and assert:

```scad
echo("BOM", "M3x16 screw", 1);
```

appears inside `<id>_negative()` beside a `d = 3.4` centered cylinder whose height is the cube thickness plus Boolean overlap beyond both faces. Assert `<id>_positive()` contains a simple `cube`, and `<id>()` uses `difference()` to subtract the negative module from the positive module. Assembly initially renders that same composed module.

- [ ] **Step 3: Add failing naming, collision, and template-validation tests**

Retain path-safety cases and add: names beginning with a digit fail without mutation; hyphen-to-underscore identifiers pass; creating `pump-bracket` when sibling `things/pump_bracket/` exists (and the reverse) reports both requested/existing names plus shared stem; case remains significant. Before staging, reject invalid UTF-8, no reserved token, a leftover token after substitution, a missing required named-module declaration, generic `part*` aliases, missing/default-wrong view, anything other than exactly `<id>, assembly`, missing metadata for either view, no preset, default preset not containing both views in order, and a preset referencing an undeclared view. Every case leaves no destination or staging artifact.

- [ ] **Step 4: Add failing permission, race, and containment tests**

Create an executable (`0755`) source template and assert the generated SCAD has ordinary non-executable mode `0666 & ~umask`. Run creation under a controlled umask and assert the published directory is `0777 & ~umask`, never `tempfile`'s `0700`.

Inject a commit hook that creates the destination after preflight but immediately before publication. Assert creation raises `FileExistsError`, preserves the competing directory and sentinel byte-for-byte, and removes staging. This test must exercise the atomic no-replace primitive itself, not a second `exists()` check.

Add a template race test that discovers a contained template, replaces its path with a symlink to an outside file before read, and asserts failure without reading outside content or creating a destination. Open templates descriptor-relatively beneath the validated template root with `O_NOFOLLOW`; compare `fstat` identity with discovery and decode only bytes read from that descriptor.

- [ ] **Step 5: Add failing CLI operation-classification tests**

Keep unknown template, invalid name/identifier, normalized collision, invalid metadata/template contract, and existing destination as JSON CAD200/exit 2. Inject `PermissionError`, `ENOSPC`, and generic `OSError` from discovery, read, staging write, and commit; require JSON CAD400 with `kind: operation_failed`, exit 4, no traceback, and no partial destination. Do not classify raw operational `OSError` as a bad user selection.

- [ ] **Step 6: Run focused tests and verify RED**

```bash
.venv/bin/python -m unittest tests.test_cad_scaffold tests.test_cad_cli -v
```

Expected: failures show byte copying, generic module names, missing BOM/hole geometry, normalized-name acceptance, unsafe publication, `0700` staging permissions, executable-mode handling, symlink race exposure, and CAD200 misclassification of operational errors.

- [ ] **Step 7: Implement exact substitution and preflight validation**

Decode the securely opened template as UTF-8, require at least one `__PLAMP_PART__`, replace every exact token with the derived identifier, and reject any remainder. Validate source/substituted structure before mutation with focused helpers for identifier, sibling-stem collision, exact views, metadata/default preset, required modules, forbidden generic aliases, and dispatch. Preserve all template bytes except UTF-8 token substitution.

Rewrite all three repository templates to the same named contract. Use a centered cube in positive geometry; in negative geometry emit the exact BOM echo immediately before a centered `cylinder(d = 3.4, h = part_h + 2 * boolean_overlap, center = true)`; compose with `difference()`; dispatch both the named view and `assembly` to `__PLAMP_PART__()`.

- [ ] **Step 8: Implement ordinary permissions and atomic no-replace publication**

Create the random staging directory with `os.mkdir(path, 0o777)` beneath `things/` so the process umask supplies ordinary permissions; write the staged SCAD with exclusive create mode `0o666` rather than copying template mode. Validate the staged result.

Publish the complete directory with a platform no-replace rename helper: Linux uses `renameat2(..., RENAME_NOREPLACE)`, macOS uses `renamex_np(..., RENAME_EXCL)`, and an unsupported platform fails operationally rather than falling back to overwrite-capable `rename()`. Map `EEXIST` to the expected existing-destination selection error; preserve all other `OSError` values as operational failures. Always remove staging after failure.

- [ ] **Step 9: Fix CLI error boundaries and verify GREEN**

Convert expected scaffold validation/existence failures to a dedicated selection exception caught as CAD200/exit 2. Let operational filesystem failures reach the CAD400/exit-4 boundary. Then run:

```bash
.venv/bin/python -m unittest tests.test_cad_scaffold tests.test_cad_cli -v
python3 -m py_compile plamp/cad_scaffold.py plamp/cad_cli.py \
  tests/test_cad_scaffold.py tests/test_cad_cli.py
git diff --check
```

Expected: all focused tests pass without invoking OpenSCAD.

- [ ] **Step 10: Exercise generated output through CAD discovery and commit**

In a temporary Git repository, generate `pump-bracket`, then run the direct command boundary for `views`, `validate`, and `plan` against it. Assert ordered views `pump_bracket, assembly`, valid metadata/default preset, two planned jobs in that order, and zero OpenSCAD calls.

```bash
git add plamp/cad_scaffold.py plamp/cad_cli.py things/3d_template \
  tests/test_cad_scaffold.py tests/test_cad_cli.py
git commit -m "Generate named CAD part scaffolds"
git push origin feature/remove-generate-bash
```

---

### Task 2: Close direct CLI parity gaps before shell removal

**Files:**
- Modify: `plamp/cad_generation.py`
- Modify: `plamp/cad_cli.py`
- Modify: `tests/test_cad_generation.py`
- Modify: `tests/test_cad_cli.py`

**Interfaces:**
- Produces `resolve_openscad(explicit, *, env, system, which, home) -> Path` with strict precedence: explicit `--openscad`, `OPENSCAD_BIN`, `PATH`, then supported platform paths.
- Render argv explicitly requests ASCII STL.
- Legacy positional commit selection archives that commit and engraves its resolved short hash; explicit `--revision LABEL` keeps literal-label engraving semantics.
- Direct `generate --help` fully documents selection, definitions, source/revision, output/archive, preview, and executable resolution.

- [ ] **Step 1: Write failing executable-resolution tests**

Test the pure resolver with injected environment/platform/`which`: an executable explicit path or explicitly named command wins over every other source; invalid explicit selection fails without fallback; executable `OPENSCAD_BIN` is second and invalid env override fails; `PATH` is third; Darwin fallbacks are `/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD` then `$HOME/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD`; Linux fallbacks are `/usr/bin/openscad`, `/usr/local/bin/openscad`, `/snap/bin/openscad`, `/var/lib/flatpak/exports/bin/org.openscad.OpenSCAD`, then `$HOME/.local/share/flatpak/exports/bin/org.openscad.OpenSCAD`. Unsupported/missing cases return a humane error recommending `--openscad` or `OPENSCAD_BIN`.

Change `menu` and `generate` parser defaults for `--openscad` to `None`; resolve once at the command boundary and pass the resolved `Path` into generation. Tests must prove menu and generate share the same resolver.

- [ ] **Step 2: Write failing exact-argv and preview-order tests**

Update `test_exact_argv_uses_argument_list_and_effective_plan_values` to compare the complete argv, including exactly one adjacent pair:

```python
["--export-format", "asciistl"]
```

Keep the existing argument-list/no-shell guarantee. Place the export pair immediately before the final source path while preserving the existing `-o`, output, and ordered `-D` arguments; assert the manifest command and fake executable argv are identical.

Move preview parity to the direct CLI with:

```bash
plamp cad generate fixture --preview \
  --define render_fn=48 --define render_text=true --openscad FAKE --json
```

Assert preview defaults are inserted first (`render_fn=24`, `render_text=false`), later explicit definitions win, no `ball_quality` definition appears, and the effective manifest/argv contains `render_fn=48` and `render_text=true` exactly once.

- [ ] **Step 3: Write failing positional-commit versus literal-revision tests**

Create two commits touching a fixture part. For legacy positional `OUTPUT OLD_COMMIT`, assert archived source comes from the old commit while `source.revision`, STL naming, and `revision_string` use `git rev-parse --short OLD_COMMIT`, never the supplied long hash or token. For `--revision HEAD`, assert committed source resolves from HEAD but engraving remains literal `HEAD`; for dirty source with `--revision fit-test-1`, assert the current working copy is archived and literal `fit-test-1` is engraved. Keep the mutual-exclusion error for positional commit plus `--revision`.

Implement this distinction explicitly in source preparation, for example `prepare_source(..., revision_is_commit: bool = False)`: positional commit passes `True` and always derives the label from the resolved commit; `--revision` passes `False` and retains its supplied label even when it identifies historical source.

- [ ] **Step 4: Write failing comprehensive help tests**

Capture `plamp cad generate --help` and require examples/explanations for: mutually exclusive preset versus repeatable views; repeatable `--define NAME=EXPR` and `--view-define VIEW:NAME=EXPR` with later-wins precedence; dirty-source literal `--revision LABEL`; historical positional commit and short-hash engraving; default managed archive versus `--output DIR`; `--preview` defaults and explicit override order; and executable precedence `--openscad`, `OPENSCAD_BIN`, `PATH`, platform fallback. Keep help truthful if positional compatibility remains supported.

- [ ] **Step 5: Run RED, implement minimally, and verify GREEN**

Run RED before edits, then implement the resolver, revision-mode distinction, export argv, help text, and direct preview behavior. Verify:

```bash
.venv/bin/python -m unittest tests.test_cad_generation tests.test_cad_cli -v
python3 -m py_compile plamp/cad_generation.py plamp/cad_cli.py \
  tests/test_cad_generation.py tests/test_cad_cli.py
git diff --check
git add plamp/cad_generation.py plamp/cad_cli.py tests/test_cad_generation.py tests/test_cad_cli.py
git commit -m "Preserve direct CAD generation behavior"
git push origin feature/remove-generate-bash
```

Expected: all parity tests pass with fake executables only.

---

### Task 3: Remove both retired shell interfaces

**Files:**
- Delete: the legacy generator file in each of `things/3d_template/`, `things/iharvest_cover/`, `things/plamp8/`, and `things/plamp_stand/`
- Delete: the legacy scaffolder in `things/` matched by `template[.]bash`
- Modify: `tests/test_things_cad_scripts.py`

**Interfaces:**
- Consumes: tested `plamp cad new` from Task 1 and direct-generation parity from Task 2.
- Produces: no tracked per-part generator and no tracked shell scaffolder; new parts are created only through Python CLI.
- Does not modify CAD behavior or SCAD metadata.

- [ ] **Step 1: Replace wrapper-oriented tests with failing sole-interface tests**

Remove `make_wrapper_repo()` and the tests dedicated to wrapper delegation, argument translation, wrapper preview, and wrapper dirty-source behavior. Keep their direct CLI coverage in `tests/test_cad_cli.py`; do not duplicate the CAD engine tests.

Delete shell-scaffolder tests now covered by `tests/test_cad_scaffold.py` and `tests/test_cad_cli.py`.

Add one acceptance test that checks tracked filenames without embedding either forbidden literal in its own source:

```python
def test_retired_cad_shell_files_are_untracked(self):
    tracked = run(["git", "ls-files", "-z"], REPO_ROOT, check=True).stdout.split("\0")
    removed_names = {"generate" + ".bash", "template" + ".bash"}
    self.assertTrue(removed_names.isdisjoint(Path(path).name for path in tracked if path))
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_cad_cli.CadCliTests.test_new_part_json_reports_metadata_valid_output \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_retired_cad_shell_files_are_untracked -v
```

Expected: CLI scaffolding passes; the filename gate reports five retired tracked files.

- [ ] **Step 3: Delete all five retired shell entry points**

Delete the four part-local generators and the `things/` scaffolder with `apply_patch`. Do not alter template SCAD files or their embedded JSON; Task 1 discovers them directly.

- [ ] **Step 4: Verify GREEN and commit**

Run:

```bash
.venv/bin/python -m unittest tests.test_things_cad_scripts -v
git diff --check
```

Expected: the updated tests pass; no real OpenSCAD render runs.

Commit and push:

```bash
git add -A things tests/test_things_cad_scripts.py
git commit -m "Remove retired CAD shell interfaces"
git push origin feature/remove-generate-bash
```

---

### Task 4: Convert live documentation, the CAD skill, and the Stand smoke check

**Files:**
- Modify: `README.md`
- Modify: `things/README.md`
- Modify: `things/plamp_stand/README.md`
- Modify: `things/plamp_stand/check_generates_stl_files_from_scad.bash`
- Modify: `docs/host-tools.md`
- Modify: `CHECKLIST.md`
- Modify: `agent/skills/openscad-cad/SKILL.md`
- Modify: `agent/skills/openscad-cad/references/plamp-things.md`
- Modify: `tests/test_things_cad_scripts.py`

**Interfaces:**
- Consumes: `plamp cad new|views|validate|plan|generate|runs|show|log`; `new` accepts `--template`, `--list-templates`, and `--json`; `generate` accepts `--view`, `--preset`, `--revision`, `--preview`, and `--output`.
- Produces: one consistent human/agent workflow and a Stand check which writes its explicit-output run beneath a temporary directory.

- [ ] **Step 1: Add failing live-documentation and smoke-script source tests**

Extend `test_cad_documentation_covers_the_stable_local_workflow` to include the current README, `things` README, Stand README/check script, checklist, and both repo skill files. Assert each runnable CAD generation example contains `plamp cad`; assert the Stand script contains:

```python
self.assertIn("plamp cad generate plamp_stand", stand_check)
self.assertIn('--preset all-views-default', stand_check)
self.assertIn('--output "$outdir/out"', stand_check)
```

Also assert current new-part instructions use `plamp cad new PART --template NAME` and template discovery uses `plamp cad new --list-templates --json`. Task 5 adds the final repository-wide wording guard after historical records are migrated.

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_cad_documentation_covers_the_stable_local_workflow \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_retired_cad_shell_files_are_untracked -v
```

Expected: failures identify the stale live instructions and Stand check.

- [ ] **Step 3: Replace live instructions with direct commands**

Use this command vocabulary everywhere:

```bash
plamp cad new --list-templates --json
plamp cad new PART --template NAME --json
plamp cad views PART --json
plamp cad validate PART --json
plamp cad plan PART --preset PRESET --json
plamp cad generate PART --preset PRESET --json
```

Delete the skill's alternate/legacy-interface section entirely and remove that section from its contents list. Describe direct `plamp cad` as the only interface. In `docs/host-tools.md`, replace explicit-output examples with:

```bash
plamp cad generate plamp8 --view sub_panel --output prints/plamp8_sub_panel
plamp cad generate plamp8 --preset fuse-box --output prints/plamp8_fuse_box
plamp cad generate plamp8 --preview --view sub_panel --output prints/plamp8_preview --revision HEAD
```

Update the Stand smoke script to invoke the checkout launcher, skip clearly when it is unavailable, and render its declared preset:

```bash
plamp_bin="$REPO_ROOT/bin/plamp"
if [[ ! -x "$plamp_bin" ]]; then
  echo "SKIP: plamp launcher not found: $plamp_bin"
  exit 0
fi

"$plamp_bin" cad generate plamp_stand \
  --preset all-views-default \
  --revision "$commit" \
  --output "$outdir/out"
```

Update the expected artifact loop to include `tripod` because that preset contains `assembly`, `tripod`, `camera_clip`, and `plate`. Change the success text to name `plamp cad`, and keep the OpenSCAD-not-found skip.

- [ ] **Step 4: Verify fake generation, script syntax, and skill content**

Use the existing fake OpenSCAD helper tests; do not invoke the Stand script with real OpenSCAD:

```bash
.venv/bin/python -m unittest tests.test_cad_cli tests.test_things_cad_scripts -v
bash -n things/plamp_stand/check_generates_stl_files_from_scad.bash
git grep -n -I -e 'generate[.]bash' -e 'template[.]bash' -- \
  README.md CHECKLIST.md things docs/host-tools.md agent/skills
```

Expected: tests and syntax pass; `git grep` exits 1 with no output.

- [ ] **Step 5: Commit and push**

```bash
git add README.md things/README.md things/plamp_stand/README.md \
  things/plamp_stand/check_generates_stl_files_from_scad.bash \
  docs/host-tools.md CHECKLIST.md agent/skills/openscad-cad \
  tests/test_things_cad_scripts.py
git commit -m "Document plamp cad as the sole CAD interface"
git push origin feature/remove-generate-bash
```

---

### Task 5: Purge stale shell-interface references from historical plans and specs

**Files:**
- Modify: `docs/superpowers/specs/2026-05-13-plamp8-box-builder-design.md`
- Modify: `docs/superpowers/specs/2026-07-18-plamp8-flat-wall-enclosure-design.md`
- Modify: `docs/superpowers/specs/2026-07-20-cad-generation-recipes-design.md`
- Modify: `docs/superpowers/specs/2026-07-20-plamp8-support-free-wall-details-design.md`
- Modify: `docs/superpowers/plans/2026-05-13-plamp8-box-builder.md`
- Modify: `docs/superpowers/plans/2026-07-13-plamp8-xt60-switch-clearance.md`
- Modify: `docs/superpowers/plans/2026-07-17-plamp8-sub-panel-fit.md`
- Modify: `docs/superpowers/plans/2026-07-18-plamp8-flat-wall-enclosure.md`
- Modify: `docs/superpowers/plans/2026-07-19-plamp8-compass-assembly-labels.md`
- Modify: `docs/superpowers/plans/2026-07-19-plamp8-component-fit-and-cable-corridor.md`
- Modify: `docs/superpowers/plans/2026-07-19-plamp8-corner-spine-labels.md`
- Modify: `docs/superpowers/plans/2026-07-19-plamp8-ring-removal.md`
- Modify: `docs/superpowers/plans/2026-07-19-plamp8-simplified-corners.md`
- Modify: `docs/superpowers/plans/2026-07-20-cad-generation-recipes.md`
- Modify: `docs/superpowers/plans/2026-07-20-plamp8-fused-box-view.md`
- Modify: `docs/superpowers/plans/2026-07-20-plamp8-support-free-wall-details.md`
- Modify: `tests/test_things_cad_scripts.py`

**Interfaces:**
- Consumes: the current direct CLI flags documented in Task 4.
- Produces: historical context that remains accurate without advertising, requiring, testing, or naming a removed interface.

- [ ] **Step 1: Confirm the repository gate fails on historical documents**

Run:

```bash
git grep -n -I -e 'generate[.]bash' -e 'template[.]bash' -- docs/superpowers
```

Expected: nonzero output names every historical file listed above that mentions either retired shell interface.

- [ ] **Step 2: Apply the exact command migration rules**

First add the final textual acceptance test:

```python
def test_tracked_text_names_only_plamp_cad_interfaces(self):
    references = run(
        ["git", "grep", "-n", "-I", "-e", "generate[.]bash", "-e", "template[.]bash", "--"],
        REPO_ROOT,
    )
    self.assertEqual(references.returncode, 1, references.stdout + references.stderr)
```

Use `apply_patch` and preserve each document's historical design intent. Apply these transformations to every runnable example:

| Old intent | Direct replacement |
|---|---|
| one named view | `plamp cad generate plamp8 --view VIEW --output DIR` |
| preview one view | add `--preview` |
| fused box shortcut | `--preset fuse-box` |
| explicit engraved label | add `--revision LABEL` |
| exact committed source | add `--revision COMMIT` |
| syntax check of removed shell | `plamp cad validate plamp8 --json` followed by `plamp cad plan plamp8 ... --json` |
| default Plamp8 printable set | `plamp cad generate plamp8 --preset split-box` |
| create a new part from the default template | `plamp cad new PART` |
| create from a named template | `plamp cad new PART --template NAME` |
| discover available templates | `plamp cad new --list-templates --json` |

Where an obsolete command supplied both a friendly label and `HEAD`, retain the honest label and remove `HEAD`; direct `--revision` accepts one source/label value. Replace narrative statements about preserving or using the removed file with statements about preserving metadata, directory-specific revision identity, and using `plamp cad`. In the CAD recipes design/plan, revise the architecture and constraints from delegating wrappers to a single direct interface; remove wrapper file lists and wrapper-specific tests rather than pretending they still exist.

- [ ] **Step 3: Run the zero-reference and documentation tests**

Run:

```bash
git grep -n -I -e 'generate[.]bash' -e 'template[.]bash' --
.venv/bin/python -m unittest \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_tracked_text_names_only_plamp_cad_interfaces \
  tests.test_things_cad_scripts.ThingsCadScriptsTest.test_cad_documentation_covers_the_stable_local_workflow -v
git diff --check
```

Expected: `git grep` exits 1 without output; both tests pass; diff check is clean.

- [ ] **Step 4: Commit and push**

```bash
git add docs/superpowers/plans docs/superpowers/specs
git commit -m "Retire stale CAD generator references"
git push origin feature/remove-generate-bash
```

---

### Task 6: Move operating documentation into the canonical agent tree

**Files:**
- Create: `agent/skills/plamp-workflow/references/current-contract.md`
- Create: `agent/skills/plamp-setup/references/host-tools.md`, `installation.md`, `configuration.md`
- Create: `agent/skills/plamp-operate/references/rest-api.md`, `web-service.md`, `operations.md`
- Create: `agent/skills/plamp-pico/references/scheduler.md`, `hardware-and-usb.md`
- Create: `agent/skills/plamp-troubleshoot/references/diagnostics.md`, `verification.md`
- Create: `agent/skills/openscad-cad/references/things-index.md`, `plamp-stand.md`
- Modify to forwarding pages: `docs/spec-current.md`, `docs/host-tools.md`, `plamp_cli/README.md`, `plamp_web/README.md`, `pico_scheduler/README.md`, `things/README.md`, `things/plamp_stand/README.md`
- Modify: `README.md`
- Create: `tests/test_agent_docs.py`
- Modify: `tests/test_bootstrap_installer.py`, `tests/test_package_metadata.py`, `tests/test_plamp_cli.py`, `tests/test_things_cad_scripts.py`

**Interfaces:**
- Produces one canonical copy of operating prose under `agent/skills/*/references`; old paths contain only a Markdown title and one relative link.
- Keep `agent/check_alive.bash`, `agent/check_daily.md`, `agent/check_weekly.md`, `CHECKLIST.md`, `docs/superpowers/**`, executable scripts, Python sources, and live CLI help in place.

- [ ] **Step 1: Add failing canonical-location and forwarding-page tests**

Create a table in `tests/test_agent_docs.py` mapping every old path to its canonical target:

```python
FORWARDERS = {
    "docs/spec-current.md": "agent/skills/plamp-workflow/references/current-contract.md",
    "docs/host-tools.md": "agent/skills/plamp-setup/references/host-tools.md",
    "plamp_cli/README.md": "agent/skills/plamp-operate/references/rest-api.md",
    "plamp_web/README.md": "agent/skills/plamp-operate/references/web-service.md",
    "pico_scheduler/README.md": "agent/skills/plamp-pico/references/scheduler.md",
    "things/README.md": "agent/skills/openscad-cad/references/things-index.md",
    "things/plamp_stand/README.md": "agent/skills/openscad-cad/references/plamp-stand.md",
}
```

For each pair assert the canonical target is a real file, the old file has at most four nonblank lines, contains exactly one Markdown link resolving to the target, and contains no operational fenced code block. Add a Markdown-link walker for canonical agent Markdown; ignore external URLs and anchors, but require every relative file target to exist. Update old tests to read canonical sources for content and separately rely on this forwarding contract.

- [ ] **Step 2: Run documentation tests and verify RED**

```bash
.venv/bin/python -m unittest tests.test_agent_docs tests.test_bootstrap_installer \
  tests.test_package_metadata tests.test_plamp_cli tests.test_things_cad_scripts -v
```

Expected: missing canonical files and nonminimal old documents fail.

- [ ] **Step 3: Move substance without duplication**

Use `apply_patch` to create the mapped canonical files and replace each old file with a title plus a relative link to its canonical location. Preserve all still-current facts and examples, but consolidate by responsibility: tool/install material under setup; REST/web usage under operate; Pico firmware/USB under pico; verification and daily/weekly/heartbeat links under troubleshoot; system identity under workflow; CAD under the existing OpenSCAD skill. Fix relative links for their canonical locations.

Reduce root `README.md` to a human landing page retaining the project image, one installation path, and a prominent link labeled `How to be a Plamp agent` to `agent/README.md`. Do not duplicate detailed operations or CAD commands there.

- [ ] **Step 4: Verify and commit**

```bash
.venv/bin/python -m unittest tests.test_agent_docs tests.test_bootstrap_installer \
  tests.test_package_metadata tests.test_plamp_cli tests.test_things_cad_scripts -v
git diff --check
git add README.md agent/skills docs/host-tools.md docs/spec-current.md \
  plamp_cli/README.md plamp_web/README.md pico_scheduler/README.md \
  things/README.md things/plamp_stand/README.md tests
git commit -m "Centralize Plamp agent operating references"
git push origin feature/remove-generate-bash
```

Expected: all content and link tests pass, and every compatibility page is pointer-only.

---

### Task 7: Add the complete Plamp skill set and automatic repo routing

**Files:**
- Create: `agent/AGENTS.md`, `agent/README.md`
- Create: `AGENTS.md` as a relative symlink to `agent/AGENTS.md`
- Create: `agent/skills/plamp-workflow/SKILL.md`
- Create: `agent/skills/plamp-setup/SKILL.md`
- Create: `agent/skills/plamp-operate/SKILL.md`
- Create: `agent/skills/plamp-pico/SKILL.md`
- Create: `agent/skills/plamp-troubleshoot/SKILL.md`
- Modify: `agent/skills/openscad-cad/SKILL.md`
- Create: `agent/skills/*/agents/openai.yaml`
- Modify: `tests/test_agent_docs.py`

**Interfaces:**
- `plamp-workflow` routes general repository/deployment/tool-choice work.
- `plamp-setup` covers kit install, configuration, service setup, and upgrades.
- `plamp-operate` covers controllers, schedules, cameras, pictures, JSON, web, and REST.
- `plamp-pico` covers USB identity, scheduler state, firmware, pulse safety, and recovery.
- `plamp-troubleshoot` covers status/logs and service, network, USB, camera, and hardware evidence.
- `openscad-cad` owns manufacturing and the sole `plamp cad` workflow.

- [ ] **Step 1: Add failing taxonomy and schema tests**

Assert the immediate skill directory names equal exactly the six names above; each has `SKILL.md` with YAML frontmatter containing only matching `name` and a nonempty `description`; each reference link resolves; and each has `agents/openai.yaml`. Assert `AGENTS.md` is a Git mode `120000` relative link whose strict resolution equals `agent/AGENTS.md`. Assert `agent/README.md` links every skill, the daily/weekly checks, heartbeat, installation, setup, operation, Pico, troubleshooting, and CAD.

- [ ] **Step 2: Run and verify RED**

```bash
.venv/bin/python -m unittest tests.test_agent_docs -v
```

Expected: five skill directories, routing docs, metadata, and root agent entrypoint are missing.

- [ ] **Step 3: Write concise skills and routing**

Keep each `SKILL.md` procedural and short, routing detail to Task 6 references. Establish the exact tool boundary: `plampctl` changes hosts/services and performs upgrades/migrations; `plamp` performs local direct operations including CAD; `python3 -m plamp_cli` is the explicitly named REST compatibility client. Require JSON discovery for agents, evidence before mutation, and narrow skill selection. `agent/AGENTS.md` must point agents first to `agent/README.md` and instruct them to use the matching skill.

Create the root symlink with:

```bash
ln -s agent/AGENTS.md AGENTS.md
```

- [ ] **Step 4: Validate skills and commit**

Run the available skill validator against all six directories, then:

```bash
.venv/bin/python -m unittest tests.test_agent_docs -v
git diff --check
git add AGENTS.md agent tests/test_agent_docs.py
git commit -m "Ship complete Plamp agent skills"
git push origin feature/remove-generate-bash
```

Expected: schema, link, taxonomy, and root entrypoint tests pass.

---

### Task 8: Build the safe registry-managed skill installer

**Files:**
- Create: `agent/install-skills`
- Create: `tests/test_agent_skills.py`
- Modify: `agent/README.md`, `agent/skills/plamp-setup/references/installation.md`

**Interfaces:**
- Commands: `agent/install-skills {install|sync|status|uninstall} [--allow-dirty] [--migrate-existing NAME|all]`.
- Registry: `${CODEX_HOME:-$HOME/.codex}/skills/.plamp-managed.json`; lock beside it; backups under `.plamp-backups/<UTC timestamp>/`.
- Produces direct absolute links from each installed skill name to this checkout's matching `agent/skills/<name>` directory.

- [ ] **Step 1: Write isolated RED tests**

Use temporary repo clones and Codex homes, including spaces. Cover exact six-skill discovery and frontmatter-name matching; clean-source refusal/`--allow-dirty`; install/status/idempotence; one collision causing zero partial writes; preservation of `.system` and unrelated file/directory/symlink skills; explicit migration backing up all unexpected content; checkout A to B sync; broken registered target retarget; manual replacement refusal; add/remove repo skill sync; uninstall of exact registered links only; malformed registry; concurrent lock refusal; and atomic valid JSON registry replacement.

- [ ] **Step 2: Run and verify RED**

```bash
.venv/bin/python -m unittest tests.test_agent_skills -v
```

Expected: installer missing.

- [ ] **Step 3: Implement the stdlib-only transaction**

Use Python 3.11 `argparse`, `pathlib`, `json`, `os.open(..., O_CREAT|O_EXCL)`, `os.replace`, `os.lstat`, and `subprocess.run` for read-only Git identity/dirty checks. Validate the complete plan before changing anything. Create links through uniquely named temporary symlinks followed by `os.replace`; registry writes use a same-directory temporary file, flush/fsync, then `os.replace`. Only retarget/prune/uninstall a destination when both registry ownership and the current exact link target agree. Migration uses `os.replace` into a timestamped backup before linking. Never enumerate or mutate `.system`, never run skill scripts, and report checkout path, origin, commit, and dirty state.

- [ ] **Step 4: Document exact commands and verify**

```bash
./agent/install-skills status
./agent/install-skills install
./agent/install-skills install --migrate-existing openscad-cad
./agent/install-skills sync
./agent/install-skills uninstall
```

Run:

```bash
.venv/bin/python -m unittest tests.test_agent_skills tests.test_agent_docs -v
python3 -m py_compile agent/install-skills tests/test_agent_skills.py
git diff --check
git add agent tests/test_agent_skills.py
git commit -m "Install repository skills safely"
git push origin feature/remove-generate-bash
```

---

### Task 9: Add explicit install and opted-in upgrade lifecycle

**Files:**
- Modify: `deploy/bootstrap/install-plamp.sh`, `plampctl`
- Modify: `tests/test_bootstrap_installer.py`, `tests/test_plampctl.py`, `tests/test_setup_sh.py`
- Modify: `agent/README.md`, `agent/skills/plamp-setup/references/installation.md`, `README.md`

**Interfaces:**
- Bootstrap option `--install-agent-skills` invokes `<repo>/agent/install-skills install` as the invoking user after checkout; default bootstrap never invokes it.
- `plampctl upgrade` invokes `agent/install-skills sync` only when the registry exists and identifies this repository's managed skills; no registry means no opt-in.
- `setup.sh` remains side-effect-free with respect to Codex files.

- [ ] **Step 1: Write failing lifecycle tests**

Extend bootstrap tests to assert help/documentation and default no-call versus explicit one-call behavior without `sudo`. Extend `PlampctlTests.run_with_stubs()` with a fake installer/registry and assert upgrade syncs only opted-in installs, reports sync failure without hiding it, and never calls the installer through `sudo`. Add a setup test that snapshots a temporary Codex home before/after sourcing `setup.sh` and finds no change.

- [ ] **Step 2: Run and verify RED**

```bash
.venv/bin/python -m unittest tests.test_bootstrap_installer tests.test_plampctl tests.test_setup_sh -v
```

Expected: option and conditional sync behavior are absent.

- [ ] **Step 3: Implement opt-in lifecycle hooks**

Parse `--install-agent-skills` in bootstrap without prompting. After clone/update and before service installation, execute `"${repo_dir}/agent/install-skills" install`; always print the post-install command when not opted in. In `plampctl upgrade`, after the fast-forward and dependency sync, call `agent/install-skills sync` only when `.plamp-managed.json` exists under the invoking user's Codex skill root and contains at least one source under this repository. Do not use `sudo`; on failure stop before claiming a clean completed upgrade and print the recovery command.

- [ ] **Step 4: Verify and commit**

```bash
.venv/bin/python -m unittest tests.test_bootstrap_installer tests.test_plampctl tests.test_setup_sh -v
bash -n deploy/bootstrap/install-plamp.sh plampctl setup.sh
git diff --check
git add deploy/bootstrap/install-plamp.sh plampctl tests agent README.md
git commit -m "Sync agent skills after explicit opt-in"
git push origin feature/remove-generate-bash
```

---

### Task 10: End-to-end acceptance, forward tests, and stable-main handoff

**Files:**
- Modify only within earlier task file groups if verification finds an omission.

**Interfaces:**
- Produces merge-ready evidence and, after merge, safe local migration/deployment instructions from stable `main`.

- [ ] **Step 1: Run static and focused acceptance**

```bash
test -z "$(git ls-files | rg '(^|/)(generate|template)[.]bash$')"
test "$(git grep -n -I -e 'generate[.]bash' -e 'template[.]bash' -- | wc -l)" -eq 0
python3 -m py_compile agent/install-skills tests/test_agent_docs.py tests/test_agent_skills.py
bash -n things/plamp_stand/check_generates_stl_files_from_scad.bash \
  deploy/bootstrap/install-plamp.sh plampctl setup.sh
.venv/bin/python -m unittest tests.test_agent_docs tests.test_agent_skills \
  tests.test_cad_metadata tests.test_cad_recipes tests.test_cad_generation tests.test_cad_scaffold \
  tests.test_cad_cli tests.test_things_cad_scripts tests.test_bootstrap_installer \
  tests.test_plampctl tests.test_setup_sh -v
git diff --check
```

Expected: no removed file/name, no real Plamp8 render, and all focused tests pass.

- [ ] **Step 2: Run full suite and isolated installer smoke**

```bash
.venv/bin/python -m unittest discover -s tests -v
skill_home="$(mktemp -d /tmp/plamp-codex-skills-XXXXXX)"
CODEX_HOME="$skill_home" ./agent/install-skills install
CODEX_HOME="$skill_home" ./agent/install-skills status
CODEX_HOME="$skill_home" ./agent/install-skills sync
```

Expected: full suite passes; six exact links are installed; status/sync are no-op successes; `.system` and unrelated paths remain untouched.

- [ ] **Step 3: Forward-test fresh-agent discovery**

Give fresh agents only the GitHub repository/root `AGENTS.md` and separately ask: generate the Plamp8 fused box; install/configure a kit; take a picture and inspect controller state; recover an undiscovered Pico; diagnose an unhealthy service. Require each agent to select the intended narrow skill, cite canonical `agent/` references, use `plamp cad views` then `validate` then `plan` for CAD, choose the correct `plampctl`/`plamp`/REST boundary, and never invent an alternate CAD interface. Record prompts and results in the review report, not as tracked fixtures.

- [ ] **Step 4: Final review and push**

Run an independent whole-branch review against all global constraints. Fix findings through a fresh implementation agent and re-review. Push the clean branch; do not install links from the feature worktree.

- [ ] **Step 5: After approved merge, migrate and deploy from stable main**

From the stable main checkout, explicitly back up and migrate the two known copied local skills, then install all six:

```bash
git switch main
git pull --ff-only origin main
./agent/install-skills install --migrate-existing all
./agent/install-skills sync
```

Verify `status`, then deploy/upgrade Tower and Sprout through `plampctl` and smoke-test service health. Never point installed skills at a temporary worktree that will be removed.
