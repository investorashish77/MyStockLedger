"""
Filings View
Shows important portfolio-specific corporate filings with document links and concise summaries.
"""

from datetime import datetime
from urllib.parse import urlparse

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMessageBox, QComboBox,
    QDialog, QTextBrowser, QStyle, QScrollArea, QFrame
)
from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QFont, QDesktopServices

from database.db_manager import DatabaseManager
from services.alert_service import AlertService
from services.ai_summary_service import AISummaryService
from services.background_job_service import BackgroundJobService
from utils.config import config


class AlertsView(QWidget):
    """Filings view widget (kept class name for compatibility)."""

    SETTING_BACKFILL_DONE = "filings_api_backfill_done_v1"
    SETTING_LAST_SYNC_DATE = "filings_api_last_sync_date"

    def __init__(
        self,
        db: DatabaseManager,
        alert_service: AlertService,
        ai_service: AISummaryService,
        background_jobs: BackgroundJobService = None
    ):
        """Init.

        Args:
            db: Input parameter.
            alert_service: Input parameter.
            ai_service: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        super().__init__()
        self.db = db
        self.alert_service = alert_service
        self.ai_service = ai_service
        self.background_jobs = background_jobs
        self.current_user_id = None
        self.current_user = None
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
        """Setup ui.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
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

        self.admin_sync_ann_btn = QPushButton("Admin Sync Announcements")
        self.admin_sync_ann_btn.clicked.connect(self.admin_sync_announcements)
        self.admin_sync_ann_btn.setVisible(False)
        header.addWidget(self.admin_sync_ann_btn)

        self.admin_sync_bhav_btn = QPushButton("Admin Sync Bhavcopy")
        self.admin_sync_bhav_btn.clicked.connect(self.admin_sync_bhavcopy)
        self.admin_sync_bhav_btn.setVisible(False)
        header.addWidget(self.admin_sync_bhav_btn)
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
        """Load alerts.

        Args:
            user_id: Input parameter.
            sync_announcements: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        self.current_user_id = user_id
        self.current_user = self.db.get_user_by_id(user_id)
        can_admin = self._can_run_admin_operations()
        self.admin_sync_ann_btn.setVisible(can_admin)
        self.admin_sync_bhav_btn.setVisible(can_admin)
        self._load_stock_filter_options(user_id)
        if sync_announcements:
            self.sync_filings(force_api=False)
        else:
            self.load_filings(user_id)

    def sync_filings(self, force_api: bool = False):
        """Sync filings.

        Args:
            force_api: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
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
        """Load filings.

        Args:
            user_id: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
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
        """Filter changed.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        if self.current_user_id:
            self.load_filings(self.current_user_id)

    def _load_stock_filter_options(self, user_id: int):
        """Load stock filter options.

        Args:
            user_id: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
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
        """Open pdf.

        Args:
            url: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        if not url:
            QMessageBox.information(self, "No Link", "No filing link available.")
            return
        QDesktopServices.openUrl(QUrl(url))

    @staticmethod
    def _join_base_and_filename(base_url: str, filename: str) -> str:
        """Join base and filename.

        Args:
            base_url: Input parameter.
            filename: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        base = (base_url or "").strip()
        if not base:
            return ""
        if not base.endswith("/"):
            base = f"{base}/"
        return f"{base}{filename}"

    @staticmethod
    def _extract_pdf_filename(value: str) -> str:
        """Extract pdf filename.

        Args:
            value: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        text = (value or "").strip()
        if not text:
            return ""
        parsed = urlparse(text)
        candidate = parsed.path.split("/")[-1] if parsed.path else text.split("/")[-1]
        candidate = candidate.split("?")[0].strip()
        return candidate if candidate.lower().endswith(".pdf") else ""

    @classmethod
    def resolve_document_urls(cls, raw_value: str):
        """
        Resolve primary/alternate BSE filing links.
        Primary uses AttachLive base; alternate uses AttachHis base.
        """
        value = (raw_value or "").strip()
        if not value:
            return "", ""

        filename = cls._extract_pdf_filename(value)
        if filename:
            primary = cls._join_base_and_filename(config.BSE_ATTACH_PRIMARY_BASE, filename)
            alternate = cls._join_base_and_filename(config.BSE_ATTACH_SECONDARY_BASE, filename)
            # If raw absolute URL is not one of the configured canonical links, keep it as alternate.
            if value.startswith("http://") or value.startswith("https://"):
                if value not in {primary, alternate}:
                    alternate = value
            return primary, alternate

        if value.startswith("http://") or value.startswith("https://"):
            return value, ""
        return f"https://www.bseindia.com/{value.lstrip('/')}", ""

    def open_filing_details(self, row: int, column: int):
        """Open filing details.

        Args:
            row: Input parameter.
            column: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        if row < 0 or row >= len(self.current_filings):
            return
        filing = self.current_filings[row]
        summary = filing.get("announcement_summary") or filing.get("headline") or "-"
        doc_url, alt_doc_url = self.resolve_document_urls(filing.get("pdf_link"))
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
        if doc_url:
            links = [f'<a href="{doc_url}">Open Document (Primary)</a>']
            if alt_doc_url:
                links.append(f'<a href="{alt_doc_url}">Open Alternate Link</a>')
            link_lbl = QLabel(" | ".join(links))
            link_lbl.setOpenExternalLinks(True)
            layout.addWidget(link_lbl)

        browser = QTextBrowser()
        browser.setPlainText(summary)
        layout.addWidget(browser)

        dialog.exec_()

    def _sync_bse_api_before_render(self, force: bool = False):
        """Sync bse api before render.

        Args:
            force: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
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
        """Category color.

        Args:
            category: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
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
        """Build timeline card.

        Args:
            filing: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        card = QFrame()
        card.setObjectName("timelineCard")
        card.setStyleSheet(self._card_style())
        root = QVBoxLayout()
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(6)
        card.setLayout(root)

        top = QHBoxLayout()
        category = filing.get("effective_category") or filing.get("category") or "General Update"
        category_lbl = QLabel(category)
        category_lbl.setStyleSheet(
            f"background:{self._category_color(category)}; color:white; border-radius:10px; padding:3px 9px; font-size:11px;"
        )
        top.addWidget(category_lbl)
        if filing.get("category_override"):
            override_lbl = QLabel("Manual")
            override_lbl.setStyleSheet("color:#60A5FA; font-size:11px; font-weight:600;")
            top.addWidget(override_lbl)
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
        doc_url, alt_doc_url = self.resolve_document_urls(filing.get("pdf_link"))
        doc_btn = QPushButton("Open Document")
        doc_btn.setIcon(self.style().standardIcon(QStyle.SP_FileIcon))
        doc_btn.setEnabled(bool(doc_url))
        if alt_doc_url:
            doc_btn.setToolTip(f"Primary: {doc_url}\nAlternate: {alt_doc_url}")
        doc_btn.clicked.connect(lambda _=False, url=doc_url: self.open_pdf(url))
        alt_btn = QPushButton("Alternate Link")
        alt_btn.setIcon(self.style().standardIcon(QStyle.SP_DialogOpenButton))
        alt_btn.setEnabled(bool(alt_doc_url))
        alt_btn.clicked.connect(lambda _=False, url=alt_doc_url: self.open_pdf(url))
        actions.addWidget(doc_btn)
        actions.addWidget(alt_btn)
        root.addLayout(actions)

        if self._can_override_categories():
            override_row = QHBoxLayout()
            override_row.addWidget(QLabel("Category Override:"))
            override_combo = QComboBox()
            override_combo.addItem("Auto (Detected)", userData="")
            for option in self.category_options:
                if option == "ALL":
                    continue
                override_combo.addItem(option, userData=option)
            active_override = filing.get("category_override") or ""
            idx = override_combo.findData(active_override)
            override_combo.setCurrentIndex(idx if idx >= 0 else 0)
            override_row.addWidget(override_combo, 1)
            save_btn = QPushButton("Apply")
            save_btn.clicked.connect(
                lambda _=False, fid=filing.get("filing_id"), c=override_combo: self._apply_category_override(fid, c)
            )
            override_row.addWidget(save_btn)
            root.addLayout(override_row)
        return card

    def open_filing_detail_dialog(self, filing: dict):
        """Open filing detail dialog.

        Args:
            filing: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        summary = filing.get("announcement_summary") or filing.get("headline") or "-"
        doc_url, alt_doc_url = self.resolve_document_urls(filing.get("pdf_link"))
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
        if doc_url:
            links = [f'<a href="{doc_url}">Open Document (Primary)</a>']
            if alt_doc_url:
                links.append(f'<a href="{alt_doc_url}">Open Alternate Link</a>')
            link_lbl = QLabel(" | ".join(links))
            link_lbl.setOpenExternalLinks(True)
            layout.addWidget(link_lbl)
        browser = QTextBrowser()
        browser.setPlainText(summary)
        layout.addWidget(browser)
        dialog.exec_()

    def _apply_active_theme(self, widget: QWidget):
        """Apply active theme.

        Args:
            widget: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        win = self.window() if hasattr(self, "window") else None
        if win and hasattr(win, "styleSheet"):
            widget.setStyleSheet(win.styleSheet())

    def _is_dark_theme(self) -> bool:
        """Is dark theme.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        win = self.window() if hasattr(self, "window") else None
        return bool(win and hasattr(win, "current_theme") and getattr(win, "current_theme") == "dark")

    def _card_style(self) -> str:
        """Card style.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        if self._is_dark_theme():
            return "QFrame#timelineCard { border: 1px solid rgba(120,160,200,0.22); border-radius: 12px; padding: 8px; background: rgba(20,28,38,0.72); }"
        return "QFrame#timelineCard { border: 1px solid #D8E1EA; border-radius: 12px; padding: 8px; background: #FFFFFF; }"

    def _can_override_categories(self) -> bool:
        """Can override categories.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        if not config.FILINGS_OVERRIDE_ADMIN_ONLY:
            return True
        return self._is_admin_user()

    def _is_admin_user(self) -> bool:
        """Check if current user is configured as admin."""
        if not self.current_user:
            return False
        user_id = self.current_user.get("user_id")
        mobile = str(self.current_user.get("mobile_number") or "").strip()
        return (user_id in config.ADMIN_USER_IDS) or (mobile in config.ADMIN_USER_MOBILES)

    def _apply_category_override(self, filing_id: int, combo: QComboBox):
        """Apply category override.

        Args:
            filing_id: Input parameter.
            combo: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        if not filing_id:
            return
        override_value = combo.currentData()
        override_value = (override_value or "").strip() or None
        self.db.set_filing_category_override(filing_id, override_value, locked=True)
        self.load_filings(self.current_user_id)

    def _can_run_admin_operations(self) -> bool:
        """Check if current user can run admin sync operations."""
        if not config.ADMIN_SYNC_ADMIN_ONLY:
            return True
        return self._is_admin_user()

    def admin_sync_announcements(self):
        """Queue admin announcements sync in background."""
        if not self.current_user_id:
            return
        if not self._can_run_admin_operations():
            QMessageBox.information(self, "Access Denied", "Admin sync operations are restricted.")
            return
        if not self.background_jobs:
            QMessageBox.information(self, "Unavailable", "Background job service not ready.")
            return
        job_id = self.background_jobs.enqueue_announcements_sync_job(self.current_user_id, force_full=False)
        QMessageBox.information(
            self,
            "Queued",
            f"Announcements sync queued (Job #{job_id}). We will alert you once it is complete."
        )

    def admin_sync_bhavcopy(self):
        """Queue admin bhavcopy sync in background."""
        if not self.current_user_id:
            return
        if not self._can_run_admin_operations():
            QMessageBox.information(self, "Access Denied", "Admin sync operations are restricted.")
            return
        if not self.background_jobs:
            QMessageBox.information(self, "Unavailable", "Background job service not ready.")
            return
        job_id = self.background_jobs.enqueue_bhavcopy_sync_job(self.current_user_id, force_full=False)
        QMessageBox.information(
            self,
            "Queued",
            f"Bhavcopy sync queued (Job #{job_id}). We will alert you once it is complete."
        )
