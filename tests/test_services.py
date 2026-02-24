"""
Unit Tests for Equity Tracker Services
Tests all service layer functionality
"""

import unittest
import sys
import os
import tempfile
from pathlib import Path
from datetime import datetime, date
from unittest.mock import patch, MagicMock

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.db_manager import DatabaseManager
from services.auth_service import AuthService
from services.stock_service import StockService
from services.alert_service import AlertService
from services.ai_summary_service import AISummaryService
from services.symbol_master_service import SymbolMasterService
from services.bse_feed_service import BSEFeedService
from services.bse_bhavcopy_service import BSEBhavcopyService
from services.nsetools_adapter import NSEToolsAdapter
from services.watchman_service import WatchmanService
from services.financial_result_parser import FinancialResultParser
from utils.config import config


class TestAuthService(unittest.TestCase):
    """Test authentication service"""
    
    def setUp(self):
        """Set up test database"""
        self.db = DatabaseManager(':memory:')  # Use in-memory database for testing
        self.auth = AuthService(self.db)
    
    def test_password_hashing(self):
        """Test password is hashed correctly"""
        password = "test123"
        hash1 = self.auth.hash_password(password)
        hash2 = self.auth.hash_password(password)
        
        self.assertEqual(hash1, hash2, "Same password should produce same hash")
        self.assertNotEqual(password, hash1, "Password should be hashed, not plaintext")
    
    def test_mobile_validation(self):
        """Test mobile number validation"""
        self.assertTrue(self.auth.validate_mobile_number("9876543210"))
        self.assertTrue(self.auth.validate_mobile_number("98765 43210"))  # With space
        self.assertFalse(self.auth.validate_mobile_number("123"))  # Too short
        self.assertFalse(self.auth.validate_mobile_number("12345678901"))  # Too long
    
    def test_password_validation(self):
        """Test password validation"""
        is_valid, msg = self.auth.validate_password("test123")
        self.assertTrue(is_valid)
        
        is_valid, msg = self.auth.validate_password("12345")  # Too short
        self.assertFalse(is_valid)
        self.assertIn("at least 6 characters", msg)
    
    def test_user_registration(self):
        """Test user registration"""
        success, msg, user_id = self.auth.register_user(
            mobile_number="9876543210",
            name="Test User",
            password="test123",
            email="test@example.com"
        )
        
        self.assertTrue(success, "Registration should succeed")
        self.assertIsNotNone(user_id, "User ID should be returned")
        
        # Test duplicate registration
        success, msg, user_id = self.auth.register_user(
            mobile_number="9876543210",
            name="Another User",
            password="test123"
        )
        self.assertFalse(success, "Duplicate registration should fail")
        self.assertIn("already exists", msg)
    
    def test_user_login(self):
        """Test user login"""
        # Register user first
        self.auth.register_user("9876543210", "Test User", "test123")
        
        # Test successful login
        success, msg, user_data = self.auth.login("9876543210", "test123")
        self.assertTrue(success, "Login should succeed")
        self.assertIsNotNone(user_data, "User data should be returned")
        self.assertEqual(user_data['mobile_number'], "9876543210")
        
        # Test wrong password
        success, msg, user_data = self.auth.login("9876543210", "wrong_password")
        self.assertFalse(success, "Login should fail with wrong password")
        
        # Test non-existent user
        success, msg, user_data = self.auth.login("0000000000", "test123")
        self.assertFalse(success, "Login should fail for non-existent user")


class TestStockService(unittest.TestCase):
    """Test stock service"""
    
    def setUp(self):
        """Set up stock service"""
        self.stock_service = StockService()
    
    def test_get_stock_info_valid(self):
        """Test fetching valid stock info"""
        # Test with a well-known stock
        info = self.stock_service.get_stock_info("AAPL")
        
        if info:  # Only test if we have internet connection
            self.assertIsNotNone(info)
            self.assertIn('symbol', info)
            self.assertIn('company_name', info)
            self.assertIn('current_price', info)
    
    def test_get_stock_info_invalid(self):
        """Test fetching invalid stock"""
        info = self.stock_service.get_stock_info("INVALID_SYMBOL_XYZ")
        self.assertIsNone(info, "Invalid stock should return None")
    
    def test_calculate_pnl(self):
        """Test P&L calculation"""
        result = self.stock_service.calculate_pnl(
            avg_price=100.0,
            current_price=120.0,
            quantity=10
        )
        
        self.assertEqual(result['total_invested'], 1000.0)
        self.assertEqual(result['current_value'], 1200.0)
        self.assertEqual(result['pnl'], 200.0)
        self.assertEqual(result['pnl_percentage'], 20.0)
    
    def test_calculate_pnl_loss(self):
        """Test P&L calculation with loss"""
        result = self.stock_service.calculate_pnl(
            avg_price=100.0,
            current_price=80.0,
            quantity=10
        )
        
        self.assertEqual(result['pnl'], -200.0)
        self.assertEqual(result['pnl_percentage'], -20.0)

    @patch('services.stock_service.yf.Ticker')
    def test_get_stock_info_uses_cache_for_repeated_symbol(self, mock_ticker):
        """Test repeated get_stock_info calls use in-memory cache."""
        ticker_instance = MagicMock()
        ticker_instance.info = {
            'symbol': 'AAPL',
            'longName': 'Apple Inc.',
            'currentPrice': 180.0,
            'previousClose': 178.0,
            'marketCap': 100,
            'currency': 'USD',
            'exchange': 'NASDAQ'
        }
        mock_ticker.return_value = ticker_instance

        info1 = self.stock_service.get_stock_info("AAPL")
        info2 = self.stock_service.get_stock_info("AAPL")

        self.assertIsNotNone(info1)
        self.assertIsNotNone(info2)
        self.assertEqual(info1['company_name'], "Apple Inc.")
        self.assertEqual(mock_ticker.call_count, 1)


