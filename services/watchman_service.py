"""
Watchman Service
Builds quarter-specific portfolio insights from filings.
"""

from datetime import datetime, date
import re
from urllib.parse import urlparse
from typing import Dict, List, Optional, Tuple

from database.db_manager import DatabaseManager
from services.ai_summary_service import AISummaryService
from utils.config import config
from utils.logger import get_logger


class WatchmanService:
    """Material news analyst for portfolio-level Results/Concall insights."""

    INSIGHT_RESULT = "RESULT_SUMMARY"
    INSIGHT_CONCALL = "CONCALL_SUMMARY"
    DAILY_RUN_SETTING_KEY = "watchman_last_run_date"
    MIN_SCORE_BY_INSIGHT = {
        INSIGHT_RESULT: 6,
        INSIGHT_CONCALL: 8,
    }
    MATERIAL_SCAN_LAST_RUN_KEY_PREFIX = "watchman_material_last_run_date_user_"
    MATERIAL_SCAN_LAST_ID_KEY_PREFIX = "watchman_material_last_announcement_id_user_"
    MATERIAL_CATEGORY_KEYWORDS = {
        "New Order Win": [
            "order win", "new order", "work order", "order received", "receives order",
            "new export order", "contract awarded", "contract win"
        ],
        "New Plant Commissioning": [
            "plant commissioned", "commissioning", "commencement of commercial production",
            "new plant", "capacity expansion", "capacity commissioned"
        ],
        "New Acquisition": [
            "acquisition", "acquire", "takeover", "merger", "amalgamation"
        ],
        "Preferential Share": [
            "preferential issue", "preferential allotment", "preferential shares"
        ],
        "Fund Raise": [
            "fund raise", "qip", "rights issue", "debenture", "ncd", "fpo", "raise capital"
        ],
        "Joint Venture": [
            "joint venture", "jv agreement", "strategic alliance"
        ],
    }

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

    def run_daily_material_scan(self, user_id: int, daily_only: bool = True) -> Dict[str, int]:
        """Scan newly ingested announcements and raise short material alerts for portfolio companies."""
        today = date.today().isoformat()
        run_key = f"{self.MATERIAL_SCAN_LAST_RUN_KEY_PREFIX}{user_id}"
        if daily_only and self.db.get_setting(run_key) == today:
            return {"scanned": 0, "alerts_created": 0, "skipped_daily": 1}

        last_id_key = f"{self.MATERIAL_SCAN_LAST_ID_KEY_PREFIX}{user_id}"
        last_seen_id = int(self.db.get_setting(last_id_key, "0") or "0")
        announcements = self.db.get_bse_announcements_since_id(last_seen_id, limit=8000)
        stocks = self.db.get_user_stocks_with_symbol_master(user_id)
        if not stocks:
            self.db.set_setting(run_key, today)
            if announcements:
                self.db.set_setting(last_id_key, str(max(a.get("announcement_id", 0) for a in announcements)))
            return {"scanned": len(announcements), "alerts_created": 0, "skipped_daily": 0}

        symbol_id_map = {s.get("symbol_id"): s for s in stocks if s.get("symbol_id")}
        bse_code_map = {str(s.get("bse_code")).strip(): s for s in stocks if s.get("bse_code")}
        alerts_created = 0
        max_seen = last_seen_id
        for announcement in announcements:
            ann_id = int(announcement.get("announcement_id") or 0)
            if ann_id > max_seen:
                max_seen = ann_id
            stock = self._match_announcement_to_stock_for_material(announcement, stocks, symbol_id_map, bse_code_map)
            if not stock:
                continue
            category = self._classify_material_category(announcement.get("headline") or "")
            if not category:
                continue
            dedupe_key = self._material_notification_dedupe_key(stock, announcement, category)
            if self.db.has_notification_dedupe(user_id, "MATERIAL_ALERT", dedupe_key):
                continue
            short_summary = self._build_material_summary(announcement.get("headline") or "")
            title = f"{category} Alert 🚨"
            detail_url, alt_url = self._resolve_document_urls(announcement.get("attachment_url") or "")
            detail_url = detail_url or "-"
            message = (
                f"Company: {stock.get('company_name') or stock.get('symbol')}\n\n"
                f"🧾Summary: {short_summary}\n\n"
                f"📁Details: {detail_url}"
            )
            if alt_url:
                message = f"{message}\nAlternate: {alt_url}"
            self.db.add_notification(
                user_id=user_id,
                notif_type="MATERIAL_ALERT",
                title=title,
                message=message,
                metadata={
                    "stock_id": stock.get("stock_id"),
                    "symbol": stock.get("symbol"),
                    "announcement_id": ann_id,
                    "category": category,
                    "detail_url": detail_url,
                    "alternate_url": alt_url,
                },
                dedupe_key=dedupe_key
            )
            alerts_created += 1

        self.db.set_setting(run_key, today)
        self.db.set_setting(last_id_key, str(max_seen))
        self.logger.info(
            "Watchman material scan complete user=%s scanned=%s alerts=%s last_id=%s",
            user_id, len(announcements), alerts_created, max_seen
        )
        return {"scanned": len(announcements), "alerts_created": alerts_created, "skipped_daily": 0}

    def _match_announcement_to_stock_for_material(
        self,
        announcement: Dict,
        stocks: List[Dict],
        symbol_id_map: Dict[int, Dict],
        bse_code_map: Dict[str, Dict],
    ) -> Optional[Dict]:
        """Match a new announcement to one of the portfolio stocks for material scanning."""
        sid = announcement.get("symbol_id")
        if sid in symbol_id_map:
            return symbol_id_map[sid]

        scrip_code = str(announcement.get("scrip_code") or "").strip()
        if scrip_code and scrip_code in bse_code_map:
            return bse_code_map[scrip_code]

        headline = (announcement.get("headline") or "").upper()
        headline_clean = re.sub(r"[^A-Z0-9 ]+", " ", headline)
        for stock in stocks:
            symbol = (stock.get("symbol") or "").upper().replace(".NS", "").replace(".BO", "")
            if symbol and re.search(rf"\b{re.escape(symbol)}\b", headline_clean):
                return stock
            company = (stock.get("company_name") or "").upper()
            alias = re.sub(r"\b(LIMITED|LTD|INDIA)\b", "", company).strip()
            if alias and alias in headline_clean:
                return stock
        return None

    def _classify_material_category(self, headline: str) -> Optional[str]:
        """Return one critical material category if matched, else None."""
        text = (headline or "").lower()
        for category, keywords in self.MATERIAL_CATEGORY_KEYWORDS.items():
            if any(keyword in text for keyword in keywords):
                return category
        return None

    @staticmethod
    def _material_notification_dedupe_key(stock: Dict, announcement: Dict, category: str) -> str:
        """Stable dedupe key for material alerts across repeated scans."""
        exchange_ref_id = (announcement.get("exchange_ref_id") or "").strip().lower()
        rss_guid = (announcement.get("rss_guid") or "").strip().lower()
        attachment_url = (announcement.get("attachment_url") or "").strip()
        headline = (announcement.get("headline") or "").strip().lower()
        headline = re.sub(r"\s+", " ", headline)
        headline = re.sub(r"[^a-z0-9 ]+", "", headline)
        announcement_date = str(announcement.get("announcement_date") or "").strip()[:10]
        scrip_code = str(announcement.get("scrip_code") or "").strip()

        source_ref = exchange_ref_id or rss_guid
        if not source_ref and attachment_url:
            parsed = urlparse(attachment_url)
            url_path = (parsed.path or "").strip().lower()
            source_ref = f"{url_path}|{(parsed.query or '').strip().lower()}".strip("|")
        if not source_ref:
            source_ref = f"{scrip_code}|{announcement_date}|{headline}"

        symbol = (stock.get("symbol") or "").strip().upper()
        return f"{symbol}|{category.strip().lower()}|{str(source_ref).strip()}"

    @staticmethod
    def _build_material_summary(headline: str, max_words: int = 20) -> str:
        """Build a concise alert summary from headline text."""
        words = re.sub(r"\s+", " ", (headline or "").strip()).split(" ")
        words = [w for w in words if w]
        if not words:
            return "Material filing identified."
        if len(words) <= max_words:
            return " ".join(words)
        return f"{' '.join(words[:max_words])}..."

    @staticmethod
    def _join_base_and_filename(base_url: str, filename: str) -> str:
        """Join configured base URL and PDF filename."""
        base = (base_url or "").strip()
        if not base:
            return ""
        if not base.endswith("/"):
            base = f"{base}/"
        return f"{base}{filename}"

    @staticmethod
    def _extract_pdf_filename(value: str) -> str:
        """Extract file name from URL/path when announcement payload has relative path."""
        text = (value or "").strip()
        if not text:
            return ""
        parsed = urlparse(text)
        candidate = parsed.path.split("/")[-1] if parsed.path else text.split("/")[-1]
        candidate = candidate.split("?")[0].strip()
        return candidate if candidate.lower().endswith(".pdf") else ""

    @classmethod
    def _resolve_document_urls(cls, raw_value: str) -> Tuple[str, str]:
        """Resolve primary + alternate filing URLs from raw attachment value."""
        value = (raw_value or "").strip()
        if not value:
            return "", ""
        filename = cls._extract_pdf_filename(value)
        if filename:
            # Prefer AttachHis for material alerts; keep AttachLive as fallback.
            primary = cls._join_base_and_filename(config.BSE_ATTACH_PRIMARY_BASE, filename)
            alternate = cls._join_base_and_filename(config.BSE_ATTACH_SECONDARY_BASE, filename)
            if value.startswith("http://") or value.startswith("https://"):
                if value not in {primary, alternate}:
                    alternate = value
            return primary, alternate
        if value.startswith("http://") or value.startswith("https://"):
            return value, ""
        return f"https://www.bseindia.com/{value.lstrip('/')}", ""

    def _generate_one_insight_for_stock(
        self,
        stock: Dict,
        quarter_label: str,
        filings: List[Dict],
        insight_type: str,
        force_regenerate: bool = False,
    ) -> Dict[str, int]:
        """Generate one insight for stock.

        Args:
            stock: Input parameter.
            quarter_label: Input parameter.
            filings: Input parameter.
            insight_type: Input parameter.
            force_regenerate: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        stock_id = stock["stock_id"]
        symbol_id = self._resolve_symbol_id_for_stock(stock, filings)
        if not symbol_id:
            return {"generated": 0, "skipped_existing": 0, "not_available": 1, "failed": 0}

        existing = self.db.get_global_insight_snapshot(symbol_id, quarter_label, insight_type)
        if existing and not force_regenerate:
            return {"generated": 0, "skipped_existing": 1, "not_available": 0, "failed": 0}

        ranked_candidates = self._rank_candidates(filings, quarter_label, insight_type)
        if not ranked_candidates:
            self.db.upsert_global_insight_snapshot(
                symbol_id=symbol_id,
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
            supplementary_urls: List[str] = []
            if insight_type == self.INSIGHT_RESULT:
                supplementary_urls = self._collect_results_supplementary_urls(
                    filings=filings,
                    quarter_label=quarter_label,
                    primary_candidate=candidate,
                )
            generated = self.ai_service.generate_summary(
                stock_symbol=stock.get("symbol") or "",
                announcement_text=f"{candidate.get('headline') or ''}\n{candidate.get('announcement_summary') or ''}".strip(),
                announcement_type=announcement_type,
                document_url=candidate.get("pdf_link"),
                supplementary_document_urls=supplementary_urls,
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
            self.db.upsert_global_insight_snapshot(
                symbol_id=symbol_id,
                quarter_label=quarter_label,
                insight_type=insight_type,
                summary_text="Not available for this quarter.",
                sentiment="NEUTRAL",
                status="FAILED",
                source_filing_id=fallback.get("filing_id"),
                source_ref=fallback.get("source_ref"),
                provider=summary.get("provider") if summary else self.ai_service.provider,
                model_version=None,
            )
            return {"generated": 0, "skipped_existing": 0, "not_available": 0, "failed": 1}

        self.db.upsert_global_insight_snapshot(
            symbol_id=symbol_id,
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

    def _resolve_symbol_id_for_stock(self, stock: Dict, filings: List[Dict]) -> Optional[int]:
        """Resolve symbol id for stock.

        Args:
            stock: Input parameter.
            filings: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        for filing in filings:
            sid = filing.get("symbol_id")
            if sid:
                return sid
        symbol = (stock.get("symbol") or "").upper()
        symbol = symbol.replace(".NS", "").replace(".BO", "")
        mapped = self.db.get_symbol_by_symbol(symbol)
        if mapped:
            return mapped.get("symbol_id")
        return None

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
            if not self._is_allowed_filing_for_insight(filing, insight_type):
                continue
            score = self._candidate_score(filing, insight_type)
            candidates.append((score, self._normalized_dt_key(filing.get("announcement_date")), filing))
        if not candidates:
            return []
        candidates.sort(key=lambda row: (row[0], row[1]), reverse=True)
        min_score = self.MIN_SCORE_BY_INSIGHT.get(insight_type, 0)
        ranked = [filing for score, _, filing in candidates if score >= min_score]
        if not ranked:
            # Graceful fallback: when strict threshold misses generic "results attached herewith"
            # filings, allow best positive-scored candidates.
            ranked = [filing for score, _, filing in candidates if score > 0][:3]
        return ranked

    def _collect_results_supplementary_urls(
        self,
        filings: List[Dict],
        quarter_label: str,
        primary_candidate: Dict,
    ) -> List[str]:
        """Collect same-quarter investor/earnings presentation PDFs for result summarization."""
        out: List[str] = []
        primary_link = (primary_candidate.get("pdf_link") or "").strip()
        for filing in filings:
            if filing.get("filing_id") == primary_candidate.get("filing_id"):
                continue
            if self._quarter_from_filing(filing) != quarter_label:
                continue
            link = (filing.get("pdf_link") or "").strip()
            if not link or link == primary_link:
                continue
            text = f"{filing.get('headline') or ''} {filing.get('category') or ''}".lower()
            if any(
                token in text
                for token in (
                    "investor presentation",
                    "earnings presentation",
                    "result presentation",
                    "q3 presentation",
                    "q4 presentation",
                    "q2 presentation",
                    "q1 presentation",
                )
            ):
                out.append(link)
        # Preserve order, unique, keep small.
        seen = set()
        unique = []
        for u in out:
            if u in seen:
                continue
            seen.add(u)
            unique.append(u)
        return unique[:2]

    def _resolve_latest_quarter_for_stock(self, stock_id: int, filings: List[Dict]) -> Optional[str]:
        """Resolve latest quarter for stock.

        Args:
            stock_id: Input parameter.
            filings: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
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
    def _is_allowed_filing_for_insight(filing: Dict, insight_type: str) -> bool:
        """Return True when filing can be considered for the target insight.

        Args:
            filing: Input parameter.
            insight_type: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        category = filing.get("category")
        c = (category or "").strip().lower()
        text = f"{filing.get('headline') or ''} {filing.get('announcement_summary') or ''} {category or ''}".lower()
        if insight_type == WatchmanService.INSIGHT_RESULT:
            if any(marker in text for marker in ("monitoring agency report", "monitoring agency")):
                return False
            if c == "results":
                return True
            if any(marker in text for marker in ("conference call", "earnings call", "concall", "transcript")) and "financial result" not in text:
                return False
            # Some exchanges tag result packs as "General Update"/"Announcements".
            positive_markers = (
                "financial result",
                "results for the quarter",
                "unaudited financial",
                "audited financial",
                "statement of financial results",
                "outcome of the board meeting",
                "outcome for the just concluded meeting",
                "results attached herewith",
            )
            return any(marker in text for marker in positive_markers)
        if insight_type == WatchmanService.INSIGHT_CONCALL:
            if c == "earnings call":
                return True
            return any(marker in text for marker in ("conference call", "earnings call", "concall", "transcript"))
        return False

    @staticmethod
    def _candidate_score(filing: Dict, insight_type: str) -> int:
        """Candidate score.

        Args:
            filing: Input parameter.
            insight_type: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        text = f"{filing.get('headline') or ''} {filing.get('announcement_summary') or ''}".lower()
        score = 0
        category_text = (filing.get("category") or "").strip().lower()
        if filing.get("pdf_link"):
            score += 3
        if category_text == "results":
            score += 5
        if insight_type == WatchmanService.INSIGHT_RESULT:
            very_strong_positive = (
                "statement of financial results",
                "consolidated statement of financial results",
                "standalone statement of financial results",
                "unaudited financial results for the quarter",
                "audited financial results for the quarter",
                "results for the quarter ended",
                "limited review report",
            )
            strong_positive = (
                "financial result",
                "financial results",
                "unaudited financial",
                "audited financial",
                "standalone and consolidated",
            )
            weak_positive = ("standalone", "consolidated", "quarter ended")
            strong_negative = (
                "conference call", "earnings call", "transcript",
                "call recording", "audio recording", "audio link", "newspaper advertisement",
                "board meeting intimation", "notice of board meeting",
                "monitoring agency report", "post buyback", "voting results"
            )
            medium_negative = (
                "outcome of board meeting",
                "investor presentation",
                "earnings presentation",
                "quarterly presentation",
                "press release",
            )
            newspaper_negative = (
                "newspaper publication",
                "newspaper advertisement",
                "publication of un-audited financial results",
                "publication of unaudited financial results",
            )
            narrative_negative = (
                "to considered and approved",
                "interalia",
                "closure of trading window",
                "record date",
                "date of payment of interim dividend",
            )
            for kw in very_strong_positive:
                if kw in text:
                    score += 7
            for kw in strong_positive:
                if kw in text:
                    score += 4
            if "quarter and nine months ended" in text and "financial result" in text:
                score += 4
            if text.startswith("unaudited financial results") or text.startswith("audited financial results"):
                score += 8
            for kw in weak_positive:
                if kw in text:
                    score += 1
            for kw in medium_negative:
                if kw in text:
                    score -= 3
            if "press release" in text and "financial result" in text:
                score += 6
            for kw in newspaper_negative:
                if kw in text:
                    score -= 35
            for kw in narrative_negative:
                if kw in text:
                    score -= 10
            if "to considered and approved the followings" in text:
                score -= 12
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
        """Quarter from filing.

        Args:
            filing: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        d = WatchmanService._parse_date(filing.get("announcement_date"))
        if not d:
            return None
        return WatchmanService._reported_quarter_label_for_date(d)

    @staticmethod
    def _parse_date(value: str) -> Optional[date]:
        """Parse date.

        Args:
            value: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
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
        """Is usable result summary.

        Args:
            summary_text: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
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
        """Normalized dt key.

        Args:
            value: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        d = WatchmanService._parse_date(value)
        return d.isoformat() if d else ""
