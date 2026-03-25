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
            "volatility_state": "MEDIUM",
            "range_position": "TOP",
        }
        self.assertIsNone(choose_model("CONFIRMED_UP", signal))

    def test_low_volatility_returns_no_trade(self):
        signal = {
            "up_score": -6,
            "down_score": 6,
            "move_1m": -0.0008,
            "move_3m": -0.0018,
            "volatility_state": "LOW",
            "range_position": "BOTTOM",
            "trend_state": "FLAT",
            "price_vs_ma_1h_pct": -0.002,
        }
        self.assertIsNone(choose_model("CONFIRMED_DOWN", signal))

    def test_low_imbalance_returns_no_trade(self):
        signal = {
            "up_score": 3,
            "down_score": -1,
            "move_1m": 0.001,
            "move_3m": 0.002,
            "volatility_state": "MEDIUM",
            "range_position": "TOP",
        }
        self.assertIsNone(choose_model("EARLY_UP", signal))

    def test_early_up_is_blocked_even_in_medium_volatility(self):
        signal = {
            "up_score": 6,
            "down_score": -6,
            "move_1m": 0.0006,
            "move_3m": 0.0014,
            "volatility_state": "MEDIUM",
            "range_position": "TOP",
            "trend_state": "FLAT",
            "price_vs_ma_1h_pct": 0.0015,
        }
        self.assertIsNone(choose_model("EARLY_UP", signal))

    def test_downside_exhaustion_selects_fade(self):
        signal = {
            "up_score": -7,
            "down_score": 7,
            "move_1m": -0.0008,
            "move_3m": -0.0024,
            "volatility_state": "MEDIUM",
            "range_position": "BOTTOM",
            "trend_state": "FLAT",
            "price_vs_ma_1h_pct": -0.003,
        }
        self.assertEqual(choose_model("CONFIRMED_DOWN", signal), "fade")

    def test_upside_confirmed_exhaustion_selects_fade(self):
        signal = {
            "up_score": 6,
            "down_score": -6,
            "move_1m": 0.0007,
            "move_3m": 0.0024,
            "volatility_state": "MEDIUM",
            "range_position": "TOP",
            "trend_state": "UP",
            "price_vs_ma_1h_pct": 0.003,
        }
        self.assertEqual(choose_model("CONFIRMED_UP", signal), "fade")

    def test_continuation_is_never_selected(self):
        signal = {
            "up_score": -7,
            "down_score": 7,
            "move_1m": -0.0008,
            "move_3m": -0.0024,
            "volatility_state": "MEDIUM",
            "range_position": "BOTTOM",
            "trend_state": "FLAT",
            "price_vs_ma_1h_pct": -0.003,
        }
        self.assertFalse(is_selected_model("continuation", "CONFIRMED_DOWN", signal))
        self.assertTrue(is_selected_model("fade", "CONFIRMED_DOWN", signal))


if __name__ == "__main__":
    unittest.main()
