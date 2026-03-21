from market_context import (
    compute_traditional_indicators,
    range_position,
    volatility_state,
)


def _recent_directional_consistency(price_history):
    recent_prices = [price for _, price in price_history[-5:]]
    if len(recent_prices) < 4:
        return None

    deltas = [current - previous for previous, current in zip(recent_prices, recent_prices[1:])]
    positive_moves = sum(1 for delta in deltas if delta > 0)
    negative_moves = sum(1 for delta in deltas if delta < 0)

    if positive_moves >= 3:
        return "UP"
    if negative_moves >= 3:
        return "DOWN"
    return "MIXED"


def _xau_trend_state(price_history, now_ts, current_price):
    indicators = compute_traditional_indicators(price_history, now_ts, current_price)
    ma_5m = indicators["ma_5m"]
    ma_15m = indicators["ma_15m"]
    if ma_5m is None or ma_15m is None:
        return "FLAT", indicators

    directional_consistency = _recent_directional_consistency(price_history)
    price_above_both = current_price > ma_5m and current_price > ma_15m
    price_below_both = current_price < ma_5m and current_price < ma_15m
    ma_alignment_up = ma_5m > ma_15m
    ma_alignment_down = ma_5m < ma_15m

    distance_from_ma_5m = abs(indicators["price_vs_ma_5m_pct"] or 0)
    distance_from_ma_15m = abs(indicators["price_vs_ma_15m_pct"] or 0)
    sufficiently_extended = distance_from_ma_5m >= 0.0006 and distance_from_ma_15m >= 0.0008

    if (
        ma_alignment_up
        and price_above_both
        and directional_consistency == "UP"
        and sufficiently_extended
    ):
        return "STRONG_UP", indicators

    if (
        ma_alignment_down
        and price_below_both
        and directional_consistency == "DOWN"
        and sufficiently_extended
    ):
        return "STRONG_DOWN", indicators

    if ma_alignment_up and price_above_both:
        return "UP", indicators

    if ma_alignment_down and price_below_both:
        return "DOWN", indicators

    return "FLAT", indicators


def compute_xauusd_market_context(price_history, now_ts, current_price, news_flag):
    trend_state, indicators = _xau_trend_state(price_history, now_ts, current_price)
    current_volatility = volatility_state(price_history, now_ts)

    return {
        "volatility_state": current_volatility,
        "range_position": range_position(price_history, now_ts, current_price),
        "news_flag": news_flag,
        "trend_state": trend_state,
        "skip_candidate": False,
        "skip_reason": None,
        "selection_reason": None,
        **indicators,
    }


def xauusd_skip_decision(state, direction, context):
    trend_state = context.get("trend_state")
    range_position_value = context.get("range_position")
    volatility = context.get("volatility_state")

    if state.startswith("EARLY") and trend_state == "FLAT":
        return True, "flat_early_signal"

    if volatility == "LOW":
        return True, "low_volatility"

    if direction == "UP" and trend_state in {"DOWN", "STRONG_DOWN"}:
        return True, "direction_conflicts_with_trend"

    if direction == "DOWN" and trend_state in {"UP", "STRONG_UP"}:
        return True, "direction_conflicts_with_trend"

    if range_position_value == "TOP" and direction == "UP" and trend_state != "STRONG_UP":
        return True, "blocked_top_up_not_strong"

    if range_position_value == "BOTTOM" and direction == "DOWN" and trend_state != "STRONG_DOWN":
        return True, "blocked_bottom_down_not_strong"

    return False, None
