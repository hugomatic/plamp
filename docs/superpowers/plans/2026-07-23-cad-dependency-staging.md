# Reproducible OpenSCAD Dependency Staging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Discover every OpenSCAD source/import dependency, archive a deterministic self-contained closure, render from staged paths, and reject undeclared or host-only resolution.

**Architecture:** `cad_dependencies` parses OpenSCAD make dependency files, learns active library roots from `openscad --info`, classifies each resolved path against the model/repository/system declarations, and builds deterministic staged roots. `cad_generation` performs a cheap CSG dependency pass before rendering, renders with staged `OPENSCADPATH`, compares the second dependency closure, and archives complete dependency provenance.

**Tech Stack:** Python 3.11 standard library, OpenSCAD CLI (`-d`, CSG/STL export, `--info`), Git archive, SHA-256, filesystem-safe staging, `unittest`

## Global Constraints

- This plan depends on both `2026-07-23-cad-system-catalog.md` and `2026-07-23-cad-manufacturing-metadata.md`.
- Discover both `use`/`include` SCAD sources and `import()`/`surface()` assets through OpenSCAD's own dependency file; do not infer the complete graph with regular expressions.
- OpenSCAD resolves calling-file-relative paths before `OPENSCADPATH`, user libraries, and installation libraries; staging must preserve the relative layout that produced discovery.
- Clean/historical generation discovers repository files from one selected Git commit, never an unrelated current working tree.
- Dirty generation requires the existing explicit revision label and hashes/copies the exact discovered working-tree closure.
- Model-local files continue to archive as the complete model folder.
- Repository-local, declared shared, built-in/installation, and imported-asset dependencies receive explicit classifications, hashes, and archive paths.
- Absolute paths outside approved roots, unsafe symlinks, undeclared shared libraries, missing files, and staged closure differences fail before artifact publication.
- Actual rendering uses staged library roots first, an isolated user-library home, and a second `-d` file; any dependency resolving outside staging fails the job even if OpenSCAD returned success.
- Do not download libraries during generation. BOSL2 is optional declared input; converting Plamp8 geometry to BOSL2 is out of scope.
- Fake OpenSCAD tests cover dependency behavior; real validation uses a tiny fixture, never full Plamp8 STL.

---

### Task 1: Parse make dependencies and OpenSCAD library information

**Files:**
- Create: `plamp/cad_dependencies.py`
- Create: `tests/test_cad_dependencies.py`

**Interfaces:**
- Produces `CadDependencyError`, `OpenScadInfo`, `DependencyRecord`,
  `parse_make_dependencies()`, `parse_openscad_info()`,
  `query_openscad_info()`, and `content_hash()`.
- `parse_make_dependencies(path, working_directory)` returns normalized absolute dependency paths in first-seen order.

- [ ] **Step 1: Write failing make/info parser tests**

```python
def test_make_dependencies_handle_continuations_spaces_and_escapes(self):
    path = self.write("deps.d", "out.csg: root.scad lib\\ file.scad \\\n+ nested/part.scad asset\\#1.svg\n")
    self.assertEqual(parse_make_dependencies(path, self.root), (
        self.root / "root.scad",
        self.root / "lib file.scad",
        self.root / "nested/part.scad",
        self.root / "asset#1.svg",
    ))

def test_parses_active_library_roots_from_openscad_info(self):
    info = parse_openscad_info('''
OpenSCAD Version: 2021.01
OpenSCAD library path:
/home/me/.local/share/OpenSCAD/libraries
/opt/OpenSCAD/libraries

OPENSCAD_FONT_PATH:
''')
    self.assertEqual(info.version, "2021.01")
    self.assertEqual(info.library_paths, (
        Path("/home/me/.local/share/OpenSCAD/libraries"),
        Path("/opt/OpenSCAD/libraries"),
    ))
```

Cover CRLF, drive-letter targets, escaped backslashes, duplicate dependencies, missing dependency files, malformed `--info`, nonzero subprocess status, and injected environment.

- [ ] **Step 2: Run tests and verify RED**

Run: `.venv/bin/python -m unittest tests.test_cad_dependencies -v`

Expected: FAIL because `plamp.cad_dependencies` does not exist.

- [ ] **Step 3: Implement deterministic parsers and info query**

```python
@dataclass(frozen=True)
class OpenScadInfo:
    version: str
    user_library_path: Path | None
    library_paths: tuple[Path, ...]
    raw_output: str

@dataclass(frozen=True)
class DependencyRecord:
    source_path: Path
    classification: str
    logical_name: str
    archive_path: Path
    content_hash: str
    git_revision: str | None = None
    license: str | None = None
    asset: bool = False
```

