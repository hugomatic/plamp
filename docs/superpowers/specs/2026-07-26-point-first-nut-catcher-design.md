# Point-First Nut Catcher Design

## Goal

Make the shared M3 nut catcher accept a hex nut in only the intended
orientation and retain it with printable floor nibs.

## Geometry

`m3_nut_catcher_negative()` remains the single authoritative catcher. Its
hexagonal seated pocket has a vertex on the insertion axis. A point-first nut
therefore presents its smaller across-flats dimension across the tunnel and
fits. A nut turned flat-first presents its larger across-corners dimension and
does not fit through the across-flats-sized tunnel.

The seated nut also has a vertex at the back of the pocket. The two existing
angled nibs remain paired around the corresponding rear vertex.

## Printable nibs

Each nib is a solid wedge left in the floor of the subtractive catcher. From
the tunnel entrance toward the pocket, the nut encounters the wedge's gradual
ramp first. After insertion, the steep face retains the nut. The wedge rises
from supported floor material and introduces no downward-facing shelf.

The existing global nib height, length, width, and angle parameters remain the
only fit controls. Panel and corner catchers receive identical pocket and nib
geometry through the shared module.

## Verification

- A source regression test requires vertex-first hex orientation.
- A source regression test requires the nib high edge to be nearer the pocket
  than its floor-only entrance edge.
- Existing shared-dimension and shared-module tests remain green.
- The nut-catcher adjustment jig and NORTH wall render as valid non-empty
  solids without OpenSCAD warnings or errors.
- Physical retention remains subject to the next printed adjustment jig.