class TestDatabaseManager(unittest.TestCase):
    """Test database operations"""
    
    def setUp(self):
        """Set up test database"""
        self.db = DatabaseManager(':memory:')
    
    def test_create_user(self):
        """Test creating a user"""
        user_id = self.db.create_user(
            mobile_number="9876543210",
            name="Test User",
            password_hash="hashed_password"
        )
        
        self.assertIsNotNone(user_id)
        self.assertGreater(user_id, 0)
    
    def test_get_user_by_mobile(self):
        """Test retrieving user by mobile"""
        # Create user
        self.db.create_user("9876543210", "Test User", "hash")
        
        # Retrieve user
        user = self.db.get_user_by_mobile("9876543210")
        self.assertIsNotNone(user)
        self.assertEqual(user['name'], "Test User")
        
        # Non-existent user
        user = self.db.get_user_by_mobile("0000000000")
        self.assertIsNone(user)
    
    def test_add_stock(self):
        """Test adding a stock"""
        # Create user first
        user_id = self.db.create_user("9876543210", "Test User", "hash")
        
        # Add stock
        stock_id = self.db.add_stock(
            user_id=user_id,
            symbol="AAPL",
            company_name="Apple Inc.",
            exchange="NASDAQ"
        )
        
        self.assertIsNotNone(stock_id)
        self.assertGreater(stock_id, 0)
        
        # Test duplicate stock returns same ID
        stock_id2 = self.db.add_stock(user_id, "AAPL", "Apple Inc.", "NASDAQ")
        self.assertEqual(stock_id, stock_id2)
    
    def test_add_transaction(self):
        """Test adding a transaction"""
        user_id = self.db.create_user("9876543210", "Test User", "hash")
        stock_id = self.db.add_stock(user_id, "AAPL", "Apple Inc.", "NASDAQ")
        
        transaction_id = self.db.add_transaction(
            stock_id=stock_id,
            transaction_type="BUY",
            quantity=10,
            price_per_share=150.0,
            transaction_date="2024-01-01",
            investment_horizon="LONG",
            target_price=200.0,
            thesis="Good company"
        )
        
        self.assertIsNotNone(transaction_id)
        self.assertGreater(transaction_id, 0)
    
    def test_get_portfolio_summary(self):
        """Test portfolio summary calculation"""
        user_id = self.db.create_user("9876543210", "Test User", "hash")
        stock_id = self.db.add_stock(user_id, "AAPL", "Apple Inc.", "NASDAQ")
        
        # Add buy transaction
        self.db.add_transaction(
            stock_id=stock_id,
            transaction_type="BUY",
            quantity=10,
            price_per_share=100.0,
            transaction_date="2024-01-01",
            investment_horizon="LONG"
        )
        
        portfolio = self.db.get_portfolio_summary(user_id)
        
        self.assertEqual(len(portfolio), 1)
        self.assertEqual(portfolio[0]['symbol'], "AAPL")
        self.assertEqual(portfolio[0]['quantity'], 10)
        self.assertEqual(portfolio[0]['avg_price'], 100.0)

    def test_sell_transaction_computes_fifo_realized_pnl(self):
        """SELL transaction should compute realized pnl using FIFO lots."""
        user_id = self.db.create_user("9876543201", "FIFO User", "hash")
        stock_id = self.db.add_stock(user_id, "AAPL", "Apple Inc.", "NASDAQ")
        self.db.add_transaction(stock_id, "BUY", 10, 100.0, "2026-01-01", "LONG")
        self.db.add_transaction(stock_id, "BUY", 10, 120.0, "2026-01-10", "LONG")

        sell_tx = self.db.add_transaction(
            stock_id=stock_id,
            transaction_type="SELL",
            quantity=15,
            price_per_share=130.0,
            transaction_date="2026-02-01",
            investment_horizon="LONG",
        )
        tx = self.db.get_transaction_by_id(sell_tx)
        # FIFO cost basis = (10*100) + (5*120) = 1600
        # sell value = 15*130 = 1950, realized pnl = 350
        self.assertAlmostEqual(tx["realized_cost_basis"], 1600.0, places=2)
        self.assertAlmostEqual(tx["realized_pnl"], 350.0, places=2)

        portfolio = self.db.get_portfolio_summary(user_id)
        self.assertEqual(len(portfolio), 1)
        self.assertEqual(portfolio[0]["quantity"], 5)

    def test_sell_transaction_rejects_when_quantity_exceeds_holdings(self):
        """SELL quantity greater than available should raise validation error."""
        user_id = self.db.create_user("9876543202", "Sell Guard", "hash")
        stock_id = self.db.add_stock(user_id, "MSFT", "Microsoft Corp.", "NASDAQ")
        self.db.add_transaction(stock_id, "BUY", 5, 200.0, "2026-01-01", "LONG")
        with self.assertRaises(ValueError):
            self.db.add_transaction(
                stock_id=stock_id,
                transaction_type="SELL",
                quantity=6,
                price_per_share=220.0,
                transaction_date="2026-01-15",
                investment_horizon="LONG",
            )

    def test_realized_pnl_summary_uses_indian_financial_year(self):
        """FY rollup should include SELL transactions within Apr-Mar window."""
        user_id = self.db.create_user("9876543203", "FY User", "hash")
        stock_id = self.db.add_stock(user_id, "INFY", "Infosys Ltd", "NSE")
        self.db.add_transaction(stock_id, "BUY", 10, 100.0, "2025-03-20", "LONG")
        # Falls in FY25-26 (starts 2025-04-01)
        self.db.add_transaction(stock_id, "SELL", 5, 130.0, "2025-04-05", "LONG")
        # Falls in FY26-27 (starts 2026-04-01)
        self.db.add_transaction(stock_id, "SELL", 2, 140.0, "2026-04-02", "LONG")

        fy_2526 = self.db.get_realized_pnl_summary(
            user_id,
            fy_start=date(2025, 4, 1),
            fy_end=date(2026, 3, 31),
        )
        self.assertAlmostEqual(fy_2526["total_realized_pnl"], 150.0, places=2)
        self.assertEqual(fy_2526["sell_transaction_count"], 1)

        fy_2627 = self.db.get_realized_pnl_summary(
            user_id,
            fy_start=date(2026, 4, 1),
            fy_end=date(2027, 3, 31),
        )
        self.assertAlmostEqual(fy_2627["total_realized_pnl"], 80.0, places=2)
        self.assertEqual(fy_2627["sell_transaction_count"], 1)

    def test_update_transaction_including_type(self):
        """Test updating transaction fields including transaction_type"""
        user_id = self.db.create_user("9876543210", "Test User", "hash")
        stock_id = self.db.add_stock(user_id, "AAPL", "Apple Inc.", "NASDAQ")

        transaction_id = self.db.add_transaction(
            stock_id=stock_id,
            transaction_type="BUY",
            quantity=10,
            price_per_share=100.0,
            transaction_date="2024-01-01",
            investment_horizon="LONG",
            target_price=150.0,
            thesis="Initial thesis"
        )

        updated = self.db.update_transaction(
            transaction_id,
            transaction_type="SELL",
            quantity=5,
            price_per_share=120.0
        )
        self.assertTrue(updated)

        txn = self.db.get_transaction_by_id(transaction_id)
        self.assertEqual(txn['transaction_type'], "SELL")
        self.assertEqual(txn['quantity'], 5)
        self.assertEqual(txn['price_per_share'], 120.0)

    def test_delete_stock_cascades_related_records(self):
        """Test deleting stock removes related transactions/alerts/prices/summaries"""
        user_id = self.db.create_user("9876543210", "Test User", "hash")
        stock_id = self.db.add_stock(user_id, "AAPL", "Apple Inc.", "NASDAQ")
        self.db.add_transaction(stock_id, "BUY", 10, 100.0, "2024-01-01", "LONG")
        alert_id = self.db.add_alert(stock_id, "ANNOUNCEMENT", "Test alert")
        self.db.save_ai_summary(alert_id, "Summary", "NEUTRAL")
        self.db.save_price(stock_id, 123.45)

        deleted = self.db.delete_stock(stock_id)
        self.assertTrue(deleted)

        self.assertEqual(self.db.get_stock_transactions(stock_id), [])
        self.assertEqual(self.db.get_latest_price(stock_id), None)
        self.assertEqual(self.db.get_user_stocks(user_id), [])
        self.assertEqual(self.db.get_user_alerts(user_id), [])

    def test_app_settings_upsert_and_read(self):
        """Test app_settings key-value persistence."""
        self.assertIsNone(self.db.get_setting("missing_key"))
        self.assertEqual(self.db.get_setting("missing_with_default", "x"), "x")

        self.db.set_setting("filings_api_last_sync_date", "20260214")
        self.assertEqual(self.db.get_setting("filings_api_last_sync_date"), "20260214")

        self.db.set_setting("filings_api_last_sync_date", "20260215")
        self.assertEqual(self.db.get_setting("filings_api_last_sync_date"), "20260215")

    def test_background_job_enqueue_claim_complete(self):
        """Test background job enqueue claim complete.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        user_id = self.db.create_user("9000000003", "Job User", "hash")
        job_id = self.db.enqueue_background_job(
            job_type="GENERATE_MISSING_INSIGHTS",
            requested_by=user_id,
            payload={"user_id": user_id, "force_regenerate": False}
        )
        self.assertGreater(job_id, 0)

        claimed = self.db.claim_next_background_job()
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed["job_id"], job_id)
        self.assertEqual(claimed["status"], "RUNNING")
        self.assertEqual(claimed["payload"]["user_id"], user_id)

        self.db.complete_background_job(job_id, status="SUCCESS", result={"generated": 2})
        self.assertIsNone(self.db.claim_next_background_job())

    def test_notifications_unread_count_and_mark_read(self):
        """Test notifications unread count and mark read.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        user_id = self.db.create_user("9000000004", "Notify User", "hash")
        self.db.add_notification(user_id, "INSIGHTS_READY", "Insights Ready", "Done", {"job_id": 1})
        self.db.add_notification(None, "SYSTEM", "Global", "Hello", {})
        self.assertEqual(self.db.get_unread_notifications_count(user_id), 2)
        rows = self.db.get_user_notifications(user_id, unread_only=True, limit=10)
        self.assertEqual(len(rows), 2)
        self.db.mark_all_notifications_read(user_id)
        self.assertEqual(self.db.get_unread_notifications_count(user_id), 0)

    def test_get_user_stocks_with_symbol_master_matches_ns_suffix(self):
        """Stock rows with .NS should map to symbol_master base symbol."""
        user_id = self.db.create_user("9000000001", "Suffix User", "hash")
        self.db.add_stock(user_id, "MTARTECH.NS", "MTAR Technologies Limited", "NSI")
        self.db.upsert_symbol_master(
            symbol="MTARTECH",
            company_name="MTAR Technologies Limited",
            exchange="NSE",
            bse_code="543270",
            nse_code="MTARTECH",
            source="TEST"
        )

        rows = self.db.get_user_stocks_with_symbol_master(user_id)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["bse_code"], "543270")

    def test_bse_daily_price_upsert_and_portfolio_series(self):
        """Test bse daily price upsert and portfolio series.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        user_id = self.db.create_user("9000000002", "Bhavcopy User", "hash")
        stock_id = self.db.add_stock(user_id, "GOODLUCK", "Goodluck India Limited", "NSE")
        self.db.upsert_symbol_master(
            symbol="GOODLUCK",
            company_name="Goodluck India Limited",
            exchange="NSE",
            bse_code="530655",
            nse_code="GOODLUCK",
            source="TEST"
        )
        self.db.add_transaction(stock_id, "BUY", 10, 100.0, "2026-01-01", "LONG")
        self.db.add_transaction(stock_id, "SELL", 5, 110.0, "2026-01-03", "LONG")

        self.db.upsert_bse_daily_price("530655", "2026-01-01", close_price=100.0, open_price=99.0)
        self.db.upsert_bse_daily_price("530655", "2026-01-02", close_price=110.0, open_price=101.0)
        self.db.upsert_bse_daily_price("530655", "2026-01-03", close_price=120.0, open_price=115.0)

        rows = self.db.get_bse_daily_prices("530655", limit=10)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[-1]["close_price"], 120.0)

        series = self.db.get_portfolio_performance_series(user_id=user_id)
        self.assertEqual(len(series), 3)
        # day1 qty=10 => 1000, day2 qty=10 => 1100, day3 after SELL(5) => 600
        self.assertEqual(series[0]["portfolio_value"], 1000.0)
        self.assertEqual(series[1]["portfolio_value"], 1100.0)
        self.assertEqual(series[2]["portfolio_value"], 600.0)

    def test_analyst_consensus_upsert_and_get(self):
        """Test analyst consensus upsert and get.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        user_id = self.db.create_user("9000011111", "Analyst User", "hash")
        stock_id = self.db.add_stock(user_id, "INFY", "Infosys Ltd", "NSE")
        consensus_id = self.db.upsert_analyst_consensus(
            stock_id=stock_id,
            report_text="Sample analyst consensus report",
            status="GENERATED",
            provider="groq",
            as_of_date="2026-02-18",
        )
        self.assertIsNotNone(consensus_id)
        row = self.db.get_analyst_consensus(stock_id)
        self.assertIsNotNone(row)
        self.assertEqual(row["status"], "GENERATED")
        self.assertEqual(row["provider"], "groq")
        self.assertIn("consensus", row["report_text"])


