def choose_model(state, signal=None):
    if signal and signal.get("skip_candidate"):
        return None

    if state == "EARLY_DOWN":
        if (
            signal
            and signal.get("down_score", 0) > signal.get("up_score", 0)
            and signal.get("range_position") == "BOTTOM"
            and signal.get("trend_state") == "DOWN"
        ):
            return "continuation"
        return None

    if state == "EARLY_UP":
        if signal and signal.get("range_position") == "TOP":
            return "fade"
        return None

    if state == "CONFIRMED_DOWN":
        if signal and signal.get("volatility_state") == "LOW":
            return None
        if signal and signal.get("range_position") == "BOTTOM":
            return None
        return "continuation"

    if state == "CONFIRMED_UP":
        if signal and signal.get("volatility_state") == "LOW":
            return None
        if (
            signal
            and signal.get("range_position") == "TOP"
            and signal.get("trend_state") in {"FLAT", "DOWN"}
        ):
            return None
        return "continuation"

    return None


def is_selected_model(model, state, signal=None):
    selected_model = choose_model(state, signal)
    return selected_model is not None and model == selected_model
