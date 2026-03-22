import unittest

from replay.btc.classifier import classify_history
from replay.shared.types import PricePoint


class BTCClassifierTest(unittest.TestCase):
    def test_classifier_emits_signal_with_selected_model(self):
        history = [
            PricePoint(timestamp=0, price=100.0),
            PricePoint(timestamp=60, price=101.5),
            PricePoint(timestamp=120, price=102.5),
            PricePoint(timestamp=180, price=103.5),
            PricePoint(timestamp=240, price=104.2),
            PricePoint(timestamp=300, price=105.0),
        ]
        signal = classify_history(history, 300, 105.0, news_flag=False)
        self.assertIsNotNone(signal)
        self.assertIn(signal["state"], {"EARLY_UP", "CONFIRMED_UP"})
        self.assertTrue(signal["skip_candidate"])
        self.assertIsNone(signal["selected_model"])


if __name__ == "__main__":
    unittest.main()
