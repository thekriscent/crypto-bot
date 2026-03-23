from xauusd_config import CHECKPOINTS, THRESHOLDS, WINDOWS


def pct_change(old_price, new_price):
    if old_price is None or old_price == 0:
        return None
    return (new_price - old_price) / old_price


def opposite_direction(direction):
    return "DOWN" if direction == "UP" else "UP"


def expected_trade_direction(model, signal_direction, signal_state=None):
    if model == "continuation":
        if signal_state and signal_state.endswith("_DOWN"):
            return "DOWN"
        if signal_state and signal_state.endswith("_UP"):
            return "UP"
        return signal_direction
    if model == "fade":
        return opposite_direction(signal_direction)
    return signal_direction


def continuation_allowed(signal=None):
    return continuation_block_reason(signal) is None


def continuation_block_reason(signal=None):
    if not signal:
        return None

    state = signal.get("state") or signal.get("signal_state")
    signal_direction = signal.get("direction") or signal.get("signal_direction")
    range_position = signal.get("range_position")
    trend_state = signal.get("trend_state")
    move_1m = signal.get("move_1m")
    price_vs_ma_1h_pct = signal.get("price_vs_ma_1h_pct")

    if signal_direction == "UP":
        if move_1m is None or move_1m <= 0:
            return "blocked_up_move_1m_nonpositive"
        if price_vs_ma_1h_pct is None or price_vs_ma_1h_pct < 0:
            return "blocked_up_below_1h_ma"

    if signal_direction == "DOWN":
        if move_1m is None or move_1m >= 0:
            return "blocked_down_move_1m_nonnegative"
        if price_vs_ma_1h_pct is None or price_vs_ma_1h_pct > 0:
            return "blocked_down_above_1h_ma"

    if range_position == "TOP" and signal_direction == "UP":
        if state != "CONFIRMED_UP" or trend_state != "STRONG_UP":
            return "blocked_top_up_needs_stronger_confirmation"

    if range_position == "BOTTOM" and signal_direction == "DOWN":
        if state != "CONFIRMED_DOWN" or trend_state != "STRONG_DOWN":
            return "blocked_bottom_down_needs_stronger_confirmation"

    if signal_direction == "UP" and trend_state not in {"UP", "STRONG_UP"}:
        if state == "CONFIRMED_UP":
            return "blocked_confirmed_up_mixed_context"
        return "blocked_up_mixed_context"

    if signal_direction == "DOWN" and trend_state not in {"DOWN", "STRONG_DOWN"}:
        if state == "CONFIRMED_DOWN":
            return "blocked_confirmed_down_mixed_context"
        return "blocked_down_mixed_context"

    return None


def choose_model(state, signal=None):
    if signal and signal.get("skip_candidate") is True:
        signal["selection_reason"] = signal.get("skip_reason") or "no_trade"
        return "no_trade"

    if state in {"EARLY_DOWN", "EARLY_UP", "CONFIRMED_UP", "CONFIRMED_DOWN"}:
        if signal is not None:
            signal["selection_reason"] = None
        block_reason = continuation_block_reason(signal)
        if block_reason is None:
            if signal is not None:
                signal["selection_reason"] = "continuation_selected"
            return "continuation"
        if signal is not None:
            signal["selection_reason"] = block_reason or "no_trade"
        return "no_trade"

    if signal is not None:
        signal["selection_reason"] = "no_trade"
    return "no_trade"
