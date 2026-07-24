---
name: openscad-cad
description: Use when creating or modifying OpenSCAD CAD, STL files, laser-cut DXF/SVG/PDF output, 3D-printable parts, plate or assembly views, revision engraving, or plamp things/ workflows.
---

# OpenSCAD CAD

## Workflow

1. Inspect the part and repository conventions. Under plamp `things/`, read [plamp-things.md](references/plamp-things.md).
2. Identify the process and keep dimensions/fit controls parametric.
3. Preserve printable and assembly sets. Compose positive geometry and negative cutters/engraving with `difference()`.
4. Put `revision_string` where readable without affecting fit.
5. Render and verify requested sets.

## Plamp CAD

Use `plamp cad` as the only Plamp CAD generation interface. Discover systems, models, sets, and products; validate metadata; then generate directly. `plan` is an optional advanced preview that expands jobs and variables without invoking OpenSCAD.

```bash
plamp cad systems --json
plamp cad models --system SYSTEM --json
plamp cad sets MODEL --system SYSTEM --json
plamp cad products --system SYSTEM --json
plamp cad validate MODEL --system SYSTEM --json
plamp cad generate --system SYSTEM --product PRODUCT --json
```

Use `--json` for agents. Direct selection supports repeatable `--set`, `--define NAME=EXPR`, and `--set-define SET:NAME=EXPR`; `--all-sets` selects every named set. Omit output arguments to use the managed archive.

Read [plamp-things.md](references/plamp-things.md) for metadata, precedence, source snapshots, archives/logs, and the exact Plamp8 workflow.

## New Parts

Create and register a named model from a described template. The command writes
the paired SCAD source and sidecar:

```bash
plamp cad templates --json
plamp cad new PART --system SYSTEM --template TEMPLATE
```

## FDM Printing

- Choose orientation deliberately. Check mid-air starts, bridges, overhangs, trapped support, and removal access; prefer support-free geometry.
- Treat strength as anisotropic. Orient service loads within layers when practical; address separation, thin bonds, cantilevers, and fastener loads with ribs, gussets, radii, or material.
- Test fit-critical clearances with coupons before long prints.

## Laser Cutting

- Parameterize thickness, kerf, tab/slot clearance, fasteners, and joint strength.
- Keep a 2D profile authoritative. For a plane intersection, transform it onto XY at Z=0 and use `projection(cut=true)`; use `cut=false` only for a silhouette. Use `linear_extrude()` for previews.
- Export DXF/SVG, or PDF when required. Verify scale, closed paths, duplicate lines, cutouts, and LightBurn import.

## OpenSCAD Practices

- Set `$fn` high enough for final curves without crippling preview.
- Use named `shim` as Boolean overlap, not fit clearance; extend cutters through both faces.
- Use `use <...>` for modules without top-level execution and `include <...>` when definitions are required.
- Document non-obvious origins/orientations and name offsets, tolerances, thicknesses, holes, and clearances.
- Engrave shallowly or emboss thin faces; avoid text too small to slice.

## Verification

- Confirm every requested artifact exists and is non-empty.
- Inspect logs for missing includes, warnings, errors, or empty geometry; check orientation, fit, support, strength, and process constraints.
- When OpenSCAD is unavailable, run the Plamp plan and report its jobs, effective variables, exact intended generation command, and managed output location.

## Common Mistakes

- Do not treat a successful render as proof of printability, strength, fit, or cut readiness.
- Do not commit generated STL/DXF/SVG/PDF, manifests, or logs unless explicitly requested; commit reproducible source.
- Do not invent alternate part-local generation interfaces; use `plamp cad`.
