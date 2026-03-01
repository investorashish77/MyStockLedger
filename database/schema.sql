
-- Users Table
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    mobile_number TEXT UNIQUE NOT NULL,
    name TEXT,
    email TEXT,
    password_hash TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Stocks Table
CREATE TABLE IF NOT EXISTS stocks (
    stock_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    symbol TEXT NOT NULL,
    company_name TEXT,
    exchange TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- Transactions Table
CREATE TABLE IF NOT EXISTS transactions (
    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER,
    transaction_type TEXT,
    quantity INTEGER,
    price_per_share REAL,
    transaction_date DATE,
    investment_horizon TEXT,
    target_price REAL,
    thesis TEXT,
    setup_type TEXT,
    confidence_score INTEGER,
    risk_tags TEXT,
    mistake_tags TEXT,
    reflection_note TEXT,
    realized_pnl REAL,
    realized_cost_basis REAL,
    realized_match_method TEXT,
    sell_note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (stock_id) REFERENCES stocks(stock_id)
);

CREATE TABLE IF NOT EXISTS transaction_lot_matches (
    match_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sell_transaction_id INTEGER NOT NULL,
    buy_transaction_id INTEGER NOT NULL,
    matched_quantity INTEGER NOT NULL,
    buy_price_per_share REAL NOT NULL,
    sell_price_per_share REAL NOT NULL,
    realized_pnl REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cash_ledger (
    ledger_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    entry_type TEXT NOT NULL,  -- INIT_DEPOSIT, DEPOSIT, WITHDRAWAL, BUY_DEBIT, SELL_CREDIT
    amount REAL NOT NULL,
    entry_date DATE,
    note TEXT,
    reference_transaction_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (reference_transaction_id) REFERENCES transactions(transaction_id)
);

CREATE INDEX IF NOT EXISTS idx_cash_ledger_user_date
ON cash_ledger(user_id, entry_date, ledger_id);

-- Alerts Table
CREATE TABLE IF NOT EXISTS alerts (
    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER,
    alert_type TEXT,
    alert_message TEXT,
    announcement_details TEXT,
    announcement_url TEXT,
    triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_read BOOLEAN DEFAULT 0,
    FOREIGN KEY (stock_id) REFERENCES stocks(stock_id)
);

-- AI Summaries Table
CREATE TABLE IF NOT EXISTS ai_summaries (
    summary_id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_id INTEGER,
    summary_text TEXT,
    sentiment TEXT,
    impact_analysis TEXT,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (alert_id) REFERENCES alerts(alert_id)
);

-- Price History Table
CREATE TABLE IF NOT EXISTS price_history (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER,
    price REAL,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (stock_id) REFERENCES stocks(stock_id)
);

-- Symbol Master Table
CREATE TABLE IF NOT EXISTS symbol_master (
    symbol_id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL UNIQUE,
    company_name TEXT NOT NULL,
    exchange TEXT NOT NULL DEFAULT 'NSE',
    bse_code TEXT,
    nse_code TEXT,
    quote_symbol_yahoo TEXT,
    sector TEXT,
    industry_group TEXT,
    industry TEXT,
    is_active BOOLEAN DEFAULT 1,
    source TEXT DEFAULT 'MANUAL',
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Quarterly Financial Results
CREATE TABLE IF NOT EXISTS financials_quarterly (
    result_id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol_id INTEGER NOT NULL,
    fiscal_year INTEGER NOT NULL,
    fiscal_quarter TEXT NOT NULL,  -- Q1/Q2/Q3/Q4
    period_end_date DATE,
    total_sales REAL,
    ebitda REAL,
    ebit REAL,
    pbt REAL,
    pat REAL,
    eps REAL,
    book_value_per_share REAL,
    source_url TEXT,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol_id, fiscal_year, fiscal_quarter),
    FOREIGN KEY (symbol_id) REFERENCES symbol_master(symbol_id)
);

-- Annual Balance Sheet Data
CREATE TABLE IF NOT EXISTS balance_sheet_annual (
    balance_sheet_id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol_id INTEGER NOT NULL,
    fiscal_year INTEGER NOT NULL,
    total_assets REAL,
    total_liabilities REAL,
    total_equity REAL,
    cash_and_equivalents REAL,
    total_debt REAL,
    net_worth REAL,
    source_url TEXT,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol_id, fiscal_year),
    FOREIGN KEY (symbol_id) REFERENCES symbol_master(symbol_id)
);

-- Financial Ratios Snapshot
CREATE TABLE IF NOT EXISTS financial_ratios (
    ratio_id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol_id INTEGER NOT NULL,
    as_of_date DATE NOT NULL,
    eps_ttm REAL,
    book_value_per_share REAL,
    total_sales_ttm REAL,
    ebitda_ttm REAL,
    enterprise_value REAL,
    market_cap REAL,
    pe_ratio REAL,
    pb_ratio REAL,
    ps_ratio REAL,
    ev_to_ebitda REAL,
    close_price REAL,
    source TEXT DEFAULT 'CALCULATED',
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol_id, as_of_date),
    FOREIGN KEY (symbol_id) REFERENCES symbol_master(symbol_id)
);

