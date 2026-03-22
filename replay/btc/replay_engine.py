from dataclasses import asdict
from pathlib import Path

from replay.btc.adapters.btc_selection_adapter import choose_selected_model
from replay.btc.adapters.btc_simulation_adapter import calc_pnl_pct, expected_trade_direction
from replay.btc.classifier import classify_history
from replay.btc.event_store import ensure_output_dir, load_scenario_headlines, load_scenario_meta
from replay.btc.event_schema import ReplaySimulation
from replay.shared.types import PricePoint
from replay.shared.utils import epoch_to_iso, iso_to_epoch, write_json


CHECKPOINTS = (60, 180, 300)


def build_synthetic_price_series(meta: dict):
    start_ts = iso_to_epoch(meta["start_utc"])
    prices = [
        17100.0,
        17080.0,
        17020.0,
        16940.0,
        16860.0,
        16790.0,
        16720.0,
        16640.0,
        16590.0,
        16510.0,
        16480.0,
    ]
    return [
        PricePoint(timestamp=start_ts + (index * 60), price=price)
        for index, price in enumerate(prices)
    ]


def _headline_news_flag(headlines: list[dict], timestamp_utc: str):
    current_ts = iso_to_epoch(timestamp_utc)
    for headline in headlines:
        headline_ts = iso_to_epoch(headline["timestamp_utc"])
        if 0 <= current_ts - headline_ts <= 300:
            return True
    return False


def _future_price_at_or_after(points: list[PricePoint], target_ts: float):
    for point in points:
        if point.timestamp >= target_ts:
            return point.price
    return points[-1].price


def build_simulations(signal: dict, all_points: list[PricePoint], current_index: int):
    future_points = all_points[current_index:]
    selected_model = choose_selected_model(signal["state"], signal)
    simulations = []
    for model in ("continuation", "fade"):
        trade_direction = expected_trade_direction(model, signal["direction"], signal["state"])
        checkpoints = {}
        for checkpoint in CHECKPOINTS:
            future_price = _future_price_at_or_after(
                future_points,
                iso_to_epoch(signal["timestamp_utc"]) + checkpoint,
            )
            checkpoints[checkpoint] = {
                "price": round(future_price, 2),
                "pnl_pct": round(calc_pnl_pct(trade_direction, signal["price_now"], future_price), 4),
            }
        simulations.append(
            asdict(
                ReplaySimulation(
                    model=model,
                    signal_state=signal["state"],
                    signal_direction=signal["direction"],
                    trade_direction=trade_direction,
                    entry_price=signal["price_now"],
                    checkpoints=checkpoints,
                    selected=1 if model == selected_model else 0,
                )
            )
        )
    return simulations


def run_replay(scenario_id: str, output_dir: Path | None = None):
    meta = load_scenario_meta(scenario_id)
    headlines = load_scenario_headlines(scenario_id)
    price_points = build_synthetic_price_series(meta)
    history = []
    signals = []

    for index, point in enumerate(price_points):
        history.append(point)
        news_flag = _headline_news_flag(headlines, epoch_to_iso(point.timestamp))
        signal = classify_history(history, point.timestamp, point.price, news_flag=news_flag)
        if signal:
            signal["simulations"] = build_simulations(signal, price_points, index)
            signals.append(signal)

    result = {
        "scenario_id": scenario_id,
        "meta": meta,
        "headline_count": len(headlines),
        "signal_count": len(signals),
        "signals": signals,
    }

    if output_dir is None:
        output_dir = ensure_output_dir(scenario_id)
    write_json(output_dir / "result.json", result)
    return result
