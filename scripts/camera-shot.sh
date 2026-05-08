#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 OUTPUT_JPG_PATH" >&2
  exit 2
fi

output_path="$1"
camera_id="${PLAMP_CAMERA_ID:-camera}"
timestamp="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
timestamp_fs="${timestamp//:/-}"
af_mode="${PLAMP_AUTOFOCUS_MODE:-auto}"
af_delay_ms="${PLAMP_AUTOFOCUS_DELAY_MS:-1200}"
log_file="/tmp/plamp-camera-${camera_id}-${timestamp_fs}.log"

mkdir -p "$(dirname -- "${output_path}")"

if command -v rpicam-still >/dev/null 2>&1; then
  cmd=(rpicam-still)
elif command -v libcamera-still >/dev/null 2>&1; then
  cmd=(libcamera-still)
else
  echo "camera command not found: tried rpicam-still and libcamera-still" >&2
  exit 127
fi

cmd+=(-o "${output_path}" -n)
if [[ -n "${af_mode}" ]]; then
  cmd+=(--autofocus-mode "${af_mode}")
fi
if [[ "${af_delay_ms}" =~ ^[0-9]+$ ]] && [[ "${af_delay_ms}" -gt 0 ]]; then
  cmd+=(--timeout "${af_delay_ms}")
fi

if "${cmd[@]}" >"${log_file}" 2>&1; then
  exit_code=0
else
  exit_code=$?
fi

echo "timestamp=${timestamp}"
echo "image=${output_path}"
echo "command=${cmd[*]}"
echo "exit_code=${exit_code}"
echo "log=${log_file}"
echo "camera_id=${camera_id}"

exit "${exit_code}"
