import importlib
import sys
import types


def _load_trend_bot():
    try:
        return importlib.import_module("trend_bot")
    except ModuleNotFoundError as error:
        if error.name != "requests":
            raise
        sys.modules.setdefault("requests", types.ModuleType("requests"))
        return importlib.import_module("trend_bot")


def classify_signal_state(metrics):
    trend_bot = _load_trend_bot()
    return trend_bot.classify_state(metrics)
