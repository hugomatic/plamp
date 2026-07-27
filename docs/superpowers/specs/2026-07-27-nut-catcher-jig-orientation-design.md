# Nut Catcher Jig Orientation Design

## Goal

Make each nut-catcher adjustment coupon represent a usable printed catcher orientation.

## Changes

- Make the `45` coupon use the same local transform as the north-wall corner nut catcher, including its support-free flat roof.
- Make `S RF` and `S R30` expose their insertion shafts at the coupon `-Y` edge, like the other one-per-line coupons.
- Keep geometry, labels, candidate values, nibs, and all non-sideways variants unchanged.

## Verification

Add source-level regression checks for the north-canonical 45 transform and the sideways shaft orientation; render the adjustment-test set and inspect the resulting logs.
