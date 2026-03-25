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


def _all_momentum_positive(signal):
    m1 = signal.get("move_1m")
    m3 = signal.get("move_3m")
    m5 = signal.get("move_5m")
    return (
        m1 is not None and m1 > 0
        and m3 is not None and m3 > 0
        and m5 is not None and m5 > 0
    )


def _all_momentum_negative(signal):
    m1 = signal.get("move_1m")
    m3 = signal.get("move_3m")
    m5 = signal.get("move_5m")
    return (
        m1 is not None and m1 < 0
        and m3 is not None and m3 < 0
        and m5 is not None and m5 < 0
    )


def _weakening_follow_through_up(signal):
    m1 = signal.get("move_1m")
    m3 = signal.get("move_3m")
    m5 = signal.get("move_5m")
    if m5 is None or m1 is None:
        return False
    if m5 > 0 and m1 <= 0:
        return True
    if m5 > 0 and m3 is not None and m1 < m3 * 0.5:
        return True
    return False


def _weakening_follow_through_down(signal):
    m1 = signal.get("move_1m")
    m3 = signal.get("move_3m")
    m5 = signal.get("move_5m")
    if m5 is None or m1 is None:
        return False
    if m5 < 0 and m1 >= 0:
        return True
    if m5 < 0 and m3 is not None and m1 > m3 * 0.5:
        return True
    return False


def _early_reversal_quality_ok(signal, state):
    range_position = signal.get("range_position")
    m1 = signal.get("move_1m")
    m5 = signal.get("move_5m")
    if state == "EARLY_UP" and range_position == "TOP":
        if m5 is not None and m5 > 0 and m1 is not None and m1 <= 0:
            return True
    if state == "EARLY_DOWN" and range_position == "BOTTOM":
        if m5 is not None and m5 < 0 and m1 is not None and m1 >= 0:
            return True
    return False


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
        return "blocked_continuation_top_exhaustion"
    if range_position == "BOTTOM" and signal_direction == "DOWN" and trend_state != "STRONG_DOWN":
        return "blocked_continuation_bottom_exhaustion"
    return None


def choose_model(state, signal=None):
    regime = signal.get("regime") if signal else None

    if regime == "NO_TRADE":
        if signal is not None:
            signal["selection_reason"] = "regime_no_trade"
        return "no_trade"

    if signal and signal.get("skip_candidate") is True:
        skip_reason = signal.get("skip_reason") or "no_trade"
        if skip_reason != "flat_early_signal":
            signal["selection_reason"] = skip_reason
            return "no_trade"

    trend_state = signal.get("trend_state") if signal else None
    range_position = signal.get("range_position") if signal else None
    ma_pct = signal.get("price_vs_ma_1h_pct") if signal else None

    if state == "EARLY_UP":
        if signal and range_position == "TOP" and _early_reversal_quality_ok(signal, state):
            if regime == "TREND":
                signal["selection_reason"] = "regime_trend_blocks_fade"
                return "no_trade"
            signal["selection_reason"] = "fade_selected_top_reversal"
            return "fade"
        if signal and trend_state in {"UP", "STRONG_UP"}:
            if regime == "RANGE":
                signal["selection_reason"] = "regime_range_blocks_continuation"
                return "no_trade"
            signal["selection_reason"] = "continuation_selected"
            return "continuation"
        if signal is not None:
            signal["selection_reason"] = "no_trade_weak_early_reversal"
        return "no_trade"

    if state == "EARLY_DOWN":
        if signal and range_position == "BOTTOM" and _early_reversal_quality_ok(signal, state):
            if regime == "TREND":
                signal["selection_reason"] = "regime_trend_blocks_fade"
                return "no_trade"
            signal["selection_reason"] = "fade_selected_bottom_reversal"
            return "fade"
        if signal and trend_state in {"DOWN", "STRONG_DOWN"}:
            if regime == "RANGE":
                signal["selection_reason"] = "regime_range_blocks_continuation"
                return "no_trade"
            signal["selection_reason"] = "continuation_selected"
            return "continuation"
        if signal is not None:
            signal["selection_reason"] = "no_trade_weak_early_reversal"
        return "no_trade"

    if state in {"CONFIRMED_UP", "CONFIRMED_DOWN"}:
        is_up = state == "CONFIRMED_UP"

        if trend_state == "FLAT":
            if signal and is_up and _weakening_follow_through_up(signal):
                if regime == "TREND":
                    signal["selection_reason"] = "regime_trend_blocks_fade"
                    return "no_trade"
                signal["selection_reason"] = "fade_selected_top_reversal"
                return "fade"
            if signal and not is_up and _weakening_follow_through_down(signal):
                if regime == "TREND":
                    signal["selection_reason"] = "regime_trend_blocks_fade"
                    return "no_trade"
                signal["selection_reason"] = "fade_selected_bottom_reversal"
                return "fade"
            if signal is not None:
                signal["selection_reason"] = "blocked_continuation_flat_context"
            return "no_trade"

        if is_up and range_position == "TOP":
            if (
                trend_state == "STRONG_UP"
                and signal and _all_momentum_positive(signal)
                and ma_pct is not None and ma_pct > 0
            ):
                if regime == "RANGE":
                    signal["selection_reason"] = "regime_range_blocks_continuation"
                    return "no_trade"
                signal["selection_reason"] = "continuation_selected"
                return "continuation"
            if signal and _weakening_follow_through_up(signal):
                if regime == "TREND":
                    signal["selection_reason"] = "regime_trend_blocks_fade"
                    return "no_trade"
                signal["selection_reason"] = "fade_selected_top_reversal"
                return "fade"
            if signal is not None:
                signal["selection_reason"] = "blocked_continuation_top_exhaustion"
            return "no_trade"

        if not is_up and range_position == "BOTTOM":
            if (
                trend_state == "STRONG_DOWN"
                and signal and _all_momentum_negative(signal)
                and ma_pct is not None and ma_pct < 0
            ):
                if regime == "RANGE":
                    signal["selection_reason"] = "regime_range_blocks_continuation"
                    return "no_trade"
                signal["selection_reason"] = "continuation_selected"
                return "continuation"
            if signal and _weakening_follow_through_down(signal):
                if regime == "TREND":
                    signal["selection_reason"] = "regime_trend_blocks_fade"
                    return "no_trade"
                signal["selection_reason"] = "fade_selected_bottom_reversal"
                return "fade"
            if signal is not None:
                signal["selection_reason"] = "blocked_continuation_bottom_exhaustion"
            return "no_trade"

        if regime == "RANGE":
            if signal is not None:
                signal["selection_reason"] = "regime_range_blocks_continuation"
            return "no_trade"
        if signal is not None:
            signal["selection_reason"] = "continuation_selected"
        return "continuation"

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
