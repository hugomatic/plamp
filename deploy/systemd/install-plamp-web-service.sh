#!/usr/bin/env bash
set -euo pipefail

service_name="plamp-web"
service_user=""
repo_root=""
uv_bin=""
host="127.0.0.1"
port="8000"
print_unit=0

usage() {
  cat <<'USAGE'
Usage: deploy/systemd/install-plamp-web-service.sh [options]

Install a systemd service that starts Plamp's Uvicorn server on boot.
Run this from the user account that should own the Plamp process.

Options:
  --print-unit          Print the generated service unit instead of installing it
  --user USER           Service user; defaults to the current user
  --repo-root PATH      Plamp repository path; defaults to the current repo
  --uv PATH             uv executable path; defaults to command -v uv
  --host HOST           Bind host; defaults to 127.0.0.1
  --port PORT           Bind port; defaults to 8000
  --service-name NAME   systemd service name; defaults to plamp-web
  -h, --help            Show this help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --print-unit)
      print_unit=1
      shift
      ;;
    --user)
      service_user="$2"
      shift 2
      ;;
    --repo-root)
      repo_root="$2"
      shift 2
      ;;
    --uv)
      uv_bin="$2"
      shift 2
      ;;
    --host)
      host="$2"
      shift 2
      ;;
    --port)
      port="$2"
      shift 2
      ;;
    --service-name)
      service_name="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
default_repo_root="$(cd "$script_dir/../.." && pwd -P)"

if [[ -z "$service_user" ]]; then
  if [[ "${EUID}" -eq 0 ]]; then
    echo "run this installer as the user that should run Plamp, not as root" >&2
    exit 1
  fi
  service_user="$(id -un)"
fi

if [[ -z "$repo_root" ]]; then
  repo_root="$default_repo_root"
fi

if [[ -z "$uv_bin" ]]; then
  if ! uv_bin="$(command -v uv)"; then
    echo "uv was not found on PATH; install uv or pass --uv /path/to/uv" >&2
    exit 1
  fi
fi

generate_unit() {
  cat <<UNIT
[Unit]
Description=Plamp web server
After=network.target
RequiresMountsFor=$repo_root

[Service]
Type=simple
User=$service_user
WorkingDirectory=$repo_root
ExecStart=$uv_bin run uvicorn plamp_web.server:app --host $host --port $port
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT
}

if [[ "$print_unit" -eq 1 ]]; then
  generate_unit
  exit 0
fi

if ! id "$service_user" >/dev/null 2>&1; then
  echo "service user does not exist: $service_user" >&2
  exit 1
fi

if [[ ! -d "$repo_root" ]]; then
  echo "repo root does not exist: $repo_root" >&2
  exit 1
fi

if [[ ! -x "$uv_bin" ]]; then
  echo "uv executable is not executable: $uv_bin" >&2
  exit 1
fi

if ! id -nG "$service_user" | tr ' ' '\n' | grep -qx 'dialout'; then
  echo "warning: $service_user is not in the dialout group; Pico serial access may fail" >&2
fi

unit_path="/etc/systemd/system/${service_name}.service"
tmp_unit="$(mktemp)"
trap 'rm -f "$tmp_unit"' EXIT

generate_unit > "$tmp_unit"

sudo install -m 0644 "$tmp_unit" "$unit_path"
sudo systemctl daemon-reload
sudo systemctl enable "$service_name"
sudo systemctl restart "$service_name"

echo "installed and started $service_name"
echo "check status with: sudo systemctl status $service_name"
