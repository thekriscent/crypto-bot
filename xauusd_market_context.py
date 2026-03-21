from market_context import compute_market_context


def compute_xauusd_market_context(price_history, now_ts, current_price, news_flag):
    # Reuse the existing market context architecture for now. If XAUUSD needs
    # different volatility or range behavior later, isolate that tuning here.
    return compute_market_context(price_history, now_ts, current_price, news_flag)
