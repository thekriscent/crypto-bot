import json
import os
from datetime import datetime, timezone


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


def log_entry(entry: dict, filename="crypto_signal_log.json"):
    entries = load_entries(filename)
    entries.append({
        "timestamp_utc": utc_now_iso(),
        **entry,
    })
    save_entries(filename, entries)