#!/usr/bin/env bash

set -euo pipefail

log_note() {
  printf '[dice-randomness] %s\n' "$*" | tee -a "$LOG_FILE"
}

run_logged() {
  log_note "$*"
  "$@" 2>&1 | tee -a "$LOG_FILE"
}
