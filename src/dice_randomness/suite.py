"""Repeated-run GPU audit suites for spotting persistent drift."""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Dict, List, Tuple

from .audit import AuditResult, run_gpu_bucket_stream_audit
from .report import write_artifacts


@dataclass(frozen=True)
class SuiteRunSummary:
    run_index: int
    master_seed: str
    run_dir: str
    total_rolls: int
    total_source_bytes: int
    observed_rejection_rate: float
    max_abs_face_z: float
    max_abs_outcome_z: float
    max_abs_rejected_byte_z: float
    max_outcome_cell: str
    max_outcome_cell_z: float
    outcome_chi_square: float
    outcome_chi_square_reference_mean: int
    outcome_chi_square_p_upper_approx: float


@dataclass(frozen=True)
class GpuSuiteSummary:
    backend: str
    run_count: int
    candidate_bytes_per_run: int
    total_source_bytes: int
    total_rolls: int
    max_abs_outcome_z_across_runs: float
    max_abs_face_z_across_runs: float
    max_abs_rejected_byte_z_across_runs: float
    runs: List[SuiteRunSummary]

    def to_jsonable(self) -> Dict[str, object]:
        return asdict(self)


def run_gpu_bucket_suite(
    runs: int,
    candidate_bytes: int,
    master_seed: str,
    chunk_size: int,
    out_dir: Path,
    plots: bool = True,
) -> GpuSuiteSummary:
    if runs <= 0:
        raise ValueError("runs must be positive")
    if candidate_bytes <= 0:
        raise ValueError("candidate_bytes must be positive")

    out_dir.mkdir(parents=True, exist_ok=True)
    summaries: List[SuiteRunSummary] = []

    for index in range(1, runs + 1):
        run_seed = f"{master_seed}-run-{index:03d}"
        run_dir = out_dir / f"run_{index:03d}"
        result = run_gpu_bucket_stream_audit(
            candidate_bytes=candidate_bytes,
            master_seed=run_seed,
            chunk_size=chunk_size,
        )
        write_artifacts(result, run_dir, plots=plots)
        cell, cell_z = _max_outcome_cell(result)
        summaries.append(
            SuiteRunSummary(
                run_index=index,
                master_seed=run_seed,
                run_dir=str(run_dir),
                total_rolls=result.total_rolls,
                total_source_bytes=result.total_source_bytes,
                observed_rejection_rate=result.observed_rejection_rate,
                max_abs_face_z=result.max_abs_face_z,
                max_abs_outcome_z=result.max_abs_outcome_z,
                max_abs_rejected_byte_z=result.max_abs_rejected_byte_z,
                max_outcome_cell=cell,
                max_outcome_cell_z=cell_z,
                outcome_chi_square=float(result.chi_square_outcomes["statistic"]),
                outcome_chi_square_reference_mean=int(result.chi_square_outcomes["degrees_of_freedom"]),
                outcome_chi_square_p_upper_approx=float(
                    result.chi_square_outcomes["p_value_upper_approx"]
                ),
            )
        )

    suite = GpuSuiteSummary(
        backend="gpu-bucket-stream",
        run_count=runs,
        candidate_bytes_per_run=candidate_bytes,
        total_source_bytes=sum(summary.total_source_bytes for summary in summaries),
        total_rolls=sum(summary.total_rolls for summary in summaries),
        max_abs_outcome_z_across_runs=max(
            (summary.max_abs_outcome_z for summary in summaries),
            default=0.0,
        ),
        max_abs_face_z_across_runs=max(
            (summary.max_abs_face_z for summary in summaries),
            default=0.0,
        ),
        max_abs_rejected_byte_z_across_runs=max(
            (summary.max_abs_rejected_byte_z for summary in summaries),
            default=0.0,
        ),
        runs=summaries,
    )

    _write_suite_artifacts(suite, out_dir)
    return suite


def _max_outcome_cell(result: AuditResult) -> Tuple[str, float]:
    max_cell = "1,1"
    max_value = 0.0
    for row_index, row in enumerate(result.outcome_z_scores, start=1):
        for column_index, z_score in enumerate(row, start=1):
            if abs(z_score) > abs(max_value):
                max_value = z_score
                max_cell = f"{row_index},{column_index}"
    return max_cell, max_value


def _write_suite_artifacts(suite: GpuSuiteSummary, out_dir: Path) -> None:
    with (out_dir / "suite_summary.json").open("w", encoding="utf-8") as file_obj:
        json.dump(suite.to_jsonable(), file_obj, indent=2, sort_keys=True)
        file_obj.write("\n")

    with (out_dir / "suite_summary.csv").open("w", newline="", encoding="utf-8") as file_obj:
        writer = csv.writer(file_obj)
        writer.writerow(
            [
                "run_index",
                "master_seed",
                "run_dir",
                "total_rolls",
                "total_source_bytes",
                "observed_rejection_rate",
                "max_abs_face_z",
                "max_abs_outcome_z",
                "max_abs_rejected_byte_z",
                "max_outcome_cell",
                "max_outcome_cell_z",
                "outcome_chi_square",
                "outcome_chi_square_reference_mean",
                "outcome_chi_square_p_upper_approx",
            ]
        )
        for run in suite.runs:
            writer.writerow(
                [
                    run.run_index,
                    run.master_seed,
                    run.run_dir,
                    run.total_rolls,
                    run.total_source_bytes,
                    f"{run.observed_rejection_rate:.10f}",
                    f"{run.max_abs_face_z:.6f}",
                    f"{run.max_abs_outcome_z:.6f}",
                    f"{run.max_abs_rejected_byte_z:.6f}",
                    run.max_outcome_cell,
                    f"{run.max_outcome_cell_z:.6f}",
                    f"{run.outcome_chi_square:.6f}",
                    run.outcome_chi_square_reference_mean,
                    f"{run.outcome_chi_square_p_upper_approx:.8f}",
                ]
            )

    _write_suite_dashboard_svg(suite, out_dir / "suite_dashboard.svg")
    _write_suite_report(suite, out_dir / "suite_report.md")


