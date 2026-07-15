# Agent-First Plamp Architecture

## Intent

Plamp should be fully operable by agents through a local CLI, including when the web service is stopped. Remote agents should normally use that CLI over SSH. REST, SSE, and web applications remain useful adapters, but they must not define Plamp behavior or become dependencies of the CLI.

The design follows the useful part of [Ports and Adapters](https://alistair.cockburn.us/hexagonal-architecture/): command-line, HTTP, web, and test clients can drive the same capabilities, while hardware and storage details remain replaceable. Plamp will not introduce an interface for every action or funnel all workflows through one dispatcher. It will share mechanisms and data models; each adapter may orchestrate those capabilities for its own use.

## Process Model

Plamp has one optional long-running application service and no hardware broker:

- The CLI runs as a short-lived process and calls the shared library directly.
- The application service calls the same library and provides REST, SSE, periodic Pico report collection, and scheduled camera captures.
- Browser applications use REST for commands and reads, and SSE for unsolicited updates. Multiple web applications may coexist or be replaced independently.
- `plampctl` continues to install, upgrade, restart, and inspect the host service. It is not a plant-control interface.

When the application service is stopped, automatic report collection, scheduled photos, REST, SSE, and dependent web apps stop. Pico schedules, direct CLI reports, configuration, firmware operations, diagnostics, and direct CLI camera captures continue to work.

## Python Package Boundary

A `plamp` package contains the reusable library and its CLI entry point:

```text
plamp/
    __init__.py
    __main__.py
    cli.py
    config.py
    locks.py
    pico_discovery.py
    pico_transport.py
    pico_protocol.py
    pico_firmware.py
    schedules.py
    camera.py
```

`python -m plamp` invokes `plamp.__main__`, which only calls the CLI entry point. Importing `plamp` does not parse arguments, initialize cameras, open serial devices, or start workers.

The REST/SSE service imports the library. Browser apps call REST/SSE rather than importing the library. During migration, the existing `python -m plamp_cli` interface remains as a compatibility adapter; callers are not forced to migrate in the first slice.

## Shared Mechanisms, Independent Workflows

The shared library owns mechanisms that must behave consistently across processes:

- stable USB identity discovery;
- filesystem locking and deadlines;
- serial framing and JSON validation;
- Pico command encoding and report decoding;
- atomic configuration storage;
- schedule validation and compilation;
- camera acquisition and capture;
- MicroPython provisioning and Plamp application upgrades.

The library exposes focused operations rather than a universal action dispatcher. The CLI, REST API, collector, and web apps may combine operations differently. For example, a CLI report command prints one fresh report and exits, while the collector stores a report and publishes it over SSE.

## Pico Transactions

Every Pico transaction uses the configured USB serial number as identity. `/dev/ttyACM*` paths are rediscovered for every transaction and are never authoritative.

The transaction sequence is:

1. Acquire an exclusive per-Pico filesystem lock.
2. Discover the current device path for the configured USB serial number.
3. Open the serial connection and discard stale input.
4. Send a command.
5. Accumulate bytes through a complete newline-terminated message.
6. Validate and return the response.
7. Close serial and release the lock.

The lock is held through the complete request and response. Other CLI and service processes wait for it within their declared deadline. The operating system releases the lock when a process exits. Python exposes the underlying advisory lock through [`fcntl.flock`](https://docs.python.org/3/library/fcntl.html).

Routine reports are demand-driven. The Pico sends a full report only in response to `r`; it does not emit periodic full reports. The host setting `report_poll_seconds` controls how often the optional collector requests reports. This is host automation configuration, not firmware behavior or a web-only preference.

The Sprout measurement on 2026-07-14 established the performance target: ten cold open/send-`r`/report/close transactions took 8.2–8.6 ms each. Implementations should not add boot waits or multi-second reconnect backoff to an ordinary transaction.

## Reset and Reconnection

Firmware operations are transactions that may span multiple USB connections:

1. Begin the firmware operation while holding the Pico lock.
2. Copy or install firmware and reset the Pico.
3. Whenever the configured Pico connection appears, open it and send `r`.
4. If it disconnects before a valid report, immediately resume discovery with only a small scheduling yield.
5. Complete only after receiving a valid post-reset report, or fail at the overall deadline.

The implementation does not assume one connection, two connections, a fixed boot duration, or a readiness banner. The Sprout measurement encountered two connections and received a valid report 552 ms after reset completion and 920 ms after firmware copy began.

## Runtime Configuration and Firmware

Schedule changes must not reflash application code. Three operations remain distinct:

- **Configure:** validate, transmit, persist, and apply schedules and runtime settings without rebooting; return the confirmed resulting report.
- **Upgrade:** update the Plamp application or MicroPython version, reset, rediscover, and verify protocol compatibility and a valid report.
- **Provision:** install the approved MicroPython UF2 on a new or recovery-mode Pico, upload the Plamp application, apply host configuration, and verify the report. Physical BOOTSEL entry may still be required.

MicroPython's documented [`mpremote`](https://docs.micropython.org/en/latest/reference/mpremote.html) file-copy and reset facilities remain valid implementation tools. They are hidden behind library operations rather than embedded in HTTP handlers.

The host retains enough desired configuration to rebuild a replacement Pico. Firmware reports describe observed runtime state; they do not reconstruct host-only intent such as editor units or display preferences.

## Configuration Ownership

Configuration is divided by purpose:

- Pico runtime configuration: channels, pins, schedules, and output behavior.
- Host automation configuration: report polling, camera schedules, retention, and controller-to-USB identity mapping.
- Web presentation preferences: layout, filters, and display choices.

All processes use the same configuration store. Cross-process writes use a filesystem lock, validation, a temporary file, and atomic replacement. The existing in-process `threading.Lock` is not sufficient once CLI and service processes both write configuration.

Desired configuration and observed state remain separate. A failed configure or firmware transaction must not be presented as successfully applied merely because desired configuration was saved.

## Camera Transactions

Camera capture is available directly from the CLI and through the service. Every capture:

1. Acquires a per-camera filesystem lock.
2. Initializes and captures from that camera.
3. Closes the camera.
4. Releases the lock.

Captures for the same camera serialize across CLI and service processes. Different cameras may operate concurrently. The service may retain scheduling and an internal queue, but neither is the authority for cross-process exclusion. Importing the library never starts the camera worker.

## API and Web Applications

REST represents bounded commands and reads. SSE continues to publish reports, status changes, camera results, and operation progress. WebSocket and peer-to-peer transports are out of scope until a concrete bidirectional or network-topology requirement exists.

The current web interface becomes one fallback client. New web applications may use different frameworks or presentation models against the same REST/SSE contract. No browser application receives direct filesystem, serial, camera, or firmware responsibilities.

## CLI Contract

The CLI is the primary agent interface. It must provide:

- stable machine-readable JSON output;
- useful human-readable output where requested;
- documented exit codes and structured errors;
- complete `--help` examples;
- explicit deadlines for waiting on locked or disconnected hardware;
- validation and dry-run support for configuration changes;
- idempotent behavior where the operation permits it.

SSH is the initial remote CLI transport. P2P may later become another adapter; it does not affect the library or hardware protocol now.

## Testing and Evidence

The shared mechanisms require tests independent of physical hardware:

- fake Pico transport for complete, partial, malformed, delayed, and disconnected responses;
- one-connection and transient-then-stable firmware reconnect cases;
- lock contention, timeout, and process-exit release;
- USB path changes for a stable serial number;
- atomic configuration writes and failed-apply separation;
- same-camera serialization and different-camera concurrency;
- CLI and REST adapter contract tests against the same library results.

Hardware verification on Sprout remains a separate acceptance layer. Timing logs must distinguish firmware work, reset completion, device discovery, serial open, command transmission, and valid response.

## Migration Order

1. Extract locked Pico discovery, transport, protocol, and report operations without changing the current external interfaces.
2. Make `r` the only source of full routine reports and move report polling into host automation configuration.
3. Move Pico apply confirmation onto the reconnect-until-valid-report transaction.
4. Extract camera capture behind a cross-process lock.
5. Move CLI commands from REST dependency to direct library operations while retaining an explicit remote REST mode only where still useful.
6. Move REST/SSE handlers and background collectors onto the library.
7. Separate runtime configuration updates from firmware upgrades.
8. Add explicit provisioning and recovery workflows.
9. Reduce the current website to a REST/SSE fallback client and permit additional web apps.

Each stage must leave the existing tower workflow usable and must be deployable and reversible independently.

## Non-Goals

- No serial broker, leader election, Swarm coordination, or permanently owned serial port.
- No requirement that every caller use REST or the CLI executable.
- No single universal action dispatcher.
- No WebSocket or P2P rewrite in this work.
- No requirement that the application service be running for direct hardware operation.
