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
   - `ripgrep`, `gh`, `shellcheck`, `jq`, `usbutils`, `lsof`, `strace`, and
     `openscad` make source, JSON, GitHub, Bash, USB, process, system-call, and
     CAD work readily available.

Both groups install by default. There is no opt-in flag and no machine role.
Optional nginx installation remains controlled by `--public`.

## Heavy CAD Tool

OpenSCAD installs on every Plamp Pi so any human or cloud agent can edit and
render the repository's CAD without machine roles. Documentation must state
that CGAL rendering is CPU- and memory-heavy on a Raspberry Pi. Headless STL
generation is supported; graphical image preview may require a display server.

## Documentation

Add `docs/host-tools.md` with tables for runtime dependencies and agentic tools,
including an explicit heavy-tool note for OpenSCAD. Each row names the Debian
package, command, and reason it exists. Agentic-tool examples must be read-only
or preserve a backup; the `sed` examples demonstrate previewing before
`sed -i.bak`.

Link the tool contract from the README installation section. Installer tests
must enforce both headings, both exact package groups, and default installation
of agentic tools including OpenSCAD.
