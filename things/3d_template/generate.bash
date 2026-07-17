#!/usr/bin/env bash
set -euo pipefail

cad="__cad__name__"

# this file logs the output of this script
log="readme.md"

SCAD_FILE="${cad}.scad"
# name of the stl file, without the commit
STL_PREFIX="${cad}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null)" || {
  echo "Could not find git repository root for $SCRIPT_DIR" >&2
  exit 1
}
SCAD_REPO_DIR="${SCRIPT_DIR#$REPO_ROOT/}"
name=$0

find_openscad() {
  if [[ -n "${OPENSCAD_BIN:-}" ]]; then
    [[ -x "$OPENSCAD_BIN" ]] && {
      printf '%s\n' "$OPENSCAD_BIN"
      return 0
    }
    echo "OPENSCAD_BIN is set but not executable: $OPENSCAD_BIN" >&2
    return 1
  fi

  if command -v openscad >/dev/null 2>&1; then
    command -v openscad
    return 0
  fi

  case "$(uname -s)" in
    Darwin)
      for p in \
        "/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD" \
        "$HOME/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD"
      do
        [[ -x "$p" ]] && {
          printf '%s\n' "$p"
          return 0
        }
      done
      ;;
    Linux)
      for p in \
        "/usr/bin/openscad" \
        "/usr/local/bin/openscad" \
        "/snap/bin/openscad" \
        "/var/lib/flatpak/exports/bin/org.openscad.OpenSCAD" \
        "$HOME/.local/share/flatpak/exports/bin/org.openscad.OpenSCAD"
      do
        [[ -x "$p" ]] && {
          printf '%s\n' "$p"
          return 0
        }
      done
      ;;
  esac

  echo "OpenSCAD not found. Set OPENSCAD_BIN=/path/to/openscad" >&2
  return 1
}

usage() {
  local source_date source_revision
  source_revision="$(git -C "$REPO_ROOT" log --max-count=1 --format=%h -- "$SCAD_REPO_DIR" 2>/dev/null || true)"
  source_date="$(git -C "$REPO_ROOT" log --max-count=1 --date=format:%B%d --format=%cd -- "$SCAD_REPO_DIR" 2>/dev/null | tr 'A-Z' 'a-z' || true)"
  cat <<EOF

$cad stl generator

usage:
  $name [--revision TEXT] [--scad FILE] [--view VIEW] [--preview] [--define EXPR] target_directory [commit]

examples:
  # Generate every view from the latest committed part source.
  $name prints/${cad}_${source_date:-unknown}

  # Reproduce a broken part from its engraved commit hash.
  $name prints/${cad}_${source_date:-unknown}_replacement ${source_revision:-COMMIT}

  # Render uncommitted fit-test changes with an honest temporary label.
  $name --revision fit-test-1 prints/${cad}_fit

  # Quickly check one low-detail view without text; not for printing.
  $name --revision layout --preview --view top_panel prints/${cad}_preview

EOF
}

sanitize_label() {
  printf '%s' "$1" | tr -c 'A-Za-z0-9_.-' '_'
}

extract_views() {
  local scad_path="$1"
  local line comment assigned

  line="$(grep -m 1 -E '^[[:space:]]*view[[:space:]]*=' "$scad_path" || true)"
  comment="$(printf '%s\n' "$line" | sed -n 's/.*\/\/[[:space:]]*\[\([^]]*\)\].*/\1/p')"
  if [[ -n "$comment" ]]; then
    printf '%s\n' "$comment" |
      tr ',' '\n' |
      sed 's/^[[:space:]]*//; s/[[:space:]]*$//' |
      sed '/^$/d'
    return
  fi

  assigned="$(printf '%s\n' "$line" | sed -n 's/^[[:space:]]*view[[:space:]]*=[[:space:]]*"\([^"]*\)".*/\1/p')"
  if [[ -n "$assigned" ]]; then
    printf '%s\n' "$assigned"
    return
  fi

  printf '%s\n' "assembly"
}

target_directory=""
commit=""
revision_text=""
preview=0
extra_defines=()
view_filter=""

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --revision)
      [[ "$#" -ge 2 ]] || {
        echo "--revision requires a value" >&2
        exit 2
      }
      revision_text="$2"
      shift 2
      ;;
    --scad)
      [[ "$#" -ge 2 ]] || {
        echo "--scad requires a value" >&2
        exit 2
      }
      SCAD_FILE="$2"
      STL_PREFIX="$(basename "$SCAD_FILE" .scad)"
      shift 2
      ;;
    --preview)
      preview=1
      shift
      ;;
    --view)
      [[ "$#" -ge 2 ]] || {
        echo "--view requires a value" >&2
        exit 2
      }
      view_filter="$2"
      shift 2
      ;;
    --define|-D)
      [[ "$#" -ge 2 ]] || {
        echo "$1 requires a value" >&2
        exit 2
      }
      extra_defines+=("$2")
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    -*)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
    *)
      if [[ -z "$target_directory" ]]; then
        target_directory="$1"
      elif [[ -z "$commit" ]]; then
        commit="$1"
      else
        echo "Unexpected argument: $1" >&2
        usage >&2
        exit 2
      fi
      shift
      ;;
  esac
