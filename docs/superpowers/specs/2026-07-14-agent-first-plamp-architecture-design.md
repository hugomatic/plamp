# Agent-First Plamp Architecture

## Goal

Agents should operate Plamp through a local library and CLI even when the web service is stopped. Remote agents normally use that CLI over SSH. REST, SSE, and web applications are adapters, not dependencies of the CLI.

## Process model

- `plamp`: shared Python library and direct CLI.
- `plamp_cli`: REST-backed compatibility CLI during migration.
- `plamp-web`: optional long-running REST/SSE service, report collector, and camera scheduler.
- Web apps: replaceable REST/SSE clients.
- `plampctl`: host installation, upgrades, service control, logs, and migrations.

With the service stopped, automatic reports, scheduled pictures, REST/SSE, and dependent web apps pause. Pico schedules and direct CLI hardware operations continue.

## Command launcher

The command named `plamp` is the `plamp` module's direct CLI. The repository-owned
`bin/plamp` launcher resolves its checkout and runs that checkout's virtual-environment
Python with `-m plamp`. It exposes neither virtual-environment activation nor uv to the
operator. `plampctl` creates and synchronizes the environment during installation and
upgrades. If the environment is missing, the launcher reports an installation error
with a `plampctl` recovery command; it does not silently choose another interpreter.

`plamp_cli` remains explicitly named REST compatibility code while migration is
incomplete. It must not own the `plamp` command or become a dependency of the direct
CLI.

## Shared mechanisms

The library owns behavior that must remain consistent across processes:

- USB discovery by stable serial number;
- filesystem locking and operation budgets;
- serial framing and Pico protocol validation;
- atomic configuration storage;
- schedule validation;
- camera capture;
- Pico provisioning and upgrades.

It exposes focused capabilities, not a universal action dispatcher. CLI, REST, collectors, and web apps may compose them differently.

## Hardware transactions

Each Pico or camera has a cross-process filesystem lock. A Pico transaction:

1. Acquires the lock.
2. Discovers the current tty path from the configured USB serial.
3. Opens serial and discards stale input.
4. Sends a command.
5. Buffers bytes through newline-delimited messages.
6. Validates and returns the expected response.
7. Closes serial and releases the lock.

Operation budgets bound lock waiting and controllable serial reads/writes. Synchronous OS/driver discovery, open, flush, and close calls cannot be forcibly preempted. Hardware timing belongs in component tests and operational evidence, not this architecture contract.

## Reports and background work

Target firmware produces full routine reports on demand after `r`. The host setting `report_poll_seconds` controls the optional collector; it is not a web-only or firmware preference. Explicit asynchronous alarm events may be added later.

The application service remains the one background process for REST, SSE, periodic report collection, and scheduled pictures. It does not permanently own hardware.

## Configuration and firmware

Keep desired host configuration separate from observed reports:

- Pico runtime: pins, schedules, output behavior.
- Host automation: report polling, camera schedules, retention, hardware identity.
- Presentation: web layout and filters.

Cross-process writes use a filesystem lock, validation, temporary file, and atomic replacement.

Separate three Pico operations:

- **Configure:** apply and persist schedules/settings without reflashing.
- **Upgrade:** replace Plamp application or MicroPython, reset, and verify.
- **Provision:** install MicroPython on a new/BOOTSEL Pico, upload Plamp, apply configuration, and verify.

The host retains enough desired configuration to rebuild a replacement Pico.

## Interfaces

The CLI is the primary agent interface: stable JSON, diagnostics on stderr, documented exit codes, help, validation, dry-run support, and explicit budgets.

REST handles bounded commands and reads. SSE carries reports, status, camera results, and progress. WebSocket and P2P remain out of scope until a concrete requirement exists.

The REST/SSE server imports and composes focused `plamp` capabilities. Web application
code reaches those capabilities only through REST/SSE; it does not import internal
hardware, configuration, scheduling, or camera behavior.

Initially the REST/SSE service may serve the web application's static HTML, JavaScript,
CSS, and other assets. This is only a deployment convenience. Once loaded, the browser
uses the same REST/SSE contract as a separately hosted client. The first conversion
target is the main dashboard, followed by settings, controller diagnostics, system
information, and API-test pages. A later React or other web service can therefore be
developed and deployed separately without changing `plamp` or the REST/SSE contract.

Cross-origin browser access is disabled unless exact allowed origins are present in
`PLAMP_DATA_DIR/host.json`. The `plamp` module owns origin validation, locking, and
atomic persistence. The direct CLI exposes `plamp host cors list|allow|remove`, while
`plampctl cors` composes those operations with a service restart and readiness check.
The server applies one policy to REST, preflight requests, errors, and SSE. Wildcard
origins are rejected; CORS is browser policy and is not presented as authentication.

## Migration

1. Extract locked Pico report transactions and direct CLI access.
2. Move firmware to demand-driven reports and service polling.
3. Confirm flashing through reconnect-until-valid-report transactions.
4. Add cross-process camera capture and direct CLI access.
5. Add atomic configuration writes and explicit desired/applied state.
6. Update runtime configuration without flashing.
7. Add provisioning, upgrades, and recovery.
8. Correct `bin/plamp` to launch the direct module CLI through the hidden environment.
9. Move remaining REST/SSE behavior onto the shared library.
10. Convert the main dashboard, then remaining pages, into static REST/SSE clients.
11. Add configurable exact-origin CORS for separately hosted web development.

Each slice must preserve tower operation and remain independently reversible.
