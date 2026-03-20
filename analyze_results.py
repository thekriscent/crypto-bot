import argparse
import sqlite3

from storage import initialize_database


CHECKPOINTS = (60, 180, 300)
DEFAULT_CUMULATIVE_HORIZON = 300
DEFAULT_NOTIONAL = 10000.0
MODEL_SWAP = {
    "continuation": "fade",
    "fade": "continuation",
}


def fetch_rows(conn, query, params=()):
    cursor = conn.execute(query, params)
    columns = [col[0] for col in cursor.description]
    return columns, cursor.fetchall()


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

    header = " | ".join(column.ljust(widths[idx]) for idx, column in enumerate(columns))
    divider = "-+-".join("-" * widths[idx] for idx in range(len(columns)))

    print(header)
    print(divider)
    for row in rows:
        print(" | ".join(format_value(row[idx]).ljust(widths[idx]) for idx in range(len(columns))))
    print()


def query_signals_by_state_and_direction(conn):
    return fetch_rows(
        conn,
        """
        SELECT state, direction, COUNT(*) AS total_signals
        FROM signals
        GROUP BY state, direction
        ORDER BY state, direction
        """,
    )


def simulation_filter_clause(selected_only):
    clauses = ["s.status = 'COMPLETED'"]
    if selected_only:
        clauses.append("s.selected = 1")
    return f"WHERE {' AND '.join(clauses)}"


def checkpoint_where_clause(selected_only):
    clauses = ["s.status = 'COMPLETED'", "sc.checkpoint_seconds IN (?, ?, ?)"]
    if selected_only:
        clauses.insert(1, "s.selected = 1")
    return f"WHERE {' AND '.join(clauses)}"


def query_simulations_by_model_and_direction(conn, selected_only=False):
    return fetch_rows(
        conn,
        """
        SELECT s.model, s.trade_direction, COUNT(*) AS total_simulations
        FROM simulations s
        {where_clause}
        GROUP BY model, trade_direction
        ORDER BY model, trade_direction
        """.format(where_clause=simulation_filter_clause(selected_only)),
    )


def query_average_pnl_by_checkpoint(conn, selected_only=False):
    return fetch_rows(
        conn,
        """
        SELECT
            sc.checkpoint_seconds,
            COUNT(*) AS samples,
            AVG(sc.pnl_pct) AS avg_pnl_pct
        FROM simulation_checkpoints sc
        JOIN simulations s
            ON s.id = sc.simulation_id
        {where_clause}
        GROUP BY sc.checkpoint_seconds
        ORDER BY sc.checkpoint_seconds
        """.format(where_clause=checkpoint_where_clause(selected_only)),
        CHECKPOINTS,
    )


def query_win_rate_by_group(conn, group_column, title_column, selected_only=False, exclude_null_column=None):
    clauses = ["s.status = 'COMPLETED'"]
    if selected_only:
        clauses.append("s.selected = 1")
    if exclude_null_column:
        clauses.append(f"{exclude_null_column} IS NOT NULL")
    where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    return fetch_rows(
        conn,
        f"""
        SELECT
            {group_column} AS {title_column},
            ROUND(100.0 * AVG(CASE WHEN sc60.pnl_pct > 0 THEN 1.0 ELSE 0.0 END), 2) AS win_rate_60s,
            ROUND(100.0 * AVG(CASE WHEN sc180.pnl_pct > 0 THEN 1.0 ELSE 0.0 END), 2) AS win_rate_180s,
            ROUND(100.0 * AVG(CASE WHEN sc300.pnl_pct > 0 THEN 1.0 ELSE 0.0 END), 2) AS win_rate_300s,
            COUNT(*) AS simulations
        FROM simulations s
        LEFT JOIN simulation_checkpoints sc60
            ON sc60.simulation_id = s.id AND sc60.checkpoint_seconds = 60
        LEFT JOIN simulation_checkpoints sc180
            ON sc180.simulation_id = s.id AND sc180.checkpoint_seconds = 180
        LEFT JOIN simulation_checkpoints sc300
            ON sc300.simulation_id = s.id AND sc300.checkpoint_seconds = 300
        {where_clause}
        GROUP BY {group_column}
        ORDER BY {group_column}
        """,
    )


