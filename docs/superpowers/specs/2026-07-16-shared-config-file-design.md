# Shared Configuration File

## Goal

Let the direct CLI and web service read and write the same human-readable
`config.json` through small shared functions in `plamp`. Keep the file usable by
people and scripts without introducing a database, ownership service, or
coordination protocol.

## File contract

`plamp.config` loads JSON, validates the configuration, and saves a complete
configuration. Saving validates first, writes a temporary sibling file, flushes
it, and atomically replaces `config.json`. The temporary file exists only for
the duration of the save.

There is no cross-process lock. Concurrent or manual edits are not merged; the
last completed replacement wins. Any process with filesystem permission may
read or write the file.

The web service must use the shared load and save functions instead of keeping
its own JSON persistence implementation. Interfaces may still compose config
operations differently; this is a shared file boundary, not a universal action
dispatcher.

## CLI

The direct CLI exposes whole-file operations:

- `plamp config get` prints the validated configuration as JSON.
- `plamp config write FILE` validates and replaces the configured JSON file.
  `FILE` may be `-` for standard input.

Validation failures go to standard error, leave the existing file unchanged,
and return the CLI validation-error exit code. Successful writes print the
saved configuration as JSON. Domain commands for editing one schedule or
camera are separate future operations; they may use the same library functions
without routing through this whole-file CLI command.

## State model

Persist only desired configuration. Do not create a saved “applied state.” A
fresh Pico report is the evidence for what firmware is actually running.
Presentation preferences that the Pico does not report remain desired host
configuration.

## Verification

Tests cover valid reads and writes, malformed JSON, schema rejection, unchanged
files after failed writes, atomic replacement, stdin input, JSON output, and web
use of the shared persistence functions. No concurrency or conflict-resolution
behavior is promised or tested.