class TestAlertService(unittest.TestCase):
    """Test alert service"""
    
    def setUp(self):
        """Set up test environment"""
        self.db = DatabaseManager(':memory:')
        self.alert_service = AlertService(self.db)
    
    def test_create_manual_alert(self):
        """Test creating manual alert"""
        user_id = self.db.create_user("9876543210", "Test User", "hash")
        stock_id = self.db.add_stock(user_id, "AAPL", "Apple Inc.", "NASDAQ")
        
        alert_id = self.alert_service.create_manual_alert(
            stock_id=stock_id,
            alert_type="ANNOUNCEMENT",
            message="Q3 Results",
            details="Revenue up 20%"
        )
        
        self.assertIsNotNone(alert_id)
        self.assertGreater(alert_id, 0)
    
    def test_get_user_alerts(self):
        """Test retrieving user alerts"""
        user_id = self.db.create_user("9876543210", "Test User", "hash")
        stock_id = self.db.add_stock(user_id, "AAPL", "Apple Inc.", "NASDAQ")
        
        # Create alert
        self.alert_service.create_manual_alert(
            stock_id=stock_id,
            alert_type="ANNOUNCEMENT",
            message="Test Alert"
        )
        
        alerts = self.alert_service.get_user_alerts(user_id)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]['alert_message'], "Test Alert")

    def test_sync_portfolio_announcements_material_only(self):
        """Test syncing only material announcements for portfolio symbols."""
        user_id = self.db.create_user("9876543210", "Test User", "hash")
        stock_id = self.db.add_stock(user_id, "INFY", "Infosys", "NSE")
        symbol_id = self.db.upsert_symbol_master(
            symbol="INFY",
            company_name="Infosys",
            exchange="NSE",
            source="TEST"
        )

        # Material announcement (should create alert)
        self.db.add_bse_announcement(
            symbol_id=symbol_id,
            headline="INFY Q3 Results announced",
            category="BSE_RSS",
            announcement_date="Fri, 13 Feb 2026 10:00:00 GMT",
            attachment_url="https://example.com/infy-q3",
            rss_guid="guid-infy-q3",
            raw_payload='{"description":"Revenue up 10% YoY","link":"https://example.com/infy-q3"}'
        )

        # Non-material announcement (should be ignored)
        self.db.add_bse_announcement(
            symbol_id=symbol_id,
            headline="INFY updates investor presentation website link",
            category="BSE_RSS",
            announcement_date="Fri, 13 Feb 2026 11:00:00 GMT",
            attachment_url="https://example.com/infy-link",
            rss_guid="guid-infy-link",
            raw_payload='{"description":"Routine website update","link":"https://example.com/infy-link"}'
        )

        created = self.alert_service.sync_portfolio_announcements(user_id)
        self.assertEqual(created, 1)

        alerts = self.alert_service.get_user_alerts(user_id)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["stock_id"], stock_id)
        self.assertIn("Results", alerts[0]["alert_message"])

    def test_sync_portfolio_announcements_matches_multiple_stocks_and_caps_per_stock(self):
        """Should match by headline fallback and keep only up to 4 per stock per sync."""
        user_id = self.db.create_user("9999999999", "Multi", "hash")
        stock_id_1 = self.db.add_stock(user_id, "HIKAL", "Hikal Ltd", "NSE")
        stock_id_2 = self.db.add_stock(user_id, "SOLARA", "Solara Active Pharma Sciences Ltd", "NSE")
        self.db.upsert_symbol_master(symbol="HIKAL", company_name="Hikal Ltd", exchange="NSE", source="TEST")
        self.db.upsert_symbol_master(symbol="SOLARA", company_name="Solara Active Pharma Sciences Ltd", exchange="NSE", source="TEST")

        # 6 material headlines for HIKAL; sync should cap to 4.
        for i in range(6):
            self.db.add_bse_announcement(
                symbol_id=None,
                headline=f"HIKAL Q3 Results update #{i}",
                category="BSE_RSS",
                announcement_date=f"Fri, 13 Feb 2026 1{i}:00:00 GMT",
                attachment_url=f"https://example.com/hikal-{i}",
                rss_guid=f"guid-hikal-{i}",
                raw_payload='{"description":"Quarterly results"}'
            )

        # 1 material headline for SOLARA.
        self.db.add_bse_announcement(
            symbol_id=None,
            headline="SOLARA board meeting outcome and dividend",
            category="BSE_RSS",
            announcement_date="Fri, 13 Feb 2026 20:00:00 GMT",
            attachment_url="https://example.com/solara-1",
            rss_guid="guid-solara-1",
            raw_payload='{"description":"Board outcome"}'
        )

        created = self.alert_service.sync_portfolio_announcements(user_id)
        self.assertEqual(created, 5)  # 4 for HIKAL + 1 for SOLARA

        alerts = self.alert_service.get_user_alerts(user_id)
        by_stock = {}
        for alert in alerts:
            by_stock.setdefault(alert["stock_id"], 0)
            by_stock[alert["stock_id"]] += 1
        self.assertEqual(by_stock.get(stock_id_1, 0), 4)
        self.assertEqual(by_stock.get(stock_id_2, 0), 1)

    @patch("services.bse_feed_service.BSEFeedService.ingest_api_range")
    def test_sync_bse_feed_for_portfolio_uses_bse_codes(self, mock_ingest):
        """Test sync bse feed for portfolio uses bse codes.

        Args:
            mock_ingest: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        user_id = self.db.create_user("9999999998", "BSE Sync", "hash")
        self.db.add_stock(user_id, "GOODLUCK", "Goodluck India Limited", "NSE")
        self.db.upsert_symbol_master(
            symbol="GOODLUCK",
            company_name="Goodluck India Limited",
            exchange="NSE",
            bse_code="530655",
            nse_code="GOODLUCK",
            source="TEST"
        )

        self.alert_service.sync_bse_feed_for_portfolio(
            user_id=user_id,
            start_date_yyyymmdd="20260101",
            end_date_yyyymmdd="20260214",
            max_pages_per_symbol=5
        )

        self.assertEqual(mock_ingest.call_count, 1)
        kwargs = mock_ingest.call_args.kwargs
        self.assertEqual(kwargs["start_date_yyyymmdd"], "20260101")
        self.assertEqual(kwargs["end_date_yyyymmdd"], "20260214")
        self.assertEqual(kwargs["scrip_code"], "530655")

    def test_classify_category_earnings_call_not_results(self):
        """Test classify category earnings call not results.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        headline = "Transcript of Earnings Conference Call for Q3 FY26"
        category = self.alert_service._classify_category(headline)
        self.assertEqual(category, "Earnings Call")

    def test_classify_category_results_strong_term(self):
        """Test classify category results strong term.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        headline = "Unaudited Financial Results for quarter ended December 31, 2025"
        category = self.alert_service._classify_category(headline)
        self.assertEqual(category, "Results")

    def test_sync_portfolio_filings_uses_targeted_announcements_not_global_recent_slice(self):
        """Test sync portfolio filings uses targeted announcements not global recent slice.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        user_id = self.db.create_user("9999999997", "Targeted Filings", "hash")
        stock_id = self.db.add_stock(user_id, "GOODLUCK", "Goodluck India Limited", "NSE")
        symbol_id = self.db.upsert_symbol_master(
            symbol="GOODLUCK",
            company_name="Goodluck India Limited",
            exchange="NSE",
            bse_code="530655",
            nse_code="GOODLUCK",
            source="TEST"
        )

        # Portfolio-relevant material announcement.
        self.db.add_bse_announcement(
            symbol_id=symbol_id,
            scrip_code="530655",
            headline="GOODLUCK Q3 Results announced",
            category="BSE_API_CSV",
            announcement_date="2026-02-10T10:00:00",
            attachment_url="https://example.com/goodluck-q3",
            exchange_ref_id="goodluck-q3-ref",
            rss_guid="goodluck-q3-guid",
            raw_payload="{}"
        )

        # Large set of unrelated announcements that could crowd out global recent scans.
        for i in range(200):
            self.db.add_bse_announcement(
                symbol_id=None,
                scrip_code=f"9{i:05d}",
                headline=f"Unrelated company update {i}",
                category="BSE_API_CSV",
                announcement_date=f"2026-02-14T12:{i%60:02d}:00",
                attachment_url=f"https://example.com/unrelated-{i}",
                exchange_ref_id=f"unrelated-ref-{i}",
                rss_guid=f"unrelated-guid-{i}",
                raw_payload="{}"
            )

        upserted = self.alert_service.sync_portfolio_filings(user_id, limit=10, per_stock_limit=4)
        self.assertGreaterEqual(upserted, 1)

        filings = self.db.get_user_filings(user_id=user_id, limit=20)
        self.assertTrue(any(f["stock_id"] == stock_id for f in filings))


