#!/usr/bin/env python3
"""
Equity Tracker Development Agent
AI-powered coding assistant for feature development

This agent helps you:
- Generate new features
- Update existing code
- Run tests
- Get code explanations
- Implement designs
"""

import os
import sys
from pathlib import Path

class DevelopmentAgent:
    """Interactive development agent for Equity Tracker"""
    
    def __init__(self):
        """Init.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        self.project_root = Path(__file__).parent
        self.codebase_map = self._build_codebase_map()
        self.features_design = self._load_design_doc()
    
    def _build_codebase_map(self):
        """Build a map of the codebase structure"""
        codebase = {
            'database': {
                'db_manager.py': 'Database operations (CRUD)',
                'schema.sql': 'Database schema'
            },
            'services': {
                'auth_service.py': 'User authentication',
                'stock_service.py': 'Stock data fetching',
                'alert_service.py': 'Alert management',
                'ai_summary_service.py': 'AI summaries'
            },
            'ui': {
                'main_window.py': 'Main application window',
                'login_dialog.py': 'Login/registration',
                'portfolio_view.py': 'Portfolio display',
                'add_stock_dialog.py': 'Add stock dialog',
                'alerts_view.py': 'Alerts display',
                'summary_dialog.py': 'AI summary popup'
            },
            'utils': {
                'config.py': 'Configuration management'
            },
            'tests': {
                'test_imports.py': 'Import validation tests',
                'test_services.py': 'Unit tests',
                'test_integration.py': 'Integration tests',
                'run_tests.py': 'Test runner'
            }
        }
        return codebase
    
    def _load_design_doc(self):
        """Load the enhanced features design document"""
        design_path = self.project_root / 'ENHANCED_FEATURES_DESIGN.md'
        if design_path.exists():
            with open(design_path, 'r') as f:
                return f.read()
        return None
    
    def show_menu(self):
        """Show interactive menu"""
        print("\n" + "="*70)
        print("  🤖 EQUITY TRACKER DEVELOPMENT AGENT")
        print("="*70)
        print("\nWhat would you like to do?\n")
        print("  1. 🎯 Implement a new feature")
        print("  2. ✏️  Edit existing code")
        print("  3. 🧪 Run tests")
        print("  4. 📖 Explain code")
        print("  5. 🗺️  View codebase structure")
        print("  6. 📋 View feature roadmap")
        print("  7. 💡 Get implementation help")
        print("  8. 🚪 Exit")
        print("\n" + "="*70)
    
    def show_codebase_structure(self):
        """Display the codebase structure"""
        print("\n📁 CODEBASE STRUCTURE\n")
        
        for folder, files in self.codebase_map.items():
            print(f"\n{folder}/")
            for filename, description in files.items():
                print(f"  ├── {filename:<25} → {description}")
    
    def show_feature_roadmap(self):
        """Show available features to implement"""
        print("\n🗺️  FEATURE ROADMAP\n")
        
        features = [
            {
                'name': 'Edit Transaction',
                'priority': 'HIGH',
                'complexity': 'Low',
                'time': '2-3 hours',
                'files': ['ui/edit_transaction_dialog.py', 'database/db_manager.py']
            },
            {
                'name': 'Delete Transaction',
                'priority': 'HIGH',
                'complexity': 'Low',
                'time': '1-2 hours',
                'files': ['ui/portfolio_view.py', 'database/db_manager.py']
            },
            {
                'name': 'Sell Stock UI',
                'priority': 'HIGH',
                'complexity': 'Medium',
                'time': '3-4 hours',
                'files': ['ui/sell_stock_dialog.py', 'ui/portfolio_view.py']
            },
            {
                'name': 'Portfolio Analytics',
                'priority': 'MEDIUM',
                'complexity': 'High',
                'time': '6-8 hours',
                'files': ['ui/analytics_view.py', 'services/analytics_service.py']
            },
            {
                'name': 'Index Comparison',
                'priority': 'MEDIUM',
                'complexity': 'High',
                'time': '4-5 hours',
                'files': ['services/index_data_service.py', 'ui/analytics_view.py']
            }
        ]
        
        print(f"{'Feature':<25} {'Priority':<10} {'Complexity':<12} {'Est. Time':<12}")
        print("-" * 70)
        
        for i, feature in enumerate(features, 1):
            print(f"{i}. {feature['name']:<22} {feature['priority']:<10} "
                  f"{feature['complexity']:<12} {feature['time']:<12}")
    
    def generate_feature_code(self, feature_name):
        """Generate code for a specific feature"""
        print(f"\n🔨 Generating code for: {feature_name}\n")
        
        # This is where we'd integrate with Claude API to generate actual code
        # For now, provide templates and guidance
        
        templates = {
            'edit_transaction': self._get_edit_transaction_template(),
            'delete_transaction': self._get_delete_transaction_template(),
            'sell_stock': self._get_sell_stock_template(),
            'analytics': self._get_analytics_template()
        }
        
        # Normalize feature name
        feature_key = feature_name.lower().replace(' ', '_')
        
        if feature_key in templates:
            return templates[feature_key]
        else:
            return "Feature template not found. Please check feature name."
    
    def _get_edit_transaction_template(self):
        """Template for edit transaction feature"""
        return """
