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


def expected_trade_direction(model, signal_direction, signal_state=None):
    trend_bot = _load_trend_bot()
    return trend_bot.expected_trade_direction(model, signal_direction, signal_state)


def calc_pnl_pct(trade_direction, entry_price, current_price):
    trend_bot = _load_trend_bot()
    return trend_bot.calc_pnl_pct(trade_direction, entry_price, current_price)
