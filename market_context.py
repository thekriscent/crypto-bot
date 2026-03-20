import math
import statistics


VOLATILITY_WINDOW_SECONDS = 5 * 60
RANGE_1H_SECONDS = 60 * 60
RANGE_24H_SECONDS = 24 * 60 * 60
TREND_SHORT_SECONDS = 15 * 60
TREND_LONG_SECONDS = 60 * 60
MA_5M_SECONDS = 5 * 60
MA_15M_SECONDS = 15 * 60
MA_1H_SECONDS = 60 * 60


def prices_in_window(price_history, now_ts, window_seconds):
    cutoff = now_ts - window_seconds
    return [(ts, px) for ts, px in price_history if ts >= cutoff]


def has_full_window(price_history, now_ts, window_seconds):
    cutoff = now_ts - window_seconds
    return any(ts <= cutoff for ts, _ in price_history)


def volatility_state(price_history, now_ts):
    window = prices_in_window(price_history, now_ts, VOLATILITY_WINDOW_SECONDS)
    prices = [price for _, price in window]
    if len(prices) < 3:
        return "LOW"

    returns = []
    for previous, current in zip(prices, prices[1:]):
        if previous <= 0 or current <= 0:
            continue
        returns.append(math.log(current / previous))

    if len(returns) < 2:
        return "LOW"

    realized_vol = statistics.pstdev(returns)
    if realized_vol < 0.0003:
        return "LOW"
    if realized_vol < 0.0008:
        return "MEDIUM"
    return "HIGH"


def range_position(price_history, now_ts, current_price):
    if has_full_window(price_history, now_ts, RANGE_24H_SECONDS):
        window = prices_in_window(price_history, now_ts, RANGE_24H_SECONDS)
    elif has_full_window(price_history, now_ts, RANGE_1H_SECONDS):
        window = prices_in_window(price_history, now_ts, RANGE_1H_SECONDS)
    else:
        window = price_history

    prices = [price for _, price in window]
    if not prices:
        return "MIDDLE"

    low = min(prices)
    high = max(prices)
    if high <= low:
        return "MIDDLE"

    position = (current_price - low) / (high - low)
    if position <= 0.33:
        return "BOTTOM"
    if position >= 0.67:
        return "TOP"
    return "MIDDLE"


def trend_state(price_history, now_ts):
    short_window = prices_in_window(price_history, now_ts, TREND_SHORT_SECONDS)
    long_window = prices_in_window(price_history, now_ts, TREND_LONG_SECONDS)

    short_prices = [price for _, price in short_window]
    long_prices = [price for _, price in long_window]

    if len(short_prices) < 3 or len(long_prices) < 3:
        return "FLAT"

    short_avg = sum(short_prices) / len(short_prices)
    long_avg = sum(long_prices) / len(long_prices)
    if long_avg == 0:
        return "FLAT"

    slope = (short_avg - long_avg) / long_avg
    if slope >= 0.0010:
        return "UP"
    if slope <= -0.0010:
        return "DOWN"
    return "FLAT"


def window_high_low(price_history, now_ts, window_seconds, current_price):
    window = prices_in_window(price_history, now_ts, window_seconds)
    prices = [price for _, price in window]
    if not prices:
        return round(current_price, 2), round(current_price, 2)
    return round(max(prices), 2), round(min(prices), 2)


def moving_average(price_history, now_ts, window_seconds):
    window = prices_in_window(price_history, now_ts, window_seconds)
    prices = [price for _, price in window]
    if not prices:
        return None
    return sum(prices) / len(prices)


def pct_distance(current_price, reference_price):
    if reference_price in (None, 0):
        return None
    return (current_price - reference_price) / reference_price


def compute_traditional_indicators(price_history, now_ts, current_price):
    ma_5m = moving_average(price_history, now_ts, MA_5M_SECONDS)
    ma_15m = moving_average(price_history, now_ts, MA_15M_SECONDS)
    ma_1h = moving_average(price_history, now_ts, MA_1H_SECONDS)
    high_1h, low_1h = window_high_low(price_history, now_ts, RANGE_1H_SECONDS, current_price)
    high_24h, low_24h = window_high_low(price_history, now_ts, RANGE_24H_SECONDS, current_price)

    return {
        "high_1h": high_1h,
        "low_1h": low_1h,
        "high_24h": high_24h,
        "low_24h": low_24h,
        "ma_5m": round(ma_5m, 2) if ma_5m is not None else None,
        "ma_15m": round(ma_15m, 2) if ma_15m is not None else None,
        "ma_1h": round(ma_1h, 2) if ma_1h is not None else None,
        "price_vs_ma_5m_pct": round(pct_distance(current_price, ma_5m), 4) if ma_5m is not None else None,
        "price_vs_ma_15m_pct": round(pct_distance(current_price, ma_15m), 4) if ma_15m is not None else None,
        "price_vs_ma_1h_pct": round(pct_distance(current_price, ma_1h), 4) if ma_1h is not None else None,
    }


def compute_market_context(price_history, now_ts, current_price, news_flag):
    current_volatility = volatility_state(price_history, now_ts)
    return {
        "volatility_state": current_volatility,
        "range_position": range_position(price_history, now_ts, current_price),
        "news_flag": news_flag,
        "trend_state": trend_state(price_history, now_ts),
        "skip_candidate": bool(news_flag or current_volatility == "HIGH"),
        **compute_traditional_indicators(price_history, now_ts, current_price),
    }
