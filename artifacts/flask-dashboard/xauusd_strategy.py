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


def _directional_threshold(direction, window, strong=False):
    side = "up" if direction == "UP" else "down"
    strength = "strong" if strong else "soft"
    return THRESHOLDS[f"move_{window}_{side}_{strength}"]


def _move_supports_direction(move_value, direction, window="1m", strong=False):
    if move_value is None:
        return False

    threshold = _directional_threshold(direction, window, strong=strong)
    if direction == "UP":
        return move_value >= threshold
    return move_value <= threshold


def _price_vs_ma_aligned(direction, price_vs_ma_1h_pct):
    if price_vs_ma_1h_pct is None:
        return False
    if direction == "UP":
        return price_vs_ma_1h_pct >= 0
    return price_vs_ma_1h_pct <= 0


def _trend_aligned(direction, trend_state):
    if direction == "UP":
        return trend_state in {"UP", "STRONG_UP"}
    return trend_state in {"DOWN", "STRONG_DOWN"}


def _trend_strong(direction, trend_state):
    if direction == "UP":
        return trend_state == "STRONG_UP"
    return trend_state == "STRONG_DOWN"


def _is_exhaustion_extreme(direction, range_position):
    return (
        (direction == "UP" and range_position == "TOP")
        or (direction == "DOWN" and range_position == "BOTTOM")
    )


def _has_stretched_context(signal):
    direction = signal.get("direction") or signal.get("signal_direction")
    move_3m = signal.get("move_3m")
    move_5m = signal.get("move_5m")
    price_vs_ma_1h_pct = signal.get("price_vs_ma_1h_pct")

    return (
        _price_vs_ma_aligned(direction, price_vs_ma_1h_pct)
        and (
            _move_supports_direction(move_3m, direction, window="3m", strong=True)
            or _move_supports_direction(move_5m, direction, window="5m")
        )
    )


def _is_late_cycle_reversal_setup(signal):
    state = signal.get("state") or signal.get("signal_state")
    direction = signal.get("direction") or signal.get("signal_direction")
    trend_state = signal.get("trend_state")
    move_1m = signal.get("move_1m")
    move_3m = signal.get("move_3m")
    move_5m = signal.get("move_5m")
    price_vs_ma_1h_pct = signal.get("price_vs_ma_1h_pct")

    if state not in {"EARLY_UP", "EARLY_DOWN", "CONFIRMED_UP", "CONFIRMED_DOWN"}:
        return False

    if not _move_supports_direction(move_3m, direction, window="3m"):
        return False

    if move_5m is not None and not _move_supports_direction(move_5m, direction, window="5m"):
        return False

    return not (
        _move_supports_direction(move_1m, direction, window="1m", strong=True)
        and _price_vs_ma_aligned(direction, price_vs_ma_1h_pct)
        and _trend_aligned(direction, trend_state)
    )


def _exceptionally_strong_continuation(signal):
    direction = signal.get("direction") or signal.get("signal_direction")
    trend_state = signal.get("trend_state")
    move_1m = signal.get("move_1m")
    move_3m = signal.get("move_3m")
    move_5m = signal.get("move_5m")
    price_vs_ma_1h_pct = signal.get("price_vs_ma_1h_pct")

    return (
        _trend_strong(direction, trend_state)
        and _move_supports_direction(move_1m, direction, window="1m", strong=True)
        and _move_supports_direction(move_3m, direction, window="3m")
        and (move_5m is None or _move_supports_direction(move_5m, direction, window="5m"))
        and _price_vs_ma_aligned(direction, price_vs_ma_1h_pct)
    )


def continuation_block_reason(signal=None):
    if not signal:
        return None

    signal_direction = signal.get("direction") or signal.get("signal_direction")
    range_position = signal.get("range_position")
    trend_state = signal.get("trend_state")
    move_1m = signal.get("move_1m")
    price_vs_ma_1h_pct = signal.get("price_vs_ma_1h_pct")

    if not _move_supports_direction(move_1m, signal_direction, window="1m"):
        return "blocked_continuation_1m_not_aligned"

    if not _price_vs_ma_aligned(signal_direction, price_vs_ma_1h_pct):
        return "blocked_continuation_1h_ma_misaligned"

    if not _trend_aligned(signal_direction, trend_state):
        return "blocked_continuation_mixed_context"

    if _is_exhaustion_extreme(signal_direction, range_position) and not _exceptionally_strong_continuation(signal):
        return "blocked_continuation_exhaustion_extreme"

    return None