class TestAISummaryService(unittest.TestCase):
    """Test AI summary service"""
    
    def setUp(self):
        """Set up AI service"""
        self.ai_service = AISummaryService()
    
    def test_service_initialization(self):
        """Test AI service initializes without error"""
        self.assertIsNotNone(self.ai_service)
    
    def test_is_available(self):
        """Test checking if AI is available"""
        # This will be False unless API key is configured
        available = self.ai_service.is_available()
        self.assertIsInstance(available, bool)
    
    def test_extract_sentiment(self):
        """Test sentiment extraction"""
        positive_text = "SENTIMENT: POSITIVE - Strong growth expected"
        negative_text = "SENTIMENT: NEGATIVE - Declining revenues"
        neutral_text = "SENTIMENT: NEUTRAL - Stable performance"
        
        self.assertEqual(
            self.ai_service._extract_sentiment(positive_text),
            'POSITIVE'
        )
        self.assertEqual(
            self.ai_service._extract_sentiment(negative_text),
            'NEGATIVE'
        )
        self.assertEqual(
            self.ai_service._extract_sentiment(neutral_text),
            'NEUTRAL'
        )

    def test_extract_quick_financial_metrics_hint(self):
        """Test metric hint extraction for result-style text."""
        text = (
            "Revenue up 12% YoY and 3% QoQ. EBITDA margin improved. "
            "PAT rose 18% YoY. EPS at 45.2. One-off tax gain reported."
        )
        hint = self.ai_service._extract_quick_financial_metrics(text)
        self.assertIn("Revenue:", hint)
        self.assertIn("EBITDA:", hint)
        self.assertIn("PAT:", hint)
        self.assertIn("EPS:", hint)
        self.assertIn("Special hint:", hint)

    def test_financial_result_parser_extracts_key_metrics(self):
        """Parser should extract metric lines with hints from text blob."""
        text = (
            "Revenue from operations stood at INR 712 crore, up 12.4% YoY and 3.1% QoQ. "
            "EBITDA at INR 46.1 crore, margin improved. "
            "Profit after tax (PAT) at INR 29.6 crore, up 8.5% YoY. "
            "EPS at Rs 5.2 for the quarter. Exceptional item: tax credit reversal."
        )
        parsed = FinancialResultParser.parse_from_text(text)
        self.assertEqual(parsed["Revenue"]["value"].lower().startswith("inr 712"), True)
        self.assertIn("Cr", parsed["Revenue"]["value_crore"])
        self.assertIn("yoy", parsed["Revenue"]["yoy"].lower())
        self.assertIn("qoq", parsed["Revenue"]["qoq"].lower())
        self.assertNotEqual(parsed["PAT"]["value"], "NA")
        self.assertNotEqual(parsed["EPS"]["value"], "NA")
        self.assertIn("special", FinancialResultParser.to_prompt_hint(parsed).lower())

    def test_financial_result_parser_normalizes_lakh_and_negative_brackets(self):
        """Lakhs should normalize to crores and bracket values should become negative."""
        text = (
            "Statement of unaudited results (Rs in Lakhs). "
            "Revenue from operations 12,500. EBITDA (590). "
            "Profit after tax (PAT) (310). EPS (2.4). Exceptional items (250)."
        )
        parsed = FinancialResultParser.parse_from_text(text)
        self.assertEqual(parsed["Revenue"]["value_crore"], "125.00 Cr")
        self.assertTrue(parsed["EBITDA"]["value"].startswith("(590"))
        self.assertEqual(parsed["EBITDA"]["value_crore"], "-5.90 Cr")
        self.assertEqual(parsed["PAT"]["value_crore"], "-3.10 Cr")
        self.assertIn("Validation:", FinancialResultParser.to_prompt_hint(parsed))

    def test_financial_result_parser_table_column_resolution_and_calc(self):
        """Should pick latest quarter column and compute YoY/QoQ from table values."""
        table = [
            ["Particulars", "Q3 FY26 Unaudited", "Q2 FY26 Unaudited", "Q3 FY25 Unaudited"],
            ["Revenue from operations", "712.0", "650.0", "635.0"],
            ["EBITDA", "46.1", "40.0", "38.2"],
            ["Profit after tax", "29.6", "24.0", "22.5"],
            ["Earnings per share", "5.2", "4.1", "3.9"],
            ["Exceptional items", "12.0", "0.0", "0.0"],
        ]
        parsed = FinancialResultParser._parse_from_table_rows(table)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["Quarter Label"], "Q3 FY26")
        self.assertEqual(parsed["Revenue"]["value"], "712.0")
        self.assertIn("QoQ", parsed["Revenue"]["qoq"])
        self.assertIn("YoY", parsed["Revenue"]["yoy"])
        hint = FinancialResultParser.to_prompt_hint(parsed)
        self.assertIn("Detected Quarter: Q3 FY26", hint)
        self.assertIn("Validation:", hint)

    def test_results_prompt_uses_structured_parser_hints(self):
        """Results prompt should include parser-derived structured hints."""
        text = (
            "Total income INR 500 crore; 10% YoY and 2% QoQ. "
            "EBITDA INR 80 crore. PAT INR 45 crore. EPS Rs 4.5."
        )
        prompt = self.ai_service._create_results_prompt("ABC", text, "Results")
        self.assertIn("Revenue:", prompt)
        self.assertIn("EBITDA:", prompt)
        self.assertIn("PAT:", prompt)
        self.assertIn("EPS:", prompt)

    def test_prompt_branching_results_vs_non_results(self):
        """Test prompt branching results vs non results.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        results_prompt = self.ai_service._create_prompt("ABC", "Unaudited financial results text", "Results")
        non_results_prompt = self.ai_service._create_prompt("ABC", "Investor call transcript text", "Earnings Call")
        self.assertIn("Result Summary", results_prompt)
        self.assertIn("Summary:", non_results_prompt)

    def test_generate_summary_uses_cache_when_db_available(self):
        """Test generate summary uses cache when db available.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        db = DatabaseManager(":memory:")
        ai = AISummaryService(db_manager=db)
        ai.provider = "groq"
        ai.client = object()
        ai._generate_groq_summary = MagicMock(return_value={
            "summary_text": "Summary:\n- Cached response",
            "sentiment": "NEUTRAL",
            "provider": "groq",
        })

        first = ai.generate_summary("ABC", "Some filing text", "ANNOUNCEMENT", document_url=None)
        second = ai.generate_summary("ABC", "Some filing text", "ANNOUNCEMENT", document_url=None)

        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertEqual(ai._generate_groq_summary.call_count, 1)
        self.assertTrue(second.get("cache_hit"))

    def test_generate_analyst_consensus_uses_analyst_provider_override(self):
        """Test generate analyst consensus uses analyst provider override.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        db = DatabaseManager(":memory:")
        ai = AISummaryService(db_manager=db)
        ai.provider = "ollama"
        ai.client = True
        with patch.object(config, "ANALYST_AI_PROVIDER", "groq"), patch.object(
            ai, "_generate_with_cache_for_provider"
        ) as gen_override:
            gen_override.return_value = {
                "summary_text": "Analyst consensus",
                "sentiment": "NEUTRAL",
                "provider": "groq",
            }
            result = ai.generate_analyst_consensus("ABC Ltd", "ABC")
        self.assertIsNotNone(result)
        kwargs = gen_override.call_args.kwargs
        self.assertEqual(kwargs.get("provider"), "groq")

    @patch("services.ai_summary_service.PdfReader")
    @patch("services.ai_summary_service.requests.get")
    def test_extract_pdf_text_from_url_in_memory(self, mock_get, mock_pdf_reader):
        """PDF text extraction should parse response bytes in memory."""
        page = MagicMock()
        page.extract_text.return_value = "Revenue 1000 | EBITDA 200"
        reader_instance = MagicMock()
        reader_instance.pages = [page]
        mock_pdf_reader.return_value = reader_instance

        response = MagicMock()
        response.content = b"%PDF-1.4 dummy"
        response.raise_for_status.return_value = None
        mock_get.return_value = response

        text = self.ai_service._extract_pdf_text_from_url("https://example.com/doc.pdf")
        self.assertIn("Revenue 1000", text)

    @patch("services.ai_summary_service.PdfReader")
    @patch("services.ai_summary_service.requests.get")
    def test_extract_pdf_text_falls_back_to_secondary_link(self, mock_get, mock_pdf_reader):
        """Test extract pdf text falls back to secondary link.

        Args:
            mock_get: Input parameter.
            mock_pdf_reader: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        page = MagicMock()
        page.extract_text.return_value = "PAT 120 | EPS 4.2"
        reader_instance = MagicMock()
        reader_instance.pages = [page]
        mock_pdf_reader.return_value = reader_instance

        primary_fail = MagicMock()
        primary_fail.raise_for_status.side_effect = Exception("404")
        secondary_ok = MagicMock()
        secondary_ok.content = b"%PDF-1.4 dummy"
        secondary_ok.raise_for_status.return_value = None
        mock_get.side_effect = [primary_fail, secondary_ok]

        text = self.ai_service._extract_pdf_text_from_url("https://example.com/abcd-1234.pdf")
        self.assertIn("PAT 120", text)
        self.assertGreaterEqual(mock_get.call_count, 2)

    @patch("services.ai_summary_service.requests.post")
    def test_ollama_model_fallback_uses_secondary_model(self, mock_post):
        """Test ollama model fallback uses secondary model.

        Args:
            mock_post: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        ai = AISummaryService()
        ai.provider = "ollama"
        ai.client = True

        first_fail = MagicMock()
        first_fail.raise_for_status.side_effect = Exception("model load failed")

        second_ok = MagicMock()
        second_ok.raise_for_status.return_value = None
        second_ok.json.return_value = {"message": {"content": "Summary:\n- Fallback worked"}}
        mock_post.side_effect = [first_fail, second_ok]

        with patch.object(config, "OLLAMA_MODEL", "qwen2.5:14b"), patch.object(
            config, "OLLAMA_FALLBACK_MODELS", ["gemma3:4b"]
        ), patch.object(config, "OLLAMA_TIMEOUT_PRIMARY_SEC", 150), patch.object(
            config, "OLLAMA_TIMEOUT_FALLBACK_SEC", 45
        ):
            result = ai._generate_ollama_summary("test prompt", max_tokens=120)

        self.assertIsNotNone(result)
        self.assertEqual(result.get("provider"), "ollama")
        self.assertEqual(result.get("model"), "gemma3:4b")
        self.assertEqual(mock_post.call_count, 2)
        self.assertEqual(mock_post.call_args_list[0].kwargs.get("timeout"), 150)
        self.assertEqual(mock_post.call_args_list[1].kwargs.get("timeout"), 45)

    def test_prompt_file_missing_uses_builtin_fallback(self):
        """Missing prompt file should not break prompt creation."""
        ai = AISummaryService()
        ai._prompt_file_path = Path("/tmp/non_existent_prompt_file.md")
        ai._load_prompt_config()
        prompt = ai._create_prompt("ABC", "Result text", "Results")
        self.assertIn("Result Summary", prompt)
        self.assertIn("ABC", prompt)

    def test_prompt_file_custom_template_is_loaded_and_rendered(self):
        """Custom prompt file should render governance + template placeholders."""
        content = """# System Prompt
