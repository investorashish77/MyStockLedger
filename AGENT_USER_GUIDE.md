# 🤖 Development Agent - User Guide

## What is the Development Agent?

The Development Agent is your **AI-powered coding assistant** that helps you build new features for the Equity Tracker app. Think of it as having an experienced developer who knows your codebase and can:

- ✅ Generate code templates for new features
- ✅ Show you exactly where to add code
- ✅ Provide step-by-step implementation guidance
- ✅ Run tests to verify everything works
- ✅ Help you understand the codebase

---

## 🚀 Quick Start

### Step 1: Run the Agent

```bash
cd ~/Desktop/equity-tracker  # or your project folder
python3 dev_agent.py
```

### Step 2: Choose What You Want to Do

You'll see a menu:
```
🤖 EQUITY TRACKER DEVELOPMENT AGENT

What would you like to do?

  1. 🎯 Implement a new feature
  2. ✏️  Edit existing code
  3. 🧪 Run tests
  4. 📖 Explain code
  5. 🗺️  View codebase structure
  6. 📋 View feature roadmap
  7. 💡 Get implementation help
  8. 🚪 Exit
```

### Step 3: Follow the Instructions

The agent will guide you through each step!

---

## 📋 Feature Roadmap

The agent knows about these features you can implement:

| Priority | Feature | Complexity | Time | What It Does |
|----------|---------|------------|------|--------------|
| **HIGH** | Edit Transaction | Low | 2-3h | Fix mistakes in transactions |
| **HIGH** | Delete Transaction | Low | 1-2h | Remove wrong entries |
| **HIGH** | Sell Stock UI | Medium | 3-4h | Sell stocks you own |
| **MEDIUM** | Portfolio Analytics | High | 6-8h | Charts and graphs |
| **MEDIUM** | Index Comparison | High | 4-5h | Compare vs NIFTY50 |

**Recommendation**: Start with Edit/Delete Transaction (easiest!)

---

## 🎯 Example: Implementing Edit Transaction

### Conversation with Agent

```
You: [Run dev_agent.py]

Agent: [Shows menu]

You: 1 [Implement a new feature]

Agent: [Shows feature roadmap]

You: 1 [Edit Transaction]

Agent: [Generates complete code template with:]
       - Database methods
       - UI dialog code
       - Integration code
       - Test cases
       - Step-by-step instructions
```

### What You Get

The agent provides:

1. **Complete code** for the feature
2. **File locations** where to add it
3. **Step-by-step instructions**
4. **Test cases** to verify it works

### Implementation Steps

1. **Copy database methods** → `database/db_manager.py`
2. **Create new dialog** → `ui/edit_transaction_dialog.py`
3. **Update portfolio view** → `ui/portfolio_view.py`
4. **Test it**: `python3 tests/run_tests.py`
5. **Run app**: `python3 main.py`

---

## 🔧 How Features Are Built

### Typical Feature Implementation

```
1. Database Layer
   └─ Add methods to db_manager.py
   └─ Example: update_transaction(), delete_transaction()

2. UI Layer
   └─ Create new dialog or update existing view
   └─ Example: EditTransactionDialog

3. Integration
   └─ Connect UI to database
   └─ Add buttons, handlers

4. Testing
   └─ Add tests for new functionality
   └─ Run test suite

5. Deployment
   └─ Test manually in app
   └─ Verify everything works
```

---

## 📚 Detailed Feature Guides

### Edit Transaction Feature

**What it does:**
- Let users fix mistakes in their transactions
- Update quantity, price, date, etc.
- Recalculate portfolio automatically

**Implementation:**

1. **Database Methods** (db_manager.py)
```python
def update_transaction(self, transaction_id, **updates):
    # Updates transaction with new values
    
def get_transaction_by_id(self, transaction_id):
    # Fetches single transaction
```

2. **UI Dialog** (ui/edit_transaction_dialog.py)
```python
class EditTransactionDialog:
    # Pre-filled form
    # Save changes
    # Validation
```

3. **Integration** (ui/portfolio_view.py)
```python
def edit_transaction(self, transaction_id):
    # Opens edit dialog
    # Refreshes portfolio after save
```

---

### Delete Transaction Feature

**What it does:**
- Remove incorrect transactions
- Confirm before deleting
- Update portfolio immediately

**Implementation:**

1. **Database Method** (db_manager.py)
```python
def delete_transaction(self, transaction_id):
    # Deletes transaction
```

2. **UI Update** (ui/portfolio_view.py)
```python
def delete_transaction(self, transaction_id):
    # Shows confirmation
    # Deletes if confirmed
    # Refreshes portfolio
```

---

### Sell Stock UI Feature

**What it does:**
- Dedicated sell flow
- Shows available quantity
- Calculates realized P&L
- Prevents selling more than owned

**Implementation:**

1. **Validation Logic** (services/stock_service.py)
```python
def validate_sell_quantity(holdings, sell_quantity):
    # Ensures can't sell more than owned
```

2. **Sell Dialog** (ui/sell_stock_dialog.py)
```python
class SellStockDialog:
    # Shows current holdings
    # Calculates P&L
    # Confirms sale
```

3. **Quick Sell Button** (ui/portfolio_view.py)
```python
# Add "Sell" button to each stock
# Opens SellStockDialog pre-filled
```

---

### Portfolio Analytics Feature

**What it does:**
- Charts showing portfolio growth
- Compare against NIFTY50, NIFTY500
- Calculate returns, volatility
- Show top performers

**Implementation:**

