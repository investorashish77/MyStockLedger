#!/usr/bin/env python3
"""
Sync BSE announcement CSV files (daily snapshots) into bse_announcements table.
"""

import argparse
import csv
import os
import sys
from pathlib import Path


def _clean(value):
    if value is None:
        return None
    text = str(value).strip()
    if text == "" or text.lower() == "nan":
        return None
    return text


def _resolve_symbol_id(db, scrip_code):
    row = db.get_symbol_by_bse_code(scrip_code)
    return row["symbol_id"] if row else None


def main():
    parser = argparse.ArgumentParser(description="Sync announcement CSV files into bse_announcements")
    parser.add_argument("--db-path", default="data/equity_tracker.db")
    parser.add_argument("--input-dir", default="announcements", help="Directory containing daily announcement CSV files")
    parser.add_argument("--pattern", default="bse_announcements_*.csv", help="CSV filename glob pattern")
    args = parser.parse_args()

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sys.path.insert(0, project_root)

    from database.db_manager import DatabaseManager
    from services.bse_feed_service import BSEFeedService
    from utils.logger import get_logger

    logger = get_logger(__name__)
    db = DatabaseManager(args.db_path)
    feed_service = BSEFeedService(db)

    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        logger.error("Input directory does not exist: %s", input_dir)
        print(f"Input directory does not exist: {input_dir}")
        return 1

    files = sorted(input_dir.glob(args.pattern))
    if not files:
        logger.error("No CSV files found in %s matching %s", input_dir, args.pattern)
        print(f"No CSV files found in {input_dir} matching {args.pattern}")
        return 1

    total_files = 0
    total_rows = 0
    total_written = 0

    for file_path in files:
        total_files += 1
        file_rows = 0
        file_written = 0
        with open(file_path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                file_rows += 1
                headline = (
                    _clean(row.get("HEADLINE"))
                    or _clean(row.get("NEWS_SUB"))
                    or _clean(row.get("SUBCATNAME"))
                    or "BSE Announcement"
                )
                scrip_code = _clean(row.get("SCRIP_CD")) or _clean(row.get("scrip_code"))
                news_id = _clean(row.get("NEWSID")) or _clean(row.get("guid"))
                link = (
                    _clean(row.get("ATTACHMENTNAME"))
                    or _clean(row.get("NSURL"))
                    or _clean(row.get("pdf_link"))
                    or _clean(row.get("attachment_url"))
                )
                announcement_date = (
                    _clean(row.get("NEWS_DT"))
                    or _clean(row.get("DissemDT"))
                    or _clean(row.get("DT_TM"))
                    or _clean(row.get("announcement_date"))
                )
                symbol_id = _resolve_symbol_id(db, scrip_code)

                exchange_ref_id = feed_service._build_exchange_ref_id({
                    "guid": news_id,
                    "link": link,
                    "title": headline,
                    "pubDate": announcement_date,
                })

                db.add_bse_announcement(
                    symbol_id=symbol_id,
                    scrip_code=scrip_code,
                    headline=headline,
                    category="BSE_API_CSV",
                    announcement_date=announcement_date,
                    attachment_url=link,
                    exchange_ref_id=exchange_ref_id,
                    rss_guid=news_id,
                    raw_payload=str(row),
                )
                file_written += 1

        total_rows += file_rows
        total_written += file_written
        logger.info("%s: read=%s, upsert_attempts=%s", file_path.name, file_rows, file_written)
        print(f"{file_path.name}: read={file_rows}, upsert_attempts={file_written}")

    logger.info(
        "Completed CSV sync. files=%s, read_rows=%s, upsert_attempts=%s",
        total_files,
        total_rows,
        total_written,
    )
    print(
        f"Completed CSV sync. files={total_files}, read_rows={total_rows}, "
        f"upsert_attempts={total_written}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
