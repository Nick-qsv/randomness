import unittest

from dice_randomness.audit import run_exact_cpu_audit


class AuditTests(unittest.TestCase):
    def test_exact_cpu_audit_counts_rolls_faces_and_rejections(self):
        result = run_exact_cpu_audit(
            rolls=25,
            master_seed="unit-test-seed",
            sample_receipts=3,
        )

        self.assertEqual(result.total_rolls, 25)
        self.assertEqual(result.total_dice, 50)
        self.assertEqual(sum(result.face_counts), 50)
        self.assertEqual(sum(sum(row) for row in result.outcome_counts), 25)
        self.assertEqual(len(result.sample_proofs), 3)
        self.assertGreaterEqual(result.total_source_bytes, 50)
        self.assertEqual(
            result.total_source_bytes,
            result.total_dice + result.rejected_sample_count,
        )


if __name__ == "__main__":
    unittest.main()
