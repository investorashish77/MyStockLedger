# 🧪 Equity Tracker - Testing Guide

## Overview

This project includes a comprehensive test suite to ensure code quality and catch bugs early.

---

## 🎯 What the Tests Cover

### 1. **Import Tests** (`test_imports.py`)
- ✅ Verifies all modules can be imported without errors
- ✅ Catches missing imports (like the QDialog issue you found!)
- ✅ Checks all required classes exist
- ✅ Validates PyQt5 imports

### 2. **Unit Tests** (`test_services.py`)
- ✅ Tests individual components in isolation
- ✅ AuthService: login, registration, password hashing
- ✅ StockService: price fetching, P&L calculations
- ✅ DatabaseManager: all CRUD operations
- ✅ AlertService: alert creation and retrieval
- ✅ AISummaryService: sentiment extraction

### 3. **Integration Tests** (`test_integration.py`)
- ✅ Tests complete workflows
- ✅ User registration → login → portfolio management
- ✅ Add stock → add transaction → calculate P&L
- ✅ Create alerts → retrieve alerts → mark as read
- ✅ Multi-user scenarios

---

## 🚀 Running Tests

### Option 1: Run All Tests (Recommended)

```bash
cd ~/Desktop/equity-tracker  # or your project folder
python3 tests/run_tests.py
```

This will:
1. Run quick sanity check
2. Run import tests
3. Run unit tests
4. Run integration tests
5. Generate comprehensive report

### Option 2: Run Specific Test Suites

```bash
# Quick sanity check only
python3 tests/run_tests.py --quick

# Import tests only
python3 tests/run_tests.py --imports

# Unit tests only
python3 tests/run_tests.py --unit

# Integration tests only
python3 tests/run_tests.py --integration
```

### Option 3: Run Individual Test Files

```bash
# Import tests
python3 tests/test_imports.py

# Unit tests
python3 tests/test_services.py

# Integration tests
python3 tests/test_integration.py
```

---

## 📊 Understanding Test Output

### ✅ Successful Test Run

```
======================================================================
  EQUITY TRACKER - AUTOMATED TEST SUITE
======================================================================

Running comprehensive tests to ensure code quality...

======================================================================
  Test Suite 1: Import Tests
======================================================================
test_import_database_modules ... ok
test_import_service_modules ... ok
test_import_ui_modules ... ok
...

✅ PASSED: All imports successful

🎉 ALL TESTS PASSED!

Your application is ready to run:
  python3 main.py
```

### ❌ Failed Test Run

```
❌ FAILED: Some imports failed

FAILED (failures=1)

⚠️  SOME TESTS FAILED

Please fix the failing tests before running the application.
```

---

## 🐛 Common Test Failures and Fixes

### 1. Import Errors

**Error:**
```
ImportError: No module named 'PyQt5'
```

**Fix:**
```bash
pip3 install PyQt5 --break-system-packages
```

### 2. Missing __init__.py

**Error:**
```
ImportError: cannot import name 'DatabaseManager'
```

**Fix:**
Ensure all package folders have `__init__.py`:
```bash
touch database/__init__.py
touch services/__init__.py
touch ui/__init__.py
touch utils/__init__.py
```

### 3. Missing Imports in Files

**Error:**
```
NameError: name 'QDialog' is not defined
```

**Fix:**
The import tests will catch this! Check the test output for which file is missing imports.

---

## 📝 Adding New Tests

### When to Add Tests

- ✅ When adding a new feature
- ✅ When fixing a bug
- ✅ When refactoring code
- ✅ Before deploying to production

### How to Add Tests

1. **For new services:**
   Add tests to `tests/test_services.py`

2. **For new workflows:**
   Add tests to `tests/test_integration.py`

3. **For new modules:**
   Add import tests to `tests/test_imports.py`

### Example: Adding a Test

```python
# In tests/test_services.py

class TestMyNewFeature(unittest.TestCase):
    """Test my new feature"""
    
    def setUp(self):
        """Set up test environment"""
        self.db = DatabaseManager(':memory:')
    
    def test_feature_works(self):
        """Test that feature works correctly"""
        result = my_new_function()
        self.assertEqual(result, expected_value)
```

---

## 🔄 Continuous Testing Workflow

### Before Every Commit

```bash
python3 tests/run_tests.py
```

### Before Running the App

```bash
python3 tests/run_tests.py --quick
```

### When Fixing a Bug

1. Write a test that reproduces the bug
2. Run the test (it should fail)
3. Fix the bug
4. Run the test again (it should pass)
5. Run all tests to ensure nothing broke

---

## 📋 Test Checklist

Before running `python3 main.py`, ensure:

- [ ] Quick check passes: `python3 tests/run_tests.py --quick`
- [ ] Import tests pass: `python3 tests/run_tests.py --imports`
- [ ] Unit tests pass: `python3 tests/run_tests.py --unit`
- [ ] Integration tests pass: `python3 tests/run_tests.py --integration`
- [ ] All dependencies installed: `pip3 list`
- [ ] Database exists: `ls data/equity_tracker.db`
- [ ] Config file exists: `ls .env`

---

## 🎓 Test Coverage

Current test coverage:

| Component | Tests | Coverage |
|-----------|-------|----------|
| AuthService | 5 tests | Login, registration, validation |
| StockService | 3 tests | Price fetching, P&L calculation |
| DatabaseManager | 5 tests | All CRUD operations |
| AlertService | 2 tests | Alert management |
| AISummaryService | 3 tests | Sentiment extraction |
| UI Modules | 6 tests | Import validation |
| Integration | 5 suites | End-to-end workflows |

**Total: 29+ individual tests**

---

## 🚨 Critical Tests (Must Pass)

These tests MUST pass before running the app:

1. ✅ `test_import_ui_modules` - Catches missing imports like QDialog
2. ✅ `test_user_registration` - Ensures users can register
3. ✅ `test_user_login` - Ensures users can login
4. ✅ `test_add_stock_and_view_portfolio` - Core functionality
5. ✅ `test_complete_registration_login_workflow` - Full workflow

---

## 💡 Pro Tips

### Speed Up Testing

```bash
# Run only failed tests from last run
python3 tests/run_tests.py --failfast

# Run tests in parallel (if you have many)
python3 -m pytest tests/ -n auto
```

### Debugging Failed Tests

```bash
# Run with verbose output
python3 tests/test_services.py -v

# Run a specific test
python3 -m unittest tests.test_services.TestAuthService.test_user_login
```

### Test with Real Database

By default, tests use in-memory database (`:memory:`). To test with real database:

```python
# Change in test file
self.db = DatabaseManager('test_data/test.db')
```

---

## 📚 Additional Resources

- Python unittest docs: https://docs.python.org/3/library/unittest.html
- PyQt5 testing: https://doc.qt.io/qt-5/qtest-overview.html
- Test-driven development: https://en.wikipedia.org/wiki/Test-driven_development

---

## ✅ Next Steps

1. **Run the tests:**
   ```bash
   python3 tests/run_tests.py
   ```

2. **Fix any failures** following the error messages

3. **Run the app:**
   ```bash
   python3 main.py
   ```

4. **Add tests** when you add new features

---

## 🎉 Benefits of Testing

✅ Catch bugs before they reach users  
✅ Prevent regressions when refactoring  
✅ Document how code should work  
✅ Enable confident code changes  
✅ Improve code quality  
✅ Sleep better at night! 😴

---

**Happy Testing! 🧪📈**
