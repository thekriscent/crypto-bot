import argparse
import sqlite3
from datetime import datetime, timedelta, timezone


HORIZONS_MINUTES = (5, 15, 30, 60)
DEFAULT_MAX_BASELINE_LAG_MINUTES = 10


def parse_iso_datetime(value):
    if not value:
        return None

    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def format_value(value):
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def print_table(title, columns, rows):
    print(title)

    if not rows:
        print("(no data)\n")
        return

    widths = []
    for idx, column in enumerate(columns):
        cell_width = max(len(format_value(row[idx])) for row in rows)
        widths.append(max(len(column), cell_width))

    print(" | ".join(column.ljust(widths[idx]) for idx, column in enumerate(columns)))
    print("-+-".join("-" * widths[idx] for idx in range(len(columns))))
    for row in rows:
        print(" | ".join(format_value(row[idx]).ljust(widths[idx]) for idx in range(len(columns))))
    print()


def get_news_items(conn, limit=None):
    query = """
        SELECT id, timestamp_utc, published_at, source, headline, url
        FROM news_items
        ORDER BY COALESCE(published_at, timestamp_utc) DESC, id DESC
    """
    params = ()
    if limit is not None:
        query += " LIMIT ?"
        params = (limit,)
    return conn.execute(query, params).fetchall()


def get_first_tick_at_or_after(conn, timestamp_utc):
    return conn.execute(
        """
        SELECT observed_at_utc, price
        FROM ticks
        WHERE observed_at_utc >= ?
        ORDER BY observed_at_utc
        LIMIT 1
        """,
        (timestamp_utc,),
    ).fetchone()


def build_news_move_rows(conn, news_items, max_baseline_lag_minutes):
    rows = []

    for news_id, collected_at, published_at, source, headline, url in news_items:
        event_time = published_at or collected_at
        baseline = get_first_tick_at_or_after(conn, event_time)
        if not baseline:
            continue

        baseline_time, baseline_price = baseline
        event_dt = parse_iso_datetime(event_time)
        baseline_dt = parse_iso_datetime(baseline_time)
        baseline_lag_minutes = (baseline_dt - event_dt).total_seconds() / 60.0

        if baseline_lag_minutes > max_baseline_lag_minutes:
            continue

        moves = {}
        for horizon in HORIZONS_MINUTES:
            target_time = (event_dt + timedelta(minutes=horizon)).isoformat()
            future_tick = get_first_tick_at_or_after(conn, target_time)
            if not future_tick:
                moves[horizon] = None
                continue

            _, future_price = future_tick
            moves[horizon] = (future_price - baseline_price) / baseline_price

        rows.append(
            {
                "news_id": news_id,
                "event_time": event_time,
                "baseline_time": baseline_time,
                "baseline_lag_minutes": baseline_lag_minutes,
                "source": source,
                "headline": headline,
                "url": url,
                "baseline_price": baseline_price,
                "moves": moves,
            }
        )

    return rows


def summarize_by_source(news_move_rows):
    summary = []

    for source in sorted({row["source"] for row in news_move_rows}):
        source_rows = [row for row in news_move_rows if row["source"] == source]
        output_row = [source, len(source_rows)]

        for horizon in HORIZONS_MINUTES:
            values = [row["moves"][horizon] for row in source_rows if row["moves"][horizon] is not None]
            avg_move = sum(values) / len(values) if values else None
            up_rate = (100.0 * sum(1 for value in values if value > 0) / len(values)) if values else None
            output_row.extend([avg_move, up_rate, len(values)])

        summary.append(tuple(output_row))

    return summary


def build_recent_item_rows(news_move_rows, limit):
    rows = []
    for row in news_move_rows[:limit]:
        output_row = [
            row["event_time"],
            row["source"],
            row["headline"],
            row["baseline_lag_minutes"],
            row["baseline_price"],
        ]
        for horizon in HORIZONS_MINUTES:
            output_row.append(row["moves"][horizon])
        rows.append(tuple(output_row))
    return rows


def main():
    parser = argparse.ArgumentParser(description="Analyze how stored news lines up with market moves.")
    parser.add_argument(
        "--db",
        default="trend_bot.db",
        help="Path to the SQLite database file (default: trend_bot.db)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Maximum number of latest news items to analyze (default: 200)",
    )
    parser.add_argument(
        "--recent",
        type=int,
        default=15,
        help="How many recent matched headlines to print (default: 15)",
    )
    parser.add_argument(
        "--max-baseline-lag-minutes",
        type=float,
        default=DEFAULT_MAX_BASELINE_LAG_MINUTES,
        help="Maximum allowed gap between news time and first baseline tick (default: 10)",
    )
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    try:
        news_items = get_news_items(conn, args.limit)
        news_move_rows = build_news_move_rows(
            conn,
            news_items,
            max_baseline_lag_minutes=args.max_baseline_lag_minutes,
        )

        print(f"Database: {args.db}")
        print(f"News items loaded: {len(news_items)}")
        print(f"News items matched to ticks: {len(news_move_rows)}\n")

        print_table(
            "1. Source impact summary",
            (
                "source",
                "news_items",
                "avg_5m",
                "up_rate_5m",
                "samples_5m",
                "avg_15m",
                "up_rate_15m",
                "samples_15m",
                "avg_30m",
                "up_rate_30m",
                "samples_30m",
                "avg_60m",
                "up_rate_60m",
                "samples_60m",
            ),
            summarize_by_source(news_move_rows),
        )

        print_table(
            "2. Recent news matched to forward moves",
            (
                "event_time",
                "source",
                "headline",
                "lag_min",
                "baseline_px",
                "move_5m",
                "move_15m",
                "move_30m",
                "move_60m",
            ),
            build_recent_item_rows(news_move_rows, args.recent),
        )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
