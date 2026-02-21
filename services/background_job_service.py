"""
Background Job Service
Processes long-running jobs asynchronously and emits user notifications.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta
from typing import Optional

from database.db_manager import DatabaseManager
from services.alert_service import AlertService
from services.ai_summary_service import AISummaryService
from services.bse_bhavcopy_service import BSEBhavcopyService
from services.watchman_service import WatchmanService
from utils.config import config
from utils.logger import get_logger


class BackgroundJobService:
    """DB-backed background worker for async tasks."""

    JOB_GENERATE_MISSING = "GENERATE_MISSING_INSIGHTS"
    JOB_REGENERATE = "REGENERATE_INSIGHTS"
    JOB_MATERIAL_SCAN = "MATERIAL_SCAN"
    JOB_SYNC_ANNOUNCEMENTS = "SYNC_ANNOUNCEMENTS"
    JOB_SYNC_BHAVCOPY = "SYNC_BHAVCOPY"
    SETTING_FILINGS_BACKFILL_DONE = "filings_api_backfill_done_v1"
    SETTING_FILINGS_LAST_SYNC_DATE = "filings_api_last_sync_date"
    SETTING_BHAVCOPY_LAST_SYNC_DATE = "bhavcopy_last_sync_date"

    def __init__(self, db: DatabaseManager, ai_service: AISummaryService):
        """Init.

        Args:
            db: Input parameter.
            ai_service: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        self.db = db
        self.ai_service = ai_service
        self.watchman = WatchmanService(db, ai_service)
        self.alert_service = AlertService(db)
        self.bhavcopy_service = BSEBhavcopyService(db)
        self.logger = get_logger(__name__)
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Start worker thread if not already running."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="background-job-worker", daemon=True)
        self._thread.start()
        self.logger.info("Background job worker started.")

    def stop(self, timeout: float = 2.0):
        """Stop worker thread."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        self.logger.info("Background job worker stopped.")

    def enqueue_insight_job(self, user_id: int, force_regenerate: bool = False) -> int:
        """Queue generate-missing/regenerate insights job."""
        job_type = self.JOB_REGENERATE if force_regenerate else self.JOB_GENERATE_MISSING
        return self.db.enqueue_background_job(
            job_type=job_type,
            requested_by=user_id,
            payload={"user_id": user_id, "force_regenerate": bool(force_regenerate)},
        )

    def enqueue_material_scan_job(self, user_id: int, daily_only: bool = True) -> int:
        """Queue portfolio material-announcement scan job."""
        return self.db.enqueue_background_job(
            job_type=self.JOB_MATERIAL_SCAN,
            requested_by=user_id,
            payload={"user_id": user_id, "daily_only": bool(daily_only)},
        )

    def enqueue_announcements_sync_job(self, user_id: int, force_full: bool = False) -> int:
        """Queue announcements sync job for a user's portfolio."""
        return self.db.enqueue_background_job(
            job_type=self.JOB_SYNC_ANNOUNCEMENTS,
            requested_by=user_id,
            payload={"user_id": user_id, "force_full": bool(force_full)},
        )

    def enqueue_bhavcopy_sync_job(self, user_id: int, force_full: bool = False) -> int:
        """Queue bhavcopy sync job."""
        return self.db.enqueue_background_job(
            job_type=self.JOB_SYNC_BHAVCOPY,
            requested_by=user_id,
            payload={"user_id": user_id, "force_full": bool(force_full)},
        )

    def _run_loop(self):
        """Run loop.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        while not self._stop_event.is_set():
            try:
                job = self.db.claim_next_background_job()
                if not job:
                    time.sleep(1.0)
                    continue
                self._execute_job(job)
            except Exception as exc:
                self.logger.error("Background worker loop error: %s", exc)
                time.sleep(1.0)

    def _execute_job(self, job: dict):
        """Execute job.

        Args:
            job: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        job_id = job.get("job_id")
        job_type = job.get("job_type")
        requested_by = job.get("requested_by")
        payload = job.get("payload") or {}
        user_id = payload.get("user_id") or requested_by
        if not user_id:
            self.db.complete_background_job(job_id, status="FAILED", progress=100, error_message="Missing user_id")
            return

        self.logger.info("Processing background job id=%s type=%s user_id=%s", job_id, job_type, user_id)
        try:
            if job_type in {self.JOB_GENERATE_MISSING, self.JOB_REGENERATE}:
                result = self.watchman.run_for_user(
                    user_id=int(user_id),
                    force_regenerate=bool(payload.get("force_regenerate", False))
                )
                self.db.complete_background_job(job_id, status="SUCCESS", progress=100, result=result)
                self.db.add_notification(
                    user_id=int(user_id),
                    notif_type="INSIGHTS_READY",
                    title="Insights Ready",
                    message=(
                        f"Quarter insights are ready. Generated: {result.get('generated', 0)}, "
                        f"Missing: {result.get('not_available', 0)}, Failed: {result.get('failed', 0)}."
                    ),
                    metadata={"job_id": job_id, "result": result},
                )
            elif job_type == self.JOB_MATERIAL_SCAN:
                result = self.watchman.run_daily_material_scan(
                    user_id=int(user_id),
                    daily_only=bool(payload.get("daily_only", True))
                )
                self.db.complete_background_job(job_id, status="SUCCESS", progress=100, result=result)
                if result.get("alerts_created", 0) > 0:
                    self.db.add_notification(
                        user_id=int(user_id),
                        notif_type="MATERIAL_SCAN_READY",
                        title="Material Announcement Scan Complete",
                        message=f"Watchman identified {result.get('alerts_created', 0)} material announcement alert(s).",
                        metadata={"job_id": job_id, "result": result},
                    )
            elif job_type == self.JOB_SYNC_ANNOUNCEMENTS:
                result = self._run_announcements_sync(user_id=int(user_id), force_full=bool(payload.get("force_full", False)))
                self.db.complete_background_job(job_id, status="SUCCESS", progress=100, result=result)
                self.db.add_notification(
                    user_id=int(user_id),
                    notif_type="ADMIN_SYNC_READY",
                    title="Announcements Sync Complete",
                    message=(
                        f"Fetched {result.get('fetched_rows', 0)} rows and synced "
                        f"{result.get('portfolio_filings', 0)} portfolio filing(s)."
                    ),
                    metadata={"job_id": job_id, "result": result},
                )
            elif job_type == self.JOB_SYNC_BHAVCOPY:
                result = self._run_bhavcopy_sync(force_full=bool(payload.get("force_full", False)))
                self.db.complete_background_job(job_id, status="SUCCESS", progress=100, result=result)
                self.db.add_notification(
                    user_id=int(user_id),
                    notif_type="ADMIN_SYNC_READY",
                    title="Bhavcopy Sync Complete",
                    message=f"Synced {result.get('rows_upserted', 0)} bhavcopy row(s).",
                    metadata={"job_id": job_id, "result": result},
                )
            else:
                self.db.complete_background_job(
                    job_id,
                    status="FAILED",
                    progress=100,
                    error_message=f"Unsupported job type: {job_type}",
                )
        except Exception as exc:
            self.logger.error("Background job failed id=%s: %s", job_id, exc)
            self.db.complete_background_job(job_id, status="FAILED", progress=100, error_message=str(exc))
            self.db.add_notification(
                user_id=int(user_id),
                notif_type="INSIGHTS_FAILED",
                title="Insights Generation Failed",
                message=f"Job #{job_id} failed. Open Insights and try again.",
                metadata={"job_id": job_id, "error": str(exc)},
            )

    def _run_announcements_sync(self, user_id: int, force_full: bool = False) -> dict:
        """Run BSE announcements ingestion + portfolio filings sync with incremental cursor.

        Note:
            Cursor keys are intentionally global, not user-scoped.
            Rationale: once announcements are ingested centrally, all users benefit and
            duplicate upstream API calls are avoided.
        """
        today = datetime.now().strftime("%Y%m%d")
        backfill_done = self.db.get_setting(self.SETTING_FILINGS_BACKFILL_DONE, "0") == "1"
        last_sync_date = self.db.get_setting(self.SETTING_FILINGS_LAST_SYNC_DATE, "")

        if force_full or not backfill_done:
            from_date = config.BSE_HISTORY_START_DATE
        else:
            from_date = last_sync_date or today

        if not from_date or len(from_date) != 8 or not from_date.isdigit():
            from_date = today

        fetched = self.alert_service.sync_bse_feed_for_portfolio(
            user_id=user_id,
            start_date_yyyymmdd=from_date,
            end_date_yyyymmdd=today,
            max_pages_per_symbol=max(5, int(config.BSE_API_MAX_PAGES / 10)),
        )
        filings = self.alert_service.sync_portfolio_filings(user_id=user_id, per_stock_limit=4)
        self.db.set_setting(self.SETTING_FILINGS_BACKFILL_DONE, "1")
        self.db.set_setting(self.SETTING_FILINGS_LAST_SYNC_DATE, today)
        return {
            "from_date": from_date,
            "to_date": today,
            "fetched_rows": fetched,
            "portfolio_filings": filings,
        }

    def _run_bhavcopy_sync(self, force_full: bool = False) -> dict:
        """Run BSE bhavcopy sync with incremental cursor."""
        today = datetime.now().date()
        last_sync_str = self.db.get_setting(self.SETTING_BHAVCOPY_LAST_SYNC_DATE, "")
        from_date = None
        if force_full or not last_sync_str:
            from_date = self._parse_yyyymmdd(config.BSE_HISTORY_START_DATE) or today
        else:
            parsed = self._parse_iso_date(last_sync_str)
            from_date = (parsed + timedelta(days=1)) if parsed else today
        if from_date > today:
            from_date = today
        rows = self.bhavcopy_service.fetch_and_ingest_range(
            from_date=from_date,
            to_date=today,
            skip_weekends=True,
            fail_fast=False,
        )
        self.db.set_setting(self.SETTING_BHAVCOPY_LAST_SYNC_DATE, today.strftime("%Y-%m-%d"))
        return {
            "from_date": from_date.strftime("%Y-%m-%d"),
            "to_date": today.strftime("%Y-%m-%d"),
            "rows_upserted": rows,
        }

    @staticmethod
    def _parse_yyyymmdd(value: str):
        try:
            return datetime.strptime((value or "").strip(), "%Y%m%d").date()
        except Exception:
            return None

    @staticmethod
    def _parse_iso_date(value: str):
        try:
            return datetime.strptime((value or "").strip(), "%Y-%m-%d").date()
        except Exception:
            return None
