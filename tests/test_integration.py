"""
Integration Tests
Tests complete workflows and interactions between components
"""

import unittest
import sys
import os
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.db_manager import DatabaseManager
from services.auth_service import AuthService
from services.stock_service import StockService
from services.alert_service import AlertService


class TestUserWorkflow(unittest.TestCase):
    """Test complete user registration and login workflow"""
    
    def setUp(self):
        """Set up test environment"""
        self.db = DatabaseManager(':memory:')
        self.auth = AuthService(self.db)
    
    def test_complete_registration_login_workflow(self):
        """Test user can register and then login"""
        # Step 1: Register
        success, msg, user_id = self.auth.register_user(
            mobile_number="9876543210",
            name="Test User",
            password="secure123",
            email="test@example.com"
        )
        
        self.assertTrue(success, "Registration should succeed")
        self.assertIsNotNone(user_id)
        
        # Step 2: Login with correct credentials
        success, msg, user_data = self.auth.login("9876543210", "secure123")
        
        self.assertTrue(success, "Login should succeed")
        self.assertEqual(user_data['name'], "Test User")
        self.assertEqual(user_data['email'], "test@example.com")
        
        # Step 3: Verify password is not in returned data
        self.assertNotIn('password_hash', user_data)


class TestPortfolioWorkflow(unittest.TestCase):
    """Test complete portfolio management workflow"""
    
    def setUp(self):
        """Set up test environment"""
        self.db = DatabaseManager(':memory:')
        self.auth = AuthService(self.db)
        self.stock_service = StockService()
        
        # Create a test user
        success, msg, self.user_id = self.auth.register_user(
            "9876543210", "Test User", "test123"
        )
        self.assertTrue(success)
    
    def test_add_stock_and_view_portfolio(self):
        """Test adding stock and viewing portfolio"""
        # Step 1: Add a stock
        stock_id = self.db.add_stock(
            user_id=self.user_id,
            symbol="AAPL",
            company_name="Apple Inc.",
            exchange="NASDAQ"
        )
        
        self.assertIsNotNone(stock_id)
        
        # Step 2: Add a buy transaction
        trans_id = self.db.add_transaction(
            stock_id=stock_id,
            transaction_type="BUY",
            quantity=10,
            price_per_share=150.0,
            transaction_date="2024-01-01",
            investment_horizon="LONG",
            target_price=200.0,
            thesis="Strong fundamentals"
        )
        
        self.assertIsNotNone(trans_id)
        
        # Step 3: View portfolio
        portfolio = self.db.get_portfolio_summary(self.user_id)
        
        self.assertEqual(len(portfolio), 1)
        self.assertEqual(portfolio[0]['symbol'], "AAPL")
        self.assertEqual(portfolio[0]['quantity'], 10)
        self.assertEqual(portfolio[0]['avg_price'], 150.0)
        
        # Step 4: Get transactions
        transactions = self.db.get_stock_transactions(stock_id)
        
        self.assertEqual(len(transactions), 1)
        self.assertEqual(transactions[0]['thesis'], "Strong fundamentals")
    
    def test_multiple_transactions_average_price(self):
        """Test that average price is calculated correctly with multiple buys"""
        stock_id = self.db.add_stock(self.user_id, "AAPL", "Apple Inc.", "NASDAQ")
        
        # First buy: 10 shares at $100
        self.db.add_transaction(
            stock_id, "BUY", 10, 100.0, "2024-01-01", "LONG"
        )
        
        # Second buy: 10 shares at $120
        self.db.add_transaction(
            stock_id, "BUY", 10, 120.0, "2024-02-01", "LONG"
        )
        
        portfolio = self.db.get_portfolio_summary(self.user_id)
        
        # Average should be (10*100 + 10*120) / 20 = 110
        self.assertEqual(portfolio[0]['quantity'], 20)
        self.assertEqual(portfolio[0]['avg_price'], 110.0)
    
    def test_buy_and_sell_workflow(self):
        """Test buying and selling shares"""
        stock_id = self.db.add_stock(self.user_id, "AAPL", "Apple Inc.", "NASDAQ")
        
        # Buy 20 shares
        self.db.add_transaction(stock_id, "BUY", 20, 100.0, "2024-01-01", "LONG")
        
        # Sell 10 shares
        self.db.add_transaction(stock_id, "SELL", 10, 120.0, "2024-02-01", "LONG")
        
        portfolio = self.db.get_portfolio_summary(self.user_id)
        
        # Should have 10 shares remaining
        self.assertEqual(portfolio[0]['quantity'], 10)

    def test_edit_and_delete_transaction_workflow(self):
        """Test updating and deleting a transaction"""
        stock_id = self.db.add_stock(self.user_id, "AAPL", "Apple Inc.", "NASDAQ")
        tx_id = self.db.add_transaction(
            stock_id, "BUY", 10, 100.0, "2024-01-01", "LONG", 150.0, "Initial thesis"
        )

        updated = self.db.update_transaction(
            tx_id,
            transaction_type="SELL",
            quantity=5,
            price_per_share=130.0,
            thesis="Updated thesis"
        )
        self.assertTrue(updated)

        tx = self.db.get_transaction_by_id(tx_id)
        self.assertEqual(tx['transaction_type'], "SELL")
        self.assertEqual(tx['quantity'], 5)
        self.assertEqual(tx['price_per_share'], 130.0)
        self.assertEqual(tx['thesis'], "Updated thesis")

        deleted = self.db.delete_transaction(tx_id)
        self.assertTrue(deleted)
        self.assertEqual(self.db.get_stock_transactions(stock_id), [])

    def test_delete_stock_workflow(self):
        """Test deleting an entire stock position and related data"""
        stock_id = self.db.add_stock(self.user_id, "AAPL", "Apple Inc.", "NASDAQ")
        self.db.add_transaction(stock_id, "BUY", 10, 100.0, "2024-01-01", "LONG")
        alert_id = self.db.add_alert(stock_id, "ANNOUNCEMENT", "Test announcement")
        self.db.save_ai_summary(alert_id, "AI summary", "NEUTRAL")
        self.db.save_price(stock_id, 101.25)

        deleted = self.db.delete_stock(stock_id)
        self.assertTrue(deleted)
        self.assertEqual(self.db.get_user_stocks(self.user_id), [])
        self.assertEqual(self.db.get_user_alerts(self.user_id), [])


