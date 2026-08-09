# Plamp8 Robust Corner Nut Entry Design

## Problem and physical validation

The north and south wall corner nuts required heat and force to pass through
the 45-degree entry. Before the first revision, the diagonal mouth was 6.10 mm
wide, but only its final 1.5 mm used that width. The rest of the enlarged boss
was traversed through the calibrated 5.65 mm pocket width and 2.42 mm pocket
height. PLA therefore turned the longer tunnel into a tight interference fit.
Heating a completed wall could deform the final hex seat, allowing the nut to
rotate under load.

The first revised PLA coupon widened the complete diagonal tunnel to 6.10 mm
and raised it to 2.52 mm. A nut could then enter approximately 2 mm before
stopping. This distance matches the remaining 0.20 mm retention nibs, which
still derive from the old 5.50 mm throat. The nibs—not the widened rectangular
tunnel—are therefore the remaining insertion obstruction.

## Decision

Treat insertion and anti-rotation as separate fits:

- Keep the final M3 hex pocket width snug: 5.46 mm measured nut width plus
  0.19 mm clearance, producing 5.65 mm across flats. Width prevents rotation.
- Give the corner hex pocket the material-tolerant 0.14 mm thickness
  clearance, producing a 2.52 mm pocket height. Extra axial clearance does not
  permit rotation.
- Use the existing 6.10 mm diagonal mouth width for the complete corner entry
  tunnel, not only its outer detent segment.
- Keep the complete corner entry tunnel at the same 2.52 mm height.
- Disable retention nibs for the 45-degree wall catchers. The nut must reach
  the hex seat by finger pressure without heat or tools.
- Do not add printed plugs. Retaining a nut while handling a loose wall is
  secondary; preventing rotation while tightening the screw is required.
- Apply these tunnel overrides only in `support_free_m3_nut_trap()` and the
  matching 45-degree coupon. Side-loaded panel traps retain their existing
  dimensions.

The shared `m3_nut_catcher_negative()` module gains optional tunnel width and
tunnel height parameters. Their defaults remain the pocket dimensions, so all
existing callers preserve their geometry unless they explicitly request the
corner-entry fit.

The corner adapter additionally supplies its 0.14 mm pocket thickness
clearance and zero nib height. The 45-degree coupon must supply the identical
values. No global M3 fit constant changes.

## Test pieces

The existing `nut_catcher_adjustment_test` set remains the printable test
artifact. Its 45-degree coupons must use the same corner tunnel overrides as
the north and south walls. This avoids calibrating a simplified substitute.
Their labels identify the 6.10 mm tunnel width, 2.52 mm pocket/tunnel height,
and absence of retention nibs.
The generation command is:

```sh
plamp cad generate plamp8 --set nut_catcher_adjustment_test
```

The output revision engraving identifies the source used for the test print.

## Verification

Source-contract tests must fail before implementation and then prove that:

- the canonical catcher exposes independent optional tunnel dimensions;
- the corner trap supplies the 6.10 mm tunnel width, 2.52 mm pocket/tunnel
  height, and zero nib height;
- the 45-degree coupon supplies those same values and labels them;
- ordinary panel trap callers do not opt into the corner dimensions.

Run the Plamp CAD source tests, OpenSCAD syntax/render validation, and generate
the test set before reporting the command to print.
