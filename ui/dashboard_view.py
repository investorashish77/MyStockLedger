"""Dashboard view for EquityJournal."""

from datetime import datetime

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PyQt5.QtWidgets import (
    QAction,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)

from database.db_manager import DatabaseManager
from services.ai_summary_service import AISummaryService
from services.stock_service import StockService
from ui.add_stock_dialog import AddStockDialog
from ui.portfolio_view import PortfolioView
from ui.ui_kit import SectionPanel, WeightBar
from utils.config import config


class PortfolioValueChart(QWidget):
    """Dark-theme portfolio value line chart."""

    def __init__(self):
        super().__init__()
        self._points = []
        self.setMinimumHeight(150)

    def set_series(self, series_rows):
        monthly = {}
        for row in series_rows or []:
            date_text = (row.get("trade_date") or "").strip()
            value = float(row.get("portfolio_value") or 0.0)
            if len(date_text) < 7:
                continue
            month_key = date_text[:7]
            monthly[month_key] = value
        if not monthly:
            self._points = []
            self.update()
            return

        keys = sorted(monthly.keys())[-7:]
        self._points = [(k, monthly[k]) for k in keys]
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#0A1520"))

        rect = self.rect().adjusted(12, 8, -12, -26)
        if len(self._points) < 2:
            p.setPen(QPen(QColor("#6D819A"), 1))
            p.drawText(rect, Qt.AlignCenter, "No trend data")
            return

        values = [v for _, v in self._points]
        low = min(values)
        high = max(values)
        span = (high - low) or 1.0
        step_x = rect.width() / (len(values) - 1)

        coords = []
        for i, value in enumerate(values):
            x = rect.left() + i * step_x
            y = rect.bottom() - ((value - low) / span) * rect.height()
            coords.append((x, y))

        path = QPainterPath()
        path.moveTo(coords[0][0], coords[0][1])
        for i in range(1, len(coords)):
            prev_x, prev_y = coords[i - 1]
            x, y = coords[i]
            cx = (prev_x + x) / 2.0
            path.cubicTo(cx, prev_y, cx, y, x, y)

        fill_path = QPainterPath(path)
        fill_path.lineTo(rect.right(), rect.bottom())
        fill_path.lineTo(rect.left(), rect.bottom())
        fill_path.closeSubpath()

        grad = QLinearGradient(rect.left(), rect.top(), rect.left(), rect.bottom())
        grad.setColorAt(0.0, QColor(14, 165, 233, 78))
        grad.setColorAt(1.0, QColor(14, 165, 233, 0))
        p.fillPath(fill_path, grad)

        p.setPen(QPen(QColor("#11B9FF"), 2.2))
        p.drawPath(path)

        # Highlight last point.
        last_x, last_y = coords[-1]
        p.setPen(QPen(QColor("#0A1520"), 2))
        p.setBrush(QColor("#E6EDF3"))
        p.drawEllipse(int(last_x - 4), int(last_y - 4), 8, 8)

        # Month labels.
        p.setPen(QPen(QColor("#3A5573"), 1))
        for i, (month_key, _) in enumerate(self._points):
            x = rect.left() + i * step_x
            month_label = self._month_name(month_key)
            p.drawText(int(x - 14), rect.bottom() + 20, 30, 14, Qt.AlignCenter, month_label)

    @staticmethod
    def _month_name(month_key: str) -> str:
        try:
            dt = datetime.strptime(month_key, "%Y-%m")
            return dt.strftime("%b")
        except Exception:
            return month_key


