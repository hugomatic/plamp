---
name: openscad-cad
description: Create, modify, template, render, and verify OpenSCAD CAD parts for 3D printing and assemblies. Use when Codex is asked to do CAD, OpenSCAD, STL generation, 3D-printable parts, plate/assembly views, revision/commit engraving, or plamp repo things/ workflows including things/template.bash and things/3d_template/generate.bash.
---

# OpenSCAD CAD

## Workflow

1. Inspect the repo's CAD conventions before editing. In plamp, read `things/template.bash`, `things/3d_template/generate.bash`, the selected part directory, and [plamp-things.md](references/plamp-things.md) when working under `things/`.
2. Keep parts parametric. Put dimensions near the top, name them clearly, and preserve user-provided measurements unless intentionally changing fit.
3. Preserve a view contract. Prefer `view = "assembly"; // [assembly, plate]` or the part's existing ordered view array/comment. `plate` is for printable orientation/layout; `assembly` is for visual context.
4. Use the positive/negative pattern for robust parts: model additive geometry in positive modules, subtract holes/cutouts/engraving in negative modules, and compose with `difference()`.
5. Brand/version physical prints with `revision_string`. Engrave or emboss the string where it will print clearly and not affect critical fit. For generated builds, use the git commit hash or explicit dirty-worktree revision text.
6. Render and verify requested views when OpenSCAD is available. Check that STL files are non-empty and logs do not report an empty top-level object.
7. Avoid committing generated STL/print artifacts unless the user explicitly asks. Commit source `.scad` and generator/template changes needed to reproduce outputs.

## New Parts

Use the existing template script when the user asks for a new part and the repo provides one:

```bash
cd things
./template.bash part_name
```

If template selection is supported, use `--template <name>` and keep the generated main file named `<part>/<part>.scad`. If the requested template is unavailable, list available templates and either use the default or ask only when the choice materially affects the part.

For plamp CAD conventions and planned generator behavior, read [plamp-things.md](references/plamp-things.md).

## Rendering

Prefer the part's `generate.bash` over direct `openscad` commands because it handles revision strings, output naming, and repo conventions. Common flow:

```bash
cd things/<part>
./generate.bash HEAD /tmp/<part>_gen
```

If the script requires a specific commit hash, commit first when reproducibility matters, then render that commit. If the part directory is dirty and the generator supports explicit revision text, use a meaningful label supplied by the user or a concise local label such as `fit-test-1`.

## OpenSCAD Practices

- Keep `$fn` high enough for final curved prints, but do not hide preview/performance issues behind excessive resolution.
- Use `use <...>` when importing modules without executing top-level code; use `include <...>` only when variables/top-level definitions are needed.
- Keep coordinate systems intentional: document origin and printable orientation when not obvious.
- Make fit-sensitive features easy to tune: offsets, tolerances, lip thickness, hole diameters, and clearances should be named parameters.
- For engraving text, subtract shallow text from a printable face or emboss it positively if the face is too thin. Avoid tiny text that will not survive slicing.
