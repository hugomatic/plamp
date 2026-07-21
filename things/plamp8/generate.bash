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
expect_value=0
options_enabled=1
for arg in "$@"; do
  if [[ "$expect_value" -eq 1 ]]; then
    args+=("$arg")
    expect_value=0
    continue
  fi
  if [[ "$options_enabled" -eq 0 ]]; then
    args+=("$arg")
    continue
  fi
  case "$arg" in
    --)
      args+=("$arg")
      options_enabled=0
      ;;
    --preset|--view|--define|-D|--view-define|--revision|--output|--openscad|--scad|--legacy-output|--legacy-commit)
      args+=("$arg")
      expect_value=1
      ;;
    --box) args+=(--preset fuse-box) ;;
    *) args+=("$arg") ;;
  esac
done

exec "$python_bin" -m plamp cad generate "$script_dir/$cad.scad" "${args[@]}"
