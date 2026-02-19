"""
Insights View
Quarter-specific Result + Concall snapshots for portfolio stocks.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox
)
from PyQt5.QtGui import QFont

from database.db_manager import DatabaseManager
from services.ai_summary_service import AISummaryService
from services.alert_service import AlertService
from services.watchman_service import WatchmanService
from ui.summary_dialog import SummaryDialog
from utils.config import config


class InsightsView(QWidget):
    """Quarter-based insights focused on Results and Earnings Call only."""

    def __init__(self, db: DatabaseManager, alert_service: AlertService, ai_service: AISummaryService):
        super().__init__()
        self.db = db
        self.alert_service = alert_service
        self.ai_service = ai_service
        self.watchman = WatchmanService(db, ai_service)
        self.current_user_id = None
        self.rows = []
        self.all_rows = []
        self.stock_filter_map = {}
        self.quarter_filter_value_map = {}
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
        self.stock_filter.currentIndexChanged.connect(self._on_filter_change)
        header.addWidget(QLabel("Company:"))
        header.addWidget(self.stock_filter)

        self.quarter_filter = QComboBox()
        self.quarter_filter.currentIndexChanged.connect(self._on_filter_change)
        header.addWidget(QLabel("Quarter:"))
        header.addWidget(self.quarter_filter)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.load_insights)
        header.addWidget(refresh_btn)

        gen_btn = QPushButton("Generate Missing")
        gen_btn.clicked.connect(self.generate_missing_summaries)
        header.addWidget(gen_btn)

        regen_btn = QPushButton("Regenerate (Admin)")
        regen_btn.clicked.connect(self.regenerate_summaries_admin)
        regen_btn.setVisible(config.ENABLE_ADMIN_REGENERATE)
        self.regen_btn = regen_btn
        header.addWidget(regen_btn)
        layout.addLayout(header)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Quarter", "Insight", "Company", "Updated", "Summary (Brief)", "View"
        ])
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(2, QHeaderView.Stretch)
        h.setSectionResizeMode(4, QHeaderView.Stretch)
        layout.addWidget(self.table)

        self.info_label = QLabel()
        layout.addWidget(self.info_label)

    def load_for_user(self, user_id: int):
        self.current_user_id = user_id
        self._load_stock_filter_options(user_id)
        self._load_quarter_filter_options(user_id)
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

    def _load_quarter_filter_options(self, user_id: int):
        snapshots = self.db.get_user_insight_snapshots(user_id, limit=1000)
        usable_snapshots = []
        for row in snapshots:
            status = (row.get("status") or "").upper()
            summary_text = (row.get("summary_text") or "").strip().lower()
            if status in {"NOT_AVAILABLE", "FAILED"}:
                continue
            if summary_text == "not available for this quarter.":
                continue
            usable_snapshots.append(row)
        quarter_labels = sorted(
            {row.get("quarter_label") for row in usable_snapshots if row.get("quarter_label")},
            key=self._quarter_sort_key,
            reverse=True,
        )
        self.quarter_filter.blockSignals(True)
        self.quarter_filter.clear()
        self.quarter_filter_value_map = {"Latest Quarter": "LATEST", "All Quarters": "ALL"}
        self.quarter_filter.addItem("Latest Quarter")
        self.quarter_filter.addItem("All Quarters")
        for q in quarter_labels:
            self.quarter_filter_value_map[q] = q
            self.quarter_filter.addItem(q)
        self.quarter_filter.blockSignals(False)

    def _on_filter_change(self):
        self.load_insights()

    def load_insights(self):
        self.table.setRowCount(0)
        if not self.current_user_id:
            return
        selected_stock_id = self.stock_filter_map.get(self.stock_filter.currentText())
        if selected_stock_id == "ALL":
            selected_stock_id = None
        selected_quarter = self.quarter_filter_value_map.get(self.quarter_filter.currentText(), "LATEST")
        snapshots = self.db.get_user_insight_snapshots(self.current_user_id, limit=1000)
        self.all_rows = []
        for row in snapshots:
            if selected_stock_id is not None and row.get("stock_id") != selected_stock_id:
                continue
            self.all_rows.append(row)

        latest_quarter = None
        available_quarters = [r.get("quarter_label") for r in self.all_rows if r.get("quarter_label")]
        if available_quarters:
            latest_quarter = sorted(set(available_quarters), key=self._quarter_sort_key, reverse=True)[0]

        self.rows = []
        for row in self.all_rows:
            status = (row.get("status") or "").upper()
            summary_text = (row.get("summary_text") or "").strip()
            if status in {"NOT_AVAILABLE", "FAILED"}:
                continue
            if summary_text.lower() == "not available for this quarter.":
                continue
            if selected_quarter == "LATEST" and latest_quarter and row.get("quarter_label") != latest_quarter:
                continue
            if selected_quarter not in ("ALL", "LATEST") and row.get("quarter_label") != selected_quarter:
                continue
            self.rows.append(row)

        for i, row in enumerate(self.rows):
            self.table.insertRow(i)
            quarter = row.get("quarter_label") or "-"
            insight_type = row.get("insight_type")
            insight_label = (
                f"{quarter} Result Summary"
                if insight_type == WatchmanService.INSIGHT_RESULT
                else f"{quarter} Con Call Summary"
            )
            self.table.setItem(i, 0, QTableWidgetItem(quarter))
            self.table.setItem(i, 1, QTableWidgetItem(insight_label))
            self.table.setItem(i, 2, QTableWidgetItem(row.get("company_name") or row.get("symbol") or "-"))
            self.table.setItem(i, 3, QTableWidgetItem(row.get("updated_at") or row.get("generated_at") or "-"))
            text = row.get("summary_text") or "Not available for this quarter."
            brief = text if len(text) <= 220 else f"{text[:217]}..."
            item = QTableWidgetItem(brief)
            item.setToolTip(text)
            self.table.setItem(i, 4, item)

            btn = QPushButton("Open")
            btn.setObjectName("actionBlendBtn")
            btn.clicked.connect(lambda checked, idx=i: self.open_summary_dialog(idx))
            self.table.setCellWidget(i, 5, btn)

        self.info_label.setText(f"Showing {len(self.rows)} quarter insight snapshot(s).")

    @staticmethod
    def _quarter_sort_key(quarter_label: str):
        if not quarter_label:
            return (0, 0)
        parts = quarter_label.strip().split()
        if len(parts) != 2:
            return (0, 0)
        q_part, fy_part = parts
        q_num = 0
        if q_part.upper().startswith("Q"):
            try:
                q_num = int(q_part[1:])
            except ValueError:
                q_num = 0
        fy_num = 0
        if fy_part.upper().startswith("FY"):
            try:
                fy_num = int(fy_part[2:])
            except ValueError:
                fy_num = 0
        return (fy_num, q_num)

    def open_summary_dialog(self, row_idx: int):
        if row_idx < 0 or row_idx >= len(self.rows):
            return
        row = self.rows[row_idx]
        dialog = SummaryDialog(
            stock_symbol=row.get("symbol") or "",
            summary_text=row.get("summary_text") or "",
            sentiment=row.get("sentiment") or "NEUTRAL",
            parent=self
        )
        dialog.exec_()

    def generate_missing_summaries(self):
        if not self.current_user_id:
            return
        if not self.ai_service.is_available():
            QMessageBox.information(self, "AI Not Available", "Configure AI provider key first.")
            return

        result = self.watchman.run_for_user(user_id=self.current_user_id, force_regenerate=False)
        self._load_quarter_filter_options(self.current_user_id)
        self.load_insights()
        QMessageBox.information(
            self,
            "Insights",
            (
                f"Generated: {result['generated']}\n"
                f"Skipped existing: {result['skipped_existing']}\n"
                f"Not available: {result['not_available']}\n"
                f"Failed: {result['failed']}"
            )
        )

    def regenerate_summaries_admin(self):
        if not self.current_user_id:
            return
        if not config.ENABLE_ADMIN_REGENERATE:
            QMessageBox.information(self, "Disabled", "Admin regenerate is disabled by configuration.")
            return
        if not self.ai_service.is_available():
            QMessageBox.information(self, "AI Not Available", "Configure AI provider key first.")
            return
        reply = QMessageBox.question(
            self,
            "Admin Regenerate",
            "Regenerate quarter insights for portfolio stocks?\nThis will overwrite existing snapshots.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        result = self.watchman.run_for_user(user_id=self.current_user_id, force_regenerate=True)
        self._load_quarter_filter_options(self.current_user_id)
        self.load_insights()
        QMessageBox.information(
            self,
            "Admin Regenerate",
            (
                f"Generated: {result['generated']}\n"
                f"Not available: {result['not_available']}\n"
                f"Failed: {result['failed']}"
            )
        )
