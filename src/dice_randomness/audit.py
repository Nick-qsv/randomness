"""Audit runners for the dice algorithm and bucket mapping."""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
import subprocess
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .algorithm import (
    ACCEPTED_VALUE_COUNT,
    DICE_ALGORITHM_VERSION,
    REJECTED_VALUES,
    SOURCE_VALUE_COUNT,
    derive_audit_seed,
    dice_public_context,
    roll_proof_and_rejected_value_counts,
)
from .stats import chi_square_uniform, max_abs, z_scores_for_cells


@dataclass(frozen=True)
class AuditConfig:
    backend: str
    rolls: int
    candidate_bytes: Optional[int]
    master_seed: str
    start_sequence: int
    match_id: str
    command_prefix: str
    workers: int
    sample_receipts: int

    def to_jsonable(self):
        return asdict(self)


@dataclass(frozen=True)
class AuditResult:
    config: AuditConfig
    generated_at: str
    algorithm_version: str
    git_commit: str
    git_dirty: bool
    face_counts: List[int]
    outcome_counts: List[List[int]]
    rejected_byte_counts: Dict[str, int]
    total_rolls: int
    total_dice: int
    total_source_bytes: int
    rejected_sample_count: int
    observed_rejection_rate: float
    expected_rejection_rate: float
    chi_square_faces: Dict[str, object]
    chi_square_outcomes: Dict[str, object]
    face_z_scores: List[float]
    outcome_z_scores: List[List[float]]
    rejected_byte_z_scores: Dict[str, float]
    max_abs_face_z: float
    max_abs_outcome_z: float
    max_abs_rejected_byte_z: float
    sample_proofs: List[Dict[str, object]]
    notes: List[str]

    def to_jsonable(self) -> Dict[str, object]:
        return asdict(self)


def run_exact_cpu_audit(
    rolls: int,
    master_seed: str,
    start_sequence: int = 0,
    match_id: str = "dice-randomness-audit",
    command_prefix: str = "audit-roll",
    workers: int = 1,
    sample_receipts: int = 8,
) -> AuditResult:
    if rolls <= 0:
        raise ValueError("rolls must be positive")
    if workers <= 0:
        raise ValueError("workers must be positive")

    chunks = _chunk_ranges(start_sequence, rolls, workers)
    if workers == 1:
        partials = [
            _run_exact_cpu_chunk(start, count, master_seed, match_id, command_prefix)
            for start, count in chunks
        ]
    else:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            partials = list(
                executor.map(
                    _run_exact_cpu_chunk_from_tuple,
                    [
                        (start, count, master_seed, match_id, command_prefix)
                        for start, count in chunks
                    ],
                )
            )

    face_counts, outcome_counts, rejected_byte_counts = _merge_partials(partials)
    sample_proofs = _sample_proofs(
        sample_receipts,
        start_sequence,
        rolls,
        master_seed,
        match_id,
        command_prefix,
    )

    return _build_result(
        config=AuditConfig(
            backend="exact-cpu",
            rolls=rolls,
            candidate_bytes=None,
            master_seed=master_seed,
            start_sequence=start_sequence,
            match_id=match_id,
            command_prefix=command_prefix,
            workers=workers,
            sample_receipts=sample_receipts,
        ),
        face_counts=face_counts,
        outcome_counts=outcome_counts,
        rejected_byte_counts=rejected_byte_counts,
        sample_proofs=sample_proofs,
        notes=[
            "This backend mirrors bgb_vos_v1/src/match_authority/dice.rs exactly.",
            "Seeds are deterministically derived from the audit master seed so the run can be repeated.",
        ],
    )


