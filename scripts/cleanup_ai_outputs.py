#!/usr/bin/env python3
"""
Clean AI-generated outputs so they can be regenerated.

Targets:
- insight_snapshots (RESULT_SUMMARY, CONCALL_SUMMARY)
- analyst_consensus
- ai_response_cache entries for summary/analyst_consensus

Usage:
  python3 scripts/cleanup_ai_outputs.py --dry-run
  python3 scripts/cleanup_ai_outputs.py --execute
  python3 scripts/cleanup_ai_outputs.py --execute --user-id 1
"""

import argparse
import os
import sqlite3
import sys


def main() -> int:
    """Main.

    Args:
        None.

    Returns:
        Any: Method output for caller use.
    """
    parser = argparse.ArgumentParser(description="Cleanup AI-generated summaries for retesting.")
    parser.add_argument("--db-path", default="data/equity_tracker.db", help="SQLite DB path")
    parser.add_argument("--user-id", type=int, default=None, help="Optional scope to one user")
    parser.add_argument("--dry-run", action="store_true", help="Preview counts only")
    parser.add_argument("--execute", action="store_true", help="Perform deletion")
    args = parser.parse_args()

    if not args.dry_run and not args.execute:
        print("Choose one: --dry-run or --execute")
        return 1

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sys.path.insert(0, project_root)
    from utils.logger import get_logger

    logger = get_logger(__name__)

    conn = sqlite3.connect(args.db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    params = []
    stock_scope = ""
    if args.user_id is not None:
        stock_scope = " AND stock_id IN (SELECT stock_id FROM stocks WHERE user_id = ?) "
        params = [args.user_id]

    counts = {}
    cur.execute(
        f"""
        SELECT COUNT(*) AS c
        FROM insight_snapshots
        WHERE insight_type IN ('RESULT_SUMMARY', 'CONCALL_SUMMARY')
        {stock_scope}
        """,
        tuple(params),
    )
    counts["insight_snapshots"] = int(cur.fetchone()["c"])

    cur.execute(
        f"""
        SELECT COUNT(*) AS c
        FROM analyst_consensus
        WHERE 1=1
        {stock_scope}
        """,
        tuple(params),
    )
    counts["analyst_consensus"] = int(cur.fetchone()["c"])

    # cache is global by prompt hash; keep cleanup focused on task types
    cur.execute(
        """
        SELECT COUNT(*) AS c
        FROM ai_response_cache
        WHERE task_type IN ('summary', 'analyst_consensus')
        """
    )
    counts["ai_response_cache"] = int(cur.fetchone()["c"])

    print("Cleanup targets:")
    for key, value in counts.items():
        print(f"- {key}: {value}")

    if args.dry_run:
        logger.info("Dry-run cleanup done user_id=%s counts=%s", args.user_id, counts)
        conn.close()
        return 0

    cur.execute(
        f"""
        DELETE FROM insight_snapshots
        WHERE insight_type IN ('RESULT_SUMMARY', 'CONCALL_SUMMARY')
        {stock_scope}
        """,
        tuple(params),
    )
    deleted_snapshots = cur.rowcount or 0

    cur.execute(
        f"""
        DELETE FROM analyst_consensus
        WHERE 1=1
        {stock_scope}
        """,
        tuple(params),
    )
    deleted_analyst = cur.rowcount or 0

    cur.execute(
        """
        DELETE FROM ai_response_cache
        WHERE task_type IN ('summary', 'analyst_consensus')
        """
    )
    deleted_cache = cur.rowcount or 0

    conn.commit()
    conn.close()

    result = {
        "insight_snapshots": deleted_snapshots,
        "analyst_consensus": deleted_analyst,
        "ai_response_cache": deleted_cache,
    }
    print("Deleted:")
    for key, value in result.items():
        print(f"- {key}: {value}")
    logger.info("Cleanup executed user_id=%s result=%s", args.user_id, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