def _write_suite_report(suite: GpuSuiteSummary, path: Path) -> None:
    lines = [
        "# GPU Dice Randomness Suite",
        "",
        "This suite repeats the GPU bucket-stream audit with independent seeds.",
        "A single warm-looking cell is not suspicious by itself; repeated drift in the same direction or many runs crossing high z-score thresholds would be more concerning.",
        "",
        f"- runs: `{suite.run_count}`",
        f"- candidate bytes per run: `{suite.candidate_bytes_per_run:,}`",
        f"- total source bytes: `{suite.total_source_bytes:,}`",
        f"- total ordered rolls: `{suite.total_rolls:,}`",
        f"- max absolute outcome z-score across runs: `{suite.max_abs_outcome_z_across_runs:.3f}`",
        f"- max absolute face z-score across runs: `{suite.max_abs_face_z_across_runs:.3f}`",
        f"- max absolute rejected-byte z-score across runs: `{suite.max_abs_rejected_byte_z_across_runs:.3f}`",
        "",
        "![Suite dashboard](suite_dashboard.svg)",
        "",
        "## Runs",
        "",
        "| run | rejection rate | max outcome z | max cell | outcome chi-square | report |",
        "| --- | ---: | ---: | --- | ---: | --- |",
    ]
    for run in suite.runs:
        run_dir_name = Path(run.run_dir).name
        lines.append(
            f"| {run.run_index} | {run.observed_rejection_rate:.6%} | "
            f"{run.max_abs_outcome_z:.3f} | {run.max_outcome_cell} "
            f"({run.max_outcome_cell_z:.3f}) | {run.outcome_chi_square:.3f} | "
            f"[report]({run_dir_name}/report.md) |"
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_suite_dashboard_svg(suite: GpuSuiteSummary, path: Path) -> None:
    width = 1200
    height = 170 + suite.run_count * 54
    row_left = 70
    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        _svg_text(width / 2, 36, "Repeated GPU Bucket Audit Suite", 24, "#111", "middle"),
        _svg_text(
            width / 2,
            72,
            f"{suite.run_count} independent runs, {suite.candidate_bytes_per_run:,} candidate bytes each, {suite.total_rolls:,} ordered rolls total",
            16,
            "#333",
            "middle",
        ),
        _svg_text(row_left, 125, "run", 14, "#333"),
        _svg_text(160, 125, "rejection rate", 14, "#333"),
        _svg_text(360, 125, "max outcome z", 14, "#333"),
        _svg_text(570, 125, "max cell", 14, "#333"),
        _svg_text(740, 125, "chi-square", 14, "#333"),
        _svg_text(940, 125, "read", 14, "#333"),
    ]
    max_z_reference = max(4.0, suite.max_abs_outcome_z_across_runs, 1.0)
    for index, run in enumerate(suite.runs):
        y = 154 + index * 54
        fill = "#f7f7f2" if index % 2 == 0 else "#ffffff"
        elements.append(_svg_rect(row_left - 18, y - 24, 1080, 42, fill, "#e5e5e5"))
        elements.append(_svg_text(row_left, y, str(run.run_index), 15, "#111"))
        elements.append(_svg_text(160, y, f"{run.observed_rejection_rate:.6%}", 15, "#111"))
        bar_width = 160 * (run.max_abs_outcome_z / max_z_reference)
        elements.append(_svg_rect(360, y - 12, 160, 12, "#eeeeee", "none"))
        elements.append(_svg_rect(360, y - 12, bar_width, 12, "#6d597a", "none"))
        elements.append(_svg_text(530, y, f"{run.max_abs_outcome_z:.3f}", 15, "#111"))
        elements.append(_svg_text(570, y, f"{run.max_outcome_cell} ({run.max_outcome_cell_z:.2f})", 15, "#111"))
        elements.append(
            _svg_text(
                740,
                y,
                f"{run.outcome_chi_square:.3f} / mean {run.outcome_chi_square_reference_mean}",
                15,
                "#111",
            )
        )
        elements.append(_svg_text(940, y, f"run_{run.run_index:03d}/report.md", 14, "#333"))
    elements.append("</svg>")
    path.write_text("\n".join(elements), encoding="utf-8")


def _svg_text(x, y, text, size, fill, anchor="start") -> str:
    return (
        f'<text x="{x:.2f}" y="{y:.2f}" fill="{fill}" font-family="Arial, sans-serif" '
        f'font-size="{size}" text-anchor="{anchor}">{text}</text>'
    )


def _svg_rect(x, y, width, height, fill, stroke="#dddddd") -> str:
    return (
        f'<rect x="{x:.2f}" y="{y:.2f}" width="{width:.2f}" height="{height:.2f}" '
        f'fill="{fill}" stroke="{stroke}"/>'
    )
