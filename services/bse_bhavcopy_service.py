"""
BSE Bhavcopy Service
Fetches daily BSE bhavcopy data and persists OHLCV rows.
"""

import csv
import io
import os
import zipfile
from pathlib import Path
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

import requests

from database.db_manager import DatabaseManager
from utils.logger import get_logger


class BSEBhavcopyService:
    """Ingest BSE daily bhavcopy OHLCV data."""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.logger = get_logger(__name__)
        cache_dir = os.getenv("BSE_BHAVCOPY_CACHE_DIR", "BhavCopy").strip() or "BhavCopy"
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def ingest_rows(self, rows: List[Dict], source: str = "BSE_BHAVCOPY") -> int:
        """Ingest normalized bhavcopy rows."""
        written = 0
        for row in rows:
            bse_code = str(
                row.get("bse_code")
                or row.get("FinInstrmId")
                or row.get("SC_CODE")
                or row.get("SCRIP_CD")
                or row.get("scripCode")
                or ""
            ).strip()
            trade_date = str(
                row.get("trade_date") or row.get("TradDt") or row.get("DATE1") or row.get("TRADE_DATE") or ""
            ).strip()
            close_price = row.get("close_price") or row.get("ClsPric") or row.get("CLOSE") or row.get("close")
            if not bse_code or not trade_date or close_price in (None, ""):
                continue

            self.db.upsert_bse_daily_price(
                bse_code=bse_code,
                trade_date=trade_date,
                open_price=self._to_float(
                    row.get("open_price") or row.get("OpnPric") or row.get("OPEN") or row.get("open")
                ),
                high_price=self._to_float(
                    row.get("high_price") or row.get("HghPric") or row.get("HIGH") or row.get("high")
                ),
                low_price=self._to_float(
                    row.get("low_price") or row.get("LwPric") or row.get("LOW") or row.get("low")
                ),
                close_price=self._to_float(close_price),
                total_shares_traded=self._to_float(
                    row.get("total_shares_traded")
                    or row.get("TtlTradgVol")
                    or row.get("NO_OF_SHRS")
                    or row.get("totalSharesTraded")
                ),
                total_trades=self._to_float(
                    row.get("total_trades") or row.get("TtlNbTrad") or row.get("NO_TRADES") or row.get("totalTrades")
                ),
                turnover=self._to_float(
                    row.get("turnover") or row.get("TtlTrfVal") or row.get("NET_TURNOV") or row.get("netTurnover")
                ),
                source=source,
            )
            written += 1
        return written

    def fetch_and_ingest_date(self, trade_date: date) -> int:
        """Fetch one bhavcopy date directly from BSE download URL and ingest."""
        rows = self._fetch_bhavcopy_rows_for_date(trade_date)
        if not rows:
            self.logger.info("No bhavcopy rows found for %s", trade_date.isoformat())
            return 0
        written = self.ingest_rows(rows=rows, source="BSE_BHAVCOPY_HTTP")
        self.logger.info(
            "Bhavcopy synced for %s. Rows upserted: %s",
            trade_date.isoformat(),
            written,
        )
        return written

    def fetch_and_ingest_range(self, from_date: date, to_date: date, skip_weekends: bool = True, fail_fast: bool = False) -> int:
        total = 0
        failures = 0
        current = from_date
        while current <= to_date:
            if skip_weekends and current.weekday() >= 5:
                current += timedelta(days=1)
                continue
            try:
                total += self.fetch_and_ingest_date(current)
            except Exception as exc:
                failures += 1
                self.logger.error("Bhavcopy fetch failed for %s: %s", current.isoformat(), exc)
                if fail_fast:
                    raise
            current += timedelta(days=1)
        if total == 0 and failures > 0:
            raise RuntimeError(
                f"No bhavcopy rows ingested. Failed days: {failures}. "
                "Run with a narrower date window or check BSE/network availability."
            )
        return total

    @staticmethod
    def _normalize_raw_rows(raw, trade_date: date) -> List[Dict]:
        if raw is None:
            return []
        if hasattr(raw, "to_dict"):
            # pandas DataFrame
            raw = raw.to_dict(orient="records")
        if not isinstance(raw, list):
            return []

        out = []
        date_str = trade_date.strftime("%Y-%m-%d")
        for row in raw:
            if not isinstance(row, dict):
                continue
            norm = dict(row)
            norm.setdefault("trade_date", BSEBhavcopyService._normalize_date_string(row.get("DATE1")) or date_str)
            out.append(norm)
        return out

    def _fetch_bhavcopy_rows_for_date(self, trade_date: date) -> List[Dict]:
        payload = self._load_or_download_bhavcopy_payload(trade_date)
        if payload is None:
            return []
        csv_bytes = self._extract_csv_bytes(payload)
        rows = self._parse_csv_rows(csv_bytes)
        return self._normalize_raw_rows(rows, trade_date)

    def _load_or_download_bhavcopy_payload(self, trade_date: date) -> Optional[bytes]:
        cache_file = self._cache_file_path(trade_date)
        if cache_file.exists() and cache_file.stat().st_size > 0:
            self.logger.info("Using cached bhavcopy for %s from %s", trade_date.isoformat(), cache_file)
            return cache_file.read_bytes()
        return self._download_and_cache_bhavcopy_payload(trade_date, cache_file)

    def _download_and_cache_bhavcopy_payload(self, trade_date: date, cache_file: Path) -> Optional[bytes]:
        target_url = self._build_bhavcopy_url(trade_date)
        self.logger.info("Downloading bhavcopy for %s from %s", trade_date.isoformat(), target_url)
        response = requests.get(
            target_url,
            timeout=30,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                ),
                "Referer": "https://www.bseindia.com/markets/MarketInfo/BhavCopy.aspx",
            },
        )
        if response.status_code == 404:
            self.logger.warning("Bhavcopy not available for %s (404)", trade_date.isoformat())
            return None
        response.raise_for_status()

        payload = response.content or b""
        if not payload:
            self.logger.warning("Received empty bhavcopy payload for %s", trade_date.isoformat())
            return None

        tmp_file = cache_file.with_suffix(cache_file.suffix + ".tmp")
        tmp_file.write_bytes(payload)
        tmp_file.replace(cache_file)
        self.logger.info("Saved bhavcopy for %s to %s", trade_date.isoformat(), cache_file)
        return payload

    def _cache_file_path(self, trade_date: date) -> Path:
        filename = f"BhavCopy_BSE_CM_0_0_0_{trade_date.strftime('%Y%m%d')}_F_0000.csv"
        return self.cache_dir / filename

    @staticmethod
    def _extract_csv_bytes(content: bytes) -> bytes:
        if content.startswith(b"PK"):
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                members = [m for m in zf.namelist() if m.lower().endswith(".csv")]
                if not members:
                    return b""
                return zf.read(members[0])
        return content

    @staticmethod
    def _parse_csv_rows(csv_bytes: bytes) -> List[Dict]:
        if not csv_bytes:
            return []
        text = ""
        for encoding in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                text = csv_bytes.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        if not text.strip():
            return []
        reader = csv.DictReader(io.StringIO(text))
        return [dict(r) for r in reader if isinstance(r, dict)]

    @staticmethod
    def _build_bhavcopy_url(trade_date: date) -> str:
        date_token = trade_date.strftime("%Y%m%d")
        url_template = os.getenv(
            "BSE_BHAVCOPY_URL_TEMPLATE",
            "https://www.bseindia.com/download/BhavCopy/Equity/BhavCopy_BSE_CM_0_0_0_{date}_F_0000.csv",
        )
        return url_template.format(date=date_token)

    @staticmethod
    def _normalize_date_string(value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        text = str(value).strip()
        # Common bhavcopy format: 13-Feb-2026
        for fmt in ("%d-%b-%Y", "%Y-%m-%d", "%d/%m/%Y", "%d %b %Y"):
            try:
                return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
            except Exception:
                continue
        if len(text) == 8 and text.isdigit():
            try:
                return datetime.strptime(text, "%Y%m%d").strftime("%Y-%m-%d")
            except Exception:
                return text
        return text

    @staticmethod
    def _to_float(value):
        if value in (None, ""):
            return None
        try:
            return float(str(value).replace(",", ""))
        except Exception:
            return None
