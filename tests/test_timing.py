import unittest

from fco.timing import readiness_delays


class ReadinessTimingTests(unittest.TestCase):
    def test_poll_early_without_shortening_total_readiness_budget(self):
        for budget in (0.96, 1.2):
            with self.subTest(budget=budget):
                delays = list(readiness_delays(budget))
                self.assertEqual(delays[:3], [0.02, 0.04, 0.08])
                self.assertAlmostEqual(sum(delays), budget)
                self.assertTrue(all(0 < value <= 0.08 for value in delays))