Always be precise.

# Tool Usage Policy
Only use provided content.

## Results
```prompt
Custom Results for {stock_symbol}
Type: {announcement_type}
Body: {announcement_text}
Hint: {quick_metrics_hint}
```
"""
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)
        try:
            ai = AISummaryService()
            ai._prompt_file_path = tmp_path
            ai._load_prompt_config()
            prompt = ai._create_prompt("XYZ", "Quarterly filing body", "Results")
            self.assertIn("System Prompt:", prompt)
            self.assertIn("Always be precise.", prompt)
            self.assertIn("Custom Results for XYZ", prompt)
            self.assertIn("Type: Results", prompt)
        finally:
            try:
                tmp_path.unlink()
            except Exception:
                pass

    def test_prompt_file_malformed_template_falls_back(self):
        """Malformed template block should fall back to built-in prompt text."""
        bad_content = """# System Prompt
Be strict.

## Results
No fenced prompt block here
"""
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as tmp:
            tmp.write(bad_content)
            tmp_path = Path(tmp.name)
        try:
            ai = AISummaryService()
            ai._prompt_file_path = tmp_path
            ai._load_prompt_config()
            prompt = ai._create_prompt("ABC", "Some results text", "Results")
            self.assertIn("Result Summary", prompt)
            self.assertNotIn("No fenced prompt block here", prompt)
        finally:
            try:
                tmp_path.unlink()
            except Exception:
                pass


class TestResearchDataLayer(unittest.TestCase):
    """Test symbol master, financial schema operations, and BSE feed ingestion."""

    def setUp(self):
        """Setup.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        self.db = DatabaseManager(':memory:')
        self.symbol_service = SymbolMasterService(self.db)
        self.bse_service = BSEFeedService(self.db)
        self.bhav_service = BSEBhavcopyService(self.db)

    def test_symbol_master_population_and_search(self):
        """Test symbol master population and search.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        rows = [
            {"symbol": "RELIANCE", "company_name": "Reliance Industries Ltd", "exchange": "NSE", "bse_code": "500325"},
            {"symbol": "TCS", "company_name": "Tata Consultancy Services Ltd", "exchange": "NSE", "bse_code": "532540"},
        ]
        written = self.symbol_service.populate_symbols_from_rows(rows, source="TEST")
        self.assertEqual(written, 2)

        matches = self.symbol_service.search("RELI", limit=10)
        self.assertGreaterEqual(len(matches), 1)
        self.assertEqual(matches[0]["symbol"], "RELIANCE")

    def test_symbol_master_population_from_nsetools_adapter(self):
        """Test symbol master population from nsetools adapter.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        class FakeNSEAdapter:
            def fetch_symbol_rows(self):
                """Fetch symbol rows.

                Args:
                    None.

                Returns:
                    Any: Method output for caller use.
                """
                return [
                    {"symbol": "INFY", "company_name": "Infosys Ltd", "exchange": "NSE"},
                    {"symbol": "HDFCBANK", "company_name": "HDFC Bank Ltd", "exchange": "NSE"},
                ]

        written = self.symbol_service.populate_symbols_from_nsetools(adapter=FakeNSEAdapter())
        self.assertEqual(written, 2)

        infy = self.db.get_symbol_by_symbol("INFY")
        self.assertIsNotNone(infy)
        self.assertEqual(infy["exchange"], "NSE")

    def test_symbol_master_population_from_bse_csv_headers(self):
        """Test symbol master population from bse csv headers.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        csv_text = """Security Code,Issuer Name,Security Id,Security Name,Status,Group,Face Value,ISIN No,Instrument
