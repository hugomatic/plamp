# Suggestions

## Scheduler follow-ups (2026-09-01)

Completed in `9fdf661`:

- Re-anchor daily clock-window schedules to tower's current local time whenever
  they are applied. Preserve live phase only for elapsed-time cycle schedules.
- In operational views, use the Pico report as the source of truth. Show
  `enabled`, `current_value`, and the active phase; do not present saved editor
  settings as current behavior.
- Keep saved schedules as defaults only in the rescheduling editor. A disabled
  channel must read `DISABLED` / `OFF` and must not display an active cycle.
- Do not hide operational state merely because a channel has
  `visibility: hidden` in its saved editor settings.

Still wanted:

- Add a clear **Stop** operation distinct from **Pulse**. Decide whether Stop
  persistently disables the channel (preferred for safety) or installs a
  temporary force-OFF override, then expose and verify it through firmware,
  REST, CLI, and web UI.
- Add a `plamp-cli` command for applying/rescheduling a controller so routine
  workflows do not require raw `curl` against
  `POST /api/controllers/{controller}/apply`.
- Fix the local `uv run plamp ...` packaging/import failure; currently
  `uv run python -m plamp_cli ...` is the working REST CLI invocation.
- Investigate why the first service restart on 2026-09-01 loaded the four 12 V
  channels as enabled after they had previously been saved disabled. Reapplying
  that loaded state briefly turned pins 18–21 on. The channels were immediately
  disabled again and verified from a fresh Pico report. Add a restart
  persistence regression test before treating this as resolved.
- Improve schedule-apply responses so their returned `current_value` cannot be
  mistaken for a fresh post-apply hardware report. The caller should receive or
  explicitly request verified post-apply state.

- Define a reusable project-tooling convention for future repositories:
  `<project>` for human-facing workflows, optional domain commands such as
  `<project> cad`, and `<project>ctl` for packaging, deployment, services,
  upgrades, logs, and migrations. Agent discovery should ask which of these
  interfaces exists and is authoritative before using lower-level commands.
  A small future CAD project can be the first independent trial.
