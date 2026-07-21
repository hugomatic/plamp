# Plamp8 Support-Free Wall Details Design

## Goal

Make the fused Plamp8 `box` printable without generated support while giving both manufacturing arrangements easier center-facing nut access:

- standalone walls printed exterior-face down; and
- the fused `box` printed floor-down.

The design keeps the assembled fastener axes and existing wall/floor dimensions unchanged.

## Print coordinate contract

Wall-local coordinates remain authoritative:

- X runs along the wall;
- Y runs along the enclosure height and corner-screw axis; and
- Z runs inward from the exterior wall face.

For a standalone wall, print-up is wall-local +Z. In `box`, print-up is assembled/global +Z, which is wall-local +Y for the north and south nut-owning walls.

Wall modules receive an explicit print-orientation parameter only where box geometry must differ. They must not inspect the global `view` value. Standalone wall calls retain their current geometry by default; `box` passes the box orientation explicitly.

The support-free threshold is a surface rising at least 30 degrees above horizontal. Point-up regular-hex roof facets satisfy this threshold.

## Corner nut access

All top and bottom nut entries point 45 degrees from inward toward the box center. Mirroring the existing left/right wall-end feature supplies the matching handedness at the two ends. North/south assembly transforms then point all eight entries toward the enclosure center.

This same geometry has a manufacturing benefit for standalone walls: the 45-degree center-facing path combines wall-local X and +Z, so its rectangular tunnel rises 45 degrees above the build plane and is support-free.

Standalone walls preserve the existing point-up hexagonal nut pocket, detents, and support-free geometry. Only the rectangular entry channel and its throat turn 45 degrees; the nut pocket itself does not rotate or change shape.

In box orientation, the nut clearance core is rectangular and sized from the existing M3 nut dimensions and clearances. Its print-facing roof points in wall-local +Y/global +Z.

The roof is the upper, support-relevant portion of a point-up regular hex: vertical clearance walls below and the two 30-degree rising facets meeting at the ridge. It does not add lower hexagonal facets to the nut clearance core.

In flat-wall orientation, the rising 45-degree entry does not need a second longitudinal roof. In box orientation, the entry is horizontal in assembled XY and receives the same global-up roof as the pocket. Existing nut-entry detents turn with the entry and throat so retention remains at the mouth of the new access path.

## Corner screw bores

Standalone wall screw bores remain horizontal and support-free, but their old 45-degree roof is replaced by tangent 30-degree facets. This keeps substantially more of the circular clearance while meeting the agreed print threshold.

Box corner screw bores are vertical. They remain true round M3 clearance bores; no pointed roof is applied. The bore choice follows the explicit print-orientation parameter and does not change the screw axis or nominal clearance diameter.

## Wall ribs

Standalone wall ribs change from rectangular projections to smooth semicylinders. Their flat diameter lies on the face-up wall, so successive layers recede without requiring support.

Box ribs use support-aware profiles selected inside the existing placement module; rib loops are not duplicated.

For `box`, a single `$fn = 6` cylinder clipped at its diameter provides the true regular half-hex cross-section. The vertical ribs extend continuously from the floor-supported horizontal rib, through the upper horizontal rib, to the underside datum of the sub-panel. They therefore provide direct perimeter support without an isolated lower-end ramp. Suspended and floor-touching horizontal ribs reuse the same low-facet core; the floor supports the bottom run directly.

Rib centerlines, vent clearances, and revision-text clearance remain unchanged. The vertical ribs form a continuous ladder and terminate at local Y = `h + sub_panel_bottom_z`, exactly matching the assembled sub-panel underside.

## Vents, labels, and unchanged geometry

Standalone wall vents remain round because their axes are vertical while the wall is printed flat. Box vents retain their existing point-up regular hexagons because their 30-degree roof facets meet the support-free threshold.

The floor receives three shallow component-placement engravings at the existing 0.6 mm compass-label depth. Each label stays within its component footprint and avoids mount holes, airflow posts, and retaining corners:

- `Pico Relay-B` is oriented like `WEST` (90 degrees);
- `PSU` is oriented like `NORTH` (0 degrees); and
- `DC/DC` is oriented like `SOUTH` (180 degrees).

These floor markings replace the raised `RELAYS`, `12V PSU`, and `DC/DC` labels on the transparent assembly keepouts. The transparent colors and component geometry remain unchanged; only their raised text is removed.

The underside of the sub-panel receives shallow mirrored wiring engravings that read normally while looking at the panel from the back:

- DC top row: `CH1`, `CH2`;
- DC bottom row: `CH3`, `CH4`, placing `CH2` and `CH4` nearest the AC input;
- left AC column: `CH5` above `CH7`;
- right AC column below USB: `CH6` above `CH8`;
- `AC` at the AC input; and
- `USB` at the USB connector.

The back engravings use the existing 0.6 mm marking depth and avoid connector openings, screw holes, and rim-relief geometry.

Wall text, floor geometry, corner-tab stack heights, nut offsets, floor locators, screw lengths, and the 0.02 mm box-only miter overlap remain unchanged.

No box-specific copy of a wall, rib loop, nut trap, or bore loop is introduced. The existing modules remain authoritative and accept print-orientation/profile parameters.

## Production print plates

Default generation produces five printable jobs: `floor`, paired `north_south_walls`, paired `east_west_walls`, `top_panel`, and `sub_panel`. Box generation uses `generate.bash --box` and produces only `box`, `top_panel`, and `sub_panel`. Individual wall, coupon, component, and assembly views remain available for diagnostics through `--view` and the OpenSCAD view selector.

The obsolete hand-positioned `plate()` presentation layout is removed rather than maintained as a production surface.

## Assembly preview Z-fighting

The rounded-rectangle label-pocket cutters are not the source of the preview artifact: they already cut from Z = 2.5 mm through Z = 5.5 mm across the top of the 3 mm panel, providing 0.5 mm of intentional penetration.

The actual coplanar interface is the mounted top-panel underside and sub-panel top, which both lie at Z = `-plate_t`. Add a named 0.01 mm separation only while `$preview` is true and apply it in the assembly placement transform. Final renders and generated STL use zero separation, so manufactured dimensions and the physical stack remain unchanged. This preserves fast OpenSCAD preview colors without requiring a long CGAL render.

## Verification and delivery

Source-contract tests will verify:

- both explicit print orientations;
- 45-degree mirrored center-facing nut entries;
- flat-wall roofed horizontal bores and box round vertical bores;
- print-up roofs on nut pockets and box entry tunnels;
- smooth standalone semicylindrical ribs and continuous low-`$fn` half-hex box ribs;
- engraved floor component labels with the required compass orientations and no raised transparent-keepout labels;
- mirrored sub-panel back labels for CH1-CH8, AC, and USB in the specified wiring layout;
- preview-only top/sub-panel separation with unchanged render geometry; and
- continued reuse of complete wall modules by `box`.
- exactly five default flat-wall print jobs and three `--box` print jobs.

Changes are committed and pushed before OpenSCAD runs. Verification renders only targeted standalone wall/corner geometry and `box`, never the full assembly. Generated STL and render logs stay outside the repository.

## Deferred follow-up

The initially proposed fifth central fastener was superseded by the full-width sub-panel USB support rib described in `2026-07-20-plamp8-subpanel-usb-rib-design.md`.
