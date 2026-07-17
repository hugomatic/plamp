# Plampctl operations

`plampctl` provides memorable, task-oriented local operations while showing the standard Unix commands it uses.

- `status`: show `plamp-web` service state and HTTP readiness; fail if either is unhealthy.
- `logs [--lines N] [--follow]`: show 100 lines by default or follow the journal.
- `restart`: restart immediately, poll HTTP immediately, and return at first success; fail after 15 seconds.
- `upgrade` and `reinstall`: finish with the same readiness check.
- Print each meaningful underlying command with a `+ ` prefix before execution.
- Help text names the equivalent `systemctl`, `journalctl`, and `curl` commands.
- Keep operations local. Existing SSH and `remote-install` remain the remote mechanisms.
