#!/usr/bin/env python3
"""
Sync BSE announcement CSV files (daily snapshots) into bse_announcements table.
"""

import argparse
import csv
import os
import sys
import re
from datetime import datetime
from pathlib import Path

FILE_DATE_PATTERN = re.compile(r"(\d{8})(?=\.csv$)")
SYNC_KEY_PREFIX = "bse_csv_sync_sig"


def _clean(value):
    """Clean.

    Args:
        value: Input parameter.

    Returns:
        Any: Method output for caller use.
    """
    if value is None:
        return None
    text = str(value).strip()
    if text == "" or text.lower() == "nan":
        return None
    return text


def _resolve_symbol_id(db, scrip_code):
    """Resolve symbol id.

    Args:
        db: Input parameter.
        scrip_code: Input parameter.

    Returns:
        Any: Method output for caller use.
    """
    row = db.get_symbol_by_bse_code(scrip_code)
    return row["symbol_id"] if row else None


def _parse_yyyymmdd(raw_value, arg_name):
    """Parse YYYYMMDD argument value into date."""
    if not raw_value:
        return None
    try:
        return datetime.strptime(raw_value, "%Y%m%d").date()
    except ValueError as exc:
        raise ValueError(f"{arg_name} must be in YYYYMMDD format, got: {raw_value}") from exc


def _extract_file_date(file_name):
    """Extract YYYYMMDD date from CSV file name."""
    match = FILE_DATE_PATTERN.search(file_name)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y%m%d").date()
    except ValueError:
        return None


def _file_signature(file_path):
    """Build lightweight file signature (size + mtime)."""
    stat = file_path.stat()
    return f"{stat.st_size}:{stat.st_mtime_ns}"


def _sync_key(input_dir, file_path):
    """Build deterministic app_settings key for file sync state."""
    return f"{SYNC_KEY_PREFIX}::{str(input_dir.resolve())}::{file_path.name}"


def main():
    """Main.

    Args:
        None.

    Returns:
        Any: Method output for caller use.
    """
    parser = argparse.ArgumentParser(description="Sync announcement CSV files into bse_announcements")
    parser.add_argument("--db-path", default="data/equity_tracker.db")
    parser.add_argument("--input-dir", default="announcements", help="Directory containing daily announcement CSV files")
    parser.add_argument("--pattern", default="bse_announcements_*.csv", help="CSV filename glob pattern")
    parser.add_argument("--from-date", default="", help="Process files on/after YYYYMMDD (parsed from filename)")
    parser.add_argument("--to-date", default="", help="Process files on/before YYYYMMDD (parsed from filename)")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reprocess selected files even if unchanged and already synced before",
    )
    args = parser.parse_args()

    try:
        from_date = _parse_yyyymmdd(args.from_date, "--from-date")
        to_date = _parse_yyyymmdd(args.to_date, "--to-date")
    except ValueError as exc:
        print(str(exc))
        return 1
    if from_date and to_date and from_date > to_date:
        print(f"--from-date ({args.from_date}) cannot be after --to-date ({args.to_date})")
        return 1

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

    selected_files = []
    skipped_range = 0
    skipped_synced = 0

    for file_path in files:
        file_date = _extract_file_date(file_path.name)
        if from_date or to_date:
            if file_date is None:
                skipped_range += 1
                logger.warning("Skipping %s: unable to infer YYYYMMDD from filename for date-range filter", file_path.name)
                print(f"{file_path.name}: skipped (cannot infer YYYYMMDD filename date for range filter)")
                continue
            if from_date and file_date < from_date:
                skipped_range += 1
                continue
            if to_date and file_date > to_date:
                skipped_range += 1
                continue

        sync_key = _sync_key(input_dir, file_path)
        file_sig = _file_signature(file_path)
        if not args.force:
            synced_sig = db.get_setting(sync_key)
            if synced_sig == file_sig:
                skipped_synced += 1
                logger.info("%s: unchanged file already synced, skipping", file_path.name)
                print(f"{file_path.name}: skipped (already synced, unchanged)")
                continue

        selected_files.append((file_path, sync_key, file_sig))

    if not selected_files:
        print(
            "No files selected for sync after applying range/sync-state filters. "
            f"(range_skipped={skipped_range}, synced_skipped={skipped_synced})"
        )
        return 0

    total_files = 0
    total_rows = 0
    total_written = 0

    for file_path, sync_key, file_sig in selected_files:
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

        db.set_setting(sync_key, file_sig)
        total_rows += file_rows
        total_written += file_written
        logger.info("%s: read=%s, upsert_attempts=%s", file_path.name, file_rows, file_written)
        print(f"{file_path.name}: read={file_rows}, upsert_attempts={file_written}")

    logger.info(
        "Completed CSV sync. files=%s, read_rows=%s, upsert_attempts=%s, range_skipped=%s, synced_skipped=%s",
        total_files,
        total_rows,
        total_written,
        skipped_range,
        skipped_synced,
    )
    print(
        f"Completed CSV sync. files={total_files}, read_rows={total_rows}, "
        f"upsert_attempts={total_written}, range_skipped={skipped_range}, "
        f"synced_skipped={skipped_synced}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
