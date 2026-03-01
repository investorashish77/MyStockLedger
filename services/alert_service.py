"""
Alert Service
Manages price alerts and corporate announcements
"""

import json
import re
from typing import List, Dict
from database.db_manager import DatabaseManager
from services.stock_service import StockService
from services.bse_feed_service import BSEFeedService
from utils.config import config

class AlertService:
    """Handles stock alerts and notifications"""

    MATERIAL_KEYWORDS = [
        "result", "results", "financial result", "quarter", "q1", "q2", "q3", "q4",
        "dividend", "board meeting", "fund raise", "rights issue", "bonus", "split",
        "merger", "acquisition", "buyback", "credit rating", "default", "pledge",
        "material", "outcome"
    ]
    CATEGORY_KEYWORDS = {
        "Results": ["result", "results", "q1", "q2", "q3", "q4", "financial result", "quarterly"],
        "Earnings Call": ["earnings call", "conference call", "investor call", "audio recording", "transcript", "call recording"],
        "Order Wins": ["order", "contract", "work order", "award"],
        "Fund Raising": ["fund raise", "qip", "preferential", "rights issue", "debenture", "ncd", "fpo"],
        "Capacity Expansion": ["capacity", "expansion", "plant", "new facility", "commissioned"],
        "Bonus Issue": ["bonus issue", "bonus shares", "stock split", "split"],
        "Acquisitions": ["acquisition", "merger", "amalgamation", "takeover"],
        "Open Offer": ["open offer", "delisting", "buyback", "tender offer"],
    }
    
    def __init__(self, db_manager: DatabaseManager):
        """Init.

        Args:
            db_manager: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        self.db = db_manager
        self.stock_service = StockService()
        self.bse_feed_service = BSEFeedService(db_manager)
    
    def check_price_targets(self, user_id: int, use_live_quotes: bool = True) -> List[Dict]:
        """
        Check if any stocks have reached their target prices
        Returns list of triggered alerts
        """
        triggered_alerts = []
        
        # Get user's portfolio
        portfolio = self.db.get_portfolio_summary(user_id)
        
        for stock in portfolio:
            stock_id = stock['stock_id']
            symbol = stock['symbol']
            exchange = stock.get('exchange')
            
            # Get transactions for this stock to check target prices
            transactions = self.db.get_stock_transactions(stock_id)
            
            # Get current price (live or latest persisted DB quote).
            if use_live_quotes:
                quote_symbol = self.stock_service.to_quote_symbol(symbol, exchange=exchange)
                current_price = self.stock_service.get_current_price(quote_symbol)
                if current_price is not None:
                    self.db.save_price(stock_id, float(current_price))
                else:
                    current_price = self.db.get_latest_price(stock_id)
            else:
                current_price = self.db.get_latest_price(stock_id)
            
            if not current_price:
                continue
            
            # Check each transaction's target price
            for trans in transactions:
                if trans['target_price'] and current_price >= trans['target_price']:
                    alert_message = f"{symbol} has reached target price ₹{trans['target_price']:.2f} (Current: ₹{current_price:.2f})"
                    
                    # Add alert to database
                    alert_id = self.db.add_alert(
                        stock_id=stock_id,
                        alert_type='PRICE_TARGET',
                        alert_message=alert_message
                    )
                    
                    triggered_alerts.append({
                        'alert_id': alert_id,
                        'stock_id': stock_id,
                        'symbol': symbol,
                        'message': alert_message
                    })
        
        return triggered_alerts
    
    def create_manual_alert(self, stock_id: int, alert_type: str, 
                           message: str, details: str = None, url: str = None) -> int:
        """Create a manual alert (for announcements, news, etc.)"""
        return self.db.add_alert(
            stock_id=stock_id,
            alert_type=alert_type,
            alert_message=message,
            announcement_details=details,
            announcement_url=url
        )
    
    def get_user_alerts(self, user_id: int, unread_only: bool = False) -> List[Dict]:
        """Get all alerts for a user"""
        return self.db.get_user_alerts(user_id, unread_only)
    
    def mark_as_read(self, alert_id: int):
        """Mark an alert as read"""
        self.db.mark_alert_as_read(alert_id)
    
    # Placeholder for future implementation
    def fetch_corporate_announcements(self, symbol: str) -> List[Dict]:
        """
        Fetch corporate announcements from NSE/BSE
        This is a placeholder - actual implementation would scrape NSE/BSE websites
        """
        # TODO: Implement web scraping for NSE/BSE announcements
        # For now, return empty list
        return []
    
    def create_sample_alert(self, user_id: int, stock_symbol: str) -> int:
        """Create a sample announcement alert for testing"""
        # Get stock_id
        stocks = self.db.get_user_stocks(user_id)
        stock = next((s for s in stocks if s['symbol'] == stock_symbol), None)
        
        if not stock:
            return None
        
        sample_announcement = """
