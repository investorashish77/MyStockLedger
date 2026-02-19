"""
Watchman Service
Builds quarter-specific portfolio insights from filings.
"""

from datetime import datetime, date
import re
from typing import Dict, List, Optional, Tuple

from database.db_manager import DatabaseManager
from services.ai_summary_service import AISummaryService
from utils.logger import get_logger


class WatchmanService:
    """Material news analyst for portfolio-level Results/Concall insights."""

    INSIGHT_RESULT = "RESULT_SUMMARY"
    INSIGHT_CONCALL = "CONCALL_SUMMARY"
    DAILY_RUN_SETTING_KEY = "watchman_last_run_date"
    MIN_SCORE_BY_INSIGHT = {
        INSIGHT_RESULT: 7,
        INSIGHT_CONCALL: 8,
    }

    def __init__(self, db: DatabaseManager, ai_service: AISummaryService):
        self.db = db
        self.ai_service = ai_service
        self.logger = get_logger(__name__)

    def run_for_user(self, user_id: int, force_regenerate: bool = False) -> Dict[str, int]:
        """
        Generate quarter insights for each portfolio stock.
        - Creates one Results summary and one Concall summary for latest quarter per stock.
        - Never regenerates existing summaries unless force_regenerate=True.
        """
        stocks = self.db.get_user_stocks(user_id)
        if not stocks:
            return {"generated": 0, "skipped_existing": 0, "not_available": 0, "failed": 0, "stocks": 0}

        filings = self.db.get_user_filings(user_id=user_id, limit=5000)
        filings_by_stock = {}
        for filing in filings:
            filings_by_stock.setdefault(filing["stock_id"], []).append(filing)

        totals = {"generated": 0, "skipped_existing": 0, "not_available": 0, "failed": 0, "stocks": len(stocks)}
        for stock in stocks:
            stock_id = stock["stock_id"]
            stock_filings = filings_by_stock.get(stock_id, [])
            quarter = self._resolve_latest_quarter_for_stock(stock_id, stock_filings)
            if not quarter:
                quarter = self._reported_quarter_label_for_date(date.today())

            result = self._generate_one_insight_for_stock(
                stock=stock,
                quarter_label=quarter,
                filings=stock_filings,
                insight_type=self.INSIGHT_RESULT,
                force_regenerate=force_regenerate
            )
            concall = self._generate_one_insight_for_stock(
                stock=stock,
                quarter_label=quarter,
                filings=stock_filings,
                insight_type=self.INSIGHT_CONCALL,
                force_regenerate=force_regenerate
            )
            for key in totals:
                if key in result:
                    totals[key] += result[key]
                if key in concall:
                    totals[key] += concall[key]

        self.logger.info("Watchman run complete for user=%s: %s", user_id, totals)
        return totals

    def run_daily_if_due(self, user_id: int) -> Optional[Dict[str, int]]:
        """Run watchman once per calendar day."""
        today = date.today().isoformat()
        last_run = self.db.get_setting(self.DAILY_RUN_SETTING_KEY)
        if last_run == today:
            return None
        result = self.run_for_user(user_id=user_id, force_regenerate=False)
        self.db.set_setting(self.DAILY_RUN_SETTING_KEY, today)
        return result

    def _generate_one_insight_for_stock(
        self,
        stock: Dict,
        quarter_label: str,
        filings: List[Dict],
        insight_type: str,
        force_regenerate: bool = False,
    ) -> Dict[str, int]:
        stock_id = stock["stock_id"]
        existing = self.db.get_insight_snapshot(stock_id, quarter_label, insight_type)
        if existing and not force_regenerate:
            return {"generated": 0, "skipped_existing": 1, "not_available": 0, "failed": 0}

        ranked_candidates = self._rank_candidates(filings, quarter_label, insight_type)
        if not ranked_candidates:
            self.db.upsert_insight_snapshot(
                stock_id=stock_id,
                quarter_label=quarter_label,
                insight_type=insight_type,
                summary_text="Not available for this quarter.",
                sentiment="NEUTRAL",
                status="NOT_AVAILABLE",
                source_filing_id=None,
                source_ref=None,
                provider=None,
                model_version=None,
            )
            return {"generated": 0, "skipped_existing": 0, "not_available": 1, "failed": 0}

        announcement_type = "Results" if insight_type == self.INSIGHT_RESULT else "Earnings Call"
        selected_candidate = None
        summary = None
        for candidate in ranked_candidates:
            generated = self.ai_service.generate_summary(
                stock_symbol=stock.get("symbol") or "",
                announcement_text=f"{candidate.get('headline') or ''}\n{candidate.get('announcement_summary') or ''}".strip(),
                announcement_type=announcement_type,
                document_url=candidate.get("pdf_link"),
            )
            if not generated or not (generated.get("summary_text") or "").strip():
                continue
            if insight_type == self.INSIGHT_RESULT and not self._is_usable_result_summary(generated.get("summary_text")):
                continue
            selected_candidate = candidate
            summary = generated
            break

        if not selected_candidate or not summary:
            fallback = ranked_candidates[0]
            self.db.upsert_insight_snapshot(
                stock_id=stock_id,
                quarter_label=quarter_label,
                insight_type=insight_type,
                summary_text="Not available for this quarter.",
                sentiment="NEUTRAL",
                status="FAILED",
                source_filing_id=fallback.get("filing_id"),
                source_ref=fallback.get("source_ref"),
                provider=self.ai_service.provider,
                model_version=None,
            )
            return {"generated": 0, "skipped_existing": 0, "not_available": 0, "failed": 1}

        self.db.upsert_insight_snapshot(
            stock_id=stock_id,
            quarter_label=quarter_label,
            insight_type=insight_type,
            summary_text=summary.get("summary_text"),
            sentiment=summary.get("sentiment") or "NEUTRAL",
            status="GENERATED",
            source_filing_id=selected_candidate.get("filing_id"),
            source_ref=selected_candidate.get("source_ref"),
            provider=summary.get("provider") or self.ai_service.provider,
            model_version=None,
        )
        return {"generated": 1, "skipped_existing": 0, "not_available": 0, "failed": 0}

    def _rank_candidates(
        self,
        filings: List[Dict],
        quarter_label: str,
        insight_type: str
    ) -> List[Dict]:
        """Rank candidate filings for given quarter/insight type."""
        candidates = []
        for filing in filings:
            filing_quarter = self._quarter_from_filing(filing)
            if filing_quarter != quarter_label:
                continue
            if not self._is_allowed_category(filing.get("category"), insight_type):
                continue
            score = self._candidate_score(filing, insight_type)
            candidates.append((score, self._normalized_dt_key(filing.get("announcement_date")), filing))
        if not candidates:
            return []
        candidates.sort(key=lambda row: (row[0], row[1]), reverse=True)
        min_score = self.MIN_SCORE_BY_INSIGHT.get(insight_type, 0)
        ranked = [filing for score, _, filing in candidates if score >= min_score]
        return ranked

    def _resolve_latest_quarter_for_stock(self, stock_id: int, filings: List[Dict]) -> Optional[str]:
        latest_dt = None
        latest_quarter = None
        for filing in filings:
            d = self._parse_date(filing.get("announcement_date"))
            if not d:
                continue
            if latest_dt is None or d > latest_dt:
                latest_dt = d
                latest_quarter = self._reported_quarter_label_for_date(d)
        return latest_quarter

    @staticmethod
    def _is_allowed_category(category: str, insight_type: str) -> bool:
        c = (category or "").strip().lower()
        if insight_type == WatchmanService.INSIGHT_RESULT:
            return c == "results"
        if insight_type == WatchmanService.INSIGHT_CONCALL:
            return c == "earnings call"
        return False

    @staticmethod
    def _candidate_score(filing: Dict, insight_type: str) -> int:
        text = f"{filing.get('headline') or ''} {filing.get('announcement_summary') or ''}".lower()
        score = 0
        if filing.get("pdf_link"):
            score += 3
        if insight_type == WatchmanService.INSIGHT_RESULT:
            strong_positive = (
                "financial result", "financial results", "results for the quarter",
                "statement of unaudited", "statement of audited", "unaudited financial",
                "audited financial", "standalone and consolidated", "outcome of board meeting",
                "investor presentation", "earnings presentation", "quarterly presentation"
            )
            weak_positive = ("standalone", "consolidated", "quarter ended", "year ended")
            strong_negative = (
                "conference call", "earnings call", "transcript",
                "call recording", "audio recording", "audio link", "newspaper advertisement",
                "board meeting intimation", "notice of board meeting"
            )
            for kw in strong_positive:
                if kw in text:
                    score += 4
            for kw in weak_positive:
                if kw in text:
                    score += 1
            for kw in strong_negative:
                if kw in text:
                    score -= 6
        else:
            strong_positive = (
                "conference call transcript", "earnings call transcript", "transcript of earnings call",
                "conference call recording", "audio recording", "audio link", "webcast recording"
            )
            weak_positive = ("conference call", "earnings call", "investor call", "concall")
            strong_negative = (
                "financial result", "results for the quarter", "statement of unaudited",
                "statement of audited", "outcome of board meeting", "newspaper advertisement"
            )
            for kw in strong_positive:
                if kw in text:
                    score += 6
            for kw in weak_positive:
                if kw in text:
                    score += 2
            for kw in strong_negative:
                if kw in text:
                    score -= 4
            if "notice" in text and not any(
                key in text for key in ("transcript", "recording", "audio", "webcast")
            ):
                score -= 4
        return score

    @staticmethod
    def _quarter_from_filing(filing: Dict) -> Optional[str]:
        d = WatchmanService._parse_date(filing.get("announcement_date"))
        if not d:
            return None
        return WatchmanService._reported_quarter_label_for_date(d)

    @staticmethod
    def _parse_date(value: str) -> Optional[date]:
        if not value:
            return None
        text = str(value).strip()
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%a, %d %b %Y %H:%M:%S %Z"):
            try:
                return datetime.strptime(text, fmt).date()
            except Exception:
                pass
        # Fallback: pick first YYYY-MM-DD pattern.
        m = re.search(r"(\d{4}-\d{2}-\d{2})", text)
        if m:
            try:
                return datetime.strptime(m.group(1), "%Y-%m-%d").date()
            except Exception:
                return None
        return None

    @staticmethod
    def _reported_quarter_label_for_date(d: date) -> str:
        """
        Map filing announcement date to reported quarter label.
        Typical cadence:
        - Jan-Mar announcements => Q3 FYyy
        - Apr-Jun announcements => Q4 FYyy
        - Jul-Sep announcements => Q1 FY(y+1)
        - Oct-Dec announcements => Q2 FY(y+1)
        """
        month = d.month
        year = d.year
        if month >= 1 and month <= 3:
            quarter = "Q3"
            fy = year
        elif month >= 4 and month <= 6:
            quarter = "Q4"
            fy = year
        elif month >= 7 and month <= 9:
            quarter = "Q1"
            fy = year + 1
        else:
            quarter = "Q2"
            fy = year + 1
        return f"{quarter} FY{str(fy)[-2:]}"

    @staticmethod
    def _is_usable_result_summary(summary_text: str) -> bool:
        if not summary_text:
            return False
        text = summary_text.lower()
        metric_na_patterns = [
            r"revenue:\s*na",
            r"ebitda:\s*na",
            r"pat:\s*na",
            r"eps:\s*na",
        ]
        matches = sum(1 for pattern in metric_na_patterns if re.search(pattern, text))
        return matches < 4

    @staticmethod
    def _normalized_dt_key(value: str) -> str:
        d = WatchmanService._parse_date(value)
        return d.isoformat() if d else ""
