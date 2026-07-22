#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)"
cd "$SCRIPT_DIR"

if ! command -v openscad >/dev/null 2>&1; then
  echo "SKIP: openscad not found on PATH"
  exit 0
fi

commit=$(git -C "$REPO_ROOT" log -n 1 --pretty=format:%h -- "$SCRIPT_DIR/plamp_stand.scad")
outdir=$(mktemp -d /tmp/plamp-stand-check-XXXXXX)
trap 'rm -rf "$outdir"' EXIT

"$REPO_ROOT/bin/plamp" cad generate plamp_stand --preset all-views-default --revision "$commit" --output "$outdir/out"

for f in \
  "$outdir/out/plamp_stand_assembly_${commit}.stl" \
  "$outdir/out/plamp_stand_tripod_${commit}.stl" \
  "$outdir/out/plamp_stand_plate_${commit}.stl" \
  "$outdir/out/plamp_stand_camera_clip_${commit}.stl" \
  "$outdir/out/readme.md"
do
  if [[ ! -s "$f" ]]; then
    echo "FAIL: expected non-empty file missing: $f"
    exit 1
  fi
done

echo "PASS: plamp cad produced STL files from plamp_stand.scad for commit $commit"
