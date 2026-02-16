# 🎨 EQUITY TRACKER - ENHANCED FEATURES DESIGN

## Overview
This document outlines the design for three critical feature enhancements:
1. Edit/Delete Transaction capability
2. Sell Stock workflow
3. Portfolio Analytics with Index Comparison

This document now also tracks:
4. Investment note visibility in Portfolio
5. Stock lookup optimization (debounce + caching)
6. Fundamental and analyst-data design for upcoming releases

---

## 0. RECENT IMPLEMENTATION UPDATES (Current State)

### A) Portfolio note visibility
- Portfolio rows now expose latest investment note (thesis) on hover.
- Double-click stock opens transaction manager with a dedicated Note column.
- Full note remains available as tooltip in transaction rows.

### B) Stock lookup optimization in Add Stock
- Symbol lookup is now debounced to avoid API calls on every keystroke.
- Stock info and current price lookups use short-lived in-memory caching.
- Add flow reuses last validated symbol info to prevent duplicate network fetch.

### C) Test coverage updates
- Added tests for transaction type update behavior.
- Added tests for stock delete cascades.
- Added UI tests for row action buttons and note tooltip rendering.

### D) Phase-1 data foundation implemented
- Added `symbol_master` table for local symbol/company directory.
- Added `financials_quarterly` table for 4-8 quarter results data.
- Added `balance_sheet_annual` table for annual balance-sheet fields.
- Added `financial_ratios` snapshot table for runtime + computed ratios.
- Added `bse_announcements` table for RSS ingest and processing pipeline.
- Added `SymbolMasterService` for seed/list ingestion into symbol master.
- Added `NSEToolsAdapter` + `SymbolMasterService.populate_symbols_from_nsetools()` for NSE symbol bootstrap.
- Added script `scripts/sync_nse_symbols.py` to sync NSE symbol master into local DB.
- Added `BSEFeedService` for RSS fetch + persistence of announcement metadata.
- Alerts now auto-sync latest material announcements for portfolio stocks only (results + key events keyword filter).
- Alerts action buttons were redesigned for visibility with higher contrast styles.

---

## 1. EDIT/DELETE TRANSACTIONS

### Current Problem
- Users cannot correct mistakes in transactions
- No way to remove erroneous entries
- Data integrity issues if wrong entries made

### Solution Design

#### Database Layer
**New Methods in db_manager.py:**
```python
def update_transaction(transaction_id, **kwargs):
    """Update a transaction with new values"""
    
def delete_transaction(transaction_id):
    """Delete a transaction"""
    
def get_transaction_by_id(transaction_id):
    """Get single transaction details"""
```

#### UI Layer
**Portfolio View Enhancement:**
- Add "Edit" button next to each transaction
- Add "Delete" button with confirmation
- Double-click transaction → Edit dialog

**New Dialog: EditTransactionDialog**
- Pre-populated form with existing values
- All fields editable except stock_id
- Save/Cancel buttons
- Validation before update

**User Flow:**
1. User views portfolio
2. Clicks stock → sees transaction list
3. Click "Edit" on transaction
4. Edit dialog opens with pre-filled data
5. User modifies fields
6. Clicks "Save"
7. Confirmation dialog
8. Database updated
9. Portfolio refreshes

---

## 2. SELL STOCK WORKFLOW

### Current Problem
- Can only add BUY transactions
- No sell functionality in UI
- Portfolio shows gross holdings, not net

### Solution Design

#### Existing Code (Already Works!)
- `transaction_type` field supports 'BUY' and 'SELL'
- Database calculates net position correctly
- P&L calculation works with sells

#### What's Missing: UI Flow

**Enhanced Add Stock Dialog:**
- Transaction Type dropdown: BUY/SELL
- When SELL selected:
  - Show available quantity for stock
  - Validate: can't sell more than owned
  - Calculate realized P&L
  - Show gain/loss before confirming