def run_gpu_bucket_stream_audit(
    candidate_bytes: int,
    master_seed: str,
    chunk_size: int = 100_000_000,
) -> AuditResult:
    if candidate_bytes <= 0:
        raise ValueError("candidate_bytes must be positive")
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    try:
        import cupy as cp  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "CuPy is required for --backend gpu-bucket-stream. "
            "Install with `python -m pip install -e .[gpu,viz]` on the Spark host."
        ) from exc

    seed_int = int.from_bytes(derive_audit_seed(master_seed, 0)[:8], "big") % (2**32)
    rng = cp.random.default_rng(seed_int)
    face_counts = [0 for _ in range(6)]
    outcome_counts = [[0 for _ in range(6)] for _ in range(6)]
    rejected_byte_counts = {value: 0 for value in REJECTED_VALUES}
    pending_face: Optional[int] = None
    total_rolls = 0
    remaining = candidate_bytes

    while remaining > 0:
        current = min(chunk_size, remaining)
        remaining -= current

        values = rng.integers(0, SOURCE_VALUE_COUNT, size=current, dtype=cp.uint8)
        byte_counts = cp.bincount(values, minlength=SOURCE_VALUE_COUNT).get()
        for value in REJECTED_VALUES:
            rejected_byte_counts[value] += int(byte_counts[value])

        accepted_faces = values[values < ACCEPTED_VALUE_COUNT].astype(cp.int16) // 42
        del values

        accepted_count = int(accepted_faces.size)
        start_index = 0
        if pending_face is not None and accepted_count > 0:
            first_zero_based = pending_face - 1
            second_zero_based = int(accepted_faces[0].get())
            start_index = 1
            face_counts[first_zero_based] += 1
            face_counts[second_zero_based] += 1
            outcome_counts[first_zero_based][second_zero_based] += 1
            total_rolls += 1
            pending_face = None

        usable = accepted_count - start_index
        paired = usable - (usable % 2)
        if paired > 0:
            pairs = accepted_faces[start_index : start_index + paired].reshape((-1, 2))
            first_counts = cp.bincount(pairs[:, 0], minlength=6).get()
            second_counts = cp.bincount(pairs[:, 1], minlength=6).get()
            outcome_indices = pairs[:, 0] * 6 + pairs[:, 1]
            outcome_flat = cp.bincount(outcome_indices, minlength=36).get()

            for face_index in range(6):
                face_counts[face_index] += int(first_counts[face_index] + second_counts[face_index])
            for index, count in enumerate(outcome_flat):
                outcome_counts[index // 6][index % 6] += int(count)
            total_rolls += paired // 2
            del pairs
            del outcome_indices

        if usable % 2 == 1:
            pending_face = int(accepted_faces[start_index + paired].get()) + 1
        del accepted_faces

    return _build_result(
        config=AuditConfig(
            backend="gpu-bucket-stream",
            rolls=total_rolls,
            candidate_bytes=candidate_bytes,
            master_seed=master_seed,
            start_sequence=0,
            match_id="gpu-byte-stream",
            command_prefix="gpu-byte-stream",
            workers=1,
            sample_receipts=0,
        ),
        face_counts=face_counts,
        outcome_counts=outcome_counts,
        rejected_byte_counts=rejected_byte_counts,
        sample_proofs=[],
        notes=[
            "This backend tests the rejection bucket mapping at GPU scale using CuPy-generated bytes.",
            "It does not compute SHA-256 roll proofs; use exact-cpu for canonical replay verification.",
        ],
    )


def _run_exact_cpu_chunk_from_tuple(args: Tuple[int, int, str, str, str]):
    return _run_exact_cpu_chunk(*args)


def _run_exact_cpu_chunk(
    start_sequence: int,
    count: int,
    master_seed: str,
    match_id: str,
    command_prefix: str,
) -> Tuple[List[int], List[List[int]], Dict[int, int]]:
    face_counts = [0 for _ in range(6)]
    outcome_counts = [[0 for _ in range(6)] for _ in range(6)]
    rejected_byte_counts = {value: 0 for value in REJECTED_VALUES}

    for sequence in range(start_sequence, start_sequence + count):
        seed_ref = derive_audit_seed(master_seed, sequence)
        context = dice_public_context(match_id, f"{command_prefix}-{sequence}", sequence)
        proof, rejected_values = roll_proof_and_rejected_value_counts(seed_ref, context)

        first, second = proof.roll
        face_counts[first - 1] += 1
        face_counts[second - 1] += 1
        outcome_counts[first - 1][second - 1] += 1
        for value in REJECTED_VALUES:
            rejected_byte_counts[value] += rejected_values.get(value, 0)

    return face_counts, outcome_counts, rejected_byte_counts


def _merge_partials(
    partials: Sequence[Tuple[List[int], List[List[int]], Dict[int, int]]]
) -> Tuple[List[int], List[List[int]], Dict[int, int]]:
    face_counts = [0 for _ in range(6)]
    outcome_counts = [[0 for _ in range(6)] for _ in range(6)]
    rejected_byte_counts = {value: 0 for value in REJECTED_VALUES}

    for partial_faces, partial_outcomes, partial_rejects in partials:
        for index, count in enumerate(partial_faces):
            face_counts[index] += count
        for row_index, row in enumerate(partial_outcomes):
            for column_index, count in enumerate(row):
                outcome_counts[row_index][column_index] += count
        for value in REJECTED_VALUES:
            rejected_byte_counts[value] += partial_rejects.get(value, 0)

    return face_counts, outcome_counts, rejected_byte_counts


def _sample_proofs(
    sample_receipts: int,
    start_sequence: int,
    rolls: int,
    master_seed: str,
    match_id: str,
    command_prefix: str,
) -> List[Dict[str, object]]:
    samples = []
    for sequence in range(start_sequence, start_sequence + min(sample_receipts, rolls)):
        seed_ref = derive_audit_seed(master_seed, sequence)
        context = dice_public_context(match_id, f"{command_prefix}-{sequence}", sequence)
        proof, rejected_values = roll_proof_and_rejected_value_counts(seed_ref, context)
        samples.append(
            {
                "sequence": sequence,
                "proof": proof.to_jsonable(),
                "rejected_value_counts": {str(key): value for key, value in rejected_values.items()},
            }
        )
    return samples


def _build_result(
    config: AuditConfig,
    face_counts: List[int],
    outcome_counts: List[List[int]],
    rejected_byte_counts: Dict[int, int],
    sample_proofs: List[Dict[str, object]],
    notes: List[str],
) -> AuditResult:
    total_rolls = sum(sum(row) for row in outcome_counts)
    total_dice = sum(face_counts)
    rejected_sample_count = sum(rejected_byte_counts.values())
    total_source_bytes = total_dice + rejected_sample_count
    observed_rejection_rate = (
        rejected_sample_count / total_source_bytes if total_source_bytes else 0.0
    )
    expected_rejection_rate = len(REJECTED_VALUES) / SOURCE_VALUE_COUNT

    face_expected = total_dice / 6.0 if total_dice else 0.0
    outcome_expected = total_rolls / 36.0 if total_rolls else 0.0
    face_chi = chi_square_uniform(face_counts, face_expected).to_jsonable()
    outcome_flat = [count for row in outcome_counts for count in row]
    outcome_chi = chi_square_uniform(outcome_flat, outcome_expected).to_jsonable()

    face_z_scores = z_scores_for_cells(face_counts, total_dice, 1.0 / 6.0)
    outcome_z_flat = z_scores_for_cells(outcome_flat, total_rolls, 1.0 / 36.0)
    outcome_z_scores = [outcome_z_flat[index : index + 6] for index in range(0, 36, 6)]

    rejected_z_scores: Dict[str, float] = {}
    reject_variance_total = total_source_bytes * (1.0 / SOURCE_VALUE_COUNT) * (
        1.0 - 1.0 / SOURCE_VALUE_COUNT
    )
    reject_expected_each = total_source_bytes / SOURCE_VALUE_COUNT if total_source_bytes else 0.0
    reject_denom = reject_variance_total**0.5 if reject_variance_total > 0 else 1.0
    for value in REJECTED_VALUES:
        rejected_z_scores[str(value)] = (
            (rejected_byte_counts.get(value, 0) - reject_expected_each) / reject_denom
            if total_source_bytes
            else 0.0
        )

    return AuditResult(
        config=config,
        generated_at=datetime.now(timezone.utc).isoformat(),
        algorithm_version=DICE_ALGORITHM_VERSION,
        git_commit=_git_commit(),
        git_dirty=_git_dirty(),
        face_counts=face_counts,
        outcome_counts=outcome_counts,
        rejected_byte_counts={str(key): rejected_byte_counts.get(key, 0) for key in REJECTED_VALUES},
        total_rolls=total_rolls,
        total_dice=total_dice,
        total_source_bytes=total_source_bytes,
        rejected_sample_count=rejected_sample_count,
        observed_rejection_rate=observed_rejection_rate,
        expected_rejection_rate=expected_rejection_rate,
        chi_square_faces=face_chi,
        chi_square_outcomes=outcome_chi,
        face_z_scores=face_z_scores,
        outcome_z_scores=outcome_z_scores,
        rejected_byte_z_scores=rejected_z_scores,
        max_abs_face_z=max_abs(face_z_scores),
        max_abs_outcome_z=max_abs(outcome_z_flat),
        max_abs_rejected_byte_z=max_abs(rejected_z_scores.values()),
        sample_proofs=sample_proofs,
        notes=notes,
    )


def _chunk_ranges(start_sequence: int, rolls: int, workers: int) -> List[Tuple[int, int]]:
    chunk_count = min(workers, rolls)
    base = rolls // chunk_count
    remainder = rolls % chunk_count
    chunks = []
    cursor = start_sequence
    for index in range(chunk_count):
        count = base + (1 if index < remainder else 0)
        chunks.append((cursor, count))
        cursor += count
    return chunks


def _git_commit() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return "unavailable"
    commit = completed.stdout.strip()
    return commit or "unavailable"


def _git_dirty() -> bool:
    try:
        completed = subprocess.run(
            ["git", "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return True
    return bool(completed.stdout.strip())