class TestAlertWorkflow(unittest.TestCase):
    """Test alert creation and retrieval workflow"""
    
    def setUp(self):
        """Set up test environment"""
        self.db = DatabaseManager(':memory:')
        self.auth = AuthService(self.db)
        self.alert_service = AlertService(self.db)
        
        # Create user and stock
        success, msg, self.user_id = self.auth.register_user(
            "9876543210", "Test User", "test123"
        )
        self.stock_id = self.db.add_stock(
            self.user_id, "AAPL", "Apple Inc.", "NASDAQ"
        )
    
    def test_create_and_retrieve_alert(self):
        """Test creating and retrieving alerts"""
        # Create alert
        alert_id = self.alert_service.create_manual_alert(
            stock_id=self.stock_id,
            alert_type="ANNOUNCEMENT",
            message="Q3 Results Announced",
            details="Revenue up 15% YoY",
            url="https://example.com"
        )
        
        self.assertIsNotNone(alert_id)
        
        # Retrieve alerts
        alerts = self.alert_service.get_user_alerts(self.user_id)
        
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]['alert_message'], "Q3 Results Announced")
        self.assertEqual(alerts[0]['announcement_details'], "Revenue up 15% YoY")
        self.assertFalse(alerts[0]['is_read'])
    
    def test_mark_alert_as_read(self):
        """Test marking alert as read"""
        alert_id = self.alert_service.create_manual_alert(
            self.stock_id, "NEWS", "Breaking News"
        )
        
        # Mark as read
        self.alert_service.mark_as_read(alert_id)
        
        # Verify it's read
        alerts = self.alert_service.get_user_alerts(self.user_id)
        self.assertTrue(alerts[0]['is_read'])
        
        # Verify unread_only filter works
        unread_alerts = self.alert_service.get_user_alerts(self.user_id, unread_only=True)
        self.assertEqual(len(unread_alerts), 0)


