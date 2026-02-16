"""
Portfolio View
Displays user's stock portfolio with P&L calculations
"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QTableWidget, QTableWidgetItem, QLabel, QHeaderView,
                             QMessageBox, QDialog, QFrame)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor
from database.db_manager import DatabaseManager
from services.stock_service import StockService
from ui.add_stock_dialog import AddStockDialog

class PortfolioView(QWidget):
    """Portfolio view widget"""
    
    def __init__(self, db: DatabaseManager, stock_service: StockService):
        super().__init__()
        self.db = db
        self.stock_service = stock_service
        self.current_user_id = None
        
        self.setup_ui()
    
    def setup_ui(self):
        """Setup UI"""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Header with Add Stock button
        header = QHBoxLayout()
        
        title = QLabel("My Portfolio")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        header.addWidget(title)
        
        header.addStretch()
        
        add_btn = QPushButton("+ Add Stock")
        add_btn.clicked.connect(self.add_stock)
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        header.addWidget(add_btn)
        
        layout.addLayout(header)

        # KPI cards
        self.kpi_layout = QHBoxLayout()
        self.daily_kpi = self._build_kpi_card("Daily Gain/Loss")
        self.weekly_kpi = self._build_kpi_card("Weekly Gain/Loss")
        self.overall_kpi = self._build_kpi_card("Overall Gain/Loss")
        self.kpi_layout.addWidget(self.daily_kpi)
        self.kpi_layout.addWidget(self.weekly_kpi)
        self.kpi_layout.addWidget(self.overall_kpi)
        layout.addLayout(self.kpi_layout)

        # Portfolio summary
        self.summary_label = QLabel()
        layout.addWidget(self.summary_label)
        
        # Portfolio table
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            'Symbol', 'Company', 'Quantity', 'Avg Price', 
            'Current Price', 'Investment', 'Current Value', 'P&L', 'Actions'
        ])
        
        # Set column widths
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        
        self.table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #ddd;
                border-radius: 4px;
            }
            QHeaderView::section {
                background-color: #f0f0f0;
                padding: 8px;
                border: none;
                font-weight: bold;
            }
            QTableWidget::item {
                padding: 8px;
            }
        """)
        
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.doubleClicked.connect(self.view_stock_details)
        
        layout.addWidget(self.table)
        
        # Instructions
        instructions = QLabel("Tip: Hover a stock to preview notes. Double-click for full transaction details.")
        layout.addWidget(instructions)

    @staticmethod
    def _build_kpi_card(title: str):
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
    
    def load_portfolio(self, user_id: int):
        """Load portfolio for user"""
        self.current_user_id = user_id
        self.table.setRowCount(0)
        
        # Get portfolio
        portfolio = self.db.get_portfolio_summary(user_id)
        
        if not portfolio:
            self.summary_label.setText("No stocks in portfolio. Click '+ Add Stock' to get started!")
            return
        
        # Calculate totals
        total_invested = 0
        total_current_value = 0
        total_daily_pnl = 0
        total_weekly_pnl = 0
        
        # Populate table
        for i, stock in enumerate(portfolio):
            self.table.insertRow(i)
            
            symbol = stock['symbol']
            exchange = stock.get('exchange')
            quantity = stock['quantity']
            avg_price = stock['avg_price']
            
            # Get current price
            quote_symbol = self.stock_service.to_quote_symbol(symbol, exchange=exchange)
            current_price = self.stock_service.get_current_price(quote_symbol)
            
            if current_price is None:
                current_price = avg_price  # Fallback
            else:
                self.db.save_price(stock['stock_id'], current_price)
            
            # Calculate values
            investment = avg_price * quantity
            current_value = current_price * quantity
            pnl = current_value - investment
            pnl_pct = (pnl / investment * 100) if investment > 0 else 0

            daily_pnl = self._compute_daily_pnl(quote_symbol, current_price, quantity)
            weekly_pnl = self._compute_weekly_pnl(quote_symbol, current_price, quantity)
            total_daily_pnl += daily_pnl
            total_weekly_pnl += weekly_pnl
            
            total_invested += investment
            total_current_value += current_value
            
            # Add to table
            self.table.setItem(i, 0, QTableWidgetItem(symbol))
            self.table.setItem(i, 1, QTableWidgetItem(stock['company_name']))
            self.table.setItem(i, 2, QTableWidgetItem(str(int(quantity))))
            self.table.setItem(i, 3, QTableWidgetItem(f"₹{avg_price:.2f}"))
            self.table.setItem(i, 4, QTableWidgetItem(f"₹{current_price:.2f}"))
            self.table.setItem(i, 5, QTableWidgetItem(f"₹{investment:,.2f}"))
            self.table.setItem(i, 6, QTableWidgetItem(f"₹{current_value:,.2f}"))

            # Investment note preview (latest non-empty thesis)
            transactions = self.db.get_stock_transactions(stock['stock_id'])
            theses = [t['thesis'].strip() for t in transactions if t.get('thesis') and t['thesis'].strip()]
            note_preview = theses[0] if theses else "No investment notes added."
            tooltip_text = f"Investment Note:\n{note_preview}"
            self.table.item(i, 0).setToolTip(tooltip_text)
            self.table.item(i, 1).setToolTip(tooltip_text)
            
            # P&L with color
            pnl_item = QTableWidgetItem(f"₹{pnl:,.2f} ({pnl_pct:+.2f}%)")
            if pnl > 0:
                pnl_item.setForeground(QColor('#4CAF50'))
            elif pnl < 0:
                pnl_item.setForeground(QColor('#F44336'))
            self.table.setItem(i, 7, pnl_item)

            # Row actions: edit transactions and delete stock
            actions_widget = QWidget()
            actions_layout = QHBoxLayout()
            actions_layout.setContentsMargins(5, 2, 5, 2)

            edit_btn = QPushButton("Edit")
            edit_btn.clicked.connect(
                lambda checked, sid=stock['stock_id'], sym=symbol: self.open_stock_transactions(sid, sym)
            )
            actions_layout.addWidget(edit_btn)

            delete_btn = QPushButton("Delete")
            delete_btn.setStyleSheet("background-color: #f44336; color: white;")
            delete_btn.clicked.connect(
                lambda checked, sid=stock['stock_id'], sym=symbol: self.delete_stock_position(sid, sym)
            )
            actions_layout.addWidget(delete_btn)

            actions_widget.setLayout(actions_layout)
            self.table.setCellWidget(i, 8, actions_widget)
            
            # Store stock_id in row
            self.table.item(i, 0).setData(Qt.UserRole, stock['stock_id'])
        
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
        self._set_kpi_value(self.daily_kpi, total_daily_pnl)
        self._set_kpi_value(self.weekly_kpi, total_weekly_pnl)
        self._set_kpi_value(self.overall_kpi, total_pnl)

    def _compute_daily_pnl(self, quote_symbol: str, current_price: float, quantity: int) -> float:
        info = self.stock_service.get_stock_info(quote_symbol) or {}
        prev_close = info.get("previous_close") or info.get("current_price")
        try:
            prev_close = float(prev_close)
        except Exception:
            return 0.0
        return (current_price - prev_close) * quantity

    def _compute_weekly_pnl(self, quote_symbol: str, current_price: float, quantity: int) -> float:
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
        stock_id = self.table.item(row, 0).data(Qt.UserRole)
        symbol = self.table.item(row, 0).text()
        self.open_stock_transactions(stock_id, symbol)

    def open_stock_transactions(self, stock_id, symbol):
        """View stock transactions with edit/delete options."""
        transactions = self.db.get_stock_transactions(stock_id)
        
        # Create transaction list dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(f"{symbol} - Transactions")
        dialog.setMinimumSize(800, 400)
        
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
