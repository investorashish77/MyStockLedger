#!/usr/bin/env python3
"""
Sync NSE symbols into local symbol_master using nsetools adapter.
"""

import argparse
import os
import sys


def main():
    parser = argparse.ArgumentParser(description="Sync NSE symbols into symbol_master")
    parser.add_argument(
        "--db-path",
        default="data/equity_tracker.db",
        help="SQLite database path (default: data/equity_tracker.db)",
    )
    args = parser.parse_args()

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sys.path.insert(0, project_root)

    from database.db_manager import DatabaseManager
    from services.symbol_master_service import SymbolMasterService
    from utils.logger import get_logger

    logger = get_logger(__name__)
    logger.info("Using database: %s", args.db_path)
    print(f"Using database: {args.db_path}")
    db = DatabaseManager(args.db_path)
    service = SymbolMasterService(db)

    try:
        count = service.populate_symbols_from_nsetools()
    except RuntimeError as exc:
        logger.error("NSE sync dependency error: %s", exc)
        print(f"Error: {exc}")
        print("Install dependency and retry: python3 -m pip install -r requirements.txt")
        return 1
    except Exception as exc:
        logger.exception("Unexpected error during NSE sync: %s", exc)
        print(f"Unexpected error during NSE sync: {exc}")
        return 1

    logger.info("NSE symbol sync completed. Upserted rows: %s", count)
    print(f"NSE symbol sync completed. Upserted rows: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
