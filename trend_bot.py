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
from market_context import compute_market_context
from strategy_selection import choose_model

COINBASE_TICKER_URL = "https://api.coinbase.com/v2/prices/BTC-USD/spot"
LOG_FILE = "trend_bot_log.json"
DB_FILE = "trend_bot.db"

SCAN_INTERVAL = 5
COOLDOWN_SECONDS = 60

WINDOWS = [60, 180, 300]  # 1m, 3m, 5m
CHECKPOINTS = [60, 180, 300]

# Scoring thresholds
EARLY_SCORE_THRESHOLD = 4
CONFIRMED_SCORE_THRESHOLD = 6
PULLBACK_SCORE_THRESHOLD = 4
CONTEXT_HISTORY_SECONDS = (24 * 60 * 60) + 60

price_history = []
last_signal_time = 0
open_simulations = []


def get_btc_spot_price():
    response = requests.get(COINBASE_TICKER_URL, timeout=10)
    response.raise_for_status()
    data = response.json()
    return float(data["data"]["amount"])


def prune_history(now_ts):
    global price_history
    cutoff = now_ts - max(CONTEXT_HISTORY_SECONDS, max(WINDOWS) + 60)
    price_history = [(ts, px) for ts, px in price_history if ts >= cutoff]


def get_price_n_seconds_ago(now_ts, seconds_back):
    target = now_ts - seconds_back
    candidates = [item for item in price_history if item[0] <= target]
    if not candidates:
        return None
    return candidates[-1][1]


def pct_change(old_price, new_price):
    if old_price is None or old_price == 0:
        return None
    return (new_price - old_price) / old_price


def opposite_direction(direction):
    return "DOWN" if direction == "UP" else "UP"


def simulation_trade_direction(model, signal_direction):
    if model == "continuation":
        return signal_direction
    if model == "fade":
        return opposite_direction(signal_direction)
    return signal_direction


def recent_tick_direction():
    if len(price_history) < 3:
        return None

    p1 = price_history[-3][1]
    p2 = price_history[-2][1]
    p3 = price_history[-1][1]

    if p3 > p2 > p1:
        return "UP"
    if p3 < p2 < p1:
        return "DOWN"
    return "MIXED"


def trend_metrics(now_ts, current_price):
    p1 = get_price_n_seconds_ago(now_ts, 60)
    p3 = get_price_n_seconds_ago(now_ts, 180)
    p5 = get_price_n_seconds_ago(now_ts, 300)

    m1 = pct_change(p1, current_price)
    m3 = pct_change(p3, current_price)
    m5 = pct_change(p5, current_price)

    return {
        "price_1m_ago": p1,
        "price_3m_ago": p3,
        "price_5m_ago": p5,
        "move_1m": round(m1, 4) if m1 is not None else None,
        "move_3m": round(m3, 4) if m3 is not None else None,
        "move_5m": round(m5, 4) if m5 is not None else None,
        "recent_tick_direction": recent_tick_direction(),
    }


def score_up(metrics):
    score = 0

    m1 = metrics["move_1m"]
    m3 = metrics["move_3m"]
    m5 = metrics["move_5m"]
    tick = metrics["recent_tick_direction"]

    # 1m
    if m1 is not None:
        if m1 >= 0.0006:
            score += 2
        elif m1 >= 0.0003:
            score += 1
        elif m1 <= -0.0003:
            score -= 2

    # 3m
    if m3 is not None:
        if m3 >= 0.0012:
            score += 2
        elif m3 >= 0.0008:
            score += 1
        elif m3 <= -0.0008:
            score -= 2

    # 5m
    if m5 is not None:
        if m5 >= 0.0020:
            score += 2
        elif m5 >= 0.0012:
            score += 1
        elif m5 <= -0.0010:
            score -= 2

    if tick == "UP":
        score += 1
    elif tick == "DOWN":
        score -= 1

    return score


def score_down(metrics):
    score = 0

    m1 = metrics["move_1m"]
    m3 = metrics["move_3m"]
    m5 = metrics["move_5m"]
    tick = metrics["recent_tick_direction"]

    # 1m
    if m1 is not None:
        if m1 <= -0.0006:
            score += 2
        elif m1 <= -0.0003:
            score += 1
        elif m1 >= 0.0003:
            score -= 2

    # 3m
    if m3 is not None:
        if m3 <= -0.0012:
            score += 2
        elif m3 <= -0.0008:
            score += 1
        elif m3 >= 0.0008:
            score -= 2

    # 5m
    if m5 is not None:
        if m5 <= -0.0020:
            score += 2
        elif m5 <= -0.0012:
            score += 1
        elif m5 >= 0.0010:
            score -= 2

    if tick == "DOWN":
        score += 1
    elif tick == "UP":
        score -= 1

    return score


