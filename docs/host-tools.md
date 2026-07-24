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

A **system** is a catalog that can span several OpenSCAD **models**. Each
model's SCAD `set` declaration is the authoritative ordered set list; its
adjacent `.cad.json` sidecar describes those sets. A system defines ordered
**products**, which may combine sets from multiple models or nest other
products. Every navigation listing includes descriptions:

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

### Manufacturing profiles and advice

List the system's versioned profiles and opt into one by short or qualified
name. The committed `system:draft` profile changes OpenSCAD geometry quality
only; it does not assume a printer, material, layer height, or calibration:

```bash
plamp cad profiles --system plamp
plamp cad generate --system plamp --product fit-and-function --profile system:draft
```

Workstation-specific profiles belong in
`$PLAMP_DATA_DIR/cad/profiles/<name>.json`, outside the repository. For
example, start with a local profile whose values name your own slicer setup:

```json
{
  "schema": "plamp-cad-profile/1",
  "name": "my-printer",
  "kind": "printer",
  "cad": {},
  "slicing": {
    "notes": ["Apply the tested settings from my workstation slicer profile."]
  },
  "machine": {
    "slicer_profile": "replace-with-my-local-profile-name"
  }
}
```

Defaults are also instance-local. Put them in
`$PLAMP_DATA_DIR/cad/preferences.json`; they apply before profiles named on
the command line:

```json
{
  "schema": "plamp-cad-preferences/1",
  "default_system": "plamp",
  "default_profiles": {"plamp": ["local:my-printer"]}
}
```

Use `--no-default-profiles` when a run must ignore those configured defaults.
Every generated run's `readme.md` translates resolved slicing metadata into
human-readable recommendations. Advice is deliberately non-executable: check
it against the selected printer, material, and slicer before printing.

Generate directly for normal work. `plamp cad plan` is an optional advanced
command that expands the exact same selection and identities without invoking
OpenSCAD. It is useful for inspecting a large product before committing Pi CPU
time, but it is not a prerequisite for `generate`.

### OpenSCAD dependencies and offline generation

OpenSCAD models have two related kinds of dependency:

- `use <library.scad>` makes modules and functions available without evaluating
  the library's top-level geometry. `include <library.scad>` also evaluates its
  top-level statements. Both are source dependencies.
- `import("shape.svg")`, `import("part.stl")`, and similar calls load geometry or
  data assets. Plamp tracks imported SVG, DXF, STL, PNG, and other files as
  dependencies too.

OpenSCAD first resolves calling-file-relative references, then searches its
active library paths. Those paths can include `OPENSCADPATH`, the user's library
directory, and installation libraries. A model-local source or asset belongs
beside the model; repository-local shared code belongs elsewhere in this Git
checkout. A shared library outside the repository must be declared by the
system. Installation libraries reported by OpenSCAD are recorded separately;
an undeclared file found only in the user's library directory is rejected.

Declare a shared library in the selected `*.system.cad.json` manifest. The path
may be repository-relative or absolute. Include license and pinned revision
metadata when the library has an independent origin:

```json
{
  "libraries": {
    "fasteners": {
      "path": "vendor/fasteners",
      "license": "SPDX-license-identifier",
      "revision": "exact-tag-or-commit"
    }
  }
}
```

The declaration authorizes an already installed or vendored directory; CAD
generation never downloads a missing library. Check declarations and their
resolved paths before generating:

```bash
plamp cad libraries --system plamp
plamp cad libraries --system plamp --json
```

If generation reports an `undeclared host CAD dependency`, either move that
file into the model/repository or add the library containing it to the system
manifest with its license and revision. If `plamp cad libraries` says a path is
missing or is not a directory, install or vendor the exact declared revision at
that path. Do not fix either error by adding an unrecorded workstation search
path: another host would silently use different geometry.

Generation asks OpenSCAD for its complete transitive dependency list with a
cheap CSG `-d` pass. For a clean or historical run, discovery uses a Git archive
of the selected commit, so a repository helper cannot leak in from the current
working tree. A dirty run uses the explicitly revision-labelled working-tree
closure. Plamp then hashes and classifies the closure, stages it without
flattening paths, and renders with an isolated home and a sanitized
`OPENSCADPATH`. It compares a second `-d` result after rendering; a missing,
changed, escaped, or newly host-resolved dependency fails before publication.
There is no network fallback, so a fully staged run can render offline.

The staged layout preserves relative references:

```text
repository/<repository-relative model and shared files>
libraries/<declared-library-name>/<library-relative files>
libraries/openscad-N/<installation-library-relative files>
```

Every run's `manifest.json` records each job's `dependencies` with its logical
name, classification, staged archive path, SHA-256 content hash, asset flag,
license, and revision. It also records the discovery and sanitized render
search environments. The generated `readme.md` summarizes the same inventory.
Inspect it without guessing paths:

```bash
plamp cad show RUN_ID
jq '.jobs[] | {model, set, dependencies, dependency_environment}' \
  "$PLAMP_DATA_DIR/cad/prints/plamp/RUN_ID/manifest.json"
```

OpenSCAD documents the [library search paths and `use`/`include`
semantics](https://en.wikibooks.org/wiki/OpenSCAD_User_Manual/Libraries) and
the command-line [`-d` dependency-file
option](https://en.wikibooks.org/wiki/OpenSCAD_User_Manual/Using_OpenSCAD_in_a_command_line_environment).

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
`$PLAMP_DATA_DIR/cad/prints/<system>/<RUN_ID>/`. This instance-data directory
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
