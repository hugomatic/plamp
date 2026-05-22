#!/usr/bin/env bash
set -euo pipefail

script_source="${BASH_SOURCE[0]-}"
if [[ -n "${script_source}" && -f "${script_source}" ]]; then
  script_dir="$(cd -- "$(dirname -- "${script_source}")" && pwd)"
  default_repo_dir="$(cd -- "${script_dir}/../.." && pwd)"
else
  script_dir=""
  default_repo_dir="${HOME}/plamp"
fi

repo_url="https://github.com/hugomatic/plamp.git"
repo_dir="${default_repo_dir}"
branch="main"
public_mode=0
update_os=0
enable_heartbeat=0
heartbeat_file=""

usage() {
  cat <<'USAGE'
Usage: deploy/bootstrap/install-plamp.sh [options]

Bootstrap Plamp on a Raspberry Pi with optional public nginx and heartbeat cron jobs.

Options:
  --repo-url URL              Git repo URL (default: https://github.com/hugomatic/plamp.git)
  --repo-dir PATH             Clone/install directory (default: local repo directory)
  --plamp-dir PATH            Alias for --repo-dir
  --branch NAME               Git branch/tag to check out (default: main)
  --public                    Configure nginx on port 80 proxying plamp-web on 127.0.0.1:8000
  --update-os                 Run apt update + full-upgrade
  --enable-heartbeat          Install cron job running agent/check_alive.bash
  --heartbeat-file PATH       Heartbeat target file (used by check_alive via PLAMP_HEARTBEAT_FILE)
  -h, --help                  Show this help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo-url) repo_url="$2"; shift 2 ;;
    --repo-dir|--plamp-dir) repo_dir="$2"; shift 2 ;;
    --branch) branch="$2"; shift 2 ;;
    --public) public_mode=1; shift ;;
    --update-os) update_os=1; shift ;;
    --enable-heartbeat) enable_heartbeat=1; shift ;;
    --heartbeat-file) heartbeat_file="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

echo "==> Installing system packages"
sudo apt-get update
if [[ "${update_os}" -eq 1 ]]; then
  sudo DEBIAN_FRONTEND=noninteractive apt-get -y full-upgrade
fi
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y git curl ca-certificates ffmpeg python3-picamera2 avahi-daemon avahi-utils libnss-mdns
if [[ "${public_mode}" -eq 1 ]]; then
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y nginx
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "==> Installing uv"
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi

if ! command -v uv >/dev/null 2>&1; then
  export PATH="${HOME}/.local/bin:${PATH}"
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is not available after install; ensure ~/.local/bin is on PATH, then retry." >&2
  exit 1
fi
uv_bin="$(command -v uv)"

echo "==> Cloning/updating repo"
if [[ -d "${repo_dir}/.git" ]]; then
  git -C "${repo_dir}" fetch --all --prune
  git -C "${repo_dir}" checkout "${branch}"
  git -C "${repo_dir}" pull --ff-only
else
  git clone "${repo_url}" "${repo_dir}"
  git -C "${repo_dir}" checkout "${branch}"
fi

echo "==> Syncing Python environment"
${uv_bin} sync --project "${repo_dir}"
mkdir -p "${repo_dir}/data"

echo "==> Installing mpremote tool (required for Pico flashing from web UI)"
${uv_bin} tool install --force mpremote
if ! command -v mpremote >/dev/null 2>&1; then
  export PATH="${HOME}/.local/bin:${PATH}"
fi
if ! command -v mpremote >/dev/null 2>&1; then
  echo "mpremote install failed or is not on PATH; cannot continue." >&2
  exit 1
fi

echo "==> Installing plamp-web systemd service"
"${repo_dir}/deploy/systemd/install-plamp-web-service.sh" --repo-root "${repo_dir}" --host 127.0.0.1 --port 8000

echo "==> Enabling mDNS hostname advertising"
sudo systemctl enable --now avahi-daemon

if [[ "${public_mode}" -eq 1 ]]; then
  echo "==> Configuring nginx public proxy on port 80"
  sudo cp "${repo_dir}/deploy/nginx/plamp.conf" /etc/nginx/sites-available/plamp
  sudo ln -sf /etc/nginx/sites-available/plamp /etc/nginx/sites-enabled/plamp
  sudo rm -f /etc/nginx/sites-enabled/default
  sudo nginx -t
  sudo systemctl reload nginx
fi

tmp_cron="$(mktemp)"
trap 'rm -f "${tmp_cron}"' EXIT
crontab -l 2>/dev/null > "${tmp_cron}" || true

if [[ "${enable_heartbeat}" -eq 1 ]]; then
  echo "==> Installing heartbeat cron"
  sed -i '/# plamp-heartbeat/d' "${tmp_cron}"
  sed -i '/agent\/check_alive.bash/d' "${tmp_cron}"
  hb_env=""
  if [[ -n "${heartbeat_file}" ]]; then
    hb_env="PLAMP_HEARTBEAT_FILE=${heartbeat_file} "
  fi
  echo "*/5 * * * * cd ${repo_dir} && ${hb_env}${repo_dir}/agent/check_alive.bash >> ${repo_dir}/data/heartbeat.log 2>&1 # plamp-heartbeat" >> "${tmp_cron}"
fi

crontab "${tmp_cron}"

echo "==> Health checks"
sudo systemctl status plamp-web --no-pager | sed -n '1,10p' || true
wait_for_http() {
  local url="$1"
  local label="$2"
  local attempts="${3:-15}"
  local delay="${4:-1}"
  local attempt
  for ((attempt = 1; attempt <= attempts; attempt += 1)); do
    if curl -fsS "${url}" >/dev/null; then
      echo "${label} OK"
      return 0
    fi
    sleep "${delay}"
  done
  echo "${label} failed" >&2
  return 1
}

wait_for_http "http://127.0.0.1:8000/" "plamp-web :8000"
if [[ "${public_mode}" -eq 1 ]]; then
  wait_for_http "http://127.0.0.1/" "nginx :80"
fi

echo "Done."
