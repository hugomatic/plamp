# Hybrid configuration compatibility

## Problem

Older Plamp versions could leave a top-level `devices` object beside the current
controller configuration. The web service ignored that object once devices were
configured inside a controller. The shared configuration loader instead tries to
migrate it and refuses to start when it names an obsolete controller.

## Rule

When any controller already has its own device configuration, that controller
configuration is the source used by Plamp. Preserve a top-level `devices` object
in the JSON file, but do not validate or migrate it.

When controllers do not contain device configuration, continue treating a
top-level `devices` object as legacy input. Migrate valid references and reject
unknown controllers as before.

## Scope

Change only configuration normalization. Do not rewrite configuration files,
create missing controllers, merge the two device lists, or alter API behavior.

## Verification

Add a regression test with current controller devices plus stale top-level devices
that reference a missing controller. Loading must succeed, use the controller's
devices, and preserve the stale object. Existing pure-legacy migration and invalid
legacy-reference tests must continue to pass.
