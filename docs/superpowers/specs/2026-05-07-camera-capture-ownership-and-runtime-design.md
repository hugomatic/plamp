# Camera Capture Ownership And Runtime Design

## Goal

Make camera capture a first-class Plamp responsibility with one simple rule:

- each camera writes into one configured destination folder

The camera layer does not need to know what a grow is. If a camera is effectively owned by a grow, its configured destination folder points into that grow's `captures` tree.

This replaces the split model where:

- web/manual capture writes to `data/camera/captures`
- legacy grow tooling writes directly into `grow/grows/<grow-id>/captures`
- periodic capture is owned by cron outside the main Plamp control plane

## Summary

Plamp should own both manual and periodic capture through one shared capture path.

Per camera:

- config declares the destination folder and scheduling settings
- manual and automatic captures write into the same folder tree
- filenames encode enough meaning that no sidecar JSON is required
- runtime keeps a small recent-capture buffer for the UI and agents

The service remains responsible for taking pictures. Config says what should happen; runtime says what is happening now.

## Why This Change

Current problems:

- there are two storage conventions for captures
- manual capture and scheduled capture are not clearly one system
- cron hides behavior outside the visible Plamp control plane
- the UI has to reason about `camera_roll` versus grow captures instead of one canonical capture model
- agents need to understand too much implementation detail

Desired properties:

- one camera, one configured destination
- manual and automatic captures share the same execution path
- images naturally become grow evidence when their destination is a grow capture folder
- the UI and agents can work from runtime state instead of scanning disk for every question
- configuration stays small and easy to understand

## Ownership Model

Camera ownership is folder-based, not grow-based.

Each camera declares:

- a `capture_dir`
- whether the camera is enabled
- whether automatic capture is enabled
- how often automatic capture runs
- camera-specific capture settings

The capture subsystem does not need a `grow_id`. It only needs a valid destination path.

If the destination path is:

```text
grow/grows/grow-thai-basil-siam-queen-2026-03-27/captures
```

then the camera is effectively serving that grow.

This keeps the camera subsystem generic while still supporting grow-owned evidence.

## Config Model

Per-camera settings live under:

```json
{
  "cameras": {
    "rpicam_cam0": {
      "label": "Top view",
      "capture_dir": "grow/grows/grow-thai-basil-siam-queen-2026-03-27/captures",
      "enabled": true,
      "auto_enabled": true,
      "capture_every_seconds": 3600,
      "manual_prefix": "manual",
      "auto_prefix": "auto",
      "autofocus_mode": "auto",
      "autofocus_delay_ms": 1200
    }
  }
}
```

### Rules

- `capture_dir` is required for configured cameras that can capture
- `capture_dir` is repo-relative only
- absolute paths are rejected
- canonical camera IDs should use stable Plamp-visible IDs such as `rpicam_cam0`
- low-level device-tree or bus-path details belong in `System status`, not in the canonical camera config
- `enabled=false` disables the camera entirely
- `auto_enabled=false` disables only periodic capture
- manual capture still works when `auto_enabled=false`, as long as `enabled=true`
- `capture_every_seconds` is required when `auto_enabled=true`
- `manual_prefix` and `auto_prefix` default to `manual` and `auto`
- prefixes should be simple path-safe strings

### Why Repo-Relative Only

Repo-relative paths are preferred because they:

- keep behavior predictable across machines
- reduce security and validation complexity
- make UI, runtime, and agent tooling simpler
- preserve the option to add named storage roots later without starting from arbitrary absolute paths now

## Capture Layout

Each camera writes under its configured `capture_dir` using date subfolders:

```text
<capture_dir>/YYYY-MM-DD/<kind>-<camera_id>-<timestamp>-<token>.jpg
```

Example:

```text
grow/grows/grow-thai-basil-siam-queen-2026-03-27/captures/2026-05-07/auto-cam0-2026-05-07T18-12-44Z-a1b2c3.jpg
```

### Rules

- no sidecar JSON is written
- no separate `manual/` or `auto/` folders are created
- `kind` is one of `manual` or `auto`
- `camera_id` is included in the filename as a disambiguator
- timestamps use UTC `Z` form
- token prevents collisions when two captures happen in the same second

### Why No Sidecars

Sidecars add file count, cognitive overhead, and token cost for agents. The chosen filename structure carries the minimum metadata needed for browsing and recent-history display.

