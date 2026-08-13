# Plamp8 Laser-Cut Enclosure Exploration

## Status and purpose

This document records the goals, constraints, existing features, and design questions considered while exploring a laser-cut version of the Plamp8 enclosure. It deliberately does not select an architecture or prescribe a solution. Its purpose is to preserve the design context so exploration can resume later without repeating it.

## Motivation

The current enclosure takes too long to manufacture because the large floor and walls are 3D printed. A 40 W Creality Falcon2 diode laser and approximately 1/8-inch birch plywood are available. The investigation concerns moving suitable planar geometry to laser cutting while retaining 3D printing only where it provides capabilities that flat sheet cannot.

## Primary goals

- Reduce total 3D-printing time substantially.
- Keep as much of the existing Plamp8 design, dimensions, component layout, and assembly logic as practical.
- Keep all four walls removable during wiring so the electronics are accessible without walls surrounding them.
- Preserve serviceability after assembly.
- Avoid introducing another complicated or unreliable fastener-retention system.
- Identify the exact boundary between laser-cut sheet parts, printed features, and commodity hardware before choosing a construction method.

## Fabrication constraints

- The expected sheet material is nominal 1/8-inch birch plywood; actual thickness must be measured because plywood thickness varies.
- Laser-cut edges are perpendicular to the sheet. The current 45-degree wall mitres cannot be reproduced directly.
- The laser can make profiles, holes, slots, tabs, ventilation patterns, and engraving.
- A single laser-cut sheet cannot make countersinks, counterbores, horizontal bores, raised bosses, ribs, ledges, or enclosed nut pockets.
- Kerf and joint clearance will need measurement if fitted sheet joints are used.
- The existing screws include countersunk screws, but button-head screws may be appropriate where a head must remain visible on plywood.
- No current tooling should be assumed for cutting threaded rod or tapping custom metal parts.

## Existing non-planar enclosure features

These features are currently integrated into printed parts and cannot be transferred directly to one flat laser-cut sheet.

### Corner and wall fastening

- Corner screw bosses
- Boss spines connecting or reinforcing screw locations
- Wall corner tabs
- Horizontal screw bores
- Captured-nut pockets or nut catchers
- Nut-entry tunnels
- Nut-retention detents
- Countersinks and counterbores
- The current 45-degree wall mating edges
- Local wall thickening around joints
- Wall stiffening ribs and gussets
- Raised wall, floor, top-panel, and sub-panel locating features

### Floor and component mounting

- Countersunk floor fasteners
- Floor locator lands and keys
- Mounting pedestals
- PSU retaining corners and side guides
- DC/DC converter retaining corners
- Relay retaining features
- PSU and converter airflow standoffs
- Other raised component-positioning features

### Panel support

- Features that establish the sub-panel height
- The sub-panel's integrated nut catchers
- The raised perimeter and support ribs on the sub-panel
- Lips, ledges, and screw lands associated with the top/sub-panel stack

## Naturally planar features

The following are compatible with laser-cut sheet construction in principle:

- Floor, wall, top-panel, ring, and other flat outlines
- Ordinary through-holes and clearance holes
- Slots and tabs
- Ventilation patterns
- Connector openings
- Labels and other engraved markings
- Flat component-location marks or openings

This classification does not imply that any particular existing part will be converted.

## Assembly and servicing considerations

- Wiring should be possible with no walls installed.
- The relationship between the floor, sub-panel, top panel, and electronics must remain understandable when the walls are absent.
- A wall may need to be installed by sliding from above or by placing it sideways; the advantages of both methods were considered.
- Sideways placement could allow one wall to be removed without removing the top, but may require additional clamps, corner pieces, or hardware.
- Sliding walls favor continuous corner channels or posts and generally require top access.
- Finger joints could align and strengthen wall corners, but conventional finger joints conflict with independent sliding and may couple removal of adjacent walls.
- Plain butt seams preserve independent wall placement but require another structure to align and reinforce the corners.
- The acceptable number of visible wall screws remains undecided; four to six screws per wall was discussed.

## Corner structures considered

The discussion considered these forms without selecting one:

- Four full-height printed road-case-style corner posts with two wall channels
- Eight short printed corner units, one at each upper and lower corner
- Four full-height internal 90-degree L-shaped corner rails
- Eight short commodity metal 90-degree brackets
- Printed boss or alignment geometry reinforced by short metal brackets
- Printed structures screwed to the plywood walls through ordinary laser-cut holes

