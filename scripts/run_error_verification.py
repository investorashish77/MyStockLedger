#!/usr/bin/env python3
"""
Generate parser verification report from financial parser logs.

Examples:
  python3 scripts/run_error_verification.py
  python3 scripts/run_error_verification.py --limit 100
  python3 scripts/run_error_verification.py --since "2026-02-24 00:00:00"
  python3 scripts/run_error_verification.py --all-events
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path


def _parse_since(since_text: str):
    """Parse optional since timestamp."""
    if not since_text:
        return None
    return datetime.strptime(since_text.strip(), "%Y-%m-%d %H:%M:%S")


def main() -> int:
    """Run parser verification report generation."""
    parser = argparse.ArgumentParser(description="Run parser error verification report.")
    parser.add_argument("--db-path", default="data/equity_tracker.db", help="SQLite DB path")
    parser.add_argument("--log-path", default="logs/equity_tracker.log", help="Application log path")
    parser.add_argument("--limit", type=int, default=200, help="Max rows in report")
    parser.add_argument(
        "--since",
        default="",
        help='Optional timestamp lower bound, format "YYYY-MM-DD HH:MM:SS"',
    )
    parser.add_argument(
        "--all-events",
        action="store_true",
        help="Do not collapse to latest per company.",
    )
    parser.add_argument(
        "--out",
        default="",
        help="Output markdown path. Default: logs/parser_verification_YYYYMMDD_HHMMSS.md",
    )
    args = parser.parse_args()

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sys.path.insert(0, project_root)

    from services.error_verification_service import ErrorVerificationService
    from utils.logger import get_logger

    logger = get_logger(__name__)
    since = _parse_since(args.since) if args.since else None
    verifier = ErrorVerificationService(db_path=args.db_path, log_path=args.log_path)
    rows = verifier.generate_report_rows(
        limit=args.limit,
        since=since,
        latest_per_company=(not args.all_events),
    )

    out_path = args.out.strip()
    if not out_path:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = f"logs/parser_verification_{stamp}.md"

    report_path = verifier.write_markdown_report(rows, out_path)
    logger.info("Parser verification report generated rows=%s path=%s", len(rows), report_path)

    print(f"Report rows: {len(rows)}")
    print(f"Report path: {report_path}")
    print("\nTop entries:")
    for row in rows[:10]:
        print(f"- {row['Company']} | {row['Output']} | {row['Score']} | {row['Notes']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

