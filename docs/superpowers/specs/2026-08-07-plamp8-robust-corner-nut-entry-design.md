# Plamp8 Robust Corner Nut Entry Design

## Problem

The north and south wall corner nuts require heat and force to pass through
the 45-degree entry. The current diagonal mouth is 6.10 mm wide, but only its
final 1.5 mm is that wide. The rest of the enlarged boss is traversed through
the calibrated 5.65 mm pocket width and 2.42 mm pocket height. PLA therefore
turns the longer tunnel into a tight interference fit. Heating a completed
wall can deform the final hex seat, allowing the nut to rotate under load.

## Decision

Treat insertion and retention as separate fits:

- Keep the final M3 hex pocket at its calibrated dimensions: 5.46 mm measured
  nut width plus 0.19 mm clearance, and 2.38 mm measured nut thickness plus
  0.04 mm clearance.
- Use the existing 6.10 mm diagonal mouth width for the complete corner entry
  tunnel, not only its outer detent segment.
- Give the complete corner entry tunnel the earlier, material-tolerant 0.14 mm
  thickness clearance, producing a 2.52 mm tunnel height.
- Keep the retention nibs and snug hex pocket. The tunnel is permitted to be
  roomy because it guides the nut; the pocket prevents rotation.
- Apply these tunnel overrides only in `support_free_m3_nut_trap()` and the
  matching 45-degree coupon. Side-loaded panel traps retain their existing
  dimensions.

The shared `m3_nut_catcher_negative()` module gains optional tunnel width and
tunnel height parameters. Their defaults remain the pocket dimensions, so all
existing callers preserve their geometry unless they explicitly request the
corner-entry fit.

## Test pieces

The existing `nut_catcher_adjustment_test` set remains the printable test
artifact. Its 45-degree coupons must use the same corner tunnel overrides as
the north and south walls. This avoids calibrating a simplified substitute.
The generation command is:

```sh
plamp cad generate plamp8 --set nut_catcher_adjustment_test
```

The output revision engraving identifies the source used for the test print.

## Verification

Source-contract tests must fail before implementation and then prove that:

- the canonical catcher exposes independent optional tunnel dimensions;
- the corner trap supplies the 6.10 mm width and 2.52 mm height;
- the 45-degree coupon supplies those same values; and
- ordinary panel trap callers do not opt into the corner dimensions.

Run the Plamp CAD source tests, OpenSCAD syntax/render validation, and generate
the test set before reporting the command to print.
