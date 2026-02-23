"""
Financial Result Parser
Extracts key quarterly metrics from result-document text.
"""

from __future__ import annotations

import re
from io import BytesIO
from datetime import date
from typing import Dict, List, Optional, Tuple
from utils.logger import get_logger

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

try:
    import pdfplumber
except ImportError:
    pdfplumber = None


class FinancialResultParser:
    """Parse Revenue/EBITDA/PAT/EPS + YoY/QoQ hints from filing text."""
    _logger = get_logger(__name__)

    METRIC_PATTERNS = {
        "Revenue": [
            r"revenue from operations",
            r"total income",
            r"revenue",
            r"net sales",
        ],
        "EBITDA": [
            r"ebitda",
            r"operating profit",
        ],
        "PAT": [
            r"profit after tax",
            r"\bpat\b",
            r"net profit",
            r"profit for the period",
        ],
        "EPS": [
            r"earnings per share",
            r"\beps\b",
            r"eps\s*\(basic\)",
            r"basic\s+eps",
            r"earning\s+per\s+equity\s+share",
        ],
    }

    SPECIAL_ITEM_PATTERNS = [
        r"exceptional item[s]?",
        r"one[\s-]*off",
        r"extraordinary item[s]?",
        r"impairment",
        r"write[\s-]*off",
        r"tax credit",
        r"deferred tax",
    ]

    AMOUNT_PATTERN = (
        r"(?:rs\.?|inr|₹)?\s*"
        r"\(?\s*[-+]?\d[\d,]*(?:\.\d+)?\s*\)?\s*"
        r"(?:crore[s]?|cr|million|mn|billion|bn|lakh[s]?|lakhs|%)?"
    )
    YOY_PATTERN = r"[-+]?\d+(?:\.\d+)?\s*%\s*(?:yoy|y\/y|year[\s-]*over[\s-]*year)"
    QOQ_PATTERN = r"[-+]?\d+(?:\.\d+)?\s*%\s*(?:qoq|q\/q|quarter[\s-]*over[\s-]*quarter)"
    _QUARTER_RE = re.compile(r"\bq([1-4])\s*fy\s*([0-9]{2,4})\b", flags=re.IGNORECASE)
    _DATE_NUMERIC_RE = re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})\b")
    _DATE_TEXT_RE = re.compile(
        r"\b(\d{1,2})\s*[- ]?\s*"
        r"(jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|sept|september|oct|october|nov|november|dec|december)"
        r"\s*[-, ]\s*(\d{2,4})\b",
        flags=re.IGNORECASE
    )
    _MONTH_MAP = {
        "jan": 1, "january": 1,
        "feb": 2, "february": 2,
        "mar": 3, "march": 3,
        "apr": 4, "april": 4,
        "may": 5,
        "jun": 6, "june": 6,
        "jul": 7, "july": 7,
        "aug": 8, "august": 8,
        "sep": 9, "sept": 9, "september": 9,
        "oct": 10, "october": 10,
        "nov": 11, "november": 11,
        "dec": 12, "december": 12,
    }

    @staticmethod
    def _normalize_text(text: str) -> str:
        """Normalize whitespace and punctuation spacing for regex extraction."""
        t = (text or "").replace("\xa0", " ")
        t = re.sub(r"[ \t]+", " ", t)
        t = re.sub(r"\s*\n\s*", "\n", t)
        return t.strip()

    @classmethod
    def _detect_reporting_unit(cls, text: str) -> str:
        """Detect default reporting unit from filing text."""
        lowered = (text or "").lower()
        if "in lakhs" in lowered or "in lacs" in lowered or "in lakh" in lowered:
            return "lakh"
        if "in million" in lowered or "in mn" in lowered:
            return "million"
        if "in billion" in lowered or "in bn" in lowered:
            return "billion"
        return "crore"

    @classmethod
    def _normalize_fy(cls, fy_token: str) -> int:
        """Normalize FY token to 4-digit year end."""
        fy = int(fy_token)
        if fy < 100:
            fy += 2000
        return fy

    @classmethod
    def _is_reasonable_fy_end(cls, fy_end: int) -> bool:
        """Validate FY-end year inferred from noisy OCR text."""
        current = date.today().year
        return (current - 5) <= fy_end <= (current + 2)

    @classmethod
    def _extract_quarter_tuple(cls, header_text: str) -> Optional[Tuple[int, int]]:
        """Extract (fy_end_year, quarter) from header text."""
        if not header_text:
            return None
        text = str(header_text).strip()
        m = cls._QUARTER_RE.search(text)
        if not m:
            # Try date-driven quarter mapping (e.g., "31.12.2025" => Q3 FY26).
            d = cls._DATE_NUMERIC_RE.search(text)
            if d:
                month = int(d.group(2))
                year = cls._normalize_fy(d.group(3))
                return cls._quarter_for_month_year(month, year)
            d2 = cls._DATE_TEXT_RE.search(text)
            if d2:
                month = cls._MONTH_MAP.get(d2.group(2).lower(), 0)
                year = cls._normalize_fy(d2.group(3))
                if month:
                    return cls._quarter_for_month_year(month, year)
            return None
        q = int(m.group(1))
        fy = cls._normalize_fy(m.group(2))
        if not cls._is_reasonable_fy_end(fy):
            return None
        return fy, q

    @classmethod
    def _quarter_for_month_year(cls, month: int, year: int) -> Optional[Tuple[int, int]]:
        """Map calendar month/year to Indian FY quarter tuple (fy_end, quarter)."""
        if month < 1 or month > 12:
            return None
        fy_end = year + 1 if month >= 4 else year
        if not cls._is_reasonable_fy_end(fy_end):
            return None
        if 4 <= month <= 6:
            return fy_end, 1
        if 7 <= month <= 9:
            return fy_end, 2
        if 10 <= month <= 12:
            return fy_end, 3
        return fy_end, 4

    @classmethod
    def _is_quarterly_period_header(cls, header_text: str) -> bool:
        """Return True if header likely represents quarterly (not 9M/YTD/full-year) data."""
        h = (header_text or "").lower()
        blockers = [
            "nine month", "9 month", "9m", "year to date", "ytd",
            "year ended", "twelve month", "12 month", "annual",
        ]
        return not any(b in h for b in blockers)

    @classmethod
    def _select_quarter_columns(cls, headers: List[str]) -> Dict[str, Optional[int]]:
        """Select current/preceding/yoy column indexes from table headers."""
        quarter_cols_all = []
        for idx, h in enumerate(headers):
            qt = cls._extract_quarter_tuple(h or "")
            if qt:
                quarter_cols_all.append((idx, qt[0], qt[1], str(h or "")))
        if not quarter_cols_all:
            return {"current": None, "preceding": None, "yoy": None, "quarter_label": None}

        quarter_cols = [c for c in quarter_cols_all if cls._is_quarterly_period_header(c[3])]
        if not quarter_cols:
            quarter_cols = quarter_cols_all

        quarter_cols.sort(key=lambda x: (x[1], x[2]), reverse=True)
        cur_idx, cur_fy, cur_q, _ = quarter_cols[0]
        preceding = None
        yoy = None
        for idx, fy, q, _ in quarter_cols[1:]:
            if preceding is None and (fy < cur_fy or (fy == cur_fy and q < cur_q)):
                preceding = idx
            if yoy is None and fy == (cur_fy - 1) and q == cur_q:
                yoy = idx
            if preceding is not None and yoy is not None:
                break

        quarter_label = f"Q{cur_q} FY{str(cur_fy)[-2:]}"
        return {"current": cur_idx, "preceding": preceding, "yoy": yoy, "quarter_label": quarter_label}

    @classmethod
    def _build_combined_headers(cls, table_rows: List[List[str]], max_header_rows: int = 4) -> Tuple[List[str], int]:
        """Combine first 1..N rows into headers to handle nested multi-row table headings."""
        if not table_rows:
            return [], 0
        width = max(len(r or []) for r in table_rows[:max_header_rows]) if table_rows else 0
        best_headers: List[str] = []
        best_end = 1
        best_score = -1
        for n in range(1, min(max_header_rows, len(table_rows)) + 1):
            headers = []
            for col in range(width):
                parts = []
                for r in range(n):
                    row = table_rows[r] or []
                    cell = str(row[col]).strip() if col < len(row) and row[col] is not None else ""
                    if cell:
                        parts.append(cell)
                headers.append(" ".join(parts).strip())
            col_map = cls._select_quarter_columns(headers)
            score = 0
            if col_map.get("current") is not None:
                score += 2
            if col_map.get("preceding") is not None:
                score += 1
            if col_map.get("yoy") is not None:
                score += 1
            if score > best_score:
                best_score = score
                best_headers = headers
                best_end = n
        return best_headers, best_end

    @classmethod
    def _parse_amount_token(
        cls,
        token: str,
        default_unit: str = "crore",
        allow_percent: bool = False
    ) -> Tuple[Optional[float], str]:
        """Parse numeric token; supports bracket-negatives and unit conversion to crore."""
        t = (token or "").strip()
        if not t:
            return None, "crore"
        lowered = t.lower()
        compact = re.sub(r"\s+", "", lowered)

        # Reject expressions like "(5-6)" and explicit formula-like cells.
        if re.search(r"^\(?\s*\d+(?:\.\d+)?\s*[-+/*]\s*\d+(?:\.\d+)?\s*\)?$", lowered):
            return None, default_unit
        if "formula" in lowered:
            return None, default_unit
        if "%" in lowered and not allow_percent:
            return None, default_unit

        # Detect explicit unit in token or fallback to filing-level default.
        unit = default_unit
        if "crore" in lowered or re.search(r"\bcr\b", lowered):
            unit = "crore"
        elif "lakh" in lowered or "lac" in lowered:
            unit = "lakh"
        elif "million" in lowered or re.search(r"\bmn\b", lowered):
            unit = "million"
        elif "billion" in lowered or re.search(r"\bbn\b", lowered):
            unit = "billion"

        negative = "(" in t and ")" in t
        number_match = re.search(r"[-+]?\d[\d,]*(?:\.\d+)?", t)
        if not number_match:
            return None, unit
        # Avoid cells that contain many unrelated numbers unless they clearly specify a unit.
        many_numbers = len(re.findall(r"\d[\d,]*(?:\.\d+)?", compact)) > 2
        has_unit = any(k in lowered for k in ["crore", "cr", "lakh", "lac", "million", "mn", "billion", "bn"])
        if many_numbers and not has_unit:
            return None, unit
        num = number_match.group(0).replace(",", "")
        try:
            value = float(num)
        except Exception:
            return None, unit
        if negative and value > 0:
            value = -value

        # Normalize to crore.
        if unit == "lakh":
            value = value / 100.0
        elif unit == "million":
            value = value / 10.0
        elif unit == "billion":
            value = value * 100.0
        return value, unit

    @classmethod
    def _clean_table_cell(cls, cell: str) -> str:
        """Normalize table cell text for numeric extraction."""
        text = str(cell or "").replace("\n", " ").strip()
        text = re.sub(r"\s+", " ", text)
        return text

    @classmethod
    def _parse_metric_cell(
        cls,
        metric_name: str,
        cell: str,
        default_unit: str
    ) -> Tuple[str, str, Optional[float]]:
        """Parse a metric-specific table cell into raw value + normalized value + numeric base."""
        raw = cls._clean_table_cell(cell)
        if not raw:
            return "NA", "NA", None

        # For EPS keep per-share scale; never convert to crore.
        if metric_name == "EPS":
            val, _ = cls._parse_amount_token(raw, default_unit=default_unit, allow_percent=False)
            return raw, "NA", val

        # EBITDA row can contain margin%; avoid converting percentage to amount.
        if metric_name == "EBITDA" and "%" in raw and not re.search(r"(₹|rs\.?|inr|cr|crore|lakh|million|billion)", raw, flags=re.IGNORECASE):
            return raw, "NA", None

        val, _ = cls._parse_amount_token(raw, default_unit=default_unit, allow_percent=False)
        return raw, cls._format_crore(val), val

    @classmethod
    def _format_crore(cls, value: Optional[float]) -> str:
        """Format normalized crore value."""
        if value is None:
            return "NA"
        return f"{value:.2f} Cr"

    @classmethod
    def extract_text_from_pdf_bytes(cls, pdf_bytes: bytes, max_chars: int = 50000) -> str:
        """Extract plain text from PDF bytes in memory."""
        if not pdf_bytes:
            return ""
        # Prefer pdfplumber text extraction first; it is often better for table-heavy Indian filings.
        if pdfplumber is not None:
            try:
                parts: List[str] = []
                with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
                    for page in pdf.pages[:20]:
                        ptext = (page.extract_text() or "").strip()
                        if ptext:
                            parts.append(ptext)
                        if sum(len(p) for p in parts) >= max_chars:
                            break
                text = cls._normalize_text("\n".join(parts))
                if text:
                    return text[:max_chars]
            except Exception:
                pass
        if PdfReader is None:
            return ""
        return cls._extract_text_pypdf(pdf_bytes, max_chars=max_chars)

    @classmethod
    def _extract_text_pypdf(cls, pdf_bytes: bytes, max_chars: int = 50000) -> str:
        """Extract text with pypdf only (used for targeted fallback heuristics)."""
        if PdfReader is None or not pdf_bytes:
            return ""
        try:
            reader = PdfReader(BytesIO(pdf_bytes))
        except Exception:
            return ""

        parts: List[str] = []
        for page in reader.pages[:20]:
            try:
                ptext = (page.extract_text() or "").strip()
            except Exception:
                ptext = ""
            if ptext:
                parts.append(ptext)
            if sum(len(p) for p in parts) >= max_chars:
                break
        return cls._normalize_text("\n".join(parts))[:max_chars]

    @classmethod
    def _extract_metric_line(cls, text: str, metric_name: str, default_unit: str = "crore") -> Dict[str, str]:
        """Extract one metric line with value + YoY/QoQ hints."""
        patterns = cls.METRIC_PATTERNS.get(metric_name, [])
        lines = [ln.strip() for ln in (text or "").splitlines() if ln and ln.strip()]
        best_line = ""
        best_line_score = -1
        for idx, line in enumerate(lines):
            low = line.lower()
            if not any(re.search(rf"\b{pat}\b", low, flags=re.IGNORECASE) for pat in patterns):
                continue
            # Score line by "likely row with values": many numeric tokens, metric presence.
            numeric_tokens = cls._extract_numeric_tokens(line)
            score = len(numeric_tokens) * 3 + 2
            # Pull one or two next lines if they carry numeric table continuation.
            merged = line
            for j in range(idx + 1, min(idx + 3, len(lines))):
                follow = lines[j]
                if len(cls._extract_numeric_tokens(follow)) >= 3 and len(follow) < 200:
                    merged = f"{merged} {follow}"
                    score += 1
                else:
                    break
            if score > best_line_score:
                best_line = merged
                best_line_score = score

        if not best_line:
            return {"value": "NA", "yoy": "NA", "qoq": "NA", "evidence": ""}

        clean_line = re.sub(r"\(\s*\d+(?:\.\d+)?\s*[-+/*]\s*\d+(?:\.\d+)?\s*\)", " ", best_line)
        clean_line = re.sub(r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b", " ", clean_line)
        clean_line = re.sub(r"^\s*\d{1,2}\s+(?=[A-Za-z])", " ", clean_line)  # strip row-index prefix
        tokens = cls._extract_numeric_tokens(clean_line)
        non_pct_tokens = [t for t in tokens if "%" not in t]
        # Drop leading table row index if it still leaks (e.g., "7 Profit after tax ...").
        if non_pct_tokens:
            first_num = non_pct_tokens[0].replace(",", "").strip()
            if re.fullmatch(r"\d{1,2}", first_num):
                non_pct_tokens = non_pct_tokens[1:]

        value = non_pct_tokens[0] if non_pct_tokens else "NA"
        prev_q_value = non_pct_tokens[1] if len(non_pct_tokens) >= 2 else "NA"
        prev_y_value = non_pct_tokens[2] if len(non_pct_tokens) >= 3 else "NA"
        # Apply metric-aware numeric parsing for text fallback mode.
        unit_for_metric = default_unit
        # Common BSE KPI-summary block pattern: "EBITDA <num> <num> <x>% ... PBT ... Adjusted PAT ..."
        # These rows are often in Rs million even when statement tables are in lakhs.
        if metric_name == "EBITDA":
            evidence_low = clean_line.lower()
            if "%" in clean_line and "pbt" in evidence_low and "adjusted pat" in evidence_low:
                unit_for_metric = "million"

        raw_value, normalized, cur_num = cls._parse_metric_cell(metric_name, value, unit_for_metric)

        # Derive QoQ/YoY hints from row-style token sequence if available.
        qoq_hint = "NA"
        yoy_hint = "NA"
        has_percent = "%" in clean_line
        if len(non_pct_tokens) >= 2:
            _, _, prev_num = cls._parse_metric_cell(metric_name, non_pct_tokens[1], unit_for_metric)
            qoq_hint = cls._compute_pct_change(cur_num, prev_num, "QoQ")
        # If line contains KPI-style `%` with 9M aggregates, third numeric token is usually not prior-year quarter.
        allow_prev_y = len(non_pct_tokens) >= 3 and not (has_percent and len(non_pct_tokens) >= 4)
        if allow_prev_y:
            _, _, yoy_num = cls._parse_metric_cell(metric_name, non_pct_tokens[2], unit_for_metric)
            yoy_hint = cls._compute_pct_change(cur_num, yoy_num, "YoY")
        # If explicit percentage hints exist in line, prefer those.
        yoy_explicit = re.search(cls.YOY_PATTERN, clean_line, flags=re.IGNORECASE)
        qoq_explicit = re.search(cls.QOQ_PATTERN, clean_line, flags=re.IGNORECASE)
        if yoy_explicit:
            yoy_hint = yoy_explicit.group(0).strip()
        if qoq_explicit:
            qoq_hint = qoq_explicit.group(0).strip()

        quarter_label = cls._quarter_label_from_text(clean_line)
        prev_y_value = prev_y_value if allow_prev_y else "NA"
        return {
            "value": raw_value or "NA",
            "value_crore": normalized,
            "value_prev_quarter": prev_q_value,
            "value_prev_year_same_quarter": prev_y_value,
            "yoy": yoy_hint,
            "qoq": qoq_hint,
            "evidence": clean_line,
            "quarter_label": quarter_label or "NA",
        }

    @classmethod
    def _extract_numeric_tokens(cls, text: str) -> List[str]:
        """Extract likely numeric tokens from a table-like text row."""
        out: List[str] = []
        for m in re.finditer(
            r"(?:₹|rs\.?|inr)?\s*\(?\s*[-+]?\d[\d,]*(?:\.\d+)?\s*\)?\s*(?:%|crore[s]?|cr|million|mn|billion|bn|lakh[s]?|lakhs)?",
            text or "",
            flags=re.IGNORECASE,
        ):
            token = re.sub(r"\s+", " ", (m.group(0) or "").strip())
            if not token:
                continue
            # Skip likely years and day values.
            if re.fullmatch(r"\d{4}", token):
                continue
            if token in {"1", "2", "3", "4"}:
                continue
            out.append(token)
        return out

    @classmethod
    def _quarter_label_from_text(cls, text: str) -> Optional[str]:
        """Infer quarter label from date(s) embedded in row/header text."""
        if not text:
            return None
        m = cls._DATE_NUMERIC_RE.search(text)
        if m:
            month = int(m.group(2))
            year = cls._normalize_fy(m.group(3))
            q = cls._quarter_for_month_year(month, year)
            if q:
                return f"Q{q[1]} FY{str(q[0])[-2:]}"
        m2 = cls._DATE_TEXT_RE.search(text)
        if m2:
            month = cls._MONTH_MAP.get(m2.group(2).lower(), 0)
            year = cls._normalize_fy(m2.group(3))
            if month:
                q = cls._quarter_for_month_year(month, year)
                if q:
                    return f"Q{q[1]} FY{str(q[0])[-2:]}"
        return None

    @classmethod
    def _compute_pct_change(cls, current: Optional[float], base: Optional[float], label: str) -> str:
        """Compute percentage change safely."""
        if current is None or base is None or base == 0:
            return "NA"
        pct = ((current - base) / abs(base)) * 100.0
        sign = "+" if pct >= 0 else ""
        return f"{sign}{pct:.1f}% {label} (calc)"

    @classmethod
    def _extract_special_items(cls, text: str) -> str:
        """Extract concise special-items hint."""
        for pat in cls.SPECIAL_ITEM_PATTERNS:
            m = re.search(rf"([^\n.]{{0,80}}\b{pat}\b[^\n.]{{0,140}})", text, flags=re.IGNORECASE)
            if m:
                return m.group(1).strip()
        return "None highlighted"

    @classmethod
    def _metric_row_match(cls, label: str, metric_name: str) -> bool:
        """Check whether table row label maps to metric."""
        lbl = (label or "").lower()
        if not lbl:
            return False
        for pat in cls.METRIC_PATTERNS.get(metric_name, []):
            if re.search(rf"\b{pat}\b", lbl, flags=re.IGNORECASE):
                return True
        return False

    @classmethod
    def _parse_from_table_rows(cls, table_rows: List[List[str]]) -> Optional[Dict[str, Dict[str, str]]]:
        """Parse metrics from table rows with quarter-aware column selection."""
        if not table_rows or len(table_rows) < 2:
            return None
        headers, header_rows_used = cls._build_combined_headers(table_rows)
        col_map = cls._select_quarter_columns(headers)
        if col_map.get("current") is None:
            return None

        text_blob = cls._normalize_text("\n".join(" | ".join([str(c or "") for c in row]) for row in table_rows))
        default_unit = cls._detect_reporting_unit(text_blob)
        data_rows = table_rows[header_rows_used:]

        # Identify best label column (not always first column in merged tables).
        max_width = max(len(r or []) for r in data_rows) if data_rows else 0
        metric_names = ("Revenue", "EBITDA", "PAT", "EPS")
        best_label_col = 0
        best_label_score = -1
        for col_idx in range(max_width):
            score = 0
            for row in data_rows[:40]:
                cell = str(row[col_idx]).strip() if col_idx < len(row) and row[col_idx] is not None else ""
                if not cell:
                    continue
                if any(cls._metric_row_match(cell, m) for m in metric_names):
                    score += 1
                if "particular" in cell.lower():
                    score += 1
            if score > best_label_score:
                best_label_score = score
                best_label_col = col_idx

        def _row_for_metric(metric: str) -> Optional[List[str]]:
            for row in data_rows:
                row_label = str((row[best_label_col] if best_label_col < len(row) and row else "") or "").strip()
                if cls._metric_row_match(row_label, metric):
                    return row
            return None

        parsed: Dict[str, Dict[str, str]] = {}
        for metric in metric_names:
            row = _row_for_metric(metric)
            if not row:
                parsed[metric] = {"value": "NA", "value_crore": "NA", "yoy": "NA", "qoq": "NA", "evidence": ""}
                continue

            cur_cell = cls._clean_table_cell(row[col_map["current"]] if col_map["current"] < len(row) else "")
            prev_cell = (
                cls._clean_table_cell(row[col_map["preceding"]] if col_map["preceding"] is not None and col_map["preceding"] < len(row) else "")
            )
            yoy_cell = cls._clean_table_cell(row[col_map["yoy"]] if col_map["yoy"] is not None and col_map["yoy"] < len(row) else "")

            raw_value, normalized, cur_val = cls._parse_metric_cell(metric, cur_cell, default_unit)
            _, _, prev_val = cls._parse_metric_cell(metric, prev_cell, default_unit)
            _, _, yoy_val = cls._parse_metric_cell(metric, yoy_cell, default_unit)

            parsed[metric] = {
                "value": raw_value or "NA",
                "value_crore": normalized,
                "value_prev_quarter": prev_cell or "NA",
                "value_prev_year_same_quarter": yoy_cell or "NA",
                "yoy": cls._compute_pct_change(cur_val, yoy_val, "YoY"),
                "qoq": cls._compute_pct_change(cur_val, prev_val, "QoQ"),
                "evidence": " | ".join([x for x in [cur_cell, prev_cell, yoy_cell] if x]),
            }

        special_row = None
        for row in data_rows:
            row_label = str((row[best_label_col] if best_label_col < len(row) and row else "") or "").strip()
            if re.search(r"exceptional item|one[\s-]*off|extraordinary", row_label, flags=re.IGNORECASE):
                special_row = row
                break
        special = "None highlighted"
        if special_row:
            special = " | ".join([str(c or "").strip() for c in special_row if str(c or "").strip()]) or "None highlighted"

        out = {
            "Revenue": parsed["Revenue"],
            "EBITDA": parsed["EBITDA"],
            "PAT": parsed["PAT"],
            "EPS": parsed["EPS"],
            "Special Items": special,
            "Validation Flags": [],
            "Quarter Label": col_map.get("quarter_label"),
        }
        cls._append_validation_flags(out)
        return out

    @classmethod
    def parse_from_text(cls, text: str) -> Dict[str, Dict[str, str]]:
        """Parse key result metrics from normalized text."""
        normalized = cls._normalize_text(text)
        default_unit = cls._detect_reporting_unit(normalized)
        if not normalized:
            return {
                "Revenue": {"value": "NA", "value_crore": "NA", "yoy": "NA", "qoq": "NA", "evidence": ""},
                "EBITDA": {"value": "NA", "value_crore": "NA", "yoy": "NA", "qoq": "NA", "evidence": ""},
                "PAT": {"value": "NA", "value_crore": "NA", "yoy": "NA", "qoq": "NA", "evidence": ""},
                "EPS": {"value": "NA", "value_crore": "NA", "yoy": "NA", "qoq": "NA", "evidence": ""},
                "Special Items": "None highlighted",
                "Validation Flags": [],
            }

        parsed = {
            "Revenue": cls._extract_metric_line(normalized, "Revenue", default_unit=default_unit),
            "EBITDA": cls._extract_metric_line(normalized, "EBITDA", default_unit=default_unit),
            "PAT": cls._extract_metric_line(normalized, "PAT", default_unit=default_unit),
            "EPS": cls._extract_metric_line(normalized, "EPS", default_unit=default_unit),
            "Special Items": cls._extract_special_items(normalized),
            "Validation Flags": [],
        }
        row_quarters = [
            (parsed.get(m) or {}).get("quarter_label")
            for m in ("Revenue", "EBITDA", "PAT", "EPS")
            if (parsed.get(m) or {}).get("quarter_label") not in {None, "", "NA"}
        ]
        if row_quarters:
            parsed["Quarter Label"] = row_quarters[0]
        parsed = cls._apply_sanity_guardrails(parsed)
        return parsed

    @classmethod
    def _append_validation_flags(cls, parsed: Dict[str, Dict[str, str]]) -> None:
        """Add production-safety validation flags for ambiguous result interpretation."""
        flags: List[str] = parsed.get("Validation Flags", [])
        special = (parsed.get("Special Items") or "").lower()
        pat_crore_text = ((parsed.get("PAT") or {}).get("value_crore") or "NA").split(" ")[0]
        special_val, _ = cls._parse_amount_token(parsed.get("Special Items") or "")
        try:
            pat_val = float(pat_crore_text) if pat_crore_text != "NA" else None
        except Exception:
            pat_val = None
        if "exceptional" in special or "one-off" in special or special_val is not None:
            flags.append("Exceptional item present; verify PAT quality before comparing growth.")
        if pat_val is not None and special_val is not None and abs(pat_val) > 0:
            if abs(special_val) >= 0.5 * abs(pat_val):
                flags.append("PAT likely materially impacted by exceptional items.")
        # Preserve order while removing duplicates.
        parsed["Validation Flags"] = list(dict.fromkeys(flags))

    @classmethod
    def _sanitize_metric_row(cls, metric_name: str, row: Dict[str, str]) -> Dict[str, str]:
        """Apply sanity checks to one metric row and suppress implausible outliers."""
        if not row:
            return row

        value = str(row.get("value", "NA") or "NA").strip()
        prev_q = str(row.get("value_prev_quarter", "NA") or "NA").strip()
        prev_y = str(row.get("value_prev_year_same_quarter", "NA") or "NA").strip()
        normalized = str(row.get("value_crore", "NA") or "NA").strip()

        # Helper parse without unit conversion surprises for EPS.
        def _num(token: str, metric: str) -> Optional[float]:
            if token in {"", "NA", "None"}:
                return None
            if metric == "EPS":
                m = re.search(r"[-+]?\d[\d,]*(?:\.\d+)?", token)
                if not m:
                    return None
                try:
                    return float(m.group(0).replace(",", ""))
                except Exception:
                    return None
            n, _ = cls._parse_amount_token(token, default_unit="crore")
            return n

        cur_n = _num(value, metric_name)
        q_n = _num(prev_q, metric_name)
        y_n = _num(prev_y, metric_name)

        # Basic token hygiene.
        if metric_name == "EPS" and value not in {"NA", ""} and not re.search(r"\d", value):
            row["value"] = "NA"
        if metric_name in {"Revenue", "EBITDA", "PAT"}:
            if normalized not in {"NA", ""}:
                try:
                    norm_num = float(normalized.split(" ")[0])
                    # Suppress absurd OCR explosions.
                    if abs(norm_num) > 100000:
                        row["value"] = "NA"
                        row["value_crore"] = "NA"
                        row["yoy"] = "NA"
                        row["qoq"] = "NA"
                except Exception:
                    pass

        # Growth sanity.
        for gkey in ("yoy", "qoq"):
            gval = str(row.get(gkey, "NA") or "NA")
            m = re.search(r"([-+]?\d+(?:\.\d+)?)\s*%", gval)
            if m:
                try:
                    pct = abs(float(m.group(1)))
                    if pct > 500:
                        row[gkey] = "NA"
                except Exception:
                    row[gkey] = "NA"

        # Relative-ratio sanity between adjacent quarters for same metric.
        if cur_n is not None and q_n not in (None, 0):
            ratio = abs(cur_n / q_n)
            if ratio > 20 or ratio < 0.05:
                row["qoq"] = "NA"
        if cur_n is not None and y_n not in (None, 0):
            ratio = abs(cur_n / y_n)
            if ratio > 20 or ratio < 0.05:
                row["yoy"] = "NA"

        return row

    @classmethod
    def _apply_sanity_guardrails(cls, parsed: Dict[str, Dict[str, str]]) -> Dict[str, Dict[str, str]]:
        """Apply quality guardrails across parsed result output."""
        if not parsed:
            return parsed
        for metric in ("Revenue", "EBITDA", "PAT", "EPS"):
            if metric in parsed:
                parsed[metric] = cls._sanitize_metric_row(metric, parsed.get(metric) or {})
        # Cross-metric sanity: EBITDA should generally not be far below PAT.
        try:
            ebitda_norm = str((parsed.get("EBITDA") or {}).get("value_crore") or "NA").split(" ")[0]
            pat_norm = str((parsed.get("PAT") or {}).get("value_crore") or "NA").split(" ")[0]
            ebitda_n = float(ebitda_norm) if ebitda_norm not in {"NA", ""} else None
            pat_n = float(pat_norm) if pat_norm not in {"NA", ""} else None
            if ebitda_n is not None and pat_n is not None and abs(ebitda_n) < (abs(pat_n) * 0.5):
                parsed["EBITDA"] = {
                    "value": "NA",
                    "value_crore": "NA",
                    "value_prev_quarter": "NA",
                    "value_prev_year_same_quarter": "NA",
                    "yoy": "NA",
                    "qoq": "NA",
                    "evidence": "",
                    "quarter_label": "NA",
                }
        except Exception:
            pass
        # Rebuild validation flags after sanitation.
        parsed["Validation Flags"] = []
        cls._append_validation_flags(parsed)
        return parsed

    @classmethod
    def _extract_statement_section_text(cls, text: str) -> str:
        """Extract statement block (prefer consolidated) from full PDF text."""
        t = cls._normalize_text(text or "")
        if not t:
            return ""
        lower = t.lower()
        start_markers = [
            "consolidated statement of financial results",
            "standalone statement of financial results",
        ]
        end_markers = [
            "notes:",
            "limited review report",
        ]
        start_idx = -1
        for marker in start_markers:
            idx = lower.find(marker)
            if idx != -1:
                start_idx = idx
                break
        if start_idx == -1:
            return t
        end_idx = len(t)
        lower_tail = lower[start_idx:]
        for marker in end_markers:
            idx = lower_tail.find(marker)
            if idx != -1:
                end_idx = min(end_idx, start_idx + idx)
        return t[start_idx:end_idx].strip()

    @classmethod
    def _extract_statement_quarter_label(cls, section_text: str) -> Optional[str]:
        """Infer quarter label from statement section header dates."""
        if not section_text:
            return None
        dates = re.findall(r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b", section_text[:1200])
        for d in dates:
            m = re.match(r"(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})", d)
            if not m:
                continue
            month = int(m.group(2))
            year = cls._normalize_fy(m.group(3))
            q = cls._quarter_for_month_year(month, year)
            if q:
                return f"Q{q[1]} FY{str(q[0])[-2:]}"
        return None

    @classmethod
    def _extract_row_values_from_line(cls, line: str) -> List[str]:
        """Extract ordered numeric values from a statement row.

        Handles OCR artifacts commonly seen in BSE PDFs:
        - row prefixes (e.g. "7 e 4368.11")
        - formula refs (e.g. "(1-2)")
        - split decimals (e.g. "2001 .30")
        - split integers (e.g. "41 18.99" -> "4118.99")
        """
        if not line:
            return []
        clean = str(line)
        clean = re.sub(r"^\s*\d{1,2}(?=\s+[A-Za-z\(\)])", "", clean)
        clean = re.sub(r"\(\s*\d+\s*[-+/*]\s*\d+\s*\)", " ", clean)
        clean = re.sub(r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b", " ", clean)
        clean = re.sub(r"(\d)\s+\.(\d)", r"\1.\2", clean)
        clean = re.sub(r"\s+", " ", clean).strip()
        clean = re.sub(r"[A-Za-z_]+", " ", clean)

        tokens = re.findall(r"-?\([\d,\.]*\d[\d,\.]*\)|-?\d[\d,]*(?:\.\d+)?", clean)
        values: List[str] = []
        for tok in tokens:
            token = tok.strip()
            if not token:
                continue
            if token.startswith("(") and token.endswith(")"):
                core = token[1:-1].replace(",", "")
                if re.fullmatch(r"\d+(?:\.\d+)?", core):
                    values.append(f"-{core}")
                continue
            values.append(token)

        # Merge OCR-split number pairs when row has too many numeric fragments.
        if len(values) > 6:
            merged: List[str] = []
            i = 0
            while i < len(values) and len(merged) < 6:
                cur = values[i]
                surplus = len(merged) + (len(values) - i) - 6
                if (
                    surplus > 0
                    and re.fullmatch(r"-?\d{1,3}", cur)
                    and i + 1 < len(values)
                    and re.fullmatch(r"\d{1,2}(?:\.\d+)?", values[i + 1])
                ):
                    merged.append(f"{cur}{values[i + 1]}")
                    i += 2
                    continue
                merged.append(cur)
                i += 1
            values = merged[:6]

        return values[:6]

    @classmethod
    def _find_statement_line(cls, lines: List[str], patterns: List[str]) -> str:
        """Find best line matching any pattern and include continuation if useful."""
        best_line = ""
        best_score = -1
        for i, line in enumerate(lines):
            low = line.lower()
            if not any(re.search(p, low, flags=re.IGNORECASE) for p in patterns):
                continue
            merged = line
            score = 0
            vals = cls._extract_row_values_from_line(line)
            score += len(vals) * 3
            for j in range(i + 1, min(i + 3, len(lines))):
                nxt = lines[j]
                nxt_vals = cls._extract_row_values_from_line(nxt)
                if len(nxt_vals) >= 3 and len(nxt) < 220:
                    merged = f"{merged} {nxt}"
                    score += len(nxt_vals)
                else:
                    break
            if score > best_score:
                best_score = score
                best_line = merged
        return best_line

    @classmethod
    def _is_suspicious_parsed_output(cls, parsed: Dict[str, Dict[str, str]]) -> bool:
        """Detect obviously bad parses and force fallback path."""
        if not parsed:
            return True

        def _metric_value(name: str) -> str:
            return str((parsed.get(name) or {}).get("value") or "NA").replace(" ", "")

        revenue = _metric_value("Revenue")
        eps = _metric_value("EPS")
        pat = _metric_value("PAT")
        core_present = sum(1 for v in (revenue, pat, eps) if v not in {"", "NA"})

        # If only one core metric was found, quality is too weak.
        if core_present < 2:
            return True

        # EPS should not mirror Revenue row values.
        if revenue not in {"", "NA"} and eps not in {"", "NA"} and revenue == eps:
            return True

        # EPS sanity range; values above 1000 are almost certainly OCR leakage.
        try:
            eps_num = float(eps.replace(",", ""))
            if abs(eps_num) > 1000:
                return True
        except Exception:
            pass

        return False

    @classmethod
    def _is_metric_missing(cls, parsed: Dict[str, Dict[str, str]], metric: str) -> bool:
        """Return True when a metric row has no usable current value."""
        row = parsed.get(metric) or {}
        value = str(row.get("value") or "NA").strip()
        return value in {"", "NA", "None"}

    @classmethod
    def _extract_eps_values_from_lines(cls, lines: List[str]) -> List[str]:
        """Extract EPS values from 'Earnings per share' section using Basic/Diluted rows."""
        if not lines:
            return []
        idx_candidates = [
            i for i, ln in enumerate(lines)
            if re.search(r"earnings\s*per\s*share|\beps\b", ln, flags=re.IGNORECASE)
        ]

        def _candidate_values(start_idx: int) -> List[str]:
            window = lines[start_idx:min(len(lines), start_idx + 8)]
            candidate_rows: List[List[str]] = []
            for ln in window:
                if re.search(r"\bbasic\b", ln, flags=re.IGNORECASE):
                    vals = cls._extract_row_values_from_line(ln)
                    if len(vals) >= 3:
                        candidate_rows.append(vals)
            for ln in window:
                if re.search(r"\bdiluted\b", ln, flags=re.IGNORECASE):
                    vals = cls._extract_row_values_from_line(ln)
                    if len(vals) >= 3:
                        candidate_rows.append(vals)
            if not candidate_rows:
                return []

            def _score(vals: List[str]) -> float:
                score = 0.0
                try:
                    a = float(vals[0].replace(",", ""))
                    b = float(vals[1].replace(",", ""))
                    c = float(vals[2].replace(",", ""))
                    if 0 < a < 100:
                        score += 2
                    if abs(a - b) <= 3:
                        score += 2
                    if abs(b - c) <= 3:
                        score += 2
                    if all("." in v for v in vals[:3]):
                        score += 1
                    if c > 25:  # often OCR bleed from other columns, de-prioritize
                        score -= 1
                except Exception:
                    score -= 2
                return score

            candidate_rows.sort(key=_score, reverse=True)
            return candidate_rows[0]

        best: List[str] = []
        for idx in idx_candidates:
            vals = _candidate_values(idx)
            if len(vals) >= 3:
                best = vals
                v0 = vals[0].replace(",", "")
                if re.fullmatch(r"\d+(?:\.\d{1,2})?", v0) and "." in vals[0]:
                    return vals

        # Fallback: scan all lines for Basic/Diluted rows even without EPS anchor.
        if not best:
            all_candidates: List[List[str]] = []
            for ln in lines:
                if re.search(r"\bbasic\b|\bdiluted\b", ln, flags=re.IGNORECASE):
                    vals = cls._extract_row_values_from_line(ln)
                    if len(vals) >= 3:
                        all_candidates.append(vals)
            if all_candidates:
                def _score(vals: List[str]) -> float:
                    try:
                        a = float(vals[0].replace(",", ""))
                        b = float(vals[1].replace(",", ""))
                        c = float(vals[2].replace(",", ""))
                        return (2 if 0 < a < 100 else -2) + (2 if abs(a - b) <= 3 else 0) + (2 if abs(b - c) <= 3 else 0) + (1 if all("." in v for v in vals[:3]) else 0)
                    except Exception:
                        return -2
                all_candidates.sort(key=_score, reverse=True)
                best = all_candidates[0]
        return best

    @classmethod
    def _extract_pat_values_from_lines(cls, lines: List[str]) -> List[str]:
        """Extract PAT values from explicit 'Net Profit/Loss for the period' style rows."""
        if not lines:
            return []
        strong_patterns = [
            r"profit\s*/?\s*\(?loss\)?\s*for\s*the\s*period",
            r"net\s*profit\s*/?\s*loss\s*for\s*the\s*period",
            r"net\s*profit\s*for\s*the\s*period",
        ]
        weak_patterns = [
            r"profit\s*after\s*tax",
            r"\bpat\b",
        ]
        blacklist = [
            r"total\s+net\s+profit\s+after\s+tax",
            r"total\s+comprehensive\s+income",
            r"investor\s+release",
            r"press\s+release",
            r"for\s+the\s+quarter\s+ended",
        ]
        candidates: List[Tuple[float, List[str]]] = []
        for ln in lines:
            low = ln.lower().strip()
            if len(low) > 260:
                continue
            if any(re.search(p, low, flags=re.IGNORECASE) for p in blacklist):
                continue
            strong = any(re.search(p, low, flags=re.IGNORECASE) for p in strong_patterns)
            weak = any(re.search(p, low, flags=re.IGNORECASE) for p in weak_patterns)
            if not strong and not weak:
                continue
            vals = cls._extract_row_values_from_line(ln)
            if len(vals) >= 3:
                score = 0.0
                score += 6.0 if strong else 1.0
                if re.search(r"profit\s*/?\s*\(?loss\)?\s*for\s*the\s*period", low, flags=re.IGNORECASE):
                    score += 2.0
                # Table-like rows are short and dense with numeric values.
                score += min(len(vals), 6) * 0.5
                candidates.append((score, vals[:3]))
        if not candidates:
            return []

        def _score(vals: List[str]) -> float:
            try:
                a, b, c = [float(v.replace(",", "")) for v in vals[:3]]
                score = 0.0
                if abs(a) >= 10:
                    score += 1
                if abs(a - b) <= max(5000.0, abs(a) * 0.6):
                    score += 2
                if abs(a - c) <= max(5000.0, abs(a) * 0.8):
                    score += 2
                return score
            except Exception:
                return -2.0

        candidates.sort(key=lambda x: (x[0] + _score(x[1])), reverse=True)
        return candidates[0][1]

    @classmethod
    def _extract_eps_values_from_raw_text(cls, raw_text: str) -> List[str]:
        """Extract EPS values from raw OCR-like text around Basic/Diluted anchors."""
        if not raw_text:
            return []

        def _score(vals: List[str]) -> float:
            try:
                a, b, c = [float(v.replace(",", "")) for v in vals[:3]]
                score = 0.0
                if 0 < a < 100:
                    score += 2
                if abs(a - b) <= 3:
                    score += 2
                if abs(b - c) <= 3:
                    score += 2
                if all("." in v for v in vals[:3]):
                    score += 1
                return score
            except Exception:
                return -2.0

        candidates: List[List[str]] = []
        for m in re.finditer(r"\bbasic\b|\bdiluted\b", raw_text, flags=re.IGNORECASE):
            win = raw_text[m.start():m.start() + 450]
            nums = re.findall(r"\b\d{1,2}\.\d{1,2}\b", win)
            if len(nums) >= 3:
                candidates.append(nums[:3])
        if not candidates:
            return []
        candidates.sort(key=_score, reverse=True)
        return candidates[0]

    @classmethod
    def _build_metric_from_values(
        cls,
        metric_name: str,
        values: List[str],
        default_unit: str,
        evidence: str,
    ) -> Dict[str, str]:
        """Build one metric dict from current/prevQ/prevY values."""
        cur = values[0] if len(values) >= 1 else "NA"
        prev_q = values[1] if len(values) >= 2 else "NA"
        prev_y = values[2] if len(values) >= 3 else "NA"
        raw, normalized, cur_num = cls._parse_metric_cell(metric_name, cur, default_unit)
        _, _, prev_q_num = cls._parse_metric_cell(metric_name, prev_q, default_unit)
        _, _, prev_y_num = cls._parse_metric_cell(metric_name, prev_y, default_unit)
        return {
            "value": raw or "NA",
            "value_crore": normalized,
            "value_prev_quarter": prev_q or "NA",
            "value_prev_year_same_quarter": prev_y or "NA",
            "yoy": cls._compute_pct_change(cur_num, prev_y_num, "YoY"),
            "qoq": cls._compute_pct_change(cur_num, prev_q_num, "QoQ"),
            "evidence": evidence[:600],
            "quarter_label": "NA",
        }

    @classmethod
    def _parse_statement_section_from_text(cls, full_text: str) -> Optional[Dict[str, Dict[str, str]]]:
        """Parse BSE statement-style text block with strict row mapping."""
        section = cls._extract_statement_section_text(full_text)
        if not section:
            return None
        lines = [ln.strip() for ln in section.splitlines() if ln and ln.strip()]
        if not lines:
            return None
        default_unit = cls._detect_reporting_unit(section)
        quarter_label = cls._extract_statement_quarter_label(section)

        revenue_line = cls._find_statement_line(
            lines,
            [r"sales\s*/?\s*income\s*from\s*op", r"revenue\s*from\s*operations", r"total income from operations", r"total income"],
        )
        pat_line = cls._find_statement_line(
            lines,
            [r"net\s*profit\s*/?\s*loss\s*for\s*the\s*period", r"profit\s*after\s*tax", r"\bpat\b"],
        )
        eps_line = cls._find_statement_line(
            lines,
            [r"\(\s*a\s*\)\s*basic", r"earnings\s*per\s*share", r"\beps\b"],
        )
        eps_vals = cls._extract_eps_values_from_lines(lines)
        finance_line = cls._find_statement_line(lines, [r"finance\s*cost"])
        dep_line = cls._find_statement_line(lines, [r"depreciation", r"amortisation"])
        pbt_line = cls._find_statement_line(lines, [r"profit\s*/?\s*\(?loss\)?\s*before\s*tax", r"profit\s*before\s*tax"])
        if not pbt_line:
            pbt_line = cls._find_statement_line(
                lines,
                [r"rofit\s*/?\s*\(?loss\)?\s*before\s*tax", r"rofit\s*before\s*tax"],
            )
        special_line = cls._find_statement_line(lines, [r"exceptional\s*item"])

        revenue_vals = cls._extract_row_values_from_line(revenue_line)
        pat_vals = cls._extract_pat_values_from_lines(lines)
        if len(pat_vals) < 3:
            pat_vals = cls._extract_row_values_from_line(pat_line)
        if not eps_vals:
            eps_vals = cls._extract_row_values_from_line(eps_line)
        pbt_vals = cls._extract_row_values_from_line(pbt_line)
        finance_vals = cls._extract_row_values_from_line(finance_line)
        dep_vals = cls._extract_row_values_from_line(dep_line)

        # EBITDA as PBT + Finance + Depreciation where available.
        ebitda_vals: List[str] = []
        for i in range(3):
            pbt = pbt_vals[i] if len(pbt_vals) > i else "NA"
            fin = finance_vals[i] if len(finance_vals) > i else "NA"
            dep = dep_vals[i] if len(dep_vals) > i else "NA"
            pbt_num, _ = cls._parse_amount_token(pbt, default_unit=default_unit)
            fin_num, _ = cls._parse_amount_token(fin, default_unit=default_unit)
            dep_num, _ = cls._parse_amount_token(dep, default_unit=default_unit)
            if pbt_num is None or fin_num is None or dep_num is None:
                ebitda_vals.append("NA")
            else:
                ebitda_vals.append(f"{(pbt_num + fin_num + dep_num):.2f}")

        out = {
            "Revenue": cls._build_metric_from_values("Revenue", revenue_vals, default_unit, revenue_line),
            "EBITDA": cls._build_metric_from_values("EBITDA", ebitda_vals, default_unit, f"{pbt_line} {finance_line} {dep_line}".strip()),
            "PAT": cls._build_metric_from_values("PAT", pat_vals, default_unit, pat_line),
            "EPS": cls._build_metric_from_values("EPS", eps_vals, default_unit, eps_line),
            "Special Items": special_line or "None highlighted",
            "Validation Flags": [],
            "Quarter Label": quarter_label,
        }
        cls._append_validation_flags(out)
        # Require at least two core metrics to accept this path.
        score = sum(
            1 for m in ("Revenue", "PAT", "EPS")
            if (out.get(m) or {}).get("value") not in {"", "NA", None}
        )
        return out if score >= 2 else None

    @classmethod
    def parse_from_pdf_bytes(cls, pdf_bytes: bytes) -> Dict[str, Dict[str, str]]:
        """Best-effort parse from table extraction first, then text fallback."""
        table_text_parts: List[str] = []
        best_table_parse: Optional[Dict[str, Dict[str, str]]] = None
        best_score = -1
        if pdfplumber is not None and pdf_bytes:
            try:
                with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
                    for page in pdf.pages[:20]:
                        tables = page.extract_tables() or []
                        if not tables:
                            tables = page.extract_tables(
                                table_settings={
                                    "vertical_strategy": "lines",
                                    "horizontal_strategy": "lines",
                                    "snap_tolerance": 3,
                                    "join_tolerance": 3,
                                    "edge_min_length": 3,
                                    "intersection_tolerance": 3,
                                }
                            ) or []
                        if not tables:
                            tables = page.extract_tables(
                                table_settings={
                                    "vertical_strategy": "text",
                                    "horizontal_strategy": "text",
                                    "snap_tolerance": 3,
                                    "join_tolerance": 3,
                                    "min_words_vertical": 1,
                                    "min_words_horizontal": 1,
                                }
                            ) or []
                        for table in tables:
                            if not table:
                                continue
                            parsed_table = cls._parse_from_table_rows(table)
                            if parsed_table:
                                score = sum(
                                    1 for m in ("Revenue", "EBITDA", "PAT", "EPS")
                                    if (parsed_table.get(m) or {}).get("value") not in {"", "NA"}
                                )
                                if score > best_score:
                                    best_score = score
                                    best_table_parse = parsed_table

                            row_texts = []
                            for row in table:
                                cells = [str(c).strip() for c in row if c is not None and str(c).strip()]
                                if cells:
                                    row_texts.append(" | ".join(cells))
                            if row_texts:
                                table_text_parts.append("\n".join(row_texts))
            except Exception:
                table_text_parts = []
                best_table_parse = None

        if best_table_parse is not None and best_score >= 1:
            best_table_parse = cls._apply_sanity_guardrails(best_table_parse)
            if not cls._is_suspicious_parsed_output(best_table_parse):
                cls._log_parsed_snapshot(
                    parsed=best_table_parse,
                    source="table",
                    table_score=best_score,
                )
                return best_table_parse
            cls._logger.info(
                "Table parse rejected by quality gate; falling back to statement/text parser (table_score=%s).",
                best_score,
            )

        # Structured statement-text parser (works for many BSE layouts where table extraction fails).
        full_text = cls.extract_text_from_pdf_bytes(pdf_bytes)
        structured = cls._parse_statement_section_from_text(full_text)
        if structured is not None:
            # Fallback EPS recovery from entire PDF text when section-specific EPS is weak.
            eps_value = (structured.get("EPS") or {}).get("value")
            eps_prev_y = (structured.get("EPS") or {}).get("value_prev_year_same_quarter")
            suspicious_eps = False
            try:
                if eps_value not in {"", "NA", None} and eps_prev_y not in {"", "NA", None}:
                    a = float(str(eps_value).replace(",", ""))
                    c = float(str(eps_prev_y).replace(",", ""))
                    suspicious_eps = c > (a * 2.0)
            except Exception:
                suspicious_eps = False
            if eps_value in {"", "NA", None} or suspicious_eps:
                all_lines = [ln.strip() for ln in (full_text or "").splitlines() if ln and ln.strip()]
                eps_vals = cls._extract_eps_values_from_lines(all_lines)
                if len(eps_vals) < 3:
                    raw_pypdf = cls._extract_text_pypdf(pdf_bytes)
                    eps_vals = cls._extract_eps_values_from_raw_text(raw_pypdf)
                if len(eps_vals) >= 3:
                    default_unit = cls._detect_reporting_unit(full_text)
                    structured["EPS"] = cls._build_metric_from_values(
                        "EPS", eps_vals, default_unit, "EPS row extracted from full text"
                    )
            pat_value = (structured.get("PAT") or {}).get("value")
            if pat_value in {"", "NA", None}:
                all_lines = [ln.strip() for ln in (full_text or "").splitlines() if ln and ln.strip()]
                pat_vals = cls._extract_pat_values_from_lines(all_lines)
                if len(pat_vals) < 3:
                    raw_pypdf = cls._extract_text_pypdf(pdf_bytes)
                    pat_vals = cls._extract_pat_values_from_lines([ln.strip() for ln in raw_pypdf.splitlines() if ln.strip()])
                if len(pat_vals) >= 3:
                    default_unit = cls._detect_reporting_unit(full_text)
                    structured["PAT"] = cls._build_metric_from_values(
                        "PAT", pat_vals, default_unit, "PAT row extracted from full text"
                    )
            # Recompute validation after late metric overrides.
            structured = cls._apply_sanity_guardrails(structured)
            # Supplement missing metrics using generic text parser (useful for EBITDA rows
            # present in commentary/summary sections but absent in strict statement blocks).
            supplement = cls.parse_from_text(full_text)
            for metric in ("Revenue", "EBITDA", "PAT", "EPS"):
                if cls._is_metric_missing(structured, metric) and not cls._is_metric_missing(supplement, metric):
                    structured[metric] = supplement.get(metric) or structured.get(metric)
            if not structured.get("Quarter Label") and supplement.get("Quarter Label"):
                structured["Quarter Label"] = supplement.get("Quarter Label")
            structured = cls._apply_sanity_guardrails(structured)
            if not cls._is_suspicious_parsed_output(structured):
                cls._log_parsed_snapshot(
                    parsed=structured,
                    source="structured_text",
                    table_score=best_score,
                )
                return structured
            cls._logger.info("Structured-text parse rejected by quality gate; trying generic text parse.")

        table_text = cls._normalize_text("\n".join(table_text_parts))
        if table_text:
            parsed = cls.parse_from_text(table_text)
            parsed = cls._apply_sanity_guardrails(parsed)
            cls._log_parsed_snapshot(
                parsed=parsed,
                source="table_text",
                table_score=best_score,
            )
            return parsed

        # Fallback to pypdf text extraction.
        parsed = cls.parse_from_text(full_text)
        parsed = cls._apply_sanity_guardrails(parsed)
        cls._log_parsed_snapshot(
            parsed=parsed,
            source="pdf_text",
            table_score=best_score,
        )
        return parsed

    @classmethod
    def to_prompt_hint(cls, parsed: Dict[str, Dict[str, str]]) -> str:
        """Convert parsed result into compact prompt-ready hint block."""
        if not parsed:
            return "No numeric hints detected."
        lines = []
        for metric in ("Revenue", "EBITDA", "PAT", "EPS"):
            row = parsed.get(metric) or {}
            current = row.get("value", "NA")
            prev_q = row.get("value_prev_quarter", "NA")
            prev_y = row.get("value_prev_year_same_quarter", "NA")
            lines.append(
                f"{metric}: Current={current} | PrevQ={prev_q} | PrevY={prev_y} | "
                f"Normalized={row.get('value_crore', 'NA')} | YoY hint: {row.get('yoy', 'NA')} | QoQ hint: {row.get('qoq', 'NA')}"
            )
        if parsed.get("Quarter Label"):
            lines.append(f"Detected Quarter: {parsed.get('Quarter Label')}")
        lines.append(f"Special hint: {parsed.get('Special Items', 'None highlighted')}")
        validation = parsed.get("Validation Flags") or []
        if validation:
            lines.append("Validation: " + " ; ".join(validation[:2]))
        return "\n".join(lines)

    @classmethod
    def _log_parsed_snapshot(cls, parsed: Dict[str, Dict[str, str]], source: str, table_score: int = -1) -> None:
        """Log compact parser output for quality auditing."""
        if not parsed:
            cls._logger.info("Result parser output source=%s table_score=%s parsed=empty", source, table_score)
            return

        def _metric_brief(metric_name: str) -> str:
            row = parsed.get(metric_name) or {}
            return (
                f"{metric_name}[val={row.get('value', 'NA')},"
                f" norm={row.get('value_crore', 'NA')},"
                f" yoy={row.get('yoy', 'NA')},"
                f" qoq={row.get('qoq', 'NA')}]"
            )

        metrics = " | ".join(
            [
                _metric_brief("Revenue"),
                _metric_brief("EBITDA"),
                _metric_brief("PAT"),
                _metric_brief("EPS"),
            ]
        )
        quarter = parsed.get("Quarter Label") or "NA"
        special = str(parsed.get("Special Items") or "None highlighted").replace("\n", " ")[:200]
        flags = "; ".join((parsed.get("Validation Flags") or [])[:2]) or "None"
        cls._logger.info(
            "Result parser output source=%s table_score=%s quarter=%s %s special=%s flags=%s",
            source,
            table_score,
            quarter,
            metrics,
            special,
            flags,
        )
