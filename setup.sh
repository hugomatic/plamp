#!/usr/bin/env bash

_plamp_remove_path_entry() {
  local target="$1"
  local part
  local rebuilt=""
  local -a parts

  IFS=: read -r -a parts <<< "${PATH:-}"
  for part in "${parts[@]}"; do
    [[ "$part" == "$target" ]] && continue
    if [[ -z "$rebuilt" ]]; then
      rebuilt="$part"
    else
      rebuilt="${rebuilt}:$part"
    fi
  done
  PATH="$rebuilt"
}

_plamp_setup_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
_plamp_old_root="${PLAMP_ROOT:-}"

if [[ -n "$_plamp_old_root" ]]; then
  _plamp_remove_path_entry "$_plamp_old_root/bin"
  _plamp_remove_path_entry "$_plamp_old_root/.venv/bin"
  _plamp_remove_path_entry "$_plamp_old_root"
fi

_plamp_remove_path_entry "$_plamp_setup_dir/bin"
_plamp_remove_path_entry "$_plamp_setup_dir/.venv/bin"
_plamp_remove_path_entry "$_plamp_setup_dir"

export PLAMP_ROOT="$_plamp_setup_dir"
if [[ -n "${1:-}" ]]; then
  case "$1" in
    /*) export PLAMP_DATA_DIR="$1" ;;
    *) export PLAMP_DATA_DIR="$(realpath -m -- "$PWD/$1")" ;;
  esac
else
  export PLAMP_DATA_DIR="$PLAMP_ROOT/data"
fi
export PATH="$PLAMP_ROOT/bin:$PLAMP_ROOT/.venv/bin:$PLAMP_ROOT:$PATH"
hash -r

printf 'PLAMP_ROOT=%s\n' "$PLAMP_ROOT"
printf 'PLAMP_DATA_DIR=%s\n' "$PLAMP_DATA_DIR"

unset _plamp_setup_dir _plamp_old_root
unset -f _plamp_remove_path_entry
