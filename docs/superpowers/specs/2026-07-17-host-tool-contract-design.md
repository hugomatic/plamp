# Plamp Host Tool Contract

## Goal

Every `plampctl reinstall` or bootstrap installation produces a Pi that can run
Plamp and can be efficiently inspected by a human or cloud agent. The installer
must distinguish operational dependencies from convenience tools honestly.

## Installer Groups

The installer performs one package-index update, then prints and installs two
explicit groups:

1. `Installing Plamp runtime dependencies`
   - `bash`, `coreutils`, `findutils`, `grep`, `sed`, `tar`, and `cron` support
     the repository's shell and lifecycle scripts.
   - `git`, `curl`, `ca-certificates`, `ffmpeg`, `python3-picamera2`,
     `avahi-daemon`, `avahi-utils`, and `libnss-mdns` support installation,
     cameras, and network discovery.
2. `Installing tools for agentic efficiency`
   - `ripgrep`, `gh`, `shellcheck`, `jq`, `usbutils`, `lsof`, and `strace` make
     source, JSON, GitHub, Bash, USB, process, and system-call diagnosis readily
     available.

Both groups install by default. There is no opt-in flag and no machine role.
Optional nginx installation remains controlled by `--public`.

## Heavy Tools

OpenSCAD is not installed by the Plamp bootstrap. It remains supported and is
documented as an optional CAD-host tool because CGAL rendering is expensive on
a Raspberry Pi. Tower may retain OpenSCAD; controller-only Pis do not need it.

## Documentation

Add `docs/host-tools.md` with three tables: runtime dependencies, agentic tools,
and optional heavy tools. Each row names the Debian package, command, and reason
it exists. Agentic-tool examples must be read-only or preserve a backup; the
`sed` examples demonstrate previewing before `sed -i.bak`.

Link the tool contract from the README installation section. Installer tests
must enforce both headings, both exact package groups, default installation of
agentic tools, and exclusion of OpenSCAD.
