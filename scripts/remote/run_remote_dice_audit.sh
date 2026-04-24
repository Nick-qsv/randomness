#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$ROOT_DIR/scripts/remote/_common.sh"
load_remote_env

MODE="${1:-exact}"

case "$MODE" in
  exact)
    SESSION_NAME="${REMOTE_TMUX_SESSION:-dice_exact_audit}"
    ROLLS="${REMOTE_EXACT_ROLLS:-1000000}"
    REMOTE_COMMAND="$(build_remote_checkout_command "
      PYTHON_BIN=$(printf '%q' "$REMOTE_PYTHON_BIN") ./scripts/spark/bootstrap_checkout.sh
      ROLLS=$(printf '%q' "$ROLLS") ./scripts/spark/run_exact_audit.sh
    ")"
    ;;
  gpu)
    SESSION_NAME="${REMOTE_TMUX_SESSION:-dice_gpu_bucket_audit}"
    CANDIDATE_BYTES="${REMOTE_GPU_CANDIDATE_BYTES:-1000000000}"
    REMOTE_COMMAND="$(build_remote_checkout_command "
      PYTHON_BIN=$(printf '%q' "$REMOTE_PYTHON_BIN") ./scripts/spark/bootstrap_checkout.sh
      CANDIDATE_BYTES=$(printf '%q' "$CANDIDATE_BYTES") ./scripts/spark/run_gpu_bucket_audit.sh
    ")"
    ;;
  *)
    echo "usage: $0 [exact|gpu]" >&2
    exit 2
    ;;
esac

run_remote_tmux_job "$SESSION_NAME" "$REMOTE_COMMAND"
echo "Attach with:"
echo "  ssh -p $REMOTE_PORT $REMOTE_SSH_TARGET"
echo "  tmux attach -t $SESSION_NAME"