500325,Reliance Industries Limited,RELIANCE,Reliance Industries Ltd,Active,A,10,INE002A01018,Equity
532540,Tata Consultancy Services Limited,TCS,Tata Consultancy Services Ltd,Active,A,1,INE467B01029,Equity
"""
        written = self.symbol_service.populate_symbols_from_csv_text(csv_text, source="BSE_CSV_TEST")
        self.assertEqual(written, 2)

        reliance = self.db.get_symbol_by_symbol("RELIANCE")
        self.assertIsNotNone(reliance)
        self.assertEqual(reliance["bse_code"], "500325")
        self.assertEqual(reliance["nse_code"], "RELIANCE")

    def test_quarterly_financials_and_ratios_upsert(self):
        """Test quarterly financials and ratios upsert.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        symbol_id = self.db.upsert_symbol_master(
            symbol="AAPL",
            company_name="Apple Inc",
            exchange="NASDAQ",
            source="TEST"
        )

        result_id = self.db.upsert_quarterly_financials(
            symbol_id=symbol_id,
            fiscal_year=2025,
            fiscal_quarter="Q2",
            period_end_date="2025-06-30",
            total_sales=1000.0,
            ebitda=200.0,
            eps=5.5
        )
        self.assertIsNotNone(result_id)

        ratio_id = self.db.upsert_financial_ratios(
            symbol_id=symbol_id,
            as_of_date="2026-02-13",
            eps_ttm=20.0,
            book_value_per_share=50.0,
            total_sales_ttm=4000.0,
            ebitda_ttm=800.0,
            enterprise_value=100000.0,
            pe_ratio=30.0,
            pb_ratio=6.0,
            ps_ratio=10.0,
            ev_to_ebitda=12.5,
            close_price=600.0,
            source="TEST"
        )
        self.assertIsNotNone(ratio_id)

        quarterly = self.db.get_quarterly_financials(symbol_id=symbol_id, limit=8)
        self.assertEqual(len(quarterly), 1)
        self.assertEqual(quarterly[0]["fiscal_quarter"], "Q2")

        latest_ratio = self.db.get_latest_financial_ratios(symbol_id=symbol_id)
        self.assertIsNotNone(latest_ratio)
        self.assertEqual(latest_ratio["pe_ratio"], 30.0)

    @patch("services.bse_feed_service.requests.get")
    def test_bse_rss_ingestion(self, mock_get):
        """Test bse rss ingestion.

        Args:
            mock_get: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
<rss><channel>
  <item>
    <title>Company Update - Scrip Code 500325</title>
    <link>https://example.com/announcement/500325</link>
    <guid>guid-500325</guid>
    <pubDate>Fri, 13 Feb 2026 10:00:00 GMT</pubDate>
    <description>Quarterly result posted</description>
  </item>
</channel></rss>
"""
        mock_response = MagicMock()
        mock_response.content = rss_xml.encode("utf-8")
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        ingested = self.bse_service.ingest_rss_feed("https://example.com/rss.xml")
        self.assertEqual(ingested, 1)

        pending = self.bse_service.get_unprocessed(limit=10)
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["rss_guid"], "guid-500325")
        self.assertEqual(pending[0]["scrip_code"], "500325")

    def test_bse_announcement_upsert_handles_exchange_ref_conflict(self):
        """Upsert should not fail when exchange_ref_id repeats with changed rss_guid."""
        id1 = self.db.add_bse_announcement(
            headline="First headline",
            exchange_ref_id="ref-123",
            rss_guid="guid-123-a",
            attachment_url="https://example.com/a"
        )
        self.assertIsNotNone(id1)

        id2 = self.db.add_bse_announcement(
            headline="Updated headline",
            exchange_ref_id="ref-123",
            rss_guid="guid-123-b",
            attachment_url="https://example.com/b"
        )
        self.assertEqual(id2, id1)

        rows = self.db.get_recent_bse_announcements(limit=10)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["headline"], "Updated headline")

    def test_bse_bhavcopy_ingest_rows_camel_case(self):
        """Test bse bhavcopy ingest rows camel case.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        rows = [
            {
                "scripCode": "530655",
                "trade_date": "2026-02-14",
                "open": 100.0,
                "high": 110.0,
                "low": 95.0,
                "close": 108.0,
                "totalSharesTraded": 123456,
                "totalTrades": 789,
                "netTurnover": 1234567.0,
            }
        ]
        count = self.bhav_service.ingest_rows(rows)
        self.assertEqual(count, 1)
        stored = self.db.get_bse_daily_prices("530655", limit=5)
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]["close_price"], 108.0)

    @patch("services.bse_bhavcopy_service.requests.get")
    def test_bse_bhavcopy_fetch_and_ingest_direct_csv(self, mock_get):
        """Test bse bhavcopy fetch and ingest direct csv.

        Args:
            mock_get: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        csv_text = (
            "FinInstrmId,TradDt,OpnPric,HghPric,LwPric,ClsPric,TtlTradgVol,TtlNbTrad,TtlTrfVal\n"
            "530655,20260214,100,110,95,108,123456,789,1234567\n"
        )
        response = MagicMock()
        response.status_code = 200
        response.content = csv_text.encode("utf-8")
        response.raise_for_status.return_value = None
        mock_get.return_value = response

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict(os.environ, {"BSE_BHAVCOPY_CACHE_DIR": tmp_dir}, clear=False):
                service = BSEBhavcopyService(self.db)
                count = service.fetch_and_ingest_date(datetime.strptime("2026-02-14", "%Y-%m-%d").date())
                self.assertEqual(count, 1)

                cached_file = os.path.join(tmp_dir, "BhavCopy_BSE_CM_0_0_0_20260214_F_0000.csv")
                self.assertTrue(os.path.exists(cached_file))

                mock_get.reset_mock()
                count_cached = service.fetch_and_ingest_date(datetime.strptime("2026-02-14", "%Y-%m-%d").date())
                self.assertEqual(count_cached, 1)
                self.assertFalse(mock_get.called)

        stored = self.db.get_bse_daily_prices("530655", limit=5)
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]["close_price"], 108.0)
        self.assertEqual(stored[0]["trade_date"], "2026-02-14")

    @patch("services.bse_feed_service.requests.get")
    def test_bse_api_ingestion_uses_expected_params_and_pagination(self, mock_get):
        """Test bse api ingestion uses expected params and pagination.

        Args:
            mock_get: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        page_1 = MagicMock()
        page_1.status_code = 200
        page_1.raise_for_status.return_value = None
        page_1.json.return_value = {
            "Table": [
                {
                    "SCRIP_CD": "500325",
                    "HEADLINE": "RELIANCE quarterly results announced",
                    "NEWS_DT": "2026-02-14T10:00:00",
                    "ATTACHMENTNAME": "https://example.com/r.pdf",
                    "NEWSID": "news-1",
                }
            ]
        }

        page_2 = MagicMock()
        page_2.status_code = 200
        page_2.raise_for_status.return_value = None
        page_2.json.return_value = {"Table": []}

        mock_get.side_effect = [page_1, page_2]

        ingested = self.bse_service.ingest_api_range(
            api_url=None,
            start_date_yyyymmdd="20260201",
            end_date_yyyymmdd="20260214",
            max_pages=5,
        )
        self.assertEqual(ingested, 1)

        first_call = mock_get.call_args_list[0]
        self.assertEqual(
            first_call.kwargs["params"]["strScrip"],
            ""
        )
        self.assertEqual(
            first_call.kwargs["params"]["subcategory"],
            ""
        )
        self.assertEqual(
            first_call.kwargs["params"]["strPrevDate"],
            "20260201"
        )
        self.assertEqual(
            first_call.kwargs["params"]["strToDate"],
            "20260214"
        )

        rows = self.db.get_recent_bse_announcements(limit=10)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["headline"], "RELIANCE quarterly results announced")


class TestWatchmanService(unittest.TestCase):
    def setUp(self):
        """Setup.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        self.db = DatabaseManager(":memory:")
        self.user_id = self.db.create_user("9111111111", "Watchman User", "hash")
        self.symbol_id = self.db.upsert_symbol_master(
            symbol="GOODLUCK",
            company_name="Goodluck India Limited",
            exchange="NSE",
            nse_code="GOODLUCK",
            source="TEST",
        )
        self.stock_id = self.db.add_stock(self.user_id, "GOODLUCK", "Goodluck India Limited", "NSE")
        self.ai = MagicMock()
        self.ai.provider = "test"
        self.ai.generate_summary.return_value = {
            "summary_text": "Result Summary\nRevenue: NA | YoY: NA | QoQ: NA",
            "sentiment": "NEUTRAL",
            "provider": "test",
        }
        self.watchman = WatchmanService(self.db, self.ai)

    def _seed_filing(self, category: str, headline: str, dt: str, ref: str):
        """Seed filing.

        Args:
            category: Input parameter.
            headline: Input parameter.
            dt: Input parameter.
            ref: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        self.db.upsert_filing(
            stock_id=self.stock_id,
            symbol_id=None,
            category=category,
            headline=headline,
            announcement_summary=headline,
            announcement_date=dt,
            pdf_link=f"https://example.com/{ref}.pdf",
            source_exchange="BSE",
            source_ref=ref,
        )

    def test_generates_two_snapshots_for_latest_quarter(self):
        """Test generates two snapshots for latest quarter.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        self._seed_filing("Results", "Q3 FY26 financial results", "2026-02-14", "res-q3")
        self._seed_filing("Earnings Call", "Q3 FY26 conference call transcript", "2026-02-16", "cc-q3")
        result = self.watchman.run_for_user(self.user_id, force_regenerate=False)
        self.assertEqual(result["generated"], 2)

        snapshots = self.db.get_user_global_insight_snapshots(self.user_id)
        types = {s["insight_type"] for s in snapshots}
        self.assertIn(WatchmanService.INSIGHT_RESULT, types)
        self.assertIn(WatchmanService.INSIGHT_CONCALL, types)
        self.assertTrue(all(s["quarter_label"] == "Q3 FY26" for s in snapshots))

    def test_no_regeneration_when_snapshot_exists(self):
        """Test no regeneration when snapshot exists.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        self._seed_filing("Results", "Q3 FY26 financial results", "2026-02-14", "res-q3")
        self._seed_filing("Earnings Call", "Q3 FY26 conference call transcript", "2026-02-16", "cc-q3")
        first = self.watchman.run_for_user(self.user_id, force_regenerate=False)
        second = self.watchman.run_for_user(self.user_id, force_regenerate=False)
        self.assertEqual(first["generated"], 2)
        self.assertGreaterEqual(second["skipped_existing"], 2)

    def test_daily_run_runs_once(self):
        """Test daily run runs once.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        self._seed_filing("Results", "Q3 FY26 financial results", "2026-02-14", "res-q3")
        self._seed_filing("Earnings Call", "Q3 FY26 conference call transcript", "2026-02-16", "cc-q3")
        first = self.watchman.run_daily_if_due(self.user_id)
        second = self.watchman.run_daily_if_due(self.user_id)
        self.assertIsNotNone(first)
        self.assertIsNone(second)

    def test_result_prefers_financial_result_over_call_notice(self):
        """Test result prefers financial result over call notice.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        self._seed_filing("Results", "Board meeting notice for conference call", "2026-02-12", "res-notice")
        self._seed_filing("Results", "Q3 FY26 financial results standalone and consolidated", "2026-02-14", "res-final")
        result = self.watchman.run_for_user(self.user_id, force_regenerate=False)
        self.assertEqual(result["generated"], 1)

        snapshot = self.db.get_global_insight_snapshot(self.symbol_id, "Q3 FY26", WatchmanService.INSIGHT_RESULT)
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot["source_ref"], "res-final")

    def test_concall_skips_generic_notice_without_transcript_or_recording(self):
        """Test concall skips generic notice without transcript or recording.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        self._seed_filing("Earnings Call", "Investor call notice for Q3 FY26", "2026-02-15", "cc-notice")
        result = self.watchman.run_for_user(self.user_id, force_regenerate=False)
        self.assertEqual(result["generated"], 0)
        self.assertEqual(result["not_available"], 2)

        snapshot = self.db.get_global_insight_snapshot(self.symbol_id, "Q3 FY26", WatchmanService.INSIGHT_CONCALL)
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot["status"], "NOT_AVAILABLE")

    def test_results_retries_next_candidate_when_first_summary_is_all_na(self):
        """Test results retries next candidate when first summary is all na.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        self._seed_filing("Results", "Q3 FY26 financial results - short update", "2026-02-14", "res-short")
        self._seed_filing("Results", "Q3 FY26 investor presentation with detailed financials", "2026-02-15", "res-ppt")
        self._seed_filing("Earnings Call", "Q3 FY26 conference call transcript", "2026-02-16", "cc-q3")

        self.ai.generate_summary.side_effect = [
            {
                "summary_text": (
                    "Result Summary\n"
                    "Revenue: NA | YoY: NA | QoQ: NA\n"
                    "EBITDA: NA | YoY: NA | QoQ: NA\n"
                    "PAT: NA | YoY: NA | QoQ: NA\n"
                    "EPS: NA | YoY: NA | QoQ: NA\n"
                ),
                "sentiment": "NEUTRAL",
                "provider": "test",
            },
            {
                "summary_text": (
                    "Result Summary\n"
                    "Revenue: 100 | YoY: 10% | QoQ: 2%\n"
                    "EBITDA: 20 | YoY: 8% | QoQ: 1%\n"
                    "PAT: 10 | YoY: 5% | QoQ: 1%\n"
                    "EPS: 3.2 | YoY: 4% | QoQ: 1%\n"
                ),
                "sentiment": "POSITIVE",
                "provider": "test",
            },
            {
                "summary_text": "Summary:\n- Good call insights.",
                "sentiment": "NEUTRAL",
                "provider": "test",
            },
        ]
        result = self.watchman.run_for_user(self.user_id, force_regenerate=False)
        self.assertEqual(result["generated"], 2)

        snapshot = self.db.get_global_insight_snapshot(self.symbol_id, "Q3 FY26", WatchmanService.INSIGHT_RESULT)
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot["source_ref"], "res-ppt")
        self.assertIn("Revenue: 100", snapshot["summary_text"])

    def test_daily_material_scan_creates_short_material_alert(self):
        self.db.add_bse_announcement(
            symbol_id=self.symbol_id,
            scrip_code="530655",
            headline="GOODLUCK receives new export order for steel structures worth Rs 180 crore",
            category="Announcement",
            announcement_date="2026-02-20",
            attachment_url="https://example.com/material.pdf",
            exchange_ref_id="mat-1",
            rss_guid="mat-1",
        )
        result = self.watchman.run_daily_material_scan(self.user_id, daily_only=True)
        self.assertEqual(result["alerts_created"], 1)

        notifs = self.db.get_user_notifications(self.user_id, unread_only=False, limit=10)
        material = next((n for n in notifs if n["notif_type"] == "MATERIAL_ALERT"), None)
        self.assertIsNotNone(material)
        self.assertIn("Company: Goodluck India Limited", material["message"])
        summary_line = next((line for line in material["message"].splitlines() if line.startswith("🧾Summary:")), "")
        self.assertTrue(summary_line)
        summary_words = summary_line.replace("🧾Summary:", "").strip().replace("...", "").split()
        self.assertLessEqual(len(summary_words), 20)

    def test_daily_material_scan_runs_once_per_day(self):
        self.db.add_bse_announcement(
            symbol_id=self.symbol_id,
            scrip_code="530655",
            headline="GOODLUCK announces joint venture agreement with global partner",
            category="Announcement",
            announcement_date="2026-02-20",
            attachment_url="https://example.com/jv.pdf",
            exchange_ref_id="mat-2",
            rss_guid="mat-2",
        )
        first = self.watchman.run_daily_material_scan(self.user_id, daily_only=True)
        second = self.watchman.run_daily_material_scan(self.user_id, daily_only=True)
        self.assertEqual(first["skipped_daily"], 0)
        self.assertEqual(second["skipped_daily"], 1)


def run_tests():
    """Run all unit tests"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestAuthService))
    suite.addTests(loader.loadTestsFromTestCase(TestStockService))
    suite.addTests(loader.loadTestsFromTestCase(TestDatabaseManager))
    suite.addTests(loader.loadTestsFromTestCase(TestAlertService))
    suite.addTests(loader.loadTestsFromTestCase(TestAISummaryService))
    suite.addTests(loader.loadTestsFromTestCase(TestResearchDataLayer))
    suite.addTests(loader.loadTestsFromTestCase(TestWatchmanService))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return success/failure
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
