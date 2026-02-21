#!/usr/bin/env python3
"""
Sync BSE RSS announcements into local database.
"""

import argparse
import os
import sys
from datetime import datetime, timedelta
import json

import requests


def main():
    """Main.

    Args:
        None.

    Returns:
        Any: Method output for caller use.
    """
    parser = argparse.ArgumentParser(description="Sync BSE RSS announcements")
    parser.add_argument(
        "--db-path",
        default="data/equity_tracker.db",
        help="SQLite database path (default: data/equity_tracker.db)",
    )
    parser.add_argument(
        "--rss-url",
        action="append",
        default=[],
        help="RSS URL to ingest (can be provided multiple times).",
    )
    parser.add_argument("--api-url", default="", help="BSE API URL endpoint")
    parser.add_argument("--from-date", default="", help="API mode start date YYYYMMDD")
    parser.add_argument("--to-date", default="", help="API mode end date YYYYMMDD")
    parser.add_argument("--pages", type=int, default=100, help="API mode max pages")
    parser.add_argument("--category", default="-1", help="API mode strCat")
    parser.add_argument("--search", default="P", help="API mode strSearch")
    parser.add_argument("--type", dest="filing_type", default="C", help="API mode strType")
    parser.add_argument("--scrip-code", default="", help="API mode strScrip (optional BSE code)")
    parser.add_argument("--debug-api", action="store_true", help="Print first-page API diagnostics before ingest")
    args = parser.parse_args()

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sys.path.insert(0, project_root)

    from database.db_manager import DatabaseManager
    from services.bse_feed_service import BSEFeedService
    from utils.config import config
    from utils.logger import get_logger

    logger = get_logger(__name__)

    db = DatabaseManager(args.db_path)
    feed_service = BSEFeedService(db)

    def diagnose_api(api_url: str, from_date: str, to_date: str):
        """Print first-page API diagnostics to help troubleshoot zero-row responses."""
        params = {
            "pageno": 1,
            "strCat": args.category,
            "strPrevDate": from_date,
            "strScrip": (args.scrip_code or "").strip(),
            "strSearch": args.search,
            "strToDate": to_date,
            "strType": args.filing_type,
            "subcategory": "",
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0",
            "Referer": "https://www.bseindia.com/",
        }
        print("API DIAGNOSTICS")
        print(f"URL: {api_url}")
        print(f"Params: {params}")
        try:
            resp = requests.get(api_url, params=params, headers=headers, timeout=30)
            print(f"HTTP: {resp.status_code}")
            print(f"Content-Type: {resp.headers.get('content-type')}")
            payload = resp.json()
            keys = list(payload.keys()) if isinstance(payload, dict) else []
            print(f"Payload keys: {keys[:15]}")
            rows = None
            if isinstance(payload, dict):
                for key in ("Table", "Table1", "Data", "data", "results"):
                    if isinstance(payload.get(key), list):
                        rows = payload.get(key)
                        print(f"Rows key: {key}")
                        break
            row_count = len(rows) if isinstance(rows, list) else 0
            print(f"Row count (page 1): {row_count}")
            if row_count:
                print("Sample row keys:", list(rows[0].keys())[:25])
                print("Sample row:", json.dumps(rows[0], ensure_ascii=False)[:1000])
            else:
                print("Payload snippet:", json.dumps(payload, ensure_ascii=False)[:1000])
        except Exception as exc:
            print(f"Diagnostics failed: {exc}")

    if args.from_date or args.to_date:
        to_date = args.to_date or datetime.now().strftime("%Y%m%d")
        from_date = args.from_date or (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")
        api_url = args.api_url or config.BSE_API_ENDPOINT
        if args.debug_api:
            diagnose_api(api_url=api_url, from_date=from_date, to_date=to_date)
        try:
            count = feed_service.ingest_api_range(
                api_url=api_url,
                start_date_yyyymmdd=from_date,
                end_date_yyyymmdd=to_date,
                max_pages=args.pages,
                category=args.category,
                search=args.search,
                filing_type=args.filing_type,
                scrip_code=(args.scrip_code or "").strip() or None,
            )
            logger.info("Ingested %s item(s) from API: %s [%s..%s]", count, api_url, from_date, to_date)
            print(f"Ingested {count} item(s) from API: {api_url} [{from_date}..{to_date}]")
            return 0
        except Exception as exc:
            logger.exception("Failed API ingest for %s: %s", api_url, exc)
            print(f"Failed API ingest for {api_url}: {exc}")
            return 1

    urls = args.rss_url or config.BSE_RSS_URLS
    if not urls:
        logger.error("No RSS URLs provided. Use --rss-url or API mode.")
        print("No RSS URLs provided.")
        print("Use --rss-url, or provide --from-date/--to-date for API mode.")
        return 1

    total = 0
    for url in urls:
        try:
            count = feed_service.ingest_rss_feed(url)
            total += count
            logger.info("Ingested %s item(s) from: %s", count, url)
            print(f"Ingested {count} item(s) from: {url}")
        except Exception as exc:
            logger.exception("Failed for %s: %s", url, exc)
            print(f"Failed for {url}: {exc}")

    logger.info("Total ingested items: %s", total)
    print(f"Total ingested items: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
