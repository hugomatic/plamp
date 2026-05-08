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
enable_hourly_capture=0
grow_id=""
enable_heartbeat=0
heartbeat_file=""

usage() {
  cat <<'USAGE'
Usage: deploy/bootstrap/install-plamp.sh [options]

Bootstrap Plamp on a Raspberry Pi with optional public nginx and automation cron jobs.

Options:
  --repo-url URL              Git repo URL (default: https://github.com/hugomatic/plamp.git)
  --repo-dir PATH             Clone/install directory (default: local repo directory)
  --plamp-dir PATH            Alias for --repo-dir
  --branch NAME               Git branch/tag to check out (default: main)
  --public                    Configure nginx on port 80 proxying plamp-web on 127.0.0.1:8000
  --update-os                 Run apt update + full-upgrade
  --enable-hourly-capture     Install cron job for grow/hourly_tend.py
  --grow-id ID                Required with --enable-hourly-capture
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
    --enable-hourly-capture) enable_hourly_capture=1; shift ;;
    --grow-id) grow_id="$2"; shift 2 ;;
    --enable-heartbeat) enable_heartbeat=1; shift ;;
    --heartbeat-file) heartbeat_file="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ "${enable_hourly_capture}" -eq 1 && -z "${grow_id}" ]]; then
  echo "--grow-id is required with --enable-hourly-capture" >&2
  exit 2
fi

echo "==> Installing system packages"
sudo apt-get update
if [[ "${update_os}" -eq 1 ]]; then
  sudo DEBIAN_FRONTEND=noninteractive apt-get -y full-upgrade
fi
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y git curl ca-certificates
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

if [[ "${public_mode}" -eq 1 ]]; then
  echo "==> Configuring nginx public proxy on port 80"
  sudo cp "${repo_dir}/deploy/nginx/plamp.conf" /etc/nginx/sites-available/plamp
  sudo ln -sf /etc/nginx/sites-available/plamp /etc/nginx/sites-enabled/plamp
  sudo rm -f /etc/nginx/sites-enabled/default
  sudo nginx -t
  sudo systemctl reload nginx
fi

install_user="$(id -un)"
tmp_cron="$(mktemp)"
trap 'rm -f "${tmp_cron}"' EXIT
crontab -l 2>/dev/null > "${tmp_cron}" || true

if [[ "${enable_hourly_capture}" -eq 1 ]]; then
  echo "==> Installing hourly capture cron"
  sed -i '/# plamp-hourly-capture/d' "${tmp_cron}"
  sed -i '/grow\/hourly_tend.py --grow/d' "${tmp_cron}"
  echo "0 * * * * cd ${repo_dir} && ${uv_bin} run python grow/hourly_tend.py --grow ${grow_id} >> ${repo_dir}/data/hourly_tend.log 2>&1 # plamp-hourly-capture" >> "${tmp_cron}"
fi

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
curl -fsS http://127.0.0.1:8000/ >/dev/null && echo "plamp-web :8000 OK"
if [[ "${public_mode}" -eq 1 ]]; then
  curl -fsS http://127.0.0.1/ >/dev/null && echo "nginx :80 OK"
fi

echo "Done."
