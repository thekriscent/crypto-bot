import json
import os
from datetime import datetime, timezone

from storage import (
    DEFAULT_MARKET,
    has_recent_news as has_recent_news_sqlite,
    initialize_database,
    insert_tick as insert_tick_sqlite,
    log_entry as log_entry_sqlite,
)

DEFAULT_DB_FILE = "trend_bot.db"

_storage_config = {
    "db_filename": DEFAULT_DB_FILE,
    "market": DEFAULT_MARKET.copy(),
    "initialized": False,
}


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def load_entries(filename):
    if not os.path.exists(filename):
        return []

    try:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def save_entries(filename, entries):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)


def init_storage(db_filename=DEFAULT_DB_FILE, market=None):
    _storage_config["db_filename"] = db_filename
    _storage_config["market"] = (market or DEFAULT_MARKET).copy()
    initialize_database(
        db_filename=_storage_config["db_filename"],
        market=_storage_config["market"],
    )
    _storage_config["initialized"] = True


def log_entry(entry: dict, filename="crypto_signal_log.json"):
    if not _storage_config["initialized"]:
        init_storage()

    enriched_entry = {
        "timestamp_utc": utc_now_iso(),
        **entry,
    }

    log_entry_sqlite(
        db_filename=_storage_config["db_filename"],
        entry=enriched_entry,
        timestamp_utc=enriched_entry["timestamp_utc"],
        market=_storage_config["market"],
    )

    entries = load_entries(filename)
    entries.append(enriched_entry)
    save_entries(filename, entries)


def log_tick(price, observed_at_epoch, observed_at_utc=None, source=None, raw_payload=None):
    if not _storage_config["initialized"]:
        init_storage()

    insert_tick_sqlite(
        db_filename=_storage_config["db_filename"],
        observed_at_utc=observed_at_utc or utc_now_iso(),
        observed_at_epoch=observed_at_epoch,
        price=price,
        market=_storage_config["market"],
        source=source,
        raw_payload=raw_payload,
    )


def recent_news_exists(reference_time_utc, lookback_seconds=300):
    if not _storage_config["initialized"]:
        init_storage()

    return has_recent_news_sqlite(
        db_filename=_storage_config["db_filename"],
        reference_time_utc=reference_time_utc,
        lookback_seconds=lookback_seconds,
    )