def classify_state(metrics):
    m1 = metrics["move_1m"]
    m3 = metrics["move_3m"]
    m5 = metrics["move_5m"]

    up_score = score_up(metrics)
    down_score = score_down(metrics)

    # Need enough history before classifying
    if m1 is None or m3 is None:
        return None, up_score, down_score

    # Confirmed trend
    if m5 is not None:
        if up_score >= CONFIRMED_SCORE_THRESHOLD:
            return "CONFIRMED_UP", up_score, down_score
        if down_score >= CONFIRMED_SCORE_THRESHOLD:
            return "CONFIRMED_DOWN", up_score, down_score

    # Early trend
    if up_score >= EARLY_SCORE_THRESHOLD and (m3 is not None and m3 > 0):
        return "EARLY_UP", up_score, down_score
    if down_score >= EARLY_SCORE_THRESHOLD and (m3 is not None and m3 < 0):
        return "EARLY_DOWN", up_score, down_score

    # Pullback in larger trend
    if m3 is not None and m5 is not None:
        if m3 > 0 and m5 > 0 and m1 is not None and m1 < 0 and up_score >= PULLBACK_SCORE_THRESHOLD:
            return "PULLBACK_UP", up_score, down_score
        if m3 < 0 and m5 < 0 and m1 is not None and m1 > 0 and down_score >= PULLBACK_SCORE_THRESHOLD:
            return "PULLBACK_DOWN", up_score, down_score

    return None, up_score, down_score


def compute_signal(now_ts, current_price):
    global last_signal_time

    metrics = trend_metrics(now_ts, current_price)
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


def create_simulations(signal, now_ts):
    return [
        {
            "event": "simulation_result",
            "model": "continuation",
            "signal_state": signal["state"],
            "signal_direction": signal["direction"],
            "trade_direction": simulation_trade_direction("continuation", signal["direction"]),
            "entry_price": signal["price_now"],
            "signal_time": now_ts,
            "captured": {},
            "done": False,
            "move_1m": signal["move_1m"],
            "move_3m": signal["move_3m"],
            "move_5m": signal["move_5m"],
            "up_score": signal["up_score"],
            "down_score": signal["down_score"],
        },
        {
            "event": "simulation_result",
            "model": "fade",
            "signal_state": signal["state"],
            "signal_direction": signal["direction"],
            "trade_direction": simulation_trade_direction("fade", signal["direction"]),
            "entry_price": signal["price_now"],
            "signal_time": now_ts,
            "captured": {},
            "done": False,
            "move_1m": signal["move_1m"],
            "move_3m": signal["move_3m"],
            "move_5m": signal["move_5m"],
            "up_score": signal["up_score"],
            "down_score": signal["down_score"],
        },
    ]


def calc_pnl_pct(trade_direction, entry_price, current_price):
    if trade_direction == "UP":
        return (current_price - entry_price) / entry_price
    return (entry_price - current_price) / entry_price


def update_simulations(now_ts, current_price):
    completed = []

    for sim in open_simulations:
        if sim["done"]:
            continue

        elapsed = int(now_ts - sim["signal_time"])

        for checkpoint in CHECKPOINTS:
            if checkpoint not in sim["captured"] and elapsed >= checkpoint:
                pnl_pct = calc_pnl_pct(
                    sim["trade_direction"],
                    sim["entry_price"],
                    current_price,
                )
                sim["captured"][checkpoint] = {
                    "price": round(current_price, 2),
                    "pnl_pct": round(pnl_pct, 4),
                }

        if all(cp in sim["captured"] for cp in CHECKPOINTS):
            sim["done"] = True
            completed.append(sim)

    return completed


def print_simulation_result(sim):
    print("\nSIM RESULT")
    print(f"Model: {sim['model']}")
    print(f"State: {sim['signal_state']}")
    print(f"Signal direction: {sim['signal_direction']}")
    print(f"Trade direction: {sim['trade_direction']}")
    print(f"Entry: {sim['entry_price']}")
    print(
        f"1m: {sim['move_1m']} | "
        f"3m: {sim['move_3m']} | "
        f"5m: {sim['move_5m']} | "
        f"up_score: {sim['up_score']} | "
        f"down_score: {sim['down_score']}"
    )

    for checkpoint in CHECKPOINTS:
        cp = sim["captured"][checkpoint]
        print(f"+{checkpoint}s -> {cp['price']} | pnl {cp['pnl_pct']}")
    print()