**New: Quick Sell Button**
- In portfolio view, "Sell" button per stock
- Opens dialog pre-filled:
  - Stock already selected
  - Transaction type = SELL
  - Current price auto-filled
  - Quantity field (max = current holdings)

**Sell Confirmation Dialog:**
```
You are selling 10 shares of AAPL

Purchase Price:     ₹100.00
Sale Price:         ₹120.00
Quantity:           10
Realized P&L:       ₹200.00 (20%)

Proceed with sale?
[Yes] [No]
```

---

## 3. PORTFOLIO ANALYTICS & INDEX COMPARISON

### Requirements
- Visualize portfolio growth over time
- Compare against NIFTY50, NIFTY500, S&P500
- Interactive charts
- Time period selection (1M, 3M, 6M, 1Y, ALL)

### Solution Design

#### Database Enhancements
**New Methods:**
```python
def get_portfolio_history(user_id, start_date, end_date):
    """Get portfolio value over time"""
    
def get_daily_portfolio_value(user_id, date):
    """Calculate portfolio value for specific date"""
```

**New Table (optional):**
```sql
CREATE TABLE portfolio_snapshots (
    snapshot_id INTEGER PRIMARY KEY,
    user_id INTEGER,
    snapshot_date DATE,
    total_value REAL,
    total_invested REAL,
    pnl REAL,
    pnl_percentage REAL
);
```

#### Index Data Service
**New: IndexDataService**
```python
class IndexDataService:
    def get_nifty50_data(start_date, end_date):
        """Fetch NIFTY50 historical data"""
    
    def get_nifty500_data(start_date, end_date):
        """Fetch NIFTY500 historical data"""
    
    def get_sp500_data(start_date, end_date):
        """Fetch S&P500 historical data"""
    
    def normalize_returns(values, base_value=100):
        """Normalize to percentage returns"""
```

#### UI Components

**New Tab: Analytics**
```
┌─────────────────────────────────────────────────────┐
│  📊 Portfolio Analytics                             │
├─────────────────────────────────────────────────────┤
│                                                      │
│  [1M] [3M] [6M] [1Y] [ALL]   vs [NIFTY50 ▼]       │
│                                                      │
│  ┌───────────────────────────────────────────────┐ │
│  │                                               │ │
│  │         📈 PORTFOLIO GROWTH CHART             │ │
│  │                                               │ │
│  │    Your Portfolio: +25%                       │ │
│  │    NIFTY50:        +18%                       │ │
│  │    Outperformance: +7%                        │ │
│  │                                               │ │
│  └───────────────────────────────────────────────┘ │
│                                                      │
│  Key Metrics:                                        │
│  ┌──────────────┬──────────────┬──────────────┐   │
│  │ Total Value  │   Returns    │  Volatility  │   │
│  │  ₹1,50,000   │   +25.5%     │    12.3%     │   │
│  └──────────────┴──────────────┴──────────────┘   │
│                                                      │
│  Top Performers:                                     │
│  1. AAPL    +35%                                    │
│  2. GOOGL   +28%                                    │
│  3. MSFT    +22%                                    │
│                                                      │
└─────────────────────────────────────────────────────┘
```

**Chart Library:**
- Use matplotlib (for static charts)
- OR PyQtGraph (for interactive charts)
- OR plotly (web-based, more features)

**Implementation:**
```python
class AnalyticsView(QWidget):
    def __init__(self):
        # Time period selector
        # Index selector dropdown
        # Chart widget
        # Metrics display
        
    def plot_portfolio_vs_index(self, period, index_name):
        # Fetch portfolio history
        # Fetch index data
        # Normalize both to same base
        # Plot comparative chart
        
    def calculate_metrics(self):
        # Total returns
        # CAGR
        # Volatility
        # Sharpe ratio
        # Max drawdown
```

---

## 4. FUNDAMENTALS (4-8 QUARTERS) & ANALYST CONSENSUS DESIGN

### Product Goals
- Show last 4-8 quarters of key financials for each stock.
- Show core fundamental ratios (valuation, profitability, growth, leverage).
- Show analyst consensus: Buy/Hold/Sell distribution and average target price.

