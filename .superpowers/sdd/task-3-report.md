# Task 3 Report: CAD system render planning

## Status

Implemented direct set and nested product expansion into immutable render plans,
including stable fingerprints, artifact identifiers, product memberships, effective
variable provenance, raw defines, JSON serialization, and the prerequisite repeated
sibling validation correction.

## TDD evidence

### RED

Command:

```text
.venv/bin/python -m unittest tests.test_cad_system tests.test_cad_planning -v
```

Observed 18 tests run with two expected errors:

- `ModuleNotFoundError: No module named 'plamp.cad_planning'`
- identical sibling assignments failed with `CAD125 ... require distinct variants`

### GREEN

Command:

```text
.venv/bin/python -m unittest tests.test_cad_model tests.test_cad_system tests.test_cad_planning tests.test_cad_generation -v
python3 -m py_compile plamp/cad_planning.py plamp/cad_values.py
git diff --check
```

Result: 77 tests passed; compilation and diff checks exited successfully.

### Full suite

Command:

```text
.venv/bin/python -m unittest discover -s tests -v
```

Result: 678 tests passed in 19.160 seconds.

## Files

- Created `plamp/cad_planning.py`
- Created `plamp/cad_values.py`
- Created `tests/test_cad_planning.py`
- Modified `plamp/cad_generation.py`
- Modified `plamp/cad_recipes.py` to retain the legacy API while sharing value handling
- Modified `plamp/cad_system.py`
- Modified `tests/test_cad_system.py`

## Commit

`Plan nested CAD products` (the Task 3 commit at `HEAD`)

## Self-review

- Confirmed depth-first declared order and deepest-product-outward precedence.
- Confirmed CLI typed/set/raw precedence and provenance.
- Confirmed fingerprints cover schema, manifest, source, model, set, typed variables,
  and raw expressions and use canonical JSON plus SHA-256.
- Confirmed fingerprint deduplication retains unique product paths.
- Confirmed direct named sets preserve requested order and `all_sets` preserves model order.
- Confirmed legacy recipe imports remain usable until Task 8.
- Confirmed repeated sibling descriptions do not count as effective assignments, while
  variable/profile/slicing differences still require distinct variants.

## Concerns

None.

## Review fix: manufacturing metadata identity

Review found that effective product/item profiles and slicing were discarded,
allowing profile-only or slicing-only sibling variants to collapse during
fingerprint deduplication.

### RED

```text
.venv/bin/python -m unittest \
  tests.test_cad_planning.CadPlanningTests.test_profile_only_sibling_variants_remain_distinct_and_compose_root_to_leaf \
  tests.test_cad_planning.CadPlanningTests.test_slicing_only_sibling_variants_remain_distinct_and_overlay_deepest_outward -v
```

Result: both tests failed because each plan contained one job instead of two.

### GREEN

```text
.venv/bin/python -m unittest tests.test_cad_planning -v
```

Result: 9 tests passed. Effective profiles and slicing now survive in immutable
jobs and JSON, and both participate in the canonical fingerprint.

### Fix commit

`Preserve CAD manufacturing plan metadata` (the review-fix commit following the
Task 3 implementation commit)
