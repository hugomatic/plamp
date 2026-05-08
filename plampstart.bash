#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
install_script="${script_dir}/deploy/bootstrap/install-plamp.sh"

usage() {
  cat <<'USAGE'
Usage: ./plampstart.bash [restart|reinstall] [install options]

Without an action, prompts interactively.

Actions:
  restart                  Restart plamp-web and show status
  reinstall [options...]   Run deploy/bootstrap/install-plamp.sh with --plamp-dir set to this repo root

Examples:
  ./plampstart.bash
  ./plampstart.bash restart
  ./plampstart.bash reinstall --public
  ./plampstart.bash reinstall --update-os --enable-heartbeat

Help:
  ./plampstart.bash -h
USAGE
}

restart_plamp() {
  sudo systemctl restart plamp-web
  sudo systemctl status plamp-web --no-pager
}

reinstall_plamp() {
  if [[ ! -x "${install_script}" ]]; then
    echo "install script not found or not executable: ${install_script}" >&2
    exit 1
  fi
  "${install_script}" --plamp-dir "${script_dir}" "$@"
}

prompt_action() {
  local reply
  printf 'Choose action: [r]estart, re[i]nstall, [c]ancel: '
  read -r reply
  case "${reply}" in
    r|R|restart|Restart)
      restart_plamp
      ;;
    i|I|reinstall|Reinstall)
      reinstall_plamp
      ;;
    c|C|cancel|Cancel|"")
      echo "Cancelled."
      ;;
    *)
      echo "unknown choice: ${reply}" >&2
      usage >&2
      exit 2
      ;;
  esac
}

case "${1-}" in
  "")
    prompt_action
    ;;
  -h|--help)
    usage
    ;;
  restart)
    shift
    if [[ $# -gt 0 ]]; then
      echo "restart does not accept extra arguments." >&2
      usage >&2
      exit 2
    fi
    restart_plamp
    ;;
  reinstall)
    shift
    reinstall_plamp "$@"
    ;;
  *)
    echo "unknown action: $1" >&2
    usage >&2
    exit 2
    ;;
esac
