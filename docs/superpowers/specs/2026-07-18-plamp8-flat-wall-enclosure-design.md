# Plamp8 Flat-Wall Enclosure Design

## Goal

Redesign the Plamp8 enclosure walls so support is minimized, deliberate, and easy to remove, while the enclosure can be wired with its relay-board long sides accessible. Replace the current one-piece upright wall shell and its large support-driven corner geometry with four independently printable walls, a separate ledge ring, and shared M3 corner joints.

The redesign must preserve the current floor, top-panel, and sub-panel interfaces wherever possible. In particular, the existing printed sub-panel should remain usable unless a physical corner-stack test proves that no available screw length can clamp it correctly.

## Coordinate System And Wall Names

Use unambiguous compass names throughout the SCAD source, Customizer, generated files, tests, and documentation:

- North wall: `y = box_d`
- South wall: `y = 0`
- West wall: `x = 0`
- East wall: `x = box_w`
- Floor: XY plane
- Z: enclosure height

The relay board's long axis runs along Y. West and east are therefore the two walls that must remain absent during wiring so both long sides of the relay board are reachable.

## Chosen Mechanical Approach

Print four independent walls flat with each plain exterior face on the build plate. Join adjacent walls with hidden, vertically stacked internal tabs at the top and bottom of every corner. One vertical M3 screw at each top corner and one at each bottom corner clamps both intersecting walls plus the adjacent panel, ring, or floor.

This design was chosen over:

- Keeping the upright one-piece shell, because its raised bosses and nut traps begin in mid-air and require support.
- Full-height dovetails or grooves, because a long printed wall can warp enough to make those joints bind and because they complicate installing the west and east walls after wiring.
- A separate bottom ring, because the flat-printed floor already provides the required structural plane and locating surface.

## Four Wall Parts

Replace the monolithic `walls` printable part with four modules and four printable views:

- `north_wall`
- `south_wall`
- `west_wall`
- `east_wall`

Each printable wall view must place its exterior face flat on Z=0. Interior ribs, tabs, nut traps, and locating features then build upward from supported material. Prefer printable slopes, but allow small intentional support patches where they preserve joint strength or serviceability. Avoid large, trapped, inaccessible, or accidental support regions.

All four vertical exterior seams use 45-degree mitres through the wall thickness. The mitres hide the seam from the outside; they are not the structural joint. The internal M3 corner tabs provide the structural connection.

Do not add a full-height tongue, dovetail, or groove along a wall seam. Use only short, shallow wall-to-wall locating keys near the bottom corners. These keys establish alignment before tightening the screws without entering the top panel stack or creating a long tolerance-sensitive sliding fit.

Each wall is a separately printable part and must carry `revision_string` on a non-critical interior face. The marking must be readable in the STL and must not affect a mating, sealing, or hardware surface.

## Adjustable Wall Height

Expose a dedicated Customizer parameter:

```scad
wall_z_height = 83;
```

The default preserves the current wall height, which is derived today from `internal_clearance_h = 80` plus `wall_t = 3`.

Preserve the established top datum: the top surface is Z=0, the 3 mm top panel occupies Z=-3..0, the existing 10 mm sub-panel occupies Z=-13..-3, and the new 3 mm ledge ring occupies Z=-16..-13. At the default height, the wall bottom edge and floor underside remain at Z=-83.

`wall_z_height` is the full exterior wall height from the bottom wall edge to the top wall edge. In assembly coordinates, the top edge remains at Z=0 and the bottom edge is `-wall_z_height`. Changing it must:

- Resize all four walls equally.
- Move the bottom joints, floor, and floor-mounted components with the bottom wall edge.
- Keep the top joints, ledge ring, mounted panels, and top surface fixed relative to the top wall edge.
- Keep each top and bottom attachment feature at a fixed offset from its respective wall end.
- Recenter or regenerate wall ventilation within fixed top and bottom safety margins.
- Update internal-component and assembly placement that is currently derived from `box_h`.

Floor thickness, ledge-ring thickness, top-panel thickness, and sub-panel dimensions do not change with `wall_z_height`. The geometry should assert that there is enough height for the two joint zones and their required separation. Component interference at unusually short heights should remain visible in the assembly view rather than silently moving components.

