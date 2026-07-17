# Shared Configuration File

## Goal

Let the direct CLI and web service read and write the same human-readable
`config.json` through small shared functions in `plamp`. Keep the file usable by
people and scripts without introducing a database, ownership service, or
coordination protocol.

## Installation and instance paths

Plamp currently runs from a Git checkout. `plampctl` locates that checkout from
its own script path and uses Git there for upgrades. Runtime code does not
search Git or walk parent directories to find configuration.

The running Plamp package determines the default code root. `PLAMP_ROOT` may
state that root explicitly; relative values are resolved before use. A data
directory defines one Plamp instance and contains `config.json`, logs, timers,
grow data, and other persistent state. `PLAMP_DATA_DIR` selects it and defaults
to `$PLAMP_ROOT/data`.

Configuration is always `$PLAMP_DATA_DIR/config.json`. There is no
`PLAMP_CONFIG`, `--config`, or `--data-dir` option and no other path precedence.
The web system page and `plamp context` show the effective root, data directory,
revision, and the environment-variable names.

An optional `setup.sh [DATA_DIR]` selects a checkout for an interactive shell.
It removes exact PATH entries added by the previous Plamp activation, exports
`PLAMP_ROOT` and the resolved `PLAMP_DATA_DIR`, prepends the checkout and its
`.venv/bin`, runs `hash -r`, and prints the selected context. It does not run
Git or `uv`, change directory, start services, or modify `PYTHONPATH`.

The systemd service sets both variables explicitly. A missing
`PLAMP_DATA_DIR` is therefore a convenient interactive default, not hidden
production configuration.

Hardware locks are machine-wide runtime coordination, not instance data. A
different data directory must not create an independent default lock namespace:
two instances that name the same Pico or camera must still serialize access.
The default lock directory is the per-user system temporary path
`<temp>/plamp-<uid>/locks`, shared by all checkouts and instances for that user.
Multiple simultaneous web-service instances would also require distinct
service names and ports and are not part of this work.

## File contract

`plamp.config` loads JSON, validates the configuration, and saves a complete
configuration. Saving validates first, writes a temporary sibling file, flushes
it, and atomically replaces `config.json`. The temporary file exists only for
the duration of the save.

There is no cross-process lock for configuration writes. Concurrent or manual
edits are not merged; the last completed replacement wins. This is independent
of the hardware locks described above. Any process with filesystem permission
may read or write the file.

The web service must use the shared load and save functions instead of keeping
its own JSON persistence implementation. Interfaces may still compose config
operations differently; this is a shared file boundary, not a universal action
dispatcher.

## CLI

The direct CLI exposes whole-file operations:

- `plamp config get` prints the validated configuration as JSON.
- `plamp config write FILE` validates and replaces the configured JSON file.
  `FILE` may be `-` for standard input.

Both commands use `$PLAMP_DATA_DIR/config.json`.

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
