import unittest

from replay.btc.metrics import compute_metrics
from replay.shared.types import PricePoint


class BTCReplayMetricsTest(unittest.TestCase):
    def test_compute_metrics_returns_expected_changes(self):
        history = [
            PricePoint(timestamp=0, price=100.0),
            PricePoint(timestamp=60, price=99.0),
            PricePoint(timestamp=120, price=98.0),
            PricePoint(timestamp=180, price=97.0),
            PricePoint(timestamp=240, price=96.0),
            PricePoint(timestamp=300, price=95.0),
        ]
        metrics = compute_metrics(history, 300, 95.0)
        self.assertEqual(metrics["recent_tick_direction"], "DOWN")
        self.assertAlmostEqual(metrics["move_1m"], -0.0104, places=4)
        self.assertAlmostEqual(metrics["move_3m"], -0.0306, places=4)


if __name__ == "__main__":
    unittest.main()
