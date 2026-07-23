# Readable CAD Run IDs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give managed CAD archives readable local-time IDs and safely prevent or regenerate duplicate same-day renders.

**Architecture:** Keep archive identity and replacement mechanics in `plamp.cad_generation`, using existing source hashes, selection snapshots, and ordered job fingerprints. Expose a typed duplicate exception to `plamp.cad_cli`, where TTY prompting and the explicit `--regenerate` switch remain user-interface concerns. Preserve manifest schema version 1 and explicit-output behavior.

**Tech Stack:** Python standard library, `argparse`, immutable CAD recipe dataclasses, `unittest`, Git-backed source snapshots.

## Global Constraints

- Managed IDs use `<year>-<lowercase-month><day>-<part>-<selector>-<hour>h:<minute>m-<revision>` in workstation-local time with no seconds.
- A rare distinct same-minute path collision fails clearly; no random or numeric suffix is allocated.
- Duplicate matching includes local calendar date, source content, selection, preset tree, and ordered job fingerprints.
- Interactive copy says `Regenerate`; JSON and non-TTY commands never prompt.
- A failed or interrupted regeneration must not destroy the existing run.
- Explicit `--output` keeps its existing exact-directory semantics.
- Manifest schema remains version 1 with no new fields.

---

### Task 1: Readable IDs and duplicate identity

**Files:**
- Modify: `plamp/cad_generation.py`
- Test: `tests/test_cad_generation.py`

**Interfaces:**
- Produces: `CadRunExistsError(existing_run_id: str, existing_run_dir: Path)`.
- Produces: `_readable_run_id(now: datetime, part: str, selector: str, revision: str) -> str`.
- Produces: duplicate matching derived from a `RenderPlan`, `SourceSnapshot`, and schema-1 manifests.

- [ ] **Step 1: Replace the random-ID test with failing readable-ID tests**

Add tests that patch the local clock to `datetime(2026, 7, 23, 22, 19, tzinfo=timezone(timedelta(hours=-10)))` and assert:

```python
self.assertEqual(
    load_run(result.run_dir)["run_id"],
    f"2026-jul23-fixture-print-22h:19m-{self.commit[:7]}",
)
```

Cover preset, one direct view, and multiple direct views, plus two distinct plans in the same minute producing a clear path-collision failure.

- [ ] **Step 2: Run the readable-ID tests and verify RED**

Run:

```bash
python3 -m unittest \
  tests.test_cad_generation.CadGenerationTests.test_run_ids_are_human_readable \
  tests.test_cad_generation.CadGenerationTests.test_distinct_same_minute_runs_fail_clearly -v
```

Expected: failures showing the existing compact UTC/random-token IDs.

- [ ] **Step 3: Implement ID formatting and numeric allocation**

Remove `secrets` from normal run-ID generation. Add a local clock seam and helpers equivalent to:

```python
def _local_now() -> datetime:
    return datetime.now().astimezone()

def _readable_run_id(now: datetime, part: str, selector: str, revision: str) -> str:
    return "-".join((
        f"{now.year:04d}",
        f"{now.strftime('%b').lower()}{now.day}",
        _safe_component(part),
        _safe_component(selector),
        f"{now.hour:02d}h:{now.minute:02d}m",
        _safe_component(revision),
    ))
```

For managed output, create the base directory exclusively and preserve the resulting clear `FileExistsError` on the rare distinct same-minute collision. Explicit output still uses the supplied directory while its manifest receives the base readable ID.

- [ ] **Step 4: Add failing duplicate-identity tests**

Generate once, advance the local clock within the same day, and assert the second call raises `CadRunExistsError` with the first ID and exact directory. Add non-match cases for the next local day, a changed source snapshot, changed defines, and changed ordered job fingerprints.

- [ ] **Step 5: Run duplicate tests and verify RED**

Run the new duplicate-focused test names with `python3 -m unittest ... -v`.

Expected: `CadRunExistsError` is missing or no collision is detected.

- [ ] **Step 6: Implement typed duplicate detection**

Build a canonical identity from the already archived schema-1 values:

```python
{
    "source_content_hash": source_content_hash,
    "selection": plan_as_dict(plan)["selection"],
    "preset_tree": plan_as_dict(plan)["preset_tree"],
    "job_fingerprints": [job.fingerprint for job in plan.jobs],
}
```

Compare it with each valid manifest under the managed part directory after converting `created_at` from UTC to the current local timezone. Ignore malformed manifests rather than making generation unusable, but do not ignore valid failed/interrupted matches. Raise `CadRunExistsError` before invoking OpenSCAD.

- [ ] **Step 7: Run the focused and complete generation tests**

Run:

```bash
python3 -m unittest tests.test_cad_generation -v
```

Expected: all generation tests pass, including unchanged schema and explicit-output tests.

- [ ] **Step 8: Commit Task 1**

```bash
git add plamp/cad_generation.py tests/test_cad_generation.py
git commit -m "Add readable CAD run identities"
```

### Task 2: Safe regeneration transaction

**Files:**
- Modify: `plamp/cad_generation.py`
- Test: `tests/test_cad_generation.py`

**Interfaces:**
- Changes: `generate_plan(..., regenerate: bool = False) -> GenerationResult`.
- Consumes: `CadRunExistsError` and duplicate identity from Task 1.
- Guarantees: existing run survives unsuccessful regeneration.

- [ ] **Step 1: Add failing safe-regeneration tests**

