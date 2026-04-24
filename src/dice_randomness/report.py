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
        diagram_paths = _write_diagrams(result, out_dir)
        plot_paths.update(diagram_paths)
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
            ("Algorithm flow", "algorithm_flow_graphic"),
            ("Audit dashboard", "audit_dashboard_graphic"),
        ]:
            if key in plot_paths:
                filename = Path(plot_paths[key]).name
                lines.extend([f"### {label}", "", f"![{label}]({filename})", ""])

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


def _write_diagrams(result: AuditResult, out_dir: Path) -> Dict[str, str]:
    algorithm_path = out_dir / "algorithm_flow.svg"
    dashboard_path = out_dir / "audit_dashboard.svg"

    _write_algorithm_flow_svg(result, algorithm_path)
    _write_dashboard_svg(result, dashboard_path)

    return {
        "algorithm_flow_graphic": str(algorithm_path),
        "audit_dashboard_graphic": str(dashboard_path),
    }


def _write_algorithm_flow_svg(result: AuditResult, path: Path) -> None:
    width = 1280
    height = 720
    elements = _svg_header(width, height, "Dice Algorithm Flow")

    steps = [
        ("Server seed", "Private 32-byte seed committed by hash"),
        ("Public context", "match id + command id + roll sequence"),
        ("SHA-256 block", "version + seed + context + block index"),
        ("Byte stream", "read digest bytes in order"),
        ("Reject 252-255", "retry until two accepted samples exist"),
        ("Bucket 0-251", "six equal buckets, 42 values each"),
        ("Ordered roll", "first accepted face, second accepted face"),
    ]
    x_positions = [50, 220, 410, 590, 760, 940, 1110]
    y = 170
    box_width = 140
    box_height = 118

    for index, ((title, subtitle), x) in enumerate(zip(steps, x_positions)):
        color = "#f4f1de" if index < 2 else "#e6f2f1"
        if index == 4:
            color = "#f9e6de"
        if index == 6:
            color = "#e7eadf"
        elements.append(_svg_round_rect(x, y, box_width, box_height, color, "#333", 8))
        elements.append(_svg_text(x + box_width / 2, y + 35, title, 16, "#111", "middle"))
        for line_index, line in enumerate(_wrap_words(subtitle, 18)):
            elements.append(
                _svg_text(
                    x + box_width / 2,
                    y + 64 + line_index * 18,
                    line,
                    12,
                    "#333",
                    "middle",
                )
            )
        if index < len(steps) - 1:
            start_x = x + box_width
            end_x = x_positions[index + 1]
            elements.append(_svg_arrow(start_x + 8, y + box_height / 2, end_x - 8, y + box_height / 2))

    bucket_y = 410
    bucket_left = 150
    bucket_width = 700
    bucket_height = 58
    colors = ["#8bb6a3", "#f2cc8f", "#81b29a", "#e07a5f", "#6d597a", "#3d5a80"]
    for index in range(6):
        x = bucket_left + index * bucket_width / 6
        start = index * 42
        end = start + 41
        elements.append(
            _svg_rect(x, bucket_y, bucket_width / 6, bucket_height, colors[index], stroke="#ffffff")
        )
        elements.append(_svg_text(x + bucket_width / 12, bucket_y + 24, f"face {index + 1}", 14, "#111", "middle"))
        elements.append(_svg_text(x + bucket_width / 12, bucket_y + 44, f"{start}-{end}", 12, "#111", "middle"))

    rejected_x = bucket_left + bucket_width + 36
    elements.append(_svg_round_rect(rejected_x, bucket_y, 180, bucket_height, "#f5c2aa", "#7b3324", 8))
    elements.append(_svg_text(rejected_x + 90, bucket_y + 25, "reject", 15, "#111", "middle"))
    elements.append(_svg_text(rejected_x + 90, bucket_y + 45, "252-255", 13, "#111", "middle"))

    elements.append(
        _svg_text(
            width / 2,
            540,
            "No-bias proof: 252 accepted byte values / 6 faces = 42 values per face",
            22,
            "#111",
            "middle",
        )
    )
    elements.append(
        _svg_text(
            width / 2,
            590,
            f"This run: {result.total_source_bytes:,} source bytes, {result.rejected_sample_count:,} rejected, {result.total_rolls:,} ordered rolls counted",
            17,
            "#333",
            "middle",
        )
    )
    elements.append("</svg>")
    path.write_text("\n".join(elements), encoding="utf-8")


