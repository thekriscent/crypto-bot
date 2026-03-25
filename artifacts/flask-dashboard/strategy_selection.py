MIN_IMBALANCE = 5
MIN_MA_STRETCH_PCT = 0.001


def _set_reason(signal, reason):
    if signal is not None:
        signal["selection_reason"] = reason


def _imbalance(signal=None):
    if not signal:
        return 0
    return abs(signal.get("up_score", 0) - signal.get("down_score", 0))


def _medium_volatility(signal=None):
    return bool(signal) and signal.get("volatility_state") == "MEDIUM"


def _weakening_up_follow_through(signal=None):
    if not signal:
        return False
    move_1m = signal.get("move_1m")
    move_3m = signal.get("move_3m")
    if move_1m is None or move_3m is None:
        return False
    return move_1m <= move_3m


def _weakening_down_follow_through(signal=None):
    if not signal:
        return False
    move_1m = signal.get("move_1m")
    move_3m = signal.get("move_3m")
    if move_1m is None or move_3m is None:
        return False
    return move_1m >= move_3m


def _downside_exhaustion_ready(state, signal=None):
    if not signal or state not in {"EARLY_DOWN", "CONFIRMED_DOWN"}:
        return False

    return (
        signal.get("range_position") == "BOTTOM"
        and signal.get("trend_state") in {"FLAT", "DOWN"}
        and signal.get("price_vs_ma_1h_pct") is not None
        and signal.get("price_vs_ma_1h_pct") <= -MIN_MA_STRETCH_PCT
        and _weakening_down_follow_through(signal)
    )


def _upside_exhaustion_ready(state, signal=None):
    if not signal or state != "CONFIRMED_UP":
        return False

    return (
        signal.get("range_position") == "TOP"
        and signal.get("trend_state") in {"FLAT", "UP"}
        and signal.get("price_vs_ma_1h_pct") is not None
        and signal.get("price_vs_ma_1h_pct") >= MIN_MA_STRETCH_PCT
        and _weakening_up_follow_through(signal)
    )


def choose_model(state, signal=None):
    if signal and signal.get("skip_candidate"):
        _set_reason(signal, signal.get("skip_reason") or "blocked_skip_candidate")
        return None

    if _imbalance(signal) < MIN_IMBALANCE:
        _set_reason(signal, "blocked_low_imbalance")
        return None

    if not _medium_volatility(signal):
        _set_reason(signal, "blocked_non_medium_volatility")
        return None

    if state == "EARLY_UP":
        _set_reason(signal, "blocked_early_up_fade")
        return None

    if _downside_exhaustion_ready(state, signal):
        _set_reason(signal, "fade_downside_exhaustion")
        return "fade"

    if _upside_exhaustion_ready(state, signal):
        _set_reason(signal, "fade_upside_exhaustion")
        return "fade"

    _set_reason(signal, "blocked_context_mismatch")
    return None


def is_selected_model(model, state, signal=None):
    selected_model = choose_model(state, signal)
    return selected_model is not None and model == selected_model
