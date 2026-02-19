"""
Database Manager
Handles all database operations for the Equity Tracker app
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

class DatabaseManager:
    """Manages database operations"""
    
    def __init__(self, db_path: str = 'data/equity_tracker.db'):
        self.db_path = db_path
        self._in_memory = db_path == ':memory:'
        self._shared_conn = None

        if self._in_memory:
            # Keep one shared connection alive for in-memory databases.
            # This ensures all operations access the same schema/data in tests.
            self._shared_conn = sqlite3.connect(self.db_path)
            self._create_schema(self._shared_conn)
        else:
            self._ensure_database_exists()
    
    def _ensure_database_exists(self):
        """Ensure database file and tables exist"""
        db_file = Path(self.db_path)
        if not db_file.parent.exists():
            db_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Always run schema to keep local DB migrated with latest CREATE IF NOT EXISTS tables.
        self._create_schema()
        self._run_migrations()

    def _run_migrations(self):
        """Run lightweight schema migrations for existing databases."""
        conn = self.get_connection()
        cursor = conn.cursor()

        def has_column(table: str, column: str) -> bool:
            cursor.execute(f"PRAGMA table_info({table})")
            return any(row[1] == column for row in cursor.fetchall())

        # Add quote symbol mapping column for Yahoo-compatible tickers.
        if has_column("symbol_master", "quote_symbol_yahoo") is False:
            cursor.execute("ALTER TABLE symbol_master ADD COLUMN quote_symbol_yahoo TEXT")

        # Shared settings store for sync cursors and feature flags.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_symbol_master_bse_code ON symbol_master(bse_code)")
        cursor.execute("""
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
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bse_daily_prices_code_date ON bse_daily_prices(bse_code, trade_date)")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS insight_snapshots (
                snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_id INTEGER NOT NULL,
                quarter_label TEXT NOT NULL,
                insight_type TEXT NOT NULL,
                source_filing_id INTEGER,
                source_ref TEXT,
                summary_text TEXT,
                sentiment TEXT,
                status TEXT NOT NULL DEFAULT 'GENERATED',
                provider TEXT,
                model_version TEXT,
                generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(stock_id, quarter_label, insight_type)
            )
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_insight_snapshots_stock_quarter ON insight_snapshots(stock_id, quarter_label)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_insight_snapshots_type ON insight_snapshots(insight_type, quarter_label)"
        )
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analyst_consensus (
                consensus_id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_id INTEGER NOT NULL UNIQUE,
                report_text TEXT,
                status TEXT NOT NULL DEFAULT 'GENERATED',
                provider TEXT,
                as_of_date DATE,
                generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_analyst_consensus_stock ON analyst_consensus(stock_id)")

        conn.commit()
        self._close_connection(conn)
    
    def _create_schema(self, conn=None):
        """Create database schema"""
        schema_path = Path(__file__).parent / 'schema.sql'
        if schema_path.exists():
            with open(schema_path, 'r') as f:
                schema = f.read()
            
            conn = conn or self.get_connection()
            conn.executescript(schema)
            conn.commit()
            self._close_connection(conn)
    
    def get_connection(self):
        """Get database connection"""
        if self._in_memory and self._shared_conn is not None:
            return self._shared_conn
        return sqlite3.connect(self.db_path)

    def _close_connection(self, conn):
        """Close only non-shared connections."""
        if not self._in_memory and conn is not None:
            conn.close()
    
    # User operations
    def create_user(self, mobile_number: str, name: str, password_hash: str, email: str = None) -> int:
        """Create a new user"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO users (mobile_number, name, email, password_hash)
            VALUES (?, ?, ?, ?)
        """, (mobile_number, name, email, password_hash))
        
        user_id = cursor.lastrowid
        conn.commit()
        self._close_connection(conn)
        
        return user_id
    
    def get_user_by_mobile(self, mobile_number: str) -> Optional[Dict]:
        """Get user by mobile number"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT user_id, mobile_number, name, email, password_hash, created_at
            FROM users WHERE mobile_number = ?
        """, (mobile_number,))
        
        row = cursor.fetchone()
        self._close_connection(conn)
        
        if row:
            return {
                'user_id': row[0],
                'mobile_number': row[1],
                'name': row[2],
                'email': row[3],
                'password_hash': row[4],
                'created_at': row[5]
            }
        return None
    
    # Stock operations
    def add_stock(self, user_id: int, symbol: str, company_name: str, exchange: str = 'NSE') -> int:
        """Add a stock to user's portfolio"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Check if stock already exists for user
        cursor.execute("""
            SELECT stock_id FROM stocks 
            WHERE user_id = ? AND symbol = ?
        """, (user_id, symbol))
        
        existing = cursor.fetchone()
        if existing:
            self._close_connection(conn)
            return existing[0]
        
        cursor.execute("""
            INSERT INTO stocks (user_id, symbol, company_name, exchange)
            VALUES (?, ?, ?, ?)
        """, (user_id, symbol, company_name, exchange))
        
        stock_id = cursor.lastrowid
        conn.commit()
        self._close_connection(conn)
        
        return stock_id
    
    def get_user_stocks(self, user_id: int) -> List[Dict]:
        """Get all stocks for a user"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT stock_id, symbol, company_name, exchange
            FROM stocks WHERE user_id = ?
            ORDER BY symbol
        """, (user_id,))
        
        stocks = []
        for row in cursor.fetchall():
            stocks.append({
                'stock_id': row[0],
                'symbol': row[1],
                'company_name': row[2],
                'exchange': row[3]
            })
        
        self._close_connection(conn)
        return stocks

    def get_user_stocks_with_symbol_master(self, user_id: int) -> List[Dict]:
        """Get user stocks enriched with symbol_master metadata."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.stock_id, s.symbol, s.company_name, s.exchange,
                   sm.symbol_id, sm.bse_code, sm.nse_code, sm.sector
            FROM stocks s
            LEFT JOIN symbol_master sm
                ON sm.symbol = s.symbol
               OR sm.symbol = REPLACE(REPLACE(UPPER(s.symbol), '.NS', ''), '.BO', '')
            WHERE s.user_id = ?
            ORDER BY s.symbol
        """, (user_id,))
        rows = cursor.fetchall()
        self._close_connection(conn)
        return [
            {
                'stock_id': row[0],
                'symbol': row[1],
                'company_name': row[2],
                'exchange': row[3],
                'symbol_id': row[4],
                'bse_code': row[5],
                'nse_code': row[6],
                'sector': row[7],
            }
            for row in rows
        ]
    
    # Transaction operations
    def add_transaction(self, stock_id: int, transaction_type: str, quantity: int, 
                       price_per_share: float, transaction_date: str, 
                       investment_horizon: str, target_price: float = None, 
                       thesis: str = None) -> int:
        """Add a buy/sell transaction"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO transactions 
            (stock_id, transaction_type, quantity, price_per_share, transaction_date,
             investment_horizon, target_price, thesis)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (stock_id, transaction_type, quantity, price_per_share, transaction_date,
              investment_horizon, target_price, thesis))
        
        transaction_id = cursor.lastrowid
        conn.commit()
        self._close_connection(conn)
        
        return transaction_id
    
    def get_stock_transactions(self, stock_id: int) -> List[Dict]:
        """Get all transactions for a stock"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT transaction_id, transaction_type, quantity, price_per_share,
                   transaction_date, investment_horizon, target_price, thesis
            FROM transactions WHERE stock_id = ?
            ORDER BY transaction_date DESC
        """, (stock_id,))
        
        transactions = []
        for row in cursor.fetchall():
            transactions.append({
                'transaction_id': row[0],
                'transaction_type': row[1],
                'quantity': row[2],
                'price_per_share': row[3],
                'transaction_date': row[4],
                'investment_horizon': row[5],
                'target_price': row[6],
                'thesis': row[7]
            })
        
        self._close_connection(conn)
        return transactions

    def get_user_journal_notes(self, user_id: int) -> List[Dict]:
        """Get latest non-empty thesis note per stock for a user."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.stock_id, s.symbol, s.company_name,
                   t.transaction_id, t.transaction_date, t.thesis
            FROM stocks s
            JOIN transactions t ON s.stock_id = t.stock_id
            JOIN (
                SELECT stock_id, MAX(transaction_date) AS latest_date
                FROM transactions
                WHERE thesis IS NOT NULL AND TRIM(thesis) <> ''
                GROUP BY stock_id
            ) last_t
              ON last_t.stock_id = t.stock_id
             AND last_t.latest_date = t.transaction_date
            WHERE s.user_id = ?
              AND t.thesis IS NOT NULL
              AND TRIM(t.thesis) <> ''
            ORDER BY t.transaction_date DESC, s.symbol ASC
        """, (user_id,))
        rows = cursor.fetchall()
        self._close_connection(conn)
        return [
            {
                "stock_id": row[0],
                "symbol": row[1],
                "company_name": row[2],
                "transaction_id": row[3],
                "transaction_date": row[4],
                "thesis": row[5],
            }
            for row in rows
        ]
    
    def get_portfolio_summary(self, user_id: int) -> List[Dict]:
        """Get portfolio summary with holdings"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                s.stock_id, s.symbol, s.company_name, s.exchange,
                SUM(CASE WHEN t.transaction_type = 'BUY' THEN t.quantity ELSE -t.quantity END) as total_quantity,
                SUM(CASE WHEN t.transaction_type = 'BUY' THEN t.quantity * t.price_per_share ELSE 0 END) /
                    NULLIF(SUM(CASE WHEN t.transaction_type = 'BUY' THEN t.quantity ELSE 0 END), 0) as avg_price
            FROM stocks s
            LEFT JOIN transactions t ON s.stock_id = t.stock_id
            WHERE s.user_id = ?
            GROUP BY s.stock_id, s.symbol, s.company_name, s.exchange
            HAVING total_quantity > 0
        """, (user_id,))
        
        portfolio = []
        for row in cursor.fetchall():
            portfolio.append({
                'stock_id': row[0],
                'symbol': row[1],
                'company_name': row[2],
                'exchange': row[3],
                'quantity': row[4],
                'avg_price': row[5] or 0
            })
        
        self._close_connection(conn)
        return portfolio
    
    # Alert operations
    def add_alert(self, stock_id: int, alert_type: str, alert_message: str,
                 announcement_details: str = None, announcement_url: str = None) -> int:
        """Add an alert"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO alerts 
            (stock_id, alert_type, alert_message, announcement_details, announcement_url)
            VALUES (?, ?, ?, ?, ?)
        """, (stock_id, alert_type, alert_message, announcement_details, announcement_url))
        
        alert_id = cursor.lastrowid
        conn.commit()
        self._close_connection(conn)
        
        return alert_id
    
    def get_user_alerts(self, user_id: int, unread_only: bool = False) -> List[Dict]:
        """Get alerts for user's stocks"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT a.alert_id, a.stock_id, s.symbol, a.alert_type, 
                   a.alert_message, a.announcement_details, a.announcement_url,
                   a.triggered_at, a.is_read
            FROM alerts a
            JOIN stocks s ON a.stock_id = s.stock_id
            WHERE s.user_id = ?
        """
        
        if unread_only:
            query += " AND a.is_read = 0"
        
        query += " ORDER BY a.triggered_at DESC"
        
        cursor.execute(query, (user_id,))
        
        alerts = []
        for row in cursor.fetchall():
            alerts.append({
                'alert_id': row[0],
                'stock_id': row[1],
                'symbol': row[2],
                'alert_type': row[3],
                'alert_message': row[4],
                'announcement_details': row[5],
                'announcement_url': row[6],
                'triggered_at': row[7],
                'is_read': bool(row[8])
            })
        
        self._close_connection(conn)
        return alerts
    
    def mark_alert_as_read(self, alert_id: int):
        """Mark an alert as read"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("UPDATE alerts SET is_read = 1 WHERE alert_id = ?", (alert_id,))
        
        conn.commit()
        self._close_connection(conn)
    
    # AI Summary operations
    def save_ai_summary(self, alert_id: int, summary_text: str, 
                       sentiment: str, impact_analysis: str = None) -> int:
        """Save AI-generated summary"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO ai_summaries (alert_id, summary_text, sentiment, impact_analysis)
            VALUES (?, ?, ?, ?)
        """, (alert_id, summary_text, sentiment, impact_analysis))
        
        summary_id = cursor.lastrowid
        conn.commit()
        self._close_connection(conn)
        
        return summary_id
    
    def get_alert_summary(self, alert_id: int) -> Optional[Dict]:
        """Get AI summary for an alert"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT summary_id, summary_text, sentiment, impact_analysis, generated_at
            FROM ai_summaries WHERE alert_id = ?
            ORDER BY generated_at DESC LIMIT 1
        """, (alert_id,))
        
        row = cursor.fetchone()
        self._close_connection(conn)
        
        if row:
            return {
                'summary_id': row[0],
                'summary_text': row[1],
                'sentiment': row[2],
                'impact_analysis': row[3],
                'generated_at': row[4]
            }
        return None
    
    # Price history operations
    def save_price(self, stock_id: int, price: float):
        """Save current stock price"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO price_history (stock_id, price)
            VALUES (?, ?)
        """, (stock_id, price))
        
        conn.commit()
        self._close_connection(conn)
    
    def get_latest_price(self, stock_id: int) -> Optional[float]:
        """Get latest price for a stock"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT price FROM price_history 
            WHERE stock_id = ?
            ORDER BY recorded_at DESC LIMIT 1
        """, (stock_id,))
        
        row = cursor.fetchone()
        self._close_connection(conn)
        
        return row[0] if row else None

    def update_transaction(self, transaction_id: int, **updates) -> bool:
        '''Update a transaction with new values'''
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Build UPDATE query dynamically based on provided fields
        valid_fields = ['transaction_type', 'quantity', 'price_per_share', 'transaction_date', 
                    'investment_horizon', 'target_price', 'thesis']
        
        update_fields = []
        values = []
        for field, value in updates.items():
            if field in valid_fields:
                update_fields.append(f"{field} = ?")
                values.append(value)
        
        if not update_fields:
            return False
        
        query = f"UPDATE transactions SET {', '.join(update_fields)} WHERE transaction_id = ?"
        values.append(transaction_id)
        
        cursor.execute(query, values)
        conn.commit()
        self._close_connection(conn)
        
        return True

    def delete_transaction(self, transaction_id: int) -> bool:
        '''Delete a transaction'''
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM transactions WHERE transaction_id = ?", 
                    (transaction_id,))
        
        conn.commit()
        self._close_connection(conn)
        
        return True

    def delete_stock(self, stock_id: int) -> bool:
        """Delete a stock and all related records."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM ai_summaries WHERE alert_id IN (SELECT alert_id FROM alerts WHERE stock_id = ?)", (stock_id,))
        cursor.execute("DELETE FROM alerts WHERE stock_id = ?", (stock_id,))
        cursor.execute("DELETE FROM transactions WHERE stock_id = ?", (stock_id,))
        cursor.execute("DELETE FROM price_history WHERE stock_id = ?", (stock_id,))
        cursor.execute("DELETE FROM stocks WHERE stock_id = ?", (stock_id,))

        conn.commit()
        self._close_connection(conn)
        return True

    # Symbol master operations
    def upsert_symbol_master(
        self,
        symbol: str,
        company_name: str,
        exchange: str = 'NSE',
        bse_code: str = None,
        nse_code: str = None,
        sector: str = None,
        source: str = 'MANUAL',
        quote_symbol_yahoo: str = None
    ) -> int:
        """Insert or update a symbol master record and return symbol_id."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO symbol_master
            (symbol, company_name, exchange, bse_code, nse_code, sector, source, quote_symbol_yahoo, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(symbol) DO UPDATE SET
                company_name = excluded.company_name,
                exchange = excluded.exchange,
                bse_code = COALESCE(excluded.bse_code, symbol_master.bse_code),
                nse_code = COALESCE(excluded.nse_code, symbol_master.nse_code),
                sector = COALESCE(excluded.sector, symbol_master.sector),
                source = excluded.source,
                quote_symbol_yahoo = COALESCE(excluded.quote_symbol_yahoo, symbol_master.quote_symbol_yahoo),
                is_active = 1,
                last_updated = CURRENT_TIMESTAMP
        """, (symbol.upper().strip(), company_name.strip(), exchange.strip(), bse_code, nse_code, sector, source, quote_symbol_yahoo))

        conn.commit()

        cursor.execute("SELECT symbol_id FROM symbol_master WHERE symbol = ?", (symbol.upper().strip(),))
        row = cursor.fetchone()
        self._close_connection(conn)
        return row[0]

    def search_symbol_master(self, query: str, limit: int = 20) -> List[Dict]:
        """Search symbol master by symbol or company name."""
        conn = self.get_connection()
        cursor = conn.cursor()

        pattern = f"%{query.strip()}%"
        cursor.execute("""
            SELECT symbol_id, symbol, company_name, exchange, bse_code, nse_code, sector, quote_symbol_yahoo
            FROM symbol_master
            WHERE is_active = 1
              AND (symbol LIKE ? OR company_name LIKE ?)
            ORDER BY
                CASE WHEN symbol = ? THEN 0 ELSE 1 END,
                symbol
            LIMIT ?
        """, (pattern, pattern, query.strip().upper(), limit))

        rows = cursor.fetchall()
        self._close_connection(conn)
        return [
            {
                'symbol_id': row[0],
                'symbol': row[1],
                'company_name': row[2],
                'exchange': row[3],
                'bse_code': row[4],
                'nse_code': row[5],
                'sector': row[6],
                'quote_symbol_yahoo': row[7]
            }
            for row in rows
        ]

    def get_symbol_by_symbol(self, symbol: str) -> Optional[Dict]:
        """Get symbol master record by symbol."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT symbol_id, symbol, company_name, exchange, bse_code, nse_code, sector, quote_symbol_yahoo
            FROM symbol_master
            WHERE symbol = ?
        """, (symbol.upper().strip(),))

        row = cursor.fetchone()
        self._close_connection(conn)
        if not row:
            return None
        return {
            'symbol_id': row[0],
            'symbol': row[1],
            'company_name': row[2],
            'exchange': row[3],
            'bse_code': row[4],
            'nse_code': row[5],
            'sector': row[6],
            'quote_symbol_yahoo': row[7]
        }

    # Quarterly financials operations
    def upsert_quarterly_financials(
        self,
        symbol_id: int,
        fiscal_year: int,
        fiscal_quarter: str,
        period_end_date: str = None,
        total_sales: float = None,
        ebitda: float = None,
        ebit: float = None,
        pbt: float = None,
        pat: float = None,
        eps: float = None,
        book_value_per_share: float = None,
        source_url: str = None
    ) -> int:
        """Insert or update quarterly financials and return result_id."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO financials_quarterly
            (symbol_id, fiscal_year, fiscal_quarter, period_end_date, total_sales, ebitda, ebit,
             pbt, pat, eps, book_value_per_share, source_url, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(symbol_id, fiscal_year, fiscal_quarter) DO UPDATE SET
                period_end_date = COALESCE(excluded.period_end_date, financials_quarterly.period_end_date),
                total_sales = COALESCE(excluded.total_sales, financials_quarterly.total_sales),
                ebitda = COALESCE(excluded.ebitda, financials_quarterly.ebitda),
                ebit = COALESCE(excluded.ebit, financials_quarterly.ebit),
                pbt = COALESCE(excluded.pbt, financials_quarterly.pbt),
                pat = COALESCE(excluded.pat, financials_quarterly.pat),
                eps = COALESCE(excluded.eps, financials_quarterly.eps),
                book_value_per_share = COALESCE(excluded.book_value_per_share, financials_quarterly.book_value_per_share),
                source_url = COALESCE(excluded.source_url, financials_quarterly.source_url),
                fetched_at = CURRENT_TIMESTAMP
        """, (
            symbol_id, fiscal_year, fiscal_quarter, period_end_date, total_sales, ebitda, ebit,
            pbt, pat, eps, book_value_per_share, source_url
        ))
        conn.commit()

        cursor.execute("""
            SELECT result_id FROM financials_quarterly
            WHERE symbol_id = ? AND fiscal_year = ? AND fiscal_quarter = ?
        """, (symbol_id, fiscal_year, fiscal_quarter))
        row = cursor.fetchone()
        self._close_connection(conn)
        return row[0]

    def get_quarterly_financials(self, symbol_id: int, limit: int = 8) -> List[Dict]:
        """Get latest quarterly financials for a symbol."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT fiscal_year, fiscal_quarter, period_end_date, total_sales, ebitda, ebit,
                   pbt, pat, eps, book_value_per_share, source_url, fetched_at
            FROM financials_quarterly
            WHERE symbol_id = ?
            ORDER BY fiscal_year DESC,
                CASE fiscal_quarter WHEN 'Q4' THEN 4 WHEN 'Q3' THEN 3 WHEN 'Q2' THEN 2 WHEN 'Q1' THEN 1 ELSE 0 END DESC
            LIMIT ?
        """, (symbol_id, limit))
        rows = cursor.fetchall()
        self._close_connection(conn)
        return [
            {
                'fiscal_year': row[0],
                'fiscal_quarter': row[1],
                'period_end_date': row[2],
                'total_sales': row[3],
                'ebitda': row[4],
                'ebit': row[5],
                'pbt': row[6],
                'pat': row[7],
                'eps': row[8],
                'book_value_per_share': row[9],
                'source_url': row[10],
                'fetched_at': row[11]
            }
            for row in rows
        ]

    # Annual balance sheet operations
    def upsert_annual_balance_sheet(
        self,
        symbol_id: int,
        fiscal_year: int,
        total_assets: float = None,
        total_liabilities: float = None,
        total_equity: float = None,
        cash_and_equivalents: float = None,
        total_debt: float = None,
        net_worth: float = None,
        source_url: str = None
    ) -> int:
        """Insert or update annual balance sheet and return balance_sheet_id."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO balance_sheet_annual
            (symbol_id, fiscal_year, total_assets, total_liabilities, total_equity, cash_and_equivalents,
             total_debt, net_worth, source_url, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(symbol_id, fiscal_year) DO UPDATE SET
                total_assets = COALESCE(excluded.total_assets, balance_sheet_annual.total_assets),
                total_liabilities = COALESCE(excluded.total_liabilities, balance_sheet_annual.total_liabilities),
                total_equity = COALESCE(excluded.total_equity, balance_sheet_annual.total_equity),
                cash_and_equivalents = COALESCE(excluded.cash_and_equivalents, balance_sheet_annual.cash_and_equivalents),
                total_debt = COALESCE(excluded.total_debt, balance_sheet_annual.total_debt),
                net_worth = COALESCE(excluded.net_worth, balance_sheet_annual.net_worth),
                source_url = COALESCE(excluded.source_url, balance_sheet_annual.source_url),
                fetched_at = CURRENT_TIMESTAMP
        """, (
            symbol_id, fiscal_year, total_assets, total_liabilities, total_equity,
            cash_and_equivalents, total_debt, net_worth, source_url
        ))
        conn.commit()

        cursor.execute("""
            SELECT balance_sheet_id FROM balance_sheet_annual
            WHERE symbol_id = ? AND fiscal_year = ?
        """, (symbol_id, fiscal_year))
        row = cursor.fetchone()
        self._close_connection(conn)
        return row[0]

    # Financial ratios operations
    def upsert_financial_ratios(
        self,
        symbol_id: int,
        as_of_date: str,
        eps_ttm: float = None,
        book_value_per_share: float = None,
        total_sales_ttm: float = None,
        ebitda_ttm: float = None,
        enterprise_value: float = None,
        market_cap: float = None,
        pe_ratio: float = None,
        pb_ratio: float = None,
        ps_ratio: float = None,
        ev_to_ebitda: float = None,
        close_price: float = None,
        source: str = 'CALCULATED'
    ) -> int:
        """Insert or update financial ratios snapshot and return ratio_id."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO financial_ratios
            (symbol_id, as_of_date, eps_ttm, book_value_per_share, total_sales_ttm, ebitda_ttm,
             enterprise_value, market_cap, pe_ratio, pb_ratio, ps_ratio, ev_to_ebitda, close_price, source, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(symbol_id, as_of_date) DO UPDATE SET
                eps_ttm = COALESCE(excluded.eps_ttm, financial_ratios.eps_ttm),
                book_value_per_share = COALESCE(excluded.book_value_per_share, financial_ratios.book_value_per_share),
                total_sales_ttm = COALESCE(excluded.total_sales_ttm, financial_ratios.total_sales_ttm),
                ebitda_ttm = COALESCE(excluded.ebitda_ttm, financial_ratios.ebitda_ttm),
                enterprise_value = COALESCE(excluded.enterprise_value, financial_ratios.enterprise_value),
                market_cap = COALESCE(excluded.market_cap, financial_ratios.market_cap),
                pe_ratio = COALESCE(excluded.pe_ratio, financial_ratios.pe_ratio),
                pb_ratio = COALESCE(excluded.pb_ratio, financial_ratios.pb_ratio),
                ps_ratio = COALESCE(excluded.ps_ratio, financial_ratios.ps_ratio),
                ev_to_ebitda = COALESCE(excluded.ev_to_ebitda, financial_ratios.ev_to_ebitda),
                close_price = COALESCE(excluded.close_price, financial_ratios.close_price),
                source = excluded.source,
                fetched_at = CURRENT_TIMESTAMP
        """, (
            symbol_id, as_of_date, eps_ttm, book_value_per_share, total_sales_ttm, ebitda_ttm,
            enterprise_value, market_cap, pe_ratio, pb_ratio, ps_ratio, ev_to_ebitda, close_price, source
        ))
        conn.commit()

        cursor.execute("""
            SELECT ratio_id FROM financial_ratios
            WHERE symbol_id = ? AND as_of_date = ?
        """, (symbol_id, as_of_date))
        row = cursor.fetchone()
        self._close_connection(conn)
        return row[0]

    def get_latest_financial_ratios(self, symbol_id: int) -> Optional[Dict]:
        """Get latest financial ratio snapshot for symbol."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT as_of_date, eps_ttm, book_value_per_share, total_sales_ttm, ebitda_ttm,
                   enterprise_value, market_cap, pe_ratio, pb_ratio, ps_ratio, ev_to_ebitda, close_price, source, fetched_at
            FROM financial_ratios
            WHERE symbol_id = ?
            ORDER BY as_of_date DESC
            LIMIT 1
        """, (symbol_id,))
        row = cursor.fetchone()
        self._close_connection(conn)
        if not row:
            return None
        return {
            'as_of_date': row[0],
            'eps_ttm': row[1],
            'book_value_per_share': row[2],
            'total_sales_ttm': row[3],
            'ebitda_ttm': row[4],
            'enterprise_value': row[5],
            'market_cap': row[6],
            'pe_ratio': row[7],
            'pb_ratio': row[8],
            'ps_ratio': row[9],
            'ev_to_ebitda': row[10],
            'close_price': row[11],
            'source': row[12],
            'fetched_at': row[13]
        }

    # BSE announcement feed operations
    def add_bse_announcement(
        self,
        headline: str,
        rss_guid: str = None,
        symbol_id: int = None,
        scrip_code: str = None,
        category: str = None,
        announcement_date: str = None,
        attachment_url: str = None,
        exchange_ref_id: str = None,
        raw_payload: str = None
    ) -> int:
        """Insert BSE announcement if not already present; returns announcement_id."""
        conn = self.get_connection()
        cursor = conn.cursor()
        # Resolve existing row by any stable unique key.
        existing_id = None
        if exchange_ref_id:
            cursor.execute("SELECT announcement_id FROM bse_announcements WHERE exchange_ref_id = ?", (exchange_ref_id,))
            row = cursor.fetchone()
            if row:
                existing_id = row[0]

        if existing_id is None and rss_guid:
            cursor.execute("SELECT announcement_id FROM bse_announcements WHERE rss_guid = ?", (rss_guid,))
            row = cursor.fetchone()
            if row:
                existing_id = row[0]

        if existing_id is not None:
            cursor.execute("""
                UPDATE bse_announcements
                SET symbol_id = COALESCE(?, symbol_id),
                    scrip_code = COALESCE(?, scrip_code),
                    headline = ?,
                    category = COALESCE(?, category),
                    announcement_date = COALESCE(?, announcement_date),
                    attachment_url = COALESCE(?, attachment_url),
                    exchange_ref_id = COALESCE(?, exchange_ref_id),
                    rss_guid = COALESCE(?, rss_guid),
                    raw_payload = COALESCE(?, raw_payload),
                    fetched_at = CURRENT_TIMESTAMP
                WHERE announcement_id = ?
            """, (
                symbol_id, scrip_code, headline, category, announcement_date, attachment_url,
                exchange_ref_id, rss_guid, raw_payload, existing_id
            ))
            conn.commit()
            self._close_connection(conn)
            return existing_id

        cursor.execute("""
            INSERT INTO bse_announcements
            (symbol_id, scrip_code, headline, category, announcement_date, attachment_url,
             exchange_ref_id, rss_guid, raw_payload, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (symbol_id, scrip_code, headline, category, announcement_date, attachment_url, exchange_ref_id, rss_guid, raw_payload))
        conn.commit()
        cursor.execute("SELECT announcement_id FROM bse_announcements WHERE rowid = last_insert_rowid()")
        row = cursor.fetchone()
        self._close_connection(conn)
        return row[0]

    def get_unprocessed_bse_announcements(self, limit: int = 100) -> List[Dict]:
        """Fetch unprocessed BSE announcements for downstream parsing."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT announcement_id, symbol_id, scrip_code, headline, category, announcement_date,
                   attachment_url, exchange_ref_id, rss_guid, raw_payload, fetched_at
            FROM bse_announcements
            WHERE processed = 0
            ORDER BY announcement_date DESC, announcement_id DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        self._close_connection(conn)
        return [
            {
                'announcement_id': row[0],
                'symbol_id': row[1],
                'scrip_code': row[2],
                'headline': row[3],
                'category': row[4],
                'announcement_date': row[5],
                'attachment_url': row[6],
                'exchange_ref_id': row[7],
                'rss_guid': row[8],
                'raw_payload': row[9],
                'fetched_at': row[10]
            }
            for row in rows
        ]

    def mark_bse_announcement_processed(self, announcement_id: int):
        """Mark BSE announcement as processed."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE bse_announcements
            SET processed = 1
            WHERE announcement_id = ?
        """, (announcement_id,))
        conn.commit()
        self._close_connection(conn)

    def get_bse_announcements_by_symbol_ids(self, symbol_ids: List[int], limit: int = 200) -> List[Dict]:
        """Fetch latest BSE announcements for given symbol_ids."""
        if not symbol_ids:
            return []

        conn = self.get_connection()
        cursor = conn.cursor()
        placeholders = ",".join(["?"] * len(symbol_ids))
        query = f"""
            SELECT announcement_id, symbol_id, scrip_code, headline, category, announcement_date,
                   attachment_url, exchange_ref_id, rss_guid, raw_payload, processed, fetched_at
            FROM bse_announcements
            WHERE symbol_id IN ({placeholders})
            ORDER BY announcement_date DESC, announcement_id DESC
            LIMIT ?
        """
        cursor.execute(query, (*symbol_ids, limit))
        rows = cursor.fetchall()
        self._close_connection(conn)
        return [
            {
                'announcement_id': row[0],
                'symbol_id': row[1],
                'scrip_code': row[2],
                'headline': row[3],
                'category': row[4],
                'announcement_date': row[5],
                'attachment_url': row[6],
                'exchange_ref_id': row[7],
                'rss_guid': row[8],
                'raw_payload': row[9],
                'processed': bool(row[10]),
                'fetched_at': row[11]
            }
            for row in rows
        ]

    def get_recent_bse_announcements(self, limit: int = 1000) -> List[Dict]:
        """Fetch latest BSE announcements regardless of symbol mapping."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT announcement_id, symbol_id, scrip_code, headline, category, announcement_date,
                   attachment_url, exchange_ref_id, rss_guid, raw_payload, processed, fetched_at
            FROM bse_announcements
            ORDER BY announcement_date DESC, announcement_id DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        self._close_connection(conn)
        return [
            {
                'announcement_id': row[0],
                'symbol_id': row[1],
                'scrip_code': row[2],
                'headline': row[3],
                'category': row[4],
                'announcement_date': row[5],
                'attachment_url': row[6],
                'exchange_ref_id': row[7],
                'rss_guid': row[8],
                'raw_payload': row[9],
                'processed': bool(row[10]),
                'fetched_at': row[11]
            }
            for row in rows
        ]

    def get_bse_announcements_by_scrip_codes(self, scrip_codes: List[str], limit: int = 5000) -> List[Dict]:
        """Fetch latest BSE announcements for provided BSE scrip codes."""
        normalized = [str(code).strip() for code in (scrip_codes or []) if str(code).strip()]
        if not normalized:
            return []

        conn = self.get_connection()
        cursor = conn.cursor()
        placeholders = ",".join(["?"] * len(normalized))
        query = f"""
            SELECT announcement_id, symbol_id, scrip_code, headline, category, announcement_date,
                   attachment_url, exchange_ref_id, rss_guid, raw_payload, processed, fetched_at
            FROM bse_announcements
            WHERE scrip_code IN ({placeholders})
            ORDER BY announcement_date DESC, announcement_id DESC
            LIMIT ?
        """
        cursor.execute(query, (*normalized, limit))
        rows = cursor.fetchall()
        self._close_connection(conn)
        return [
            {
                'announcement_id': row[0],
                'symbol_id': row[1],
                'scrip_code': row[2],
                'headline': row[3],
                'category': row[4],
                'announcement_date': row[5],
                'attachment_url': row[6],
                'exchange_ref_id': row[7],
                'rss_guid': row[8],
                'raw_payload': row[9],
                'processed': bool(row[10]),
                'fetched_at': row[11]
            }
            for row in rows
        ]

    def get_symbol_by_bse_code(self, bse_code: str) -> Optional[Dict]:
        """Get symbol master record by exact BSE code."""
        if not bse_code:
            return None
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT symbol_id, symbol, company_name, exchange, bse_code, nse_code, sector, quote_symbol_yahoo
            FROM symbol_master
            WHERE bse_code = ?
            LIMIT 1
        """, (str(bse_code).strip(),))
        row = cursor.fetchone()
        self._close_connection(conn)
        if not row:
            return None
        return {
            'symbol_id': row[0],
            'symbol': row[1],
            'company_name': row[2],
            'exchange': row[3],
            'bse_code': row[4],
            'nse_code': row[5],
            'sector': row[6],
            'quote_symbol_yahoo': row[7]
        }

    # Filings operations
    def upsert_filing(
        self,
        stock_id: int,
        category: str,
        headline: str,
        announcement_summary: str = None,
        announcement_date: str = None,
        pdf_link: str = None,
        source_exchange: str = "BSE",
        source_ref: str = None,
        symbol_id: int = None,
    ) -> int:
        """Insert or update filing by source_ref, returns filing_id."""
        conn = self.get_connection()
        cursor = conn.cursor()

        existing_id = None
        if source_ref:
            cursor.execute("SELECT filing_id FROM filings WHERE source_ref = ?", (source_ref,))
            row = cursor.fetchone()
            if row:
                existing_id = row[0]

        if existing_id is not None:
            cursor.execute("""
                UPDATE filings
                SET stock_id = ?,
                    symbol_id = COALESCE(?, symbol_id),
                    category = ?,
                    headline = ?,
                    announcement_summary = COALESCE(?, announcement_summary),
                    announcement_date = COALESCE(?, announcement_date),
                    pdf_link = COALESCE(?, pdf_link),
                    source_exchange = COALESCE(?, source_exchange)
                WHERE filing_id = ?
            """, (
                stock_id, symbol_id, category, headline, announcement_summary, announcement_date,
                pdf_link, source_exchange, existing_id
            ))
            conn.commit()
            self._close_connection(conn)
            return existing_id

        cursor.execute("""
            INSERT INTO filings
            (stock_id, symbol_id, category, headline, announcement_summary, announcement_date,
             pdf_link, source_exchange, source_ref, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            stock_id, symbol_id, category, headline, announcement_summary, announcement_date,
            pdf_link, source_exchange, source_ref
        ))
        conn.commit()
        cursor.execute("SELECT filing_id FROM filings WHERE rowid = last_insert_rowid()")
        row = cursor.fetchone()
        self._close_connection(conn)
        return row[0]

    def get_user_filings(
        self,
        user_id: int,
        stock_id: int = None,
        category: str = None,
        limit: int = 500
    ) -> List[Dict]:
        """Get filings for user's portfolio with optional filters."""
        conn = self.get_connection()
        cursor = conn.cursor()

        query = """
            SELECT f.filing_id, f.category, f.headline, f.announcement_summary, f.announcement_date,
                   f.pdf_link, f.source_exchange, f.source_ref,
                   s.stock_id, s.symbol, s.company_name, s.exchange,
                   sm.bse_code, sm.nse_code, sm.sector
            FROM filings f
            JOIN stocks s ON f.stock_id = s.stock_id
            LEFT JOIN symbol_master sm
                ON sm.symbol = s.symbol
               OR sm.symbol = REPLACE(REPLACE(UPPER(s.symbol), '.NS', ''), '.BO', '')
            WHERE s.user_id = ?
        """
        params = [user_id]
        if stock_id is not None:
            query += " AND s.stock_id = ?"
            params.append(stock_id)
        if category and category != "ALL":
            query += " AND f.category = ?"
            params.append(category)

        query += " ORDER BY f.announcement_date DESC, f.filing_id DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        self._close_connection(conn)
        return [
            {
                'filing_id': row[0],
                'category': row[1],
                'headline': row[2],
                'announcement_summary': row[3],
                'announcement_date': row[4],
                'pdf_link': row[5],
                'source_exchange': row[6],
                'source_ref': row[7],
                'stock_id': row[8],
                'symbol': row[9],
                'company_name': row[10],
                'exchange': row[11],
                'bse_code': row[12],
                'nse_code': row[13],
                'industry': row[14],
            }
            for row in rows
        ]

    # Insight snapshot operations
    def upsert_insight_snapshot(
        self,
        stock_id: int,
        quarter_label: str,
        insight_type: str,
        summary_text: str = None,
        sentiment: str = None,
        status: str = "GENERATED",
        source_filing_id: int = None,
        source_ref: str = None,
        provider: str = None,
        model_version: str = None,
    ) -> int:
        """Insert/update one quarter insight snapshot and return snapshot_id."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO insight_snapshots
            (stock_id, quarter_label, insight_type, source_filing_id, source_ref, summary_text, sentiment,
             status, provider, model_version, generated_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(stock_id, quarter_label, insight_type) DO UPDATE SET
                source_filing_id = COALESCE(excluded.source_filing_id, insight_snapshots.source_filing_id),
                source_ref = COALESCE(excluded.source_ref, insight_snapshots.source_ref),
                summary_text = COALESCE(excluded.summary_text, insight_snapshots.summary_text),
                sentiment = COALESCE(excluded.sentiment, insight_snapshots.sentiment),
                status = COALESCE(excluded.status, insight_snapshots.status),
                provider = COALESCE(excluded.provider, insight_snapshots.provider),
                model_version = COALESCE(excluded.model_version, insight_snapshots.model_version),
                updated_at = CURRENT_TIMESTAMP
        """, (
            stock_id, quarter_label, insight_type, source_filing_id, source_ref, summary_text, sentiment,
            status, provider, model_version
        ))
        conn.commit()
        cursor.execute("""
            SELECT snapshot_id
            FROM insight_snapshots
            WHERE stock_id = ? AND quarter_label = ? AND insight_type = ?
            LIMIT 1
        """, (stock_id, quarter_label, insight_type))
        row = cursor.fetchone()
        self._close_connection(conn)
        return row[0]

    def get_insight_snapshot(self, stock_id: int, quarter_label: str, insight_type: str) -> Optional[Dict]:
        """Get one insight snapshot if exists."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT snapshot_id, stock_id, quarter_label, insight_type, source_filing_id, source_ref,
                   summary_text, sentiment, status, provider, model_version, generated_at, updated_at
            FROM insight_snapshots
            WHERE stock_id = ? AND quarter_label = ? AND insight_type = ?
            LIMIT 1
        """, (stock_id, quarter_label, insight_type))
        row = cursor.fetchone()
        self._close_connection(conn)
        if not row:
            return None
        return {
            "snapshot_id": row[0],
            "stock_id": row[1],
            "quarter_label": row[2],
            "insight_type": row[3],
            "source_filing_id": row[4],
            "source_ref": row[5],
            "summary_text": row[6],
            "sentiment": row[7],
            "status": row[8],
            "provider": row[9],
            "model_version": row[10],
            "generated_at": row[11],
            "updated_at": row[12],
        }

    def get_user_insight_snapshots(self, user_id: int, quarter_label: str = None, limit: int = 500) -> List[Dict]:
        """List portfolio insight snapshots with stock metadata."""
        conn = self.get_connection()
        cursor = conn.cursor()
        query = """
            SELECT i.snapshot_id, i.stock_id, i.quarter_label, i.insight_type, i.source_filing_id, i.source_ref,
                   i.summary_text, i.sentiment, i.status, i.provider, i.model_version, i.generated_at, i.updated_at,
                   s.symbol, s.company_name, s.exchange
            FROM insight_snapshots i
            JOIN stocks s ON s.stock_id = i.stock_id
            WHERE s.user_id = ?
        """
        params = [user_id]
        if quarter_label:
            query += " AND i.quarter_label = ?"
            params.append(quarter_label)
        query += " ORDER BY i.quarter_label DESC, s.symbol ASC, i.insight_type ASC LIMIT ?"
        params.append(limit)
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        self._close_connection(conn)
        return [
            {
                "snapshot_id": row[0],
                "stock_id": row[1],
                "quarter_label": row[2],
                "insight_type": row[3],
                "source_filing_id": row[4],
                "source_ref": row[5],
                "summary_text": row[6],
                "sentiment": row[7],
                "status": row[8],
                "provider": row[9],
                "model_version": row[10],
                "generated_at": row[11],
                "updated_at": row[12],
                "symbol": row[13],
                "company_name": row[14],
                "exchange": row[15],
            }
            for row in rows
        ]

    def get_latest_filing_dates_by_stock(self, user_id: int) -> Dict[int, str]:
        """Return latest announcement_date string per stock in user portfolio."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT f.stock_id, MAX(f.announcement_date)
            FROM filings f
            JOIN stocks s ON s.stock_id = f.stock_id
            WHERE s.user_id = ?
            GROUP BY f.stock_id
        """, (user_id,))
        rows = cursor.fetchall()
        self._close_connection(conn)
        return {row[0]: row[1] for row in rows if row[0]}

    # Analyst consensus operations
    def upsert_analyst_consensus(
        self,
        stock_id: int,
        report_text: str = None,
        status: str = "GENERATED",
        provider: str = None,
        as_of_date: str = None,
    ) -> int:
        """Insert/update one analyst consensus report for a stock and return consensus_id."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO analyst_consensus
            (stock_id, report_text, status, provider, as_of_date, generated_at, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(stock_id) DO UPDATE SET
                report_text = COALESCE(excluded.report_text, analyst_consensus.report_text),
                status = COALESCE(excluded.status, analyst_consensus.status),
                provider = COALESCE(excluded.provider, analyst_consensus.provider),
                as_of_date = COALESCE(excluded.as_of_date, analyst_consensus.as_of_date),
                updated_at = CURRENT_TIMESTAMP
        """, (stock_id, report_text, status, provider, as_of_date))
        conn.commit()
        cursor.execute("""
            SELECT consensus_id
            FROM analyst_consensus
            WHERE stock_id = ?
            LIMIT 1
        """, (stock_id,))
        row = cursor.fetchone()
        self._close_connection(conn)
        return row[0]

    def get_analyst_consensus(self, stock_id: int) -> Optional[Dict]:
        """Get analyst consensus report for a stock if available."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT consensus_id, stock_id, report_text, status, provider, as_of_date, generated_at, updated_at
            FROM analyst_consensus
            WHERE stock_id = ?
            LIMIT 1
        """, (stock_id,))
        row = cursor.fetchone()
        self._close_connection(conn)
        if not row:
            return None
        return {
            "consensus_id": row[0],
            "stock_id": row[1],
            "report_text": row[2],
            "status": row[3],
            "provider": row[4],
            "as_of_date": row[5],
            "generated_at": row[6],
            "updated_at": row[7],
        }

    def get_transaction_by_id(self, transaction_id: int) -> Optional[Dict]:
        '''Get a single transaction by ID'''
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT transaction_id, stock_id, transaction_type, quantity, 
                price_per_share, transaction_date, investment_horizon,
                target_price, thesis
            FROM transactions WHERE transaction_id = ?
        ''', (transaction_id,))
        
        row = cursor.fetchone()
        self._close_connection(conn)
        
        if row:
            return {
                'transaction_id': row[0],
                'stock_id': row[1],
                'transaction_type': row[2],
                'quantity': row[3],
                'price_per_share': row[4],
                'transaction_date': row[5],
                'investment_horizon': row[6],
                'target_price': row[7],
                'thesis': row[8]
            }
        return None

    # App settings operations
    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Read a key from app_settings."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        self._close_connection(conn)
        return row[0] if row else default

    def set_setting(self, key: str, value: Optional[str]) -> None:
        """Upsert a key/value in app_settings."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO app_settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
        """, (key, value))
        conn.commit()
        self._close_connection(conn)

    # BSE daily prices operations
    def upsert_bse_daily_price(
        self,
        bse_code: str,
        trade_date: str,
        close_price: float,
        open_price: float = None,
        high_price: float = None,
        low_price: float = None,
        total_shares_traded: float = None,
        total_trades: float = None,
        turnover: float = None,
        source: str = "BSE_BHAVCOPY",
    ) -> int:
        """Insert/update one BSE daily OHLCV row and return price_id."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO bse_daily_prices
            (bse_code, trade_date, open_price, high_price, low_price, close_price,
             total_shares_traded, total_trades, turnover, source, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(bse_code, trade_date) DO UPDATE SET
                open_price = COALESCE(excluded.open_price, bse_daily_prices.open_price),
                high_price = COALESCE(excluded.high_price, bse_daily_prices.high_price),
                low_price = COALESCE(excluded.low_price, bse_daily_prices.low_price),
                close_price = excluded.close_price,
                total_shares_traded = COALESCE(excluded.total_shares_traded, bse_daily_prices.total_shares_traded),
                total_trades = COALESCE(excluded.total_trades, bse_daily_prices.total_trades),
                turnover = COALESCE(excluded.turnover, bse_daily_prices.turnover),
                source = COALESCE(excluded.source, bse_daily_prices.source),
                fetched_at = CURRENT_TIMESTAMP
        """, (
            str(bse_code).strip(), trade_date, open_price, high_price, low_price, close_price,
            total_shares_traded, total_trades, turnover, source
        ))
        conn.commit()
        cursor.execute("SELECT price_id FROM bse_daily_prices WHERE bse_code = ? AND trade_date = ?", (str(bse_code).strip(), trade_date))
        row = cursor.fetchone()
        self._close_connection(conn)
        return row[0]

    def get_bse_daily_prices(self, bse_code: str, start_date: str = None, end_date: str = None, limit: int = 400) -> List[Dict]:
        """Get BSE OHLCV series for one scrip code."""
        conn = self.get_connection()
        cursor = conn.cursor()
        query = """
            SELECT bse_code, trade_date, open_price, high_price, low_price, close_price,
                   total_shares_traded, total_trades, turnover
            FROM bse_daily_prices
            WHERE bse_code = ?
        """
        params = [str(bse_code).strip()]
        if start_date:
            query += " AND trade_date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND trade_date <= ?"
            params.append(end_date)
        query += " ORDER BY trade_date ASC LIMIT ?"
        params.append(limit)
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        self._close_connection(conn)
        return [
            {
                "bse_code": row[0],
                "trade_date": row[1],
                "open_price": row[2],
                "high_price": row[3],
                "low_price": row[4],
                "close_price": row[5],
                "total_shares_traded": row[6],
                "total_trades": row[7],
                "turnover": row[8],
            }
            for row in rows
        ]

    def get_portfolio_performance_series(self, user_id: int, start_date: str = None, end_date: str = None) -> List[Dict]:
        """
        Build date-wise portfolio value using BSE close prices + transactions.
        Quantity is derived as of each date from BUY/SELL transactions.
        """
        stocks = self.get_user_stocks_with_symbol_master(user_id)
        code_to_stock = {}
        for stock in stocks:
            code = (stock.get("bse_code") or "").strip()
            if code:
                code_to_stock[code] = stock
        if not code_to_stock:
            return []

        conn = self.get_connection()
        cursor = conn.cursor()

        placeholders = ",".join(["?"] * len(code_to_stock))
        query = f"""
            SELECT bse_code, trade_date, close_price
            FROM bse_daily_prices
            WHERE bse_code IN ({placeholders})
        """
        params = list(code_to_stock.keys())
        if start_date:
            query += " AND trade_date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND trade_date <= ?"
            params.append(end_date)
        query += " ORDER BY trade_date ASC"
        cursor.execute(query, tuple(params))
        price_rows = cursor.fetchall()

        tx_by_stock = {}
        for code, stock in code_to_stock.items():
            cursor.execute("""
                SELECT transaction_date, transaction_type, quantity
                FROM transactions
                WHERE stock_id = ?
                ORDER BY transaction_date ASC, transaction_id ASC
            """, (stock["stock_id"],))
            tx_by_stock[stock["stock_id"]] = cursor.fetchall()
        self._close_connection(conn)

        # Index price rows by date->code
        date_to_prices = {}
        for code, trade_date, close_price in price_rows:
            date_to_prices.setdefault(trade_date, {})[code] = float(close_price or 0.0)
        dates = sorted(date_to_prices.keys())
        if not dates:
            return []

        # Rolling quantity pointers per stock for as-of-date holdings.
        tx_idx = {sid: 0 for sid in tx_by_stock}
        qty = {sid: 0 for sid in tx_by_stock}

        series = []
        for date in dates:
            total_value = 0.0
            for code, stock in code_to_stock.items():
                sid = stock["stock_id"]
                tx_list = tx_by_stock.get(sid, [])
                while tx_idx[sid] < len(tx_list):
                    tx_date, tx_type, tx_qty = tx_list[tx_idx[sid]]
                    if tx_date and tx_date <= date:
                        delta = int(tx_qty or 0)
                        qty[sid] += delta if (tx_type or "").upper() == "BUY" else -delta
                        tx_idx[sid] += 1
                    else:
                        break
                close_price = date_to_prices.get(date, {}).get(code)
                if close_price is not None and qty[sid] > 0:
                    total_value += qty[sid] * close_price
            series.append({"trade_date": date, "portfolio_value": total_value})
        return series
