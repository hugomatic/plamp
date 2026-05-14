# Plamp `things/` CAD Conventions

Use this reference only when working in the plamp repository's `things/` CAD tree.

## Files

- `things/template.bash` scaffolds a new part directory.
- `things/3d_template/generate.bash` is the reusable render script copied into new parts.
- `things/3d_template/cad.scad` or `things/3d_template/scad/*.scad` are SCAD templates when present.
- A part usually lives at `things/<part>/<part>.scad` with `things/<part>/generate.bash`.

## SCAD Contract

Prefer this top-level shape unless the existing part has a stronger local convention:

```scad
view = "assembly"; // [assembly, plate]
revision_string = "dev";

module part_positive() { }
module part_negative() { }

module part() {
    difference() {
        part_positive();
        part_negative();
    }
}

module plate() { part(); }
module assembly() { part(); }

if (view == "plate") plate();
else if (view == "assembly") assembly();
else assembly();
```

Use descriptive module names for real parts, but keep the same separation of additive geometry, subtractive geometry, printable view, and assembly view.

## Generator Behavior To Preserve Or Add

- Find OpenSCAD via `OPENSCAD_BIN`, then `command -v openscad`, then common macOS/Linux install paths.
- Default commit argument to `HEAD`; allow an explicit commit hash.
- Resolve repo paths from the script directory, not from the caller's current directory.
- Extract ordered views from `view = "..."; // [a, b, c]`. If the bracket comment is missing, fall back to the assigned `view` value. Do not invent view order.
- For multi-file parts at a clean commit, export the whole part directory with `git archive <commit> <part-dir>` into a temp directory so relative `use` and `include` paths work.
- For dirty working-tree builds, only consider dirtiness under the part directory. Print `HEAD`, the part path, and `git status --porcelain -- <part-dir>`. Refuse unless the user supplies explicit revision text.
- When explicit dirty revision text is supplied, copy the current part directory into a temp directory, render from there, and record the base `HEAD` hash in logs/manifests.
- Keep generated output ordering aligned with the view array because OpenSCAD can be slow.

## Verification

After rendering, verify the requested outputs exist and are non-empty. Inspect OpenSCAD output for warnings that indicate empty geometry or missing includes. If rendering fails because OpenSCAD is missing, report the exact command that would run and the expected output paths.
