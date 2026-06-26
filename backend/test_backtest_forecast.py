import math
import unittest

from app.backtest_forecast import mape, rmse


class MapeTests(unittest.TestCase):
    def test_mean_absolute_percentage_error(self):
        # |10|/100 = 10%, |10|/200 = 5%  ->  mean = 7.5%
        self.assertAlmostEqual(mape([100.0, 200.0], [110.0, 190.0]), 7.5, places=6)

    def test_identical_series_is_zero(self):
        self.assertEqual(mape([5.0, 9.0, 13.0], [5.0, 9.0, 13.0]), 0.0)

    def test_skips_zero_actuals_to_avoid_div_by_zero(self):
        # The zero-actual point is excluded; only |10|/100 = 10% remains.
        self.assertAlmostEqual(mape([0.0, 100.0], [5.0, 110.0]), 10.0, places=6)

    def test_all_zero_actuals_returns_nan(self):
        self.assertTrue(math.isnan(mape([0.0, 0.0], [3.0, 4.0])))

    def test_length_mismatch_raises(self):
        with self.assertRaises(ValueError):
            mape([1.0, 2.0], [1.0])


class RmseTests(unittest.TestCase):
    def test_root_mean_squared_error(self):
        # errors of 10 and 10 -> sqrt(mean(100, 100)) = 10
        self.assertAlmostEqual(rmse([100.0, 200.0], [110.0, 190.0]), 10.0, places=6)

    def test_identical_series_is_zero(self):
        self.assertEqual(rmse([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]), 0.0)

    def test_length_mismatch_raises(self):
        with self.assertRaises(ValueError):
            rmse([1.0], [1.0, 2.0])

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            rmse([], [])


if __name__ == "__main__":
    unittest.main()