def query_model_checkpoint_stats(conn, selected_only=False):
    columns, rows = fetch_rows(
        conn,
        """
        SELECT
            s.model,
            sc.checkpoint_seconds,
            COUNT(*) AS simulations,
            ROUND(100.0 * AVG(CASE WHEN sc.pnl_pct > 0 THEN 1.0 ELSE 0.0 END), 2) AS win_rate_pct,
            AVG(sc.pnl_pct) AS avg_pnl_pct,
            SUM(sc.pnl_pct) AS cumulative_pnl_pct
        FROM simulations s
        JOIN simulation_checkpoints sc
            ON sc.simulation_id = s.id
        {where_clause}
        GROUP BY s.model, sc.checkpoint_seconds
        ORDER BY s.model, sc.checkpoint_seconds
        """.format(where_clause=checkpoint_where_clause(selected_only)),
        CHECKPOINTS,
    )

    stats = {}
    for model, checkpoint, simulations, win_rate, avg_pnl, cumulative_pnl in rows:
        stats.setdefault(model, {})[checkpoint] = {
            "simulations": simulations,
            "win_rate_pct": win_rate,
            "avg_pnl_pct": avg_pnl,
            "cumulative_pnl_pct": cumulative_pnl,
        }
    return columns, stats


def build_reversed_comparison_rows(stats, metric_key):
    rows = []
    for model in ("continuation", "fade"):
        reversed_model = MODEL_SWAP[model]
        row = [model, reversed_model]
        for checkpoint in CHECKPOINTS:
            original_value = stats.get(model, {}).get(checkpoint, {}).get(metric_key)
            reversed_value = stats.get(reversed_model, {}).get(checkpoint, {}).get(metric_key)
            row.extend([original_value, reversed_value])
        rows.append(tuple(row))
    return rows


def query_selected_cumulative_curve(conn, checkpoint_seconds, notional):
    return fetch_rows(
        conn,
        """
        SELECT
            s.id AS simulation_id,
            s.timestamp_utc,
            s.model,
            s.signal_state,
            s.trade_direction,
            s.entry_price,
            sc.pnl_pct,
            (? * sc.pnl_pct) AS trade_pnl_dollars
        FROM simulations s
        JOIN simulation_checkpoints sc
            ON sc.simulation_id = s.id
        WHERE s.status = 'COMPLETED'
          AND s.selected = 1
          AND sc.checkpoint_seconds = ?
        ORDER BY s.timestamp_utc, s.id
        """,
        (notional, checkpoint_seconds),
    )


def build_cumulative_curve_rows(rows):
    cumulative = 0.0
    output = []
    for simulation_id, timestamp_utc, model, signal_state, trade_direction, entry_price, pnl_pct, trade_pnl_dollars in rows:
        cumulative += trade_pnl_dollars
        output.append(
            (
                simulation_id,
                timestamp_utc,
                model,
                signal_state,
                trade_direction,
                entry_price,
                pnl_pct,
                trade_pnl_dollars,
                cumulative,
            )
        )
    return output


