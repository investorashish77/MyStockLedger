#!/usr/bin/env python3
"""
Export weekly gain/loss calculation inputs into CSV files for verification.

This mirrors the KPI formula used in `ui/main_window.py`:
    gain = (end_holdings + end_cash) - (start_holdings + start_cash) - net_external_cash_flow
"""

import argparse
import csv
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path


def _series_value_on_or_before(series_rows, target_date: str) -> float:
    for row in reversed(series_rows or []):
        if (row.get("trade_date") or "") <= target_date:
            return float(row.get("portfolio_value") or 0.0)
    return 0.0


def _compute_gain(db, user_id: int, series_rows: list, start_date: str, end_date: str, end_holdings_value: float):
    start_holdings = _series_value_on_or_before(series_rows, start_date)
    start_cash = float(db.get_cash_balance_as_of(user_id, start_date))
    end_cash = float(db.get_cash_balance_as_of(user_id, end_date))
    net_external_flow = float(db.get_portfolio_external_cash_flow(user_id, start_date, end_date))

    start_value = start_holdings + start_cash
    end_value = float(end_holdings_value) + end_cash
    gain_value = end_value - start_value - net_external_flow
    denominator = start_value + net_external_flow
    gain_pct = (gain_value / denominator * 100.0) if abs(denominator) > 1e-9 else 0.0

    return {
        "start_holdings": start_holdings,
        "start_cash": start_cash,
        "start_value": start_value,
        "end_holdings": float(end_holdings_value),
        "end_cash": end_cash,
        "end_value": end_value,
        "net_external_cash_flow": net_external_flow,
        "gain_value": gain_value,
        "gain_pct": gain_pct,
    }


def _latest_holdings_value_from_db(db, user_id: int) -> tuple:
    rows = db.get_portfolio_summary(user_id)
    enriched = []
    total = 0.0
    for row in rows:
        qty = int(row.get("quantity") or 0)
        avg = float(row.get("avg_price") or 0.0)
        ltp = float(db.get_latest_price(row["stock_id"]) or avg)
        current_value = qty * ltp
        enriched.append({
            "stock_id": row["stock_id"],
            "symbol": row.get("symbol"),
            "company_name": row.get("company_name"),
            "quantity": qty,
            "avg_price": avg,
            "latest_price": ltp,
            "current_value": current_value,
        })
        total += current_value
    return total, enriched


