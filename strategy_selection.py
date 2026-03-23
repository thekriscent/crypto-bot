def _imbalance(signal=None):
    if not signal:
        return 0
    return abs(signal.get("up_score", 0) - signal.get("down_score", 0))


def _has_exhaustion(signal=None):
    if not signal:
        return False

    move_1m = signal.get("move_1m") or 0
    move_3m = signal.get("move_3m") or 0
    range_position = signal.get("range_position")

    return (
        abs(move_1m) >= 0.0007
        or abs(move_3m) >= 0.0012
        or range_position in {"TOP", "BOTTOM"}
    )


def choose_model(state, signal=None):
    if signal and signal.get("skip_candidate"):
        return None

    if _imbalance(signal) < 5:
        return None

    if not _has_exhaustion(signal):
        return None

    return "fade"


def is_selected_model(model, state, signal=None):
    selected_model = choose_model(state, signal)
    return selected_model is not None and model == selected_model
