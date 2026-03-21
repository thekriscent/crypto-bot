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
    if not signal:
        return True

    signal_direction = signal.get("direction") or signal.get("signal_direction")
    range_position = signal.get("range_position")
    trend_state = signal.get("trend_state")

    if range_position == "TOP" and signal_direction == "UP" and trend_state != "STRONG_UP":
        return False

    if range_position == "BOTTOM" and signal_direction == "DOWN" and trend_state != "STRONG_DOWN":
        return False

    return True


def continuation_block_reason(signal=None):
    if not signal:
        return None

    signal_direction = signal.get("direction") or signal.get("signal_direction")
    range_position = signal.get("range_position")
    trend_state = signal.get("trend_state")

    if range_position == "TOP" and signal_direction == "UP" and trend_state != "STRONG_UP":
        return "blocked_top_up_not_strong"

    if range_position == "BOTTOM" and signal_direction == "DOWN" and trend_state != "STRONG_DOWN":
        return "blocked_bottom_down_not_strong"

    return None


def choose_model(state, signal=None):
    if signal and signal.get("skip_candidate") is True:
        signal["selection_reason"] = signal.get("skip_reason") or "no_trade"
        return "no_trade"

    if state == "EARLY_DOWN":
        if signal is not None:
            signal["selection_reason"] = None
        if signal and signal.get("trend_state") in {"DOWN", "STRONG_DOWN"}:
            signal["selection_reason"] = "continuation_selected"
            return "continuation"
        if signal is not None:
            signal["selection_reason"] = "no_trade"
        return "no_trade"

    if state == "EARLY_UP":
        if signal is not None:
            signal["selection_reason"] = None
        if signal and signal.get("trend_state") in {"UP", "STRONG_UP"}:
            signal["selection_reason"] = "continuation_selected"
            return "continuation"
        if signal is not None:
            signal["selection_reason"] = "no_trade"
        return "no_trade"

    if state in {"CONFIRMED_UP", "CONFIRMED_DOWN"}:
        if signal is not None:
            signal["selection_reason"] = None
        if continuation_allowed(signal):
            if signal is not None:
                signal["selection_reason"] = "continuation_selected"
            return "continuation"
        if signal is not None:
            signal["selection_reason"] = continuation_block_reason(signal) or "no_trade"
        return "no_trade"

    if signal is not None:
        signal["selection_reason"] = "no_trade"
    return "no_trade"
