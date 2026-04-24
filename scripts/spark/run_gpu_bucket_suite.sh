#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"
PYTHON_BIN="${PYTHON_BIN:-$VENV_DIR/bin/python}"
RUNS="${RUNS:-5}"
CANDIDATE_BYTES="${CANDIDATE_BYTES:-1000000000}"
CHUNK_SIZE="${CHUNK_SIZE:-100000000}"
MASTER_SEED="${MASTER_SEED:-dice-randomness-gpu-suite-2026-04-24}"
RUN_ID="${RUN_ID:-gpu_suite_${RUNS}x${CANDIDATE_BYTES}_$(date +"%Y%m%dT%H%M%S")}"
OUT_DIR="${OUT_DIR:-$ROOT_DIR/artifacts/dice_bias/$RUN_ID}"

cd "$ROOT_DIR"
"$PYTHON_BIN" -m dice_randomness.cli gpu-suite \
  --runs "$RUNS" \
  --candidate-bytes "$CANDIDATE_BYTES" \
  --chunk-size "$CHUNK_SIZE" \
  --master-seed "$MASTER_SEED" \
  --out-dir "$OUT_DIR"