Implement a make-token state machine: backslash escapes the next character,
backslash-newline joins lines, the first unescaped delimiter colon that is not a
Windows drive-letter colon ends the target, and whitespace separates dependency
tokens. Canonicalize with `resolve(strict=True)`, reject non-files, deduplicate
while preserving order, and never use shell parsing. Query `openscad --info`
with an argv list; parse `User Library Path:` separately and parse the ordered
lines after `OpenSCAD library path:` until the next blank/label.

- [ ] **Step 4: Verify GREEN and commit**

Run:

```bash
.venv/bin/python -m unittest tests.test_cad_dependencies -v
python3 -m py_compile plamp/cad_dependencies.py tests/test_cad_dependencies.py
git diff --check
git add plamp/cad_dependencies.py tests/test_cad_dependencies.py
git commit -m "Parse OpenSCAD dependency metadata"
```

---

### Task 2: Build revision-correct dependency discovery environments

**Files:**
- Modify: `plamp/cad_dependencies.py`
- Modify: `tests/test_cad_dependencies.py`
- Modify: `plamp/cad_generation.py`
- Modify: `tests/test_cad_generation.py`

**Interfaces:**
- Produces `DiscoveryEnvironment`, `prepare_discovery_environment()`, and `run_dependency_discovery()`.
- Clean/historical environments contain a Git archive of the selected repository revision; dirty environments reference the working source but are never used for final render.
- Discovery invokes OpenSCAD with `-o discovery.csg -d discovery.d` plus the job's exact `-D` values.

- [ ] **Step 1: Write failing revision and discovery-argv tests**

```python
def test_historical_discovery_reads_repository_dependency_from_same_commit(self):
    old = self.commit_library("old geometry")
    self.commit_library("new geometry")
    env = prepare_discovery_environment(self.repo, revision=old, dirty=False)
    self.assertEqual((env.root / "shared/lib.scad").read_text(), "old geometry")

def test_dependency_pass_uses_csg_and_exact_job_defines(self):
    result = run_dependency_discovery(
        self.fake_openscad, self.environment, self.job, self.output_dir,
        env={"OPENSCADPATH": str(self.library_root)},
    )
    self.assertEqual(result.argv[1:5], ("-o", str(self.output_dir / "discovery.csg"),
                                      "-d", str(self.output_dir / "discovery.d")))
    self.assertIn("set=\"top_panel\"", result.argv)
```

Cover current clean commit, explicit historical commit, unrelated worktree dirt, dirty model/shared dependency requiring a label, archive traversal/symlink rejection, cleanup, CSG failure diagnostics, and no STL render during discovery.

- [ ] **Step 2: Run tests and verify RED**

Run: `.venv/bin/python -m unittest tests.test_cad_dependencies tests.test_cad_generation -v`

Expected: missing discovery-environment APIs.

- [ ] **Step 3: Implement Git archive and cheap dependency pass**

```python
@dataclass(frozen=True)
class DiscoveryEnvironment:
    root: Path
    source_path: Path
    revision: str | None
    dirty: bool
    cleanup_root: Path | None

@dataclass(frozen=True)
class DiscoveryResult:
    argv: tuple[str, ...]
    dependencies: tuple[Path, ...]
    output: str

def run_dependency_discovery(openscad, environment, job, output_dir, *, env):
    deps = output_dir / "discovery.d"
    csg = output_dir / "discovery.csg"
    argv = [
        str(openscad), "-o", str(csg), "-d", str(deps),
        *_define_argv(job), str(environment.source_path),
    ]
    completed = subprocess.run(argv, cwd=environment.source_path.parent,
                               env=dict(env), text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if completed.returncode != 0 or not deps.is_file():
        raise CadDependencyError(completed.stdout)
    return DiscoveryResult(tuple(argv), parse_make_dependencies(deps, environment.source_path.parent), completed.stdout)
```

For a committed revision, resolve the commit and safely extract `git archive <commit>` into a temporary repository root before discovery. For explicit dirty generation, run discovery against the current repository; after closure classification Task 3 will check `git status --porcelain -- <closure paths>` and enforce the label. Reuse the same define builder as final rendering so conditional imports see identical values.

- [ ] **Step 4: Verify GREEN and commit**

Run:

