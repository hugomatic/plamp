# Host Tools

The Plamp installer labels and installs two system-package groups. Runtime
dependencies make Plamp operate. Agentic-efficiency tools make the same host
ready for a human or cloud agent to inspect, diagnose, and modify.

## Runtime dependencies

| Debian package | Main commands or service | Why Plamp installs it |
| --- | --- | --- |
| `bash` | `bash` | Runs `plampctl`, bootstrap, deployment, and the Plamp checkout launcher. |
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

Use the local Plamp CAD commands so source selection, revision engraving,
manifests, and logs follow one reproducible path. For the usual case, generate
directly with no arguments. If exactly one system is available, Plamp selects
that system and its default product:

```bash
plamp cad generate
```

### Navigate systems, models, sets, and products

A **system** is a catalog that can span several OpenSCAD **models**. Each model
declares renderable **sets** in its adjacent `.cad.json` sidecar. A system
defines ordered **products**, which may combine sets from multiple models or
nest other products. Every navigation listing includes descriptions:

```bash
plamp cad systems
plamp cad models --system plamp
plamp cad sets plamp8 --system plamp
plamp cad products --system plamp
plamp cad templates
```

Several `*.system.cad.json` files may live in the same `cad/` directory. In an
interactive terminal Plamp offers a choice. In noninteractive or JSON mode,
ambiguity is an error and the command names the available systems; select one
with `--system NAME_OR_PATH`.

### Generate products or model sets

Choose an entire product, one or more ordered sets from one model, or every
named set in that model:

```bash
plamp cad generate --system plamp --product fuse-box
plamp cad generate --system plamp plamp8 --set top_panel
plamp cad generate --system plamp plamp8 --set top_panel --set sub_panel
plamp cad generate --system plamp plamp8 --all-sets
```

The model's empty set is the direct model output. Request it by naming the
model without `--set`; `--all-sets` deliberately expands named sets only.
`--define NAME=EXPR` applies a raw OpenSCAD expression globally and
`--set-define SET:NAME=VALUE` targets one selected set. Later assignments win
in this order: SCAD defaults → model → set → deepest product outward →
product item → parent product → CLI global → CLI per-set.

Generate directly for normal work. `plamp cad plan` is an optional advanced
command that expands the exact same selection and identities without invoking
OpenSCAD. It is useful for inspecting a large product before committing Pi CPU
time, but it is not a prerequisite for `generate`.

### Create a model from a template

List the human-readable templates, then select one explicitly. If an
interactive `new` command omits `--template`, Plamp prompts for the choice:

```bash
plamp cad templates
plamp cad new pump_bracket --system plamp --template flat_plate
plamp cad sets pump_bracket --system plamp
plamp cad generate --system plamp pump_bracket
```

The scaffold creates a clean `.scad` file plus an adjacent `.cad.json` model
sidecar, and registers the model in the selected system manifest.

### Run archives and diagnostics

By default each generation is stored at
`$PLAMP_DATA_DIR/cad/prints/<model>/<RUN_ID>/`. This instance-data directory
contains `manifest.json`, a generated `readme.md`, the archived `source/`, STL
files under `artifacts/`, and complete OpenSCAD output under `logs/`. The
run ID is local-time and human-readable; for example:

```text
2026-jul23-plamp8-top_panel-22h:19m-47e7d26
```

Before starting OpenSCAD, managed generation checks whether the same source
and effective selection have already been rendered that local day. An
interactive command shows the existing path and asks whether to regenerate.
For automation, request the same safe replacement explicitly:

```bash
plamp cad generate --system plamp plamp8 --set top_panel --regenerate
```

The replacement is rendered separately and published only after it succeeds;
a failed regeneration leaves the existing run intact. Explicit `--output`
bypasses managed duplicate detection and keeps its exact-directory behavior.

Inspect archives with:

```bash
plamp cad runs plamp8
plamp cad show RUN_ID
plamp cad log RUN_ID ARTIFACT_ID
```

Each versioned manifest records system, model, set, and source identities,
product membership, effective typed and raw variables, exact OpenSCAD
commands, job state, timings, artifact sizes, captured echoes, typed `PLAMP`
messages, warnings, errors, and geometry statistics. Unknown OpenSCAD output
remains in the per-artifact log. Use `plamp cad show RUN_ID` for the manifest
and `plamp cad log RUN_ID ARTIFACT_ID` for one archived log.

OpenSCAD CGAL rendering is CPU- and memory-heavy on a Raspberry Pi, and a
multi-job generation can take minutes. Headless STL generation works, but
graphical image previews may require an X display or another display server.
Run archives are local instance data; do not commit them as manufacturing
source.

Use `--revision LABEL` when intentionally rendering uncommitted part changes.
`--preview` disables rendered text and sets `render_fn=24`; repeatable
`--define`/`-D` arguments can override those defaults.
