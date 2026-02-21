"""
Portfolio View
Displays user's stock portfolio with P&L calculations
"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QTableWidget, QTableWidgetItem, QLabel, QHeaderView,
                             QMessageBox, QDialog, QFrame, QToolButton, QMenu, QAction, QProgressBar)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor
from database.db_manager import DatabaseManager
from services.stock_service import StockService
from ui.add_stock_dialog import AddStockDialog

class PortfolioView(QWidget):
    """Portfolio view widget"""
    
    def __init__(self, db: DatabaseManager, stock_service: StockService):
        """Init.

        Args:
            db: Input parameter.
            stock_service: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        super().__init__()
        self.db = db
        self.stock_service = stock_service
        self.current_user_id = None
        
        self.setup_ui()
    
    def setup_ui(self):
        """Setup UI"""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Header with Add Transaction button
        header = QHBoxLayout()
        
        title = QLabel("My Portfolio")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        header.addWidget(title)
        
        header.addStretch()
        
        add_btn = QPushButton("+ Add Transaction")
        add_btn.clicked.connect(self.add_stock)
        add_btn.setStyleSheet("font-weight: 700;")
        header.addWidget(add_btn)
        
        layout.addLayout(header)

        # Portfolio summary
        self.summary_label = QLabel()
        layout.addWidget(self.summary_label)
        
        # Portfolio table
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            'Asset', 'Quantity', 'Avg Price', 'Current Price', 'Investment', 'Weight', 'P&L', 'Actions'
        ])
        
        # Set column widths
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.verticalHeader().setDefaultSectionSize(58)
        self.table.doubleClicked.connect(self.view_stock_details)
        
        layout.addWidget(self.table)
        
        # Instructions
        instructions = QLabel("Tip: Hover a stock to preview notes. Double-click for full transaction details.")
        layout.addWidget(instructions)

    @staticmethod
    def _build_kpi_card(title: str):
        """Build kpi card.

        Args:
            title: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        card = QFrame()
        card.setObjectName("kpiCard")
        inner = QVBoxLayout()
        title_lbl = QLabel(title)
        title_lbl.setObjectName("kpiTitle")
        value_lbl = QLabel("₹0.00")
        value_lbl.setObjectName("kpiValue")
        card._value_label = value_lbl
        inner.addWidget(title_lbl)
        inner.addWidget(value_lbl)
        card.setLayout(inner)
        return card
    
    def load_portfolio(self, user_id: int, use_live_quotes: bool = True):
        """Load portfolio for user"""
        self.current_user_id = user_id
        self.table.setRowCount(0)
        
        # Get portfolio
        portfolio = self.db.get_portfolio_summary(user_id)
        
        if not portfolio:
            self.summary_label.setText("No stocks in portfolio. Click '+ Add Transaction' to get started!")
            return
        
        # Calculate totals + resolve prices first (needed for weightage accuracy)
        total_invested = 0.0
        total_current_value = 0.0
        total_daily_pnl = 0.0
        total_weekly_pnl = 0.0
        computed_rows = []

        for stock in portfolio:
            symbol = stock['symbol']
            exchange = stock.get('exchange')
            quantity = stock['quantity']
            avg_price = stock['avg_price']

            quote_symbol = self.stock_service.to_quote_symbol(symbol, exchange=exchange)
            current_price = self.db.get_latest_price(stock['stock_id']) or avg_price
            if use_live_quotes:
                live_price = self.stock_service.get_current_price(quote_symbol)
                if live_price is not None:
                    current_price = live_price
                    self.db.save_price(stock['stock_id'], current_price)

            investment = avg_price * quantity
            current_value = current_price * quantity
            pnl = current_value - investment
            daily_pnl = self._compute_daily_pnl(quote_symbol, current_price, quantity) if use_live_quotes else 0.0
            weekly_pnl = self._compute_weekly_pnl(quote_symbol, current_price, quantity) if use_live_quotes else 0.0
            total_invested += investment
            total_current_value += current_value

            total_daily_pnl += daily_pnl
            total_weekly_pnl += weekly_pnl

            computed_rows.append({
                "stock": stock,
                "symbol": symbol,
                "quantity": quantity,
                "avg_price": avg_price,
                "current_price": current_price,
                "investment": investment,
                "current_value": current_value,
                "pnl": pnl,
            })

        # Populate table
        for i, row in enumerate(computed_rows):
            self.table.insertRow(i)
            stock = row["stock"]
            symbol = row["symbol"]
            quantity = row["quantity"]
            avg_price = row["avg_price"]
            current_price = row["current_price"]
            investment = row["investment"]
            current_value = row["current_value"]
            pnl = row["pnl"]
            pnl_pct = (pnl / investment * 100) if investment > 0 else 0.0

            asset_widget = self._build_asset_cell(symbol, stock['company_name'])
            self.table.setCellWidget(i, 0, asset_widget)
            qty_item = QTableWidgetItem(str(int(quantity)))
            qty_item.setData(Qt.UserRole, stock['stock_id'])
            qty_item.setData(Qt.UserRole + 1, symbol)
            self.table.setItem(i, 1, qty_item)
            self.table.setItem(i, 2, QTableWidgetItem(f"₹{avg_price:.2f}"))
            self.table.setItem(i, 3, QTableWidgetItem(f"₹{current_price:.2f}"))
            self.table.setItem(i, 4, QTableWidgetItem(f"₹{investment:,.2f}"))

            # Investment note preview (latest non-empty thesis)
            transactions = self.db.get_stock_transactions(stock['stock_id'])
            theses = [t['thesis'].strip() for t in transactions if t.get('thesis') and t['thesis'].strip()]
            note_preview = theses[0] if theses else "No investment notes added."
            tooltip_text = f"Investment Note:\n{note_preview}"
            asset_widget.setToolTip(tooltip_text)

            weight_pct = (current_value / total_current_value * 100) if total_current_value > 0 else 0.0
            self.table.setCellWidget(i, 5, self._build_weight_cell(weight_pct))
            
            # P&L with color
            pnl_item = QTableWidgetItem(f"₹{pnl:,.2f} ({pnl_pct:+.2f}%)")
            if pnl > 0:
                pnl_item.setForeground(QColor('#4CAF50'))
            elif pnl < 0:
                pnl_item.setForeground(QColor('#F44336'))
            self.table.setItem(i, 6, pnl_item)

            self.table.setCellWidget(i, 7, self._build_actions_cell(stock['stock_id'], symbol))
        
        # Update summary
        total_pnl = total_current_value - total_invested
        total_pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0
        
        summary_color = '#4CAF50' if total_pnl >= 0 else '#F44336'
        
        self.summary_label.setText(f"""
            <b>Portfolio Summary:</b> &nbsp;&nbsp;
            Total Invested: ₹{total_invested:,.2f} &nbsp;|&nbsp;
            Current Value: ₹{total_current_value:,.2f} &nbsp;|&nbsp;
            <span style='color: {summary_color};'>
            P&L: ₹{total_pnl:,.2f} ({total_pnl_pct:+.2f}%)
            </span>
        """)

    def _compute_daily_pnl(self, quote_symbol: str, current_price: float, quantity: int) -> float:
        """Compute daily pnl.

        Args:
            quote_symbol: Input parameter.
            current_price: Input parameter.
            quantity: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        info = self.stock_service.get_stock_info(quote_symbol) or {}
        prev_close = info.get("previous_close") or info.get("current_price")
        try:
            prev_close = float(prev_close)
        except Exception:
            return 0.0
        return (current_price - prev_close) * quantity

    def _compute_weekly_pnl(self, quote_symbol: str, current_price: float, quantity: int) -> float:
        """Compute weekly pnl.

        Args:
            quote_symbol: Input parameter.
            current_price: Input parameter.
            quantity: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        history = self.stock_service.get_historical_prices(quote_symbol, period="5d")
        if not history or not history.get("prices"):
            return 0.0
        base = history["prices"][0]
        try:
            base = float(base)
        except Exception:
            return 0.0
        return (current_price - base) * quantity

    @staticmethod
    def _set_kpi_value(card: QFrame, value: float):
        """Set kpi value.

        Args:
            card: Input parameter.
            value: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        label = getattr(card, "_value_label", None)
        if not label:
            return
        color = "#2E7D32" if value >= 0 else "#C62828"
        label.setText(f"₹{value:,.2f}")
        label.setStyleSheet(f"color: {color};")
    
    def add_stock(self):
        """Open add stock dialog"""
        if not self.current_user_id:
            return
        
        dialog = AddStockDialog(self.db, self.stock_service, self.current_user_id, parent=self)
        if dialog.exec_():
            # Reload portfolio
            self.load_portfolio(self.current_user_id)
    
    def view_stock_details(self, index):
        """Open transaction manager when row is double-clicked."""
        row = index.row()
        marker = self.table.item(row, 1)
        stock_id = marker.data(Qt.UserRole) if marker else None
        symbol = marker.data(Qt.UserRole + 1) if marker else ""
        if not stock_id:
            return
        self.open_stock_transactions(stock_id, symbol)

    @staticmethod
    def _build_asset_cell(symbol: str, company_name: str) -> QWidget:
        """Build asset cell.

        Args:
            symbol: Input parameter.
            company_name: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        widget = QWidget()
        row = QHBoxLayout()
        row.setContentsMargins(6, 2, 6, 2)
        row.setSpacing(8)
        initials = (symbol or "?")[:2].upper()
        bubble = QLabel(initials)
        bubble.setAlignment(Qt.AlignCenter)
        bubble.setFixedSize(26, 26)
        bubble.setStyleSheet(
            "background:#2D5A88;color:white;border-radius:13px;font-weight:700;font-size:11px;"
        )
        text_col = QVBoxLayout()
        sym_lbl = QLabel(symbol)
        sym_lbl.setStyleSheet("font-weight:600;")
        cmp_lbl = QLabel(company_name)
        cmp_lbl.setStyleSheet("font-size:11px;color:#7A8794;")
        text_col.addWidget(sym_lbl)
        text_col.addWidget(cmp_lbl)
        row.addWidget(bubble)
        row.addLayout(text_col)
        row.addStretch()
        widget.setLayout(row)
        return widget

    @staticmethod
    def _build_weight_cell(weight_pct: float) -> QWidget:
        """Build weight cell.

        Args:
            weight_pct: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(4)
        pct_label = QLabel(f"{weight_pct:.1f}%")
        pct_label.setStyleSheet("font-size:12px;font-weight:600;")
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(int(max(0.0, min(weight_pct, 100.0))))
        bar.setTextVisible(False)
        bar.setFixedHeight(8)
        bar.setStyleSheet(
            "QProgressBar{border:0;background:#E6ECF2;border-radius:3px;}"
            "QProgressBar::chunk{background:#3D5AFE;border-radius:3px;}"
        )
        layout.addWidget(pct_label)
        layout.addWidget(bar)
        widget.setLayout(layout)
        return widget

    def _build_actions_cell(self, stock_id: int, symbol: str) -> QWidget:
        """Build actions cell.

        Args:
            stock_id: Input parameter.
            symbol: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        container = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(6, 0, 6, 0)
        menu_btn = QToolButton()
        menu_btn.setText("⋮")
        menu_btn.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(menu_btn)
        open_action = QAction("View Transactions", menu_btn)
        open_action.triggered.connect(lambda: self.open_stock_transactions(stock_id, symbol))
        delete_action = QAction("Delete Stock", menu_btn)
        delete_action.triggered.connect(lambda: self.delete_stock_position(stock_id, symbol))
        menu.addAction(open_action)
        menu.addSeparator()
        menu.addAction(delete_action)
        menu_btn.setMenu(menu)
        layout.addWidget(menu_btn)
        layout.addStretch()
        container.setLayout(layout)
        return container

    def open_stock_transactions(self, stock_id, symbol):
        """View stock transactions with edit/delete options."""
        transactions = self.db.get_stock_transactions(stock_id)
        
        # Create transaction list dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(f"{symbol} - Transactions")
        dialog.setMinimumSize(800, 400)
        self._apply_active_theme(dialog)
        
        layout = QVBoxLayout()
        
        # Transaction table
        table = QTableWidget()
        table.setColumnCount(9)
        table.setHorizontalHeaderLabels([
            'Date', 'Type', 'Qty', 'Price', 'Horizon', 'Target', 'Note', 'Actions', 'ID'
        ])
        table.hideColumn(8)  # Hide ID column
        
        for i, trans in enumerate(transactions):
            table.insertRow(i)
            table.setItem(i, 0, QTableWidgetItem(trans['transaction_date']))
            table.setItem(i, 1, QTableWidgetItem(trans['transaction_type']))
            table.setItem(i, 2, QTableWidgetItem(str(trans['quantity'])))
            table.setItem(i, 3, QTableWidgetItem(f"₹{trans['price_per_share']:.2f}"))
            table.setItem(i, 4, QTableWidgetItem(trans['investment_horizon']))
            
            target = f"₹{trans['target_price']:.2f}" if trans['target_price'] else 'N/A'
            table.setItem(i, 5, QTableWidgetItem(target))

            note_text = (trans['thesis'] or '').strip() or 'N/A'
            note_item = QTableWidgetItem(note_text if len(note_text) <= 80 else f"{note_text[:77]}...")
            note_item.setToolTip(note_text)
            table.setItem(i, 6, note_item)
            
            # Action buttons
            actions = QWidget()
            actions_layout = QHBoxLayout()
            actions_layout.setContentsMargins(5, 2, 5, 2)
            
            edit_btn = QPushButton("Edit")
            edit_btn.clicked.connect(
                lambda checked, t_id=trans['transaction_id']: 
                self.edit_transaction(t_id, dialog)
            )
            actions_layout.addWidget(edit_btn)
            
            delete_btn = QPushButton("Delete")
            delete_btn.setStyleSheet("background-color: #f44336; color: white;")
            delete_btn.clicked.connect(
                lambda checked, t_id=trans['transaction_id']: 
                self.delete_transaction(t_id, dialog)
            )
            actions_layout.addWidget(delete_btn)
            
            actions.setLayout(actions_layout)
            table.setCellWidget(i, 7, actions)
            
            # Store transaction ID
            table.setItem(i, 8, QTableWidgetItem(str(trans['transaction_id'])))
        
        layout.addWidget(table)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        
        dialog.setLayout(layout)
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

    def edit_transaction(self, transaction_id, parent_dialog):
        """Edit a transaction."""
        from ui.edit_transaction_dialog import EditTransactionDialog
        
        dialog = EditTransactionDialog(self.db, transaction_id, self)
        if dialog.exec_():
            # Reload portfolio
            self.load_portfolio(self.current_user_id)
            parent_dialog.accept()

    def delete_transaction(self, transaction_id, parent_dialog):
        """Delete a transaction with confirmation."""
        reply = QMessageBox.question(
            self,
            'Confirm Delete',
            'Are you sure you want to delete this transaction?\n\nThis cannot be undone.',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            if self.db.delete_transaction(transaction_id):
                QMessageBox.information(self, "Success", 
                                    "Transaction deleted successfully!")
                self.load_portfolio(self.current_user_id)
                parent_dialog.accept()
            else:
                QMessageBox.critical(self, "Error", 
                                "Failed to delete transaction")

    def delete_stock_position(self, stock_id, symbol):
        """Delete stock and its related portfolio records."""
        reply = QMessageBox.question(
            self,
            'Delete Stock Position',
            (
                f"Delete {symbol} from portfolio?\n\n"
                "This will remove all related transactions, alerts, and price history."
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            if self.db.delete_stock(stock_id):
                QMessageBox.information(self, "Success", f"{symbol} deleted from portfolio.")
                self.load_portfolio(self.current_user_id)
            else:
                QMessageBox.critical(self, "Error", "Failed to delete stock position.")
