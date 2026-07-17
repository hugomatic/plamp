# Runtime Pico Configuration

## Goal

Ordinary schedule changes must not reflash or reset a Pico. A schedule save sends one complete controller state, and succeeds only after the Pico has persisted, applied, and reported that state.

The first schedule transaction against legacy or outdated firmware upgrades it automatically while preserving the currently committed schedule. Failure is visible and stops the transaction.

## Boundaries

- This slice replaces schedule-time flashing with runtime configuration.
- It does not provision MicroPython on a blank Pico.
- It does not add partial or per-channel firmware updates.
- It does not add request IDs, background firmware upgrades, or another database.
- The existing controller-wide REST operation and semantic host configuration remain authoritative for user intent.

## Firmware identity

Every full report includes:

```json
{
  "type": "report",
  "content": {
    "firmware": {
      "name": "pico_scheduler",
      "revision": "39f2304",
      "protocol": 2
    },
    "devices": []
  }
}
```

`protocol` defines command and report compatibility. `revision` is the latest Git commit that changed the Pico firmware sources, not an arbitrary web or documentation commit. This keeps the reported revision traceable without reflashing for unrelated host changes.

Health reports expose a mismatch. Read-only report polling never upgrades firmware. A controller-wide schedule transaction upgrades automatically when the protocol is missing or incompatible, or when the firmware revision differs from the host's expected firmware revision.

## Runtime protocol

Commands remain newline-delimited. Reports and errors remain one complete JSON document per line.

The host sends the complete compiled state:

```json
{
  "type": "configure",
  "content": {
    "devices": [
      {
        "id": "lights",
        "type": "gpio",
        "pin": 2,
        "current_t": 3600,
        "reschedule": 1,
        "pattern": [
          {"val": 1, "dur": 61200},
          {"val": 0, "dur": 25200}
        ]
      }
    ]
  }
}
```

The Pico validates the entire document before changing files, outputs, or its in-memory device list. It rejects unknown fields, duplicate IDs or pins, unsupported output types, invalid values, empty patterns, and invalid durations with one structured error:

```json
{"type":"error","content":{"command":"configure","message":"duplicate pin: 2"}}
```

On success the Pico:

1. Normalizes the complete state in memory.
2. Writes and syncs the inactive one of two generation-numbered state files.
3. Replaces the active device list and applies outputs.
4. Emits one full report.

On boot the Pico validates both state files and loads the valid file with the highest generation. A torn write is ignored, leaving the previous generation available. This avoids depending on filesystem-specific replacement semantics while remaining two ordinary JSON files, not a database.

The configured state is loaded on boot, including the phase stored by the last configuration transaction. Persistence restores the program, not knowledge of elapsed wall time: after power loss, a daily schedule may be out of phase until a trusted clock reconfigures it. Battery-backed RTC or clock synchronization is a separate feature.

## Automatic migration

The host performs migration only inside a mutating controller-wide schedule transaction:

1. Request a fresh report.
2. If firmware is current, continue to runtime configuration.
3. Otherwise compile the currently committed schedule—not the proposed edit.
4. Seed both state slots with the current state, copy the generic scheduler application, reset once, rediscover USB, and require a valid report containing the expected firmware identity and current devices.
5. If any upgrade step fails, return an error and leave host configuration unchanged.
6. Send the proposed state through the runtime protocol.

Copying current state before the new application means the old application continues running until reset. A partially completed upgrade is not accepted as success; a later transaction may retry it.

Legacy firmware is replaced rather than maintained through a compatibility command path.

## Host transaction

The existing controller-wide schedule endpoint remains the public operation:

1. Validate the complete proposed semantic controller configuration.
2. Acquire the controller and configuration locks.
3. Obtain a fresh report and perform automatic migration if required.
4. Compile the proposed complete runtime state.
5. Send one `configure` document.
6. Require a full report and compare each device's ID, type, pin, reschedule flag, and pattern with the proposal. Runtime elapsed values are not compared.
7. Only after the comparison succeeds, atomically commit host configuration and applied state.

If the configure response is malformed or absent, the host sends `r` within the same bounded transaction and compares that fresh report. It does not blindly resend `configure`. If state still cannot be proven, the operation fails and retains the previous host files.

This is not a distributed database transaction. A host process or power failure in the narrow interval after Pico persistence and before host commit may leave the Pico ahead of the host. The next report exposes the difference; automatic crash reconciliation is out of scope until evidence justifies a durable transaction journal.

## Shared library and adapters

The shared `plamp` library owns firmware identity parsing, full-state protocol validation, runtime configuration, upgrade, and report comparison. Both the direct CLI and REST service call those capabilities. The web page remains an REST/SSE client and contains no firmware decisions.

The direct CLI exposes explicit configure and upgrade operations with JSON on stdout, diagnostics on stderr, bounded timeouts, and nonzero exit status on failure. `plampctl` remains responsible for host software installation and service lifecycle, not Pico schedule changes.

## Diagnostics and errors

- Preserve every raw serial line involved in a failed exchange.
- Identify the failed stage: report, compatibility, upgrade copy, reset, rediscovery, configure, verification, or host commit.
- Never report `OK` merely because the serial port opened or a write completed.
- Never commit proposed host configuration after an unverified Pico result.
- Successful health polling stays quiet at INFO; migrations and configuration transactions are logged once with timing and firmware revisions.

## Verification

Unit and fake-serial tests prove validation is all-or-nothing, persistence precedes apply, full reports include identity, lost configure replies are resolved with `r`, and host files commit only after comparison.

Generator tests prove firmware is schedule-independent and revision selection ignores unrelated commits. Existing pulse overlays must continue to restore the newly configured base schedule.

Hardware verification on a non-production controller proves:

1. The first transaction upgrades legacy firmware once and preserves its active schedule.
2. USB disappears and returns only for that upgrade.
3. Later schedule changes do not reset USB and complete through one configure/report exchange.
4. Power cycling loads the persisted schedule and stored phase without claiming wall-clock correctness.
5. Invalid configuration leaves the prior schedule active.
6. Disconnects and malformed lines produce visible errors without changing host files.
