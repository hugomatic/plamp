# Readable CAD Run IDs and Regeneration

## Goal

Make managed `plamp cad generate` archives easy for a person to recognize while
preventing accidental duplicate renders of the same CAD selection and source on
the same day.

## Run ID

A managed run ID uses:

```text
<year>-<lowercase-month><day>-<part>-<selector>-<hour>h:<minute>m-<revision>
```

For example:

```text
2026-jul23-plamp8-top_panel-22h:19m-47e7d26
```

The date and time use the workstation's local timezone and omit seconds. The
selector is the preset name, the single view name, or `views` for an explicit
multi-view selection. The revision remains the short Git revision for clean
committed source and the explicit revision label for dirty source. Existing
component sanitization still applies to part, selector, and revision strings.
Manifest timestamps remain UTC ISO-8601 values.

An explicit `--output` directory remains authoritative: its directory name is
not rewritten, while the manifest still receives a readable run ID.

## Duplicate Identity

Before creating a managed run, Plamp examines that part's existing manifests.
A run is a duplicate when all of these match:

- workstation-local calendar date;
- part;
- complete source identity, using the archived content hash rather than only
  the seven-character display revision;
- selected preset/views and all global and per-view defines;
- expanded jobs and their fingerprints.

This is slightly stricter than “same view and commit”: two selections that
would generate different geometry are not treated as duplicates. Failed or
incomplete runs are still matches because they occupy the intended run path and
their diagnostics must not be silently discarded.

Duplicate detection applies to the managed archive. Explicit `--output` is the
advanced escape hatch and retains its existing create-exactly-this-directory
semantics.

## Collision Behavior

The generation core reports a structured duplicate-run collision containing
the existing run ID and path. It never silently creates a second directory.

Human, interactive CLI output prints a clear warning and the existing path,
then asks:

```text
Regenerate existing run? [y/N]
```

Declining exits without changing the archive. JSON/non-interactive use does not
prompt; it returns a clear CAD operation error containing the existing path and
advises the explicit `--regenerate` option. `--regenerate` is also accepted in
interactive use and skips the question.

Regeneration renders into a sibling staging directory first. Only after the new
run has finished successfully does Plamp replace the old directory. If rendering
fails or is interrupted, the existing run remains intact and the failed staging
directory is retained with diagnostics under its own clearly marked temporary
name.

## CLI and Data Boundaries

`plamp.cad_generation` owns ID formatting, duplicate identity, archive scanning,
and safe staged replacement. It exposes a specific collision exception so the
CLI does not parse error strings.

`plamp.cad_cli` owns interactivity. It passes input/output streams explicitly,
prompts only when attached to the normal human-readable command path, and passes
the confirmed regeneration intent back to the generation layer. Menu-driven
generation uses the same behavior.

No manifest schema field is added. Duplicate identity is derived from existing
source, selection, preset-tree, and job data, preserving schema version 1 and
compatibility with archived runs.

## Verification

Automated tests will cover:

- the exact readable local-time format and absence of random suffixes;
- preset, single-view, and multi-view selectors;
- duplicate matching across different minutes on the same local day;
- non-matches for source, defines, jobs, or local date changes;
- clear non-interactive collision errors containing the existing path;
- interactive decline and `Regenerate` confirmation;
- explicit `--regenerate` behavior;
- successful staged replacement and preservation of the old run after a failed
  regeneration;
- unchanged explicit-output semantics and manifest schema;
- CAD CLI, generation, and complete repository test suites.

## Out of Scope

- Compact versus pretty JSON output.
- STL checksum and verification UX.
- Changes to Plamp8 coupon geometry or presets; `test-fit` already generates the
  complete component, connector-panel, and corner coupon suite.
