def choose_model(state, signal=None):
    if signal and signal.get("skip_candidate") is True:
        return None

    if state == "EARLY_DOWN":
        if signal and signal.get("down_score", 0) > signal.get("up_score", 0):
            return "continuation"
        return None

    if state == "EARLY_UP":
        return "fade"

    if state in ["CONFIRMED_UP", "CONFIRMED_DOWN"]:
        return "continuation"

    return None


def is_selected_model(model, state, signal=None):
    selected_model = choose_model(state, signal)
    return selected_model is not None and model == selected_model