## Top Corner Joint

At every top corner, the two intersecting walls contribute overlapping inward-facing tabs on the same vertical M3 screw axis:

- The west or east wall contributes the upper tab with an M3 clearance hole.
- The north or south wall contributes the lower tab with an M3 nut trap.
- The nut trap opens toward the inside of the enclosure.
- The nut must be insertable and removable from inside after the wall is printed.
- The nut remains positively captured when the wall or enclosure is inverted and while a screwdriver starts or removes the screw.
- Use two small opposing retention detents rather than a broad catcher. Grow each detent inward on a 30-degree ramp measured from horizontal; the detents resist gravity and handling, while the solid pocket shoulder carries screw load.
- Prefer support-free nut-entry geometry, but accept small, deliberate, inward-accessible support when eliminating it would weaken the pocket or detents.
- Because the assembled vertical screw axes become horizontal in the flat wall print orientation, production tab bores must use a teardrop or 45-degree-roof profile rather than an unsupported round horizontal ceiling.
- The east/west clearance tabs are compact 5 mm-radius bosses grown from the wall's exterior build-plate face. The north/south nut-side geometry is one continuous 5 mm-radius corner spine joining the bottom and top nut-bearing zones. Do not add angled gussets: both forms begin at Z=0 in print orientation and do not need sloped support geometry.
- Each tab's corner-facing edge starts at least `corner_fit_clearance` beyond the neighboring 3 mm wall skin; the shared M3 axis remains 7 mm from the corner.
- Keep the rounded boss profile, horizontal support-aware bores, captured-nut pockets, and retention detents. Replacing the separated nut bosses with the continuous spine must not change the screw axis or either joint's stack thickness.

The nut-side corner spine is one continuous positive solid on each end of each north/south wall. It spans from the lower edge of the bottom nut-bearing zone to the upper edge of the top nut-bearing zone, filling the 6.4 mm separation left by the two extended nut bosses. Its rounded profile remains centered on the shared M3 axis and clipped at the same wall-facing and inward limits as the existing bosses. Subtract two independent bores from the spine, one entering from each end and ending beyond its associated nut trap without joining the opposite bore. Preserve the two existing side-loaded nut traps, their bearing shoulders, offsets, and retention detents. The two M3x30 screws must remain mechanically separate and must not meet inside the spine.

The spine replaces only the two north/south nut-tab positives. East/west walls retain two separate 6 mm-thick clearance tabs at every corner so the walls can still be inserted during the documented assembly sequence.

The west/east top locator keys are omitted. At the current dimensions the former top key occupied assembled Z=-19 through -3 mm, intersecting both the ledge ring at Z=-16 through -13 mm and the sub-panel at Z=-13 through -3 mm. The corner tabs, M3 screw axis, and 45-degree seam provide the top alignment without that key. Keep only the bottom wall-to-wall locator keys, using straight rectangular keys and clearance notches without angled insertion lead-ins.

At the northeast corner, for example, the final stack from top to bottom is:

1. The 3 mm top-panel corner
2. The existing 10 mm sub-panel corner, whose 5 mm base rests on the ring
3. Separate ledge ring
4. East-wall upper tab with M3 clearance hole
5. North-wall lower tab with M3 nut trap

The other three corners use the same ownership rule. This makes north and south the nut-trap walls and west and east the clearance-tab walls.

The screw installs downward from the visible top side. Its head treatment should remain compatible with the current panel corner-hole convention. Tightening the screw must clamp the top panel, sub-panel, ledge ring, and both walls without relying on friction at the 45-degree exterior seam.

The ledge ring and the north/south wall seats must support the panel assembly at its final Z position even while west and east are absent during wiring. The final corner is fully clamped only after both intersecting wall tabs are present.

## Separate Ledge Ring

Replace the integral `top_panel_ledge()` geometry with one separately printed rectangular ledge ring.

The ring must:

- Print flat without support.
- Remain one structurally connected rectangular part with straight rails and defined bearing lands for the top and sub-panel assembly.
- Use four M3 clearance holes aligned with the existing panel corner holes and wall tabs.
- Preserve the required PH Up and PH Down switch-body clearances with two 21 mm-wide reliefs: the 20 mm switch openings plus 0.5 mm clearance per side.
- Remain a closed ring. A continuous 3 mm north perimeter rail runs outside the switch-body envelopes, with 0.75 mm nominal clearance at the current dimensions.
- Include short locating features that align it with the walls without creating a long binding groove.
- Carry `revision_string` on a non-critical hidden face.