def build_signal_context(now_ts, current_price, observed_at_utc):
    news_flag = recent_news_exists(observed_at_utc, lookback_seconds=5 * 60)
    return compute_market_context(price_history, now_ts, current_price, news_flag)


def persist_pending_checkpoints(sim):
    persisted = sim.setdefault("checkpoint_persisted", set())
    for checkpoint in CHECKPOINTS:
        if checkpoint in sim["captured"] and checkpoint not in persisted:
            persist_simulation_checkpoint(sim, checkpoint)
            persisted.add(checkpoint)


def normalize_recovered_simulations(simulations):
    for sim in simulations:
        expected_direction = simulation_trade_direction(
            sim["model"],
            sim["signal_direction"],
        )
        if sim.get("trade_direction") != expected_direction:
            sim["trade_direction"] = expected_direction
            sync_open_simulation(sim)
    return simulations


def run():
    init_storage(db_filename=DB_FILE)
    open_simulations.extend(normalize_recovered_simulations(recover_open_simulations()))
    print("Starting scored trend bot...\n")
    if open_simulations:
        print(f"Recovered {len(open_simulations)} open simulations from SQLite.\n")

    while True:
        stage = "idle"
        observed_at_utc = None
        current_price = None
        try:
            now_ts = time.time()
            stage = "fetch_price"
            current_price = get_btc_spot_price()
            observed_at_utc = datetime.now(timezone.utc).isoformat()

            price_history.append((now_ts, current_price))
            prune_history(now_ts)

            stage = "compute_signal"
            signal, diagnostics = compute_signal(now_ts, current_price)

            stage = "log_tick"
            log_tick(
                price=current_price,
                observed_at_epoch=now_ts,
                observed_at_utc=observed_at_utc,
                source=COINBASE_TICKER_URL,
                diagnostics=diagnostics,
            )

            print(
                f"BTC: {current_price:.2f} | "
                f"1m: {diagnostics['move_1m']} | "
                f"3m: {diagnostics['move_3m']} | "
                f"5m: {diagnostics['move_5m']} | "
                f"tick: {diagnostics['recent_tick_direction']} | "
                f"up_score: {diagnostics['up_score']} | "
                f"down_score: {diagnostics['down_score']} | "
                f"state: {diagnostics['state_candidate']} | "
                f"cooldown_ok: {diagnostics['cooldown_ok']}"
            )

            if signal:
                stage = "build_signal_context"
                signal.update(build_signal_context(now_ts, current_price, observed_at_utc))
                print("\nTREND SIGNAL")
                print(signal)
                print()

                stage = "log_signal"
                log_entry(signal, LOG_FILE)
                stage = "create_open_simulations"
                new_simulations = create_simulations(signal, now_ts)
                for sim in new_simulations:
                    for field in (
                        "volatility_state",
                        "range_position",
                        "news_flag",
                        "trend_state",
                        "skip_candidate",
                    ):
                        sim[field] = signal[field]
                    persist_open_simulation(sim)
                    open_simulations.append(sim)

            stage = "update_simulations"
            completed = update_simulations(now_ts, current_price)

            stage = "persist_simulation_checkpoints"
            for sim in open_simulations:
                persist_pending_checkpoints(sim)

            stage = "finalize_simulations"
            for sim in open_simulations:
                if not sim["done"] or sim.get("finalized"):
                    continue
                sim["selected"] = (sim["model"] == choose_model(sim["signal_state"]))
                if all(cp in sim.get("checkpoint_persisted", set()) for cp in CHECKPOINTS):
                    complete_persisted_simulation(sim, LOG_FILE)
                    sim["finalized"] = True
                    print_simulation_result(sim)

            open_simulations[:] = [s for s in open_simulations if not s.get("finalized")]

        except Exception as e:
            record_error_event(
                source=f"trend_bot.{stage}",
                error=e,
                context={
                    "observed_at_utc": observed_at_utc,
                    "current_price": current_price,
                },
            )
            print(f"Error: {e}")

        time.sleep(SCAN_INTERVAL)


if __name__ == "__main__":
    run()
