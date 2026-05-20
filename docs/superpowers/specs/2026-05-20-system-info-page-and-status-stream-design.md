# System Info Page and Status Stream Design

## Goal

Replace the overloaded `system status` concept with a clearer `system info` snapshot command and a matching web page.

The page should give the operator a small, reliable control surface:

- host/system identity and live runtime facts
- `Restart`
- `Reinstall`
- `Upgrade`
- `Logs`

No hostname editor belongs on this page.

## Scope

In scope:

- Rename the one-shot CLI snapshot command from `system status` to `system info`.
- Add a live CLI stream command for `/api/status?stream=true`.
- Add a web page for system information and basic operational actions.
- Wire the page actions through server-side `plampctl`-backed endpoints.
- Keep logs readable from the page.

Out of scope:

- Hostname editing.
- Full settings editing.
- Additional operational actions beyond restart, reinstall, upgrade, and logs.
- Any new config editor behavior.

## CLI Behavior

### `plamp system info`

This command replaces `plamp system status` as the one-shot host/system snapshot.

It should return the same kind of data currently exposed by `/api/system`, including:

- hostname
- hardware facts
- detected Picos/cameras
- git branch and commit
- service/tooling metadata

### `plamp status`

This command becomes the live stream command.

It should connect to `/api/status?stream=true` and print each SSE message as it arrives.

Output modes:

- default: compact JSON per event
- `--pretty`: pretty-printed JSON per event

The stream command is for live state, not system identity.

## Web Page

Add a dedicated system info page that presents the same snapshot data as `plamp system info`.

Page contents:

- host name and identity
- OS/version and hardware facts
- git branch/commit
- connected/reported hardware
- logs preview or fetch control
- operational buttons

The page should be separate from the main schedule UI and from the settings page.

## Operational Actions

The page should expose four actions:

- `Restart`
- `Reinstall`
- `Upgrade`
- `Logs`

Recommended behavior:

- `Restart` restarts the web service.
- `Reinstall` reruns the repo install/deploy path.
- `Upgrade` pulls the latest repo code and restarts the service.
- `Logs` fetches recent service output.

The page does not need to expose the underlying shell commands in the UI.
The server can use `plampctl` or the same deploy/restart plumbing it already uses.

## Data Flow

1. The page loads the current system snapshot.
2. The page shows static identity information and operational buttons.
3. The CLI `system info` command reads the same snapshot endpoint.
4. The CLI `status` command streams `/api/status?stream=true`.
5. After a successful restart, reinstall, or upgrade, the page refreshes its snapshot.
6. Logs are read on demand, not streamed continuously.

## Error Handling

- If an action fails, the page shows the error and keeps the current snapshot visible.
- If logs cannot be read, the page should show a concise failure message.
- If the stream disconnects, the stream command should report that clearly without pretending it is a system-info failure.

## Testing

Manual checks:

- `plamp system info` returns a one-shot snapshot.
- `plamp status` streams live status events.
- The system page renders snapshot data.
- Restart, reinstall, upgrade, and logs all work from the page.
- No hostname editor appears anywhere on the page.

Automated checks:

- CLI tests should cover `system info` and streaming `status`.
- Page tests should cover the new system page copy and action labels.
- Server tests should cover the action endpoints and the snapshot response shape.

## Decision

Keep system identity and live status separate:

- `system info` for one-shot snapshot
- `status` for streaming state
- the system page for human operations

That keeps the naming unambiguous and avoids mixing live telemetry with host metadata.
