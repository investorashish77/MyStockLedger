"""
Financial Result Parser
Extracts key quarterly metrics from result-document text.
"""

from __future__ import annotations

import re
from io import BytesIO
from typing import Dict, List, Optional, Tuple

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

    METRIC_PATTERNS = {
        "Revenue": [
            r"revenue from operations",
            r"total income",
            r"revenue",
            r"net sales",
            r"sales",
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
    def _extract_quarter_tuple(cls, header_text: str) -> Optional[Tuple[int, int]]:
        """Extract (fy_end_year, quarter) from header text."""
        if not header_text:
            return None
        m = cls._QUARTER_RE.search(header_text)
        if not m:
            return None
        q = int(m.group(1))
        fy = cls._normalize_fy(m.group(2))
        return fy, q

    @classmethod
    def _select_quarter_columns(cls, headers: List[str]) -> Dict[str, Optional[int]]:
        """Select current/preceding/yoy column indexes from table headers."""
        quarter_cols = []
        for idx, h in enumerate(headers):
            qt = cls._extract_quarter_tuple(h or "")
            if qt:
                quarter_cols.append((idx, qt[0], qt[1]))
        if not quarter_cols:
            return {"current": None, "preceding": None, "yoy": None, "quarter_label": None}

        quarter_cols.sort(key=lambda x: (x[1], x[2]), reverse=True)
        cur_idx, cur_fy, cur_q = quarter_cols[0]
        preceding = None
        yoy = None
        for idx, fy, q in quarter_cols[1:]:
            if preceding is None and (fy < cur_fy or (fy == cur_fy and q < cur_q)):
                preceding = idx
            if yoy is None and fy == (cur_fy - 1) and q == cur_q:
                yoy = idx
            if preceding is not None and yoy is not None:
                break

        quarter_label = f"Q{cur_q} FY{str(cur_fy)[-2:]}"
        return {"current": cur_idx, "preceding": preceding, "yoy": yoy, "quarter_label": quarter_label}

    @classmethod
    def _parse_amount_token(cls, token: str, default_unit: str = "crore") -> Tuple[Optional[float], str]:
        """Parse numeric token; supports bracket-negatives and unit conversion to crore."""
        t = (token or "").strip()
        if not t:
            return None, "crore"
        lowered = t.lower()

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
    def _format_crore(cls, value: Optional[float]) -> str:
        """Format normalized crore value."""
        if value is None:
            return "NA"
        return f"{value:.2f} Cr"

    @classmethod
    def extract_text_from_pdf_bytes(cls, pdf_bytes: bytes, max_chars: int = 50000) -> str:
        """Extract plain text from PDF bytes in memory."""
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
        best_line = ""
        for pattern in patterns:
            regex = re.compile(rf"\b{pattern}\b", flags=re.IGNORECASE)
            match = regex.search(text)
            if match:
                # Capture wider local context. Do not split on '.' because decimals are common.
                start = max(0, match.start() - 40)
                end = min(len(text), match.end() + 220)
                best_line = text[start:end].strip()
                metric_match = match
                break

        if not best_line:
            return {"value": "NA", "yoy": "NA", "qoq": "NA", "evidence": ""}

        post_region = text[metric_match.end():min(len(text), metric_match.end() + 90)]
        amount = re.search(cls.AMOUNT_PATTERN, post_region, flags=re.IGNORECASE)
        if not amount:
            amount = re.search(cls.AMOUNT_PATTERN, best_line, flags=re.IGNORECASE)

        yoy = re.search(cls.YOY_PATTERN, post_region, flags=re.IGNORECASE)
        qoq = re.search(cls.QOQ_PATTERN, post_region, flags=re.IGNORECASE)

        value = (amount.group(0).strip() if amount else "NA")
        if value and value in {"-", "+", "%"}:
            value = "NA"
        value_crore, _ = cls._parse_amount_token(value, default_unit=default_unit)
        return {
            "value": value or "NA",
            "value_crore": cls._format_crore(value_crore),
            "yoy": (yoy.group(0).strip() if yoy else "NA"),
            "qoq": (qoq.group(0).strip() if qoq else "NA"),
            "evidence": best_line,
        }

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
        headers = [str(c or "").strip() for c in (table_rows[0] or [])]
        col_map = cls._select_quarter_columns(headers)
        if col_map.get("current") is None:
            return None

        text_blob = cls._normalize_text("\n".join(" | ".join([str(c or "") for c in row]) for row in table_rows))
        default_unit = cls._detect_reporting_unit(text_blob)

        def _row_for_metric(metric: str) -> Optional[List[str]]:
            for row in table_rows[1:]:
                row_label = str((row[0] if row else "") or "").strip()
                if cls._metric_row_match(row_label, metric):
                    return row
            return None

        parsed: Dict[str, Dict[str, str]] = {}
        for metric in ("Revenue", "EBITDA", "PAT", "EPS"):
            row = _row_for_metric(metric)
            if not row:
                parsed[metric] = {"value": "NA", "value_crore": "NA", "yoy": "NA", "qoq": "NA", "evidence": ""}
                continue

            cur_cell = str(row[col_map["current"]] if col_map["current"] < len(row) else "").strip()
            prev_cell = (
                str(row[col_map["preceding"]] if col_map["preceding"] is not None and col_map["preceding"] < len(row) else "").strip()
            )
            yoy_cell = str(row[col_map["yoy"]] if col_map["yoy"] is not None and col_map["yoy"] < len(row) else "").strip()

            cur_val, _ = cls._parse_amount_token(cur_cell, default_unit=default_unit)
            prev_val, _ = cls._parse_amount_token(prev_cell, default_unit=default_unit)
            yoy_val, _ = cls._parse_amount_token(yoy_cell, default_unit=default_unit)

            parsed[metric] = {
                "value": cur_cell or "NA",
                "value_crore": cls._format_crore(cur_val),
                "yoy": cls._compute_pct_change(cur_val, yoy_val, "YoY"),
                "qoq": cls._compute_pct_change(cur_val, prev_val, "QoQ"),
                "evidence": " | ".join([x for x in [cur_cell, prev_cell, yoy_cell] if x]),
            }

        special_row = None
        for row in table_rows[1:]:
            row_label = str((row[0] if row else "") or "").strip()
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
        cls._append_validation_flags(parsed)
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
        parsed["Validation Flags"] = flags

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

        if best_table_parse is not None and best_score >= 2:
            return best_table_parse

        table_text = cls._normalize_text("\n".join(table_text_parts))
        if table_text:
            return cls.parse_from_text(table_text)

        # Fallback to pypdf text extraction.
        fallback_text = cls.extract_text_from_pdf_bytes(pdf_bytes)
        return cls.parse_from_text(fallback_text)

    @classmethod
    def to_prompt_hint(cls, parsed: Dict[str, Dict[str, str]]) -> str:
        """Convert parsed result into compact prompt-ready hint block."""
        if not parsed:
            return "No numeric hints detected."
        lines = []
        for metric in ("Revenue", "EBITDA", "PAT", "EPS"):
            row = parsed.get(metric) or {}
            lines.append(
                f"{metric}: {row.get('value', 'NA')} (Normalized: {row.get('value_crore', 'NA')}) | "
                f"YoY hint: {row.get('yoy', 'NA')} | QoQ hint: {row.get('qoq', 'NA')}"
            )
        if parsed.get("Quarter Label"):
            lines.append(f"Detected Quarter: {parsed.get('Quarter Label')}")
        lines.append(f"Special hint: {parsed.get('Special Items', 'None highlighted')}")
        validation = parsed.get("Validation Flags") or []
        if validation:
            lines.append("Validation: " + " ; ".join(validation[:2]))
        return "\n".join(lines)
