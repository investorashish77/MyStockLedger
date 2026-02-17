"""
Insights View
Shows AI summaries for Results and Earnings Call categories.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox
)
from PyQt5.QtGui import QFont

from database.db_manager import DatabaseManager
from services.ai_summary_service import AISummaryService
from services.alert_service import AlertService
from ui.summary_dialog import SummaryDialog
from ui.alerts_view import AlertsView


class InsightsView(QWidget):
    """AI insights focused on results and conference-call disclosures."""
    MAX_GENERATION_CANDIDATES = 30

    def __init__(self, db: DatabaseManager, alert_service: AlertService, ai_service: AISummaryService):
        super().__init__()
        self.db = db
        self.alert_service = alert_service
        self.ai_service = ai_service
        self.current_user_id = None
        self.rows = []
        self.stock_filter_map = {}
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        header = QHBoxLayout()
        title = QLabel("Insights")
        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        title.setFont(font)
        header.addWidget(title)
        header.addStretch()

        self.stock_filter = QComboBox()
        self.stock_filter.currentIndexChanged.connect(self.load_insights)
        header.addWidget(QLabel("Company:"))
        header.addWidget(self.stock_filter)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.load_insights)
        header.addWidget(refresh_btn)

        gen_btn = QPushButton("Generate Missing")
        gen_btn.clicked.connect(self.generate_missing_summaries)
        header.addWidget(gen_btn)
        layout.addLayout(header)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Category", "Company", "Date", "Summary (Brief)", "Sentiment", "View"
        ])
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(1, QHeaderView.Stretch)
        h.setSectionResizeMode(3, QHeaderView.Stretch)
        layout.addWidget(self.table)

        self.info_label = QLabel()
        layout.addWidget(self.info_label)

    def load_for_user(self, user_id: int):
        self.current_user_id = user_id
        self._load_stock_filter_options(user_id)
        self.load_insights()

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

    def _get_filtered_filings(self):
        if not self.current_user_id:
            return []
        stock_id = self.stock_filter_map.get(self.stock_filter.currentText())
        if stock_id == "ALL":
            stock_id = None
        filings = self.db.get_user_filings(user_id=self.current_user_id, stock_id=stock_id, limit=800)
        return [f for f in filings if (f.get("category") in ("Results", "Earnings Call"))]

    def _get_or_create_alert_for_filing(self, filing, existing_alerts=None):
        resolved_url = AlertsView.resolve_document_url(filing.get("pdf_link"))
        existing = existing_alerts if existing_alerts is not None else self.db.get_user_alerts(self.current_user_id)
        for alert in existing:
            if (
                alert.get("stock_id") == filing.get("stock_id")
                and alert.get("announcement_url") == resolved_url
                and (alert.get("alert_message") or "") == (filing.get("headline") or "")
            ):
                return alert["alert_id"]
        return self.alert_service.create_manual_alert(
            stock_id=filing["stock_id"],
            alert_type="ANNOUNCEMENT",
            message=filing.get("headline") or "Filing",
            details=filing.get("announcement_summary"),
            url=resolved_url
        )

    @staticmethod
    def _category_key(category: str) -> str:
        value = (category or "").strip().lower()
        if value == "results":
            return "results"
        if value == "earnings call":
            return "earnings_call"
        return ""

    @staticmethod
    def _sort_key_for_filing(filing: dict):
        dt = filing.get("announcement_datetime") or filing.get("announcement_date") or ""
        return str(dt)

    def _select_generation_candidates(self, filings):
        """Pick latest Results + Earnings Call filings per portfolio stock."""
        sorted_rows = sorted(filings, key=self._sort_key_for_filing, reverse=True)
        selected = []
        seen = set()
        for filing in sorted_rows:
            category_key = self._category_key(filing.get("category"))
            stock_id = filing.get("stock_id")
            if not stock_id or not category_key:
                continue
            bucket = (stock_id, category_key)
            if bucket in seen:
                continue
            seen.add(bucket)
            selected.append(filing)
            if len(selected) >= self.MAX_GENERATION_CANDIDATES:
                break
        return selected

    def load_insights(self):
        self.table.setRowCount(0)
        if not self.current_user_id:
            return
        filings = self._get_filtered_filings()
        self.rows = []
        for filing in filings:
            alert_id = self._get_or_create_alert_for_filing(filing)
            ai_row = self.db.get_alert_summary(alert_id)
            if not ai_row:
                continue
            self.rows.append((filing, alert_id, ai_row))

        for i, (filing, alert_id, ai_row) in enumerate(self.rows):
            self.table.insertRow(i)
            self.table.setItem(i, 0, QTableWidgetItem(filing.get("category") or "-"))
            self.table.setItem(i, 1, QTableWidgetItem(filing.get("company_name") or filing.get("symbol") or "-"))
            self.table.setItem(i, 2, QTableWidgetItem(filing.get("announcement_date") or "-"))
            text = ai_row.get("summary_text") or "-"
            brief = text if len(text) <= 220 else f"{text[:217]}..."
            item = QTableWidgetItem(brief)
            item.setToolTip(text)
            self.table.setItem(i, 3, item)
            self.table.setItem(i, 4, QTableWidgetItem(ai_row.get("sentiment") or "NEUTRAL"))

            btn = QPushButton("Open")
            btn.clicked.connect(lambda checked, idx=i: self.open_summary_dialog(idx))
            self.table.setCellWidget(i, 5, btn)

        self.info_label.setText(f"Showing {len(self.rows)} AI insight(s).")

    def open_summary_dialog(self, row_idx: int):
        if row_idx < 0 or row_idx >= len(self.rows):
            return
        filing, alert_id, ai_row = self.rows[row_idx]
        dialog = SummaryDialog(
            stock_symbol=filing.get("symbol") or "",
            summary_text=ai_row.get("summary_text") or "",
            sentiment=ai_row.get("sentiment") or "NEUTRAL",
            parent=self
        )
        dialog.exec_()

    def generate_missing_summaries(self):
        if not self.current_user_id:
            return
        if not self.ai_service.is_available():
            QMessageBox.information(self, "AI Not Available", "Configure AI provider key first.")
            return

        filings = self._get_filtered_filings()
        candidates = self._select_generation_candidates(filings)
        existing_alerts = self.db.get_user_alerts(self.current_user_id)
        generated = 0
        for filing in candidates:
            alert_id = self._get_or_create_alert_for_filing(filing, existing_alerts=existing_alerts)
            if self.db.get_alert_summary(alert_id):
                continue

            announcement_text = filing.get("announcement_summary") or filing.get("headline") or ""
            document_url = AlertsView.resolve_document_url(filing.get("pdf_link"))
            result = self.ai_service.generate_summary(
                stock_symbol=filing.get("symbol") or "",
                announcement_text=announcement_text,
                announcement_type=filing.get("category") or "ANNOUNCEMENT",
                document_url=document_url
            )
            if not result:
                continue
            self.db.save_ai_summary(
                alert_id=alert_id,
                summary_text=result.get("summary_text") or "",
                sentiment=result.get("sentiment") or "NEUTRAL"
            )
            self.alert_service.mark_as_read(alert_id)
            generated += 1

        self.load_insights()
        QMessageBox.information(
            self,
            "Insights",
            f"Generated {generated} new AI insight(s) from {len(candidates)} latest portfolio filing candidates."
        )