### Data Model Additions

**Tables:**
```sql
CREATE TABLE fundamentals_quarterly (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER NOT NULL,
    fiscal_period TEXT NOT NULL,           -- e.g., 2025-Q4
    revenue REAL,
    ebitda REAL,
    net_income REAL,
    eps REAL,
    free_cash_flow REAL,
    debt REAL,
    cash REAL,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(stock_id, fiscal_period)
);

CREATE TABLE valuation_ratios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER NOT NULL,
    as_of_date DATE NOT NULL,
    pe REAL,
    pb REAL,
    ps REAL,
    ev_ebitda REAL,
    roe REAL,
    roa REAL,
    debt_to_equity REAL,
    current_ratio REAL,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(stock_id, as_of_date)
);

CREATE TABLE analyst_consensus (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER NOT NULL,
    as_of_date DATE NOT NULL,
    buy_count INTEGER,
    hold_count INTEGER,
    sell_count INTEGER,
    avg_target_price REAL,
    high_target_price REAL,
    low_target_price REAL,
    source TEXT,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(stock_id, as_of_date, source)
);
```

### Service Layer Design

**New service: `services/fundamentals_service.py`**
- `refresh_stock_fundamentals(stock_id, symbol)`
- `get_quarterly_financials(stock_id, limit=8)`
- `get_latest_ratios(stock_id)`

**New service: `services/analyst_service.py`**
- `refresh_analyst_consensus(stock_id, symbol)`
- `get_latest_consensus(stock_id)`

**New coordinator: `services/research_snapshot_service.py`**
- Builds one consolidated payload for UI:
  - quarterly trend cards
  - ratio cards
  - analyst distribution and target band

### UI Design (Next phase)

**Portfolio stock details dialog enhancement**
- Add tabs:
  1. Transactions
  2. Notes
  3. Financials (last 4-8 quarters)
  4. Ratios
  5. Analyst View

### Data freshness & reliability
- Use cache-first reads from local DB.
- Refresh in background with TTL policies:
  - fundamentals: daily
  - ratios: daily
  - analyst consensus: daily or provider-dependent
- If provider unavailable, show last snapshot + "stale" timestamp.

---

## IMPLEMENTATION PRIORITY

### Phase 1: Completed baseline
1. ✅ Edit Transaction functionality
2. ✅ Delete Transaction functionality
3. ✅ Portfolio row actions (Edit/Delete per stock)
4. ✅ Investment note visibility (hover + double-click flows)
5. ✅ Stock lookup debounce + cache in Add Stock flow

### Phase 2: In progress
6. ⏳ Sell Stock UI flow improvements
7. ⏳ Portfolio analytics foundation

### Phase 3: Research data layer
8. ⏳ Fundamentals quarterly data (4-8 quarters)
9. ⏳ Ratio snapshots and trend comparisons
10. ⏳ Analyst consensus and target expectations

### Phase 4: Advanced analytics
11. ⏳ Comparative charts (portfolio vs index)
12. ⏳ Multiple index support
13. ⏳ Advanced metrics (Sharpe, volatility, etc.)

---

## TECHNICAL SPECIFICATIONS

### Edit Transaction Flow
```
User clicks "Edit" button
    ↓
Load transaction data from database
    ↓
Open EditTransactionDialog pre-filled
    ↓
User modifies fields
    ↓
Validate inputs
    ↓
Update database
    ↓
Recalculate portfolio summary
    ↓
Refresh UI
```

### Sell Stock Flow
```
User clicks "Sell" button on stock
    ↓
Check current holdings
    ↓
Open SellStockDialog
    - Pre-fill stock details
    - Set transaction_type = SELL
    - Show available quantity
    ↓
User enters sell details
    ↓
Validate: quantity <= holdings
    ↓
Calculate realized P&L
    ↓
Show confirmation with P&L
    ↓
Save transaction
    ↓
Update portfolio
```

