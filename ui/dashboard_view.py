"""
Dashboard View
Modern overview with KPI cards, trend signal, portfolio snapshot, and recent filings.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QTableWidget,
    QTableWidgetItem, QHeaderView, QListWidget, QListWidgetItem, QPushButton
)
from PyQt5.QtGui import QFont, QColor

from database.db_manager import DatabaseManager
from services.stock_service import StockService


class DashboardView(QWidget):
    """Overview dashboard for key portfolio and filings insights."""

    def __init__(self, db: DatabaseManager, stock_service: StockService):
        super().__init__()
        self.db = db
        self.stock_service = stock_service
        self.current_user_id = None
        self.current_range = "weekly"
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        title_row = QHBoxLayout()
        title = QLabel("Dashboard")
        font = QFont()
        font.setPointSize(18)
        font.setBold(True)
        title.setFont(font)
        title_row.addWidget(title)
        title_row.addStretch()
        self.sync_hint = QLabel("Live overview")
        title_row.addWidget(self.sync_hint)
        layout.addLayout(title_row)

        cards = QHBoxLayout()
        self.daily_card = self._build_card("Daily Gain/Loss")
        self.weekly_card = self._build_card("Weekly Gain/Loss")
        self.overall_card = self._build_card("Total Returns")
        cards.addWidget(self.daily_card)
        cards.addWidget(self.weekly_card)
        cards.addWidget(self.overall_card)
        layout.addLayout(cards)

        middle = QHBoxLayout()
        left = QFrame()
        left.setObjectName("dashPanel")
        left_layout = QVBoxLayout()
        left.setLayout(left_layout)
        left_layout.addWidget(QLabel("Portfolio Trend Signal"))
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
        left_layout.addLayout(range_row)
        self.trend_label = QLabel("No data")
        self.trend_label.setObjectName("trendLabel")
        left_layout.addWidget(self.trend_label)
        left_layout.addWidget(QLabel("Top Holdings Snapshot"))
        self.holdings_table = QTableWidget()
        self.holdings_table.setColumnCount(3)
        self.holdings_table.setHorizontalHeaderLabels(["Asset", "Current Price", "P&L"])
        h = self.holdings_table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.Stretch)
        self.holdings_table.setMaximumHeight(230)
        left_layout.addWidget(self.holdings_table)
        middle.addWidget(left, 3)

        right = QFrame()
        right.setObjectName("dashPanel")
        right_layout = QVBoxLayout()
        right.setLayout(right_layout)
        right_header = QHBoxLayout()
        right_header.addWidget(QLabel("Recent Filings"))
        right_header.addStretch()
        self.open_filings_btn = QPushButton("Open Filings")
        right_header.addWidget(self.open_filings_btn)
        right_layout.addLayout(right_header)
        self.filings_list = QListWidget()
        right_layout.addWidget(self.filings_list)
        middle.addWidget(right, 2)
        layout.addLayout(middle)

    @staticmethod
    def _build_card(title: str):
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

    def load_dashboard(self, user_id: int):
        self.current_user_id = user_id
        portfolio = self.db.get_portfolio_summary(user_id)
        series_all = self.db.get_portfolio_performance_series(user_id=user_id)
        self._render_portfolio_metrics(portfolio, series_all)
        self._render_trend(series_all)
        self._render_holdings_table(portfolio)
        self._render_recent_filings(user_id)
        self._update_range_buttons()

    def _render_portfolio_metrics(self, portfolio, series_all):
        total_invested = 0.0
        total_current = 0.0

        for row in portfolio:
            symbol = row["symbol"]
            exchange = row.get("exchange")
            qty = row["quantity"]
            avg = row["avg_price"]
            qsym = self.stock_service.to_quote_symbol(symbol, exchange=exchange)
            current = self.stock_service.get_current_price(qsym) or avg
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
        if not series_all:
            self.trend_label.setText("No trend data available (sync bhavcopy first).")
            return
        values = [row["portfolio_value"] for row in series_all]
        if self.current_range == "daily":
            selected = values[-2:] if len(values) >= 2 else values
        elif self.current_range == "weekly":
            selected = values[-7:] if len(values) >= 7 else values
        else:
            selected = values
        self.trend_label.setText(self._sparkline(selected))

    def _render_holdings_table(self, portfolio):
        self.holdings_table.setRowCount(0)
        enriched = self.db.get_user_stocks_with_symbol_master(self.current_user_id) if self.current_user_id else []
        bse_by_symbol = {row["symbol"]: row.get("bse_code") for row in enriched}
        ranked = []
        for row in portfolio:
            symbol = row["symbol"]
            bse_code = bse_by_symbol.get(symbol) or bse_by_symbol.get(symbol.replace(".NS", ""))
            current = None
            if bse_code:
                series = self.db.get_bse_daily_prices(bse_code=bse_code, limit=1)
                if series:
                    current = series[-1]["close_price"]
            if current is None:
                qsym = self.stock_service.to_quote_symbol(symbol, exchange=row.get("exchange"))
                current = self.stock_service.get_current_price(qsym) or row["avg_price"]
            pnl = (current - row["avg_price"]) * row["quantity"]
            ranked.append((symbol, current, pnl))
        ranked.sort(key=lambda x: abs(x[2]), reverse=True)
        for i, (symbol, current, pnl) in enumerate(ranked[:8]):
            self.holdings_table.insertRow(i)
            self.holdings_table.setItem(i, 0, QTableWidgetItem(symbol))
            self.holdings_table.setItem(i, 1, QTableWidgetItem(f"₹{current:,.2f}"))
            pnl_item = QTableWidgetItem(f"₹{pnl:,.2f}")
            pnl_item.setForeground(QColor("#2E7D32" if pnl >= 0 else "#C62828"))
            self.holdings_table.setItem(i, 2, pnl_item)

    def _render_recent_filings(self, user_id: int):
        self.filings_list.clear()
        rows = self.db.get_user_filings(user_id=user_id, limit=15)
        for filing in rows:
            item = QListWidgetItem(
                f"[{filing.get('category') or 'Update'}] {filing.get('symbol')} | "
                f"{filing.get('announcement_date') or '-'}\n"
                f"{(filing.get('headline') or '-')[:120]}"
            )
            self.filings_list.addItem(item)

    def set_range(self, range_key: str):
        self.current_range = range_key
        self._update_range_buttons()
        if self.current_user_id:
            series_all = self.db.get_portfolio_performance_series(user_id=self.current_user_id)
            self._render_trend(series_all)

    def _update_range_buttons(self):
        selected = {"daily": self.daily_btn, "weekly": self.weekly_btn, "all_time": self.all_time_btn}
        for key, btn in selected.items():
            btn.setEnabled(key != self.current_range)

    @staticmethod
    def _set_card(card: QFrame, value: float, pct: float):
        color = "#2E7D32" if value >= 0 else "#C62828"
        card._value.setText(f"₹{value:,.2f}")
        card._value.setStyleSheet(f"color: {color};")
        card._sub.setText(f"{pct:+.2f}%")
        card._sub.setStyleSheet(f"color: {color};")

    @staticmethod
    def _sparkline(points):
        if not points:
            return "No trend data available"
        points = [float(p) for p in points]
        bars = "▁▂▃▄▅▆▇█"
        low = min(points)
        high = max(points)
        if high - low < 1e-9:
            return "Trend: " + (bars[3] * min(20, len(points))) + f"  | Value: ₹{points[-1]:,.2f}"
        mapped = []
        for p in points[-20:]:
            idx = int((p - low) / (high - low) * (len(bars) - 1))
            mapped.append(bars[max(0, min(idx, len(bars) - 1))])
        change = points[-1] - points[0]
        return "Trend: " + "".join(mapped) + f"  | Range Change: ₹{change:,.2f}"
