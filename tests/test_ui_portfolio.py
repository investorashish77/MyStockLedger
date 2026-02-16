"""
UI tests for PortfolioView.
Verifies that row-level Edit/Delete action buttons render for each stock.
"""

import os
import sys
import unittest

# Ensure Qt can run in headless CI/local environments.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from PyQt5.QtWidgets import QApplication, QPushButton

from database.db_manager import DatabaseManager
from ui.portfolio_view import PortfolioView


class StubStockService:
    """Deterministic stock service for UI tests."""

    def to_quote_symbol(self, symbol, exchange=None, override_yahoo_symbol=None):
        return override_yahoo_symbol or symbol

    def get_current_price(self, symbol):
        return 125.0


class TestPortfolioViewUI(unittest.TestCase):
    """Tests portfolio table UI rendering."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.db = DatabaseManager(':memory:')
        self.user_id = self.db.create_user("9876543210", "Test User", "hash")
        self.stock_id = self.db.add_stock(self.user_id, "AAPL", "Apple Inc.", "NASDAQ")
        self.db.add_transaction(
            stock_id=self.stock_id,
            transaction_type="BUY",
            quantity=10,
            price_per_share=100.0,
            transaction_date="2024-01-01",
            investment_horizon="LONG",
            target_price=150.0,
            thesis="Test thesis"
        )

    def test_portfolio_rows_render_edit_delete_buttons(self):
        view = PortfolioView(self.db, StubStockService())
        view.load_portfolio(self.user_id)

        self.assertEqual(view.table.rowCount(), 1)
        self.assertEqual(view.table.columnCount(), 9)

        actions_widget = view.table.cellWidget(0, 8)
        self.assertIsNotNone(actions_widget)

        buttons = actions_widget.findChildren(QPushButton)
        button_labels = {btn.text() for btn in buttons}

        self.assertIn("Edit", button_labels)
        self.assertIn("Delete", button_labels)

    def test_portfolio_row_hover_shows_investment_note(self):
        view = PortfolioView(self.db, StubStockService())
        view.load_portfolio(self.user_id)

        symbol_item = view.table.item(0, 0)
        self.assertIsNotNone(symbol_item)
        self.assertIn("Investment Note:", symbol_item.toolTip())
        self.assertIn("Test thesis", symbol_item.toolTip())


def run_ui_tests():
    """Run UI tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestPortfolioViewUI))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_ui_tests()
    sys.exit(0 if success else 1)