### Analytics Data Flow
```
User selects time period + index
    ↓
Fetch portfolio transactions
    ↓
Calculate daily portfolio values
    ↓
Fetch index historical data (yfinance)
    ↓
Normalize both to base 100
    ↓
Calculate returns, metrics
    ↓
Plot comparative chart
    ↓
Display metrics table
```

---

## DATABASE CHANGES

### New Methods Required

**db_manager.py:**
```python
# Transaction CRUD
def update_transaction(self, transaction_id, **updates):
def delete_transaction(self, transaction_id):
def get_transaction_by_id(self, transaction_id):

# Symbol master
def upsert_symbol_master(...):
def search_symbol_master(...):
def get_symbol_by_symbol(...):

# Quarterly and annual financials
def upsert_quarterly_financials(...):
def get_quarterly_financials(...):
def upsert_annual_balance_sheet(...):

# Financial ratios
def upsert_financial_ratios(...):
def get_latest_financial_ratios(...):

# BSE RSS pipeline
def add_bse_announcement(...):
def get_unprocessed_bse_announcements(...):
def mark_bse_announcement_processed(...):

# Analytics
def get_portfolio_value_on_date(self, user_id, date):
def get_transaction_history_range(self, user_id, start_date, end_date):
def calculate_daily_portfolio_values(self, user_id, start_date, end_date):
```

---

## NEW FILES TO CREATE

1. **ui/edit_transaction_dialog.py** - Edit existing transaction
2. **ui/sell_stock_dialog.py** - Dedicated sell flow
3. **ui/analytics_view.py** - Analytics tab with charts
4. **services/index_data_service.py** - Fetch index data
5. **services/analytics_service.py** - Calculate metrics
6. **utils/chart_utils.py** - Chart generation helpers
7. **services/symbol_master_service.py** - Symbol master ingest/search
8. **services/bse_feed_service.py** - BSE RSS ingest pipeline

---

## TESTING REQUIREMENTS

### Unit Tests
- Test edit transaction updates database correctly
- Test delete transaction removes record
- Test sell validation (can't sell more than owned)
- Test portfolio value calculation
- Test index data fetching

### Integration Tests
- Test complete edit workflow
- Test complete sell workflow
- Test portfolio value history generation
- Test chart data generation

### UI Tests
- Test edit dialog opens with correct data
- Test sell dialog validates quantity
- Test analytics view renders chart

---

## USER EXPERIENCE ENHANCEMENTS

### Edit Transaction
- Clear visual feedback on successful edit
- Undo option (optional)
- Audit trail (who edited when)

### Sell Stock
- Quick sell from portfolio view
- Realized P&L shown before confirmation
- Historical sells visible in transaction list

### Analytics
- Interactive charts (zoom, pan)
- Export chart as image
- Export data as CSV
- Multiple portfolios comparison (future)

---

## NEXT STEPS

With Development Agent, you can:
1. Generate code for each feature
2. Test incrementally
3. Integrate step by step
4. Ask for modifications
5. Get explanations

Example conversation with agent:
```
You: "Implement edit transaction functionality"
Agent: [Generates code for EditTransactionDialog + DB methods]

You: "Add validation to prevent selling more than owned"
Agent: [Adds validation logic]

You: "Create analytics view with NIFTY50 comparison"
Agent: [Generates analytics_view.py with chart]
```

---

## ESTIMATED EFFORT

| Feature | Complexity | Time |
|---------|-----------|------|
| Edit Transaction | Low | 2-3 hours |
| Delete Transaction | Low | 1-2 hours |
| Sell Stock UI | Medium | 3-4 hours |
| Portfolio History | Medium | 4-5 hours |
| Index Data Service | Medium | 3-4 hours |
| Basic Analytics View | High | 6-8 hours |
| Advanced Metrics | High | 8-10 hours |

**Total: 27-36 hours** (can be done incrementally)

---

## CONCLUSION

These features will transform the app from basic portfolio tracking to 
comprehensive investment management with professional analytics.

The Development Agent will help you build these features step by step,
with full code generation, testing, and integration support.
