# Plamp8 Auto-Only Enclosure Design

## Goal

Add an auto-only Plamp8 enclosure variant for the future dosing box while preserving the existing toggle-equipped enclosure. Construction style and control style remain independent choices:

- separate floor and walls, with toggles;
- fused box, with toggles;
- separate floor and short walls, auto-only;
- fused short box, auto-only.

This change covers enclosure geometry only. Pump selection, pH electronics, wiring, and control software are separate work.

## Product Contract

Keep the existing product names and behavior unchanged:

- `split-box`: separate floor and walls, 128 mm high, with toggles;
- `fuse-box`: fused floor and walls, 128 mm high, with toggles.

Add two products:

- `split-box-auto`: separate floor and walls, 75 mm high, without toggles;
- `fuse-box-auto`: fused floor and walls, 75 mm high, without toggles.

The CAD model should expose a single control-style parameter, such as `auto_only`, alongside the existing choice between split and fused construction. Product definitions set this parameter; they should not require duplicate auto-only part modules.

Auxiliary products and individual views remain available. Their default behavior stays toggle-equipped unless a caller explicitly sets the auto-only parameter.

## Auto-Only Geometry

When auto-only mode is enabled:

- set enclosure wall height to 75 mm;
- remove all eight top-panel toggle holes;
- remove the matching switch-body pockets and keepouts from the sub-panel;
- remove the `Auto`, `Off`, and `On` state labels;
- retain the existing connector label font sizes;
- center each channel label over its remaining connector;
- center each of the four AC outlet openings within its former outlet-and-toggle channel area;
- center each of the four XT60 openings within its former connector-and-toggle channel area;
- keep connector mounting holes, retention geometry, and channel ordering unchanged.

The sub-panel USB support rib must be relieved directly above each AC
socket, matching the existing lower socket-rim relief. Each upper relief
follows the selected AC connector center, removes the rib across the socket
envelope, and leaves the rib intact between and around sockets. This applies
to both control styles so socket removal and wiring access do not depend on
whether toggles are fitted.

Centering is derived from each existing channel region, not from the whole panel. This preserves equal channel spacing and makes the AC and DC layouts visually consistent.

When auto-only mode is disabled, the current 128 mm enclosure, connector
locations, toggles, pockets, and labels remain unchanged. The new upper
AC-socket relief is the sole geometry change shared with manual mode.

## Height And Clearance

The Pico-Relay-B mounts directly on the 3 mm floor and has an observed height of 18 mm. The AC socket harness requires approximately 48 mm downward from the panel top to accommodate the fork connector and its 90-degree wire bend.

At a 75 mm wall height, the nominal vertical separation is:

```text
75 - 3 - 18 - 48 = 6 mm
```

The assembly model should represent these measured envelopes and assert that they do not overlap. The 6 mm is a nominal packaging margin, not permission to force the harness against the relay board. Final acceptance requires an assembly inspection and a physical dry fit because the wire bend changes when pressure is applied.

The shorter height applies only to auto-only mode. It must work identically with separately printed walls and the fused box.

## XT60 Flyback Diodes

Each 12 V inductive output will use a 1N5408 flyback diode across the XT60 terminals. The diode is part of the removable connector-and-wire assembly:

- solder it directly across the XT60 terminals with correct reverse-bias polarity;
- insulate exposed conductors with heat-shrink;
- keep it tucked within the connector's wiring-side clearance envelope;
- ensure the complete XT60, diode, and lead assembly can pass through both the top-panel and sub-panel XT60 openings during disassembly.

Do not add diode lead holes, fixed clips, or pockets to the enclosure. A separate disconnect would add contacts and allow the protection diode to be accidentally omitted. The existing removable XT60 assembly already supplies the useful disconnect boundary.

CAD verification should include a conservative wiring-side envelope behind every XT60. Polarity belongs in the wiring documentation or wiring-side marking, not in geometry that traps the diode.

## Implementation Shape

The primary changes belong in:

- `things/plamp8/plamp8.scad`: add the control-style parameter, derive height and channel placement, conditionally remove toggle geometry and labels, and add clearance envelopes/assertions;
- `cad/plamp.system.cad.json`: add the two auto-only enclosure products and pass the mode parameter to every affected item;
- CAD tests or metadata tests: verify product expansion and effective variables for all four enclosure products.

Shared placement functions should return connector and label centers for a channel. Existing manual coordinates remain the non-auto branch so the established enclosure does not shift accidentally.

## Verification

Before rendering:

- validate the Plamp8 model and CAD system metadata;
- plan all four enclosure products and confirm their exact jobs and effective variables;
- verify the manual products retain 128 mm height and toggle geometry;
- verify the auto-only products use 75 mm height and no toggle geometry.

Render both auto-only products through the managed CAD workflow. Inspect the complete logs and confirm every STL is present and non-empty. Visually inspect top panel, sub-panel, and assembly views for:

- centered AC connectors and labels;
- centered XT60 connectors and labels;
- absence of toggle holes, switch pockets, and state labels;
- unchanged connector retention and fastener access;
- lower socket-rim and upper USB-support-rib relief aligned to every AC socket;
- relay, AC harness, and XT60 wiring-envelope clearance;
- top-panel removal and XT60 assembly removal without trapped wiring.

Render or plan the existing manual products as regression coverage. Complete the design with a physical dry fit of an AC socket harness, Pico-Relay-B, and one XT60 connector carrying an insulated 1N5408 before committing to the full print.

## Non-Goals

- No pH probe, ADC board, temperature probe, pump mount, reservoir, or tubing geometry.
- No dosing or pH-control software.
- No relay-channel reassignment.
- No direction reversal; the selected peristaltic pumps are operated in one direction.
- No diode socket or separate diode disconnect.
- No reduction of the toggle-equipped enclosure height.
