# Static Multi-Page Plamp Web Design

## Goal

Complete the current web migration as a framework-free static multi-page
application. The browser obtains all Plamp state and performs all actions through
REST and SSE. FastAPI may serve the files as a deployment convenience, but it
does not render or inject host, controller, configuration, camera, or revision
state into them.

This is not a single-page application and does not add React, a client router, a
bundler, Node, or a JavaScript package toolchain. A future framework-based client
would be a separate project and service using the same REST/SSE API.

## Page and route model

Existing public URLs remain stable:

| URL | Static file | Runtime data |
| --- | --- | --- |
| `/` | `index.html` | REST plus controller SSE |
| `/settings` | `settings.html` | configuration and system REST APIs |
| `/system` | `system.html` | system and log REST APIs |
| `/controllers/{controller}` | `controller.html` | controller REST and SSE APIs |
| `/api/test` | `api-test.html` | REST/SSE API discovery and requests |

Every controller URL serves the same `controller.html`. Its JavaScript reads the
controller identifier from the URL, requests that controller's data, and opens
that controller's SSE stream. An unknown or unavailable controller produces an
explicit error in the page based on the API response; the page does not invent
or retain apparently live state.

FastAPI serves these documents with `FileResponse` and serves shared static
assets below `/static/`. API routes retain their existing meanings.

## Shared browser shell

Plain shared JavaScript owns the common page shell:

- navigation links for Home, Settings, System, and API test;
- controller links discovered from `GET /api/controllers`;
- hostname and Git revision obtained from `GET /api/system`;
- consistent active-page indication and visible bootstrap failures.

Pages load the same shared shell rather than carrying independent copies of the
menu. Shared requests are memoized within a document so a page-specific script
can reuse the system or controller discovery response without issuing a second
request.

Shared CSS owns the shell, navigation, buttons, messages, and basic responsive
layout. Page-specific CSS and JavaScript remain separate static assets when that
makes a page easier to understand. Static does not mean one large HTML file.

## Page behavior

### Settings

The settings page reconstructs its current form from `GET /api/config` and
`GET /api/system`. Existing saves continue through the current configuration
REST endpoints. It preserves controller and device ordering, hidden controller
data, camera matching, and the combined-save behavior covered by the existing
tests. A failed load disables saving and identifies the failed request. A failed
save leaves the editor values visible and reports the server error.

### Controller diagnostics

The controller page derives the identifier only from the URL. It loads the
controller snapshot and serial log through their existing REST endpoints and
uses controller SSE for subsequent reports and health. Report, pulse, refresh,
and serial-log controls continue to call existing REST commands. Pin state is
shown only from the last valid report; disconnects freeze that state and mark it
stale rather than animating or predicting it.

### System

The system page loads system identity, hardware, storage, worker, and monitor
state from `GET /api/system`. Logs load only when requested. Restart, reinstall,
and upgrade retain their current REST actions and show the last confirmed action
result. The page does not claim completion while the service is unreachable.

### API test

The API-test page constructs controller choices and examples from REST discovery
instead of server-injected roles, payloads, hostname, or time format. Its request
buttons and SSE viewer keep using the public API. Copyable command examples remain
visible, but their host is derived in the browser from the active API origin.

## Data and ownership boundary

Browser code may format, filter, navigate, and retain unsaved form drafts. It may
not implement Plamp hardware, scheduling, configuration validation, persistence,
or camera behavior. Those capabilities belong to the shared `plamp` module and
are exposed by the REST/SSE adapter.

If a static page needs information that is not available through the public API,
the migration adds a generally useful REST read model. It does not add a page
bootstrap blob or return rendered HTML from an API endpoint.

## Failure behavior

Each page starts in a neutral loading state. Content becomes current only after a
valid REST response or SSE event. Request failures remain visible and name the
operation that failed. Previously valid observations may remain displayed only
when clearly marked stale; no page advances hardware state without a new report.

Navigation failure is independent of page-specific failure: a settings or
controller page remains usable when revision or controller-menu discovery fails,
with the affected menu portion marked unavailable.

## Migration and verification

The conversion proceeds as independently reversible slices:

1. Add the shared shell and move the existing dashboard navigation onto it.
2. Convert `/settings`.
3. Convert `/controllers/{controller}`.
4. Convert `/system`.
5. Convert `/api/test` and remove the unused Python page renderers.

Each slice preserves its URL and behavior tests, adds a contract proving the
served document contains no injected runtime state, and validates its JavaScript
syntax. After local focused and full-suite verification, deploy the slice to
Sprout and smoke-test its page, REST calls, and SSE where applicable. Tower is
updated only after the completed static site has passed on Sprout.

Exact-origin CORS and a configurable external API origin remain the next separate
feature. They enable a separately hosted client without changing this static
multi-page architecture.
