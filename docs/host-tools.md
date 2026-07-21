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
selection, manifests, and logs all follow the same reproducible path. A part
name such as `plamp8` resolves to `things/plamp8/plamp8.scad`; a repository
relative or absolute SCAD path also works.

Start with this Plate 1 workflow:

```bash
plamp cad views plamp8
plamp cad validate plamp8
plamp cad plan plamp8 --preset fuse-box
plamp cad generate plamp8 --preset fuse-box
plamp cad runs plamp8
plamp cad show RUN_ID
```

Use `plan` before `generate`. `plan` never invokes OpenSCAD: it expands the
recipe, shows the render jobs and effective variables, and uses compatible
archived runs for time and size estimates. The same selection options work for
both commands. `--preset NAME` chooses one named recipe; repeatable
`--view NAME` chooses individual views. The synthetic selectors
`--preset all-views` and `--preset all-presets` expand every declared view or
every named preset respectively, but are not names that may be embedded in a
SCAD file. With no selection, Plamp uses `default_preset` when present and
otherwise falls back to one render using the SCAD document's default view.

### Embedded generation metadata

Generation recipes live with the model inside a `/* generate.json ... */`
comment. The JSON object may contain:

- `global_variables`: typed OpenSCAD values applied to every job.
- `views`: metadata keyed by names from the Customizer declaration
  `view = "..."; // [view_a, view_b]`; each entry may have `description` and
  `variables`.
- `presets`: named recipes with `description`, ordered `items` using
  `view:NAME` or `preset:NAME`, plus optional `variables` and per-view
  `view_variables`.
- `default_preset`: the named recipe selected when the command has no explicit
  preset or views.

Metadata is optional for older parts. Plamp still reads their Customizer view
declaration and can render the implicit default; `validate` reports malformed
JSON, unknown references, reserved selector names, and preset cycles before a
render begins. Command-line `--define NAME=EXPR` and
`--view-define VIEW:NAME=EXPR` overrides are repeatable; use them only for
intentional OpenSCAD expressions because they are archived verbatim.

Nested variables use one exact, later-wins precedence order: SCAD defaults →
global → view → outer-to-inner preset variables → outer-to-inner matching
preset-view variables → CLI global → CLI per-view.

### Run archives and diagnostics

By default each generation is stored at
`$PLAMP_DATA_DIR/cad/prints/<part>/<RUN_ID>/`. This instance-data directory
contains `manifest.json`, a generated `readme.md`, the archived `source/`, STL
files under `artifacts/`, and complete OpenSCAD output under `logs/`. The
versioned manifest records source identity, the metadata snapshot, selection,
preset expansion, effective typed and raw variables, exact OpenSCAD commands,
job state, timings, artifact sizes, captured echoes, typed `PLAMP` messages,
warnings, errors, and geometry statistics. Unknown OpenSCAD output remains in
the per-artifact log. Use `plamp cad show RUN_ID` for the manifest and
`plamp cad log RUN_ID ARTIFACT_ID` for one archived log.

OpenSCAD CGAL rendering is CPU- and memory-heavy on a Raspberry Pi, and a
multi-job generation can take minutes. Headless STL generation works, but
graphical image previews may require an X display or another display server.
Run archives are local instance data; do not commit them as manufacturing
source.

### Legacy wrappers

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
