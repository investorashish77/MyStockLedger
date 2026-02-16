"""
EQUITY TRACKER - Installation Verification Test
================================================
Run this script to verify your installation is correct.
"""

import sys
from pathlib import Path

def test_python_version():
    """Test Python version"""
    print("\n[1/7] Testing Python version...", end=" ")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 8:
        print(f"✓ ({version.major}.{version.minor})")
        return True
    else:
        print(f"✗ ({version.major}.{version.minor} - Need 3.8+)")
        return False

def test_imports():
    """Test if all required packages can be imported"""
    print("[2/7] Testing package imports...")
    
    packages = {
        'PyQt5': 'PyQt5',
        'requests': 'requests',
        'dotenv': 'python-dotenv',
        'yfinance': 'yfinance',
        'bs4': 'beautifulsoup4',
        'pandas': 'pandas',
        'schedule': 'schedule',
        'cryptography': 'cryptography',
    }
    
    all_good = True
    for module, package in packages.items():
        try:
            __import__(module)
            print(f"  ✓ {package}")
        except ImportError:
            print(f"  ✗ {package} - NOT INSTALLED")
            all_good = False
    
    return all_good

def test_optional_imports():
    """Test optional AI packages"""
    print("[3/7] Testing AI packages (optional)...")
    
    optional = {
        'anthropic': 'Claude AI',
        'groq': 'Groq AI',
        'nsetools': 'nsetools (NSE adapter)',
    }
    
    for module, name in optional.items():
        try:
            __import__(module)
            print(f"  ✓ {name} available")
        except ImportError:
            print(f"  ⚠ {name} not installed (optional)")
    
    return True  # Optional packages don't fail the test

def test_project_structure():
    """Test if project folders exist"""
    print("[4/7] Testing project structure...", end=" ")
    
    required_folders = ['database', 'services', 'ui', 'utils', 'data']
    project_root = Path.cwd()
    
    missing = []
    for folder in required_folders:
        if not (project_root / folder).exists():
            missing.append(folder)
    
    if not missing:
        print("✓")
        return True
    else:
        print(f"✗ Missing: {', '.join(missing)}")
        return False

def test_database():
    """Test if database exists and is accessible"""
    print("[5/7] Testing database...", end=" ")
    
    db_path = Path.cwd() / 'data' / 'equity_tracker.db'
    if not db_path.exists():
        print("✗ Database file not found")
        return False
    
    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        required_tables = ['users', 'stocks', 'transactions', 'alerts', 'ai_summaries', 'price_history']
        missing_tables = [t for t in required_tables if t not in tables]
        
        conn.close()
        
        if not missing_tables:
            print(f"✓ ({len(tables)} tables)")
            return True
        else:
            print(f"✗ Missing tables: {', '.join(missing_tables)}")
            return False
    
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_config_files():
    """Test if configuration files exist"""
    print("[6/7] Testing configuration...", end=" ")
    
    env_file = Path.cwd() / '.env'
    if not env_file.exists():
        print("✗ .env file missing")
        return False
    
    print("✓")
    return True

def test_stock_data_access():
    """Test if we can fetch stock data"""
    print("[7/7] Testing stock data access...", end=" ")
    
    try:
        import yfinance as yf
        # Try to fetch a simple stock data point
        ticker = yf.Ticker("RELIANCE.NS")
        info = ticker.info
        if 'symbol' in info or 'currentPrice' in info:
            print("✓")
            return True
        else:
            print("⚠ Limited data access")
            return True  # Not a critical failure
    except Exception as e:
        print(f"⚠ Warning: {str(e)[:50]}")
        return True  # Network issues shouldn't fail the test

def main():
    """Run all tests"""
    print("="*60)
    print("  EQUITY TRACKER - Installation Verification")
    print("="*60)
    
    tests = [
        test_python_version,
        test_imports,
        test_optional_imports,
        test_project_structure,
        test_database,
        test_config_files,
        test_stock_data_access,
    ]
    
    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"✗ Test failed with error: {e}")
            results.append(False)
    
    # Summary
    print("\n" + "="*60)
    print("  TEST SUMMARY")
    print("="*60)
    
    passed = sum(results)
    total = len(results)
    
    print(f"\nPassed: {passed}/{total}")
    
    if all(results):
        print("\n✅ ALL TESTS PASSED!")
        print("\nYour installation is ready to use.")
        print("Run: python main.py")
    else:
        print("\n⚠️ SOME TESTS FAILED")
        print("\nPlease run setup_agent.py again or check INSTALL.md")
        return 1
    
    print("\n" + "="*60 + "\n")
    return 0

if __name__ == "__main__":
    sys.exit(main())
