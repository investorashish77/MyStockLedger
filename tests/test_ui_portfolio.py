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

from PyQt5.QtWidgets import QApplication, QPushButton, QToolButton

from database.db_manager import DatabaseManager
from services.ai_summary_service import AISummaryService
from services.alert_service import AlertService
from ui.alerts_view import AlertsView
from ui.portfolio_view import PortfolioView
from utils.config import config


class StubStockService:
    """Deterministic stock service for UI tests."""

    def to_quote_symbol(self, symbol, exchange=None, override_yahoo_symbol=None):
        """To quote symbol.

        Args:
            symbol: Input parameter.
            exchange: Input parameter.
            override_yahoo_symbol: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        return override_yahoo_symbol or symbol

    def get_current_price(self, symbol):
        """Get current price.

        Args:
            symbol: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        return 125.0

    def get_stock_info(self, symbol):
        """Get stock info."""
        return {
            "symbol": symbol,
            "previousClose": 120.0,
        }

    def get_historical_prices(self, symbol, period="5d"):
        """Get historical prices."""
        return {"prices": [120.0, 121.0, 122.0, 123.0, 124.0]}


class TestPortfolioViewUI(unittest.TestCase):
    """Tests portfolio table UI rendering."""

    @classmethod
    def setUpClass(cls):
        """Setupclass.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        """Setup.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
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
        """Test portfolio rows render edit delete buttons.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        view = PortfolioView(self.db, StubStockService())
        view.load_portfolio(self.user_id)

        self.assertEqual(view.table.rowCount(), 1)
        self.assertEqual(view.table.columnCount(), 8)

        actions_widget = None
        for col in range(view.table.columnCount()):
            candidate = view.table.cellWidget(0, col)
            if candidate and candidate.findChildren(QToolButton):
                actions_widget = candidate
                break
        self.assertIsNotNone(actions_widget)

        menu_buttons = actions_widget.findChildren(QToolButton)
        self.assertTrue(menu_buttons)
        menu = menu_buttons[0].menu()
        self.assertIsNotNone(menu)
        action_labels = {action.text() for action in menu.actions() if action.text().strip()}
        self.assertIn("View Transactions", action_labels)
        self.assertIn("Delete Stock", action_labels)

    def test_portfolio_row_hover_shows_investment_note(self):
        """Test portfolio row hover shows investment note.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        view = PortfolioView(self.db, StubStockService())
        view.load_portfolio(self.user_id)

        asset_widget = view.table.cellWidget(0, 0)
        self.assertIsNotNone(asset_widget)
        self.assertIn("Investment Note:", asset_widget.toolTip())
        self.assertIn("Test thesis", asset_widget.toolTip())


class TestAlertsAdminAccessUI(unittest.TestCase):
    """Tests admin permission gating for AlertsView admin sync operations."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.db = DatabaseManager(":memory:")
        self.alert_service = AlertService(self.db)
        self.ai_service = AISummaryService(self.db)
        self.view = AlertsView(self.db, self.alert_service, self.ai_service)

        self.admin_user_id = self.db.create_user("9999999999", "Admin User", "hash")
        self.normal_user_id = self.db.create_user("8888888888", "Normal User", "hash")

        self.orig_admin_sync_admin_only = config.ADMIN_SYNC_ADMIN_ONLY
        self.orig_admin_user_ids = list(config.ADMIN_USER_IDS)
        self.orig_admin_user_mobiles = list(config.ADMIN_USER_MOBILES)

    def tearDown(self):
        config.ADMIN_SYNC_ADMIN_ONLY = self.orig_admin_sync_admin_only
        config.ADMIN_USER_IDS = self.orig_admin_user_ids
        config.ADMIN_USER_MOBILES = self.orig_admin_user_mobiles
        self.view.deleteLater()

    def _set_current_user(self, user_id: int):
        self.view.current_user_id = user_id
        self.view.current_user = self.db.get_user_by_id(user_id)

    def test_admin_sync_denied_for_non_admin_when_restricted(self):
        """Admin sync should be denied to non-admin user when restricted."""
        config.ADMIN_SYNC_ADMIN_ONLY = True
        config.ADMIN_USER_IDS = [self.admin_user_id]
        config.ADMIN_USER_MOBILES = ["9999999999"]
        self._set_current_user(self.normal_user_id)
        self.assertFalse(self.view._can_run_admin_operations())

    def test_admin_sync_allowed_for_admin_user_when_restricted(self):
        """Admin sync should be allowed to configured admin user."""
        config.ADMIN_SYNC_ADMIN_ONLY = True
        config.ADMIN_USER_IDS = [self.admin_user_id]
        config.ADMIN_USER_MOBILES = []
        self._set_current_user(self.admin_user_id)
        self.assertTrue(self.view._can_run_admin_operations())

    def test_admin_sync_allowed_for_any_user_when_unrestricted(self):
        """Admin sync should be allowed for any user when restriction disabled."""
        config.ADMIN_SYNC_ADMIN_ONLY = False
        config.ADMIN_USER_IDS = []
        config.ADMIN_USER_MOBILES = []
        self._set_current_user(self.normal_user_id)
        self.assertTrue(self.view._can_run_admin_operations())


def run_ui_tests():
    """Run UI tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestPortfolioViewUI))
    suite.addTests(loader.loadTestsFromTestCase(TestAlertsAdminAccessUI))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_ui_tests()
    sys.exit(0 if success else 1)
