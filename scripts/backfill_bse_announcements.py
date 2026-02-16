#!/usr/bin/env python3
"""
Backfill BSE announcements by date range using API parameters.
"""

import argparse
import os
import sys


def main():
    parser = argparse.ArgumentParser(description="Backfill BSE announcements by date range")
    parser.add_argument("--db-path", default="data/equity_tracker.db")
    parser.add_argument(
        "--api-url",
        default="https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w",
        help="BSE API URL endpoint",
    )
    parser.add_argument("--from-date", required=True, help="YYYYMMDD")
    parser.add_argument("--to-date", required=True, help="YYYYMMDD")
    parser.add_argument("--pages", type=int, default=10, help="Max pages")
    parser.add_argument("--category", default="-1", help="BSE category code")
    parser.add_argument("--search", default="P", help="BSE strSearch value (default: P)")
    parser.add_argument("--type", dest="filing_type", default="C", help="BSE strType value (default: C)")
    args = parser.parse_args()

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sys.path.insert(0, project_root)

    from database.db_manager import DatabaseManager
    from services.bse_feed_service import BSEFeedService
    from utils.logger import get_logger

    logger = get_logger(__name__)

    db = DatabaseManager(args.db_path)
    service = BSEFeedService(db)

    try:
        count = service.ingest_api_range(
            api_url=args.api_url,
            start_date_yyyymmdd=args.from_date,
            end_date_yyyymmdd=args.to_date,
            max_pages=args.pages,
            category=args.category,
            search=args.search,
            filing_type=args.filing_type,
        )
        logger.info("Backfill completed. Ingested rows: %s", count)
        print(f"Backfill completed. Ingested rows: {count}")
        return 0
    except Exception as exc:
        logger.exception("Backfill failed: %s", exc)
        print(f"Backfill failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