Company announces Q3 FY25 results:
- Revenue: ₹25,000 Cr (↑12% YoY)
- Net Profit: ₹3,500 Cr (↑18% YoY)
- EBITDA Margin: 22.5% (↑150 bps)
- EPS: ₹45.2 (↑17% YoY)

Management Commentary:
- Strong performance across all business segments
- Digital transformation initiatives showing results
- Raised FY25 guidance by 5%

Board approved interim dividend of ₹10 per share.
        """
        
        return self.create_manual_alert(
            stock_id=stock['stock_id'],
            alert_type='ANNOUNCEMENT',
            message=f"{stock_symbol} Q3 Results Announced - Revenue up 12% YoY",
            details=sample_announcement,
            url="https://www.nseindia.com"
        )

    def sync_bse_feed_for_portfolio(
        self,
        user_id: int,
        start_date_yyyymmdd: str,
        end_date_yyyymmdd: str,
        max_pages_per_symbol: int = 30
    ) -> int:
        """
        Pull BSE announcements targeted to portfolio BSE scrip codes.
        Returns number of announcement rows ingested.
        """
        stocks = self.db.get_user_stocks_with_symbol_master(user_id)
        bse_codes = sorted({
            str(stock.get("bse_code")).strip()
            for stock in stocks
            if stock.get("bse_code")
        })
        if not bse_codes:
            return 0

        total = 0
        failures = []
        for code in bse_codes:
            try:
                total += self.bse_feed_service.ingest_api_range(
                    api_url=config.BSE_API_ENDPOINT,
                    start_date_yyyymmdd=start_date_yyyymmdd,
                    end_date_yyyymmdd=end_date_yyyymmdd,
                    max_pages=max_pages_per_symbol,
                    scrip_code=code,
                )
            except Exception as exc:
                failures.append((code, str(exc)))
                continue

        if failures and len(failures) == len(bse_codes) and total == 0:
            sample_code, sample_error = failures[0]
            raise RuntimeError(
                f"BSE API fetch failed for all portfolio BSE codes; sample {sample_code}: {sample_error}"
            )
        return total

    def sync_portfolio_announcements(self, user_id: int, limit: int = 1000, per_stock_limit: int = 4) -> int:
        """
        Pull and persist latest portfolio-related material announcements as alerts.
        Returns number of new alerts created.
        """
        # Optional feed ingestion from configured RSS URLs.
        for rss_url in config.BSE_RSS_URLS:
            try:
                self.bse_feed_service.ingest_rss_feed(rss_url)
            except Exception:
                # Keep UI responsive even when feed endpoints are unavailable.
                continue

        stocks = self.db.get_user_stocks(user_id)
        if not stocks:
            return 0

        symbol_to_stock = {s['symbol']: s for s in stocks}
        symbol_id_to_stock = {}
        symbol_meta = {}
        for symbol, stock in symbol_to_stock.items():
            sm = self.db.get_symbol_by_symbol(symbol)
            if sm:
                symbol_id_to_stock[sm['symbol_id']] = stock
                symbol_meta[symbol] = sm

        announcements = self.db.get_recent_bse_announcements(limit=limit)
        existing_alerts = self.db.get_user_alerts(user_id)
        existing_urls = {a['announcement_url'] for a in existing_alerts if a.get('announcement_url')}
        existing_messages = {(a['stock_id'], (a['alert_message'] or '').strip()) for a in existing_alerts}
        per_stock_created = {s['stock_id']: 0 for s in stocks}

        created = 0
        for announcement in announcements:
            headline = announcement.get('headline') or ''
            url = announcement.get('attachment_url')
            if not self._is_material_announcement(headline):
                continue
            if url and url in existing_urls:
                continue

            stock = self._match_announcement_to_stock(
                announcement=announcement,
                stocks=stocks,
                symbol_id_to_stock=symbol_id_to_stock,
                symbol_meta=symbol_meta
            )
            if not stock:
                continue
            if per_stock_created[stock['stock_id']] >= per_stock_limit:
                continue

            message = headline[:250] if headline else f"{stock['symbol']} material announcement"
            if (stock['stock_id'], message) in existing_messages:
                continue

            details = self._build_announcement_details(announcement)
            self.create_manual_alert(
                stock_id=stock['stock_id'],
                alert_type='ANNOUNCEMENT',
                message=message,
                details=details,
                url=url
            )
            self._upsert_filing_from_announcement(stock, announcement, headline)
            if url:
                existing_urls.add(url)
            existing_messages.add((stock['stock_id'], message))
            per_stock_created[stock['stock_id']] += 1
            created += 1

        return created

    def sync_portfolio_filings(self, user_id: int, limit: int = 1000, per_stock_limit: int = 4) -> int:
        """
        Persist latest important filings (announcement summaries) for portfolio stocks.
        Returns number of filings upserted/updated in this sync pass.
        """
        for rss_url in config.BSE_RSS_URLS:
            try:
                self.bse_feed_service.ingest_rss_feed(rss_url)
            except Exception:
                continue

        stocks = self.db.get_user_stocks_with_symbol_master(user_id)
        if not stocks:
            return 0

        symbol_id_to_stock = {}
        symbol_meta = {}
        for stock in stocks:
            if stock.get("symbol_id"):
                symbol_id_to_stock[stock["symbol_id"]] = stock
            symbol_meta[stock["symbol"]] = {
                "company_name": stock.get("company_name"),
                "bse_code": stock.get("bse_code"),
                "nse_code": stock.get("nse_code"),
            }

        symbol_ids = [s["symbol_id"] for s in stocks if s.get("symbol_id")]
        bse_codes = [s["bse_code"] for s in stocks if s.get("bse_code")]
        targeted_limit = max(limit, len(stocks) * max(per_stock_limit, 4) * 25)
        announcements = []
        if symbol_ids:
            announcements.extend(self.db.get_bse_announcements_by_symbol_ids(symbol_ids, limit=targeted_limit))
        if bse_codes:
            announcements.extend(self.db.get_bse_announcements_by_scrip_codes(bse_codes, limit=targeted_limit))
        if not announcements:
            announcements = self.db.get_recent_bse_announcements(limit=targeted_limit)

        # De-duplicate merged targeted lists.
        deduped = {}
        for announcement in announcements:
            key = announcement.get("announcement_id") or announcement.get("exchange_ref_id") or announcement.get("rss_guid")
            if key is not None:
                deduped[key] = announcement
        announcements = list(deduped.values())
        per_stock_count = {s["stock_id"]: 0 for s in stocks}
        upserted = 0
        for announcement in announcements:
            headline = announcement.get("headline") or ""
            if not self._is_material_announcement(headline):
                continue

            stock = self._match_announcement_to_stock(
                announcement=announcement,
                stocks=stocks,
                symbol_id_to_stock=symbol_id_to_stock,
                symbol_meta=symbol_meta,
            )
            if not stock:
                continue
            if per_stock_count[stock["stock_id"]] >= per_stock_limit:
                continue

            self._upsert_filing_from_announcement(stock, announcement, headline)
            per_stock_count[stock["stock_id"]] += 1
            upserted += 1

        return upserted

    def _is_material_announcement(self, headline: str) -> bool:
        """Keyword-based materiality filter for announcement headlines."""
        text = (headline or '').lower()
        return any(keyword in text for keyword in self.MATERIAL_KEYWORDS)

    def _build_announcement_details(self, announcement: Dict) -> str:
        """Build human-readable announcement details from stored payload."""
        details = []
        if announcement.get('announcement_date'):
            details.append(f"Announcement Date: {announcement['announcement_date']}")

        raw_payload = announcement.get('raw_payload')
        if raw_payload:
            try:
                payload = json.loads(raw_payload)
                if payload.get('description'):
                    details.append("")
                    details.append(str(payload['description']))
                if payload.get('link'):
                    details.append("")
                    details.append(f"Source Link: {payload['link']}")
            except Exception:
                details.append("")
                details.append(str(raw_payload))

        return "\n".join(details).strip()

    def _classify_category(self, headline: str) -> str:
        """Classify category.

        Args:
            headline: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        text = (headline or "").lower()
        if any(keyword in text for keyword in self.CATEGORY_KEYWORDS["Earnings Call"]):
            return "Earnings Call"

        # Tighten Results categorization so transcript/call notices are not mislabeled.
        strong_result_terms = [
            "unaudited financial results",
            "audited financial results",
            "financial results",
            "results for the quarter",
            "results for quarter",
            "board meeting approving results",
            "statement of financial results",
            "quarter ended",
            "nine months ended",
        ]
        if any(term in text for term in strong_result_terms):
            return "Results"

        for category in ("Order Wins", "Fund Raising", "Capacity Expansion", "Bonus Issue", "Acquisitions", "Open Offer"):
            if any(keyword in text for keyword in self.CATEGORY_KEYWORDS[category]):
                return category
        return "General Update"

    def _build_brief_summary(self, headline: str, announcement: Dict) -> str:
        """Build concise persisted summary for filing rows."""
        summary_parts = []
        if headline:
            summary_parts.append(headline.strip())
        raw_payload = announcement.get("raw_payload")
        if raw_payload:
            try:
                payload = json.loads(raw_payload)
                desc = (payload.get("description") or "").strip()
                if desc:
                    desc = re.sub(r"\s+", " ", desc)
                    summary_parts.append(desc[:300])
            except Exception:
                pass
        return " | ".join(summary_parts)[:420]

    def _upsert_filing_from_announcement(self, stock: Dict, announcement: Dict, headline: str):
        """Persist normalized filing row from an announcement."""
        category = self._classify_category(headline)
        summary = self._build_brief_summary(headline, announcement)
        source_ref = announcement.get("exchange_ref_id") or announcement.get("rss_guid") or announcement.get("attachment_url")
        self.db.upsert_filing(
            stock_id=stock["stock_id"],
            symbol_id=announcement.get("symbol_id") or stock.get("symbol_id"),
            category=category,
            headline=headline or f"{stock['symbol']} update",
            announcement_summary=summary,
            announcement_date=announcement.get("announcement_date"),
            pdf_link=announcement.get("attachment_url"),
            source_exchange="BSE",
            source_ref=source_ref
        )

    def _match_announcement_to_stock(
        self,
        announcement: Dict,
        stocks: List[Dict],
        symbol_id_to_stock: Dict[int, Dict],
        symbol_meta: Dict[str, Dict]
    ) -> Dict:
        """Match an announcement to a portfolio stock using multiple strategies."""
        # 1) Direct symbol_id mapping.
        if announcement.get('symbol_id') in symbol_id_to_stock:
            return symbol_id_to_stock[announcement['symbol_id']]

        # 2) Exact BSE code mapping.
        scrip_code = announcement.get('scrip_code')
        if scrip_code:
            mapped = self.db.get_symbol_by_bse_code(scrip_code)
            if mapped:
                for stock in stocks:
                    if self._normalize_symbol(stock['symbol']) == self._normalize_symbol(mapped['symbol']):
                        return stock

        # 3) Fallback textual matching on headline.
        headline = (announcement.get('headline') or '').upper()
        headline_clean = re.sub(r'[^A-Z0-9 ]+', ' ', headline)
        for stock in stocks:
            symbol = self._normalize_symbol(stock['symbol'])
            if re.search(rf"\b{re.escape(symbol)}\b", headline_clean):
                return stock

            meta = symbol_meta.get(stock['symbol'])
            company_name = (meta.get('company_name') if meta else stock.get('company_name') or '').upper()
            company_alias = re.sub(r'\b(LIMITED|LTD)\b', '', company_name).strip()
            if company_alias and company_alias in headline_clean:
                return stock

        return None

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        """Normalize stock symbol for matching across .NS/.BO and plain forms."""
        sym = (symbol or "").strip().upper()
        if sym.endswith(".NS") or sym.endswith(".BO"):
            sym = sym.rsplit(".", 1)[0]
        return sym
