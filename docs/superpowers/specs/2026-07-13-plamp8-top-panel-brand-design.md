# Plamp8 Top-Panel Brand Design

## Goal

Use the empty area above the top-panel revision string for understated `plamp` branding without disturbing functional labels or revision identification.

## Layout

- Add lowercase text `plamp` only to the top-panel view and printable top-panel geometry.
- Center it horizontally on the existing `revision_x` position.
- Place its center 12 mm above `revision_y`.
- Use DejaVu Sans at 7 mm, normal weight, matching the existing text system.
- Put the text in a 34 mm by 11 mm shallow label pocket using the existing flush-inlay construction.
- Retain the existing revision string, revision pocket, size, and position.

The 12 mm center offset leaves 2 mm between the 11 mm brand pocket and 9 mm revision pocket. The brand remains visually subordinate to the functional channel labels and does not alter any connector or switch geometry.

## Implementation

Define named top-panel brand parameters beside the existing revision-label parameters. Add the brand pocket to the same top-panel negative section as the revision pocket, and add the flush `plamp` text beside the existing flush revision text. Both are controlled by `include_revision` so fit-test or context variants that suppress manufacturing markings remain consistent.

## Verification

Do not run OpenSCAD locally. Verify from source that:

- brand center x equals `revision_x`;
- brand center y equals `revision_y + 12`;
- brand and revision pocket edges have a 2 mm vertical gap;
- font size is 7 mm;
- the existing revision placement is unchanged;
- only `things/plamp8/plamp8.scad` production geometry changes.

The user will render and inspect the `top_panel` view on their machine.