class DonutAllocationWidget(QWidget):
    """Simple sector allocation donut chart."""

    _colors = [
        QColor("#22C55E"), QColor("#0EA5E9"), QColor("#A855F7"), QColor("#F59E0B"),
        QColor("#F97316"), QColor("#EC4899"), QColor("#6366F1"), QColor("#14B8A6"),
    ]

    def __init__(self):
        super().__init__()
        self._segments = []
        self.setFixedSize(122, 122)

    def set_allocations(self, allocations: dict):
        total = float(sum(max(0.0, float(v or 0.0)) for v in allocations.values()))
        if total <= 0:
            self._segments = []
            self.update()
            return
        segments = []
        for idx, (name, value) in enumerate(sorted(allocations.items(), key=lambda x: x[1], reverse=True)):
            pct = float(value) / total
            segments.append((name, pct, self._colors[idx % len(self._colors)]))
        self._segments = segments
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        outer = self.rect().adjusted(10, 10, -10, -10)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#0B1521"))
        p.drawEllipse(outer)

        if not self._segments:
            p.setPen(QPen(QColor("#5A6D83"), 1))
            p.drawText(self.rect(), Qt.AlignCenter, "No\nsector")
            return

        start = 90 * 16
        for _name, pct, color in self._segments:
            span = int(-pct * 360 * 16)
            p.setBrush(color)
            p.drawPie(outer, start, span)
            start += span

        inner = outer.adjusted(22, 22, -22, -22)
        p.setBrush(QColor("#0A1520"))
        p.drawEllipse(inner)


class SortableTableWidgetItem(QTableWidgetItem):
    """Table item with explicit sortable key (numeric/date/text safe)."""

    SORT_ROLE = Qt.UserRole + 200

    def __lt__(self, other):
        if isinstance(other, QTableWidgetItem):
            mine = self.data(self.SORT_ROLE)
            theirs = other.data(self.SORT_ROLE)
            if mine is not None and theirs is not None:
                try:
                    return mine < theirs
                except Exception:
                    pass
        return super().__lt__(other)