class TestPriceTrackingWorkflow(unittest.TestCase):
    """Test price tracking and P&L calculation workflow"""
    
    def setUp(self):
        """Set up test environment"""
        self.db = DatabaseManager(':memory:')
        self.auth = AuthService(self.db)
        self.stock_service = StockService()
        
        # Create user and stock
        success, msg, self.user_id = self.auth.register_user(
            "9876543210", "Test User", "test123"
        )
        self.stock_id = self.db.add_stock(
            self.user_id, "AAPL", "Apple Inc.", "NASDAQ"
        )
    
    def test_save_and_retrieve_price(self):
        """Test saving and retrieving stock prices"""
        # Save price
        self.db.save_price(self.stock_id, 150.0)
        
        # Retrieve price
        latest_price = self.db.get_latest_price(self.stock_id)
        
        self.assertEqual(latest_price, 150.0)
    
    def test_pnl_calculation_workflow(self):
        """Test complete P&L calculation"""
        # Add transaction
        self.db.add_transaction(
            self.stock_id, "BUY", 10, 100.0, "2024-01-01", "LONG"
        )
        
        # Calculate P&L with different current price
        pnl = self.stock_service.calculate_pnl(
            avg_price=100.0,
            current_price=120.0,
            quantity=10
        )
        
        self.assertEqual(pnl['total_invested'], 1000.0)
        self.assertEqual(pnl['current_value'], 1200.0)
        self.assertEqual(pnl['pnl'], 200.0)
        self.assertEqual(pnl['pnl_percentage'], 20.0)


class TestMultiUserScenario(unittest.TestCase):
    """Test multiple users using the system"""
    
    def setUp(self):
        """Set up test environment"""
        self.db = DatabaseManager(':memory:')
        self.auth = AuthService(self.db)
    
    def test_multiple_users_separate_data(self):
        """Test that multiple users have separate data"""
        # Create two users
        success1, msg1, user_id1 = self.auth.register_user(
            "9876543210", "User One", "pass123"
        )
        success2, msg2, user_id2 = self.auth.register_user(
            "8765432109", "User Two", "pass456"
        )
        
        self.assertTrue(success1)
        self.assertTrue(success2)
        self.assertNotEqual(user_id1, user_id2)
        
        # Add stocks for each user
        stock_id1 = self.db.add_stock(user_id1, "AAPL", "Apple", "NASDAQ")
        stock_id2 = self.db.add_stock(user_id2, "GOOGL", "Google", "NASDAQ")
        
        # Get portfolios
        portfolio1 = self.db.get_user_stocks(user_id1)
        portfolio2 = self.db.get_user_stocks(user_id2)
        
        # Verify separation
        self.assertEqual(len(portfolio1), 1)
        self.assertEqual(len(portfolio2), 1)
        self.assertEqual(portfolio1[0]['symbol'], "AAPL")
        self.assertEqual(portfolio2[0]['symbol'], "GOOGL")


def run_integration_tests():
    """Run all integration tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestUserWorkflow))
    suite.addTests(loader.loadTestsFromTestCase(TestPortfolioWorkflow))
    suite.addTests(loader.loadTestsFromTestCase(TestAlertWorkflow))
    suite.addTests(loader.loadTestsFromTestCase(TestPriceTrackingWorkflow))
    suite.addTests(loader.loadTestsFromTestCase(TestMultiUserScenario))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_integration_tests()
    sys.exit(0 if success else 1)