def _write_csv(path: Path, rows: list, fieldnames: list):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main():
    parser = argparse.ArgumentParser(description="Dump weekly gain/loss calculation data to CSV")
    parser.add_argument("--db-path", default="data/equity_tracker.db", help="SQLite DB path")
    parser.add_argument("--user-id", type=int, required=True, help="User ID to analyze")
    parser.add_argument("--end-date", default="", help="Optional end date (YYYY-MM-DD)")
    parser.add_argument("--window-days", type=int, default=7, help="Window length in days")
    parser.add_argument("--out-dir", default="logs/weekly_gain_debug", help="Output directory")
    args = parser.parse_args()

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sys.path.insert(0, project_root)

    from database.db_manager import DatabaseManager
    from utils.logger import get_logger

    logger = get_logger(__name__)
    db = DatabaseManager(args.db_path)
    user_id = int(args.user_id)

    series_rows = db.get_portfolio_performance_series(user_id=user_id)
    if not series_rows:
        print(f"No portfolio performance series available for user_id={user_id}")
        return 1

    # Scenario A mirrors startup-fast path (non-live): end date from latest series date.
    series_end_date = (args.end_date or series_rows[-1]["trade_date"]).strip()
    series_end_dt = datetime.strptime(series_end_date, "%Y-%m-%d").date()
    series_start_date = (series_end_dt - timedelta(days=int(args.window_days))).isoformat()
    series_end_holdings = float(_series_value_on_or_before(series_rows, series_end_date))
    summary_series = _compute_gain(
        db=db,
        user_id=user_id,
        series_rows=series_rows,
        start_date=series_start_date,
        end_date=series_end_date,
        end_holdings_value=series_end_holdings,
    )

    # Scenario B approximates cached-latest holdings path (no network).
    latest_end_date = (args.end_date or date.today().isoformat()).strip()
    latest_end_dt = datetime.strptime(latest_end_date, "%Y-%m-%d").date()
    latest_start_date = (latest_end_dt - timedelta(days=int(args.window_days))).isoformat()
    latest_holdings_total, latest_positions = _latest_holdings_value_from_db(db, user_id)
    summary_latest = _compute_gain(
        db=db,
        user_id=user_id,
        series_rows=series_rows,
        start_date=latest_start_date,
        end_date=latest_end_date,
        end_holdings_value=latest_holdings_total,
    )

    out_dir = Path(args.out_dir) / f"user_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    out_dir.mkdir(parents=True, exist_ok=True)

    _write_csv(
        out_dir / "weekly_gain_summary.csv",
        rows=[
            {
                "scenario": "series_end_non_live",
                "start_date": series_start_date,
                "end_date": series_end_date,
                **summary_series,
            },
            {
                "scenario": "latest_price_cached",
                "start_date": latest_start_date,
                "end_date": latest_end_date,
                **summary_latest,
            },
        ],
        fieldnames=[
            "scenario",
            "start_date",
            "end_date",
            "start_holdings",
            "start_cash",
            "start_value",
            "end_holdings",
            "end_cash",
            "end_value",
            "net_external_cash_flow",
            "gain_value",
            "gain_pct",
        ],
    )

    series_dump = []
    for row in series_rows:
        d = (row.get("trade_date") or "").strip()
        series_dump.append({
            "trade_date": d,
            "portfolio_value": float(row.get("portfolio_value") or 0.0),
            "in_series_window": int(series_start_date <= d <= series_end_date),
            "in_latest_window": int(latest_start_date <= d <= latest_end_date),
        })
    _write_csv(
        out_dir / "weekly_gain_series.csv",
        rows=series_dump,
        fieldnames=["trade_date", "portfolio_value", "in_series_window", "in_latest_window"],
    )

    # Dump stock transactions used to build holdings in valuation series.
    tx_rows = []
    stocks = db.get_user_stocks(user_id)
    for stock in stocks:
        sid = stock["stock_id"]
        symbol = stock.get("symbol")
        company_name = stock.get("company_name")
        for tx in db.get_stock_transactions(sid):
            tx_date = (tx.get("transaction_date") or "").strip()
            qty = float(tx.get("quantity") or 0.0)
            pps = float(tx.get("price_per_share") or 0.0)
            tx_rows.append({
                "stock_id": sid,
                "symbol": symbol,
                "company_name": company_name,
                "transaction_id": tx.get("transaction_id"),
                "transaction_date": tx_date,
                "transaction_type": tx.get("transaction_type"),
                "quantity": qty,
                "price_per_share": pps,
                "amount": qty * pps,
                "realized_pnl": tx.get("realized_pnl"),
                "in_series_window": int(series_start_date <= tx_date <= series_end_date),
                "in_latest_window": int(latest_start_date <= tx_date <= latest_end_date),
            })
    tx_rows.sort(key=lambda x: (x["transaction_date"], x["stock_id"], x["transaction_id"]))
    _write_csv(
        out_dir / "weekly_gain_transactions.csv",
        rows=tx_rows,
        fieldnames=[
            "stock_id",
            "symbol",
            "company_name",
            "transaction_id",
            "transaction_date",
            "transaction_type",
            "quantity",
            "price_per_share",
            "amount",
            "realized_pnl",
            "in_series_window",
            "in_latest_window",
        ],
    )

    # Dump cash ledger + external flow markers.
    ledger_rows = db.get_cash_ledger_entries(user_id, limit=5000)
    ledger_dump = []
    for row in ledger_rows:
        entry_date = (row.get("entry_date") or "").strip()
        entry_type = (row.get("entry_type") or "").strip().upper()
        sign = 0
        if entry_type in {"INIT_DEPOSIT", "DEPOSIT", "SELL_CREDIT"}:
            sign = 1
        elif entry_type in {"WITHDRAWAL", "BUY_DEBIT"}:
            sign = -1
        signed_amount = sign * float(row.get("amount") or 0.0)
        is_external = int(entry_type in {"DEPOSIT", "WITHDRAWAL"})
        ledger_dump.append({
            "ledger_id": row.get("ledger_id"),
            "entry_date": entry_date,
            "entry_type": entry_type,
            "amount": float(row.get("amount") or 0.0),
            "signed_amount": signed_amount,
            "is_external": is_external,
            "note": row.get("note") or "",
            "reference_transaction_id": row.get("reference_transaction_id"),
            "in_series_window": int(series_start_date <= entry_date <= series_end_date),
            "in_latest_window": int(latest_start_date <= entry_date <= latest_end_date),
        })
    ledger_dump.sort(key=lambda x: (x["entry_date"], x["ledger_id"] or 0))
    _write_csv(
        out_dir / "weekly_gain_cash_ledger.csv",
        rows=ledger_dump,
        fieldnames=[
            "ledger_id",
            "entry_date",
            "entry_type",
            "amount",
            "signed_amount",
            "is_external",
            "note",
            "reference_transaction_id",
            "in_series_window",
            "in_latest_window",
        ],
    )

    _write_csv(
        out_dir / "weekly_gain_latest_positions.csv",
        rows=latest_positions,
        fieldnames=["stock_id", "symbol", "company_name", "quantity", "avg_price", "latest_price", "current_value"],
    )

    logger.info("Weekly gain debug dump written: %s", out_dir)
    print(f"Weekly gain debug dump written to: {out_dir}")
    print("Files:")
    print("  - weekly_gain_summary.csv")
    print("  - weekly_gain_series.csv")
    print("  - weekly_gain_transactions.csv")
    print("  - weekly_gain_cash_ledger.csv")
    print("  - weekly_gain_latest_positions.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
