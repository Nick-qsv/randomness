#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3.12}"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python interpreter not found: $PYTHON_BIN" >&2
  exit 1
fi

PYTHON_VERSION="$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")')"
if ! "$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)'; then
  echo "dice-randomness-audit requires Python 3.9+; found $PYTHON_VERSION via $PYTHON_BIN" >&2
  exit 1
fi

echo "Bootstrapping checkout at: $ROOT_DIR"
echo "Using Python: $PYTHON_BIN ($PYTHON_VERSION)"
"$PYTHON_BIN" -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -e ".[all]"

cat <<EOF

Bootstrap complete.

Next steps:
  ./scripts/docker/check_cuda_host.sh
  ROLLS=1000000 ./scripts/spark/run_exact_audit.sh
  CANDIDATE_BYTES=1000000000 ./scripts/spark/run_gpu_bucket_audit.sh

EOF