-- BSE Announcement Feed Tracker
CREATE TABLE IF NOT EXISTS bse_announcements (
    announcement_id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol_id INTEGER,
    scrip_code TEXT,
    headline TEXT NOT NULL,
    category TEXT,
    announcement_date TEXT,
    attachment_url TEXT,
    exchange_ref_id TEXT UNIQUE,
    rss_guid TEXT UNIQUE,
    raw_payload TEXT,
    processed BOOLEAN DEFAULT 0,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (symbol_id) REFERENCES symbol_master(symbol_id)
);

CREATE INDEX IF NOT EXISTS idx_symbol_master_exchange ON symbol_master(exchange, symbol);
CREATE INDEX IF NOT EXISTS idx_symbol_master_bse_code ON symbol_master(bse_code);
CREATE INDEX IF NOT EXISTS idx_financials_quarterly_symbol ON financials_quarterly(symbol_id, fiscal_year, fiscal_quarter);
CREATE INDEX IF NOT EXISTS idx_financial_ratios_symbol ON financial_ratios(symbol_id, as_of_date);
CREATE INDEX IF NOT EXISTS idx_bse_announcements_processed ON bse_announcements(processed, announcement_date);

-- Normalized portfolio-specific filings view (persisted brief summary)
CREATE TABLE IF NOT EXISTS filings (
    filing_id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER NOT NULL,
    symbol_id INTEGER,
    category TEXT NOT NULL,
    category_override TEXT,
    override_locked BOOLEAN DEFAULT 0,
    override_updated_at TIMESTAMP,
    headline TEXT NOT NULL,
    announcement_summary TEXT,
    announcement_date TEXT,
    pdf_link TEXT,
    source_exchange TEXT DEFAULT 'BSE',
    source_ref TEXT UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (stock_id) REFERENCES stocks(stock_id),
    FOREIGN KEY (symbol_id) REFERENCES symbol_master(symbol_id)
);

CREATE INDEX IF NOT EXISTS idx_filings_stock_date ON filings(stock_id, announcement_date);
CREATE INDEX IF NOT EXISTS idx_filings_category ON filings(category, announcement_date);

-- Quarter-specific portfolio insight snapshots (one per stock+quarter+insight type)
CREATE TABLE IF NOT EXISTS insight_snapshots (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER NOT NULL,
    quarter_label TEXT NOT NULL,           -- Example: Q3 FY26
    insight_type TEXT NOT NULL,            -- RESULT_SUMMARY / CONCALL_SUMMARY
    source_filing_id INTEGER,
    source_ref TEXT,
    summary_text TEXT,
    sentiment TEXT,
    status TEXT NOT NULL DEFAULT 'GENERATED', -- GENERATED / NOT_AVAILABLE / FAILED
    provider TEXT,
    model_version TEXT,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (stock_id) REFERENCES stocks(stock_id),
    FOREIGN KEY (source_filing_id) REFERENCES filings(filing_id),
    UNIQUE(stock_id, quarter_label, insight_type)
);

