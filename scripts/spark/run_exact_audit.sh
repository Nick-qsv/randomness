#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"
PYTHON_BIN="${PYTHON_BIN:-$VENV_DIR/bin/python}"
ROLLS="${ROLLS:-1000000}"
WORKERS="${WORKERS:-$(python3 -c 'import os; print(max(1, min(os.cpu_count() or 1, 16)))')}"
RUN_ID="${RUN_ID:-exact_cpu_${ROLLS}_$(date +"%Y%m%dT%H%M%S")}"
OUT_DIR="${OUT_DIR:-$ROOT_DIR/artifacts/dice_bias/$RUN_ID}"

cd "$ROOT_DIR"
"$PYTHON_BIN" -m dice_randomness.cli audit \
  --backend exact-cpu \
  --rolls "$ROLLS" \
  --workers "$WORKERS" \
  --out-dir "$OUT_DIR"
