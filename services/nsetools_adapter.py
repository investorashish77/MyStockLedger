"""
NSETools Adapter
Fetches NSE symbol master data using nsetools.
"""

from typing import Dict, List


class NSEToolsAdapter:
    """Adapter for pulling NSE symbols via nsetools."""

    def fetch_symbol_rows(self) -> List[Dict]:
        """
        Fetch symbol master rows from NSE.
        Returns a list of dict rows compatible with SymbolMasterService.
        """
        try:
            from nsetools import Nse
        except ImportError as exc:
            raise RuntimeError("nsetools is not installed. Install it via requirements/setup.") from exc

        nse = Nse()
        codes = nse.get_stock_codes()

        rows = []
        # nsetools responses vary across versions/environments.
        # Handle common shapes: dict, list[dict], list[(symbol, name)].
        if isinstance(codes, dict):
            iterable = [(k, v) for k, v in codes.items()]
        elif isinstance(codes, list):
            iterable = []
            for item in codes:
                if isinstance(item, dict):
                    symbol = item.get("symbol") or item.get("SYMBOL") or item.get("nse_code")
                    company_name = item.get("company_name") or item.get("name") or item.get("NAME OF COMPANY")
                    iterable.append((symbol, company_name))
                elif isinstance(item, (list, tuple)) and len(item) >= 2:
                    iterable.append((item[0], item[1]))
        else:
            raise RuntimeError(f"Unsupported nsetools response type: {type(codes).__name__}")

        for symbol, company_name in iterable:
            if not symbol:
                continue
            symbol = str(symbol).strip().upper()
            if not symbol or symbol == "SYMBOL":
                continue
            name = str(company_name).strip() if company_name else symbol
            rows.append(
                {
                    "symbol": symbol,
                    "company_name": name,
                    "exchange": "NSE",
                    "nse_code": symbol,
                    "source": "NSETOOLS",
                }
            )
        return rows