CREATE INDEX IF NOT EXISTS idx_insight_snapshots_stock_quarter ON insight_snapshots(stock_id, quarter_label);
CREATE INDEX IF NOT EXISTS idx_insight_snapshots_type ON insight_snapshots(insight_type, quarter_label);

-- Global insight snapshots shared across users (one per company+quarter+insight type)
CREATE TABLE IF NOT EXISTS global_insight_snapshots (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol_id INTEGER NOT NULL,
    quarter_label TEXT NOT NULL,
    insight_type TEXT NOT NULL,            -- RESULT_SUMMARY / CONCALL_SUMMARY
    source_filing_id INTEGER,
    source_ref TEXT,
    summary_text TEXT,
    sentiment TEXT,
    status TEXT NOT NULL DEFAULT 'GENERATED',
    provider TEXT,
    model_version TEXT,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (symbol_id) REFERENCES symbol_master(symbol_id),
    FOREIGN KEY (source_filing_id) REFERENCES filings(filing_id),
    UNIQUE(symbol_id, quarter_label, insight_type)
);

CREATE INDEX IF NOT EXISTS idx_global_insight_snapshots_symbol_quarter
    ON global_insight_snapshots(symbol_id, quarter_label);

-- Background job queue for non-blocking long-running tasks
CREATE TABLE IF NOT EXISTS background_jobs (
    job_id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_type TEXT NOT NULL,                     -- GENERATE_MISSING_INSIGHTS / REGENERATE_INSIGHTS
    requested_by INTEGER,
    status TEXT NOT NULL DEFAULT 'QUEUED',      -- QUEUED / RUNNING / SUCCESS / FAILED
    payload_json TEXT,
    progress INTEGER DEFAULT 0,
    result_json TEXT,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (requested_by) REFERENCES users(user_id)
);

CREATE INDEX IF NOT EXISTS idx_background_jobs_status_created
    ON background_jobs(status, created_at);
CREATE INDEX IF NOT EXISTS idx_background_jobs_requested_by
    ON background_jobs(requested_by, created_at);

-- User notifications (for job completion and future features)
CREATE TABLE IF NOT EXISTS notifications (
    notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,                            -- null => global/system
    notif_type TEXT NOT NULL,                   -- INSIGHTS_READY / INSIGHTS_FAILED / SYSTEM
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    metadata_json TEXT,
    is_read BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    read_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE INDEX IF NOT EXISTS idx_notifications_user_read
    ON notifications(user_id, is_read, created_at);

-- Generic app settings for sync cursors/feature flags
CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- BSE Daily Bhavcopy OHLCV data
CREATE TABLE IF NOT EXISTS bse_daily_prices (
    price_id INTEGER PRIMARY KEY AUTOINCREMENT,
    bse_code TEXT NOT NULL,
    trade_date DATE NOT NULL,
    open_price REAL,
    high_price REAL,
    low_price REAL,
    close_price REAL NOT NULL,
    total_shares_traded REAL,
    total_trades REAL,
    turnover REAL,
    source TEXT DEFAULT 'BSE_BHAVCOPY',
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(bse_code, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_bse_daily_prices_code_date ON bse_daily_prices(bse_code, trade_date);

-- Analyst consensus snapshots (one latest report per stock)
CREATE TABLE IF NOT EXISTS analyst_consensus (
    consensus_id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER NOT NULL UNIQUE,
    report_text TEXT,
    status TEXT NOT NULL DEFAULT 'GENERATED', -- GENERATED / FAILED
    provider TEXT,
    as_of_date DATE,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (stock_id) REFERENCES stocks(stock_id)
);

CREATE INDEX IF NOT EXISTS idx_analyst_consensus_stock ON analyst_consensus(stock_id);

-- AI response cache keyed by prompt hash/provider/model/task
CREATE TABLE IF NOT EXISTS ai_response_cache (
    cache_id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_hash TEXT NOT NULL,
    response_text TEXT NOT NULL,
    sentiment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(task_type, provider, model, prompt_hash)
);

CREATE INDEX IF NOT EXISTS idx_ai_response_cache_lookup
    ON ai_response_cache(task_type, provider, model, prompt_hash);
