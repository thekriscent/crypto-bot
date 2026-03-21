import os
import random
import time
from datetime import datetime, timezone

import requests

from journal import (
    complete_persisted_simulation,
    init_storage,
    log_entry,
    log_tick,
    persist_open_simulation,
    persist_simulation_checkpoint,
    recent_news_exists,
    record_error_event,
    recover_open_simulations,
    sync_open_simulation,
)
from xauusd_config import (
    CHECKPOINTS,
    CONTEXT_HISTORY_SECONDS,
    COOLDOWN_SECONDS,
    DB_FILE,
    DEMO_PRICE,
    LOG_FILE,
    MARKET,
    PRICE_SOURCE_URLS,
    SCAN_INTERVAL,
    SIMULATE_PRICE,
    SIMULATION_BASE_PRICE,
)
from xauusd_market_context import compute_xauusd_market_context, xauusd_skip_decision
from xauusd_strategy import (
    calc_pnl_pct,
    choose_model,
    classify_state,
    compute_metrics,
    create_simulations,
    expected_trade_direction,
)

price_history = []
open_simulations = []
last_signal_time = 0
simulated_price = SIMULATION_BASE_PRICE


def get_simulated_xauusd_price():
    global simulated_price

    # dev simulation mode
    drift = random.uniform(-0.001, 0.001)
    if simulated_price <= 0:
        simulated_price = SIMULATION_BASE_PRICE
    simulated_price = round(simulated_price * (1 + drift), 2)
    return simulated_price


def get_xauusd_spot_price():
    # A production-grade XAUUSD API can be swapped in here later without
    # changing the rest of the scaffold.
    if SIMULATE_PRICE:
        return get_simulated_xauusd_price()

    if DEMO_PRICE:
        return float(DEMO_PRICE)

    last_error = None
    for url in PRICE_SOURCE_URLS:
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            payload = response.json()
            return float(_extract_xauusd_price(payload, url))
        except requests.RequestException as error:
            print(f"XAUUSD price API failed for {url}: {error}")
            last_error = error
        except ValueError as error:
            print(f"XAUUSD price API failed for {url}: invalid JSON response")
            last_error = error
        except RuntimeError as error:
            print(f"XAUUSD price API failed for {url}: {error}")
            last_error = error

    raise RuntimeError("Failed to fetch XAUUSD price from all configured public APIs") from last_error


def _extract_xauusd_price(payload, source_url):
    if "finance.yahoo.com" in source_url:
        try:
            return payload["chart"]["result"][0]["meta"]["regularMarketPrice"]
        except (KeyError, IndexError, TypeError) as error:
            raise RuntimeError("response missing Yahoo regularMarketPrice") from error

    if isinstance(payload, dict):
        price = payload.get("price")
        if price is not None:
            return price

    if isinstance(payload, list) and payload:
        first_item = payload[0]
        if isinstance(first_item, dict):
            price = first_item.get("gold")
            if price is not None:
                return price

    raise RuntimeError("response missing expected price field")


def prune_history(now_ts):
    global price_history
    cutoff = now_ts - max(CONTEXT_HISTORY_SECONDS, max(CHECKPOINTS) + 60)
    price_history = [(ts, px) for ts, px in price_history if ts >= cutoff]


def build_signal(now_ts, current_price):
    global last_signal_time

    metrics = compute_metrics(price_history, now_ts, current_price)
    state, up_score, down_score = classify_state(metrics)

    diagnostics = {
        "move_1m": metrics["move_1m"],
        "move_3m": metrics["move_3m"],
        "move_5m": metrics["move_5m"],
        "recent_tick_direction": metrics["recent_tick_direction"],
        "up_score": up_score,
        "down_score": down_score,
        "state_candidate": state,
        "cooldown_ok": (now_ts - last_signal_time >= COOLDOWN_SECONDS),
    }

    if not state:
        return None, diagnostics

    if now_ts - last_signal_time < COOLDOWN_SECONDS:
        return None, diagnostics

    direction = "UP" if "UP" in state else "DOWN"
    last_signal_time = now_ts

    signal = {
        "event": "signal",
        "type": "trend_signal",
        "state": state,
        "direction": direction,
        "price_now": round(current_price, 2),
        "move_1m": metrics["move_1m"],
        "move_3m": metrics["move_3m"],
        "move_5m": metrics["move_5m"],
        "up_score": up_score,
        "down_score": down_score,
    }
    return signal, diagnostics


def build_signal_context(now_ts, current_price, observed_at_utc):
    news_flag = recent_news_exists(observed_at_utc, lookback_seconds=5 * 60)
    return compute_xauusd_market_context(price_history, now_ts, current_price, news_flag)


def persist_pending_checkpoints(sim):
    persisted = sim.setdefault("checkpoint_persisted", set())
    for checkpoint in CHECKPOINTS:
        if checkpoint in sim["captured"] and checkpoint not in persisted:
            persist_simulation_checkpoint(sim, checkpoint)
            persisted.add(checkpoint)


def update_simulations(now_ts, current_price):
    for sim in open_simulations:
        if sim["done"]:
            continue

        elapsed = int(now_ts - sim["signal_time"])
        for checkpoint in CHECKPOINTS:
            if checkpoint not in sim["captured"] and elapsed >= checkpoint:
                pnl_pct = calc_pnl_pct(sim["trade_direction"], sim["entry_price"], current_price)
                sim["captured"][checkpoint] = {
                    "price": round(current_price, 2),
                    "pnl_pct": round(pnl_pct, 4),
                }

        if all(checkpoint in sim["captured"] for checkpoint in CHECKPOINTS):
            sim["done"] = True


