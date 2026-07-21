# CAD Generation Recipes Final Review Fixes

## Status

All six whole-branch review findings were fixed in one integration pass. The accepted `jobs_by_view` last-variant behavior was not changed.

## Files changed

- `plamp/cad_cli.py`
- `plamp/cad_generation.py`
- `plamp/cad_metadata.py`
- `plamp/cad_recipes.py`
- `tests/test_cad_cli.py`
- `tests/test_cad_generation.py`
- `tests/test_cad_metadata.py`
- `tests/test_cad_recipes.py`

## Implementation

1. Generate commands now retain the single `SourceSnapshot` used to parse metadata and fingerprint the plan, then pass that same snapshot into `generate_plan()`. Temporary snapshots are cleaned on setup failure and after generation. The boundary regression mutates the live SCAD after planning and proves the archived/rendered source remains the original planned snapshot and the manifest retains the planned fingerprint.
2. Dirty sources are copied into an independent temporary snapshot during `prepare_source()`, before any run directory is created. This preserves explicitly labelled dirty generation and prevents recursive copying when explicit output is nested below the live part.
3. Snapshot preparation validates symlinks. Git archive members must remain in the requested part subtree; absolute, traversal, escaping symlink, and hard-link entries are rejected. A committed escaping link regression fails safely, while an in-part relative symlink remains supported.
4. `list_runs()` accepts only a non-empty, non-absolute single path component. `load_job_log()` resolves and contains the recorded path in the run directory and requires the exact `logs/<artifact-id>.log` contract.
5. Embedded JSON parsing rejects `NaN`, `Infinity`, and `-Infinity` through a stable `CAD105`/`invalid_metadata` diagnostic.
6. `PresetNode` and `RenderPlan` copy caller-supplied sequences to tuples in `__post_init__`; mutation-resistance is covered. `jobs_by_view` is unchanged.

## TDD evidence

RED command:

```text
.venv/bin/python -m unittest tests.test_cad_metadata.CadMetadataTests.test_non_finite_json_numbers_are_rejected_with_stable_diagnostic tests.test_cad_recipes.CadRecipeTests.test_frozen_plan_nodes_copy_caller_sequences_to_tuples tests.test_cad_generation.CadGenerationTests.test_dirty_explicit_output_beneath_part_does_not_copy_itself tests.test_cad_generation.CadGenerationTests.test_committed_source_rejects_symlink_that_escapes_archive tests.test_cad_generation.CadGenerationTests.test_committed_source_accepts_symlink_within_part tests.test_cad_generation.CadGenerationTests.test_list_runs_rejects_unsafe_part_components tests.test_cad_generation.CadGenerationTests.test_load_job_log_rejects_manifest_path_escape_and_unexpected_path tests.test_cad_cli.CadCliTests.test_generate_uses_the_same_snapshot_for_planning_and_rendering -v
```

Observed RED: exit 1 with the intended failures: non-finite values parsed successfully, caller lists remained mutable, nested dirty output recursed, escaping symlink was accepted, unsafe part values were accepted, manifest log paths were trusted, and the CLI prepared a second source snapshot. The nested-output reproduction raised `RecursionError`, directly confirming the reported mechanism.

GREEN command (same command after the implementation):

```text
Ran 8 tests in 0.532s
OK
```

An existing dirty-source assertion was then updated to the new required independent-snapshot contract. The four focused modules subsequently ran 91 tests successfully.

## Verification

Focused modules plus checks:

```text
git diff --check
python3 -m py_compile plamp/cad_metadata.py plamp/cad_recipes.py plamp/cad_generation.py plamp/cad_cli.py tests/test_cad_metadata.py tests/test_cad_recipes.py tests/test_cad_generation.py tests/test_cad_cli.py
.venv/bin/python -m unittest tests.test_cad_metadata tests.test_cad_recipes tests.test_cad_generation tests.test_cad_cli -q
```

Result: exit 0; `Ran 91 tests in 4.033s`, `OK`; compilation and diff checks produced no errors.