def _write_dashboard_svg(result: AuditResult, path: Path) -> None:
    width = 1280
    height = 760
    elements = _svg_header(width, height, "Dice Randomness Audit Dashboard")
    verdict = _verdict(result)
    expected_reject_pct = result.expected_rejection_rate * 100.0
    observed_reject_pct = result.observed_rejection_rate * 100.0
    max_z = max(result.max_abs_face_z, result.max_abs_outcome_z, result.max_abs_rejected_byte_z)

    elements.append(_svg_round_rect(52, 70, 1176, 90, "#f7f7f2", "#333", 8))
    elements.append(_svg_text(82, 108, f"Verdict: {verdict}", 24, "#111"))
    elements.append(_svg_text(82, 140, f"Backend: {result.config.backend}", 16, "#333"))
    elements.append(_svg_text(440, 140, f"Rolls counted: {result.total_rolls:,}", 16, "#333"))
    elements.append(_svg_text(760, 140, f"Source bytes: {result.total_source_bytes:,}", 16, "#333"))

    _dashboard_metric(
        elements,
        52,
        205,
        "Rejection rate",
        observed_reject_pct,
        expected_reject_pct,
        "%",
        "#2f6f73",
    )
    _dashboard_metric(
        elements,
        472,
        205,
        "Max z-score",
        max_z,
        6.0,
        "",
        "#6d597a",
    )
    _dashboard_metric(
        elements,
        892,
        205,
        "Outcome chi-square",
        float(result.chi_square_outcomes["statistic"]),
        float(result.chi_square_outcomes["degrees_of_freedom"]),
        "",
        "#8a5a44",
    )

    face_left = 70
    face_top = 365
    face_chart_width = 520
    face_chart_height = 250
    expected_face = result.total_dice / 6.0 if result.total_dice else 0.0
    max_face = max(max(result.face_counts, default=0), expected_face, 1.0)
    elements.append(_svg_text(face_left, face_top - 22, "Face counts vs expected", 18, "#111"))
    expected_y = face_top + face_chart_height - (expected_face / max_face) * face_chart_height
    elements.append(_svg_line(face_left, expected_y, face_left + face_chart_width, expected_y, "#c44e52", 2.5))
    for index, count in enumerate(result.face_counts):
        bar_width = 56
        gap = 34
        x = face_left + index * (bar_width + gap)
        bar_height = (count / max_face) * face_chart_height
        y = face_top + face_chart_height - bar_height
        elements.append(_svg_rect(x, y, bar_width, bar_height, "#2f6f73"))
        elements.append(_svg_text(x + bar_width / 2, face_top + face_chart_height + 28, str(index + 1), 14, "#111", "middle"))
    elements.extend(_svg_axes(face_left, face_top, face_chart_width, face_chart_height, "face", "count"))

    heat_left = 720
    heat_top = 340
    cell = 55
    elements.append(_svg_text(heat_left, heat_top - 22, "Ordered outcome z-scores", 18, "#111"))
    for row_index, row in enumerate(result.outcome_z_scores):
        for column_index, z_score in enumerate(row):
            x = heat_left + column_index * cell
            y = heat_top + row_index * cell
            elements.append(_svg_rect(x, y, cell, cell, _z_color(z_score), stroke="#ffffff"))
            elements.append(_svg_text(x + cell / 2, y + cell / 2 + 5, f"{z_score:.1f}", 12, "#111", "middle"))
    for index in range(6):
        elements.append(_svg_text(heat_left + index * cell + cell / 2, heat_top - 8, str(index + 1), 12, "#333", "middle"))
        elements.append(_svg_text(heat_left - 15, heat_top + index * cell + cell / 2 + 5, str(index + 1), 12, "#333", "middle"))

    elements.append(
        _svg_text(
            width / 2,
            705,
            "Interpretation: random runs should wobble around expected values; large, repeated z-score drift is the warning sign.",
            18,
            "#333",
            "middle",
        )
    )
    elements.append("</svg>")
    path.write_text("\n".join(elements), encoding="utf-8")


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


def _svg_round_rect(x, y, width, height, fill, stroke, radius) -> str:
    return (
        f'<rect x="{x:.2f}" y="{y:.2f}" width="{width:.2f}" height="{height:.2f}" '
        f'rx="{radius:.2f}" ry="{radius:.2f}" fill="{fill}" stroke="{stroke}"/>'
    )


def _svg_arrow(x1, y1, x2, y2) -> str:
    return "\n".join(
        [
            f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
            'stroke="#333" stroke-width="2"/>',
            f'<polygon points="{x2:.2f},{y2:.2f} {x2 - 10:.2f},{y2 - 6:.2f} '
            f'{x2 - 10:.2f},{y2 + 6:.2f}" fill="#333"/>',
        ]
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


def _wrap_words(text: str, max_chars: int) -> List[str]:
    lines: List[str] = []
    current = ""
    for word in text.split():
        proposed = word if not current else f"{current} {word}"
        if len(proposed) > max_chars and current:
            lines.append(current)
            current = word
        else:
            current = proposed
    if current:
        lines.append(current)
    return lines


def _dashboard_metric(
    elements: List[str],
    x: float,
    y: float,
    label: str,
    observed: float,
    expected: float,
    unit: str,
    color: str,
) -> None:
    width = 336
    height = 98
    elements.append(_svg_round_rect(x, y, width, height, "#ffffff", "#d8d8d8", 8))
    elements.append(_svg_text(x + 18, y + 30, label, 16, "#111"))
    elements.append(_svg_text(x + 18, y + 63, f"{observed:.4f}{unit}", 27, color))
    elements.append(_svg_text(x + 190, y + 63, f"expected {expected:.4f}{unit}", 14, "#555"))

    bar_x = x + 18
    bar_y = y + 78
    bar_width = width - 36
    max_value = max(observed, expected, 1.0)
    expected_x = bar_x + (expected / max_value) * bar_width
    observed_width = (observed / max_value) * bar_width
    elements.append(_svg_rect(bar_x, bar_y, bar_width, 8, "#eeeeee"))
    elements.append(_svg_rect(bar_x, bar_y, observed_width, 8, color))
    elements.append(_svg_line(expected_x, bar_y - 4, expected_x, bar_y + 12, "#c44e52", 2))
