import unittest

from strategy_selection import choose_model, is_selected_model


class BTCStrategySelectionTest(unittest.TestCase):
    def test_skip_candidate_returns_no_trade(self):
        signal = {
            "skip_candidate": True,
            "up_score": 7,
            "down_score": -7,
            "move_1m": 0.001,
            "move_3m": 0.002,
            "range_position": "TOP",
        }
        self.assertIsNone(choose_model("CONFIRMED_UP", signal))

    def test_high_imbalance_with_exhaustion_selects_fade(self):
        signal = {
            "up_score": 6,
            "down_score": -6,
            "move_1m": 0.0008,
            "move_3m": 0.0004,
            "range_position": "MIDDLE",
        }
        self.assertEqual(choose_model("CONFIRMED_UP", signal), "fade")

    def test_low_imbalance_returns_no_trade(self):
        signal = {
            "up_score": 3,
            "down_score": -1,
            "move_1m": 0.001,
            "move_3m": 0.002,
            "range_position": "TOP",
        }
        self.assertIsNone(choose_model("EARLY_UP", signal))

    def test_high_imbalance_without_exhaustion_returns_no_trade(self):
        signal = {
            "up_score": 5,
            "down_score": -2,
            "move_1m": 0.0002,
            "move_3m": 0.0008,
            "range_position": "MIDDLE",
        }
        self.assertIsNone(choose_model("CONFIRMED_UP", signal))

    def test_continuation_is_never_selected(self):
        signal = {
            "up_score": -7,
            "down_score": 7,
            "move_1m": -0.001,
            "move_3m": -0.0015,
            "range_position": "BOTTOM",
        }
        self.assertEqual(choose_model("CONFIRMED_DOWN", signal), "fade")
        self.assertFalse(is_selected_model("continuation", "CONFIRMED_DOWN", signal))
        self.assertTrue(is_selected_model("fade", "CONFIRMED_DOWN", signal))


if __name__ == "__main__":
    unittest.main()
