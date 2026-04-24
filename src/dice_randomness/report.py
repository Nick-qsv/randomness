"""Artifact writers for dice audit results."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, List

from .audit import AuditResult


def write_artifacts(result: AuditResult, out_dir: Path, plots: bool = True) -> Dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "json": str(out_dir / "audit.json"),
        "face_counts_csv": str(out_dir / "face_counts.csv"),
        "outcome_counts_csv": str(out_dir / "outcome_counts.csv"),
        "rejected_bytes_csv": str(out_dir / "rejected_bytes.csv"),
        "report_md": str(out_dir / "report.md"),
    }

    with (out_dir / "audit.json").open("w", encoding="utf-8") as file_obj:
        json.dump(result.to_jsonable(), file_obj, indent=2, sort_keys=True)
        file_obj.write("\n")

    _write_face_counts(result, out_dir / "face_counts.csv")
    _write_outcome_counts(result, out_dir / "outcome_counts.csv")
    _write_rejected_bytes(result, out_dir / "rejected_bytes.csv")

    plot_paths: Dict[str, str] = {}
    if plots:
        plot_paths = _write_plots(result, out_dir)
        paths.update(plot_paths)

    _write_markdown_report(result, out_dir / "report.md", plot_paths)
    return paths


def _write_face_counts(result: AuditResult, path: Path) -> None:
    expected = result.total_dice / 6.0 if result.total_dice else 0.0
    with path.open("w", newline="", encoding="utf-8") as file_obj:
        writer = csv.writer(file_obj)
        writer.writerow(["face", "observed", "expected", "z_score"])
        for index, observed in enumerate(result.face_counts, start=1):
            writer.writerow([index, observed, f"{expected:.6f}", f"{result.face_z_scores[index - 1]:.6f}"])


def _write_outcome_counts(result: AuditResult, path: Path) -> None:
    expected = result.total_rolls / 36.0 if result.total_rolls else 0.0
    with path.open("w", newline="", encoding="utf-8") as file_obj:
        writer = csv.writer(file_obj)
        writer.writerow(["die_1", "die_2", "observed", "expected", "z_score"])
        for row_index, row in enumerate(result.outcome_counts, start=1):
            for column_index, observed in enumerate(row, start=1):
                writer.writerow(
                    [
                        row_index,
                        column_index,
                        observed,
                        f"{expected:.6f}",
                        f"{result.outcome_z_scores[row_index - 1][column_index - 1]:.6f}",
                    ]
                )


def _write_rejected_bytes(result: AuditResult, path: Path) -> None:
    expected = result.total_source_bytes / 256.0 if result.total_source_bytes else 0.0
    with path.open("w", newline="", encoding="utf-8") as file_obj:
        writer = csv.writer(file_obj)
        writer.writerow(["byte_value", "observed", "expected", "z_score"])
        for value in ("252", "253", "254", "255"):
            writer.writerow(
                [
                    value,
                    result.rejected_byte_counts[value],
                    f"{expected:.6f}",
                    f"{result.rejected_byte_z_scores[value]:.6f}",
                ]
            )


def _write_plots(result: AuditResult, out_dir: Path) -> Dict[str, str]:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        return _write_svg_plots(result, out_dir)

    face_path = out_dir / "face_counts.png"
    outcome_path = out_dir / "outcome_z_heatmap.png"
    rejection_path = out_dir / "rejected_bytes.png"

    _plot_faces(result, face_path, plt)
    _plot_outcomes(result, outcome_path, plt)
    _plot_rejections(result, rejection_path, plt)

    return {
        "face_counts_graphic": str(face_path),
        "outcome_z_heatmap_graphic": str(outcome_path),
        "rejected_bytes_graphic": str(rejection_path),
    }


def _plot_faces(result: AuditResult, path: Path, plt) -> None:
    expected = result.total_dice / 6.0 if result.total_dice else 0.0
    faces = list(range(1, 7))
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(faces, result.face_counts, color="#2f6f73")
    ax.axhline(expected, color="#c44e52", linewidth=2, label="expected")
    ax.set_title("Die Face Counts")
    ax.set_xlabel("Face")
    ax.set_ylabel("Observed count")
    ax.set_xticks(faces)
    ax.legend()
    for face, count, z_score in zip(faces, result.face_counts, result.face_z_scores):
        ax.text(face, count, f"z={z_score:.2f}", ha="center", va="bottom", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plot_outcomes(result: AuditResult, path: Path, plt) -> None:
    fig, ax = plt.subplots(figsize=(7, 6))
    heatmap = ax.imshow(result.outcome_z_scores, cmap="coolwarm", vmin=-4, vmax=4)
    ax.set_title("Ordered Outcome Z-Scores")
    ax.set_xlabel("Die 2")
    ax.set_ylabel("Die 1")
    ax.set_xticks(list(range(6)))
    ax.set_yticks(list(range(6)))
    ax.set_xticklabels([str(value) for value in range(1, 7)])
    ax.set_yticklabels([str(value) for value in range(1, 7)])
    for row_index, row in enumerate(result.outcome_z_scores):
        for column_index, z_score in enumerate(row):
            ax.text(column_index, row_index, f"{z_score:.1f}", ha="center", va="center", fontsize=8)
    fig.colorbar(heatmap, ax=ax, label="z-score")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plot_rejections(result: AuditResult, path: Path, plt) -> None:
    values = ["252", "253", "254", "255"]
    observed = [result.rejected_byte_counts[value] for value in values]
    expected = result.total_source_bytes / 256.0 if result.total_source_bytes else 0.0
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.bar(values, observed, color="#8a5a44")
    ax.axhline(expected, color="#c44e52", linewidth=2, label="expected per byte")
    ax.set_title("Rejected Byte Counts")
    ax.set_xlabel("Rejected byte value")
    ax.set_ylabel("Observed count")
    ax.legend()
    for value, count in zip(values, observed):
        ax.text(value, count, f"z={result.rejected_byte_z_scores[value]:.2f}", ha="center", va="bottom", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _write_markdown_report(result: AuditResult, path: Path, plot_paths: Dict[str, str]) -> None:
    verdict = _verdict(result)
    lines: List[str] = [
        "# Dice Randomness Audit Report",
        "",
        f"Verdict: **{verdict}**",
        "",
        "## Scope",
        "",
        f"- backend: `{result.config.backend}`",
        f"- algorithm version: `{result.algorithm_version}`",
        f"- generated at: `{result.generated_at}`",
        f"- git commit: `{result.git_commit}`",
        f"- git dirty: `{result.git_dirty}`",
        "",
        "## What This Checks",
        "",
        "The dice algorithm rejects byte values `252..255` and maps `0..251` into six equal buckets.",
        "That means each face owns exactly 42 source byte values. The statistical run checks whether the observed sample behaves like that contract.",
        "",
        "## Headline Numbers",
        "",
        f"- rolls counted: `{result.total_rolls:,}`",
        f"- dice counted: `{result.total_dice:,}`",
        f"- source bytes inspected: `{result.total_source_bytes:,}`",
        f"- rejected source bytes: `{result.rejected_sample_count:,}`",
        f"- observed rejection rate: `{result.observed_rejection_rate:.6%}`",
        f"- expected rejection rate: `{result.expected_rejection_rate:.6%}`",
        f"- face chi-square: `{result.chi_square_faces['statistic']:.4f}` with df `{result.chi_square_faces['degrees_of_freedom']}`",
        f"- outcome chi-square: `{result.chi_square_outcomes['statistic']:.4f}` with df `{result.chi_square_outcomes['degrees_of_freedom']}`",
        f"- max absolute face z-score: `{result.max_abs_face_z:.3f}`",
        f"- max absolute ordered-outcome z-score: `{result.max_abs_outcome_z:.3f}`",
        f"- max absolute rejected-byte z-score: `{result.max_abs_rejected_byte_z:.3f}`",
        "",
        "## Notes",
        "",
    ]
    lines.extend(f"- {note}" for note in result.notes)
    lines.extend(
        [
            "",
            "## Visuals",
            "",
        ]
    )

    if plot_paths:
        for label, key in [
            ("Face counts", "face_counts_graphic"),
            ("Ordered outcome z-score heatmap", "outcome_z_heatmap_graphic"),
            ("Rejected byte counts", "rejected_bytes_graphic"),
        ]:
            if key in plot_paths:
                filename = Path(plot_paths[key]).name
                lines.extend([f"### {label}", "", f"![{label}]({filename})", ""])
    else:
        lines.append("Plots were not generated for this run.")
        lines.append("")

    lines.extend(
        [
            "## Audit Files",
            "",
            "- `audit.json`: complete machine-readable summary",
            "- `face_counts.csv`: face count table",
            "- `outcome_counts.csv`: ordered two-die outcome table",
            "- `rejected_bytes.csv`: rejected byte table",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _verdict(result: AuditResult) -> str:
    if result.max_abs_face_z > 6.0 or result.max_abs_outcome_z > 6.0 or result.max_abs_rejected_byte_z > 6.0:
        return "review recommended"
    return "no obvious distribution anomaly in this run"


def _write_svg_plots(result: AuditResult, out_dir: Path) -> Dict[str, str]:
    face_path = out_dir / "face_counts.svg"
    outcome_path = out_dir / "outcome_z_heatmap.svg"
    rejection_path = out_dir / "rejected_bytes.svg"

    _write_face_svg(result, face_path)
    _write_outcome_svg(result, outcome_path)
    _write_rejection_svg(result, rejection_path)

    return {
        "face_counts_graphic": str(face_path),
        "outcome_z_heatmap_graphic": str(outcome_path),
        "rejected_bytes_graphic": str(rejection_path),
    }


def _write_face_svg(result: AuditResult, path: Path) -> None:
    width = 900
    height = 520
    left = 70
    top = 60
    chart_width = 760
    chart_height = 340
    expected = result.total_dice / 6.0 if result.total_dice else 0.0
    max_value = max(max(result.face_counts, default=0), expected, 1.0)
    bar_gap = 28
    bar_width = (chart_width - bar_gap * 5) / 6
    expected_y = top + chart_height - (expected / max_value) * chart_height

    elements = _svg_header(width, height, "Die Face Counts")
    elements.append(_svg_line(left, expected_y, left + chart_width, expected_y, "#c44e52", 3))
    elements.append(_svg_text(left + chart_width + 8, expected_y + 5, "expected", 13, "#5f1f1f"))
    for index, count in enumerate(result.face_counts):
        x = left + index * (bar_width + bar_gap)
        bar_height = (count / max_value) * chart_height
        y = top + chart_height - bar_height
        elements.append(_svg_rect(x, y, bar_width, bar_height, "#2f6f73"))
        elements.append(_svg_text(x + bar_width / 2, top + chart_height + 35, str(index + 1), 16, "#222", "middle"))
        elements.append(_svg_text(x + bar_width / 2, y - 8, f"z={result.face_z_scores[index]:.2f}", 12, "#222", "middle"))
    elements.extend(_svg_axes(left, top, chart_width, chart_height, "Face", "Observed count"))
    elements.append("</svg>")
    path.write_text("\n".join(elements), encoding="utf-8")


def _write_outcome_svg(result: AuditResult, path: Path) -> None:
    width = 760
    height = 700
    left = 110
    top = 80
    cell = 82
    elements = _svg_header(width, height, "Ordered Outcome Z-Scores")
    for row_index, row in enumerate(result.outcome_z_scores):
        for column_index, z_score in enumerate(row):
            x = left + column_index * cell
            y = top + row_index * cell
            elements.append(_svg_rect(x, y, cell, cell, _z_color(z_score), stroke="#ffffff"))
            elements.append(_svg_text(x + cell / 2, y + cell / 2 + 5, f"{z_score:.1f}", 16, "#111", "middle"))
    for index in range(6):
        elements.append(_svg_text(left + index * cell + cell / 2, top - 18, str(index + 1), 16, "#222", "middle"))
        elements.append(_svg_text(left - 24, top + index * cell + cell / 2 + 5, str(index + 1), 16, "#222", "middle"))
    elements.append(_svg_text(left + cell * 3, top + cell * 6 + 48, "Die 2", 17, "#222", "middle"))
    elements.append(_svg_text(38, top + cell * 3, "Die 1", 17, "#222", "middle", rotate=-90))
    elements.append("</svg>")
    path.write_text("\n".join(elements), encoding="utf-8")


def _write_rejection_svg(result: AuditResult, path: Path) -> None:
    width = 820
    height = 500
    left = 80
    top = 60
    chart_width = 660
    chart_height = 320
    values = ["252", "253", "254", "255"]
    observed = [result.rejected_byte_counts[value] for value in values]
    expected = result.total_source_bytes / 256.0 if result.total_source_bytes else 0.0
    max_value = max(max(observed, default=0), expected, 1.0)
    bar_gap = 52
    bar_width = (chart_width - bar_gap * 3) / 4
    expected_y = top + chart_height - (expected / max_value) * chart_height

    elements = _svg_header(width, height, "Rejected Byte Counts")
    elements.append(_svg_line(left, expected_y, left + chart_width, expected_y, "#c44e52", 3))
    elements.append(_svg_text(left + chart_width + 8, expected_y + 5, "expected", 13, "#5f1f1f"))
    for index, value in enumerate(values):
        count = observed[index]
        x = left + index * (bar_width + bar_gap)
        bar_height = (count / max_value) * chart_height
        y = top + chart_height - bar_height
        elements.append(_svg_rect(x, y, bar_width, bar_height, "#8a5a44"))
        elements.append(_svg_text(x + bar_width / 2, top + chart_height + 35, value, 16, "#222", "middle"))
        elements.append(_svg_text(x + bar_width / 2, y - 8, f"z={result.rejected_byte_z_scores[value]:.2f}", 12, "#222", "middle"))
    elements.extend(_svg_axes(left, top, chart_width, chart_height, "Rejected byte", "Observed count"))
    elements.append("</svg>")
    path.write_text("\n".join(elements), encoding="utf-8")


def _svg_header(width: int, height: int, title: str) -> List[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        _svg_text(width / 2, 34, title, 22, "#111", "middle"),
    ]


def _svg_axes(left: float, top: float, width: float, height: float, x_label: str, y_label: str) -> List[str]:
    return [
        _svg_line(left, top + height, left + width, top + height, "#222", 1.5),
        _svg_line(left, top, left, top + height, "#222", 1.5),
        _svg_text(left + width / 2, top + height + 76, x_label, 16, "#222", "middle"),
        _svg_text(24, top + height / 2, y_label, 16, "#222", "middle", rotate=-90),
    ]


def _svg_rect(x, y, width, height, fill, stroke="none") -> str:
    return (
        f'<rect x="{x:.2f}" y="{y:.2f}" width="{width:.2f}" height="{height:.2f}" '
        f'fill="{fill}" stroke="{stroke}"/>'
    )


def _svg_line(x1, y1, x2, y2, stroke, stroke_width) -> str:
    return (
        f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
        f'stroke="{stroke}" stroke-width="{stroke_width}"/>'
    )


def _svg_text(x, y, text, size, fill, anchor="start", rotate=None) -> str:
    transform = f' transform="rotate({rotate} {x:.2f} {y:.2f})"' if rotate is not None else ""
    return (
        f'<text x="{x:.2f}" y="{y:.2f}" fill="{fill}" font-family="Arial, sans-serif" '
        f'font-size="{size}" text-anchor="{anchor}"{transform}>{text}</text>'
    )


def _z_color(z_score: float) -> str:
    clipped = max(-4.0, min(4.0, z_score)) / 4.0
    if clipped >= 0:
        return _interpolate_color((248, 248, 248), (192, 67, 62), clipped)
    return _interpolate_color((248, 248, 248), (47, 111, 115), abs(clipped))


def _interpolate_color(start, end, amount: float) -> str:
    channels = [
        int(round(start[index] + (end[index] - start[index]) * amount))
        for index in range(3)
    ]
    return "#{:02x}{:02x}{:02x}".format(*channels)
