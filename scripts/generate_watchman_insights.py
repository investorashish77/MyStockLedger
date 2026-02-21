#!/usr/bin/env python3
"""
Generate Result/Concall insights from filings as a standalone job.

Examples:
  python3 scripts/generate_watchman_insights.py --user-id 1
  python3 scripts/generate_watchman_insights.py --user-id 1 --force
"""

import argparse
import os
import sys


def main() -> int:
    """Main.

    Args:
        None.

    Returns:
        Any: Method output for caller use.
    """
    parser = argparse.ArgumentParser(description="Generate watchman insights for a user.")
    parser.add_argument("--db-path", default="data/equity_tracker.db", help="SQLite DB path")
    parser.add_argument("--user-id", type=int, required=True, help="Target user_id")
    parser.add_argument("--force", action="store_true", help="Regenerate even if snapshots already exist")
    args = parser.parse_args()

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sys.path.insert(0, project_root)

    from database.db_manager import DatabaseManager
    from services.ai_summary_service import AISummaryService
    from services.watchman_service import WatchmanService
    from utils.logger import get_logger

    logger = get_logger(__name__)
    db = DatabaseManager(args.db_path)
    ai = AISummaryService(db_manager=db)
    watchman = WatchmanService(db, ai)

    if not ai.is_available():
        print("AI provider is not configured/available. Check .env")
        return 1

    result = watchman.run_for_user(user_id=args.user_id, force_regenerate=args.force)
    logger.info("Watchman standalone run user_id=%s force=%s result=%s", args.user_id, args.force, result)
    print("Watchman run completed:")
    print(f"- user_id: {args.user_id}")
    print(f"- force: {args.force}")
    print(f"- generated: {result['generated']}")
    print(f"- skipped_existing: {result['skipped_existing']}")
    print(f"- not_available: {result['not_available']}")
    print(f"- failed: {result['failed']}")
    print(f"- stocks: {result['stocks']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
