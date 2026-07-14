# Plamp8 Top-Panel Brand Design

## Goal

Use the empty area above the top-panel revision string for understated `plamp` branding without disturbing functional labels or revision identification.

## Layout

- Add lowercase text `plamp` only to the top-panel view and printable top-panel geometry.
- Center it horizontally on the existing `revision_x` position.
- Top-align its pocket with the neighboring `COM` pocket, placing its center 19 mm above `revision_y`.
- Use DejaVu Sans at 4 mm, matching the revision text.
- Give the brand pocket the same 28 mm by 9 mm dimensions as the revision pocket.
- Retain the existing revision string, revision pocket, size, and position.

The 19 mm center offset puts both the brand and `COM` pocket top edges at y = 24 mm and leaves 10 mm between the brand and revision pockets. Matching the revision width prevents contact with the neighboring `COM` and `Nutrients` pockets. The brand remains visually subordinate to the functional channel labels and does not alter any connector or switch geometry.

## Implementation

Define named top-panel brand parameters beside the existing revision-label parameters. Add the brand pocket to the same top-panel negative section as the revision pocket, and add the flush `plamp` text beside the existing flush revision text. Both are controlled by `include_revision` so fit-test or context variants that suppress manufacturing markings remain consistent.

## Verification

Do not run OpenSCAD locally. Verify from source that:

- brand center x equals `revision_x`;
- brand center y equals `revision_y + 19`;
- brand and `COM` pocket top edges both equal y = 24 mm;
- brand and revision pocket edges have a 10 mm vertical gap;
- brand and revision pockets are both 28 mm by 9 mm;
- font size is 4 mm;
- the existing revision placement is unchanged;
- only `things/plamp8/plamp8.scad` production geometry changes.

The user will render and inspect the `top_panel` view on their machine.
