"""
Unit Tests for Equity Tracker Services
Tests all service layer functionality
"""

import unittest
import sys
import os
import tempfile
from datetime import datetime
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
        headline = "Transcript of Earnings Conference Call for Q3 FY26"
        category = self.alert_service._classify_category(headline)
        self.assertEqual(category, "Earnings Call")

    def test_classify_category_results_strong_term(self):
        headline = "Unaudited Financial Results for quarter ended December 31, 2025"
        category = self.alert_service._classify_category(headline)
        self.assertEqual(category, "Results")

    def test_sync_portfolio_filings_uses_targeted_announcements_not_global_recent_slice(self):
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

    def test_prompt_branching_results_vs_non_results(self):
        results_prompt = self.ai_service._create_prompt("ABC", "Unaudited financial results text", "Results")
        non_results_prompt = self.ai_service._create_prompt("ABC", "Investor call transcript text", "Earnings Call")
        self.assertIn("Result Summary", results_prompt)
        self.assertIn("Summary:", non_results_prompt)

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


class TestResearchDataLayer(unittest.TestCase):
    """Test symbol master, financial schema operations, and BSE feed ingestion."""

    def setUp(self):
        self.db = DatabaseManager(':memory:')
        self.symbol_service = SymbolMasterService(self.db)
        self.bse_service = BSEFeedService(self.db)
        self.bhav_service = BSEBhavcopyService(self.db)

    def test_symbol_master_population_and_search(self):
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
        class FakeNSEAdapter:
            def fetch_symbol_rows(self):
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
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return success/failure
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
