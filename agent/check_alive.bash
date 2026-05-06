#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AGENT_DIR="${REPO_ROOT}/agent"
STATE_FILE="${AGENT_DIR}/check_alive_state.json"
WORKSPACE_ROOT="/home/hugo/.openclaw/workspace"
LAST_SEEN_TXT="${WORKSPACE_ROOT}/last_seen_alive.txt"
GROWS_DIR="${REPO_ROOT}/grow/grows"
DAILY_CHECK_MD="${AGENT_DIR}/check_daily.md"
WEEKLY_CHECK_MD="${AGENT_DIR}/check_weekly.md"

now_iso="$(date -Iseconds)"
printf '%s\n' "${now_iso}" > "${LAST_SEEN_TXT}"

latest_grow_dir="$(find "${GROWS_DIR}" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' | sort -nr | head -n 1 | cut -d' ' -f2- || true)"
daily_dir=""
weekly_dir=""
latest_daily=""
latest_weekly=""
daily_due="unknown"
weekly_due="unknown"
daily_elapsed_seconds=""
weekly_elapsed_seconds=""

if [[ -n "${latest_grow_dir}" ]]; then
  daily_dir="${latest_grow_dir}/summaries/daily"
  weekly_dir="${latest_grow_dir}/summaries/weekly"

  if [[ -d "${daily_dir}" ]]; then
    latest_daily="$(find "${daily_dir}" -maxdepth 1 -type f -name '*.json' -printf '%T@ %p\n' | sort -nr | head -n 1 | cut -d' ' -f2- || true)"
  fi
  if [[ -d "${weekly_dir}" ]]; then
    latest_weekly="$(find "${weekly_dir}" -maxdepth 1 -type f -name '*.json' -printf '%T@ %p\n' | sort -nr | head -n 1 | cut -d' ' -f2- || true)"
  fi
fi

now_epoch="$(date +%s)"

if [[ -n "${latest_daily}" && -f "${latest_daily}" ]]; then
  daily_mtime="$(stat -c %Y "${latest_daily}")"
  daily_elapsed_seconds="$(( now_epoch - daily_mtime ))"
  if (( daily_elapsed_seconds > 86400 )); then
    daily_due="yes"
  else
    daily_due="no"
  fi
else
  daily_due="yes"
fi

if [[ -n "${latest_weekly}" && -f "${latest_weekly}" ]]; then
  weekly_mtime="$(stat -c %Y "${latest_weekly}")"
  weekly_elapsed_seconds="$(( now_epoch - weekly_mtime ))"
  if (( weekly_elapsed_seconds > 604800 )); then
    weekly_due="yes"
  else
    weekly_due="no"
  fi
else
  weekly_due="yes"
fi

json_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

cat > "${STATE_FILE}" <<EOF
{
  "last_seen_alive": "$(json_escape "${now_iso}")",
  "repo_root": "$(json_escape "${REPO_ROOT}")",
  "latest_grow": "$(json_escape "${latest_grow_dir}")",
  "latest_daily_summary": "$(json_escape "${latest_daily}")",
  "latest_weekly_summary": "$(json_escape "${latest_weekly}")",
  "daily_due": "${daily_due}",
  "weekly_due": "${weekly_due}",
  "daily_elapsed_seconds": ${daily_elapsed_seconds:-null},
  "weekly_elapsed_seconds": ${weekly_elapsed_seconds:-null}
}
EOF

echo "last_seen_alive updated: ${now_iso}"
echo "last_seen_alive file: ${LAST_SEEN_TXT}"
echo "state file: ${STATE_FILE}"
if [[ -n "${latest_grow_dir}" ]]; then
  echo "latest_grow_dir: ${latest_grow_dir}"
else
  echo "latest_grow_dir: not found"
fi

if [[ "${daily_due}" == "yes" ]]; then
  echo "DAILY_CHECK_DUE: yes"
  echo "Action: read ${DAILY_CHECK_MD} and do what is inside."
else
  echo "DAILY_CHECK_DUE: no"
fi

if [[ "${weekly_due}" == "yes" ]]; then
  echo "WEEKLY_CHECK_DUE: yes"
  echo "Action: read ${WEEKLY_CHECK_MD} and do what is inside."
else
  echo "WEEKLY_CHECK_DUE: no"
fi