def main():
    parser = argparse.ArgumentParser(description="Analyze trading bot results from SQLite.")
    parser.add_argument(
        "--db",
        default="trend_bot.db",
        help="Path to the SQLite database file (default: trend_bot.db)",
    )
    parser.add_argument(
        "--cumulative-horizon",
        type=int,
        default=DEFAULT_CUMULATIVE_HORIZON,
        choices=CHECKPOINTS,
        help="Checkpoint horizon in seconds for selected-only cumulative PnL (default: 300)",
    )
    parser.add_argument(
        "--notional",
        type=float,
        default=DEFAULT_NOTIONAL,
        help="Fixed dollar notional used for trade PnL conversion (default: 10000)",
    )
    args = parser.parse_args()

    initialize_database(args.db)
    conn = sqlite3.connect(args.db)
    try:
        print(f"Database: {args.db}\n")

        print_table(
            "1. Signals by state and direction",
            *query_signals_by_state_and_direction(conn),
        )

        print_table(
            "2a. Simulations by model and direction (all)",
            *query_simulations_by_model_and_direction(conn, selected_only=False),
        )

        print_table(
            "2b. Simulations by model and direction (selected only)",
            *query_simulations_by_model_and_direction(conn, selected_only=True),
        )

        print_table(
            "3a. Average pnl_pct by checkpoint (all)",
            *query_average_pnl_by_checkpoint(conn, selected_only=False),
        )

        print_table(
            "3b. Average pnl_pct by checkpoint (selected only)",
            *query_average_pnl_by_checkpoint(conn, selected_only=True),
        )

        print_table(
            "4a. Win rate by state (%) (all)",
            *query_win_rate_by_group(conn, "s.signal_state", "state", selected_only=False),
        )

        print_table(
            "4b. Win rate by state (%) (selected only)",
            *query_win_rate_by_group(conn, "s.signal_state", "state", selected_only=True),
        )

        print_table(
            "4c. Win rate by model (%) (all)",
            *query_win_rate_by_group(conn, "s.model", "model", selected_only=False),
        )

        print_table(
            "4d. Win rate by model (%) (selected only)",
            *query_win_rate_by_group(conn, "s.model", "model", selected_only=True),
        )

        print_table(
            "4e. Win rate by trade direction (%) (all)",
            *query_win_rate_by_group(conn, "s.trade_direction", "trade_direction", selected_only=False),
        )

        print_table(
            "4f. Win rate by trade direction (%) (selected only)",
            *query_win_rate_by_group(conn, "s.trade_direction", "trade_direction", selected_only=True),
        )

        print_table(
            "5a. Selected-only win rate by volatility_state",
            *query_win_rate_by_group(
                conn,
                "s.volatility_state",
                "volatility_state",
                selected_only=True,
                exclude_null_column="s.volatility_state",
            ),
        )

        print_table(
            "5b. Selected-only win rate by range_position",
            *query_win_rate_by_group(
                conn,
                "s.range_position",
                "range_position",
                selected_only=True,
                exclude_null_column="s.range_position",
            ),
        )

        print_table(
            "5c. Selected-only win rate by news_flag",
            *query_win_rate_by_group(
                conn,
                "CASE s.news_flag WHEN 1 THEN 'TRUE' WHEN 0 THEN 'FALSE' END",
                "news_flag",
                selected_only=True,
                exclude_null_column="s.news_flag",
            ),
        )

        print_table(
            "5d. Selected-only win rate by trend_state",
            *query_win_rate_by_group(
                conn,
                "s.trend_state",
                "trend_state",
                selected_only=True,
                exclude_null_column="s.trend_state",
            ),
        )

        print_table(
            "5e. Selected-only win rate by skip_candidate",
            *query_win_rate_by_group(
                conn,
                "CASE s.skip_candidate WHEN 1 THEN 'TRUE' WHEN 0 THEN 'FALSE' END",
                "skip_candidate",
                selected_only=True,
                exclude_null_column="s.skip_candidate",
            ),
        )

        _, model_checkpoint_stats = query_model_checkpoint_stats(conn, selected_only=False)

        print_table(
            "6a. Reversed strategy win rate comparison (%)",
            (
                "strategy",
                "reversed_as",
                "orig_60s",
                "rev_60s",
                "orig_180s",
                "rev_180s",
                "orig_300s",
                "rev_300s",
            ),
            build_reversed_comparison_rows(model_checkpoint_stats, "win_rate_pct"),
        )

        print_table(
            "6b. Reversed strategy average pnl comparison",
            (
                "strategy",
                "reversed_as",
                "orig_60s",
                "rev_60s",
                "orig_180s",
                "rev_180s",
                "orig_300s",
                "rev_300s",
            ),
            build_reversed_comparison_rows(model_checkpoint_stats, "avg_pnl_pct"),
        )

        print_table(
            "6c. Reversed strategy cumulative pnl comparison",
            (
                "strategy",
                "reversed_as",
                "orig_60s",
                "rev_60s",
                "orig_180s",
                "rev_180s",
                "orig_300s",
                "rev_300s",
            ),
            build_reversed_comparison_rows(model_checkpoint_stats, "cumulative_pnl_pct"),
        )

        cumulative_curve_rows = build_cumulative_curve_rows(
            query_selected_cumulative_curve(
                conn,
                checkpoint_seconds=args.cumulative_horizon,
                notional=args.notional,
            )[1]
        )

        print_table(
            f"7. Selected-only cumulative PnL curve ({args.cumulative_horizon}s, ${args.notional:.0f} notional)",
            (
                "simulation_id",
                "timestamp_utc",
                "model",
                "signal_state",
                "trade_direction",
                "entry_price",
                "pnl_pct",
                "trade_pnl_$",
                "cumulative_pnl_$",
            ),
            cumulative_curve_rows[-20:],
        )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
