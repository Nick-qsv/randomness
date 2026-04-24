"""Exact Python mirror of bgb_vos_v1/src/match_authority/dice.rs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

DICE_ALGORITHM_VERSION = "server_seeded_rejection_sha256_v1"
SOURCE_VALUE_COUNT = 256
ACCEPTED_VALUE_COUNT = 252
REJECTED_VALUE_COUNT = SOURCE_VALUE_COUNT - ACCEPTED_VALUE_COUNT
BUCKET_COUNT = 6
VALUES_PER_BUCKET = 42
REJECTED_VALUES = (252, 253, 254, 255)


@dataclass(frozen=True)
class DiceBucketAudit:
    source_value_count: int
    accepted_value_count: int
    rejected_value_count: int
    bucket_count: int
    values_per_bucket: int
    rejected_values: Tuple[int, int, int, int]

    @classmethod
    def v1(cls) -> "DiceBucketAudit":
        return cls(
            source_value_count=SOURCE_VALUE_COUNT,
            accepted_value_count=ACCEPTED_VALUE_COUNT,
            rejected_value_count=REJECTED_VALUE_COUNT,
            bucket_count=BUCKET_COUNT,
            values_per_bucket=VALUES_PER_BUCKET,
            rejected_values=REJECTED_VALUES,
        )


@dataclass(frozen=True)
class DiceSample:
    die_index: int
    sample_index: int
    byte_value: int
    bucket_start: int
    bucket_end: int
    face: int


@dataclass(frozen=True)
class DiceRollProof:
    algorithm_version: str
    server_seed_hex: str
    server_seed_hash: str
    public_context: str
    public_context_hash: str
    roll: Tuple[int, int]
    accepted_samples: Tuple[DiceSample, DiceSample]
    rejected_sample_count: int
    bucket_audit: DiceBucketAudit

    def to_jsonable(self) -> Dict[str, object]:
        payload = asdict(self)
        payload["roll"] = list(self.roll)
        payload["accepted_samples"] = [asdict(sample) for sample in self.accepted_samples]
        payload["bucket_audit"]["rejected_values"] = list(self.bucket_audit.rejected_values)
        return payload


def prefixed_sha256(bytes_ref: bytes) -> str:
    return "sha256:" + hashlib.sha256(bytes_ref).hexdigest()


def dice_public_context(match_id: str, command_id: str, roll_seq: int) -> str:
    return (
        f"algorithm={DICE_ALGORITHM_VERSION}|"
        f"match_id={match_id}|"
        f"command_id={command_id}|"
        f"roll_seq={roll_seq}"
    )


def sample_for_byte(die_index: int, sample_index: int, byte_value: int) -> Optional[DiceSample]:
    if byte_value >= ACCEPTED_VALUE_COUNT:
        return None

    bucket_index = byte_value // VALUES_PER_BUCKET
    bucket_start = bucket_index * VALUES_PER_BUCKET
    bucket_end = bucket_start + VALUES_PER_BUCKET - 1

    return DiceSample(
        die_index=die_index,
        sample_index=sample_index,
        byte_value=byte_value,
        bucket_start=bucket_start,
        bucket_end=bucket_end,
        face=bucket_index + 1,
    )


def dice_hash_block(seed_ref: bytes, context_ref: bytes, block_index: int) -> bytes:
    hasher = hashlib.sha256()
    hasher.update(DICE_ALGORITHM_VERSION.encode("utf-8"))
    hasher.update(bytes([0]))
    hasher.update(seed_ref)
    hasher.update(bytes([0]))
    hasher.update(context_ref)
    hasher.update(block_index.to_bytes(8, "big", signed=False))
    return hasher.digest()


def roll_proof_from_seed(seed_ref: bytes, public_context: str) -> DiceRollProof:
    proof, _rejected_value_counts = roll_proof_and_rejected_value_counts(seed_ref, public_context)
    return proof


def roll_proof_and_rejected_value_counts(
    seed_ref: bytes,
    public_context: str,
) -> Tuple[DiceRollProof, Dict[int, int]]:
    context_ref = public_context.encode("utf-8")
    accepted_samples: List[DiceSample] = []
    rejected_sample_count = 0
    rejected_value_counts = {value: 0 for value in REJECTED_VALUES}
    sample_index = 0
    block_index = 0

    while len(accepted_samples) < 2:
        block = dice_hash_block(seed_ref, context_ref, block_index)
        for byte_value in block:
            die_index = len(accepted_samples) + 1
            sample_index += 1

            sample = sample_for_byte(die_index, sample_index, byte_value)
            if sample is None:
                rejected_sample_count += 1
                rejected_value_counts[byte_value] = rejected_value_counts.get(byte_value, 0) + 1
                continue

            accepted_samples.append(sample)
            if len(accepted_samples) == 2:
                break
        block_index += 1

    first, second = accepted_samples
    proof = DiceRollProof(
        algorithm_version=DICE_ALGORITHM_VERSION,
        server_seed_hex=seed_ref.hex(),
        server_seed_hash=prefixed_sha256(seed_ref),
        public_context=public_context,
        public_context_hash=prefixed_sha256(context_ref),
        roll=(first.face, second.face),
        accepted_samples=(first, second),
        rejected_sample_count=rejected_sample_count,
        bucket_audit=DiceBucketAudit.v1(),
    )
    return proof, rejected_value_counts


def verify_roll_proof(proof: DiceRollProof) -> None:
    seed_ref = bytes.fromhex(proof.server_seed_hex)
    recomputed = roll_proof_from_seed(seed_ref, proof.public_context)
    if recomputed.roll != proof.roll:
        raise ValueError(f"roll mismatch expected {recomputed.roll}, got {proof.roll}")
    if recomputed.accepted_samples != proof.accepted_samples:
        raise ValueError(
            f"sample mismatch expected {recomputed.accepted_samples}, got {proof.accepted_samples}"
        )
    if recomputed.rejected_sample_count != proof.rejected_sample_count:
        raise ValueError(
            "rejection count mismatch expected "
            f"{recomputed.rejected_sample_count}, got {proof.rejected_sample_count}"
        )


def derive_audit_seed(master_seed: str, sequence: int) -> bytes:
    hasher = hashlib.sha256()
    hasher.update(b"dice_randomness_audit_server_seed_v1")
    hasher.update(bytes([0]))
    hasher.update(master_seed.encode("utf-8"))
    hasher.update(bytes([0]))
    hasher.update(sequence.to_bytes(8, "big", signed=False))
    return hasher.digest()


def iter_byte_mapping() -> Iterable[Tuple[int, Optional[int]]]:
    for byte_value in range(SOURCE_VALUE_COUNT):
        sample = sample_for_byte(1, 1, byte_value)
        yield byte_value, None if sample is None else sample.face
