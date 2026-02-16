"""
Symbol Master Service
Loads and manages master symbol/company list used by add-stock workflows.
"""

import csv
from io import StringIO
from typing import Dict, List

import requests

from database.db_manager import DatabaseManager
from services.nsetools_adapter import NSEToolsAdapter


class SymbolMasterService:
    """Service for symbol master ingestion and lookup."""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def populate_symbols_from_rows(self, rows: List[Dict], source: str = "MANUAL") -> int:
        """Upsert symbols from a list of row dicts; returns count written."""
        written = 0
        for row in rows:
            symbol = self._normalize_symbol(row.get("symbol"))
            company_name = (row.get("company_name") or "").strip()
            if not symbol or not company_name:
                continue

            exchange = (row.get("exchange") or "NSE").strip().upper()
            quote_symbol_yahoo = (row.get("quote_symbol_yahoo") or "").strip().upper() or self._derive_yahoo_symbol(symbol, exchange)

            self.db.upsert_symbol_master(
                symbol=symbol,
                company_name=company_name,
                exchange=exchange,
                bse_code=(row.get("bse_code") or None),
                nse_code=(row.get("nse_code") or None),
                sector=(row.get("sector") or None),
                source=source,
                quote_symbol_yahoo=quote_symbol_yahoo
            )
            written += 1
        return written

    def populate_symbols_from_csv_text(self, csv_text: str, source: str = "CSV") -> int:
        """Upsert symbols from CSV content."""
        reader = csv.DictReader(StringIO(csv_text))
        rows = [
            {
                "symbol": (
                    row.get("symbol")
                    or row.get("SYMBOL")
                    or row.get("Security Id")
                    or row.get("Security ID")
                ),
                "company_name": (
                    row.get("company_name")
                    or row.get("NAME OF COMPANY")
                    or row.get("company")
                    or row.get("Issuer Name")
                    or row.get("Security Name")
                ),
                "exchange": (
                    row.get("exchange")
                    or row.get("EXCHANGE")
                    or ("BSE" if (row.get("Security Code") or row.get("BSE CODE")) else "NSE")
                ),
                "bse_code": row.get("bse_code") or row.get("BSE CODE") or row.get("Security Code"),
                "nse_code": row.get("nse_code") or row.get("NSE CODE") or row.get("Security Id"),
                "sector": row.get("sector") or row.get("INDUSTRY")
            }
            for row in reader
        ]
        return self.populate_symbols_from_rows(rows, source=source)

    def populate_symbols_from_url(self, csv_url: str, source: str = "URL_CSV", timeout: int = 30) -> int:
        """Fetch CSV from URL and upsert symbols."""
        response = requests.get(csv_url, timeout=timeout)
        response.raise_for_status()
        return self.populate_symbols_from_csv_text(response.text, source=source)

    def populate_symbols_from_nsetools(self, source: str = "NSETOOLS", adapter: NSEToolsAdapter = None) -> int:
        """Fetch and upsert NSE symbols using nsetools adapter."""
        adapter = adapter or NSEToolsAdapter()
        rows = adapter.fetch_symbol_rows()
        return self.populate_symbols_from_rows(rows=rows, source=source)

    def search(self, query: str, limit: int = 20) -> List[Dict]:
        """Search symbols from local DB."""
        return self.db.search_symbol_master(query=query, limit=limit)

    def resolve_yahoo_symbol(self, symbol: str, exchange: str = "NSE") -> str:
        """Resolve Yahoo quote symbol using symbol master mapping, then exchange rules."""
        symbol = (symbol or "").strip().upper()
        if not symbol:
            return symbol

        row = self.db.get_symbol_by_symbol(symbol)
        if row and row.get("quote_symbol_yahoo"):
            return row["quote_symbol_yahoo"].strip().upper()
        return self._derive_yahoo_symbol(symbol, exchange)

    @staticmethod
    def _normalize_symbol(symbol_value: str) -> str:
        """Normalize symbols to the DB key style used across services."""
        symbol = (symbol_value or "").strip().upper()
        if symbol.endswith(".NS") or symbol.endswith(".BO"):
            symbol = symbol.rsplit(".", 1)[0]
        return symbol

    @staticmethod
    def _derive_yahoo_symbol(symbol: str, exchange: str) -> str:
        symbol = (symbol or "").strip().upper()
        exchange = (exchange or "").strip().upper()
        if not symbol:
            return symbol
        if "." in symbol:
            return symbol
        if exchange == "NSE":
            return f"{symbol}.NS"
        if exchange == "BSE":
            return f"{symbol}.BO"
        return symbol
