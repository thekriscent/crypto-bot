from market_context import compute_market_context

from replay.btc.adapters.btc_selection_adapter import choose_selected_model
from replay.btc.adapters.btc_signal_adapter import classify_signal_state
from replay.btc.metrics import compute_metrics
from replay.shared.utils import epoch_to_iso


def classify_history(history, now_ts, current_price, news_flag=False):
    metrics = compute_metrics(history, now_ts, current_price)
    state, up_score, down_score = classify_signal_state(metrics)
    context_input = [(point.timestamp, point.price) for point in history]
    context = compute_market_context(context_input, now_ts, current_price, news_flag)

    if not state:
        return None

    signal = {
        "timestamp_utc": epoch_to_iso(now_ts),
        "state": state,
        "direction": "UP" if "UP" in state else "DOWN",
        "price_now": round(current_price, 2),
        "move_1m": metrics["move_1m"],
        "move_3m": metrics["move_3m"],
        "move_5m": metrics["move_5m"],
        "up_score": up_score,
        "down_score": down_score,
        **context,
    }
    signal["selected_model"] = choose_selected_model(state, signal)
    return signal