```bash
.venv/bin/python -m unittest tests.test_cad_dependencies tests.test_cad_generation -v
python3 -m py_compile plamp/cad_dependencies.py plamp/cad_generation.py
git diff --check
git add plamp/cad_dependencies.py plamp/cad_generation.py tests/test_cad_dependencies.py tests/test_cad_generation.py
git commit -m "Discover CAD dependencies at selected revisions"
```

---

### Task 3: Classify and stage a self-contained dependency closure

**Files:**
- Modify: `plamp/cad_dependencies.py`
- Modify: `tests/test_cad_dependencies.py`
- Modify: `plamp/cad_system.py`
- Modify: `tests/test_cad_system.py`

**Interfaces:**
- `CadLibrary` replaces raw system-library mappings with `name`, `path`, `license`, and optional `revision`.
- Produces `DependencyClosure`, `classify_dependencies()`, and `stage_dependency_closure()`.
- Staging returns model source paths and `OPENSCADPATH` roots that contain only archived content.

- [ ] **Step 1: Write failing classification/staging tests**

```python
def test_classifies_and_stages_every_dependency_without_flattening(self):
    closure = classify_dependencies(
        dependencies=self.dependencies,
        model_root=self.repo / "things/box",
        repository_root=self.repo,
        declared_libraries={"BOSL2": self.bosl_spec},
        openscad_library_roots=(self.install_libraries,),
        selected_revision="abc123",
    )
    staged = stage_dependency_closure(closure, self.stage)
    self.assertTrue((self.stage / "repository/things/box/local/helper.scad").is_file())
    self.assertTrue((self.stage / "libraries/BOSL2/std.scad").is_file())
    self.assertTrue((self.stage / "libraries/openscad-1/MCAD/units.scad").is_file())
    self.assertEqual(staged.openscad_paths[0], self.stage / "libraries")
```

Cover complete model-folder snapshot, repository files outside model folder, declared external library roots, installation/user roots, imported STL/SVG/DXF/PNG assets, same basenames in different directories, symlink escape, absolute undeclared dependency, deterministic archive paths, hashes, license/revision metadata, and dirty closure status.

- [ ] **Step 2: Run tests and verify RED**

Run: `.venv/bin/python -m unittest tests.test_cad_dependencies tests.test_cad_system -v`

Expected: missing closure/classification types.

- [ ] **Step 3: Implement typed libraries and longest-root classification**

```python
@dataclass(frozen=True)
class CadLibrary:
    name: str
    path: Path
    license: str | None = None
    revision: str | None = None

@dataclass(frozen=True)
class DependencyClosure:
    records: tuple[DependencyRecord, ...]
    model_root: Path
    repository_root: Path

@dataclass(frozen=True)
class StagedDependencies:
    root: Path
    records: tuple[DependencyRecord, ...]
    model_source: Path
    openscad_paths: tuple[Path, ...]
```

Resolve classification by the most-specific containing root, breaking equal-root
ties in this order: complete model root, declared shared-library roots,
selected-revision repository root, reported installation library roots. Exclude
the `User Library Path` from installation roots: a dependency there must match a
declared library or it is an undeclared host dependency. Imported assets use the
containing class plus `asset` subtype in the manifest. Anything unmatched is
undeclared and fails.

Stage every repository file, including the complete model folder, under
`repository/<repo-relative>` so calling-file-relative paths remain unchanged.
Stage declared libraries under `libraries/<name>/<relative>` and installation
libraries under numbered `libraries/openscad-N/<relative>` roots. Copy with
no-follow checks, verify the post-copy SHA-256, and preserve only regular-file
modes.

- [ ] **Step 4: Verify GREEN and commit**

Run:

```bash
.venv/bin/python -m unittest tests.test_cad_dependencies tests.test_cad_system -v
python3 -m py_compile plamp/cad_dependencies.py plamp/cad_system.py
git diff --check
git add plamp/cad_dependencies.py plamp/cad_system.py tests/test_cad_dependencies.py tests/test_cad_system.py
git commit -m "Stage reproducible CAD dependency closures"
```

---

### Task 4: Render only from staging and compare the resolved closure

**Files:**
- Modify: `plamp/cad_generation.py`
- Modify: `tests/test_cad_generation.py`
- Modify: `plamp/cad_dependencies.py`
- Modify: `tests/test_cad_dependencies.py`

**Interfaces:**
- Every job performs discovery, staging, final render with `-d render.d`, and closure comparison before publishing its STL.
- Produces `verify_staged_dependencies()`; it rejects any final dependency outside the staged root or any logical closure mismatch.
- Final subprocess environment uses staged `OPENSCADPATH`, temporary `HOME`, and temporary platform user-data locations while preserving required execution variables.

