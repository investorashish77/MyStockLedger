from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
                             QLineEdit, QPushButton, QComboBox, QTextEdit,
                             QDateEdit, QSpinBox, QDoubleSpinBox, QMessageBox)
from PyQt5.QtCore import QDate
from database.db_manager import DatabaseManager

class EditTransactionDialog(QDialog):
    '''Dialog for editing an existing transaction'''
    
    def __init__(self, db: DatabaseManager, transaction_id: int, parent=None):
        """Init.

        Args:
            db: Input parameter.
            transaction_id: Input parameter.
            parent: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        super().__init__(parent)
        self.db = db
        self.transaction_id = transaction_id
        self.transaction_data = None
        
        self.setup_ui()
        self._apply_active_theme()
        self.load_transaction_data()
    
    def setup_ui(self):
        '''Setup the UI'''
        self.setWindowTitle("Edit Transaction")
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout()
        form = QFormLayout()
        
        # Transaction type
        self.type_combo = QComboBox()
        self.type_combo.addItems(['BUY', 'SELL'])
        form.addRow("Type:", self.type_combo)
        
        # Quantity
        self.quantity_spin = QSpinBox()
        self.quantity_spin.setMinimum(1)
        self.quantity_spin.setMaximum(1000000)
        form.addRow("Quantity:", self.quantity_spin)
        
        # Price
        self.price_spin = QDoubleSpinBox()
        self.price_spin.setMinimum(0.01)
        self.price_spin.setMaximum(1000000.0)
        self.price_spin.setDecimals(2)
        self.price_spin.setPrefix("₹ ")
        form.addRow("Price per Share:", self.price_spin)
        
        # Date
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        form.addRow("Date:", self.date_edit)
        
        # Investment horizon
        self.horizon_combo = QComboBox()
        self.horizon_combo.addItems(['SHORT', 'MEDIUM', 'LONG'])
        form.addRow("Investment Horizon:", self.horizon_combo)
        
        # Target price
        self.target_spin = QDoubleSpinBox()
        self.target_spin.setMinimum(0.0)
        self.target_spin.setMaximum(1000000.0)
        self.target_spin.setDecimals(2)
        self.target_spin.setPrefix("₹ ")
        form.addRow("Target Price:", self.target_spin)
        
        # Thesis
        self.thesis_edit = QTextEdit()
        self.thesis_edit.setMaximumHeight(100)
        form.addRow("Investment Thesis:", self.thesis_edit)

        # Journal V2
        self.setup_type_combo = QComboBox()
        self.setup_type_combo.setEditable(True)
        self.setup_type_combo.addItems([
            "Breakout",
            "Pullback",
            "Reversal",
            "Value",
            "Event-Driven",
            "Momentum",
            "Swing",
            "Positional",
        ])
        form.addRow("Setup Type:", self.setup_type_combo)

        self.confidence_spin = QSpinBox()
        self.confidence_spin.setRange(1, 5)
        self.confidence_spin.setValue(3)
        form.addRow("Confidence (1-5):", self.confidence_spin)

        self.risk_tags_input = QLineEdit()
        self.risk_tags_input.setPlaceholderText("e.g., debt, regulation, commodity")
        form.addRow("Risk Tags:", self.risk_tags_input)

        self.mistake_tags_input = QLineEdit()
        self.mistake_tags_input.setPlaceholderText("e.g., FOMO, no-stoploss")
        form.addRow("Mistake Tags:", self.mistake_tags_input)

        self.reflection_edit = QTextEdit()
        self.reflection_edit.setMaximumHeight(80)
        self.reflection_edit.setPlaceholderText("Post-trade reflection / checklist notes")
        form.addRow("Reflection:", self.reflection_edit)
        
        layout.addLayout(form)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton("Save Changes")
        save_btn.clicked.connect(self.save_changes)
        save_btn.setStyleSheet("font-weight: 700;")
        btn_layout.addWidget(save_btn)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def _apply_active_theme(self):
        """Apply active theme.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        win = self.parent().window() if self.parent() else None
        if win and hasattr(win, "styleSheet"):
            self.setStyleSheet(win.styleSheet())
    
    def load_transaction_data(self):
        '''Load existing transaction data'''
        self.transaction_data = self.db.get_transaction_by_id(self.transaction_id)
        
        if not self.transaction_data:
            QMessageBox.warning(self, "Error", "Transaction not found")
            self.reject()
            return
        
        # Pre-fill form
        self.type_combo.setCurrentText(self.transaction_data['transaction_type'])
        self.quantity_spin.setValue(self.transaction_data['quantity'])
        self.price_spin.setValue(self.transaction_data['price_per_share'])
        
        # Parse date
        date_parts = self.transaction_data['transaction_date'].split('-')
        if len(date_parts) == 3:
            self.date_edit.setDate(QDate(int(date_parts[0]), 
                                        int(date_parts[1]), 
                                        int(date_parts[2])))
        
        self.horizon_combo.setCurrentText(self.transaction_data['investment_horizon'])
        
        if self.transaction_data['target_price']:
            self.target_spin.setValue(self.transaction_data['target_price'])
        
        if self.transaction_data['thesis']:
            self.thesis_edit.setPlainText(self.transaction_data['thesis'])

        setup_type = self.transaction_data.get('setup_type')
        if setup_type:
            idx = self.setup_type_combo.findText(setup_type)
            if idx >= 0:
                self.setup_type_combo.setCurrentIndex(idx)
            else:
                self.setup_type_combo.setCurrentText(setup_type)

        confidence_score = self.transaction_data.get('confidence_score')
        if confidence_score:
            try:
                self.confidence_spin.setValue(int(confidence_score))
            except Exception:
                self.confidence_spin.setValue(3)

        self.risk_tags_input.setText((self.transaction_data.get('risk_tags') or '').strip())
        self.mistake_tags_input.setText((self.transaction_data.get('mistake_tags') or '').strip())
        self.reflection_edit.setPlainText((self.transaction_data.get('reflection_note') or '').strip())
    
    def save_changes(self):
        '''Save the updated transaction'''
        updates = {
            'transaction_type': self.type_combo.currentText(),
            'quantity': self.quantity_spin.value(),
            'price_per_share': self.price_spin.value(),
            'transaction_date': self.date_edit.date().toString('yyyy-MM-dd'),
            'investment_horizon': self.horizon_combo.currentText(),
            'target_price': self.target_spin.value(),
            'thesis': self.thesis_edit.toPlainText().strip(),
            'setup_type': self.setup_type_combo.currentText().strip() or None,
            'confidence_score': self.confidence_spin.value(),
            'risk_tags': self.risk_tags_input.text().strip() or None,
            'mistake_tags': self.mistake_tags_input.text().strip() or None,
            'reflection_note': self.reflection_edit.toPlainText().strip() or None,
        }
        
        if self.db.update_transaction(self.transaction_id, **updates):
            QMessageBox.information(self, "Success", 
                                   "Transaction updated successfully!")
            self.accept()
        else:
            QMessageBox.critical(self, "Error", 
                               "Failed to update transaction")