Printing long corner structures flat on a 45-degree exterior face was considered because the two perpendicular channels or flanges could then have symmetric, support-friendly print orientations.

Short metal brackets were considered beneath upper and lower boss regions rather than as full-height metal rails. The exact bracket dimensions, hole sizes, hole spacing, and hole shape are unknown until suitable hardware is found.

## Fastener considerations

- A laser cannot form the conical seat required by a countersunk screw.
- Countersunk screws bearing directly on thin plywood could remove or crush too much material even if a countersink were produced by another tool.
- Button-head screws could bear directly against plywood through plain laser-cut clearance holes and may provide an acceptable visible finish.
- Ordinary machine-screw heads may protrude more than desired.
- Screw heads could be visible outside or hidden inside; hidden heads raise questions about nut insertion and retention.
- Directly accessible nut seats are preferable to long or angled loading tunnels when geometry permits.
- The placement of nuts, printed nut catchers, or ordinary washers depends on the selected corner structure.

## Floor considerations

- The present floor contains countersinks and raised component-support geometry.
- Laser-cutting the floor removes the integrated countersinks, retaining corners, airflow posts, locators, and other raised features.
- A second floor layer with larger openings around screw heads was considered as a way to accommodate countersunk heads using only perpendicular laser cuts.
- Adding material below the existing floor datum would preserve internal component heights while increasing the external height beneath the floor.
- Raising the interior floor datum instead would affect internal height and existing component relationships.
- Small printed component supports could potentially be located by laser-cut holes or slots, but their attachment method has not been selected.

## Sub-panel considerations

- The sub-panel contains nut catchers and other detailed geometry that may justify retaining a printed lower portion.
- Printing only the functional bottom of the sub-panel was considered.
- Replacing its tall printed perimeter with one or more laser-cut rings was considered.
- The ring thickness and stack would affect the existing sub-panel support height and top-panel relationship.
- The sub-panel load path must be considered independently from wall attachment, particularly because all walls should be absent during wiring.
- If upper and lower corner structures are connected only through the plywood walls, the upper panel assembly is not connected to the floor while those walls are absent.
- It remains undecided whether the sub-panel must stay at its normal installed height during wall-free wiring.

## Top-panel considerations

- The top panel's lettering can be laser engraved.
- Its connector and fastener openings are planar and can be laser cut.
- The top could therefore remain printed or become a laser-cut part; no choice has been made.
- Its attachment and support depend on the eventual corner and sub-panel structure.

## Component-support considerations

- PSU, DC/DC converter, and relay locations should remain unchanged unless a later design explicitly revisits the component layout.
- Their retaining corners, side guides, standoffs, and mounting pedestals are inherently non-planar.
- These features could remain printed separately from the floor, be incorporated into other printed pieces, or be replaced with commodity hardware.
- Separating them from the floor would reduce the size and duration of individual prints but introduces attachment and alignment questions.

## Reference-frame and CAD context

The existing workflow can create a 3D OpenSCAD model, intersect or project the desired plane onto XY, and export a 2D DXF or SVG for laser cutting. That workflow remains viable for authoritative profiles and assembly previews.

Separately, build123d was discussed as a possible future geometry foundation because it provides explicit coordinate frames and introspection of evaluated geometry. That investigation is not a requirement or selected dependency for the laser-cut enclosure work.

## Questions intentionally left open

- Whether walls slide vertically or attach sideways
- Whether individual walls must be removable while the top remains installed
- Four full-height corner structures versus eight short corner structures
- Printed corner structures, metal brackets, or a combination
- Finger joints, butt seams, channels, clamps, or another wall-edge treatment
- The number and placement of wall fasteners
- External button-head screws versus another fastening arrangement
- How nuts are inserted, constrained, and accessed
- Whether the floor uses one layer, multiple layers, printed adapters, or different screws
- Which floor and component features remain printed
- Whether the sub-panel remains at operating height during wall-free wiring
- How much of the sub-panel remains printed and how a perimeter ring participates
- Whether the top panel remains printed or becomes engraved plywood
- Which exact metal brackets and fasteners are available
- Measured plywood thickness, laser kerf, and acceptable fit clearances

## Scope boundary

This is an exploration record, not an implementation specification. It authorizes no CAD changes and selects no construction approach. A later design must resolve the open questions and define test coupons, interfaces, tolerances, assembly order, and verification before implementation begins.