Quarter-circle ledges are not required. Their curved cross-section existed to make an integral upright-wall ledge self-supporting; the separate ring is printed flat and can use a simpler rectangular section. The PH switch reliefs interrupt only the inboard portion of the north bearing rail. They must not sever the 3 mm outer north perimeter rail or merge into one oversized opening.

The existing top-panel and sub-panel corner-hole coordinates remain the controlling interface. The ring and wall joints adapt to those coordinates rather than moving the panel holes.

## Existing Sub-Panel Compatibility

Keep the current dimensions:

```scad
sub_panel_base_h = 5;
sub_panel_h = 10;
```

Do not thin the base or reduce the overall height in the initial implementation. The sub-panel base rests directly on the ledge ring. Preserve its existing corner-hole locations and its revision marking.

Available M3 hardware includes 25 mm and 30 mm screws. Select the shortest length that passes through the real top stack, fully engages the captured nut, and leaves no dangerous excess inside the wiring space. Target full nut engagement and approximately 0-2 mm protrusion beyond the nut. Screw length must be a named parameter and must not be encoded indirectly in boss geometry.

If neither M3x25 nor M3x30 works with the existing sub-panel, stop after the corner coupon and revise the stack deliberately. Do not silently change the sub-panel thickness.

## Bottom Corner Joint

The floor-to-wall joint mirrors the top joint but has no sub-panel or ledge ring. Do not add a bottom ring in the initial design.

At every bottom corner:

- The west or east wall contributes the lower tab with an M3 clearance hole.
- The north or south wall contributes the upper tab with an inward-accessible M3 nut trap.
- The floor has an aligned M3 clearance hole and the appropriate underside head recess.
- The screw installs upward from below, leaving its head visible when looking at the enclosure bottom.

At the northeast corner, the stack from inside to outside/downward is:

1. North-wall upper tab with M3 nut trap
2. East-wall lower tab with M3 clearance hole
3. Floor
4. M3 screw head underneath

This replaces the current four midpoint M5 floor fasteners and wall tabs. Floor corner geometry must be checked against existing component mounts, perimeter ribs, and enclosure clearances before placement.

Keep the floor inside the four wall skins. Do not add circular floor corner lands beneath the wall joints: those lands occupy the wall volume. At the fixed 7 mm axis and 6.5 mm countersink diameter, the inner-only floor leaves 0.75 mm of edge ligament toward each wall. Validate that edge in the bottom coupon; if it proves inadequate, revise the countersink or shared screw axis deliberately rather than extending floor material into a wall.

The floor itself provides the bottom structural plane. Short locating keys near the corners align it with the wall interiors and prevent lateral drift while screws are loose. Do not use a continuous perimeter groove. Remove the legacy 60 mm L-shaped floor corner ribs: they occupy the new 7 mm M3 corner axes and are superseded by the local circular screw lands, locator lands, and installed walls.

## Captured Nut Traps

Every captured nut is side-loaded from the enclosure interior. In the wall's flat print orientation:

- The pocket opens toward the enclosure interior.
- Two small opposing detents positively retain the nut against inversion and screwdriver disturbance.
- Detent insertion ramps use the printer's current 30-degree minimum support-free slope measured from horizontal.
- Small intentional support is acceptable only when localized, visible in the slicer, accessible from inside, and removable without damaging the nut pocket.
- The nut remains serviceable after printing and before final enclosure closure.

Nut clearance, entry length, detent, tab thickness, tab overlap, and hole clearance remain named parameters. The existing M3 nut and clearance values are the starting point, but the fit coupon decides the final tolerances.

## Assembly And Service Sequence

The enclosure must support this workflow:

