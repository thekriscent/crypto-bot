import argparse
import json
import sqlite3
from pathlib import Path

from storage import DEFAULT_MARKET, ensure_market, initialize_database
from strategy_selection import choose_model


def connect(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def load_json_entries(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("JSON log must contain a list of entries.")
    return data


def find_existing_event_log_id(conn, market_id, entry):
    payload_json = json.dumps(entry, ensure_ascii=False, sort_keys=True)
    row = conn.execute(
        """
        SELECT id
        FROM event_log
        WHERE market_id = ?
          AND timestamp_utc = ?
          AND event = ?
          AND payload_json = ?
        """,
        (
            market_id,
            entry["timestamp_utc"],
            entry.get("event", "unknown"),
            payload_json,
        ),
    ).fetchone()
    return row[0] if row else None


def insert_event_log(conn, market_id, entry):
    payload_json = json.dumps(entry, ensure_ascii=False, sort_keys=True)
    cursor = conn.execute(
        """
        INSERT INTO event_log (market_id, timestamp_utc, event, payload_json)
        VALUES (?, ?, ?, ?)
        """,
        (
            market_id,
            entry["timestamp_utc"],
            entry.get("event", "unknown"),
            payload_json,
        ),
    )
    return cursor.lastrowid


def insert_signal(conn, market_id, event_log_id, entry):
    conn.execute(
        """
        INSERT INTO signals (
            event_log_id,
            market_id,
            timestamp_utc,
            signal_type,
            state,
            direction,
            price_now,
            move_1m,
            move_3m,
            move_5m,
            up_score,
            down_score
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_log_id,
            market_id,
            entry["timestamp_utc"],
            entry.get("type"),
            entry["state"],
            entry["direction"],
            entry["price_now"],
            entry.get("move_1m"),
            entry.get("move_3m"),
            entry.get("move_5m"),
            entry.get("up_score"),
            entry.get("down_score"),
        ),
    )


def insert_simulation(conn, market_id, event_log_id, entry):
    cursor = conn.execute(
        """
        INSERT INTO simulations (
            event_log_id,
            market_id,
            timestamp_utc,
            model,
            signal_state,
            signal_direction,
            trade_direction,
            entry_price,
            signal_time_epoch,
            move_1m,
            move_3m,
            move_5m,
            up_score,
            down_score,
            selected,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_log_id,
            market_id,
            entry["timestamp_utc"],
            entry["model"],
            entry["signal_state"],
            entry["signal_direction"],
            entry["trade_direction"],
            entry["entry_price"],
            entry.get("signal_time"),
            entry.get("move_1m"),
            entry.get("move_3m"),
            entry.get("move_5m"),
            entry.get("up_score"),
            entry.get("down_score"),
            1 if entry["model"] == choose_model(entry["signal_state"], entry) else 0,
            "COMPLETED" if entry.get("done") else "OPEN",
        ),
    )
    simulation_id = cursor.lastrowid

    for checkpoint_seconds, values in sorted(entry.get("captured", {}).items(), key=lambda item: int(item[0])):
        conn.execute(
            """
            INSERT INTO simulation_checkpoints (
                simulation_id,
                checkpoint_seconds,
                price,
                pnl_pct
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                simulation_id,
                int(checkpoint_seconds),
                values["price"],
                values["pnl_pct"],
            ),
        )


def import_entries(db_path, json_path):
    initialize_database(db_path, DEFAULT_MARKET)
    entries = load_json_entries(json_path)

    inserted = 0
    skipped = 0

    with connect(db_path) as conn:
        market_id = ensure_market(conn, DEFAULT_MARKET)

        for entry in entries:
            timestamp = entry.get("timestamp_utc")
            event = entry.get("event")

            if not timestamp or event not in {"signal", "simulation_result"}:
                skipped += 1
                continue

            if find_existing_event_log_id(conn, market_id, entry):
                skipped += 1
                continue

            event_log_id = insert_event_log(conn, market_id, entry)

            if event == "signal":
                insert_signal(conn, market_id, event_log_id, entry)
            else:
                insert_simulation(conn, market_id, event_log_id, entry)

            inserted += 1

    return inserted, skipped, len(entries)


def main():
    parser = argparse.ArgumentParser(description="Import historical JSON bot logs into SQLite.")
    parser.add_argument(
        "--json",
        default="trend_bot_log_2026-03-19T19-18-42.json",
        help="Path to the JSON log file to import.",
    )
    parser.add_argument(
        "--db",
        default="trend_bot.db",
        help="Path to the SQLite database file.",
    )
    args = parser.parse_args()

    json_path = Path(args.json)
    if not json_path.exists():
        raise SystemExit(f"JSON log file not found: {json_path}")

    inserted, skipped, total = import_entries(args.db, str(json_path))
    print(f"JSON file: {json_path}")
    print(f"Database: {args.db}")
    print(f"Total entries read: {total}")
    print(f"Inserted: {inserted}")
    print(f"Skipped: {skipped}")


if __name__ == "__main__":
    main()
