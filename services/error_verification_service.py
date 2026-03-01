"""
Error Verification Service
Builds parser quality report from financial parser logs.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from utils.logger import get_logger


@dataclass
class ParserEvent:
    """One parser audit event reconstructed from logs."""

    timestamp: datetime
    source: str
    table_score: int
    quarter: str
    metrics: Dict[str, Dict[str, str]]
    flags: str
    symbol: str = ""
    doc_ref: str = ""
    company_name: str = ""
    score: int = 0
    output: str = ""
    notes: str = ""


class ErrorVerificationService:
    """Generate parser verification report from equity_tracker.log."""

    _logger = get_logger(__name__)
    _PARSER_PREFIX = "Result parser output "
    _HINT_PREFIX = "Result parser hint "
    _METRICS = ("Revenue", "EBITDA", "PAT", "EPS")
    _MISSING = {"", "NA", "None", "none", "-", "--"}

    _MESSAGE_SPLIT_RE = re.compile(
        r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \| "
        r"(?P<level>[A-Z]+) \| (?P<logger>[^|]+) \| (?P<msg>.*)$"
    )
    _PARSER_HEADER_RE = re.compile(
        r"source=(?P<source>\S+)\s+table_score=(?P<table_score>-?\d+)\s+quarter=(?P<quarter>.*?)\s+Revenue\["
    )
    _METRIC_RE = {
        metric: re.compile(
            rf"{metric}\[val=(?P<val>.*?),\s*norm=(?P<norm>.*?),\s*yoy=(?P<yoy>.*?),\s*qoq=(?P<qoq>.*?)\]"
        )
        for metric in _METRICS
    }
    _FLAGS_RE = re.compile(r"\sflags=(?P<flags>.*)$")
    _HINT_RE = re.compile(r"symbol=(?P<symbol>\S+)\s+doc=(?P<doc>\S+)\s+hint=")

    def __init__(self, db_path: str = "data/equity_tracker.db", log_path: str = "logs/equity_tracker.log"):
        """Init.

        Args:
            db_path: SQLite DB path for symbol->company mapping.
            log_path: Log file path.
        """
        self.db_path = db_path
        self.log_path = Path(log_path)
        self._symbol_company_cache: Dict[str, str] = {}

    def generate_report_rows(
        self,
        limit: Optional[int] = 200,
        since: Optional[datetime] = None,
        latest_per_company: bool = True,
    ) -> List[Dict[str, str]]:
        """Generate report rows.

        Args:
            limit: Max rows in final report.
            since: Optional lower timestamp bound.
            latest_per_company: Keep only latest event per company.

        Returns:
            List of rows with Company | Output | Score | Notes.
        """
        events = self._read_events(since=since)
        if not events:
            return []

        for ev in events:
            self._attach_company_name(ev)
            score, output, notes = self._score_event(ev)
            ev.score = score
            ev.output = output
            ev.notes = notes

        # Show most recent first.
        events.sort(key=lambda e: e.timestamp, reverse=True)
        if latest_per_company:
            dedup: Dict[str, ParserEvent] = {}
            for ev in events:
                company_key = (ev.company_name or ev.symbol or "Unknown").upper()
                if company_key not in dedup:
                    dedup[company_key] = ev
            events = list(dedup.values())

        if limit is not None and limit > 0:
            events = events[:limit]

        rows: List[Dict[str, str]] = []
        for ev in events:
            company = ev.company_name or ev.symbol or "Unknown"
            if ev.symbol and ev.company_name and ev.symbol.upper() not in ev.company_name.upper():
                company = f"{ev.company_name} ({ev.symbol})"
            elif ev.symbol and not ev.company_name:
                company = ev.symbol
            rows.append(
                {
                    "Company": company,
                    "Output": ev.output,
                    "Score": str(ev.score),
                    "Notes": ev.notes,
                }
            )
        return rows

    @classmethod
    def rows_to_markdown(cls, rows: List[Dict[str, str]]) -> str:
        """Render rows as markdown table."""
        if not rows:
            return "| Company | Output | Score | Notes |\n|---|---|---:|---|\n| No data | NA | 0 | No parser entries found in log. |"

        lines = [
            "| Company | Output | Score | Notes |",
            "|---|---|---:|---|",
        ]
        for row in rows:
            company = cls._escape_md(row.get("Company", ""))
            output = cls._escape_md(row.get("Output", ""))
            score = cls._escape_md(row.get("Score", ""))
            notes = cls._escape_md(row.get("Notes", ""))
            lines.append(f"| {company} | {output} | {score} | {notes} |")
        return "\n".join(lines)

    def write_markdown_report(self, rows: List[Dict[str, str]], out_path: str) -> Path:
        """Write markdown report to file path."""
        target = Path(out_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.rows_to_markdown(rows), encoding="utf-8")
        return target

    def _read_events(self, since: Optional[datetime] = None) -> List[ParserEvent]:
        """Read parser and hint events from log, then correlate symbol/doc."""
        if not self.log_path.exists():
            self._logger.warning("Parser verification skipped: log file not found at %s", self.log_path)
            return []

        parser_events: List[ParserEvent] = []
        pending_idx: List[int] = []

        with self.log_path.open("r", encoding="utf-8", errors="replace") as f:
            for raw_line in f:
                parsed = self._parse_log_line(raw_line.rstrip("\n"))
                if not parsed:
                    continue
                ts = parsed["timestamp"]
                if since and ts < since:
                    continue
                msg = parsed["message"]
                logger_name = parsed["logger"]
                if logger_name.strip() == "services.financial_result_parser" and self._PARSER_PREFIX in msg:
                    event = self._parse_parser_message(ts, msg)
                    if event:
                        parser_events.append(event)
                        pending_idx.append(len(parser_events) - 1)
                elif logger_name.strip() == "services.ai_summary_service" and self._HINT_PREFIX in msg:
                    hint = self._parse_hint_message(msg)
                    if hint:
                        idx = self._find_latest_pending_event(parser_events, pending_idx, ts)
                        if idx is not None:
                            parser_events[idx].symbol = hint["symbol"]
                            parser_events[idx].doc_ref = hint["doc"]
                            pending_idx = [p for p in pending_idx if p != idx]

        return parser_events

    @classmethod
    def _parse_log_line(cls, line: str) -> Optional[Dict[str, object]]:
        """Parse standard app log line."""
        m = cls._MESSAGE_SPLIT_RE.match(line)
        if not m:
            return None
        try:
            ts = datetime.strptime(m.group("ts"), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
        return {
            "timestamp": ts,
            "logger": m.group("logger").strip(),
            "message": m.group("msg").strip(),
        }

    @classmethod
    def _parse_parser_message(cls, ts: datetime, message: str) -> Optional[ParserEvent]:
        """Parse one parser output log message."""
        m_head = cls._PARSER_HEADER_RE.search(message)
        if not m_head:
            return None
        source = (m_head.group("source") or "").strip()
        table_score = int(m_head.group("table_score"))
        quarter = (m_head.group("quarter") or "").strip()
        metrics: Dict[str, Dict[str, str]] = {}
        for metric in cls._METRICS:
            mm = cls._METRIC_RE[metric].search(message)
            metrics[metric] = {
                "val": (mm.group("val").strip() if mm else "NA"),
                "norm": (mm.group("norm").strip() if mm else "NA"),
                "yoy": (mm.group("yoy").strip() if mm else "NA"),
                "qoq": (mm.group("qoq").strip() if mm else "NA"),
            }
        fm = cls._FLAGS_RE.search(message)
        flags = (fm.group("flags").strip() if fm else "None")
        return ParserEvent(
            timestamp=ts,
            source=source,
            table_score=table_score,
            quarter=quarter,
            metrics=metrics,
            flags=flags,
        )

    @classmethod
    def _parse_hint_message(cls, message: str) -> Optional[Dict[str, str]]:
        """Parse symbol/doc from AI summary hint message."""
        m = cls._HINT_RE.search(message)
        if not m:
            return None
        return {
            "symbol": (m.group("symbol") or "").strip(),
            "doc": (m.group("doc") or "").strip(),
        }

    @staticmethod
    def _find_latest_pending_event(events: List[ParserEvent], pending_idx: List[int], hint_ts: datetime) -> Optional[int]:
        """Find nearest previous parser event for a hint line."""
        for idx in reversed(pending_idx):
            ev = events[idx]
            # Parser output and hint are emitted in the same immediate flow.
            if (hint_ts - ev.timestamp).total_seconds() <= 120:
                return idx
        return None

    def _attach_company_name(self, event: ParserEvent) -> None:
        """Attach company name using symbol and local DB mapping."""
        symbol = (event.symbol or "").strip().upper()
        if not symbol:
            event.company_name = ""
            return

        if symbol in self._symbol_company_cache:
            event.company_name = self._symbol_company_cache[symbol]
            return

        # Normalize Yahoo-style ticker for lookup in symbol_master.
        candidates = [symbol]
        if "." in symbol:
            candidates.append(symbol.split(".", 1)[0])

        company = ""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            for candidate in candidates:
                cur.execute(
                    """
                    SELECT company_name
                    FROM symbol_master
                    WHERE UPPER(symbol) = UPPER(?)
                       OR UPPER(nse_code) = UPPER(?)
                       OR UPPER(quote_symbol_yahoo) = UPPER(?)
                    LIMIT 1
                    """,
                    (candidate, candidate, candidate),
                )
                row = cur.fetchone()
                if row:
                    company = (row["company_name"] or "").strip()
                    break
            conn.close()
        except Exception:
            company = ""

        self._symbol_company_cache[symbol] = company
        event.company_name = company

    def _score_event(self, event: ParserEvent) -> tuple[int, str, str]:
        """Score parser quality and return output class + review notes."""
        score = 100
        notes: List[str] = []

        if not event.quarter or event.quarter.upper() in self._MISSING:
            score -= 8
            notes.append("Quarter not detected")

        if event.source in {"pdf_text", "table_text"}:
            score -= 8
            notes.append(f"Weaker source used ({event.source})")
        elif event.source == "structured_text":
            score -= 2

        if event.table_score < 0:
            score -= 4
        elif event.table_score >= 2:
            score += 2

        for metric in self._METRICS:
            data = event.metrics.get(metric, {})
            val = (data.get("val") or "").strip()
            norm = (data.get("norm") or "").strip()
            yoy = (data.get("yoy") or "").strip()
            qoq = (data.get("qoq") or "").strip()

            if self._is_missing(val):
                score -= 16
                notes.append(f"{metric} value missing")
            elif self._looks_malformed(val):
                score -= 6
                notes.append(f"{metric} value malformed ({val})")

            if metric != "EPS" and self._is_missing(norm):
                score -= 5
                notes.append(f"{metric} normalized value missing")

            if self._is_missing(yoy) and self._is_missing(qoq):
                score -= 3
                notes.append(f"{metric} YoY/QoQ not reviewed")

        flags = (event.flags or "").strip()
        if flags and flags.lower() != "none":
            score -= 6
            notes.append(f"Validation flag: {flags[:90]}")

        score = max(0, min(100, score))
        if score >= 80:
            output = "Good"
        elif score >= 55:
            output = "Needs Review"
        else:
            output = "Poor"

        # Keep notes compact and unique for manual review.
        deduped_notes: List[str] = []
        seen = set()
        for note in notes:
            key = note.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped_notes.append(note)
        if event.doc_ref:
            deduped_notes.append(f"Doc: {event.doc_ref}")

        return score, output, "; ".join(deduped_notes[:8]) or "No issues detected"

    @classmethod
    def _is_missing(cls, value: str) -> bool:
        """Check if value is effectively missing."""
        v = (value or "").strip()
        return v in cls._MISSING

    @staticmethod
    def _looks_malformed(value: str) -> bool:
        """Heuristic malformed numeric detector for parser outputs."""
        v = (value or "").strip()
        if not v:
            return False
        if v.count("(") != v.count(")"):
            return True
        # Cases like "(5" or "2025," are suspicious.
        if re.match(r"^\(?\d{4},?$", v):
            return True
        if re.search(r"[A-Za-z]", v) and not re.search(r"crore|cr|inr|rs", v.lower()):
            return True
        return False

    @staticmethod
    def _escape_md(text: str) -> str:
        """Escape markdown table-sensitive tokens."""
        return (text or "").replace("|", "\\|").replace("\n", " ").strip()