1. Install sockets and switches in the top panel and AC sub-panel, then join the panel assembly.
2. Mount the PSU, converter, and relay board on the floor.
3. Attach or locate the north and south walls while leaving west and east open.
4. Rest the ledge ring and connected panel assembly on north and south, or support the connected panel assembly immediately above them, with enough wire slack to lift it later.
5. Complete wiring with both YZ sides open so the relay board's long edges remain reachable.
6. Remove the four top screws and loosen or remove the four bottom corner screws.
7. Lift the connected panel assembly and ledge ring without disconnecting the wiring.
8. Insert west and east from the open sides, engaging their straight bottom locating keys and placing their tabs into the shared top and bottom corner stacks.
9. Refit the ledge ring and panel assembly.
10. Tighten the four bottom-up floor screws and four downward top screws.

No bonnet, hinge, laterally sliding service wall, or dedicated `wiring_assembly` view is required. Later service may remove the top assembly and whichever individual wall provides the needed access.

## Views And Customizer Controls

Update the ordered `view` contract to include:

- `floor`
- `north_wall`
- `south_wall`
- `west_wall`
- `east_wall`
- `ledge_ring`
- `top_panel`
- `sub_panel`
- `corner_coupon`
- `assembly`

Preserve the existing component footprint and connector coupon views. Keep `wall_corner_fastener_test` only as a temporary compatibility alias; it must not remain in the ordered view list or determine the generated STL name. Remove the obsolete monolithic `walls` printable view rather than exporting the old shell under a misleading name.

Remove feature switches and geometry that were reachable only through that obsolete monolithic shell. This includes the disabled wall-only PSU tie-wrap anchors; the supported floor PSU tie-wrap anchors remain available through `feature_psu_tie_wrap_anchors`.

Replace the single assembly `show_walls` control with:

```scad
show_north_wall = true;
show_south_wall = true;
show_west_wall = true;
show_east_wall = true;
show_ledge_ring = true;
```

Keep the existing floor, internal-component, top-panel, and sub-panel visibility controls. The normal `assembly` view is the only required assembly visualization; users can reproduce the wiring state by unchecking west and east.

Split converter visibility from PSU visibility with `show_dc_dc = true`. `show_psu` controls only the 12 V PSU keepout, `show_dc_dc` controls only the DC/DC keepout, and `show_relay` continues to control the relay keepout.

All assembly transforms must reuse the same part modules used by the printable views. Do not maintain separate approximate wall geometry for visualization.

## Assembly Illustration Labels

Treat the transparent component keepouts as assembly-manual illustration elements as well as interference envelopes. Add horizontally centered, raised labels to their top faces:

- Relay keepout: `RELAYS`
- DC/DC converter keepout: `DC/DC`
- 12 V power-supply keepout: `12V PSU`

Build each label with positive-Z `linear_extrude()` text beginning at the keepout's top surface and extending upward by a named illustration-label thickness. Put the text inside the same `color()` scope as its transparent component volume; do not apply another color or opacity to the label. Size each label independently to remain inside its component footprint. Orient `RELAYS` and `DC/DC` horizontally in the standard assembly top view, and rotate `12V PSU` 90 degrees counter-clockwise from horizontal. Labels belong only to the contextual keepout modules; they must not alter the floor, component-footprint coupons, or any printable enclosure part.

## First Printable: Corner-Stack Coupon

Before rendering four full walls, add a compact fit-test view representing one top corner and one bottom corner. It must exercise:

- Two independently printed wall-tab coupons in their production print orientation.
- The 45-degree exterior mitre.
- The straight bottom locating key and notch; the top coupon must not contain a wall-to-wall locator key.
- M3 clearance holes.
- The inward side-loaded nut trap and retention detent.
- A ledge-ring segment.
- A 3 mm top-panel surrogate stacked on a 10 mm sub-panel surrogate with its 5 mm base against the ledge-ring segment.
- A floor segment and bottom-up screw-head recess.
- M3x25 and M3x30 top-stack evaluation.

The coupon should answer four physical questions before a full-wall print:

1. Can the nut be inserted from inside without support damage or excessive force?
2. Do the two wall tabs and mitres assemble without binding?
3. Does the selected screw fully engage the nut without unsafe protrusion?
4. Do the ring, panel surrogate, floor, and both walls clamp without visible rocking or deformation?

## Source Structure

