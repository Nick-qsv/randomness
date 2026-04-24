"""Command-line interface for dice randomness audits."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .audit import run_exact_cpu_audit, run_gpu_bucket_stream_audit
from .report import write_artifacts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dice-randomness",
        description="Audit and visualize the VR Gammon SHA-256 rejection-sampling dice algorithm.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit = subparsers.add_parser("audit", help="run an audit and write JSON/CSV/Markdown artifacts")
    audit.add_argument("--backend", choices=("exact-cpu", "gpu-bucket-stream"), default="exact-cpu")
    audit.add_argument("--rolls", type=int, default=100_000, help="roll count for exact-cpu")
    audit.add_argument(
        "--candidate-bytes",
        type=int,
        default=1_000_000_000,
        help="candidate byte count for gpu-bucket-stream",
    )
    audit.add_argument("--chunk-size", type=int, default=100_000_000, help="GPU chunk size")
    audit.add_argument("--master-seed", default="dice-randomness-audit-2026-04-24")
    audit.add_argument("--start-sequence", type=int, default=0)
    audit.add_argument("--match-id", default="dice-randomness-audit")
    audit.add_argument("--command-prefix", default="audit-roll")
    audit.add_argument("--workers", type=int, default=1)
    audit.add_argument("--sample-receipts", type=int, default=8)
    audit.add_argument("--out-dir", type=Path, required=True)
    audit.add_argument("--no-plots", action="store_true", help="skip matplotlib PNG generation")
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "audit":
        if args.backend == "exact-cpu":
            result = run_exact_cpu_audit(
                rolls=args.rolls,
                master_seed=args.master_seed,
                start_sequence=args.start_sequence,
                match_id=args.match_id,
                command_prefix=args.command_prefix,
                workers=args.workers,
                sample_receipts=args.sample_receipts,
            )
        elif args.backend == "gpu-bucket-stream":
            result = run_gpu_bucket_stream_audit(
                candidate_bytes=args.candidate_bytes,
                master_seed=args.master_seed,
                chunk_size=args.chunk_size,
            )
        else:
            parser.error(f"unsupported backend: {args.backend}")

        paths = write_artifacts(result, args.out_dir, plots=not args.no_plots)
        print(f"wrote audit artifacts to {args.out_dir}")
        for label, path in sorted(paths.items()):
            print(f"  {label}: {path}")
        return 0

    parser.error("missing command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
