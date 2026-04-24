import unittest

from dice_randomness.algorithm import (
    VALUES_PER_BUCKET,
    dice_public_context,
    roll_proof_from_seed,
    sample_for_byte,
    verify_roll_proof,
)


class DiceAlgorithmTests(unittest.TestCase):
    def test_byte_mapping_splits_accepted_values_into_equal_buckets(self):
        face_counts = [0 for _ in range(6)]
        rejected_count = 0

        for byte_value in range(256):
            sample = sample_for_byte(1, 1, byte_value)
            if sample is None:
                rejected_count += 1
            else:
                face_counts[sample.face - 1] += 1
                self.assertEqual(sample.bucket_start // VALUES_PER_BUCKET + 1, sample.face)
                self.assertGreaterEqual(sample.byte_value, sample.bucket_start)
                self.assertLessEqual(sample.byte_value, sample.bucket_end)

        self.assertEqual(face_counts, [42, 42, 42, 42, 42, 42])
        self.assertEqual(rejected_count, 4)

    def test_boundary_values_map_or_reject_like_rust(self):
        self.assertEqual(sample_for_byte(1, 1, 0).face, 1)
        self.assertEqual(sample_for_byte(1, 1, 41).face, 1)
        self.assertEqual(sample_for_byte(1, 1, 42).face, 2)
        self.assertEqual(sample_for_byte(1, 1, 83).face, 2)
        self.assertEqual(sample_for_byte(1, 1, 84).face, 3)
        self.assertEqual(sample_for_byte(1, 1, 251).face, 6)
        self.assertIsNone(sample_for_byte(1, 1, 252))
        self.assertIsNone(sample_for_byte(1, 1, 255))

    def test_every_ordered_outcome_has_equal_byte_weight(self):
        counts = [[0 for _ in range(6)] for _ in range(6)]

        for first_byte in range(252):
            for second_byte in range(252):
                first = sample_for_byte(1, 1, first_byte).face
                second = sample_for_byte(2, 2, second_byte).face
                counts[first - 1][second - 1] += 1

        for row in counts:
            self.assertEqual(row, [1764, 1764, 1764, 1764, 1764, 1764])

    def test_seeded_roll_replays_and_verifies(self):
        seed = b"clear replay seed for tests"
        context = dice_public_context("match-1", "cmd-roll", 3)

        first = roll_proof_from_seed(seed, context)
        second = roll_proof_from_seed(seed, context)

        self.assertEqual(first, second)
        verify_roll_proof(first)
        self.assertEqual(first.bucket_audit.values_per_bucket, 42)
        self.assertEqual(first.bucket_audit.rejected_values, (252, 253, 254, 255))


if __name__ == "__main__":
    unittest.main()