The initial implementation may remain in `things/plamp8/plamp8.scad`, but the redesigned geometry should be divided into clearly named modules for wall bodies, mitres, clearance tabs, continuous nut-bearing corner spines, nut traps, bottom locating keys, ledge ring, printable orientations, and assembly transforms. Do not duplicate corner geometry four times; derive corner handedness and ownership from small reusable modules.

Avoid unrelated refactoring of the connector, label, PSU, converter, relay, or generator code. Preserve the directory-specific Git revision behavior in `things/plamp8/generate.bash`.

## Verification

Automated source-level tests should verify at least:

- The ordered view list contains all four named walls, the ledge ring, fit coupon, and assembly.
- The obsolete monolithic `walls` view and single `show_walls` option are gone.
- `wall_z_height` exists and drives the assembled top Z position.
- Floor corner hardware uses M3 rather than the old midpoint M5 fasteners.
- Existing sub-panel thickness and corner-hole coordinates remain unchanged.
- Top and bottom corner modules use the agreed north/south nut ownership and east/west clearance ownership.
- North/south walls use one continuous rounded spine per corner, with two separate bores and two captured-nut traps, while east/west walls retain separate clearance tabs.
- The three transparent component keepouts include the approved positive-Z assembly labels without adding those labels to printable component-footprint coupons.
- The assembly exposes an independent `show_dc_dc` control rather than coupling the converter to `show_psu`.
- Each printable part receives `revision_string` where required.

OpenSCAD verification must use `things/plamp8/generate.bash`, not ad hoc direct render commands:

1. Run shell syntax and existing CAD-script tests.
2. Render the corner fit-test first with an explicit honest dirty-worktree revision.
3. Confirm its STL is present, non-empty, and has no empty-object or missing-include warnings.
4. Inspect the coupon mesh or preview for minimized, deliberate support and obvious interference.
5. After committing the final CAD, render each wall, ledge ring, floor, top panel, sub-panel, and assembly from the directory-specific commit.
6. Confirm all requested STL files are present and non-empty.
7. Inspect OpenSCAD logs for empty objects, missing geometry, and manifold failures.
8. Visually inspect the full assembly and sectioned corner joints with individual walls toggled off and on. Confirm each north/south spine is a single union, its two screw bores remain separated, both nut entries remain accessible, `RELAYS` and `DC/DC` read horizontally, `12V PSU` reads 90 degrees counter-clockwise, and each label inherits its keepout's transparent color.
9. Check independently printed part pairs for unintended volumetric overlap. Bound the calculations to four wall-corner boxes, four narrow floor-to-wall edge strips, four narrow ring-to-wall edge strips, the thin sub-panel-to-ring perimeter, the thin top-to-sub-panel perimeter, and the two PH switch clearance regions. Coincident seating faces, designed tab contact, and fasteners occupying their clearance holes are intentional contacts; any other shared solid volume is interference.

Generated STL and print artifacts remain untracked unless explicitly requested.

## Acceptance Criteria

The redesign is complete when:

- All four walls and the ledge ring render as independent parts with support minimized and any remaining support localized and removable.
- Exterior wall seams are 45-degree mitres with no visible butt-joint step in assembly.
- Every top and bottom corner screw captures both intersecting walls.
- Each north/south corner has one continuous 5 mm-radius nut-bearing spine with separate top and bottom M3x30 screw paths; east/west clearance tabs remain separate.
- All nut traps load from inside, retain the nut when inverted, and have no accidental or inaccessible support region.
- Independently printed enclosure parts have no unintended interference in the assembled model.
- The floor uses four bottom-up corner M3 screws and no midpoint M5 enclosure fasteners.
- West and east can be omitted in assembly while north and south support the wiring configuration.
- West and east can be added after wiring without disconnecting the panel wiring.
- `wall_z_height` changes the full wall height without moving fixed end features away from their respective top or bottom wall ends.
- The existing 5 mm base / 10 mm overall sub-panel remains compatible, or a failed physical coupon provides evidence before any sub-panel redesign.
- Revision markings remain readable on every standalone printable enclosure part.
- `RELAYS`, `DC/DC`, and `12V PSU` appear as positive-Z raised text in the same transparent color scopes as their corresponding assembly keepouts and do not affect printable parts; the PSU text is rotated 90 degrees counter-clockwise.
- `show_dc_dc` independently shows or hides the converter keepout in the assembly.