Cover:

```python
replacement = self.generate(regenerate=True)
self.assertEqual(replacement.run_dir, original.run_dir)
self.assertNotEqual(
    load_run(replacement.run_dir)["finished_at"],
    original_manifest["finished_at"],
)
```

Then force the fake OpenSCAD process to fail and assert the original manifest and artifacts remain byte-for-byte unchanged while a sibling name containing `regeneration-failed` retains the failed diagnostics.

- [ ] **Step 2: Run regeneration tests and verify RED**

Run the two new regeneration tests directly.

Expected: `generate_plan` rejects `regenerate` or replaces the original unsafely.

- [ ] **Step 3: Render duplicate regeneration into a sibling staging directory**

When `regenerate=True` and a duplicate exists, use a securely created sibling staging directory. Render the complete run there while keeping the existing final directory untouched. On failed status, rename the staging directory to a collision-free `.regeneration-failed-*` diagnostic directory and return that failed `GenerationResult`.

- [ ] **Step 4: Publish a successful regeneration with rollback**

Rename the old directory to an exact sibling backup, rename staging to the original run path, rewrite stored command paths from staging to final, and remove the backup only after publication succeeds. If publication raises, restore the backup before propagating the error. Keyboard interruption follows the failed-staging preservation path.

- [ ] **Step 5: Run focused fault-injection and full generation tests**

Run:

```bash
python3 -m unittest tests.test_cad_generation -v
git diff --check
```

Expected: all tests pass and no whitespace errors are reported.

- [ ] **Step 6: Commit Task 2**

```bash
git add plamp/cad_generation.py tests/test_cad_generation.py
git commit -m "Regenerate CAD runs without losing archives"
```

### Task 3: Human prompt and automation switch

**Files:**
- Modify: `plamp/cad_cli.py`
- Test: `tests/test_cad_cli.py`

**Interfaces:**
- Adds: `plamp cad generate ... --regenerate`.
- Adds: `plamp cad menu ... --regenerate`.
- Changes: `_generate(..., stdin: TextIO, ...)` so prompting uses injected streams.

- [ ] **Step 1: Add failing parser and non-interactive collision tests**

Assert both generation actions parse `--regenerate`. Inject a generator that raises `CadRunExistsError("run-1", existing_path)` and verify JSON and non-TTY text calls return CAD400, contain the existing path and `--regenerate`, and never read stdin.

- [ ] **Step 2: Run the new CLI tests and verify RED**

Run the new test names directly with `python3 -m unittest ... -v`.

Expected: parser rejection or generic collision output without the required behavior.

- [ ] **Step 3: Add failing interactive confirmation tests**

Use a TTY-like `StringIO` test double. Assert the first generator call raises the collision, `n` leaves it unchanged, and `y` produces a second call with `regenerate=True`. Freeze exact copy:

```text
WARNING: matching CAD run already exists: <path>
Regenerate existing run? [y/N]
```

Also verify menu generation uses the same prompt after menu selection.

- [ ] **Step 4: Implement CLI collision handling**

Import `CadRunExistsError`, add `--regenerate` to `generate` and `menu`, and pass stdin into `_generate`. Attempt generation once; on a collision, prompt only when `not args.json` and `stdin.isatty()`. Retry the retained source snapshot only after an affirmative `y`/`yes`; otherwise raise an operation error containing the existing path and the explicit switch.

- [ ] **Step 5: Run all CLI and generation tests**

Run:

```bash
python3 -m unittest tests.test_cad_cli tests.test_cad_generation -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit Task 3**

```bash
git add plamp/cad_cli.py tests/test_cad_cli.py
git commit -m "Prompt before regenerating CAD archives"
```

### Task 4: Human documentation and final verification

**Files:**
- Modify: `docs/host-tools.md`
- Modify: `docs/superpowers/specs/2026-07-23-readable-cad-run-ids-design.md` only if implementation exposes a verified discrepancy.
- Test: `tests/test_things_cad_scripts.py`

**Interfaces:**
- Documents: readable archive path, duplicate warning, interactive answer, and `--regenerate` automation command.

- [ ] **Step 1: Add a failing documentation contract**

Extend the CAD documentation test to require a representative readable ID, `--regenerate`, and the statement that explicit output bypasses managed duplicate detection.

- [ ] **Step 2: Run the documentation test and verify RED**

Run the exact `ThingsCadScriptsTest` documentation test.

Expected: required readable-run text is absent.

- [ ] **Step 3: Update the human documentation**

Document examples equivalent to:

```bash
plamp cad generate plamp8 --view top_panel
plamp cad generate plamp8 --view top_panel --regenerate
```

Explain the readable path, safe same-day collision behavior, and explicit-output escape hatch without exposing internal staging mechanics as normal user workflow.

- [ ] **Step 4: Run complete verification**

Run:

```bash
python3 -m unittest tests.test_cad_generation tests.test_cad_cli tests.test_things_cad_scripts -v
python3 -m unittest discover -s tests -v
git diff --check
```

Expected: every test passes and Git reports no whitespace errors.

- [ ] **Step 5: Commit Task 4**

```bash
git add docs/host-tools.md tests/test_things_cad_scripts.py
git commit -m "Document readable CAD regeneration"
```

- [ ] **Step 6: Review and publish**

Inspect the branch diff against `origin/main`, push `feature/cad-readable-run-ids`, open a pull request, and report the URL plus the exact verification evidence.
