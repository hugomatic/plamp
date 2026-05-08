# Camera Scheduling And Settings Design

## Goal

Move camera capture from hidden host cron behavior into Plamp-owned automation with:

- one visible control plane through Plamp config, UI, API, and CLI
- per-camera schedule settings
- shared capture behavior for manual and scheduled snapshots
- lower agent token cost by making `plamp` the stable interface

This design replaces the current “manual capture in web + optional external cron” model with a first-party capture worker.

## Summary

Plamp should run a separate `plamp-capture` service that:

- reads desired per-camera capture settings from `data/config.json`
- watches for config changes and applies them as soon as possible
- executes all scheduled captures sequentially
- shares the same capture implementation as the manual “Take picture” action
- stores live worker state in `data/capture_runtime.json`

The web app remains the authority for config editing and status display. The capture worker is execution-only.

## Why This Change

Current issues:

- capture scheduling is outside Plamp’s main control plane
- cron introduces hidden machine-local state and drift
- camera capture still has legacy path assumptions in some flows
- agents have to know too much shell plumbing
- picture capture schedule is not a first-class configuration concept

Desired properties:

- every node should be able to run autonomously without an always-present agent
- all routine automation should be visible in Plamp state
- UI and CLI should manipulate the same model
- manual capture and scheduled capture should not diverge in behavior

## Architecture

### Components

1. `plamp-web`
- owns config persistence and validation
- exposes UI and API
- shows runtime status from `data/capture_runtime.json`

2. `plamp-capture`
- separate systemd service
- loads config
- maintains a small in-memory queue of capture requests
- processes captures sequentially
- writes runtime status to `data/capture_runtime.json`

3. Shared capture module
- one code path for actual snapshot execution and metadata writing
- used by both `plamp-web` manual capture and `plamp-capture` scheduled capture

### Why Separate Service

This is preferred over embedding the loop inside `plamp-web` because:

- camera loop failures do not risk web/API availability
- logs and restarts are independent
- the model scales better to multiple cameras and future node-local automations
- it preserves one control plane without requiring one process

## Config Model

Per-camera settings live under:

```json
{
  "cameras": {
    "rpicam_cam0": {
      "label": "Grow camera",
      "capture": {
        "schedule_enabled": true,
        "every_seconds": 3600,
        "autofocus_mode": "auto",
        "autofocus_delay_ms": 1200,
        "width": 2304,
        "height": 1296,
        "rotation": 0,
        "hflip": false,
        "vflip": false,
        "jpeg_quality": 90
      }
    }
  }
}
```

### Rules

- `capture` is optional; missing means no scheduled capture policy is configured
- `schedule_enabled=false` disables only automatic capture
- manual “Take picture” must still work when `schedule_enabled=false`
- each configured camera may have its own independent schedule
- multiple due cameras are processed sequentially

### Supported Settings

- `schedule_enabled`: bool
- `every_seconds`: positive integer
- `autofocus_mode`: `auto|continuous|manual|off`
- `autofocus_delay_ms`: non-negative integer
- `width`: positive integer
- `height`: positive integer
- `rotation`: `0|90|180|270`
- `hflip`: bool
- `vflip`: bool
- `jpeg_quality`: integer `1..100`

### Autofocus Rule

- if `autofocus_mode == off`, `autofocus_delay_ms` is ignored

## Runtime State

Worker runtime state lives in:

```text
data/capture_runtime.json
```

Suggested shape:

```json
{
  "worker": {
    "status": "running",
    "last_config_reload": "2026-05-07T12:00:00Z"
  },
  "queue": {
    "depth": 0,
    "active_camera_id": null
  },
  "cameras": {
    "rpicam_cam0": {
      "status": "running",
      "last_attempt": "2026-05-07T12:00:00Z",
      "last_success": "2026-05-07T12:00:01Z",
      "last_error": null,
      "consecutive_failures": 0,
      "paused_by_error": false,
      "next_due": "2026-05-07T13:00:01Z"
    }
  }
}
```

### Rules

- config expresses desired behavior
- runtime file expresses current worker state
- config and runtime must not be merged into one file

## Queue Semantics

The queue should stay simple.

### Behavior

- both manual and scheduled capture requests enqueue the same request type
- requests are processed sequentially
- no parallel capture execution
- no preemption
- no separate “manual code path” for taking pictures

### Manual Capture

- UI “Take picture” should create an immediate request
- request should use the same shared capture implementation as scheduled requests
- response may block until request completes, or the API may wait on the queued request result if implementation uses request/result signaling internally

### Scheduled Capture

- worker loop reevaluates due cameras frequently
- when config changes, waiting state is interrupted and recalculated from “now”
- changes apply as soon as possible, not only at previous cycle boundaries

## Failure Policy

### Recommendation