done

if [[ -z "$target_directory" ]]; then
  usage >&2
  exit 2
fi

case "$SCAD_FILE" in
  /*|*../*)
    echo "--scad must be a file path inside this part directory: $SCAD_FILE" >&2
    exit 2
    ;;
esac

SCAD_REPO_PATH="$SCAD_REPO_DIR/$SCAD_FILE"

if [[ -e "$target_directory" ]]; then
  echo "Error: target already exists: $target_directory" >&2
  exit 2
fi

OPENSCAD_CMD="$(find_openscad)" || exit 1

part_status="$(git -C "$REPO_ROOT" status --porcelain -- "$SCAD_REPO_DIR")"
dirty_part=0
[[ -n "$part_status" ]] && dirty_part=1

if [[ "$dirty_part" -eq 1 && -z "$revision_text" ]]; then
  head_hash="$(git -C "$REPO_ROOT" rev-parse --short HEAD)"
  echo "part directory has uncommitted changes; provide --revision TEXT to render dirty CAD" >&2
  echo "HEAD: $head_hash" >&2
  echo "part: $SCAD_REPO_DIR" >&2
  echo "git status --porcelain -- $SCAD_REPO_DIR" >&2
  printf '%s\n' "$part_status" >&2
  exit 3
fi

if [[ "$dirty_part" -eq 0 ]]; then
  if [[ -z "$commit" ]]; then
    resolved_commit="$(git -C "$REPO_ROOT" log --max-count=1 --format=%H -- "$SCAD_REPO_DIR")"
    [[ -n "$resolved_commit" ]] || {
      echo "No commit found for $SCAD_REPO_DIR" >&2
      exit 1
    }
    commit="$resolved_commit"
  else
    resolved_commit="$(git -C "$REPO_ROOT" rev-parse --verify "$commit^{commit}")"
  fi
  revision_label="$(git -C "$REPO_ROOT" rev-parse --short "$resolved_commit")"
else
  resolved_commit="$(git -C "$REPO_ROOT" rev-parse --verify HEAD)"
  revision_label="$(sanitize_label "$revision_text")"
fi

echo "commit $commit"
echo "revision $revision_label"
echo "target_directory $target_directory"
echo "openscad $OPENSCAD_CMD"

build_root="$(mktemp -d)"
cleanup() {
  rm -rf "$build_root"
}
trap cleanup EXIT

if [[ "$dirty_part" -eq 0 ]]; then
  git -C "$REPO_ROOT" archive "$resolved_commit" "$SCAD_REPO_DIR" | tar -C "$build_root" -xf -
else
  mkdir -p "$build_root/$(dirname "$SCAD_REPO_DIR")"
  cp -a "$SCRIPT_DIR" "$build_root/$SCAD_REPO_DIR"
fi

build_part_dir="$build_root/$SCAD_REPO_DIR"
build_scad_path="$build_part_dir/$SCAD_FILE"
if [[ ! -f "$build_scad_path" ]]; then
  echo "Could not find $SCAD_FILE in $SCAD_REPO_DIR" >&2
  exit 1
fi

mapfile -t views < <(extract_views "$build_scad_path")
if [[ "${#views[@]}" -eq 0 ]]; then
  echo "No views found in $SCAD_FILE" >&2
  exit 1
fi
if [[ -n "$view_filter" ]]; then
  views=("$view_filter")
fi

mkdir -p "$target_directory"
cd "$target_directory"

{
  echo "# $SCAD_FILE"
  date
  echo "source CAD:"
  echo '```'
  if [[ "$dirty_part" -eq 0 ]]; then
    echo "git archive $resolved_commit $SCAD_REPO_DIR"
  else
    echo "dirty working tree copy from $SCAD_REPO_DIR"
    echo "base HEAD $resolved_commit"
    echo "revision text $revision_text"
  fi
  echo '```'
} | tee -a "$log"

for view in "${views[@]}"
do
  stl_file="${STL_PREFIX}_${view}_${revision_label}.stl"
  echo "## [$stl_file]($stl_file)" | tee -a $log

  options=(-D "revision_string=\"$revision_label\"" -D "view=\"$view\"")
  if [[ "$preview" -eq 1 ]]; then
    options+=(-D "render_text=false" -D "render_fn=24")
  fi
  for define in "${extra_defines[@]}"; do
    options+=(-D "$define")
  done
  echo -e "\noptions: ${options[*]}\n" | tee -a $log

  echo '```' >> $log
  time "$OPENSCAD_CMD" "${options[@]}" --export-format asciistl -o "$stl_file" "$build_scad_path" 2>&1 | tee -a "$log"
  echo '```' >> $log
done
