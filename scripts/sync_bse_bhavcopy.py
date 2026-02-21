#!/usr/bin/env python3
"""
Sync BSE daily bhavcopy OHLCV data into local DB.
"""

import argparse
import os
import sys
from datetime import datetime


def main():
    """Main.

    Args:
        None.

    Returns:
        Any: Method output for caller use.
    """
    parser = argparse.ArgumentParser(description="Sync BSE bhavcopy into DB")
    parser.add_argument("--db-path", default="data/equity_tracker.db")
    parser.add_argument("--from-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--to-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--include-weekends", action="store_true", help="Try weekends too")
    parser.add_argument("--fail-fast", action="store_true", help="Stop on first date failure")
    args = parser.parse_args()

    from_date = datetime.strptime(args.from_date, "%Y-%m-%d").date()
    to_date = datetime.strptime(args.to_date, "%Y-%m-%d").date()

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sys.path.insert(0, project_root)

    from database.db_manager import DatabaseManager
    from services.bse_bhavcopy_service import BSEBhavcopyService
    from utils.logger import get_logger

    logger = get_logger(__name__)

    db = DatabaseManager(args.db_path)
    service = BSEBhavcopyService(db)
    try:
        count = service.fetch_and_ingest_range(
            from_date=from_date,
            to_date=to_date,
            skip_weekends=not args.include_weekends,
            fail_fast=args.fail_fast
        )
        logger.info("BSE bhavcopy sync completed. Rows upserted: %s", count)
        print(f"BSE bhavcopy sync completed. Rows upserted: {count}")
        return 0
    except Exception as exc:
        logger.exception("BSE bhavcopy sync failed: %s", exc)
        print(f"BSE bhavcopy sync failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
