#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
install_script="${script_dir}/deploy/bootstrap/install-plamp.sh"

usage() {
  cat <<'USAGE'
Usage: ./plampstart.bash [restart|reinstall|remote-install] [args...]

Without an action, prompts interactively.

Actions:
  restart                  Restart plamp-web and show status
  reinstall [options...]   Run deploy/bootstrap/install-plamp.sh with --plamp-dir set to this repo root
  remote-install HOST REMOTE_DIR [options...]
                           Copy deploy/bootstrap/install-plamp.sh to HOST and run it there with --plamp-dir REMOTE_DIR

Examples:
  ./plampstart.bash
  ./plampstart.bash restart
  ./plampstart.bash reinstall --public
  ./plampstart.bash reinstall --update-os --enable-heartbeat
  ./plampstart.bash remote-install hugo@sprout ~/plamp --public

Help:
  ./plampstart.bash -h
USAGE
}

restart_plamp() {
  sudo systemctl restart plamp-web
  sudo systemctl status plamp-web --no-pager
}

reinstall_plamp() {
  if [[ ! -f "${install_script}" ]]; then
    echo "install script not found: ${install_script}" >&2
    exit 1
  fi
  bash "${install_script}" --plamp-dir "${script_dir}" "$@"
}

remote_install_plamp() {
  if [[ $# -lt 2 ]]; then
    echo "remote-install requires HOST and REMOTE_DIR." >&2
    usage >&2
    exit 2
  fi
  if [[ ! -f "${install_script}" ]]; then
    echo "install script not found: ${install_script}" >&2
    exit 1
  fi

  local host="$1"
  local remote_dir="$2"
  shift 2

  local quoted_remote_dir
  quoted_remote_dir="$(printf '%q' "${remote_dir}")"

  local remote_cmd
  remote_cmd="bash -s -- --plamp-dir ${quoted_remote_dir}"
  if [[ $# -gt 0 ]]; then
    printf -v remote_cmd '%s %q' "${remote_cmd}" "$@"
  fi

  echo "Remote host    : ${host}"
  echo "Remote plamp dir: ${remote_dir}"
  echo "Remote command : ${remote_cmd}"
  ssh "${host}" "${remote_cmd}" < "${install_script}"
}

prompt_action() {
  local reply
  printf 'Choose action: [r]estart, re[i]nstall, remote-[s]sh install, [c]ancel: '
  read -r reply
  case "${reply}" in
    r|R|restart|Restart)
      restart_plamp
      ;;
    i|I|reinstall|Reinstall)
      reinstall_plamp
      ;;
    s|S|ssh|SSH|remote|Remote|remote-install|Remote-install)
      local host
      local remote_dir
      printf 'SSH host (example hugo@sprout): '
      read -r host
      printf 'Remote plamp dir (example ~/plamp): '
      read -r remote_dir
      remote_install_plamp "${host}" "${remote_dir}"
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
  remote-install)
    shift
    remote_install_plamp "$@"
    ;;
  *)
    echo "unknown action: $1" >&2
    usage >&2
    exit 2
    ;;
esac
