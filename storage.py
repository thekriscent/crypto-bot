import json
import sqlite3

DEFAULT_MARKET = {
    "exchange_code": "coinbase",
    "exchange_name": "Coinbase",
    "symbol": "BTC-USD",
    "base_asset": "BTC",
    "quote_asset": "USD",
}


def _connect(db_filename):
    conn = sqlite3.connect(db_filename)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def initialize_database(db_filename, market=None):
    market = market or DEFAULT_MARKET

    with _connect(db_filename) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS exchanges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS markets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exchange_id INTEGER NOT NULL REFERENCES exchanges(id),
                symbol TEXT NOT NULL,
                base_asset TEXT NOT NULL,
                quote_asset TEXT NOT NULL,
                UNIQUE(exchange_id, symbol)
            );

            CREATE TABLE IF NOT EXISTS event_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                market_id INTEGER NOT NULL REFERENCES markets(id),
                timestamp_utc TEXT NOT NULL,
                event TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS ticks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                market_id INTEGER NOT NULL REFERENCES markets(id),
                observed_at_utc TEXT NOT NULL,
                observed_at_epoch REAL NOT NULL,
                price REAL NOT NULL,
                source TEXT,
                raw_payload_json TEXT
            );

            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_log_id INTEGER NOT NULL UNIQUE REFERENCES event_log(id),
                market_id INTEGER NOT NULL REFERENCES markets(id),
                timestamp_utc TEXT NOT NULL,
                signal_type TEXT,
                state TEXT NOT NULL,
                direction TEXT NOT NULL,
                price_now REAL NOT NULL,
                move_1m REAL,
                move_3m REAL,
                move_5m REAL,
                up_score INTEGER,
                down_score INTEGER
            );

            CREATE TABLE IF NOT EXISTS simulations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_log_id INTEGER NOT NULL UNIQUE REFERENCES event_log(id),
                market_id INTEGER NOT NULL REFERENCES markets(id),
                timestamp_utc TEXT NOT NULL,
                model TEXT NOT NULL,
                signal_state TEXT NOT NULL,
                signal_direction TEXT NOT NULL,
                trade_direction TEXT NOT NULL,
                entry_price REAL NOT NULL,
                signal_time_epoch REAL,
                move_1m REAL,
                move_3m REAL,
                move_5m REAL,
                up_score INTEGER,
                down_score INTEGER,
                status TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS simulation_checkpoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                simulation_id INTEGER NOT NULL REFERENCES simulations(id) ON DELETE CASCADE,
                checkpoint_seconds INTEGER NOT NULL,
                price REAL NOT NULL,
                pnl_pct REAL NOT NULL,
                UNIQUE(simulation_id, checkpoint_seconds)
            );

            CREATE INDEX IF NOT EXISTS idx_event_log_market_time
            ON event_log(market_id, timestamp_utc);

            CREATE INDEX IF NOT EXISTS idx_signals_market_time
            ON signals(market_id, timestamp_utc);

            CREATE INDEX IF NOT EXISTS idx_simulations_market_time
            ON simulations(market_id, timestamp_utc);

            CREATE INDEX IF NOT EXISTS idx_ticks_market_time
            ON ticks(market_id, observed_at_utc);
            """
        )
        ensure_market(conn, market)


def ensure_market(conn, market):
    conn.execute(
        """
        INSERT INTO exchanges (code, name)
        VALUES (?, ?)
        ON CONFLICT(code) DO UPDATE SET name = excluded.name
        """,
        (market["exchange_code"], market["exchange_name"]),
    )

    exchange_id = conn.execute(
        "SELECT id FROM exchanges WHERE code = ?",
        (market["exchange_code"],),
    ).fetchone()[0]

    conn.execute(
        """
        INSERT INTO markets (exchange_id, symbol, base_asset, quote_asset)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(exchange_id, symbol) DO UPDATE SET
            base_asset = excluded.base_asset,
            quote_asset = excluded.quote_asset
        """,
        (
            exchange_id,
            market["symbol"],
            market["base_asset"],
            market["quote_asset"],
        ),
    )

    return conn.execute(
        "SELECT id FROM markets WHERE exchange_id = ? AND symbol = ?",
        (exchange_id, market["symbol"]),
    ).fetchone()[0]


def log_entry(db_filename, entry, timestamp_utc, market=None):
    market = market or DEFAULT_MARKET

    with _connect(db_filename) as conn:
        market_id = ensure_market(conn, market)
        event_log_id = conn.execute(
            """
            INSERT INTO event_log (market_id, timestamp_utc, event, payload_json)
            VALUES (?, ?, ?, ?)
            """,
            (
                market_id,
                timestamp_utc,
                entry.get("event", "unknown"),
                json.dumps(entry, ensure_ascii=False, sort_keys=True),
            ),
        ).lastrowid

        if entry.get("event") == "signal":
            _insert_signal(conn, event_log_id, market_id, entry, timestamp_utc)
        elif entry.get("event") == "simulation_result":
            _insert_simulation(conn, event_log_id, market_id, entry, timestamp_utc)

        return event_log_id


def insert_tick(db_filename, observed_at_utc, observed_at_epoch, price, market=None, source=None, raw_payload=None):
    market = market or DEFAULT_MARKET

    with _connect(db_filename) as conn:
        market_id = ensure_market(conn, market)
        conn.execute(
            """
            INSERT INTO ticks (
                market_id,
                observed_at_utc,
                observed_at_epoch,
                price,
                source,
                raw_payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                market_id,
                observed_at_utc,
                observed_at_epoch,
                price,
                source,
                json.dumps(raw_payload, ensure_ascii=False, sort_keys=True)
                if raw_payload is not None else None,
            ),
        )


def _insert_signal(conn, event_log_id, market_id, entry, timestamp_utc):
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
            timestamp_utc,
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


def _insert_simulation(conn, event_log_id, market_id, entry, timestamp_utc):
    simulation_id = conn.execute(
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
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_log_id,
            market_id,
            timestamp_utc,
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
            "COMPLETED" if entry.get("done") else "OPEN",
        ),
    ).lastrowid

    captured = entry.get("captured", {})
    for checkpoint_seconds, values in sorted(captured.items(), key=lambda item: int(item[0])):
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
