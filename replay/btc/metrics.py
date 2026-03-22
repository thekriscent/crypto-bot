from replay.shared.types import PricePoint


WINDOWS = (60, 180, 300)


def get_price_n_seconds_ago(history: list[PricePoint], now_ts: float, seconds_back: int):
    target = now_ts - seconds_back
    candidates = [point for point in history if point.timestamp <= target]
    if not candidates:
        return None
    return candidates[-1].price


def recent_tick_direction(history: list[PricePoint]):
    if len(history) < 3:
        return None

    p1 = history[-3].price
    p2 = history[-2].price
    p3 = history[-1].price
    if p3 > p2 > p1:
        return "UP"
    if p3 < p2 < p1:
        return "DOWN"
    return "MIXED"


def pct_change(old_price, new_price):
    if old_price is None or old_price == 0:
        return None
    return (new_price - old_price) / old_price


def compute_metrics(history: list[PricePoint], now_ts: float, current_price: float):
    p1 = get_price_n_seconds_ago(history, now_ts, WINDOWS[0])
    p3 = get_price_n_seconds_ago(history, now_ts, WINDOWS[1])
    p5 = get_price_n_seconds_ago(history, now_ts, WINDOWS[2])
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
        "recent_tick_direction": recent_tick_direction(history),
    }