def normalize_recovered_simulations(simulations):
    for sim in simulations:
        expected_direction = expected_trade_direction(
            sim["model"],
            sim["signal_direction"],
            sim.get("signal_state"),
        )
        if sim.get("trade_direction") != expected_direction:
            sim["trade_direction"] = expected_direction
            sync_open_simulation(sim)
    return simulations


def print_signal(prefix, payload):
    print(prefix)
    print(payload)
    print()


def print_simulation_result(sim):
    print("\nXAUUSD SIM RESULT")
    print(f"Model: {sim['model']}")
    print(f"State: {sim['signal_state']}")
    print(f"Trade direction: {sim['trade_direction']}")
    print(f"Entry: {sim['entry_price']}")
    for checkpoint in CHECKPOINTS:
        cp = sim["captured"][checkpoint]
        print(f"+{checkpoint}s -> {cp['price']} | pnl {cp['pnl_pct']}")
    print()


def apply_signal_context(sim, signal):
    for field in (
        "volatility_state",
        "range_position",
        "news_flag",
        "trend_state",
        "skip_candidate",
        "skip_reason",
        "selection_reason",
        "high_1h",
        "low_1h",
        "high_24h",
        "low_24h",
        "ma_5m",
        "ma_15m",
        "ma_1h",
        "price_vs_ma_5m_pct",
        "price_vs_ma_15m_pct",
        "price_vs_ma_1h_pct",
    ):
        sim[field] = signal[field]


def run():
    init_storage(db_filename=DB_FILE, market=MARKET)
    open_simulations.extend(normalize_recovered_simulations(recover_open_simulations()))
    print("Starting XAUUSD scaffold bot...\n")

    while True:
        stage = "idle"
        observed_at_utc = None
        current_price = None
        try:
            now_ts = time.time()
            stage = "fetch_price"
            current_price = get_xauusd_spot_price()
            observed_at_utc = datetime.now(timezone.utc).isoformat()

            price_history.append((now_ts, current_price))
            prune_history(now_ts)

            stage = "compute_signal"
            signal, diagnostics = build_signal(now_ts, current_price)

            stage = "log_tick"
            log_tick(
                price=current_price,
                observed_at_epoch=now_ts,
                observed_at_utc=observed_at_utc,
                source="env:XAUUSD_DEMO_PRICE" if DEMO_PRICE else PRICE_SOURCE_URLS[0],
                diagnostics=diagnostics,
            )

            print(
                f"XAUUSD: {current_price:.2f} | "
                f"1m: {diagnostics['move_1m']} | "
                f"3m: {diagnostics['move_3m']} | "
                f"5m: {diagnostics['move_5m']} | "
                f"up_score: {diagnostics['up_score']} | "
                f"down_score: {diagnostics['down_score']} | "
                f"state: {diagnostics['state_candidate']} | "
                f"cooldown_ok: {diagnostics['cooldown_ok']}"
            )

            if signal:
                stage = "build_signal_context"
                signal.update(build_signal_context(now_ts, current_price, observed_at_utc))
                signal["skip_candidate"], signal["skip_reason"] = xauusd_skip_decision(
                    signal["state"],
                    signal["direction"],
                    signal,
                )
                choose_model(signal["state"], signal)
                print_signal("XAUUSD TREND SIGNAL", signal)

                stage = "log_signal"
                log_entry(signal, LOG_FILE)

                stage = "create_open_simulations"
                for sim in create_simulations(signal, now_ts):
                    apply_signal_context(sim, signal)
                    persist_open_simulation(sim)
                    open_simulations.append(sim)

            stage = "update_simulations"
            update_simulations(now_ts, current_price)

            stage = "persist_checkpoints"
            for sim in open_simulations:
                persist_pending_checkpoints(sim)

            stage = "finalize_simulations"
            for sim in open_simulations:
                if not sim["done"] or sim.get("finalized"):
                    continue

                selected_model = choose_model(sim["signal_state"], sim)
                sim["selected"] = 1 if sim["model"] == selected_model else 0
                if sim["selected"] == 0:
                    if sim.get("skip_candidate") is True:
                        sim["skip_reason"] = sim.get("skip_reason") or "SKIP_CANDIDATE_TRUE"
                    elif sim.get("selection_reason") in {
                        "blocked_top_up_not_strong",
                        "blocked_bottom_down_not_strong",
                    }:
                        sim["skip_reason"] = sim["selection_reason"]
                    elif sim.get("selection_reason") == "no_trade":
                        sim["skip_reason"] = sim.get("skip_reason") or "no_trade"

                if all(cp in sim.get("checkpoint_persisted", set()) for cp in CHECKPOINTS):
                    complete_persisted_simulation(sim, LOG_FILE)
                    sim["finalized"] = True
                    print_simulation_result(sim)

            open_simulations[:] = [sim for sim in open_simulations if not sim.get("finalized")]

        except Exception as error:
            record_error_event(
                source=f"xauusd_bot.{stage}",
                error=error,
                context={
                    "observed_at_utc": observed_at_utc,
                    "current_price": current_price,
                    "pid": os.getpid(),
                },
            )
            print(f"XAUUSD scaffold error: {error}")

        time.sleep(SCAN_INTERVAL)


if __name__ == "__main__":
    run()
