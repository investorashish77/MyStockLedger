"""
Filings View
Shows important portfolio-specific corporate filings with document links and concise summaries.
"""

from datetime import datetime

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMessageBox, QComboBox,
    QDialog, QTextBrowser, QStyle, QScrollArea, QFrame
)
from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QFont, QDesktopServices

from database.db_manager import DatabaseManager
from services.alert_service import AlertService
from services.ai_summary_service import AISummaryService
from utils.config import config


class AlertsView(QWidget):
    """Filings view widget (kept class name for compatibility)."""

    SETTING_BACKFILL_DONE = "filings_api_backfill_done_v1"
    SETTING_LAST_SYNC_DATE = "filings_api_last_sync_date"

    def __init__(self, db: DatabaseManager, alert_service: AlertService, ai_service: AISummaryService):
        super().__init__()
        self.db = db
        self.alert_service = alert_service
        self.ai_service = ai_service
        self.current_user_id = None
        self.current_filings = []
        self.stock_filter_map = {}
        self.category_options = [
            "ALL",
            "Results",
            "Earnings Call",
            "Order Wins",
            "Fund Raising",
            "Capacity Expansion",
            "Bonus Issue",
            "Acquisitions",
            "Open Offer",
            "General Update",
        ]
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        header = QHBoxLayout()
        title = QLabel("Filings")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        header.addWidget(title)

        header.addStretch()

        self.stock_filter = QComboBox()
        self.stock_filter.currentIndexChanged.connect(self.filter_changed)
        header.addWidget(QLabel("Company:"))
        header.addWidget(self.stock_filter)

        self.category_filter = QComboBox()
        self.category_filter.addItems(self.category_options)
        self.category_filter.currentIndexChanged.connect(self.filter_changed)
        header.addWidget(QLabel("Category:"))
        header.addWidget(self.category_filter)

        sync_btn = QPushButton("Sync Filings")
        sync_btn.clicked.connect(lambda: self.sync_filings(force_api=True))
        header.addWidget(sync_btn)
        layout.addLayout(header)

        self.timeline_scroll = QScrollArea()
        self.timeline_scroll.setWidgetResizable(True)
        self.timeline_container = QWidget()
        self.timeline_layout = QVBoxLayout()
        self.timeline_layout.setContentsMargins(4, 4, 4, 4)
        self.timeline_layout.setSpacing(10)
        self.timeline_container.setLayout(self.timeline_layout)
        self.timeline_scroll.setWidget(self.timeline_container)
        layout.addWidget(self.timeline_scroll)

        self.info_label = QLabel()
        layout.addWidget(self.info_label)

    def load_alerts(self, user_id: int, sync_announcements: bool = True):
        self.current_user_id = user_id
        self._load_stock_filter_options(user_id)
        if sync_announcements:
            self.sync_filings(force_api=False)
        else:
            self.load_filings(user_id)

    def sync_filings(self, force_api: bool = False):
        if not self.current_user_id:
            return

        ingest_count = 0
        range_text = ""
        try:
            ingest_count, range_text = self._sync_bse_api_before_render(force=force_api)
        except Exception as exc:
            self.info_label.setText(f"API sync failed: {exc}")

        synced = self.alert_service.sync_portfolio_filings(self.current_user_id, per_stock_limit=4)
        self.load_filings(self.current_user_id)
        if synced > 0 or ingest_count > 0:
            prefix = f"Fetched {ingest_count} row(s){range_text}. " if range_text else ""
            self.info_label.setText(f"{prefix}Synced {synced} filing row(s).")
        elif not self.db.get_recent_bse_announcements(limit=1):
            today = datetime.now().strftime("%Y%m%d")
            self.info_label.setText(
                f"No feed data ingested. Run: python3 scripts/sync_bse_announcements.py --from-date 20260101 --to-date {today}"
            )

    def load_filings(self, user_id: int):
        selected_stock_id = self.stock_filter_map.get(self.stock_filter.currentText())
        if selected_stock_id == "ALL":
            selected_stock_id = None
        category = self.category_filter.currentText()
        filings = self.db.get_user_filings(
            user_id=user_id,
            stock_id=selected_stock_id,
            category=category,
            limit=500
        )
        self.current_filings = filings
        while self.timeline_layout.count():
            child = self.timeline_layout.takeAt(0)
            widget = child.widget()
            if widget:
                widget.deleteLater()
        if not filings:
            self.info_label.setText("No filings found for selected filters.")
            return

        for filing in filings:
            self.timeline_layout.addWidget(self._build_timeline_card(filing))
        self.timeline_layout.addStretch()

        self.info_label.setText(f"Showing {len(filings)} filing(s).")

    def filter_changed(self):
        if self.current_user_id:
            self.load_filings(self.current_user_id)

    def _load_stock_filter_options(self, user_id: int):
        stocks = self.db.get_user_stocks(user_id)
        self.stock_filter.blockSignals(True)
        self.stock_filter.clear()
        self.stock_filter_map = {"All Portfolio Stocks": "ALL"}
        self.stock_filter.addItem("All Portfolio Stocks")
        for stock in stocks:
            label = f"{stock['symbol']} - {stock['company_name']}"
            self.stock_filter_map[label] = stock["stock_id"]
            self.stock_filter.addItem(label)
        self.stock_filter.blockSignals(False)

    def open_pdf(self, url: str):
        if not url:
            QMessageBox.information(self, "No Link", "No filing link available.")
            return
        QDesktopServices.openUrl(QUrl(url))

    @staticmethod
    def resolve_document_url(raw_value: str) -> str:
        value = (raw_value or "").strip()
        if not value:
            return ""
        if value.startswith("http://") or value.startswith("https://"):
            return value
        if value.lower().endswith(".pdf"):
            filename = value.split("/")[-1]
            return f"https://www.bseindia.com/xml-data/corpfiling/AttachHis/{filename}"
        return f"https://www.bseindia.com/{value.lstrip('/')}"

    def open_filing_details(self, row: int, column: int):
        if row < 0 or row >= len(self.current_filings):
            return
        filing = self.current_filings[row]
        summary = filing.get("announcement_summary") or filing.get("headline") or "-"
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Filing Details - {filing.get('symbol')}")
        dialog.resize(860, 560)
        self._apply_active_theme(dialog)
        layout = QVBoxLayout(dialog)
        title = QLabel(
            f"{filing.get('company_name') or filing.get('symbol')} | "
            f"{filing.get('category') or 'General Update'} | "
            f"{filing.get('announcement_date') or '-'}"
        )
        title.setWordWrap(True)
        layout.addWidget(title)

        browser = QTextBrowser()
        browser.setPlainText(summary)
        layout.addWidget(browser)

        dialog.exec_()

    def _sync_bse_api_before_render(self, force: bool = False):
        today = datetime.now().strftime("%Y%m%d")
        backfill_done = self.db.get_setting(self.SETTING_BACKFILL_DONE, "0") == "1"
        last_sync_date = self.db.get_setting(self.SETTING_LAST_SYNC_DATE, "")

        if not backfill_done:
            from_date = config.BSE_HISTORY_START_DATE
        else:
            from_date = last_sync_date or today

        if not from_date or len(from_date) != 8 or not from_date.isdigit():
            from_date = today

        if backfill_done and (not force) and last_sync_date == today:
            return 0, f" [{today}..{today}]"

        ingested = self.alert_service.sync_bse_feed_for_portfolio(
            user_id=self.current_user_id,
            start_date_yyyymmdd=from_date,
            end_date_yyyymmdd=today,
            max_pages_per_symbol=max(5, int(config.BSE_API_MAX_PAGES / 10)),
        )
        self.db.set_setting(self.SETTING_BACKFILL_DONE, "1")
        self.db.set_setting(self.SETTING_LAST_SYNC_DATE, today)
        return ingested, f" [{from_date}..{today}]"

    @staticmethod
    def _category_color(category: str) -> str:
        cat = (category or "").lower()
        mapping = {
            "results": "#3D5AFE",
            "earnings call": "#8E44AD",
            "order wins": "#16A085",
            "fund raising": "#F39C12",
            "capacity expansion": "#2E86DE",
            "bonus issue": "#E67E22",
            "acquisitions": "#9B59B6",
            "open offer": "#C0392B",
        }
        return mapping.get(cat, "#5D6D7E")

    def _build_timeline_card(self, filing: dict) -> QWidget:
        card = QFrame()
        card.setObjectName("timelineCard")
        card.setStyleSheet(
            "QFrame#timelineCard { border: 1px solid #D8E1EA; border-radius: 10px; padding: 8px; }"
        )
        root = QVBoxLayout()
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(6)
        card.setLayout(root)

        top = QHBoxLayout()
        category = filing.get("category") or "General Update"
        category_lbl = QLabel(category)
        category_lbl.setStyleSheet(
            f"background:{self._category_color(category)}; color:white; border-radius:10px; padding:3px 9px; font-size:11px;"
        )
        top.addWidget(category_lbl)
        top.addStretch()
        top.addWidget(QLabel(filing.get("announcement_date") or "-"))
        root.addLayout(top)

        title = QLabel(f"{filing.get('company_name') or filing.get('symbol') or '-'}")
        title.setStyleSheet("font-weight:700; font-size:13px;")
        root.addWidget(title)

        meta = QLabel(f"BSE: {filing.get('bse_code') or '-'}   |   NSE: {filing.get('nse_code') or filing.get('symbol') or '-'}")
        meta.setStyleSheet("color:#718096; font-size:11px;")
        root.addWidget(meta)

        summary = filing.get("announcement_summary") or filing.get("headline") or "-"
        brief = summary if len(summary) <= 220 else f"{summary[:217]}..."
        summary_lbl = QLabel(brief)
        summary_lbl.setWordWrap(True)
        summary_lbl.setToolTip(summary)
        root.addWidget(summary_lbl)

        actions = QHBoxLayout()
        actions.addStretch()
        doc_url = self.resolve_document_url(filing.get("pdf_link"))
        doc_btn = QPushButton("Open Document")
        doc_btn.setIcon(self.style().standardIcon(QStyle.SP_FileIcon))
        doc_btn.setEnabled(bool(doc_url))
        doc_btn.clicked.connect(lambda _=False, url=doc_url: self.open_pdf(url))
        details_btn = QPushButton("Details")
        details_btn.clicked.connect(lambda _=False, f=filing: self.open_filing_detail_dialog(f))
        actions.addWidget(doc_btn)
        actions.addWidget(details_btn)
        root.addLayout(actions)
        return card

    def open_filing_detail_dialog(self, filing: dict):
        summary = filing.get("announcement_summary") or filing.get("headline") or "-"
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Filing Details - {filing.get('symbol')}")
        dialog.resize(860, 560)
        self._apply_active_theme(dialog)
        layout = QVBoxLayout(dialog)
        title = QLabel(
            f"{filing.get('company_name') or filing.get('symbol')} | "
            f"{filing.get('category') or 'General Update'} | "
            f"{filing.get('announcement_date') or '-'}"
        )
        title.setWordWrap(True)
        layout.addWidget(title)
        browser = QTextBrowser()
        browser.setPlainText(summary)
        layout.addWidget(browser)
        dialog.exec_()

    def _apply_active_theme(self, widget: QWidget):
        win = self.window() if hasattr(self, "window") else None
        if win and hasattr(win, "styleSheet"):
            widget.setStyleSheet(win.styleSheet())
