#!/usr/bin/env bash
set -euo pipefail

cad="plamp8"
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(git -C "$script_dir" rev-parse --show-toplevel)"
python_bin="$repo_root/.venv/bin/python"
if [[ ! -x "$python_bin" ]]; then
  python_bin="$(command -v python3)" || {
    echo "Python not found: expected $repo_root/.venv/bin/python or python3 on PATH" >&2
    exit 1
  }
fi
export PYTHONPATH="$repo_root${PYTHONPATH:+:$PYTHONPATH}"

args=()
for arg in "$@"; do
  case "$arg" in
    --box) args+=(--preset fuse-box) ;;
    *) args+=("$arg") ;;
  esac
done

exec "$python_bin" -m plamp cad generate "$script_dir/$cad.scad" "${args[@]}"
