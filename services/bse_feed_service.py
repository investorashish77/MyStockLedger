"""
BSE Feed Service
Ingests BSE RSS announcements into local database for downstream parsing.
"""

import json
import hashlib
import re
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional

import requests
from requests import Response

from database.db_manager import DatabaseManager


class BSEFeedService:
    """Service to ingest and track BSE RSS feed announcements."""
    DEFAULT_BSE_API_URL = "https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w"
    API_HEADERS = {
        "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0",
        "Referer": "https://www.bseindia.com/",
    }

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def fetch_rss_items(self, rss_url: str, timeout: int = 30) -> List[Dict]:
        """Fetch and parse RSS items from BSE feed URL."""
        response = self._fetch_with_headers(rss_url=rss_url, timeout=timeout)

        root = ET.fromstring(response.content)
        items = []
        for item in root.findall(".//item"):
            parsed = {
                "title": self._get_text(item, "title"),
                "link": self._get_text(item, "link"),
                "guid": self._get_text(item, "guid"),
                "pubDate": self._get_text(item, "pubDate"),
                "description": self._get_text(item, "description"),
            }
            if parsed["title"] or parsed["guid"]:
                items.append(parsed)
        return items

    def ingest_rss_feed(self, rss_url: str) -> int:
        """Fetch and store RSS items, return number of items processed."""
        items = self.fetch_rss_items(rss_url=rss_url)
        ingested = 0

        for item in items:
            payload = {
                "title": item.get("title"),
                "link": item.get("link"),
                "pubDate": item.get("pubDate"),
                "description": item.get("description"),
            }

            scrip_code = self._extract_scrip_code(item)
            symbol_id = self._resolve_symbol_id(scrip_code=scrip_code)
            self.db.add_bse_announcement(
                symbol_id=symbol_id,
                scrip_code=scrip_code,
                headline=item.get("title") or "BSE Announcement",
                category="BSE_RSS",
                announcement_date=item.get("pubDate"),
                attachment_url=item.get("link"),
                exchange_ref_id=self._build_exchange_ref_id(item),
                rss_guid=item.get("guid"),
                raw_payload=json.dumps(payload)
            )
            ingested += 1
        return ingested

    def ingest_api_range(
        self,
        api_url: Optional[str],
        start_date_yyyymmdd: str,
        end_date_yyyymmdd: str,
        max_pages: int = 200,
        category: str = "-1",
        search: str = "P",
        filing_type: str = "C",
        scrip_code: Optional[str] = None,
        timeout: int = 30,
    ) -> int:
        """
        Ingest announcements from BSE API with date params.
        Mirrors the working BSE AnnSubCategoryGetData request shape.
        """
        endpoint = (api_url or "").strip() or self.DEFAULT_BSE_API_URL
        request_params = {
            "pageno": 1,
            "strCat": category,
            "strPrevDate": start_date_yyyymmdd,
            "strScrip": (scrip_code or "").strip(),
            "strSearch": search,
            "strToDate": end_date_yyyymmdd,
            "strType": filing_type,
            "subcategory": "",
        }
        total = 0
        for page in range(1, max_pages + 1):
            request_params["pageno"] = page
            response = self._fetch_with_api_headers(api_url=endpoint, timeout=timeout, params=request_params)
            response_payload = response.json()
            rows = self._extract_api_rows(response_payload)
            if not rows:
                break

            for row in rows:
                headline = (
                    row.get("headline")
                    or row.get("HEADLINE")
                    or row.get("NEWS_SUB")
                    or row.get("SUBCATNAME")
                    or "BSE Announcement"
                )
                link = (
                    row.get("pdf_link")
                    or row.get("ATTACHMENTNAME")
                    or row.get("NSURL")
                    or row.get("attachment_url")
                )
                scrip_code = str(row.get("scrip_code") or row.get("SCRIP_CD") or row.get("SCRIPCODE") or "").strip() or None
                guid = str(row.get("guid") or row.get("NEWSID") or row.get("id") or row.get("SLONGNAME") or "").strip() or None
                symbol_id = self._resolve_symbol_id(scrip_code=scrip_code)
                self.db.add_bse_announcement(
                    symbol_id=symbol_id,
                    scrip_code=scrip_code,
                    headline=headline,
                    category="BSE_API",
                    announcement_date=str(
                        row.get("announcement_date")
                        or row.get("NEWS_DT")
                        or row.get("DissemDT")
                        or row.get("DT_TM")
                        or ""
                    ),
                    attachment_url=link,
                    exchange_ref_id=self._build_exchange_ref_id({
                        "guid": guid,
                        "link": link,
                        "title": headline,
                        "pubDate": row.get("announcement_date") or row.get("NEWS_DT")
                    }),
                    rss_guid=guid,
                    raw_payload=json.dumps(row)
                )
                total += 1
        return total

    def get_unprocessed(self, limit: int = 100) -> List[Dict]:
        """Read unprocessed announcements from DB."""
        return self.db.get_unprocessed_bse_announcements(limit=limit)

    def mark_processed(self, announcement_id: int):
        """Mark announcement as processed."""
        self.db.mark_bse_announcement_processed(announcement_id)

    def _resolve_symbol_id(self, scrip_code: Optional[str]) -> Optional[int]:
        """Map BSE scrip code to symbol_id if available."""
        if not scrip_code:
            return None

        row = self.db.get_symbol_by_bse_code(scrip_code)
        if row:
            return row["symbol_id"]
        return None

    @staticmethod
    def _get_text(node, tag: str) -> Optional[str]:
        child = node.find(tag)
        if child is None or child.text is None:
            return None
        return child.text.strip()

    @staticmethod
    def _extract_scrip_code(item: Dict) -> Optional[str]:
        """Try extracting 6-digit scrip code from title/link/description."""
        text = " ".join([
            item.get("title") or "",
            item.get("link") or "",
            item.get("description") or ""
        ])
        match = re.search(r"\b(\d{6})\b", text)
        return match.group(1) if match else None

    @staticmethod
    def _build_exchange_ref_id(item: Dict) -> str:
        """
        Build a stable per-announcement reference id.
        Must be unique across different announcements (unlike scrip code).
        """
        if item.get("guid"):
            return str(item["guid"]).strip()
        if item.get("link"):
            return str(item["link"]).strip()

        raw = "|".join([
            str(item.get("title") or "").strip(),
            str(item.get("pubDate") or "").strip(),
            str(item.get("description") or "").strip(),
        ])
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _fetch_with_headers(self, rss_url: str, timeout: int, params: Dict = None) -> Response:
        """
        Fetch feed with browser-like headers.
        BSE may return 403 for default python-requests user agent.
        """
        base_headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept": "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.bseindia.com/corporates/ann.html",
            "Connection": "keep-alive",
        }

        response = requests.get(rss_url, timeout=timeout, headers=base_headers, params=params)
        if response.status_code == 403:
            # Retry with a stricter browser navigation profile.
            retry_headers = {
                **base_headers,
                "Upgrade-Insecure-Requests": "1",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
            }
            response = requests.get(rss_url, timeout=timeout, headers=retry_headers, params=params)

        response.raise_for_status()
        return response

    def _fetch_with_api_headers(self, api_url: str, timeout: int, params: Dict = None) -> Response:
        """Fetch BSE JSON API endpoint with headers matching working browser request."""
        response = requests.get(api_url, timeout=timeout, headers=self.API_HEADERS, params=params)
        if response.status_code == 403:
            # Retry once with same headers and no-cache hints.
            retry_headers = {
                **self.API_HEADERS,
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
            }
            response = requests.get(api_url, timeout=timeout, headers=retry_headers, params=params)
        response.raise_for_status()
        return response

    @staticmethod
    def _extract_api_rows(payload) -> List[Dict]:
        """Extract list rows from common API payload shapes."""
        if payload is None:
            return []
        if isinstance(payload, list):
            return [row for row in payload if isinstance(row, dict)]
        if isinstance(payload, dict):
            for key in ("Table", "Table1", "Data", "data", "results"):
                rows = payload.get(key)
                if isinstance(rows, list):
                    return [row for row in rows if isinstance(row, dict)]
        return []
