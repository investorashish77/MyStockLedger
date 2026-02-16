"""
Import Tests
Tests that all modules can be imported without errors
This catches issues like missing imports (e.g., QDialog)
"""

import unittest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TestImports(unittest.TestCase):
    """Test all modules can be imported"""
    
    def test_import_database_modules(self):
        """Test database modules import without errors"""
        try:
            from database.db_manager import DatabaseManager
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"Failed to import DatabaseManager: {e}")
    
    def test_import_service_modules(self):
        """Test service modules import without errors"""
        try:
            from services.auth_service import AuthService
            from services.stock_service import StockService
            from services.alert_service import AlertService
            from services.ai_summary_service import AISummaryService
            from services.symbol_master_service import SymbolMasterService
            from services.bse_feed_service import BSEFeedService
            from services.nsetools_adapter import NSEToolsAdapter
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"Failed to import service modules: {e}")
    
    def test_import_ui_modules(self):
        """Test UI modules import without errors"""
        try:
            # Test each UI module individually to catch specific import errors
            from ui.login_dialog import LoginDialog
            from ui.main_window import MainWindow
            from ui.portfolio_view import PortfolioView
            from ui.add_stock_dialog import AddStockDialog
            from ui.alerts_view import AlertsView
            from ui.summary_dialog import SummaryDialog
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"Failed to import UI modules: {e}")
        except NameError as e:
            self.fail(f"NameError in UI modules (missing import): {e}")
    
    def test_import_utils_modules(self):
        """Test utils modules import without errors"""
        try:
            from utils.config import config
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"Failed to import utils modules: {e}")
    
    def test_main_module(self):
        """Test main module imports"""
        try:
            # We can't import main directly as it starts the app
            # So we just check the file exists and has proper imports
            import ast
            main_path = os.path.join(
                os.path.dirname(__file__), '..', 'main.py'
            )
            
            with open(main_path, 'r') as f:
                code = f.read()
            
            # Try to parse it - this will catch syntax errors
            ast.parse(code)
            self.assertTrue(True)
        except SyntaxError as e:
            self.fail(f"Syntax error in main.py: {e}")
        except Exception as e:
            self.fail(f"Error checking main.py: {e}")


class TestRequiredClasses(unittest.TestCase):
    """Test that all required classes exist"""
    
    def test_database_classes_exist(self):
        """Test database classes exist"""
        from database.db_manager import DatabaseManager
        
        # Check methods exist
        self.assertTrue(hasattr(DatabaseManager, 'create_user'))
        self.assertTrue(hasattr(DatabaseManager, 'get_user_by_mobile'))
        self.assertTrue(hasattr(DatabaseManager, 'add_stock'))
    
    def test_service_classes_exist(self):
        """Test service classes exist"""
        from services.auth_service import AuthService
        from services.stock_service import StockService
        
        # Check methods exist
        self.assertTrue(hasattr(AuthService, 'login'))
        self.assertTrue(hasattr(AuthService, 'register_user'))
        self.assertTrue(hasattr(StockService, 'get_stock_info'))
        self.assertTrue(hasattr(StockService, 'get_current_price'))
    
    def test_ui_classes_exist(self):
        """Test UI classes exist"""
        from ui.login_dialog import LoginDialog
        from ui.main_window import MainWindow
        
        # Check they are QDialog/QMainWindow subclasses
        from PyQt5.QtWidgets import QDialog, QMainWindow
        
        # Check class hierarchy (don't instantiate to avoid GUI)
        self.assertTrue(issubclass(LoginDialog, QDialog))
        self.assertTrue(issubclass(MainWindow, QMainWindow))


class TestPyQt5Imports(unittest.TestCase):
    """Test PyQt5 imports are correct"""
    
    def test_main_window_imports(self):
        """Test MainWindow has all required imports"""
        try:
            from ui.main_window import MainWindow
            from PyQt5.QtWidgets import QDialog
            
            # If we can import both, the QDialog should be available
            self.assertTrue(True)
        except NameError as e:
            self.fail(f"Missing import in MainWindow: {e}")
    
    def test_all_ui_qt_imports(self):
        """Test all UI modules have required Qt imports"""
        ui_modules = [
            'ui.login_dialog',
            'ui.main_window',
            'ui.portfolio_view',
            'ui.add_stock_dialog',
            'ui.alerts_view',
            'ui.summary_dialog'
        ]
        
        for module_name in ui_modules:
            try:
                __import__(module_name)
            except NameError as e:
                self.fail(f"NameError in {module_name}: {e}")
            except ImportError as e:
                # PyQt5 might not be installed in test environment
                if 'PyQt5' not in str(e):
                    self.fail(f"ImportError in {module_name}: {e}")


def run_import_tests():
    """Run all import tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestImports))
    suite.addTests(loader.loadTestsFromTestCase(TestRequiredClasses))
    suite.addTests(loader.loadTestsFromTestCase(TestPyQt5Imports))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_import_tests()
    sys.exit(0 if success else 1)
