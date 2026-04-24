#!/usr/bin/env bash

set -euo pipefail

REMOTE_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REMOTE_ROOT_DIR="$(cd "$REMOTE_SCRIPT_DIR/../.." && pwd)"
REMOTE_ENV_FILE_DEFAULT="$REMOTE_ROOT_DIR/.remote_spark.env"

load_remote_env() {
  local env_file="${REMOTE_ENV_FILE:-$REMOTE_ENV_FILE_DEFAULT}"
  if [[ -f "$env_file" ]]; then
    # shellcheck disable=SC1090
    source "$env_file"
  fi

  : "${REMOTE_HOST:?Set REMOTE_HOST in .remote_spark.env or the environment.}"
  : "${REMOTE_REPO_DIR:?Set REMOTE_REPO_DIR in .remote_spark.env or the environment.}"

  REMOTE_USER="${REMOTE_USER:-$USER}"
  REMOTE_PORT="${REMOTE_PORT:-22}"
  REMOTE_PYTHON_BIN="${REMOTE_PYTHON_BIN:-python3.12}"
  REMOTE_GIT_PULL="${REMOTE_GIT_PULL:-false}"
  REMOTE_SSH_TARGET="${REMOTE_USER}@${REMOTE_HOST}"
}

run_remote_shell() {
  local remote_command="$1"
  ssh -p "$REMOTE_PORT" "$REMOTE_SSH_TARGET" "bash -lc $(printf '%q' "$remote_command")"
}

run_remote_tmux_job() {
  local session_name="$1"
  local remote_command="$2"
  run_remote_shell "
    set -euo pipefail
    if tmux has-session -t \"$session_name\" 2>/dev/null; then
      echo \"tmux session already exists: $session_name\" >&2
      exit 1
    fi
    tmux new-session -d -s \"$session_name\" $(printf '%q' \"$remote_command\")
    echo \"started tmux session: $session_name\"
  "
}

build_remote_checkout_command() {
  local inner_command="$1"
  cat <<EOF
set -euo pipefail
cd $(printf '%q' "$REMOTE_REPO_DIR")
if [[ "$REMOTE_GIT_PULL" == "true" ]]; then
  git pull --ff-only
fi
$inner_command
EOF
}
