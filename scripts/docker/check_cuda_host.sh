#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOG_ROOT="${LOG_ROOT:-$ROOT_DIR/artifacts/setup_logs}"
CUDA_SMOKE_IMAGE="${CUDA_SMOKE_IMAGE:-nvidia/cuda:12.9.0-base-ubuntu22.04}"
RUN_CONTAINER_SMOKE_TEST="${RUN_CONTAINER_SMOKE_TEST:-true}"
TIMESTAMP="$(date +"%Y%m%dT%H%M%S")"
LOG_FILE="$LOG_ROOT/check_cuda_host_$TIMESTAMP.log"

mkdir -p "$LOG_ROOT"
source "$ROOT_DIR/scripts/docker/_logging.sh"

log_note "logging to $LOG_FILE"

run_logged uname -a
run_logged docker version
run_logged docker info --format '{{json .Runtimes}}'

if command -v nvidia-smi >/dev/null 2>&1; then
  run_logged nvidia-smi
else
  log_note "nvidia-smi not found"
fi

if command -v nvidia-ctk >/dev/null 2>&1; then
  run_logged nvidia-ctk --version
else
  log_note "nvidia-ctk not found"
fi

if [[ "$RUN_CONTAINER_SMOKE_TEST" == "true" ]]; then
  log_note "running container GPU smoke test with $CUDA_SMOKE_IMAGE"
  if ! run_logged docker run --rm --gpus all "$CUDA_SMOKE_IMAGE" nvidia-smi; then
    log_note "container GPU smoke test failed; inspect Docker, NVIDIA Container Toolkit, driver, and image access"
  fi
fi