- [ ] **Step 1: Write failing staged-render security tests**

```python
def test_final_render_uses_staged_paths_and_isolated_user_library(self):
    self.generate()
    env = self.fake_invocations[-1]["env"]
    self.assertEqual(env["OPENSCADPATH"], os.pathsep.join(map(str, self.staged_paths)))
    self.assertNotEqual(env["HOME"], str(Path.home()))
    self.assertIn("-d", self.fake_invocations[-1]["argv"])

def test_host_fallback_dependency_discards_successful_artifact(self):
    self.fake.final_dependencies.append(self.host_only_library)
    result = self.generate()
    job = json.loads(result.manifest_path.read_text())["jobs"][0]
    self.assertEqual(job["status"], "failed")
    self.assertIn("outside staged dependency closure", job["errors"][0])
    self.assertIsNone(job["artifact"])
```

Cover missing staged dependency, newly conditional final dependency, altered content hash, second makefile missing, OpenSCAD success with escaped dependency, partial multi-job failure, cleanup, and regeneration rollback.

- [ ] **Step 2: Run tests and verify RED**

Run: `.venv/bin/python -m unittest tests.test_cad_generation tests.test_cad_dependencies -v`

Expected: current renderer has no dependency pass/staged environment.

- [ ] **Step 3: Integrate the four-stage job transaction**

For each job execute exactly:

```python
discovery = run_dependency_discovery(
    openscad, discovery_environment, job, discovery_dir, env=source_environment
)
closure = classify_dependencies(
    dependencies=discovery.dependencies,
    model_root=discovery_environment.source_path.parent,
    repository_root=discovery_environment.root,
    declared_libraries=system.libraries,
    openscad_library_roots=tuple(
        path for path in openscad_info.library_paths
        if path != openscad_info.user_library_path
    ),
    selected_revision=discovery_environment.revision,
)
staged = stage_dependency_closure(closure, job_stage)
process = _start_render(
    argv=_command(
        openscad, temporary_artifact, staged.model_source,
        revision_label, job, dependency_file=render_deps,
    ),
    env=_staged_environment(base_env, staged.openscad_paths, isolated_home),
)
verify_staged_dependencies(
    expected=staged.records,
    actual=parse_make_dependencies(render_deps, staged.model_source.parent),
    staged_root=staged.root,
)
```

Write STL to its existing temporary path and publish it only after closure verification. Translate staged absolute paths back to logical dependency identities before comparing so archive root names do not create false differences. Retain dependency/discovery logs on failure.

- [ ] **Step 4: Verify GREEN and commit**

Run:

```bash
.venv/bin/python -m unittest tests.test_cad_dependencies tests.test_cad_generation -v
python3 -m py_compile plamp/cad_dependencies.py plamp/cad_generation.py
git diff --check
git add plamp/cad_dependencies.py plamp/cad_generation.py tests/test_cad_dependencies.py tests/test_cad_generation.py
git commit -m "Render CAD from verified staged dependencies"
```

---

### Task 5: Expose libraries and dependency provenance in CLI/manifests

**Files:**
- Modify: `plamp/cad_cli.py`
- Modify: `tests/test_cad_cli.py`
- Modify: `plamp/cad_generation.py`
- Modify: `tests/test_cad_generation.py`
- Modify: `plamp/cad_readme.py`
- Modify: `tests/test_cad_readme.py`

**Interfaces:**
- `plamp cad libraries --system SYSTEM` lists name, description/license, resolved source, declaration revision, and validation status.
- Run/job manifests include OpenSCAD version/info hash, effective staged library path, and every dependency record.
- README points to the dependency inventory and states whether external/shared libraries were used.

- [ ] **Step 1: Write failing navigation and provenance tests**

```python
def test_libraries_json_is_described_and_source_attributed(self):
    rows = self.run_json(["cad", "libraries", "--system", "plamp"])
    self.assertEqual(rows[0]["kind"], "library")
    self.assertEqual(rows[0]["id"], "BOSL2")
    self.assertEqual(rows[0]["license"], "BSD-2-Clause")
    self.assertIn("path", rows[0])

def test_manifest_dependency_inventory_has_hashes_and_classification(self):
    dependency = self.manifest()["jobs"][0]["dependencies"][0]
    self.assertEqual(set(dependency), {
        "logical_name", "classification", "archive_path", "content_hash",
        "git_revision", "license", "asset",
    })
```

Cover invalid/missing library rows, `(no description)`, deterministic ordering, explicit system selection, JSON path safety, README wording, and checksums.