Full CAD suite:

```text
.venv/bin/python -m unittest tests.test_cad_metadata tests.test_cad_recipes tests.test_cad_generation tests.test_cad_cli tests.test_things_cad_scripts -v
```

Result: exit 0; `Ran 122 tests in 5.490s`, `OK`.

Direct CLI smoke checks:

```text
PLAMP_DATA_DIR=/tmp/plamp-cad-final-fixes .venv/bin/python -m plamp cad validate plamp8 --json
PLAMP_DATA_DIR=/tmp/plamp-cad-final-fixes .venv/bin/python -m plamp cad plan plamp8 --preset split-box --json
```

Result: both exit 0. Validation reported `"valid": true`; planning reported five split-box jobs. An initial attempt through `.venv/bin/plamp` was unavailable in this worktree (`No such file or directory`), so the repository's supported module entry point was used.

Full repository suite:

```text
.venv/bin/python -m unittest discover -s tests -v
```

Result: exit 0; `Ran 562 tests in 16.814s`, `OK`.

## Self-review

- Re-read the design and implementation plan constraints relevant to source identity, dirty legacy generation, archive structure, diagnostics, and immutable public results.
- Confirmed snapshot cleanup occurs for parse/plan failures, successful generation, generator exceptions, and direct `generate_plan()` calls.
- Confirmed safe in-part symlinks remain supported and escaping links are rejected before extraction/copy.
- Confirmed archive log access checks both resolved containment and the exact manifest path contract.
- Confirmed no changes were made to `jobs_by_view` behavior.
- Confirmed no push was performed.

## Concerns

None. Symlink handling is intentionally conservative: archive hard links and symlink targets containing traversal components are rejected even if a traversal could normalize back into the part tree.

## Follow-up: menu snapshot ownership

The final review found that `cad menu` reaches `_generate()` with `args.action == "menu"`, while `_with_plan()` previously inferred snapshot ownership from the literal `"generate"` action. It consequently removed the planned source snapshot before real rendering began.

The fix adds an explicit `retain_snapshot` argument to `_with_plan()`. `_generate()` requests retention regardless of whether it was entered from `cad generate` or `cad menu`; `_with_plan()` still cleans snapshots on parse/selection/planning failures, and `_generate()` retains its `finally` cleanup across success, generator failure, and interrupts.

RED:

```text
.venv/bin/python -m unittest tests.test_cad_cli.CadCliTests.test_menu_retains_planned_snapshot_through_real_generation_then_cleans_it -v
```

Result before implementation: exit 1; `Ran 1 test in 0.029s`, failed because the command returned 4 instead of 0 after the real generator received an already-removed snapshot.

GREEN and focused verification:

```text
.venv/bin/python -m unittest tests.test_cad_cli.CadCliTests.test_menu_retains_planned_snapshot_through_real_generation_then_cleans_it -v
.venv/bin/python -m unittest tests.test_cad_cli tests.test_cad_generation -v
```

Results: exit 0; the regression passed in 0.108s, and `Ran 45 tests in 3.767s`, `OK`. The regression selects the `split` preset through the menu, invokes real `generate_plan()` with fake OpenSCAD, asserts the planned snapshot and SCAD exist while generation starts, verifies the archived run completes, and asserts the temporary snapshot is removed after command completion.

Full CAD and static checks:

```text
python3 -m py_compile plamp/cad_cli.py tests/test_cad_cli.py
git diff --check
.venv/bin/python -m unittest tests.test_cad_metadata tests.test_cad_recipes tests.test_cad_generation tests.test_cad_cli tests.test_things_cad_scripts -v
```

Result: exit 0; `Ran 123 tests in 5.100s`, `OK`; compilation and diff checks produced no errors.

Full repository suite:

```text
.venv/bin/python -m unittest discover -s tests -v
```

Result: exit 0; `Ran 563 tests in 17.840s`, `OK`.

Follow-up concerns: none. No push was performed.
