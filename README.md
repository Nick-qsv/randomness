# Dice Randomness Audit

This repo verifies and explains the current VR Gammon dice algorithm from:

- `/Users/w0m/Desktop/2026/VR_Gammon/bgb_vos_v1/src/match_authority/dice.rs`

The canonical algorithm is `server_seeded_rejection_sha256_v1`:

1. Hash `algorithm_version`, server seed, public context, and block index with SHA-256.
2. Read digest bytes in order.
3. Reject byte values `252..255`.
4. Map the accepted byte range `0..251` into six equal buckets of 42 values.
5. Use the first two accepted samples as an ordered dice roll.

The important no-bias fact is simple:

```text
252 accepted byte values / 6 faces = 42 byte values per face
```

The Monte Carlo tooling here is for regression detection, confidence, and public-facing audit artifacts. It does not replace the bucket proof.

## Backends

`exact-cpu` mirrors `dice.rs` exactly in Python. Use this for replayable seeded roll proofs, sampled receipts, and implementation regression checks.

`gpu-bucket-stream` uses CuPy on the DGX Spark to stress the rejection bucket rule across very large byte streams. It is intentionally labeled separately because it tests the `252 -> 6 x 42` mapping at GPU scale, not SHA-256 itself.

The architecture leaves room for a later `exact-cuda-sha256` backend if we decide we need billions of full SHA-256 roll proofs on GPU.

## Local Quick Start

The exact verifier has no runtime dependencies:

```bash
PYTHONPATH=src python3 -m dice_randomness.cli audit \
  --backend exact-cpu \
  --rolls 10000 \
  --out-dir artifacts/dice_bias/local_exact_10k \
  --no-plots
```

For visual reports:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[viz]"

dice-randomness audit \
  --backend exact-cpu \
  --rolls 100000 \
  --out-dir artifacts/dice_bias/local_exact_100k
```

Open the generated report:

```text
artifacts/dice_bias/local_exact_100k/report.md
```

## DGX Spark Run Shape

On the Spark host:

```bash
PYTHON_BIN=python3.12 ./scripts/spark/bootstrap_checkout.sh

ROLLS=1000000 ./scripts/spark/run_exact_audit.sh
CANDIDATE_BYTES=1000000000 ./scripts/spark/run_gpu_bucket_audit.sh
RUNS=5 CANDIDATE_BYTES=1000000000 ./scripts/spark/run_gpu_bucket_suite.sh
```

The exact run creates replayable proof samples. The GPU run creates high-volume distribution plots for the bucket/rejection layer.
The GPU suite repeats independent bucket runs and writes `suite_report.md` plus `suite_dashboard.svg`, which is the better way to check whether a warm heatmap cell repeats or wanders around.

## Remote Mac-to-Spark Shape

Create a local `.remote_spark.env` from `.remote_spark.env.example`, then:

```bash
./scripts/remote/run_remote_dice_audit.sh exact
./scripts/remote/run_remote_dice_audit.sh gpu
```

This follows the previous Technical_Monitor pattern: keep the repo as the source of truth, run the heavy job inside `tmux` on the Spark host, and save artifacts inside the Spark checkout.
