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


def recent_tick_direction(price_history):
    if len(price_history) < 3:
        return None

    p1 = price_history[-3][1]
    p2 = price_history[-2][1]
    p3 = price_history[-1][1]

    if p3 > p2 > p1:
        return "UP"
    if p3 < p2 < p1:
        return "DOWN"
    return "MIXED"


def get_price_n_seconds_ago(price_history, now_ts, seconds_back):
    target = now_ts - seconds_back
    candidates = [item for item in price_history if item[0] <= target]
    if not candidates:
        return None
    return candidates[-1][1]


def compute_metrics(price_history, now_ts, current_price):
    p1 = get_price_n_seconds_ago(price_history, now_ts, WINDOWS[0])
    p3 = get_price_n_seconds_ago(price_history, now_ts, WINDOWS[1])
    p5 = get_price_n_seconds_ago(price_history, now_ts, WINDOWS[2])

    m1 = pct_change(p1, current_price)
    m3 = pct_change(p3, current_price)
    m5 = pct_change(p5, current_price)

    return {
        "price_1m_ago": p1,
        "price_3m_ago": p3,
        "price_5m_ago": p5,
        "move_1m": round(m1, 4) if m1 is not None else None,
        "move_3m": round(m3, 4) if m3 is not None else None,
        "move_5m": round(m5, 4) if m5 is not None else None,
        "recent_tick_direction": recent_tick_direction(price_history),
    }


def score_up(metrics):
    score = 0
    m1 = metrics["move_1m"]
    m3 = metrics["move_3m"]
    m5 = metrics["move_5m"]
    tick = metrics["recent_tick_direction"]

    if m1 is not None:
        if m1 >= THRESHOLDS["move_1m_up_strong"]:
            score += 2
        elif m1 >= THRESHOLDS["move_1m_up_soft"]:
            score += 1
        elif m1 <= THRESHOLDS["move_1m_down_soft"]:
            score -= 2

    if m3 is not None:
        if m3 >= THRESHOLDS["move_3m_up_strong"]:
            score += 2
        elif m3 >= THRESHOLDS["move_3m_up_soft"]:
            score += 1
        elif m3 <= THRESHOLDS["move_3m_down_soft"]:
            score -= 2

    if m5 is not None:
        if m5 >= THRESHOLDS["move_5m_up_strong"]:
            score += 2
        elif m5 >= THRESHOLDS["move_5m_up_soft"]:
            score += 1
        elif m5 <= THRESHOLDS["move_5m_down_soft"]:
            score -= 2

    if tick == "UP":
        score += 1
    elif tick == "DOWN":
        score -= 1

    return score


def score_down(metrics):
    score = 0
    m1 = metrics["move_1m"]
    m3 = metrics["move_3m"]
    m5 = metrics["move_5m"]
    tick = metrics["recent_tick_direction"]

    if m1 is not None:
        if m1 <= THRESHOLDS["move_1m_down_strong"]:
            score += 2
        elif m1 <= THRESHOLDS["move_1m_down_soft"]:
            score += 1
        elif m1 >= THRESHOLDS["move_1m_up_soft"]:
            score -= 2

    if m3 is not None:
        if m3 <= THRESHOLDS["move_3m_down_strong"]:
            score += 2
        elif m3 <= THRESHOLDS["move_3m_down_soft"]:
            score += 1
        elif m3 >= THRESHOLDS["move_3m_up_soft"]:
            score -= 2

    if m5 is not None:
        if m5 <= THRESHOLDS["move_5m_down_strong"]:
            score += 2
        elif m5 <= THRESHOLDS["move_5m_down_soft"]:
            score += 1
        elif m5 >= THRESHOLDS["move_5m_up_soft"]:
            score -= 2

    if tick == "DOWN":
        score += 1
    elif tick == "UP":
        score -= 1

    return score


def classify_state(metrics):
    m1 = metrics["move_1m"]
    m3 = metrics["move_3m"]
    m5 = metrics["move_5m"]

    up_score = score_up(metrics)
    down_score = score_down(metrics)

    if m1 is None or m3 is None:
        return None, up_score, down_score

    if m5 is not None:
        if up_score >= THRESHOLDS["confirmed_score"]:
            return "CONFIRMED_UP", up_score, down_score
        if down_score >= THRESHOLDS["confirmed_score"]:
            return "CONFIRMED_DOWN", up_score, down_score

    if up_score >= THRESHOLDS["early_score"] and m3 > 0:
        return "EARLY_UP", up_score, down_score
    if down_score >= THRESHOLDS["early_score"] and m3 < 0:
        return "EARLY_DOWN", up_score, down_score

    if m3 is not None and m5 is not None:
        if m3 > 0 and m5 > 0 and m1 is not None and m1 < 0 and up_score >= THRESHOLDS["pullback_score"]:
            return "PULLBACK_UP", up_score, down_score
        if m3 < 0 and m5 < 0 and m1 is not None and m1 > 0 and down_score >= THRESHOLDS["pullback_score"]:
            return "PULLBACK_DOWN", up_score, down_score

    return None, up_score, down_score


def create_simulations(signal, now_ts):
    simulations = []
    for model in ("continuation", "fade"):
        simulations.append(
            {
                "event": "simulation_result",
                "model": model,
                "signal_state": signal["state"],
                "signal_direction": signal["direction"],
                "trade_direction": expected_trade_direction(
                    model,
                    signal["direction"],
                    signal["state"],
                ),
                "entry_price": signal["price_now"],
                "signal_time": now_ts,
                "captured": {},
                "done": False,
                "move_1m": signal["move_1m"],
                "move_3m": signal["move_3m"],
                "move_5m": signal["move_5m"],
                "up_score": signal["up_score"],
                "down_score": signal["down_score"],
            }
        )
    return simulations


def calc_pnl_pct(trade_direction, entry_price, current_price):
    if trade_direction == "UP":
        return (current_price - entry_price) / entry_price
    return (entry_price - current_price) / entry_price


def checkpoint_list():
    return list(CHECKPOINTS)