class DashboardView(QWidget):
    """Overview dashboard with portfolio value, snapshot and portfolio table."""

    def __init__(
        self,
        db: DatabaseManager,
        stock_service: StockService,
        ai_service: AISummaryService = None,
        show_kpis: bool = True,
    ):
        super().__init__()
        self.db = db
        self.stock_service = stock_service
        self.ai_service = ai_service
        self.show_kpis = show_kpis
        self.current_user_id = None
        self.current_rows = []
        self._portfolio_helper = PortfolioView(self.db, self.stock_service)
        # Use PortfolioView only as an action helper (dialogs/transactions).
        # Keep it non-visual so no legacy portfolio UI can bleed into dashboard.
        self._portfolio_helper.setParent(self)
        self._portfolio_helper.hide()
        self._portfolio_helper.setGeometry(0, 0, 0, 0)
        self._portfolio_helper.setMinimumSize(0, 0)
        self._portfolio_helper.setMaximumSize(0, 0)
        self.setup_ui()

    def setup_ui(self):
        self.setObjectName("dashboardRoot")
        self.setAutoFillBackground(True)
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        split = QHBoxLayout()
        split.setSpacing(12)
        root.addLayout(split)

        self.chart_panel = SectionPanel()
        self.chart_panel.setObjectName("dashPanel")
        split.addWidget(self.chart_panel, 3)

        value_header = QHBoxLayout()
        value_meta = QVBoxLayout()
        self.portfolio_value_title = QLabel("PORTFOLIO VALUE")
        self.portfolio_value_title.setObjectName("portfolioValueTitle")
        self.portfolio_value_label = QLabel("₹0.00")
        self.portfolio_value_label.setObjectName("portfolioValueAmount")
        value_meta.addWidget(self.portfolio_value_title)
        value_meta.addWidget(self.portfolio_value_label)
        value_header.addLayout(value_meta)
        value_header.addStretch()

        value_right = QVBoxLayout()
        self.total_return_badge = QLabel("0.00% total")
        self.total_return_badge.setObjectName("returnBadgeNeutral")
        self.invested_label = QLabel("Invested: ₹0.00")
        self.invested_label.setObjectName("investedLabel")
        value_right.addWidget(self.total_return_badge, 0, Qt.AlignRight)
        value_right.addWidget(self.invested_label, 0, Qt.AlignRight)
        value_header.addLayout(value_right)
        self.chart_panel.body_layout.addLayout(value_header)

        self.chart_widget = PortfolioValueChart()
        self.chart_panel.body_layout.addWidget(self.chart_widget)

        self.snapshot_panel = SectionPanel("HOLDING SNAPSHOT")
        self.snapshot_panel.setObjectName("dashPanel")
        split.addWidget(self.snapshot_panel, 2)
        if getattr(self.snapshot_panel, "_title_label", None):
            self.snapshot_panel._title_label.setObjectName("portfolioValueTitle")

        counts_row = QHBoxLayout()
        self.winners_card = self._build_snapshot_metric_card("WINNERS", "0", "0%")
        self.losers_card = self._build_snapshot_metric_card("LOSERS", "0", "0%")
        counts_row.addWidget(self.winners_card)
        counts_row.addWidget(self.losers_card)
        self.snapshot_panel.body_layout.addLayout(counts_row)

        best_worst = QFrame()
        best_worst.setObjectName("bestWorstBox")
        bw = QVBoxLayout(best_worst)
        bw.setContentsMargins(10, 8, 10, 8)
        bw.setSpacing(6)
        best_row = QHBoxLayout()
        best_row.setContentsMargins(0, 0, 0, 0)
        best_row.setSpacing(8)
        self.best_key = QLabel("Best performer")
        self.best_key.setObjectName("bestWorstKey")
        self.best_value = QLabel("-")
        self.best_value.setObjectName("bestPerformer")
        self.best_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        best_row.addWidget(self.best_key)
        best_row.addStretch()
        best_row.addWidget(self.best_value)
        bw.addLayout(best_row)

        worst_row = QHBoxLayout()
        worst_row.setContentsMargins(0, 0, 0, 0)
        worst_row.setSpacing(8)
        self.worst_key = QLabel("Worst performer")
        self.worst_key.setObjectName("bestWorstKey")
        self.worst_value = QLabel("-")
        self.worst_value.setObjectName("worstPerformer")
        self.worst_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        worst_row.addWidget(self.worst_key)
        worst_row.addStretch()
        worst_row.addWidget(self.worst_value)
        bw.addLayout(worst_row)
        self.snapshot_panel.body_layout.addWidget(best_worst)

        alloc_row = QHBoxLayout()
        alloc_row.setContentsMargins(0, 0, 0, 0)
        alloc_row.setSpacing(10)
        self.industry_donut = DonutAllocationWidget()
        alloc_row.addWidget(self.industry_donut, 0, Qt.AlignTop)

        legend_wrap = QWidget()
        self.industry_legend_layout = QVBoxLayout(legend_wrap)
        self.industry_legend_layout.setContentsMargins(0, 2, 0, 0)
        self.industry_legend_layout.setSpacing(5)
        alloc_row.addWidget(legend_wrap, 1)
        self.snapshot_panel.body_layout.addLayout(alloc_row)

        self.portfolio_panel = SectionPanel("Portfolio")
        self.portfolio_panel.setObjectName("dashPanel")
        if getattr(self.portfolio_panel, "_title_label", None):
            self.portfolio_panel._title_label.setObjectName("portfolioValueTitle")
        root.addWidget(self.portfolio_panel, 1)

        table_header = QHBoxLayout()
        table_header.addStretch()
        self.portfolio_panel.body_layout.addLayout(table_header)

        self.portfolio_table = QTableWidget()
        self.portfolio_table.setColumnCount(12)
        self.portfolio_table.setHorizontalHeaderLabels([
            "Date", "Symbol", "Industry", "Qty", "Avg Price", "LTP", "Investment", "Weight", "P&L", "Return", "Notes", "Action"
        ])
        header = self.portfolio_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        for idx in (3, 4, 5, 6, 8, 9, 10, 11):
            header.setSectionResizeMode(idx, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.Stretch)
        self.portfolio_table.verticalHeader().setDefaultSectionSize(46)
        self.portfolio_table.verticalHeader().setVisible(False)
        self.portfolio_table.setAlternatingRowColors(True)
        self.portfolio_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.portfolio_table.doubleClicked.connect(self._open_selected_transactions)
        self.portfolio_table.setSortingEnabled(True)
        self.portfolio_panel.body_layout.addWidget(self.portfolio_table)

        self._apply_depth_effects()

    @staticmethod
    def _build_snapshot_metric_card(title: str, value: str, pct: str) -> QFrame:
        card = QFrame()
        card.setObjectName("snapshotMetricCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)
        t = QLabel(title)
        t.setObjectName("snapshotMetricTitle")
        v = QLabel(value)
        v.setObjectName("snapshotMetricValue")
        s = QLabel(pct)
        s.setObjectName("snapshotMetricSub")
        layout.addWidget(t)
        layout.addWidget(v)
        layout.addWidget(s)
        card._title = t
        card._value = v
        card._sub = s
        return card

    def load_dashboard(self, user_id: int, use_live_quotes: bool = True):
        self.current_user_id = user_id
        rows = self._build_portfolio_rows(user_id, use_live_quotes=use_live_quotes)
        self.current_rows = rows

        series = self.db.get_portfolio_performance_series(user_id=user_id)
        self._render_value_panel(rows, series)
        self._render_snapshot(rows)
        self._render_portfolio_table(rows)

    def _build_portfolio_rows(self, user_id: int, use_live_quotes: bool = True) -> list:
        portfolio = self.db.get_portfolio_summary(user_id)
        enriched = self.db.get_user_stocks_with_symbol_master(user_id)
        sector_by_stock = {r["stock_id"]: (r.get("sector") or "Unknown") for r in enriched}
        industry_by_stock = {
            r["stock_id"]: (r.get("industry") or r.get("industry_group") or r.get("sector") or "Unknown")
            for r in enriched
        }

        rows = []
        total_current = 0.0

        for stock in portfolio:
            symbol = stock["symbol"]
            exchange = stock.get("exchange")
            qty = int(stock.get("quantity") or 0)
            avg_price = float(stock.get("avg_price") or 0.0)

            quote_symbol = self.stock_service.to_quote_symbol(symbol, exchange=exchange)
            current_price = float(self.db.get_latest_price(stock["stock_id"]) or avg_price)
            if use_live_quotes:
                live_price = self.stock_service.get_current_price(quote_symbol)
                if live_price is not None:
                    current_price = float(live_price)
                    self.db.save_price(stock["stock_id"], current_price)

            investment = avg_price * qty
            current_value = current_price * qty
            pnl = current_value - investment
            return_pct = (pnl / investment * 100.0) if investment > 0 else 0.0

            txs = self.db.get_stock_transactions(stock["stock_id"]) or []
            latest_date = txs[0].get("transaction_date") if txs else "-"
            latest_note = ""
            for tx in txs:
                thesis = (tx.get("thesis") or "").strip()
                if thesis:
                    latest_note = thesis
                    break

            row = {
                "stock_id": stock["stock_id"],
                "symbol": symbol,
                "company_name": stock.get("company_name") or symbol,
                "date": latest_date or "-",
                "qty": qty,
                "avg_price": avg_price,
                "ltp": current_price,
                "investment": investment,
                "current_value": current_value,
                "pnl": pnl,
                "return_pct": return_pct,
                "note": latest_note,
                "sector": sector_by_stock.get(stock["stock_id"], "Unknown") or "Unknown",
                "industry": industry_by_stock.get(stock["stock_id"], "Unknown") or "Unknown",
            }
            rows.append(row)
            total_current += current_value

        for row in rows:
            row["weight"] = (row["current_value"] / total_current * 100.0) if total_current else 0.0

        rows.sort(key=lambda r: r["current_value"], reverse=True)
        return rows

    def _render_value_panel(self, rows: list, series: list):
        total_current = sum(r["current_value"] for r in rows)
        total_invested = sum(r["investment"] for r in rows)
        total_return = total_current - total_invested
        total_pct = (total_return / total_invested * 100.0) if total_invested else 0.0

        self.portfolio_value_label.setText(f"₹{total_current:,.2f}")
        self.invested_label.setText(f"Invested: ₹{total_invested:,.2f}")
        self.total_return_badge.setText(f"{total_pct:+.2f}% total")

        if total_return >= 0:
            self.total_return_badge.setObjectName("returnBadgePositive")
        else:
            self.total_return_badge.setObjectName("returnBadgeNegative")
        self.total_return_badge.style().unpolish(self.total_return_badge)
        self.total_return_badge.style().polish(self.total_return_badge)

        self.chart_widget.set_series(series)

    def _render_snapshot(self, rows: list):
        winners = [r for r in rows if r["pnl"] > 0]
        losers = [r for r in rows if r["pnl"] < 0]
        total = len(rows) or 1

        self.winners_card._value.setText(str(len(winners)))
        self.winners_card._sub.setText(f"{(len(winners) / total * 100):.0f}% of holdings")

        self.losers_card._value.setText(str(len(losers)))
        self.losers_card._sub.setText(f"{(len(losers) / total * 100):.0f}% of holdings")

        if rows:
            best = max(rows, key=lambda r: r["return_pct"])
            worst = min(rows, key=lambda r: r["return_pct"])
            self.best_value.setText(f"{best['symbol']} {best['return_pct']:+.2f}%")
            self.worst_value.setText(f"{worst['symbol']} {worst['return_pct']:+.2f}%")
        else:
            self.best_value.setText("-")
            self.worst_value.setText("-")
        self._render_industry_allocation(rows)

    def _render_portfolio_table(self, rows: list):
        self.portfolio_table.setSortingEnabled(False)
        self.portfolio_table.setRowCount(0)

        for idx, row in enumerate(rows):
            self.portfolio_table.insertRow(idx)

            date_item = SortableTableWidgetItem(row["date"])
            date_item.setData(Qt.UserRole, row["stock_id"])
            date_item.setData(Qt.UserRole + 1, row["symbol"])
            date_item.setData(SortableTableWidgetItem.SORT_ROLE, self._date_sort_key(row["date"]))
            self.portfolio_table.setItem(idx, 0, date_item)

            symbol_item = SortableTableWidgetItem(f"{row['symbol']} - {row['company_name']}")
            symbol_item.setData(SortableTableWidgetItem.SORT_ROLE, (row["symbol"] or "").upper())
            self.portfolio_table.setItem(idx, 1, symbol_item)

            industry = row.get("industry") or "Unknown"
            industry_item = SortableTableWidgetItem(industry)
            industry_item.setData(SortableTableWidgetItem.SORT_ROLE, industry.upper())
            self.portfolio_table.setItem(idx, 2, industry_item)

            self.portfolio_table.setItem(idx, 3, QTableWidgetItem(str(row["qty"])))
            self.portfolio_table.setItem(idx, 4, QTableWidgetItem(f"₹{row['avg_price']:,.2f}"))
            self.portfolio_table.setItem(idx, 5, QTableWidgetItem(f"₹{row['ltp']:,.2f}"))

            investment_item = SortableTableWidgetItem(f"₹{row['investment']:,.2f}")
            investment_item.setData(SortableTableWidgetItem.SORT_ROLE, float(row["investment"]))
            self.portfolio_table.setItem(idx, 6, investment_item)

            weight_item = SortableTableWidgetItem(f"{row['weight']:.2f}%")
            weight_item.setData(SortableTableWidgetItem.SORT_ROLE, float(row["weight"]))
            self.portfolio_table.setItem(idx, 7, weight_item)
            self.portfolio_table.setCellWidget(idx, 7, self._build_weight_cell(row["weight"]))

            pnl_item = SortableTableWidgetItem(f"₹{row['pnl']:,.2f}")
            pnl_item.setData(SortableTableWidgetItem.SORT_ROLE, float(row["pnl"]))
            pnl_item.setForeground(QColor("#34D399" if row["pnl"] >= 0 else "#F87171"))
            self.portfolio_table.setItem(idx, 8, pnl_item)

            ret_item = SortableTableWidgetItem(f"{row['return_pct']:+.2f}%")
            ret_item.setData(SortableTableWidgetItem.SORT_ROLE, float(row["return_pct"]))
            ret_item.setForeground(QColor("#34D399" if row["return_pct"] >= 0 else "#F87171"))
            self.portfolio_table.setItem(idx, 9, ret_item)

            self.portfolio_table.setCellWidget(idx, 10, self._build_note_cell(row))
            self.portfolio_table.setCellWidget(idx, 11, self._build_action_cell(row))

        # Holdings count intentionally not shown to reduce visual clutter.
        self.portfolio_table.setSortingEnabled(True)
        self.portfolio_table.sortItems(6, Qt.DescendingOrder)

    def _build_note_cell(self, row: dict) -> QWidget:
        wrap = QWidget()
        layout = QHBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        btn = QToolButton()
        btn.setObjectName("inlineDocBtn")
        btn.setIcon(self.style().standardIcon(QStyle.SP_FileIcon))
        note_text = row.get("note") or "No journal note available."
        btn.setToolTip(note_text)
        btn.clicked.connect(lambda _=False, r=row: self._edit_note_for_row(r))
        layout.addWidget(btn, 0, Qt.AlignCenter)
        return wrap

    def _build_action_cell(self, row: dict) -> QWidget:
        wrap = QWidget()
        layout = QHBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        btn = QToolButton()
        btn.setObjectName("inlineActionBtn")
        btn.setText("⋮")
        btn.setPopupMode(QToolButton.InstantPopup)

        menu = QMenu(btn)
        self._apply_active_theme(menu)
        action_view = QAction("View Transactions", btn)
        action_view.triggered.connect(lambda: self._open_transactions_for_row(row))
        action_sell = QAction("Sell", btn)
        action_sell.triggered.connect(lambda: self._open_sell_for_row(row))
        menu.addAction(action_view)
        menu.addAction(action_sell)
        btn.setMenu(menu)

        layout.addWidget(btn, 0, Qt.AlignCenter)
        return wrap

    def _build_weight_cell(self, weight_pct: float) -> QWidget:
        wrap = QWidget()
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(2)
        lbl = QLabel(f"{weight_pct:.1f}%")
        lbl.setObjectName("weightPctLabel")
        bar = WeightBar(weight_pct)
        layout.addWidget(lbl)
        layout.addWidget(bar)
        return wrap

    def _open_selected_transactions(self, index):
        row = index.row()
        marker = self.portfolio_table.item(row, 0)
        stock_id = marker.data(Qt.UserRole) if marker else None
        symbol = marker.data(Qt.UserRole + 1) if marker else ""
        if not stock_id:
            return
        self._portfolio_helper.current_user_id = self.current_user_id
        self._portfolio_helper.open_stock_transactions(stock_id, symbol)

    def _open_transactions_for_row(self, row: dict):
        self._portfolio_helper.current_user_id = self.current_user_id
        self._portfolio_helper.open_stock_transactions(row["stock_id"], row["symbol"])

    def _open_sell_for_row(self, row: dict):
        self._portfolio_helper.current_user_id = self.current_user_id
        self._portfolio_helper.open_sell_dialog(row["stock_id"], row["symbol"], int(row.get("qty") or 0))
        if self.current_user_id:
            self.load_dashboard(self.current_user_id, use_live_quotes=False)

    def _edit_note_for_row(self, row: dict):
        txs = self.db.get_stock_transactions(row["stock_id"]) or []
        target_tx = txs[0] if txs else None
        for tx in txs:
            if (tx.get("thesis") or "").strip():
                target_tx = tx
                break
        if not target_tx:
            QMessageBox.information(self, "Journal", "No transactions found for this stock.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Journal Note - {row['symbol']}")
        dialog.resize(640, 360)
        self._apply_active_theme(dialog)
        root = QVBoxLayout(dialog)

        editor = QTextEdit()
        editor.setPlainText((target_tx.get("thesis") or "").strip())
        root.addWidget(editor)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        root.addWidget(buttons)

        if dialog.exec_() != QDialog.Accepted:
            return

        self.db.update_transaction(target_tx["transaction_id"], thesis=editor.toPlainText().strip())
        if self.current_user_id:
            self.load_dashboard(self.current_user_id, use_live_quotes=False)

    def add_transaction(self):
        if not self.current_user_id:
            return
        dialog = AddStockDialog(self.db, self.stock_service, self.current_user_id, parent=self)
        if dialog.exec_():
            self.load_dashboard(self.current_user_id, use_live_quotes=False)

    def _apply_depth_effects(self):
        cfg = self._panel_shadow_preset()
        for panel in (self.chart_panel, self.snapshot_panel, self.portfolio_panel):
            effect = QGraphicsDropShadowEffect()
            effect.setBlurRadius(cfg["blur"])
            effect.setOffset(0, cfg["offset"])
            effect.setColor(QColor(0, 0, 0, cfg["alpha"]))
            panel.setGraphicsEffect(effect)

    @staticmethod
    def _panel_shadow_preset():
        mapping = {
            "subtle": {"blur": 16, "offset": 3, "alpha": 75},
            "medium": {"blur": 26, "offset": 5, "alpha": 110},
            "bold": {"blur": 36, "offset": 8, "alpha": 145},
        }
        return mapping.get(config.UI_GLOW_PRESET, mapping["medium"])

    def _apply_active_theme(self, widget: QWidget):
        win = self.window() if hasattr(self, "window") else None
        if win and hasattr(win, "styleSheet"):
            widget.setStyleSheet(win.styleSheet())

    @staticmethod
    def _date_sort_key(date_text: str) -> int:
        raw = (date_text or "").strip()
        if not raw or raw == "-":
            return 0
        try:
            return int(datetime.strptime(raw, "%Y-%m-%d").strftime("%Y%m%d"))
        except Exception:
            return 0

    def _render_industry_allocation(self, rows: list):
        allocations = {}
        for row in rows:
            bucket = (row.get("industry") or "Unknown").strip() or "Unknown"
            allocations[bucket] = allocations.get(bucket, 0.0) + float(row.get("investment") or 0.0)

        self.industry_donut.set_allocations(allocations)

        while self.industry_legend_layout.count():
            item = self.industry_legend_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        total = float(sum(allocations.values()))
        if total <= 0:
            label = QLabel("No industry allocation")
            label.setObjectName("sectorLegend")
            self.industry_legend_layout.addWidget(label)
            self.industry_legend_layout.addStretch()
            return

        for idx, (name, value) in enumerate(sorted(allocations.items(), key=lambda x: x[1], reverse=True)[:6]):
            pct = (value / total) * 100.0
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(6)
            dot = QLabel()
            color = DonutAllocationWidget._colors[idx % len(DonutAllocationWidget._colors)]
            dot.setFixedSize(9, 9)
            dot.setStyleSheet(
                f"background: {color.name()}; border-radius: 4px; border: 1px solid rgba(255,255,255,0.2);"
            )
            txt = QLabel(f"{name}  {pct:.1f}%")
            txt.setObjectName("sectorLegend")
            row_layout.addWidget(dot)
            row_layout.addWidget(txt)
            row_layout.addStretch()
            self.industry_legend_layout.addWidget(row_widget)
        self.industry_legend_layout.addStretch()