1. **Index Data Service** (services/index_data_service.py)
```python
class IndexDataService:
    def get_nifty50_data(start, end):
        # Fetches NIFTY50 historical data
```

2. **Analytics Service** (services/analytics_service.py)
```python
class AnalyticsService:
    def calculate_portfolio_history(user_id):
        # Computes daily portfolio values
    
    def calculate_returns(values):
        # Returns, volatility, Sharpe ratio
```

3. **Analytics View** (ui/analytics_view.py)
```python
class AnalyticsView:
    # Chart widget
    # Time period selector
    # Index comparison dropdown
```

---

## 🧪 Testing Your Changes

### Before Testing

```bash
# Run the test suite
python3 tests/run_tests.py
```

### During Development

```bash
# Run import tests
python3 tests/run_tests.py --imports

# Run unit tests
python3 tests/run_tests.py --unit
```

### After Implementation

```bash
# Full test suite
python3 tests/run_tests.py

# If all pass, test manually
python3 main.py
```

---

## 💡 Best Practices

### When Implementing Features

1. **Start Small**: Begin with Edit/Delete (easiest)
2. **Test Incrementally**: Test after each step
3. **Read Templates Carefully**: The agent provides detailed comments
4. **Ask for Help**: Use option 7 in the agent menu
5. **Run Tests Often**: Catch bugs early

### Code Organization

```
✅ DO:
- Keep database logic in db_manager.py
- Keep UI code in separate dialog files
- Add tests for new features
- Follow existing code patterns

❌ DON'T:
- Mix UI and database code
- Skip testing
- Ignore error handling
- Forget to update imports
```

### Common Pitfalls

**Problem**: "Module not found"
**Solution**: Check imports, run `python3 tests/run_tests.py --imports`

**Problem**: "Changes don't show in app"
**Solution**: Restart the app, database may be cached

**Problem**: "Tests fail after changes"
**Solution**: Read test output, fix errors, run again

---

## 🎓 Learning Path

### Week 1: Basic Features
- Day 1-2: Implement Edit Transaction
- Day 3: Implement Delete Transaction
- Day 4-5: Implement Sell Stock UI

### Week 2: Analytics Foundation
- Day 1-2: Create portfolio value history
- Day 3-4: Add basic charts
- Day 5: Integrate into UI

### Week 3: Advanced Analytics
- Day 1-2: Add index data fetching
- Day 3-4: Comparative charts
- Day 5: Advanced metrics

---

## 🤝 Working with the Agent

### Interactive Workflow

```
You: "I want to add edit functionality"

Agent: [Generates code template]

You: [Copy code to files]

You: "Run tests"

Agent: [Runs test suite]
       ✅ All tests pass!

You: "Show me the codebase structure"

Agent: [Shows file organization]

You: [Test feature manually]

You: "Next feature!"
```

### Getting Unstuck

If you're stuck:

1. **Use option 7**: Get implementation help
2. **Use option 5**: View codebase structure
3. **Use option 3**: Run tests to see what's broken
4. **Use option 4**: Ask agent to explain code

---

## 📊 Progress Tracking

### Keep track of what you've implemented:

```
Phase 1: Critical Features
[ ] Edit Transaction
[ ] Delete Transaction  
[ ] Sell Stock UI

Phase 2: Analytics
[ ] Portfolio value history
[ ] Basic charts
[ ] Index data fetching

Phase 3: Advanced
[ ] Comparative charts
[ ] Advanced metrics
[ ] Export functionality
```

---

## 🎯 Success Criteria

### Feature is Complete When:

✅ Code is added to correct files  
✅ All tests pass  
✅ Feature works in UI  
✅ No errors in console  
✅ Data is saved correctly  
✅ Portfolio updates properly  

---

## 🆘 Getting Help

### If Something Goes Wrong

1. **Check the error message** - It usually tells you what's wrong
2. **Run tests** - `python3 tests/run_tests.py`
3. **Check imports** - `python3 tests/run_tests.py --imports`
4. **Review the template** - The agent's code includes comments
5. **Start fresh** - Sometimes easier to re-copy the code

---

## 🚀 Advanced Usage

### Custom Features

Want to add something not in the roadmap?

1. Describe the feature to the agent
2. Review the design document (ENHANCED_FEATURES_DESIGN.md)
3. Follow the same pattern as existing features
4. Add tests
5. Integrate into UI

### Modifying Generated Code

The agent provides **templates** - you can customize:
- UI styling
- Validation rules
- Error messages
- Additional fields

---

## 📝 Example Session

```bash
$ python3 dev_agent.py

🤖 EQUITY TRACKER DEVELOPMENT AGENT

What would you like to do?
  1. 🎯 Implement a new feature
  ...

Enter your choice (1-8): 1

🗺️  FEATURE ROADMAP

Feature                   Priority    Complexity    Est. Time
----------------------------------------------------------------------
1. Edit Transaction       HIGH        Low           2-3 hours
2. Delete Transaction     HIGH        Low           1-2 hours
...

Enter feature number to implement: 1

🔨 Generating code for: Edit Transaction

[Agent shows complete code template with:]
- Database methods
- UI dialog
- Integration code
- Testing instructions

Next Steps:
1. Copy the db_manager.py methods
2. Create ui/edit_transaction_dialog.py
3. Update ui/portfolio_view.py
4. Test: python3 tests/run_tests.py

Press Enter to continue...
```

---

## 🎉 You're Ready!

Start with:
```bash
python3 dev_agent.py
```

Choose option 1, select Edit Transaction, and follow the instructions!

Happy coding! 🚀📈
