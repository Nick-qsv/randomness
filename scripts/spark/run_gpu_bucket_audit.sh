#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"
PYTHON_BIN="${PYTHON_BIN:-$VENV_DIR/bin/python}"
CANDIDATE_BYTES="${CANDIDATE_BYTES:-1000000000}"
CHUNK_SIZE="${CHUNK_SIZE:-100000000}"
RUN_ID="${RUN_ID:-gpu_bucket_${CANDIDATE_BYTES}_$(date +"%Y%m%dT%H%M%S")}"
OUT_DIR="${OUT_DIR:-$ROOT_DIR/artifacts/dice_bias/$RUN_ID}"

cd "$ROOT_DIR"
"$PYTHON_BIN" -m dice_randomness.cli audit \
  --backend gpu-bucket-stream \
  --candidate-bytes "$CANDIDATE_BYTES" \
  --chunk-size "$CHUNK_SIZE" \
  --out-dir "$OUT_DIR"