- sequential retries with failure tracking
- auto-pause after repeated failures

### Behavior

- increment `consecutive_failures` on failed capture
- record `last_error`
- after threshold `N` failures, set `paused_by_error=true`
- paused camera does not continue scheduled attempts until explicitly resumed by config change or operator action

Default threshold:

- `N = 5`

This avoids endless hidden thrashing for broken camera paths or disconnected hardware.

## Manual Capture And Shared Code

Manual “Take picture” should use the most identical code path possible.

This means:

- one shared capture function performs actual snapshot work
- it handles camera invocation, settle delay, file write, sidecar write, and metadata return
- web and worker call the same function

This reduces drift between scheduled and manual behavior.

## API Direction

### Existing

- keep existing manual capture route behavior

### New

Plamp should gain explicit schedule visibility through API, either:

- through existing `config` endpoints because the settings live in `config.cameras`, or
- through a dedicated runtime/status endpoint for capture worker state

Recommended runtime endpoint:

- `GET /api/capture-runtime`

This should return `data/capture_runtime.json` content or a normalized equivalent.

## CLI Direction

The long-term public automation interface should be `plamp`, not repo scripts.

### Near-term

- existing `plamp pics take`
- existing config manipulation through `plamp config ...`

### Later

Add first-class schedule commands such as:

- `plamp pics schedule get`
- `plamp pics schedule set <camera> ...`
- `plamp pics schedule pause <camera>`
- `plamp pics schedule resume <camera>`

This keeps agent usage token-cheap and avoids shell-specific knowledge.

## Settings UI Design

### Camera Section

In `/settings`, each camera should render as a block with:

1. camera identity row
- `ID`
- `Label`
- detected hardware info

2. nested capture settings table
- `Capture schedule enabled`
- `Every seconds`
- `Autofocus mode`
- `Autofocus delay ms`
- `Width`
- `Height`
- `Rotation`
- `HFlip`
- `VFlip`
- `JPEG quality`

### Important Labeling Rule

Do not use bare `enabled`.

Use:

- `Capture schedule enabled`

and clarify:

- only affects automatic captures
- manual “Take picture” still works

### Visual Structure

Use the same nested visual pattern for:

- camera capture settings tables
- Pico Scheduler device tables

Nested tables should have:

- left indentation
- subtle left border
- lightly tinted background

This is required because current settings UI is visually confusing and nested ownership is not obvious enough.

## Device Symmetry

This design also supports adding `enabled` to devices later, with schedule-specific semantics:

- device stays configured
- automatic scheduler control is excluded

This is not required to ship the camera worker, but the UI styling should anticipate the same pattern.

## Installation / Operations

### Service

Add a new systemd service:

- `plamp-capture.service`

It should:

- start after network and Plamp repo mounts are available
- run as the Plamp user
- use the same repo root and environment conventions as `plamp-web`

### Bootstrap

Installer should eventually own:

- service creation for `plamp-web`
- service creation for `plamp-capture`
- optional nginx public proxy

Cron should become transitional only and then be retired.

## Migration

### From Current State

1. keep current manual capture working
2. add repo-local/shared capture implementation
3. add runtime worker and state file
4. surface camera schedule settings in config/UI
5. migrate nodes from cron to `plamp-capture`
6. remove legacy path assumptions and old script dependencies where possible

### Legacy Path Assumption

Current camera capture still depends on legacy `capture_script` configuration in some paths.

This design moves toward:

- Plamp-owned capture settings in repo/config
- no required `/home/hugo/.openclaw/...` path assumptions

## Non-Goals

This slice does not require:

- multi-camera parallel capture
- arbitrary camera command `extra_args`
- cloud dependency
- central supervisor architecture
- full “agent everywhere” requirement

## Risks

### Main Risks

- queue/manual request behavior may be awkward if API waits synchronously for long captures
- camera-specific tuning defaults may vary by module and lighting
- partial migration may leave confusing overlap with cron or legacy scripts

### Mitigations

- keep queue semantics simple and visible
- expose runtime state clearly
- make installer/service model explicit
- remove or clearly mark transitional cron paths

## Testing

Required tests should cover:

- config validation for per-camera capture settings
- runtime reload on config change
- sequential handling of multiple due cameras
- manual + scheduled requests using shared capture path
- autofocus delay ignored when autofocus is off
- UI rendering of nested camera capture settings table
- UI rendering indentation for camera tables and device tables
- failure count and auto-pause behavior

## References

- `docs/superpowers/specs/2026-04-12-camera-capture-api-design.md`
- `docs/superpowers/specs/2026-04-15-settings-unification-design.md`
- `docs/superpowers/specs/2026-04-30-pico-schedulers-settings-design.md`
- `docs/superpowers/specs/2026-04-30-plamp-cli-design.md`
