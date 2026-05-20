# Status Path Filtered Read Model Design

## Overview

Make `/api/status` the single read surface for live and snapshot data.

All public GET-style reads in the UI and CLI should move to `/api/status`, with optional path filtering and streaming:

- `GET /api/status` for the full snapshot
- `GET /api/status?stream=true` for the full live stream
- `GET /api/status?path=...` for filtered snapshots
- `GET /api/status?stream=true&path=...` for filtered live streams

This removes the need for public consumers to call `/api/controllers/{role}` for reads.

## Goals

- Keep `/api/status` as the canonical read model.
- Support one or more `path=` filters per request.
- Support nested paths such as `controllers.octo_relay`.
- Return filtered results in request order.
- Return all leaves under each matched path.
- Make streaming per-client, with each SSE connection using its own filter list.
- Emit stream updates only when a changed node intersects the client’s filtered paths.
- Update the test API page so the filtering and streaming behavior is visible and easy to exercise.
- Update the system info page so it reads from `/api/status` instead of a separate system GET path.

## Non-Goals

- No new write API.
- No change to controller apply or schedule write endpoints.
- No attempt to make SSE bidirectional.
- No backward-compatible aliasing of old controller GET usage in public UI/CLI.
- No generic patch protocol beyond filtered snapshots and filtered stream updates.

## Read Model Contract

### Full Snapshot

`GET /api/status` returns the current full read model.

### Filtered Snapshot

`GET /api/status?path=system`

`GET /api/status?path=controllers.octo_relay`

`GET /api/status?path=system&path=controllers.octo_relay`

Rules:

- Each `path=` value is a dotted path into the status tree.
- A path may match a subtree.
- The response should contain the leaves under the matched subtree.
- Any request with one or more `path=` filters should return an array of `{path, node}` objects in request order.
- The `path` field should echo the requested path, so the caller can map results back to filters without guessing.

### Nested Paths

Nested paths are allowed anywhere the status tree exposes them.

Examples:

- `system.host`
- `system.software`
- `controllers.octo_relay`
- `controllers.octo_relay.telemetry`

## Streaming Contract

`GET /api/status?stream=true` uses the same path filtering rules as the snapshot API.

Rules:

- Filters are per connection.
- Each SSE client receives only the filtered portion of the status tree.
- The server should emit an update only when a change intersects one of the filtered paths.
- The initial event should provide the filtered snapshot for that connection.
- Subsequent events should carry the same filtered array-of-paths shape, not an unrelated global tree.

The client should not need to interpret a patch language to use this stream.

## UI Changes

### System Page

The system page should keep its top menu and operational actions, but its data should come from filtered `/api/status` reads.

Expected behavior:

- load the system page from `/api/status?path=system`
- keep `Restart`, `Reinstall`, `Upgrade`, and `Logs`
- do not reintroduce a hostname editor
- keep the top navigation visible

### Test API Page

The test API page should become the place to exercise filtered status reads and streams.

It should let the user:

- view the full `/api/status` snapshot
- add and remove multiple `path=` filters
- run a filtered GET request
- start a filtered stream
- see live SSE messages as they arrive
- toggle pretty output for streamed JSON

The page should show the filter paths explicitly so the user can see what is being requested.

### Controller Read Usage

Public UI pages should stop calling `/api/controllers/{role}` for reads.

The controller dashboard should instead use filtered `/api/status` reads for the data it needs.

## CLI Changes

The CLI should use `/api/status` for reads that currently go through controller GET calls.

Recommended shape:

- `plamp status` for the live stream
- `plamp status --path ...` for filtered reads/streams
- `plamp system info` for system-only snapshot data

Rules:

- `system info` must read from `/api/status` with a system filter, not from a separate system read path.
- CLI output should preserve the filtered path labels when multiple paths are requested.
- The old controller GET commands should stop being used as read surfaces in normal flows.

## Error Handling

- An invalid path should fail clearly and report the bad path.
- An empty filter result should be distinguishable from a transport failure.
- Stream disconnects should be reported as stream errors, not as normal status data.
- If the user asks for multiple paths and one matches nothing, the response should still preserve the valid matches.

## Testing

Required coverage:

- `/api/status` returns the full read model.
- filtered `/api/status` reads return the expected subtree leaves.
- multiple `path=` filters return an ordered array of `{path, node}` objects.
- filtered SSE streams emit only when matching nodes change.
- the system page reads from filtered `/api/status`.
- the test API page can add multiple paths and show both snapshot and streaming results.
- public UI and CLI no longer rely on `/api/controllers/{role}` for reads.

## Decision

Use `/api/status` as the canonical read surface, with path filters that work the same way for snapshot and streaming requests.
