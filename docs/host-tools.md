# Host Tools

The Plamp installer labels and installs two system-package groups. Runtime
dependencies make Plamp operate. Agentic-efficiency tools make the same host
ready for a human or cloud agent to inspect, diagnose, and modify.

## Runtime dependencies

| Debian package | Main commands or service | Why Plamp installs it |
| --- | --- | --- |
| `bash` | `bash` | Runs `plampctl`, bootstrap, deployment, and CAD scripts. |
| `coreutils` | `ls`, `cp`, `mv`, `realpath`, `mktemp` | Provides fundamental filesystem and shell operations. |
| `findutils` | `find`, `xargs` | Finds files and safely batches filesystem operations. |
| `grep` | `grep` | Supports portable text matching inside repository scripts. |
| `sed` | `sed` | Selects and transforms text in lifecycle scripts. |
| `tar` | `tar` | Extracts archived source trees during reproducible CAD generation. |
| `cron` | `crontab`, `cron` | Runs the optional Plamp heartbeat schedule. |
| `git` | `git` | Clones, upgrades, identifies, and archives Plamp source. |
| `curl` | `curl` | Downloads bootstrap tools and performs HTTP health checks. |
| `ca-certificates` | system trust store | Verifies HTTPS downloads and Git remotes. |
| `ffmpeg` | `ffmpeg` | Supports camera and video processing. |
| `python3-picamera2` | Picamera2 Python module | Captures Raspberry Pi camera images. |
| `avahi-daemon` | `avahi-daemon` | Advertises the host over mDNS. |
| `avahi-utils` | `avahi-resolve`, `avahi-browse` | Verifies and diagnoses mDNS names. |
| `libnss-mdns` | NSS mDNS integration | Resolves names such as `sprout.local`. |

## Tools for agentic efficiency

| Debian package | Command | What it helps a human or agent do |
| --- | --- | --- |
| `ripgrep` | `rg` | Search source and logs quickly while respecting ignore files. |
| `gh` | `gh` | Inspect GitHub authentication, pull requests, and checks. |
| `shellcheck` | `shellcheck` | Find errors and portability problems in Bash scripts. |
| `jq` | `jq` | Select and format JSON when a Plamp CLI view is insufficient. |
| `usbutils` | `lsusb` | Observe devices at the USB layer independently of Pico reports. |
| `lsof` | `lsof` | Identify a process holding a serial device or network socket. |
| `strace` | `strace` | Trace system calls when normal diagnostics cannot explain a failure. |
| `openscad` | `openscad` | Render the repository's parametric CAD and printable STL files. |

## Read first, then change

Find files and text:

```bash
rg --files
rg 'revision_string|xt60' things/plamp8
```

Inspect selected lines without changing a file:

```bash
sed -n '40,80p' deploy/bootstrap/install-plamp.sh
sed -n '/Installing Plamp runtime dependencies/,+12p' deploy/bootstrap/install-plamp.sh
```

Preview a replacement on standard output, then make it with a recoverable
backup only after the preview is correct:

```bash
sed 's/old text/new text/g' example.txt
sed -i.bak 's/old text/new text/g' example.txt
```

Inspect JSON, GitHub, and Bash:

```bash
plamp --pretty system status | jq .
gh auth status
gh pr list
shellcheck plampctl deploy/bootstrap/install-plamp.sh
```

Inspect USB and ownership evidence:

```bash
lsusb
lsof /dev/ttyACM0
```

Use `strace` only after ordinary logs and diagnostics are insufficient because
tracing adds noise and can affect timing:

```bash
strace -f -e trace=file ./plampctl status
```

## OpenSCAD on a Pi

Use the local Plamp CAD commands so validation, revision engraving, source
selection, manifests, and logs all follow the same reproducible path:

```bash
plamp cad validate plamp8
plamp cad plan plamp8 --view sub_panel
plamp cad generate plamp8 --view sub_panel --output prints/plamp8_sub_panel
```

The scripts beside existing parts are compatibility shortcuts. They delegate
to `plamp cad generate`, so older positional output and commit invocations still
work:

```bash
things/plamp8/generate.bash --view sub_panel prints/plamp8_sub_panel
things/plamp8/generate.bash --box prints/plamp8_fuse_box
things/plamp8/generate.bash --preview --view sub_panel prints/plamp8_preview HEAD
```

Use `--revision LABEL` when intentionally rendering uncommitted part changes.
The legacy `--preview` shortcut disables rendered text and sets `render_fn=24`;
repeatable `--define`/`-D` arguments can override those defaults.

OpenSCAD CGAL rendering is CPU- and memory-heavy on a Raspberry Pi. Headless
STL generation works, but complex parts can be slow. Graphical image previews
may require an X display or other display server even when STL export works.
