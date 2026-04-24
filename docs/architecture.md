# Architecture

## What We Verify

The production dice algorithm is a rejection sampler over SHA-256 bytes:

```text
accepted bytes: 0..251
rejected bytes: 252..255
face 1:   0..41
face 2:  42..83
face 3:  84..125
face 4: 126..167
face 5: 168..209
face 6: 210..251
```

Because each face owns exactly 42 accepted byte values, the byte-to-face mapping is unbiased if the input bytes are uniform.

## Tool Layers

The repo has three layers:

1. `dice_randomness.algorithm`

   A direct Python mirror of `bgb_vos_v1/src/match_authority/dice.rs`. It can create and verify roll proofs from a seed and public context.

2. `dice_randomness.audit`

   Monte Carlo counters and statistical summaries. This produces face counts, ordered outcome counts, rejected-byte counts, chi-square values, and z-scores.

3. `dice_randomness.report`

   Static audit artifacts: JSON, CSV, Markdown explanations, and PNG plots.

## Backends

### `exact-cpu`

This backend is canonical. It runs the exact SHA-256 rejection sampler and saves sampled proof rows that can be replayed later. Use it to prove the Python verifier matches the server contract.

### `gpu-bucket-stream`

This backend uses CuPy to generate a very large byte stream on the DGX Spark, rejects `252..255`, maps accepted bytes into faces, and pairs accepted faces into ordered outcomes. It is a high-throughput stress check of the bucket/rejection rule, not a SHA-256 implementation.

That distinction matters. The math guarantee is the bucket split. The exact backend checks the server algorithm. The GPU backend makes giant visual distribution artifacts quickly.

### Future `exact-cuda-sha256`

If we later need billions of exact seeded SHA-256 proofs on GPU, the next backend should be a CUDA kernel that implements the same message construction as `dice.rs`. The rest of this repo should not need to change; it already expects backends to return the same count/result shape.

## Report Interpretation

The report looks for:

- each face near `total_dice / 6`
- each ordered outcome near `total_rolls / 36`
- observed rejection rate near `4 / 256 = 1.5625%`
- no large unexplained z-score drift
- exact sampled receipts that verify deterministically

Large runs will always have some nonzero z-scores. A single maximum z-score is a screening signal, not a proof of failure. Reproducibility and repeated runs matter more than one isolated number.
