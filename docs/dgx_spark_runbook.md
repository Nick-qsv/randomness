# DGX Spark Runbook

This mirrors the previous Technical_Monitor handoff pattern: repo-first, local smoke first, then long jobs in `tmux` on the Spark host.

## Host Assumptions

Known prior Spark details, memory-derived and worth rechecking if the network changed:

```text
host: 192.168.0.248
ssh:  w0m85k@spark-29e0
```

## On Spark

Clone or pull this repo on the Spark host, then:

```bash
cd /home/w0m85k/Randomness
PYTHON_BIN=python3.12 ./scripts/spark/bootstrap_checkout.sh
./scripts/docker/check_cuda_host.sh
```

Run exact server-algorithm verification:

```bash
tmux new -s dice-exact
ROLLS=1000000 ./scripts/spark/run_exact_audit.sh
```

Run GPU bucket stress:

```bash
tmux new -s dice-gpu
CANDIDATE_BYTES=1000000000 ./scripts/spark/run_gpu_bucket_audit.sh
```

Scale up after the first artifacts look sane:

```bash
CANDIDATE_BYTES=10000000000 ./scripts/spark/run_gpu_bucket_audit.sh
```

Monitor GPU:

```bash
watch -n 1 nvidia-smi
```

## From The Mac

Create `.remote_spark.env`:

```bash
cp .remote_spark.env.example .remote_spark.env
```

Then run:

```bash
./scripts/remote/run_remote_dice_audit.sh exact
./scripts/remote/run_remote_dice_audit.sh gpu
```

The remote helper starts a detached `tmux` job. SSH into Spark and attach with:

```bash
tmux attach -t dice_exact_audit
tmux attach -t dice_gpu_bucket_audit
```
