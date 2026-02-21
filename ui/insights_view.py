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
from services.background_job_service import BackgroundJobService
from ui.summary_dialog import SummaryDialog
from utils.config import config


class InsightsView(QWidget):
    """Quarter-based insights focused on Results and Earnings Call only."""

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
            background_jobs: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        super().__init__()
        self.db = db
        self.alert_service = alert_service
        self.ai_service = ai_service
        self.watchman = WatchmanService(db, ai_service)
        self.background_jobs = background_jobs
        self.current_user_id = None
        self.rows = []
        self.all_rows = []
        self.user_filings = []
        self.stock_filter_map = {}
        self.quarter_filter_value_map = {}
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
        refresh_btn.clicked.connect(self.refresh_reports_async)
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
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Quarter", "Insight", "Company", "Updated", "State", "Summary (Brief)", "View"
        ])
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(2, QHeaderView.Stretch)
        h.setSectionResizeMode(5, QHeaderView.Stretch)
        layout.addWidget(self.table)

        self.info_label = QLabel()
        layout.addWidget(self.info_label)

    def load_for_user(self, user_id: int):
        """Load for user.

        Args:
            user_id: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        self.current_user_id = user_id
        self._load_stock_filter_options(user_id)
        self._load_quarter_filter_options(user_id)
        self.load_insights()

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

    def _load_quarter_filter_options(self, user_id: int):
        """Load quarter filter options.

        Args:
            user_id: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        snapshots = self.db.get_user_global_insight_snapshots(user_id, limit=1000)
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
        """On filter change.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        self.load_insights()

    def load_insights(self):
        """Load insights.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        self.table.setRowCount(0)
        if not self.current_user_id:
            return
        selected_stock_id = self.stock_filter_map.get(self.stock_filter.currentText())
        if selected_stock_id == "ALL":
            selected_stock_id = None
        selected_quarter = self.quarter_filter_value_map.get(self.quarter_filter.currentText(), "LATEST")
        snapshots = self.db.get_user_global_insight_snapshots(self.current_user_id, limit=1000)
        self.user_filings = self.db.get_user_filings(self.current_user_id, limit=5000)
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
            state = self._insight_state(row)
            state_item = QTableWidgetItem(state)
            if state == "New filings available":
                state_item.setForeground(self.palette().highlight())
            self.table.setItem(i, 4, state_item)
            text = row.get("summary_text") or "Not available for this quarter."
            brief = text if len(text) <= 220 else f"{text[:217]}..."
            item = QTableWidgetItem(brief)
            item.setToolTip(text)
            self.table.setItem(i, 5, item)

            btn = QPushButton("Open")
            btn.setObjectName("actionBlendBtn")
            btn.clicked.connect(lambda checked, idx=i: self.open_summary_dialog(idx))
            self.table.setCellWidget(i, 6, btn)

        self.info_label.setText(f"Showing {len(self.rows)} quarter insight snapshot(s).")

    @staticmethod
    def _quarter_sort_key(quarter_label: str):
        """Quarter sort key.

        Args:
            quarter_label: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
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
        """Open summary dialog.

        Args:
            row_idx: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
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

    def _insight_state(self, snapshot: dict) -> str:
        """Detect whether newer filings exist for same stock/quarter/type than snapshot source."""
        stock_id = snapshot.get("stock_id")
        source_filing_id = snapshot.get("source_filing_id")
        quarter_label = snapshot.get("quarter_label")
        insight_type = snapshot.get("insight_type")
        if not stock_id or not quarter_label:
            return "Fresh"
        target_category = "Results" if insight_type == WatchmanService.INSIGHT_RESULT else "Earnings Call"
        relevant = []
        for filing in self.user_filings:
            if filing.get("stock_id") != stock_id:
                continue
            if (filing.get("effective_category") or filing.get("category")) != target_category:
                continue
            f_quarter = WatchmanService._quarter_from_filing(filing)
            if f_quarter != quarter_label:
                continue
            relevant.append(filing)
        if not relevant:
            return "Fresh"
        if not source_filing_id:
            return "New filings available"
        source_row = next((f for f in relevant if f.get("filing_id") == source_filing_id), None)
        if not source_row:
            return "New filings available"
        source_dt = WatchmanService._parse_date(source_row.get("announcement_date"))
        latest_dt = max((WatchmanService._parse_date(f.get("announcement_date")) for f in relevant), default=None)
        if latest_dt and source_dt and latest_dt > source_dt:
            return "New filings available"
        return "Fresh"

    def generate_missing_summaries(self):
        """Generate missing summaries.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        if not self.current_user_id:
            return
        if not self.ai_service.is_available():
            QMessageBox.information(self, "AI Not Available", "Configure AI provider key first.")
            return

        if not self.background_jobs:
            QMessageBox.information(self, "Unavailable", "Background service not ready.")
            return
        job_id = self.background_jobs.enqueue_insight_job(self.current_user_id, force_regenerate=False)
        QMessageBox.information(
            self,
            "Queued",
            (
                f"Insight generation request queued (Job #{job_id}).\n"
                "We will alert you once the reports are ready."
            )
        )

    def refresh_reports_async(self):
        """Queue a non-blocking refresh of missing insights and reload current grid."""
        self.load_insights()
        if not self.current_user_id:
            return
        if not self.ai_service.is_available():
            QMessageBox.information(self, "AI Not Available", "Configure AI provider key first.")
            return
        if not self.background_jobs:
            QMessageBox.information(self, "Unavailable", "Background service not ready.")
            return
        job_id = self.background_jobs.enqueue_insight_job(self.current_user_id, force_regenerate=False)
        QMessageBox.information(
            self,
            "Queued",
            (
                f"Refresh queued (Job #{job_id}).\n"
                "We will alert you once the reports are ready."
            )
        )

    def regenerate_summaries_admin(self):
        """Regenerate summaries admin.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
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

        if not self.background_jobs:
            QMessageBox.information(self, "Unavailable", "Background service not ready.")
            return
        job_id = self.background_jobs.enqueue_insight_job(self.current_user_id, force_regenerate=True)
        QMessageBox.information(
            self,
            "Queued",
            (
                f"Admin regenerate queued (Job #{job_id}).\n"
                "We will alert you once the reports are ready."
            )
        )
