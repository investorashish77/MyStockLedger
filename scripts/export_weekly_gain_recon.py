#!/usr/bin/env python3
"""
Export a single CSV reconciliation view for weekly gain/loss validation.

Output columns:
Date (Buy), Stock, Quantity (Buy), Buy Price, Date (Sell), Quantity (Sell), Sell Price, Today's Price
"""

import argparse
import csv
import os
import sys
from collections import deque
from datetime import date, datetime, timedelta
from pathlib import Path


def _to_date(value: str):
    text = (value or "").strip()
    if not text:
        return None
    return datetime.strptime(text, "%Y-%m-%d").date()


def _in_window(row: dict, start_dt: date, end_dt: date) -> bool:
    """Keep only rows that overlap the weekly window."""
    buy_dt = _to_date(row.get("Date (Buy)"))
    sell_dt = _to_date(row.get("Date (Sell)"))
    if buy_dt and buy_dt > end_dt:
        return False
    if sell_dt and sell_dt < start_dt:
        return False
    return True


def main():
    parser = argparse.ArgumentParser(description="Export weekly gain reconciliation CSV")
    parser.add_argument("--db-path", default="data/equity_tracker.db")
    parser.add_argument("--user-id", type=int, required=True)
    parser.add_argument("--end-date", default="", help="YYYY-MM-DD (default: today)")
    parser.add_argument("--window-days", type=int, default=7)
    parser.add_argument("--include-all-history", action="store_true", help="Do not filter rows by weekly window overlap")
    parser.add_argument("--out-file", default="", help="Optional explicit output CSV path")
    args = parser.parse_args()

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sys.path.insert(0, project_root)

    from database.db_manager import DatabaseManager
    from utils.logger import get_logger

    logger = get_logger(__name__)
    db = DatabaseManager(args.db_path)

    end_dt = _to_date(args.end_date) if args.end_date else date.today()
    start_dt = end_dt - timedelta(days=int(args.window_days))
    end_iso = end_dt.isoformat()

    # Preload stock-level fallback prices from current portfolio rows.
    portfolio = db.get_portfolio_summary(args.user_id)
    portfolio_avg_price = {int(r["stock_id"]): float(r.get("avg_price") or 0.0) for r in portfolio}

    # Use all user stocks (including closed positions) so sell rows are not missed.
    stock_map = {
        int(r["stock_id"]): {
            "symbol": r.get("symbol") or "",
        }
        for r in db.get_user_stocks(args.user_id)
    }

    rows = []

    for stock_id, info in stock_map.items():
        symbol = info["symbol"]
        txs = db.get_stock_transactions(stock_id) or []
        txs = [t for t in txs if (t.get("transaction_date") or "") <= end_iso]
        txs.sort(key=lambda t: ((t.get("transaction_date") or ""), int(t.get("transaction_id") or 0)))
        if not txs:
            continue

        last_tx_price = float(txs[-1].get("price_per_share") or 0.0)
        today_price = float(
            db.get_latest_price(stock_id)
            or portfolio_avg_price.get(stock_id, 0.0)
            or last_tx_price
            or 0.0
        )

        buy_lots = deque()
        for tx in txs:
            tx_type = (tx.get("transaction_type") or "").upper()
            tx_date = (tx.get("transaction_date") or "").strip()
            qty = float(tx.get("quantity") or 0.0)
            price = float(tx.get("price_per_share") or 0.0)

            if tx_type == "BUY":
                buy_lots.append(
                    {
                        "buy_date": tx_date,
                        "qty_remaining": qty,
                        "buy_price": price,
                    }
                )
                continue

            if tx_type != "SELL":
                continue

            sell_remaining = qty
            while sell_remaining > 1e-9 and buy_lots:
                lot = buy_lots[0]
                matched = min(float(lot["qty_remaining"]), sell_remaining)
                rows.append(
                    {
                        "Date (Buy)": lot["buy_date"],
                        "Stock": symbol,
                        "Quantity (Buy)": round(matched, 6),
                        "Buy Price": round(float(lot["buy_price"]), 6),
                        "Date (Sell)": tx_date,
                        "Quantity (Sell)": round(matched, 6),
                        "Sell Price": round(price, 6),
                        "Today's Price": round(today_price, 6),
                    }
                )
                lot["qty_remaining"] = float(lot["qty_remaining"]) - matched
                sell_remaining -= matched
                if lot["qty_remaining"] <= 1e-9:
                    buy_lots.popleft()

            # Surface data anomaly if sells exceed cumulative buys.
            if sell_remaining > 1e-9:
                rows.append(
                    {
                        "Date (Buy)": "",
                        "Stock": symbol,
                        "Quantity (Buy)": "",
                        "Buy Price": "",
                        "Date (Sell)": tx_date,
                        "Quantity (Sell)": round(sell_remaining, 6),
                        "Sell Price": round(price, 6),
                        "Today's Price": round(today_price, 6),
                    }
                )

        # Open buy lots (not yet sold).
        for lot in buy_lots:
            remaining = float(lot["qty_remaining"])
            if remaining <= 1e-9:
                continue
            rows.append(
                {
                    "Date (Buy)": lot["buy_date"],
                    "Stock": symbol,
                    "Quantity (Buy)": round(remaining, 6),
                    "Buy Price": round(float(lot["buy_price"]), 6),
                    "Date (Sell)": "",
                    "Quantity (Sell)": "",
                    "Sell Price": "",
                    "Today's Price": round(today_price, 6),
                }
            )

    if not args.include_all_history:
        rows = [r for r in rows if _in_window(r, start_dt, end_dt)]

    rows.sort(key=lambda r: ((r.get("Date (Buy)") or ""), (r.get("Stock") or ""), (r.get("Date (Sell)") or "")))

    if args.out_file:
        out_path = Path(args.out_file)
    else:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = Path("logs/weekly_gain_recon") / f"user_{args.user_id}_{stamp}.csv"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "Date (Buy)",
                "Stock",
                "Quantity (Buy)",
                "Buy Price",
                "Date (Sell)",
                "Quantity (Sell)",
                "Sell Price",
                "Today's Price",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    logger.info(
        "Weekly reconciliation exported. user_id=%s start=%s end=%s rows=%s file=%s",
        args.user_id,
        start_dt.isoformat(),
        end_dt.isoformat(),
        len(rows),
        out_path,
    )
    print(f"Weekly reconciliation CSV: {out_path}")
    print(f"Window: {start_dt.isoformat()} -> {end_dt.isoformat()} | rows: {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
