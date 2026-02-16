#!/usr/bin/env python3
"""
Sync BSE symbols from a downloaded CSV file into symbol_master.
"""

import argparse
import os
import sys


def main():
    parser = argparse.ArgumentParser(description="Sync BSE symbols into symbol_master from CSV")
    parser.add_argument("--db-path", default="data/equity_tracker.db")
    parser.add_argument("--csv-path", required=True, help="Path to downloaded BSE Equity CSV")
    args = parser.parse_args()

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sys.path.insert(0, project_root)

    from database.db_manager import DatabaseManager
    from services.symbol_master_service import SymbolMasterService
    from utils.logger import get_logger

    logger = get_logger(__name__)

    if not os.path.exists(args.csv_path):
        logger.error("CSV file not found: %s", args.csv_path)
        print(f"CSV file not found: {args.csv_path}")
        return 1

    db = DatabaseManager(args.db_path)
    service = SymbolMasterService(db)

    try:
        with open(args.csv_path, "r", encoding="utf-8-sig") as f:
            csv_text = f.read()

        count = service.populate_symbols_from_csv_text(csv_text, source="BSE_CSV")
        logger.info("BSE symbol sync completed. Upserted rows: %s", count)
        print(f"BSE symbol sync completed. Upserted rows: {count}")
        return 0
    except Exception as exc:
        logger.exception("BSE symbol sync failed: %s", exc)
        print(f"BSE symbol sync failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
