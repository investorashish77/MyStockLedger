#!/usr/bin/env python3
"""
Delete incorrect quarter insight snapshots.

Examples:
  python3 scripts/cleanup_insights_quarter.py --quarter "Q4 FY26" --dry-run
  python3 scripts/cleanup_insights_quarter.py --quarter "Q4 FY26"
  python3 scripts/cleanup_insights_quarter.py --quarter "Q4 FY26" --user-id 1
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
    parser = argparse.ArgumentParser(description="Cleanup insight snapshots by quarter label.")
    parser.add_argument(
        "--db-path",
        default="data/equity_tracker.db",
        help="SQLite database path (default: data/equity_tracker.db)",
    )
    parser.add_argument(
        "--quarter",
        default="Q4 FY26",
        help='Quarter label to remove (default: "Q4 FY26")',
    )
    parser.add_argument(
        "--user-id",
        type=int,
        default=None,
        help="Optional user_id scope; if omitted, removes for all users.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show matching row count without deleting.",
    )
    args = parser.parse_args()

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sys.path.insert(0, project_root)
    from utils.logger import get_logger

    logger = get_logger(__name__)

    q_with_space = args.quarter.strip()
    q_no_space = q_with_space.replace(" ", "")
    conn = sqlite3.connect(args.db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    where_clause = "i.quarter_label IN (?, ?)"
    params = [q_with_space, q_no_space]
    if args.user_id is not None:
        where_clause += " AND s.user_id = ?"
        params.append(args.user_id)

    count_sql = f"""
        SELECT COUNT(*) AS cnt
        FROM insight_snapshots i
        JOIN stocks s ON s.stock_id = i.stock_id
        WHERE {where_clause}
    """
    cursor.execute(count_sql, params)
    row_count = int(cursor.fetchone()["cnt"])

    if args.dry_run:
        print(f"[DRY RUN] Matching snapshots: {row_count}")
        logger.info("Dry run cleanup for quarter=%s user_id=%s matches=%s", q_with_space, args.user_id, row_count)
        conn.close()
        return 0

    delete_sql = f"""
        DELETE FROM insight_snapshots
        WHERE snapshot_id IN (
            SELECT i.snapshot_id
            FROM insight_snapshots i
            JOIN stocks s ON s.stock_id = i.stock_id
            WHERE {where_clause}
        )
    """
    cursor.execute(delete_sql, params)
    deleted = cursor.rowcount if cursor.rowcount is not None else 0
    conn.commit()
    conn.close()

    print(f"Deleted snapshots: {deleted}")
    logger.info("Cleanup complete for quarter=%s user_id=%s deleted=%s", q_with_space, args.user_id, deleted)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
