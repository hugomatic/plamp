#!/usr/bin/env bash

cad="__cad__name__"
views=("plate" "assembly")

# we are assuming that a part.scad file exists in part directory
# (if the scad file is not standalone, all depends should be put there too)
# using git show, we make a copy of part.scad in /tmp folder at the commit
#    git show 90a6eba:part/part.scad
# we then use openscad to generate an stl file from the tmp directory
#    part_90a6eba.stl

# this file logs the output of this script
log="readme.md"

SCAD_FILE="${cad}.scad"
# name of the stl file, without the commit
STL_PREFIX="${cad}"
# name of this script (generate.bash)
name=$0
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null)" || {
  echo "Could not find git repository root for $SCRIPT_DIR" >&2
  exit 1
}
SCAD_REPO_DIR="${SCRIPT_DIR#$REPO_ROOT/}"
SCAD_REPO_PATH="$SCAD_REPO_DIR/$SCAD_FILE"

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

if [[ "$#" -ne 2 ]];
    then
        last_commit=`git -C "$REPO_ROOT" log -n 1 --pretty=format:%h -- "$SCAD_REPO_PATH"`
        today=`date +%b%d | tr 'A-Z' 'a-z'`
        echo
        echo "$cad stl generator"
        echo "usage:"
        echo "  $name target_directory commit_hash"
        echo
        echo "ex:"
        echo "  $name prints/$today $last_commit"
        echo
        echo
        # check if file is modified on disk
        git_stat=`git -C "$REPO_ROOT" status --porcelain -s | grep "$SCAD_REPO_PATH"`
        if [[ $git_stat ]];
          then
            echo "!!"
            echo "!! git status: $git_stat"
            echo "!! WARNING Please commit first if you want repeatable results"
            echo "!! File $SCAD_FILE is not committed (see git status below)"
            echo "!!"
        fi
        exit -1
fi

target_directory=$1
[ -d "$1" ] && echo "Error: directory $1 already exists." && exit -2

commit=$2
OPENSCAD_CMD="$(find_openscad)" || exit 1

echo "commit $commit"
echo "target_directory $target_directory"
echo "openscad $OPENSCAD_CMD"


mkdir -p $target_directory
cd "$target_directory"
# remove any previous file
rm -f /tmp/scad_doc.scad


# get the correct version of the cad file in the temp directory
echo "# $SCAD_FILE" | tee -a $log
date | tee -a $log
echo "get the source CAD:" | tee -a $log
echo '```' >> $log
echo "git show $commit:$SCAD_REPO_PATH" | tee -a $log
echo '```' >> $log
if ! git -C "$REPO_ROOT" show "$commit:$SCAD_REPO_PATH" > /tmp/scad_doc.scad; then
  echo "Could not read $SCAD_REPO_PATH at commit $commit" >&2
  exit 1
fi

for view in "${views[@]}"
do
  stl_file="${STL_PREFIX}_${view}_${commit}.stl"
  echo "## [$stl_file]($stl_file)" | tee -a $log

  options="-D revision_string=\"$commit\" -D view=\"$view\" -D ball_quality=64"
  echo -e "\noptions: $options\n" | tee -a $log

  echo '```' >> $log
  time "$OPENSCAD_CMD" $options --export-format asciistl -o $stl_file /tmp/scad_doc.scad 2>&1 | tee -a $log
  echo '```' >> $log
done
