"""
Add Stock Dialog
Dialog for adding stocks and transactions to portfolio
"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QComboBox, QTextEdit,
                             QDateEdit, QSpinBox, QDoubleSpinBox, QMessageBox,
                             QFormLayout, QGroupBox, QCompleter)
from PyQt5.QtCore import Qt, QDate, QTimer, QStringListModel
from database.db_manager import DatabaseManager
from services.stock_service import StockService
from services.symbol_master_service import SymbolMasterService

class AddStockDialog(QDialog):
    """Dialog for adding a stock and its first transaction"""
    
    def __init__(self, db: DatabaseManager, stock_service: StockService, 
                 user_id: int, parent=None):
        super().__init__(parent)
        self.db = db
        self.stock_service = stock_service
        self.symbol_master_service = SymbolMasterService(db)
        self.user_id = user_id
        self.last_stock_info = None
        self.last_symbol = ""
        self.last_symbol_master = None
        self.pending_symbol = ""
        
        # Debounce symbol lookups to avoid API calls on every keystroke.
        self.lookup_timer = QTimer(self)
        self.lookup_timer.setSingleShot(True)
        self.lookup_timer.setInterval(500)
        self.lookup_timer.timeout.connect(self.fetch_symbol_info)

        self.symbol_suggestions_model = QStringListModel(self)
        self.symbol_completer = QCompleter(self.symbol_suggestions_model, self)
        self.symbol_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.symbol_completer.setFilterMode(Qt.MatchContains)
        
        self.setup_ui()
        self._apply_active_theme()
    
    def setup_ui(self):
        """Setup UI"""
        self.setWindowTitle("Add Stock to Portfolio")
        self.setMinimumWidth(500)
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Stock details group
        stock_group = QGroupBox("Stock Details")
        stock_layout = QFormLayout()
        stock_group.setLayout(stock_layout)
        
        # Symbol
        self.symbol_input = QLineEdit()
        self.symbol_input.setPlaceholderText("e.g., RELIANCE.NS, AAPL, TCS.NS")
        self.symbol_input.setCompleter(self.symbol_completer)
        self.symbol_input.textChanged.connect(self.on_symbol_changed)
        stock_layout.addRow("Symbol:", self.symbol_input)
        
        # Company name (auto-filled)
        self.company_name_label = QLabel("Enter symbol to fetch company name")
        self.company_name_label.setStyleSheet("color: #666;")
        stock_layout.addRow("Company:", self.company_name_label)
        
        layout.addWidget(stock_group)
        
        # Transaction details group
        trans_group = QGroupBox("Transaction Details")
        trans_layout = QFormLayout()
        trans_group.setLayout(trans_layout)
        
        # Transaction type
        self.transaction_type = QComboBox()
        self.transaction_type.addItems(['BUY', 'SELL'])
        trans_layout.addRow("Type:", self.transaction_type)
        
        # Quantity
        self.quantity_input = QSpinBox()
        self.quantity_input.setMinimum(1)
        self.quantity_input.setMaximum(1000000)
        self.quantity_input.setValue(10)
        trans_layout.addRow("Quantity:", self.quantity_input)
        
        # Price per share
        self.price_input = QDoubleSpinBox()
        self.price_input.setMinimum(0.01)
        self.price_input.setMaximum(1000000.0)
        self.price_input.setDecimals(2)
        self.price_input.setValue(100.0)
        self.price_input.setPrefix("₹ ")
        trans_layout.addRow("Price per Share:", self.price_input)
        
        # Date
        self.date_input = QDateEdit()
        self.date_input.setDate(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        trans_layout.addRow("Date:", self.date_input)
        
        layout.addWidget(trans_group)
        
        # Investment strategy group
        strategy_group = QGroupBox("Investment Strategy")
        strategy_layout = QFormLayout()
        strategy_group.setLayout(strategy_layout)
        
        # Investment horizon
        self.horizon_input = QComboBox()
        self.horizon_input.addItems(['SHORT', 'MEDIUM', 'LONG'])
        self.horizon_input.setCurrentText('LONG')
        strategy_layout.addRow("Investment Horizon:", self.horizon_input)
        
        # Target price
        self.target_price_input = QDoubleSpinBox()
        self.target_price_input.setMinimum(0.0)
        self.target_price_input.setMaximum(1000000.0)
        self.target_price_input.setDecimals(2)
        self.target_price_input.setValue(150.0)
        self.target_price_input.setPrefix("₹ ")
        strategy_layout.addRow("Target Price:", self.target_price_input)
        
        # Investment thesis
        self.thesis_input = QTextEdit()
        self.thesis_input.setPlaceholderText(
            "Why are you buying this stock?\n\n"
            "Example:\n"
            "- Strong fundamentals with 20% YoY revenue growth\n"
            "- Expanding into new markets\n"
            "- Undervalued compared to peers (P/E: 15 vs industry avg 25)"
        )
        self.thesis_input.setMaximumHeight(120)
        strategy_layout.addRow("Investment Thesis:", self.thesis_input)
        
        layout.addWidget(strategy_group)
        
        # Buttons
        buttons = QHBoxLayout()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)
        
        add_btn = QPushButton("Add to Portfolio")
        add_btn.clicked.connect(self.add_stock)
        add_btn.setStyleSheet("font-weight: 700;")
        buttons.addWidget(add_btn)
        
        layout.addLayout(buttons)

    def _apply_active_theme(self):
        """Inherit currently active theme from main window."""
        win = self.parent().window() if self.parent() else None
        if win and hasattr(win, "styleSheet"):
            self.setStyleSheet(win.styleSheet())
    
    def on_symbol_changed(self, text):
        """Debounce symbol lookup when input changes."""
        symbol = self._extract_symbol(text)
        self.pending_symbol = symbol
        self.last_stock_info = None
        self.last_symbol = ""
        self.last_symbol_master = None

        self._refresh_symbol_suggestions(text)
        
        if len(symbol) < 2:
            self.lookup_timer.stop()
            self.company_name_label.setText("Enter symbol to fetch company name")
            self.company_name_label.setStyleSheet("color: #666;")
            return

        symbol_row = self.db.get_symbol_by_symbol(symbol)
        if symbol_row:
            self.last_symbol_master = symbol_row
            self.company_name_label.setText(f"{symbol_row['company_name']} (local)")
            self.company_name_label.setStyleSheet("color: #1565C0;")
        else:
            self.company_name_label.setText("Checking symbol...")
            self.company_name_label.setStyleSheet("color: #666;")

        self.lookup_timer.start()

    def fetch_symbol_info(self):
        """Fetch stock info after debounce interval."""
        symbol = self.pending_symbol
        if len(symbol) < 2:
            return

        symbol_row = self.last_symbol_master or self.db.get_symbol_by_symbol(symbol)
        exchange = symbol_row['exchange'] if symbol_row else 'NSE'
        yahoo_symbol = self.symbol_master_service.resolve_yahoo_symbol(symbol, exchange)
        stock_info = self.stock_service.get_stock_info(yahoo_symbol)
        if stock_info:
            self.last_stock_info = stock_info
            self.last_symbol = symbol
            if symbol_row and symbol_row.get("quote_symbol_yahoo") != yahoo_symbol:
                self.db.upsert_symbol_master(
                    symbol=symbol_row['symbol'],
                    company_name=symbol_row['company_name'],
                    exchange=symbol_row['exchange'],
                    bse_code=symbol_row.get('bse_code'),
                    nse_code=symbol_row.get('nse_code'),
                    sector=symbol_row.get('sector'),
                    source='YAHOO_MAPPING',
                    quote_symbol_yahoo=yahoo_symbol
                )
            self.company_name_label.setText(stock_info['company_name'])
            self.company_name_label.setStyleSheet("color: #4CAF50;")
            
            # Auto-fill current price as purchase price
            if stock_info['current_price'] > 0:
                self.price_input.setValue(stock_info['current_price'])
                self.target_price_input.setValue(stock_info['current_price'] * 1.2)  # 20% target
        else:
            self.company_name_label.setText("❌ Stock not found. Check symbol.")
            self.company_name_label.setStyleSheet("color: #F44336;")
    
    def add_stock(self):
        """Add stock and transaction to database"""
        symbol = self._extract_symbol(self.symbol_input.text())
        
        if not symbol:
            QMessageBox.warning(self, "Error", "Please enter a stock symbol")
            return

        symbol_row = self.db.get_symbol_by_symbol(symbol)
        exchange = symbol_row['exchange'] if symbol_row else 'NSE'
        yahoo_symbol = self.symbol_master_service.resolve_yahoo_symbol(symbol, exchange)
        
        # Reuse debounced lookup result when possible to avoid duplicate API call.
        stock_info = self.last_stock_info if self.last_symbol == symbol else self.stock_service.get_stock_info(yahoo_symbol)
        if not stock_info:
            QMessageBox.warning(self, "Error", "Invalid stock symbol. Please check and try again.")
            return
        
        # Get form data
        company_name = symbol_row['company_name'] if symbol_row else stock_info['company_name']
        transaction_type = self.transaction_type.currentText()
        quantity = self.quantity_input.value()
        price = self.price_input.value()
        date = self.date_input.date().toString('yyyy-MM-dd')
        horizon = self.horizon_input.currentText()
        target_price = self.target_price_input.value()
        thesis = self.thesis_input.toPlainText().strip()
        
        try:
            # Add stock (or get existing)
            stock_id = self.db.add_stock(self.user_id, symbol, company_name, exchange)
            
            # Add transaction
            self.db.add_transaction(
                stock_id=stock_id,
                transaction_type=transaction_type,
                quantity=quantity,
                price_per_share=price,
                transaction_date=date,
                investment_horizon=horizon,
                target_price=target_price if target_price > 0 else None,
                thesis=thesis if thesis else None
            )
            
            # Save current price
            if stock_info['current_price'] > 0:
                self.db.save_price(stock_id, stock_info['current_price'])
            
            QMessageBox.information(
                self, 
                "Success", 
                f"{symbol} added to your portfolio successfully!"
            )
            
            self.accept()
        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to add stock: {str(e)}")

    def _refresh_symbol_suggestions(self, raw_text: str):
        """Refresh input suggestions from symbol master."""
        query = (raw_text or "").strip()
        if len(query) < 2:
            self.symbol_suggestions_model.setStringList([])
            return

        matches = self.db.search_symbol_master(query=query, limit=20)
        suggestions = [f"{m['symbol']} - {m['company_name']}" for m in matches]
        self.symbol_suggestions_model.setStringList(suggestions)

    @staticmethod
    def _extract_symbol(text: str) -> str:
        """Extract canonical symbol from input/completer text."""
        raw = (text or "").strip().upper()
        if " - " in raw:
            return raw.split(" - ", 1)[0].strip()
        return raw
