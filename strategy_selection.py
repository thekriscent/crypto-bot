def choose_model(state):
    if state in ["EARLY_UP", "EARLY_DOWN"]:
        return "fade"
    if state in ["CONFIRMED_UP", "CONFIRMED_DOWN"]:
        return "continuation"
    return None


def is_selected_model(model, state):
    return model == choose_model(state)
