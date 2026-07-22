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

"$REPO_ROOT/bin/plamp" cad generate plamp_stand --preset all-views-default --revision "$commit" --output "$outdir/out" --json

python3 - "$outdir/out/manifest.json" <<'PY'
import json
import sys
from pathlib import Path

manifest_path = Path(sys.argv[1])
run_dir = manifest_path.parent.resolve()
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
if manifest.get("status") != "complete":
    raise SystemExit(f"FAIL: CAD run is not complete: {manifest.get('status')!r}")
jobs = manifest.get("jobs")
if not isinstance(jobs, list) or not jobs:
    raise SystemExit("FAIL: CAD manifest has no jobs")
if not all(isinstance(job, dict) for job in jobs):
    raise SystemExit("FAIL: CAD manifest contains an invalid job")
expected_views = {"assembly", "tripod", "plate", "camera_clip"}
actual_view_values = [job.get("view") for job in jobs]
if not all(isinstance(view, str) for view in actual_view_values):
    raise SystemExit(f"FAIL: CAD manifest contains invalid views: {actual_view_values!r}")
actual_views = set(actual_view_values)
if len(actual_view_values) != len(expected_views) or actual_views != expected_views:
    missing = sorted(expected_views - actual_views)
    extra = sorted(actual_views - expected_views)
    raise SystemExit(f"FAIL: unexpected Stand views; missing={missing}, extra={extra}")
for job in jobs:
    if job.get("status") != "complete":
        raise SystemExit(f"FAIL: CAD job is not complete: {job!r}")
    relative_artifact = job.get("artifact")
    if not isinstance(relative_artifact, str):
        raise SystemExit(f"FAIL: completed CAD job has no artifact: {job!r}")
    artifact = (run_dir / relative_artifact).resolve()
    try:
        artifact.relative_to(run_dir)
    except ValueError:
        raise SystemExit(f"FAIL: artifact escapes output directory: {relative_artifact}")
    if not artifact.is_file() or artifact.stat().st_size == 0:
        raise SystemExit(f"FAIL: expected non-empty artifact missing: {artifact}")
readme = run_dir / "readme.md"
if not readme.is_file() or readme.stat().st_size == 0:
    raise SystemExit(f"FAIL: expected non-empty file missing: {readme}")
PY

echo "PASS: plamp cad produced STL files from plamp_stand.scad for commit $commit"
