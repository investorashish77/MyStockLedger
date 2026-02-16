#!/usr/bin/env python3
"""
Equity Tracker Test Runner
Runs all tests and generates a comprehensive report
"""

import sys
import os
import unittest
from io import StringIO

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def print_header(text):
    """Print a header"""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


def run_all_tests():
    """Run all test suites"""
    
    print_header("EQUITY TRACKER - AUTOMATED TEST SUITE")
    print("\nRunning comprehensive tests to ensure code quality...\n")
    
    all_passed = True
    test_results = []
    
    # Test 1: Import Tests
    print_header("Test Suite 1: Import Tests")
    print("Checking all modules can be imported without errors...")
    
    try:
        from tests.test_imports import run_import_tests
        import_result = run_import_tests()
        test_results.append(("Import Tests", import_result))
        
        if import_result:
            print("\n✅ PASSED: All imports successful")
        else:
            print("\n❌ FAILED: Some imports failed")
            all_passed = False
    except Exception as e:
        print(f"\n❌ ERROR: Import tests failed with exception: {e}")
        test_results.append(("Import Tests", False))
        all_passed = False
    
    # Test 2: Unit Tests
    print_header("Test Suite 2: Unit Tests")
    print("Testing individual components (services, database, etc.)...")
    
    try:
        from tests.test_services import run_tests
        unit_result = run_tests()
        test_results.append(("Unit Tests", unit_result))
        
        if unit_result:
            print("\n✅ PASSED: All unit tests successful")
        else:
            print("\n❌ FAILED: Some unit tests failed")
            all_passed = False
    except Exception as e:
        print(f"\n❌ ERROR: Unit tests failed with exception: {e}")
        test_results.append(("Unit Tests", False))
        all_passed = False
    
    # Test 3: Integration Tests
    print_header("Test Suite 3: Integration Tests")
    print("Testing end-to-end workflows...")
    
    try:
        from tests.test_integration import run_integration_tests
        integration_result = run_integration_tests()
        test_results.append(("Integration Tests", integration_result))
        
        if integration_result:
            print("\n✅ PASSED: All integration tests successful")
        else:
            print("\n❌ FAILED: Some integration tests failed")
            all_passed = False
    except Exception as e:
        print(f"\n❌ ERROR: Integration tests failed with exception: {e}")
        test_results.append(("Integration Tests", False))
        all_passed = False

    # Test 4: UI Tests
    print_header("Test Suite 4: UI Tests")
    print("Testing portfolio UI rendering scenarios...")

    try:
        from tests.test_ui_portfolio import run_ui_tests
        ui_result = run_ui_tests()
        test_results.append(("UI Tests", ui_result))

        if ui_result:
            print("\n✅ PASSED: All UI tests successful")
        else:
            print("\n❌ FAILED: Some UI tests failed")
            all_passed = False
    except Exception as e:
        print(f"\n❌ ERROR: UI tests failed with exception: {e}")
        test_results.append(("UI Tests", False))
        all_passed = False
    
    # Summary
    print_header("TEST SUMMARY")
    
    print("\nTest Results:")
    for test_name, result in test_results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"  {status} - {test_name}")
    
    print("\n" + "=" * 70)
    
    if all_passed:
        print("\n🎉 ALL TESTS PASSED!")
        print("\nYour application is ready to run:")
        print("  python3 main.py")
    else:
        print("\n⚠️  SOME TESTS FAILED")
        print("\nPlease fix the failing tests before running the application.")
        print("Run individual test suites for more details:")
        print("  python3 tests/test_imports.py")
        print("  python3 tests/test_services.py")
        print("  python3 tests/test_integration.py")
        print("  python3 tests/test_ui_portfolio.py")
    
    print("\n" + "=" * 70 + "\n")
    
    return all_passed


def run_quick_check():
    """Run a quick sanity check"""
    print_header("QUICK SANITY CHECK")
    print("Running quick checks to verify setup...\n")
    
    checks_passed = True
    
    # Check 1: Python version
    print("1. Checking Python version...", end=" ")
    if sys.version_info >= (3, 8):
        print("✅ OK (Python {}.{})".format(sys.version_info.major, sys.version_info.minor))
    else:
        print("❌ FAILED (Need Python 3.8+)")
        checks_passed = False
    
    # Check 2: Required packages
    print("2. Checking required packages...")
    required_packages = [
        ('PyQt5', 'PyQt5'),
        ('requests', 'requests'),
        ('yfinance', 'yfinance'),
        ('pandas', 'pandas'),
        ('dotenv', 'python-dotenv'),
    ]
    
    for package_name, install_name in required_packages:
        try:
            __import__(package_name)
            print(f"   ✅ {install_name}")
        except ImportError:
            print(f"   ❌ {install_name} (missing)")
            checks_passed = False

    optional_packages = [
        ('nsetools', 'nsetools'),
    ]
    for package_name, install_name in optional_packages:
        try:
            __import__(package_name)
            print(f"   ✅ {install_name} (optional)")
        except ImportError:
            print(f"   ⚠ {install_name} missing (optional for NSE adapter)")
    
    # Check 3: Project structure
    print("3. Checking project structure...", end=" ")
    required_dirs = ['database', 'services', 'ui', 'utils', 'data']
    project_root = os.path.dirname(os.path.dirname(__file__))
    
    missing_dirs = []
    for dir_name in required_dirs:
        if not os.path.isdir(os.path.join(project_root, dir_name)):
            missing_dirs.append(dir_name)
    
    if not missing_dirs:
        print("✅ OK")
    else:
        print(f"❌ FAILED (missing: {', '.join(missing_dirs)})")
        checks_passed = False
    
    # Check 4: Database
    print("4. Checking database...", end=" ")
    db_path = os.path.join(project_root, 'data', 'equity_tracker.db')
    if os.path.exists(db_path):
        print("✅ OK")
    else:
        print("⚠️  Not found (will be created on first run)")
    
    # Check 5: Environment file
    print("5. Checking .env file...", end=" ")
    env_path = os.path.join(project_root, '.env')
    if os.path.exists(env_path):
        print("✅ OK")
    else:
        print("⚠️  Not found (create from .env.template)")
    
    print()
    
    return checks_passed


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Run Equity Tracker tests')
    parser.add_argument('--quick', action='store_true', 
                       help='Run quick sanity check only')
    parser.add_argument('--imports', action='store_true',
                       help='Run import tests only')
    parser.add_argument('--unit', action='store_true',
                       help='Run unit tests only')
    parser.add_argument('--integration', action='store_true',
                       help='Run integration tests only')
    parser.add_argument('--ui', action='store_true',
                       help='Run UI tests only')
    
    args = parser.parse_args()
    
    if args.quick:
        success = run_quick_check()
    elif args.imports:
        from tests.test_imports import run_import_tests
        success = run_import_tests()
    elif args.unit:
        from tests.test_services import run_tests
        success = run_tests()
    elif args.integration:
        from tests.test_integration import run_integration_tests
        success = run_integration_tests()
    elif args.ui:
        from tests.test_ui_portfolio import run_ui_tests
        success = run_ui_tests()
    else:
        # Run all tests
        quick_ok = run_quick_check()
        if quick_ok:
            success = run_all_tests()
        else:
            print("\n❌ Quick check failed. Fix issues before running full tests.\n")
            success = False
    
    sys.exit(0 if success else 1)