If richer semantics are needed later, they should live in a higher-level event or note system rather than in per-image sidecars.

## Runtime State

Runtime should expose per-camera state and a small in-memory recent history.

Suggested shape:

```json
{
  "cameras": {
    "cam0": {
      "config": {
        "capture_dir": "grow/grows/grow-thai-basil-siam-queen-2026-03-27/captures",
        "enabled": true,
        "auto_enabled": true,
        "capture_every_seconds": 3600
      },
      "current": {
        "capturing": false,
        "last_capture_at": "2026-05-07T18:12:44Z",
        "last_capture_path": "grow/grows/grow-thai-basil-siam-queen-2026-03-27/captures/2026-05-07/auto-cam0-2026-05-07T18-12-44Z-a1b2c3.jpg",
        "last_error": null,
        "next_capture_at": "2026-05-07T19:12:44Z"
      },
      "recent_captures": [
        {
          "kind": "auto",
          "timestamp": "2026-05-07T18:12:44Z",
          "path": "grow/grows/grow-thai-basil-siam-queen-2026-03-27/captures/2026-05-07/auto-cam0-2026-05-07T18-12-44Z-a1b2c3.jpg"
        }
      ]
    }
  }
}
```

### Rules

- runtime is not persisted as a canonical history log
- runtime keeps the last `10` captures per camera in memory
- on service startup, recent capture history is seeded from disk once so the UI is not blank after a restart
- after startup seeding, runtime continues in memory

This gives the UI and agents a low-token summary without forcing them to scan the full capture tree for routine questions.

## Service Model

Plamp should own picture taking inside the Plamp service layer rather than through host cron.

### Behavior

- manual "Take picture" and periodic capture use the same shared capture implementation
- captures are executed sequentially
- no parallel camera capture is required in this phase
- if two cameras are due, they are processed one after the other

Sequential execution is simpler, good enough for the current scale, and avoids introducing coordination code that is not yet justified.

## UI Direction

Settings should show one camera row per configured or detected camera with room for:

- `camera_id`
- label
- `capture_dir`
- `enabled`
- `auto_enabled`
- `capture_every_seconds`
- autofocus mode
- autofocus delay

`System status` should continue to show the lower-level detected camera details, such as model, lens, and any hardware path or connector identity that is useful for debugging.

The main page camera section should show:

- the latest selected image
- recent captures from runtime
- manual "Take picture"
- a readable distinction between manual and automatic captures derived from filename or runtime metadata

The current `camera_roll` versus grow filter model should be retired in favor of camera-centric browsing over canonical capture destinations.

## API Direction

Existing manual capture endpoints may stay, but their behavior changes:

- manual capture writes into the selected camera's configured `capture_dir`
- capture listing is based on camera-configured destinations rather than the old shared camera-roll folder
- runtime should expose current camera status and recent captures so agents do not need to enumerate files for basic questions

This keeps the interface stable while correcting the storage model underneath it.

## Failure Handling

Per camera runtime should keep:

- `last_error`
- `last_capture_at`
- `capturing`
- `next_capture_at`

This phase does not require a complex retry framework. A straightforward loop with visible failure state is enough.

If capture repeatedly fails, the important thing is that:

- the error is visible
- the camera does not appear healthy in runtime
- the UI can show the failure plainly

## Migration

This design intentionally moves away from:

- `data/camera/captures` as the primary destination for new captures
- cron as the canonical periodic capture owner
- sidecar-based capture metadata
- the semantic split between generic camera roll and grow captures

Migration behavior for old files can be simple:

- existing folders remain readable
- new captures use the new per-camera destination model
- old capture listings may continue to work temporarily, but the canonical forward path is camera-configured destinations

## Open Scope Boundaries

This design does not add:

- grow-specific camera business logic
- chat or annotation storage attached directly to image files
- arbitrary absolute storage paths
- parallel capture execution
- long-term persistent capture history in runtime

Those can be layered later if needed without changing the core ownership model.

## Superseded Direction

This spec supersedes the parts of [`2026-05-07-camera-scheduling-and-settings-design.md`](./2026-05-07-camera-scheduling-and-settings-design.md) that assumed:

- a separate shared `camera_roll` destination
- sidecar capture metadata as the main representation
- a primary split between web-managed captures and grow-managed captures

The preferred direction is now:

- folder-owned cameras
- one shared capture path
- repo-relative destinations
- no sidecars
- runtime-first recent capture visibility