# FILE: database/db_manager.py
# Add these methods to DatabaseManager class:

def update_transaction(self, transaction_id: int, **updates) -> bool:
    '''Update a transaction with new values'''
    conn = self.get_connection()
    cursor = conn.cursor()
    
    # Build UPDATE query dynamically based on provided fields
    valid_fields = ['quantity', 'price_per_share', 'transaction_date', 
                   'investment_horizon', 'target_price', 'thesis']
    
    update_fields = []
    values = []
    for field, value in updates.items():
        if field in valid_fields:
            update_fields.append(f"{field} = ?")
            values.append(value)
    
    if not update_fields:
        return False
    
    query = f"UPDATE transactions SET {', '.join(update_fields)} WHERE transaction_id = ?"
    values.append(transaction_id)
    
    cursor.execute(query, values)
    conn.commit()
    conn.close()
    
    return True

def delete_transaction(self, transaction_id: int) -> bool:
    '''Delete a transaction'''
    conn = self.get_connection()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM transactions WHERE transaction_id = ?", 
                  (transaction_id,))
    
    conn.commit()
    conn.close()
    
    return True

def get_transaction_by_id(self, transaction_id: int) -> Optional[Dict]:
    '''Get a single transaction by ID'''
    conn = self.get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT transaction_id, stock_id, transaction_type, quantity, 
               price_per_share, transaction_date, investment_horizon,
               target_price, thesis
        FROM transactions WHERE transaction_id = ?
    ''', (transaction_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            'transaction_id': row[0],
            'stock_id': row[1],
            'transaction_type': row[2],
            'quantity': row[3],
            'price_per_share': row[4],
            'transaction_date': row[5],
            'investment_horizon': row[6],
            'target_price': row[7],
            'thesis': row[8]
        }
    return None

---

# FILE: ui/edit_transaction_dialog.py
# Create this new file:

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLabel,
                             QLineEdit, QPushButton, QComboBox, QTextEdit,
                             QDateEdit, QSpinBox, QDoubleSpinBox, QMessageBox)
from PyQt5.QtCore import QDate
from database.db_manager import DatabaseManager

class EditTransactionDialog(QDialog):
    '''Dialog for editing an existing transaction'''
    
    def __init__(self, db: DatabaseManager, transaction_id: int, parent=None):
        super().__init__(parent)
        self.db = db
        self.transaction_id = transaction_id
        self.transaction_data = None
        
        self.setup_ui()
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
        
        layout.addLayout(form)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton("Save Changes")
        save_btn.clicked.connect(self.save_changes)
        save_btn.setStyleSheet('''
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 4px;
            }
        ''')
        btn_layout.addWidget(save_btn)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)
    
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
    
    def save_changes(self):
        '''Save the updated transaction'''
        updates = {
            'transaction_type': self.type_combo.currentText(),
            'quantity': self.quantity_spin.value(),
            'price_per_share': self.price_spin.value(),
            'transaction_date': self.date_edit.date().toString('yyyy-MM-dd'),
            'investment_horizon': self.horizon_combo.currentText(),
            'target_price': self.target_spin.value(),
            'thesis': self.thesis_edit.toPlainText().strip()
        }
        
        if self.db.update_transaction(self.transaction_id, **updates):
            QMessageBox.information(self, "Success", 
                                   "Transaction updated successfully!")
            self.accept()
        else:
            QMessageBox.critical(self, "Error", 
                               "Failed to update transaction")

---

# FILE: ui/portfolio_view.py
# Add these methods to PortfolioView class:

def view_stock_details(self, index):
    '''View stock details with edit/delete options'''
    row = index.row()
    stock_id = self.table.item(row, 0).data(Qt.UserRole)
    symbol = self.table.item(row, 0).text()
    
    # Get transactions
    transactions = self.db.get_stock_transactions(stock_id)
    
    # Create transaction list dialog
    dialog = QDialog(self)
    dialog.setWindowTitle(f"{symbol} - Transactions")
    dialog.setMinimumSize(800, 400)
    
    layout = QVBoxLayout()
    
    # Transaction table
    table = QTableWidget()
    table.setColumnCount(8)
    table.setHorizontalHeaderLabels([
        'Date', 'Type', 'Qty', 'Price', 'Horizon', 'Target', 'Actions', 'ID'
    ])
    table.hideColumn(7)  # Hide ID column
    
    for i, trans in enumerate(transactions):
        table.insertRow(i)
        table.setItem(i, 0, QTableWidgetItem(trans['transaction_date']))
        table.setItem(i, 1, QTableWidgetItem(trans['transaction_type']))
        table.setItem(i, 2, QTableWidgetItem(str(trans['quantity'])))
        table.setItem(i, 3, QTableWidgetItem(f"₹{trans['price_per_share']:.2f}"))
        table.setItem(i, 4, QTableWidgetItem(trans['investment_horizon']))
        
        target = f"₹{trans['target_price']:.2f}" if trans['target_price'] else 'N/A'
        table.setItem(i, 5, QTableWidgetItem(target))
        
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
        table.setCellWidget(i, 6, actions)
        
        # Store transaction ID
        table.setItem(i, 7, QTableWidgetItem(str(trans['transaction_id'])))
    
    layout.addWidget(table)
    
    close_btn = QPushButton("Close")
    close_btn.clicked.connect(dialog.accept)
    layout.addWidget(close_btn)
    
    dialog.setLayout(layout)
    dialog.exec_()

def edit_transaction(self, transaction_id, parent_dialog):
    '''Edit a transaction'''
    from ui.edit_transaction_dialog import EditTransactionDialog
    
    dialog = EditTransactionDialog(self.db, transaction_id, self)
    if dialog.exec_():
        # Reload portfolio
        self.load_portfolio(self.current_user_id)
        parent_dialog.accept()  # Close parent dialog
        # Reopen with updated data
        # (or just refresh the table)

def delete_transaction(self, transaction_id, parent_dialog):
    '''Delete a transaction with confirmation'''
    reply = QMessageBox.question(
        self,
        'Confirm Delete',
        'Are you sure you want to delete this transaction?\\n\\nThis cannot be undone.',
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

---

NEXT STEPS:
1. Copy the db_manager.py methods
2. Create ui/edit_transaction_dialog.py
3. Update ui/portfolio_view.py with new methods
4. Test the functionality
5. Run tests: python3 tests/run_tests.py

Would you like me to generate the test cases for this feature?
"""
    
    def _get_delete_transaction_template(self):
        """Template for delete transaction feature"""
        return "See Edit Transaction template - delete is included there."
    
    def _get_sell_stock_template(self):
        """Template for sell stock feature"""
        return """
# Sell stock functionality template will be provided
# This builds on Edit Transaction feature
"""
    
    def _get_analytics_template(self):
        """Template for analytics feature"""
        return """
# Analytics feature template will be provided
# Requires matplotlib or plotly
"""
    
    def run_tests(self):
        """Run the test suite"""
        print("\n🧪 Running tests...\n")
        os.system("python3 tests/run_tests.py")
    
    def get_implementation_help(self):
        """Provide implementation guidance"""
        print("\n💡 IMPLEMENTATION HELP\n")
        print("""
To implement a feature using this agent:

1. Choose a feature from the roadmap
2. Generate the code template
3. Copy the code to the appropriate files
4. Test the feature
5. Integrate into the UI

Example workflow:
-----------------
Agent: [Shows Edit Transaction template]
You: Copy code to database/db_manager.py
You: Create ui/edit_transaction_dialog.py
You: Update ui/portfolio_view.py
Agent: Run tests
You: Test manually in the app
You: Commit changes

For complex features:
---------------------
Break into smaller tasks:
- Edit Transaction = DB methods + Dialog + Integration
- Analytics = Data service + Chart component + UI integration

Need help at any step? Use option 7 again!
        """)
    
    def interactive_mode(self):
        """Run the agent in interactive mode"""
        while True:
            self.show_menu()
            
            try:
                choice = input("\nEnter your choice (1-8): ").strip()
                
                if choice == '1':
                    self.show_feature_roadmap()
                    feature_num = input("\nEnter feature number to implement: ").strip()
                    
                    if feature_num == '1':
                        print(self.generate_feature_code('edit_transaction'))
                    elif feature_num == '2':
                        print(self.generate_feature_code('delete_transaction'))
                    elif feature_num == '3':
                        print(self.generate_feature_code('sell_stock'))
                    elif feature_num == '4':
                        print(self.generate_feature_code('analytics'))
                    else:
                        print("Invalid feature number")
                    
                    input("\nPress Enter to continue...")
                
                elif choice == '2':
                    print("\n✏️ Edit existing code feature coming soon...")
                    input("\nPress Enter to continue...")
                
                elif choice == '3':
                    self.run_tests()
                    input("\nPress Enter to continue...")
                
                elif choice == '4':
                    print("\n📖 Code explanation feature coming soon...")
                    input("\nPress Enter to continue...")
                
                elif choice == '5':
                    self.show_codebase_structure()
                    input("\nPress Enter to continue...")
                
                elif choice == '6':
                    self.show_feature_roadmap()
                    input("\nPress Enter to continue...")
                
                elif choice == '7':
                    self.get_implementation_help()
                    input("\nPress Enter to continue...")
                
                elif choice == '8':
                    print("\n👋 Goodbye! Happy coding!\n")
                    break
                
                else:
                    print("\n❌ Invalid choice. Please enter 1-8.")
                    input("\nPress Enter to continue...")
            
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye! Happy coding!\n")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
                input("\nPress Enter to continue...")


if __name__ == '__main__':
    agent = DevelopmentAgent()
    agent.interactive_mode()
