# Main Page Schedule Editor Stream Sync Design

## Goal

Keep the main-page schedule editor reliable while the page continues to receive live server updates.

The editor should stay simple:

- live telemetry keeps refreshing
- open schedule inputs are not overwritten by incoming SSE updates
- device membership changes can add or remove whole editor rows while editing
- the server remains authoritative on submit

## Scope

In scope:

- Use the existing live state stream as the read model for the page.
- Keep schedule edits local to the browser while a controller is open for editing.
- Allow live updates to refresh read-only parts of the controller card.
- Allow device add/remove changes to update the editor row list.
- Let the server reject stale submits instead of trying to recover them client-side.

Out of scope:

- Client-side merge logic for all incoming state changes.
- Patch protocols or per-field reconciliation.
- Optimistic writes.
- Conflict resolution beyond server rejection and user retry.

## Design

The browser treats the live stream as authoritative for the board, but not for open form fields.

When a controller enters edit mode:

- the editor rows for that controller become local draft state
- incoming SSE updates do not rewrite the current input values
- the page may still update read-only telemetry for that controller
- if the controller’s device list changes, the editor may add or remove whole rows to match membership

The page does not attempt to merge field-by-field changes from the stream into the draft. That keeps the client small and avoids the user’s edits being clobbered by a live refresh.

The intended read path is a single full-state stream, preferably `GET /api/status?stream=true`. A full snapshot resend is acceptable after writes as long as the client preserves the active editor draft.

## Data Flow

1. The page loads a full snapshot of current status/config-derived controller data.
2. The page subscribes to the live stream.
3. Read-only display parts rerender from each new snapshot.
4. If a controller is not being edited, its schedule view may rerender normally.
5. If a controller is being edited, only device membership changes are reflected in the editor.
6. On submit, the browser sends the draft to the write endpoint.
7. The server validates against current state and either applies the change or rejects it.
8. On success, the page rerenders from the fresh snapshot and closes the editor.

## Error Handling

- If a device disappears before submit, the server rejects the stale draft.
- If a device appears while editing, the row can be added without rewriting existing values.
- If the stream resends the same full snapshot, the open editor should not flicker or lose user-entered values.
- If the server returns an error, the editor stays open and shows the error near the controls.

## Testing

Manual checks:

- Open schedule editor and verify live telemetry still updates.
- Verify typing into a schedule input is not reset by incoming snapshots.
- Verify device add/remove changes can appear while editing.
- Verify save succeeds and the editor closes after apply.
- Verify stale submit returns a server error without dropping the draft unexpectedly.

Automated checks:

- Keep the current page render tests for the schedule editor.
- Add coverage for preserving editor draft state across rerenders.
- Add coverage for membership-only updates during editing if the implementation exposes it as a helper.

## Decision

Use a full-state stream for reads, local draft state for the editor, and server-side validation for writes.

That keeps normal use reliable without introducing a client-side merge system.
