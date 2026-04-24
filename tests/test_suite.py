import unittest

from dice_randomness.suite import _max_outcome_cell


class SuiteTests(unittest.TestCase):
    def test_max_outcome_cell_reports_one_based_ordered_cell(self):
        class Result:
            outcome_z_scores = [
                [0.1, -0.2, 0.3, 0.4, 0.5, 0.6],
                [0.7, -2.4, 0.9, 1.0, 1.1, 1.2],
                [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 2.2, 0.0, 0.0],
                [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            ]

        cell, z_score = _max_outcome_cell(Result())

        self.assertEqual(cell, "2,2")
        self.assertEqual(z_score, -2.4)


if __name__ == "__main__":
    unittest.main()
