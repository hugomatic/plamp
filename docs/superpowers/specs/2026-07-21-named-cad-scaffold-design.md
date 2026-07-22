# Named CAD Scaffold Design

**Date:** 2026-07-21

## Goal

`plamp cad new PART` creates a useful OpenSCAD starting point whose public
modules are named after the part. The generated file remains immediately
discoverable and renderable by `plamp cad`: it has a `view` selector, positive
and negative geometry, and valid generation metadata containing at least one
preset.

For example, `plamp cad new pump_bracket` creates
`things/pump_bracket/pump_bracket.scad` with this structure:

```scad
view = "pump_bracket"; // [pump_bracket, assembly]

module pump_bracket_positive() { /* simple cube */ }
module pump_bracket_negative() {
    echo("BOM", "M3x16 screw", 1);
    /* centered M3 clearance through-hole */
}

module pump_bracket() {
    difference() {
        pump_bracket_positive();
        pump_bracket_negative();
    }
}

```

The `pump_bracket` view calls `pump_bracket()` directly. The `assembly` view
initially renders that same module, leaving an obvious place to add related
parts later. Templates must not retain generic `part()`, `part_positive()`, or
`part_negative()` aliases.

## Naming Contract

The requested `PART` remains unchanged in the directory and filename. Its
OpenSCAD identifier is derived by replacing every hyphen with an underscore:

| Requested part | File | OpenSCAD module stem |
| --- | --- | --- |
| `pump_bracket` | `pump_bracket.scad` | `pump_bracket` |
| `pump-bracket` | `pump-bracket.scad` | `pump_bracket` |

After hyphen replacement, the stem must match
`[A-Za-z_][A-Za-z0-9_]*`. Names beginning with a digit are therefore rejected;
silently prefixing or otherwise renaming them would make the module identity
surprising. Existing path-safety rules continue to reject separators,
traversal, whitespace, shell syntax, and other characters outside
`[A-Za-z0-9_-]`.

Before mutation, scaffolding compares the derived stem with the stems of
existing sibling part directories whose names satisfy the part-name grammar.
It rejects a normalized collision, such as creating `pump-bracket` when
`things/pump_bracket/` exists, and reports both names and the shared stem.
Case remains significant, matching OpenSCAD identifiers and the repository's
case-sensitive naming convention.

## Template Contract and Substitution

Selectable templates use the reserved token `__PLAMP_PART__` everywhere the
module stem or part-named view belongs. For example, they define
`__PLAMP_PART___positive()`, `__PLAMP_PART___negative()`, and
`__PLAMP_PART__()`. The scaffolder decodes the template as UTF-8 and replaces
every exact token occurrence with the derived stem. It does not perform broad
text rewriting or create compatibility aliases. After substitution, validation
confirms that all three required module declarations exist and that no reserved
token remains.

Every selectable template must produce a file with:

- a top-level `view` variable whose default is the derived module stem;
- exactly two initial declared views: the derived module stem and `assembly`;
- a valid embedded `generate.json` object;
- metadata entries for both declared views;
- a default preset containing both views, in part-named then `assembly` order;
- the named positive, negative, and composed modules; and
- view dispatch in which the normal part/assembly path calls the named
  composed module.

The starter geometry is intentionally useful but disposable:

- `<stem>_positive()` makes a simple cube;
- `<stem>_negative()` makes a centered 3.4 mm-diameter M3 clearance hole that
  extends fully through the cube with Boolean overlap beyond both faces, and
  immediately emits `echo("BOM", "M3x16 screw", 1);` so the declared hardware
  stays coupled to the feature requiring it;
- `<stem>()` subtracts the negative module from the positive module; and
- generation logs therefore demonstrate machine-readable bill-of-material
  output whenever the screw-hole feature is rendered.

The default `cad` template provides this complete contract. Named templates
must follow it too; a template with no placeholder, invalid UTF-8, invalid
metadata, no view choices, no preset, or a preset referring to an undeclared
view is rejected before the destination is created.

This deliberately supersedes the earlier byte-for-byte copy requirement.
Apart from exact placeholder substitution, generated text remains identical to
the selected template.

## Creation and Failure Semantics

Creation retains the existing safe, atomic workflow:

1. Validate the requested part and template names, derived identifier,
   normalized sibling uniqueness, source containment, placeholder contract,
   views, presets, and metadata before mutation.
2. Create a staging directory beneath `things/`, write the substituted SCAD
   file, and validate the staged result.
3. Commit with an atomic no-replace operation. A destination that appears at
   any time, including between validation and commit, is never deleted,
   replaced, or merged.
4. Remove staging artifacts after every failure.

The final part directory uses ordinary directory permissions (`0777 & umask`,
normally `0755`), not `tempfile`'s private `0700`. The generated SCAD uses
ordinary file permissions (`0666 & umask`) and never inherits executable bits
from its template.

Expected selection and validation errors produce the established humane text
or JSON error response and exit status 2. Operational failures such as denied
permissions, disk exhaustion, or I/O errors remain operation failures with exit
status 4; they are not mislabeled as invalid user input. Template files must be
opened through their already validated, contained identity so a concurrent
symlink replacement cannot escape the template root.

## Tests and Acceptance

Pure scaffolding and CLI tests must demonstrate:

- `pump_bracket` generates the exact path and the three required named modules;
- `pump-bracket` retains its path spelling while generating
  `pump_bracket_positive()`, `pump_bracket_negative()`, and `pump_bracket()`;
- the default view is `pump_bracket` for either spelling, declared views are
  `pump_bracket` then `assembly`, and the default preset contains both in that
  order;
- each generated view path ultimately calls the named composed module and
  contains no generic `part*` module aliases;
- positive geometry is a cube, negative geometry is a centered 3.4 mm M3
  clearance through-hole with overlap on both faces, and the composed module
  differences them;
- the exact `echo("BOM", "M3x16 screw", 1);` example is inside the negative
  module beside the screw-hole cutter;
- generated metadata parses successfully, exposes the declared `view` choices,
  and has at least one valid preset;
- names beginning with digits and other invalid identifiers fail without
  mutation;
- normalized sibling collisions fail without mutation;
- a missing placeholder or required named-module declaration, a leftover
  placeholder, malformed UTF-8, invalid metadata, missing views, missing
  presets, and unknown preset views fail without mutation;
- an executable source template still produces a non-executable SCAD file;
- the result directory has ordinary umask-derived permissions;
- a destination created at commit time is preserved by atomic no-clobber;
- source replacement cannot bypass template-root containment; and
- operational I/O failures use the operation-failure CLI contract while normal
  user errors retain the selection-error contract.

Acceptance is complete when both the focused scaffold/CLI tests and the
repository CAD validation tests pass, and `plamp cad views`, `validate`, and
`plan` work on a newly generated hyphenated fixture without invoking OpenSCAD.

## Scope

This change updates scaffold templates, substitution/validation, and tests. It
does not add module aliases, alter existing CAD parts, invoke OpenSCAD during
creation, or broaden the accepted filesystem-name character set.