- [ ] **Step 2: Run tests and verify RED**

Run: `.venv/bin/python -m unittest tests.test_cad_cli tests.test_cad_generation tests.test_cad_readme -v`

Expected: missing provenance fields and incomplete library rows.

- [ ] **Step 3: Add public serialization and README guidance**

Serialize records from immutable types rather than re-reading the staging tree. Record both the raw discovery source environment and sanitized final environment without leaking unrelated environment variables. Human CLI output must explain missing paths and licenses; JSON uses explicit nulls.

- [ ] **Step 4: Verify GREEN and commit**

Run:

```bash
.venv/bin/python -m unittest tests.test_cad_cli tests.test_cad_generation tests.test_cad_readme tests.test_cad_dependencies -v
python3 -m py_compile plamp/cad_cli.py plamp/cad_generation.py plamp/cad_readme.py
git diff --check
git add plamp/cad_cli.py plamp/cad_generation.py plamp/cad_readme.py tests/test_cad_cli.py tests/test_cad_generation.py tests/test_cad_readme.py
git commit -m "Report CAD dependency provenance"
```

---

### Task 6: Add a tiny real dependency fixture, documentation, and full gate

**Files:**
- Create: `tests/fixtures/cad_dependencies/root.scad`
- Create: `tests/fixtures/cad_dependencies/lib/helper.scad`
- Create: `tests/fixtures/cad_dependencies/assets/profile.svg`
- Modify: `tests/test_cad_dependencies.py`
- Modify: `docs/host-tools.md`

**Interfaces:**
- The tiny fixture proves the installed OpenSCAD `-d` behavior when OpenSCAD is available and skips with an explicit reason otherwise.
- Docs explain local/repository/shared/built-in dependencies, offline generation, library declaration, and inspection commands.

- [ ] **Step 1: Add an optional real OpenSCAD integration test**

Use this exact small fixture:

```scad
// tests/fixtures/cad_dependencies/root.scad
use <lib/helper.scad>
helper();
linear_extrude(height = 1)
    import("assets/profile.svg");
```

```scad
// tests/fixtures/cad_dependencies/lib/helper.scad
module helper() {
    cube([1, 1, 1]);
}
```

```xml
<!-- tests/fixtures/cad_dependencies/assets/profile.svg -->
<svg xmlns="http://www.w3.org/2000/svg" width="2mm" height="2mm" viewBox="0 0 2 2">
  <path d="M0,0 L2,0 L2,2 L0,2 Z"/>
</svg>
```

```python
@unittest.skipUnless(shutil.which("openscad"), "OpenSCAD is not installed")
def test_real_openscad_reports_nested_source_and_import_asset(self):
    result = run_dependency_discovery(
        Path(shutil.which("openscad")), self.fixture_environment,
        self.fixture_job, self.output, env=os.environ,
    )
    names = {path.name for path in result.dependencies}
    self.assertTrue({"root.scad", "helper.scad", "profile.svg"} <= names)
```

The fixture must render only a small CSG/SVG extrusion and complete quickly; do not invoke STL or Plamp8.

Do not modify `cad/plamp.system.cad.json` in this task: the fixture is test-only,
and BOSL2 remains undeclared until it is separately vendored or pinned.

- [ ] **Step 2: Update user documentation**

Document `use`/`include` versus `import`, system library declarations, no-download behavior, selected-revision consistency, staged archive layout, `plamp cad libraries`, manifest dependency inspection, and actionable undeclared-library errors. Cite the OpenSCAD library search order and `-d` dependency option in the references section.

- [ ] **Step 3: Run focused and full verification**

Run:

```bash
.venv/bin/python -m unittest tests.test_cad_dependencies tests.test_cad_generation tests.test_cad_cli tests.test_cad_readme -v
.venv/bin/python -m unittest discover -s tests -v
python3 -m py_compile plamp/cad_*.py tests/test_cad_*.py
git diff --check
git status --short
```

Expected: all fake-based tests pass; the tiny real test passes when OpenSCAD exists or reports one explicit skip; no full Plamp8 render runs.

- [ ] **Step 4: Commit the completed dependency slice**

```bash
git add plamp/cad_dependencies.py plamp/cad_generation.py plamp/cad_cli.py plamp/cad_readme.py tests/fixtures/cad_dependencies tests/test_cad_dependencies.py tests/test_cad_generation.py tests/test_cad_cli.py tests/test_cad_readme.py docs/host-tools.md
git commit -m "Document reproducible CAD dependency staging"
```
