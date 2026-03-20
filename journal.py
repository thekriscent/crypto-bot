import json
import os
from datetime import datetime, timezone

from storage import (
    DEFAULT_MARKET,
    create_open_simulation as create_open_simulation_sqlite,
    finalize_simulation as finalize_simulation_sqlite,
    has_recent_news as has_recent_news_sqlite,
    initialize_database,
    insert_error_event as insert_error_event_sqlite,
    insert_tick as insert_tick_sqlite,
    load_open_simulations as load_open_simulations_sqlite,
    log_entry as log_entry_sqlite,
    persist_simulation_checkpoint as persist_simulation_checkpoint_sqlite,
    update_open_simulation as update_open_simulation_sqlite,
)

DEFAULT_DB_FILE = "trend_bot.db"

_storage_config = {
    "db_filename": DEFAULT_DB_FILE,
    "market": DEFAULT_MARKET.copy(),
    "initialized": False,
}

_INTERNAL_SIMULATION_KEYS = {
    "db_id",
    "event_log_id",
    "checkpoint_persisted",
    "finalized",
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


def _public_entry(entry):
    return {key: value for key, value in entry.items() if key not in _INTERNAL_SIMULATION_KEYS}


def _normalize_finalized_simulation_entry(entry):
    normalized = dict(entry)

    if normalized.get("skip_candidate") is True:
        normalized["selected"] = 0

    if (
        normalized.get("model") == "continuation"
        and normalized.get("signal_state") in {"EARLY_DOWN", "CONFIRMED_DOWN"}
    ):
        normalized["trade_direction"] = "DOWN"

    return normalized


def record_error_event(source, error, context=None, timestamp_utc=None):
    try:
        if not _storage_config["initialized"]:
            init_storage()

        insert_error_event_sqlite(
            db_filename=_storage_config["db_filename"],
            timestamp_utc=timestamp_utc or utc_now_iso(),
            source=source,
            error_type=type(error).__name__,
            error_message=str(error),
            context_json=json.dumps(context or {}, ensure_ascii=False, sort_keys=True),
        )
    except Exception as logging_error:
        print(f"Error logging failure ({source}): {error} | logging_error={logging_error}")


def log_tick(price, observed_at_epoch, observed_at_utc=None, source=None, raw_payload=None, diagnostics=None):
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
        diagnostics=diagnostics,
    )


def recent_news_exists(reference_time_utc, lookback_seconds=300):
    if not _storage_config["initialized"]:
        init_storage()

    return has_recent_news_sqlite(
        db_filename=_storage_config["db_filename"],
        reference_time_utc=reference_time_utc,
        lookback_seconds=lookback_seconds,
    )


def persist_open_simulation(sim):
    if not _storage_config["initialized"]:
        init_storage()

    timestamp_utc = utc_now_iso()
    simulation_id, event_log_id = create_open_simulation_sqlite(
        db_filename=_storage_config["db_filename"],
        entry={"timestamp_utc": timestamp_utc, **_public_entry(sim)},
        timestamp_utc=timestamp_utc,
        market=_storage_config["market"],
    )
    sim["db_id"] = simulation_id
    sim["event_log_id"] = event_log_id
    sim["checkpoint_persisted"] = set()
    sim["finalized"] = False
    return sim


def persist_simulation_checkpoint(sim, checkpoint_seconds):
    if not _storage_config["initialized"]:
        init_storage()

    checkpoint = sim["captured"][checkpoint_seconds]
    persist_simulation_checkpoint_sqlite(
        db_filename=_storage_config["db_filename"],
        simulation_id=sim["db_id"],
        checkpoint_seconds=checkpoint_seconds,
        price=checkpoint["price"],
        pnl_pct=checkpoint["pnl_pct"],
    )


def sync_open_simulation(sim):
    if not _storage_config["initialized"]:
        init_storage()

    timestamp_utc = utc_now_iso()
    update_open_simulation_sqlite(
        db_filename=_storage_config["db_filename"],
        simulation_id=sim["db_id"],
        event_log_id=sim["event_log_id"],
        entry={"timestamp_utc": timestamp_utc, **_public_entry(sim)},
        timestamp_utc=timestamp_utc,
        market=_storage_config["market"],
    )


def complete_persisted_simulation(sim, filename="crypto_signal_log.json"):
    if not _storage_config["initialized"]:
        init_storage()

    normalized_entry = _normalize_finalized_simulation_entry(_public_entry(sim))
    sim.update(normalized_entry)
    enriched_entry = {
        "timestamp_utc": utc_now_iso(),
        **normalized_entry,
    }

    finalize_simulation_sqlite(
        db_filename=_storage_config["db_filename"],
        simulation_id=sim["db_id"],
        event_log_id=sim["event_log_id"],
        entry=enriched_entry,
        timestamp_utc=enriched_entry["timestamp_utc"],
        market=_storage_config["market"],
    )

    entries = load_entries(filename)
    entries.append(enriched_entry)
    save_entries(filename, entries)


def recover_open_simulations():
    if not _storage_config["initialized"]:
        init_storage()
    return load_open_simulations_sqlite(db_filename=_storage_config["db_filename"])
