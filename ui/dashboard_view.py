"""
Dashboard View
Modern overview with KPI cards, trend signal, portfolio snapshot, and recent filings.
"""

from datetime import datetime

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QTableWidget,
    QTableWidgetItem, QHeaderView, QPushButton, QDialog, QTextEdit, QDialogButtonBox, QMessageBox,
    QGraphicsDropShadowEffect
)
from PyQt5.QtGui import QFont, QColor, QPainter, QPen, QPainterPath, QLinearGradient
from PyQt5.QtCore import Qt

from database.db_manager import DatabaseManager
from services.ai_summary_service import AISummaryService
from services.stock_service import StockService
from utils.config import config


class PerformanceLineChart(QWidget):
    """Simple line chart widget for portfolio trend visualization."""

    def __init__(self):
        """Init.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        super().__init__()
        self.values = []
        self.setMinimumHeight(170)

    def set_values(self, values):
        """Set values.

        Args:
            values: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        self.values = [float(v) for v in values if v is not None]
        self.update()

    def paintEvent(self, event):
        """Paintevent.

        Args:
            event: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(8, 8, -8, -8)
        painter.setPen(QPen(QColor("#6B7788"), 1, Qt.DotLine))
        painter.drawRect(rect)

        if len(self.values) < 2:
            painter.setPen(QPen(QColor("#8FA4BD"), 1))
            painter.drawText(rect.adjusted(8, 8, -8, -8), Qt.AlignCenter, "No trend data")
            return

        low = min(self.values)
        high = max(self.values)
        span = high - low or 1.0
        step_x = rect.width() / (len(self.values) - 1)

        path = QPainterPath()
        for i, value in enumerate(self.values):
            x = rect.left() + i * step_x
            y = rect.bottom() - ((value - low) / span) * rect.height()
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)

        fill_path = QPainterPath(path)
        fill_path.lineTo(rect.right(), rect.bottom())
        fill_path.lineTo(rect.left(), rect.bottom())
        fill_path.closeSubpath()

        gradient = QLinearGradient(rect.left(), rect.top(), rect.left(), rect.bottom())
        gradient.setColorAt(0.0, QColor(61, 90, 254, 90))
        gradient.setColorAt(1.0, QColor(61, 90, 254, 10))
        painter.fillPath(fill_path, gradient)

        painter.setPen(QPen(QColor("#4F8DF0"), 2.2))
        painter.drawPath(path)


class DashboardView(QWidget):
    """Overview dashboard for key portfolio and filings insights."""

    def __init__(
        self,
        db: DatabaseManager,
        stock_service: StockService,
        ai_service: AISummaryService = None,
        show_kpis: bool = True
    ):
        """Init.

        Args:
            db: Input parameter.
            stock_service: Input parameter.
            ai_service: Input parameter.
            show_kpis: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        super().__init__()
        self.db = db
        self.stock_service = stock_service
        self.ai_service = ai_service
        self.show_kpis = show_kpis
        self.current_user_id = None
        self.current_range = "weekly"
        self.current_notes = []
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

        if self.show_kpis:
            cards = QHBoxLayout()
            self.daily_card = self._build_card("Daily Gain/Loss")
            self.weekly_card = self._build_card("Weekly Gain/Loss")
            self.overall_card = self._build_card("Total Returns")
            cards.addWidget(self.daily_card)
            cards.addWidget(self.weekly_card)
            cards.addWidget(self.overall_card)
            layout.addLayout(cards)

        middle = QHBoxLayout()
        chart_panel = QFrame()
        chart_panel.setObjectName("dashPanel")
        self.chart_panel = chart_panel
        chart_layout = QVBoxLayout()
        chart_panel.setLayout(chart_layout)
        chart_title = QLabel("PORTFOLIO PERFORMANCE CHART")
        title_font = QFont()
        title_font.setPointSize(13)
        title_font.setBold(True)
        chart_title.setFont(title_font)
        chart_layout.addWidget(chart_title)
        range_row = QHBoxLayout()
        self.daily_btn = QPushButton("Daily")
        self.weekly_btn = QPushButton("Weekly")
        self.all_time_btn = QPushButton("All-Time")
        self.daily_btn.clicked.connect(lambda: self.set_range("daily"))
        self.weekly_btn.clicked.connect(lambda: self.set_range("weekly"))
        self.all_time_btn.clicked.connect(lambda: self.set_range("all_time"))
        range_row.addWidget(self.daily_btn)
        range_row.addWidget(self.weekly_btn)
        range_row.addWidget(self.all_time_btn)
        range_row.addStretch()
        chart_layout.addLayout(range_row)
        self.trend_label = QLabel("No trend data")
        self.trend_label.setObjectName("trendLabel")
        self.chart = PerformanceLineChart()
        chart_layout.addWidget(self.chart)
        chart_layout.addWidget(self.trend_label)
        middle.addWidget(chart_panel, 2)

        holdings_panel = QFrame()
        holdings_panel.setObjectName("dashPanel")
        self.holdings_panel = holdings_panel
        holdings_layout = QVBoxLayout()
        holdings_panel.setLayout(holdings_layout)
        holdings_layout.addWidget(QLabel("My Holdings"))
        self.holdings_table = QTableWidget()
        self.holdings_table.setColumnCount(2)
        self.holdings_table.setHorizontalHeaderLabels(["Asset", "P&L"])
        h = self.holdings_table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.Stretch)
        h.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.holdings_table.verticalHeader().setDefaultSectionSize(38)
        holdings_layout.addWidget(self.holdings_table)
        middle.addWidget(holdings_panel, 1)
        layout.addLayout(middle)

        notes_panel = QFrame()
        notes_panel.setObjectName("dashPanel")
        self.notes_panel = notes_panel
        notes_layout = QVBoxLayout()
        notes_panel.setLayout(notes_layout)
        notes_layout.addWidget(QLabel("Journal Notes"))
        self.notes_table = QTableWidget()
        self.notes_table.setColumnCount(4)
        self.notes_table.setHorizontalHeaderLabels(["Symbol", "Date", "Note", "Analyst View"])
        self.notes_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.notes_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.notes_table.verticalHeader().setDefaultSectionSize(46)
        self.notes_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.notes_table.doubleClicked.connect(self._edit_selected_note)
        notes_layout.addWidget(self.notes_table)
        notes_hint = QLabel("Double-click a note row to edit and save.")
        notes_hint.setObjectName("journalHint")
        notes_layout.addWidget(notes_hint)
        layout.addWidget(notes_panel)
        self._apply_depth_effects()

    @staticmethod
    def _build_card(title: str):
        """Build card.

        Args:
            title: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        card = QFrame()
        card.setObjectName("kpiCard")
        layout = QVBoxLayout()
        t = QLabel(title)
        t.setObjectName("kpiTitle")
        v = QLabel("₹0.00")
        v.setObjectName("kpiValue")
        s = QLabel("0.00%")
        s.setObjectName("kpiSub")
        card._value = v
        card._sub = s
        layout.addWidget(t)
        layout.addWidget(v)
        layout.addWidget(s)
        card.setLayout(layout)
        return card

    def load_dashboard(self, user_id: int, use_live_quotes: bool = True):
        """Load dashboard.

        Args:
            user_id: Input parameter.
            use_live_quotes: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        self.current_user_id = user_id
        portfolio = self.db.get_portfolio_summary(user_id)
        series_all = self.db.get_portfolio_performance_series(user_id=user_id)
        if self.show_kpis:
            self._render_portfolio_metrics(portfolio, series_all, use_live_quotes=use_live_quotes)
        self._render_trend(series_all)
        self._render_holdings_table(portfolio, use_live_quotes=use_live_quotes)
        self._render_journal_notes(user_id)
        self._update_range_buttons()

    def _render_portfolio_metrics(self, portfolio, series_all, use_live_quotes: bool = True):
        """Render portfolio metrics.

        Args:
            portfolio: Input parameter.
            series_all: Input parameter.
            use_live_quotes: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        total_invested = 0.0
        total_current = 0.0

        for row in portfolio:
            symbol = row["symbol"]
            exchange = row.get("exchange")
            qty = row["quantity"]
            avg = row["avg_price"]
            qsym = self.stock_service.to_quote_symbol(symbol, exchange=exchange)
            current = self.db.get_latest_price(row["stock_id"]) or avg
            if use_live_quotes:
                current = self.stock_service.get_current_price(qsym) or current
            invested = avg * qty
            current_val = current * qty
            total_invested += invested
            total_current += current_val

        total_daily = 0.0
        total_weekly = 0.0
        if series_all:
            if len(series_all) >= 2:
                total_daily = series_all[-1]["portfolio_value"] - series_all[-2]["portfolio_value"]
            if len(series_all) >= 6:
                total_weekly = series_all[-1]["portfolio_value"] - series_all[-6]["portfolio_value"]
            elif len(series_all) >= 2:
                total_weekly = series_all[-1]["portfolio_value"] - series_all[0]["portfolio_value"]

        total_returns = total_current - total_invested
        overall_pct = (total_returns / total_invested * 100) if total_invested else 0.0
        daily_pct = (total_daily / total_current * 100) if total_current else 0.0
        weekly_pct = (total_weekly / total_current * 100) if total_current else 0.0

        self._set_card(self.daily_card, total_daily, daily_pct)
        self._set_card(self.weekly_card, total_weekly, weekly_pct)
        self._set_card(self.overall_card, total_returns, overall_pct)

    def _render_trend(self, series_all):
        """Render trend.

        Args:
            series_all: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        if not series_all:
            self.chart.set_values([])
            self.trend_label.setText("No trend data available (sync bhavcopy first).")
            return
        values = [row["portfolio_value"] for row in series_all]
        if self.current_range == "daily":
            selected = values[-2:] if len(values) >= 2 else values
        elif self.current_range == "weekly":
            selected = values[-7:] if len(values) >= 7 else values
        else:
            selected = values
        self.chart.set_values(selected)
        if selected:
            delta = selected[-1] - selected[0]
            self.trend_label.setText(
                f"{self.current_range.title()} trend | Last: ₹{selected[-1]:,.2f} | Change: ₹{delta:,.2f}"
            )
        else:
            self.trend_label.setText("No trend data")

    def _render_holdings_table(self, portfolio, use_live_quotes: bool = True):
        """Render holdings table.

        Args:
            portfolio: Input parameter.
            use_live_quotes: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        self.holdings_table.setRowCount(0)
        ranked = []
        for row in portfolio:
            symbol = row["symbol"]
            exchange = row.get("exchange")
            avg_price = row["avg_price"]
            quantity = row["quantity"]
            quote_symbol = self.stock_service.to_quote_symbol(symbol, exchange=exchange)
            current = self.db.get_latest_price(row["stock_id"]) or avg_price
            if use_live_quotes:
                live_price = self.stock_service.get_current_price(quote_symbol)
                if live_price is not None:
                    current = live_price
                    self.db.save_price(row["stock_id"], current)
            pnl = (current - avg_price) * quantity
            ranked.append((symbol, pnl))
        ranked.sort(key=lambda x: abs(x[1]), reverse=True)
        for i, (symbol, pnl) in enumerate(ranked[:8]):
            self.holdings_table.insertRow(i)
            self.holdings_table.setItem(i, 0, QTableWidgetItem(symbol))
            pnl_item = QTableWidgetItem(f"₹{pnl:,.2f}")
            pnl_item.setForeground(QColor("#2E7D32" if pnl >= 0 else "#C62828"))
            self.holdings_table.setItem(i, 1, pnl_item)

    def _render_journal_notes(self, user_id: int):
        """Render journal notes.

        Args:
            user_id: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        self.notes_table.setRowCount(0)
        self.current_notes = self.db.get_user_journal_notes(user_id)
        for i, row in enumerate(self.current_notes):
            self.notes_table.insertRow(i)
            symbol_item = QTableWidgetItem(row["symbol"])
            symbol_item.setData(Qt.UserRole, row["transaction_id"])
            self.notes_table.setItem(i, 0, symbol_item)
            self.notes_table.setItem(i, 1, QTableWidgetItem(row.get("transaction_date") or "-"))
            note_text = row.get("thesis") or ""
            brief = note_text if len(note_text) <= 180 else f"{note_text[:177]}..."
            note_item = QTableWidgetItem(brief)
            note_item.setToolTip(note_text)
            self.notes_table.setItem(i, 2, note_item)
            btn = QPushButton("Analyst View")
            btn.setObjectName("actionBlendBtn")
            btn.clicked.connect(lambda _=False, idx=i: self._open_analyst_view(idx))
            self.notes_table.setCellWidget(i, 3, btn)

    def _ensure_analyst_view_for_stock(self, note_row: dict) -> bool:
        """Generate analyst view for one stock if missing."""
        stock_id = note_row.get("stock_id")
        if not stock_id:
            return False
        existing = self.db.get_analyst_consensus(stock_id)
        if existing and (existing.get("report_text") or "").strip():
            return True
        if not self.ai_service or not self.ai_service.is_available():
            return False

        as_of_date = datetime.now().strftime("%Y-%m-%d")
        current_price = self.db.get_latest_price(stock_id)
        result = self.ai_service.generate_analyst_consensus(
            company_name=note_row.get("company_name") or note_row.get("symbol") or "",
            stock_symbol=note_row.get("symbol") or "",
            current_price=current_price,
            as_of_date=as_of_date,
        )
        if result and (result.get("summary_text") or "").strip():
            self.db.upsert_analyst_consensus(
                stock_id=stock_id,
                report_text=result.get("summary_text"),
                status="GENERATED",
                provider=result.get("provider") or self.ai_service.provider,
                as_of_date=as_of_date,
            )
            return True

        self.db.upsert_analyst_consensus(
            stock_id=stock_id,
            report_text=None,
            status="FAILED",
            provider=self.ai_service.provider if self.ai_service else None,
            as_of_date=as_of_date,
        )
        return False

    def _open_analyst_view(self, row_idx: int):
        """Open analyst view.

        Args:
            row_idx: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        if row_idx < 0 or row_idx >= len(self.current_notes):
            return
        note_row = self.current_notes[row_idx]
        stock_id = note_row.get("stock_id")
        if not stock_id:
            QMessageBox.information(self, "Analyst View", "Stock reference not available.")
            return
        if not self._ensure_analyst_view_for_stock(note_row):
            QMessageBox.information(
                self,
                "Analyst View",
                "Unable to generate analyst consensus now (possible rate limit). Try again later."
            )
            return
        report = self.db.get_analyst_consensus(stock_id)
        if not report or not (report.get("report_text") or "").strip():
            QMessageBox.information(self, "Analyst View", "Analyst consensus not available yet.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Analyst View - {note_row.get('symbol')}")
        dialog.resize(820, 560)
        self._apply_active_theme(dialog)
        root = QVBoxLayout(dialog)
        meta = QLabel(
            f"{note_row.get('company_name') or note_row.get('symbol')} | "
            f"As of: {report.get('as_of_date') or '-'} | "
            f"Provider: {report.get('provider') or '-'}"
        )
        root.addWidget(meta)
        viewer = QTextEdit()
        viewer.setReadOnly(True)
        viewer.setPlainText(report.get("report_text") or "")
        root.addWidget(viewer)
        ok_btn = QDialogButtonBox(QDialogButtonBox.Ok)
        ok_btn.accepted.connect(dialog.accept)
        root.addWidget(ok_btn)
        dialog.exec_()

    def _edit_selected_note(self, index):
        """Edit selected note.

        Args:
            index: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        row = index.row()
        if row < 0 or row >= len(self.current_notes):
            return
        note_row = self.current_notes[row]
        transaction_id = note_row["transaction_id"]
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Edit Journal Note - {note_row['symbol']}")
        dialog.resize(680, 420)
        self._apply_active_theme(dialog)
        root = QVBoxLayout(dialog)
        editor = QTextEdit()
        editor.setPlainText(note_row.get("thesis") or "")
        root.addWidget(editor)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        root.addWidget(buttons)
        if dialog.exec_() == QDialog.Accepted:
            updated = editor.toPlainText().strip()
            self.db.update_transaction(transaction_id, thesis=updated)
            if self.current_user_id:
                self._render_journal_notes(self.current_user_id)

    def set_range(self, range_key: str):
        """Set range.

        Args:
            range_key: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        self.current_range = range_key
        self._update_range_buttons()
        if self.current_user_id:
            series_all = self.db.get_portfolio_performance_series(user_id=self.current_user_id)
            self._render_trend(series_all)

    def _update_range_buttons(self):
        """Update range buttons.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        selected = {"daily": self.daily_btn, "weekly": self.weekly_btn, "all_time": self.all_time_btn}
        for key, btn in selected.items():
            btn.setEnabled(key != self.current_range)

    @staticmethod
    def _set_card(card: QFrame, value: float, pct: float):
        """Set card.

        Args:
            card: Input parameter.
            value: Input parameter.
            pct: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        color = "#2E7D32" if value >= 0 else "#C62828"
        card._value.setText(f"₹{value:,.2f}")
        card._value.setStyleSheet(f"color: {color};")
        card._sub.setText(f"{pct:+.2f}%")
        card._sub.setStyleSheet(f"color: {color};")

    def _apply_depth_effects(self):
        """Apply depth effects.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        cfg = self._panel_shadow_preset()
        for panel in (self.chart_panel, self.holdings_panel, self.notes_panel):
            effect = QGraphicsDropShadowEffect()
            effect.setBlurRadius(cfg["blur"])
            effect.setOffset(0, cfg["offset"])
            effect.setColor(QColor(0, 0, 0, cfg["alpha"]))
            panel.setGraphicsEffect(effect)

    @staticmethod
    def _panel_shadow_preset():
        """Panel shadow preset.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        mapping = {
            "subtle": {"blur": 16, "offset": 3, "alpha": 75},
            "medium": {"blur": 26, "offset": 5, "alpha": 110},
            "bold": {"blur": 36, "offset": 8, "alpha": 145},
        }
        return mapping.get(config.UI_GLOW_PRESET, mapping["medium"])

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