def fade_block_reason(signal=None):
    if not signal:
        return "blocked_fade_missing_signal"

    signal_direction = signal.get("direction") or signal.get("signal_direction")
    range_position = signal.get("range_position")

    if _exceptionally_strong_continuation(signal):
        return "blocked_fade_trend_too_strong"

    if _is_exhaustion_extreme(signal_direction, range_position):
        move_1m = signal.get("move_1m")
        if (
            _move_supports_direction(move_1m, signal_direction, window="1m", strong=True)
            and not _has_stretched_context(signal)
            and not _is_late_cycle_reversal_setup(signal)
        ):
            return "blocked_fade_context_not_stretched"
        return None

    if _is_late_cycle_reversal_setup(signal):
        return None

    return "blocked_fade_no_reversal_setup"


def fade_selection_reason(signal=None):
    if not signal:
        return None

    signal_direction = signal.get("direction") or signal.get("signal_direction")
    range_position = signal.get("range_position")
    move_1m = signal.get("move_1m")

    if fade_block_reason(signal) is not None:
        return None

    if _is_exhaustion_extreme(signal_direction, range_position):
        if (
            not _move_supports_direction(move_1m, signal_direction, window="1m", strong=True)
            or _has_stretched_context(signal)
            or _is_late_cycle_reversal_setup(signal)
        ):
            return "exhaustion_fade_selected"

    if _is_late_cycle_reversal_setup(signal):
        return "fade_selected"

    return None


def pullback_continuation_block_reason(signal=None):
    if not signal:
        return "blocked_continuation_pullback_missing_signal"

    signal_direction = signal.get("direction") or signal.get("signal_direction")
    trend_state = signal.get("trend_state")
    price_vs_ma_1h_pct = signal.get("price_vs_ma_1h_pct")

    if not _trend_aligned(signal_direction, trend_state):
        return "blocked_continuation_pullback_trend_misaligned"

    if not _price_vs_ma_aligned(signal_direction, price_vs_ma_1h_pct):
        return "blocked_continuation_pullback_1h_ma_misaligned"

    return None


def choose_model(state, signal=None):
    if signal and signal.get("skip_candidate") is True:
        signal["selection_reason"] = signal.get("skip_reason") or "no_trade"
        return "no_trade"

    if state in {"PULLBACK_UP", "PULLBACK_DOWN"}:
        if signal is not None:
            signal["selection_reason"] = None
        block_reason = pullback_continuation_block_reason(signal)
        if block_reason is None:
            if signal is not None:
                signal["selection_reason"] = "pullback_continuation_selected"
            return "continuation"
        if signal is not None:
            signal["selection_reason"] = block_reason
        return "no_trade"

    if state in {"EARLY_DOWN", "EARLY_UP", "CONFIRMED_UP", "CONFIRMED_DOWN"}:
        if signal is not None:
            signal["selection_reason"] = None
        block_reason = continuation_block_reason(signal)
        fade_reason = fade_selection_reason(signal)
        if block_reason is None:
            if signal is not None:
                signal["selection_reason"] = "continuation_selected"
            return "continuation"
        if fade_reason is not None:
            if signal is not None:
                signal["selection_reason"] = fade_reason
            return "fade"
        if signal is not None:
            signal_direction = signal.get("direction") or signal.get("signal_direction")
            range_position = signal.get("range_position")
            if _is_exhaustion_extreme(signal_direction, range_position):
                signal["selection_reason"] = fade_block_reason(signal) or block_reason or "no_trade"
            else:
                signal["selection_reason"] = block_reason or fade_block_reason(signal) or "no_trade"
        return "no_trade"

    if signal is not None:
        signal["selection_reason"] = "no_trade"
    return "no_trade"
