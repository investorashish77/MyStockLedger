"""
Database Manager
Handles all database operations for the Equity Tracker app
"""

import sqlite3
import json
from datetime import datetime, date
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from utils.config import config

class DatabaseManager:
    """Manages database operations"""
    
    def __init__(self, db_path: str = 'data/equity_tracker.db'):
        """Init.

        Args:
            db_path: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        self.db_path = db_path
        self._in_memory = db_path == ':memory:'
        self._shared_conn = None

        if self._in_memory:
            # Keep one shared connection alive for in-memory databases.
            # This ensures all operations access the same schema/data in tests.
            self._shared_conn = sqlite3.connect(self.db_path)
            self._create_schema(self._shared_conn)
            self._run_migrations()
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
            """Has column.

            Args:
                table: Input parameter.
                column: Input parameter.

            Returns:
                Any: Method output for caller use.
            """
            cursor.execute(f"PRAGMA table_info({table})")
            return any(row[1] == column for row in cursor.fetchall())

        # Add quote symbol mapping column for Yahoo-compatible tickers.
        if has_column("symbol_master", "quote_symbol_yahoo") is False:
            cursor.execute("ALTER TABLE symbol_master ADD COLUMN quote_symbol_yahoo TEXT")
        if has_column("symbol_master", "industry_group") is False:
            cursor.execute("ALTER TABLE symbol_master ADD COLUMN industry_group TEXT")
        if has_column("symbol_master", "industry") is False:
            cursor.execute("ALTER TABLE symbol_master ADD COLUMN industry TEXT")

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
            CREATE TABLE IF NOT EXISTS cash_ledger (
                ledger_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                entry_type TEXT NOT NULL,
                amount REAL NOT NULL,
                entry_date DATE,
                note TEXT,
                reference_transaction_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (reference_transaction_id) REFERENCES transactions(transaction_id)
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_cash_ledger_user_date
            ON cash_ledger(user_id, entry_date, ledger_id)
        """)
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
            CREATE TABLE IF NOT EXISTS global_insight_snapshots (
                snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol_id INTEGER NOT NULL,
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
                UNIQUE(symbol_id, quarter_label, insight_type)
            )
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_global_insight_snapshots_symbol_quarter ON global_insight_snapshots(symbol_id, quarter_label)"
        )

        # Journal V2 transaction fields.
        if has_column("transactions", "setup_type") is False:
            cursor.execute("ALTER TABLE transactions ADD COLUMN setup_type TEXT")
        if has_column("transactions", "confidence_score") is False:
            cursor.execute("ALTER TABLE transactions ADD COLUMN confidence_score INTEGER")
        if has_column("transactions", "risk_tags") is False:
            cursor.execute("ALTER TABLE transactions ADD COLUMN risk_tags TEXT")
        if has_column("transactions", "mistake_tags") is False:
            cursor.execute("ALTER TABLE transactions ADD COLUMN mistake_tags TEXT")
        if has_column("transactions", "reflection_note") is False:
            cursor.execute("ALTER TABLE transactions ADD COLUMN reflection_note TEXT")
        if has_column("transactions", "realized_pnl") is False:
            cursor.execute("ALTER TABLE transactions ADD COLUMN realized_pnl REAL")
        if has_column("transactions", "realized_cost_basis") is False:
            cursor.execute("ALTER TABLE transactions ADD COLUMN realized_cost_basis REAL")
        if has_column("transactions", "realized_match_method") is False:
            cursor.execute("ALTER TABLE transactions ADD COLUMN realized_match_method TEXT")
        if has_column("transactions", "sell_note") is False:
            cursor.execute("ALTER TABLE transactions ADD COLUMN sell_note TEXT")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transaction_lot_matches (
                match_id INTEGER PRIMARY KEY AUTOINCREMENT,
                sell_transaction_id INTEGER NOT NULL,
                buy_transaction_id INTEGER NOT NULL,
                matched_quantity INTEGER NOT NULL,
                buy_price_per_share REAL NOT NULL,
                sell_price_per_share REAL NOT NULL,
                realized_pnl REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_tx_lot_match_sell ON transaction_lot_matches(sell_transaction_id)"
        )

        # Filings category override fields.
        if has_column("filings", "category_override") is False:
            cursor.execute("ALTER TABLE filings ADD COLUMN category_override TEXT")
        if has_column("filings", "override_locked") is False:
            cursor.execute("ALTER TABLE filings ADD COLUMN override_locked BOOLEAN DEFAULT 0")
        if has_column("filings", "override_updated_at") is False:
            cursor.execute("ALTER TABLE filings ADD COLUMN override_updated_at TIMESTAMP")
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
        cursor.execute("""
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
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ai_response_cache_lookup
            ON ai_response_cache(task_type, provider, model, prompt_hash)
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS background_jobs (
                job_id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_type TEXT NOT NULL,
                requested_by INTEGER,
                status TEXT NOT NULL DEFAULT 'QUEUED',
                payload_json TEXT,
                progress INTEGER DEFAULT 0,
                result_json TEXT,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_background_jobs_status_created
            ON background_jobs(status, created_at)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_background_jobs_requested_by
            ON background_jobs(requested_by, created_at)
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                notif_type TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                metadata_json TEXT,
                is_read BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                read_at TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_notifications_user_read
            ON notifications(user_id, is_read, created_at)
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notification_dedupe_keys (
                dedupe_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_scope TEXT NOT NULL,
                user_id INTEGER,
                notif_type TEXT NOT NULL,
                dedupe_key TEXT NOT NULL,
                notification_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_scope, notif_type, dedupe_key)
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_notification_dedupe_scope
            ON notification_dedupe_keys(user_scope, notif_type, created_at)
        """)

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

    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """Get user by user_id."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT user_id, mobile_number, name, email, created_at
            FROM users WHERE user_id = ?
            LIMIT 1
        """, (user_id,))
        row = cursor.fetchone()
        self._close_connection(conn)
        if not row:
            return None
        return {
            'user_id': row[0],
            'mobile_number': row[1],
            'name': row[2],
            'email': row[3],
            'created_at': row[4]
        }
    
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
                   sm.symbol_id, sm.bse_code, sm.nse_code, sm.sector, sm.industry_group, sm.industry
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
                'industry_group': row[8],
                'industry': row[9],
            }
            for row in rows
        ]
    
    # Transaction operations
    def add_transaction(self, stock_id: int, transaction_type: str, quantity: int,
                       price_per_share: float, transaction_date: str,
                       investment_horizon: str, target_price: float = None,
                       thesis: str = None, setup_type: str = None,
                       confidence_score: int = None, risk_tags: str = None,
                       mistake_tags: str = None, reflection_note: str = None,
                       realized_pnl: float = None, realized_cost_basis: float = None,
                       realized_match_method: str = None, sell_note: str = None,
                       use_cash_ledger: bool = False) -> int:
        """Add a buy/sell transaction.

        For SELL transactions, realized P/L is calculated with FIFO lots unless
        explicit realized fields are supplied by caller.
        """
        tx_type = (transaction_type or "").strip().upper()
        if tx_type not in {"BUY", "SELL"}:
            raise ValueError("transaction_type must be BUY or SELL")
        if quantity <= 0:
            raise ValueError("quantity must be > 0")
        if price_per_share is None or float(price_per_share) <= 0:
            raise ValueError("price_per_share must be > 0")

        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")

        try:
            trade_amount = float(quantity) * float(price_per_share)
            user_id = None
            if use_cash_ledger:
                user_id = self._get_user_id_for_stock(conn, stock_id)
                if user_id is None:
                    raise ValueError("Unable to resolve user for stock transaction.")
                self._bootstrap_cash_ledger_for_user(conn, user_id)
                if tx_type == "BUY":
                    # Validate against the same capital model shown in sidebar:
                    # available = Deposit - Deployed.
                    available_cash = self._capital_available_for_user_conn(conn, user_id)
                    if available_cash + 1e-9 < trade_amount:
                        shortfall = trade_amount - available_cash
                        raise ValueError(
                            f"Insufficient available cash. "
                            f"Available: ₹{available_cash:,.2f}, Required: ₹{trade_amount:,.2f}, "
                            f"Shortfall: ₹{shortfall:,.2f}"
                        )
                    # Keep ledger synchronized so BUY_DEBIT does not drive it negative.
                    self._sync_ledger_balance_for_buy_conn(
                        conn=conn,
                        user_id=user_id,
                        trade_amount=trade_amount,
                        entry_date=transaction_date,
                    )

            if tx_type == "SELL" and (realized_pnl is None or realized_cost_basis is None):
                realized_pnl, realized_cost_basis, lot_matches = self._compute_fifo_realized_for_sell(
                    conn=conn,
                    stock_id=stock_id,
                    sell_quantity=quantity,
                    sell_price=float(price_per_share),
                )
                realized_match_method = realized_match_method or "FIFO"
            else:
                lot_matches = []

            cursor.execute("""
                INSERT INTO transactions
                (stock_id, transaction_type, quantity, price_per_share, transaction_date,
                 investment_horizon, target_price, thesis, setup_type, confidence_score,
                 risk_tags, mistake_tags, reflection_note, realized_pnl, realized_cost_basis,
                 realized_match_method, sell_note)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (stock_id, tx_type, quantity, price_per_share, transaction_date,
                  investment_horizon, target_price, thesis, setup_type, confidence_score,
                  risk_tags, mistake_tags, reflection_note, realized_pnl, realized_cost_basis,
                  realized_match_method, sell_note))

            transaction_id = cursor.lastrowid

            if tx_type == "SELL" and lot_matches:
                cursor.executemany(
                    """
                    INSERT INTO transaction_lot_matches
                    (sell_transaction_id, buy_transaction_id, matched_quantity,
                     buy_price_per_share, sell_price_per_share, realized_pnl)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            transaction_id,
                            m["buy_transaction_id"],
                            m["matched_quantity"],
                            m["buy_price_per_share"],
                            m["sell_price_per_share"],
                            m["realized_pnl"],
                        )
                        for m in lot_matches
                    ],
                )

            if use_cash_ledger and user_id is not None:
                if tx_type == "BUY":
                    self._add_cash_ledger_entry_conn(
                        conn=conn,
                        user_id=user_id,
                        entry_type="BUY_DEBIT",
                        amount=trade_amount,
                        entry_date=transaction_date,
                        note=f"BUY {quantity} @ ₹{float(price_per_share):,.2f}",
                        reference_transaction_id=transaction_id,
                        enforce_balance=True,
                    )
                else:
                    self._add_cash_ledger_entry_conn(
                        conn=conn,
                        user_id=user_id,
                        entry_type="SELL_CREDIT",
                        amount=trade_amount,
                        entry_date=transaction_date,
                        note=f"SELL {quantity} @ ₹{float(price_per_share):,.2f}",
                        reference_transaction_id=transaction_id,
                        enforce_balance=False,
                    )

            conn.commit()
            return transaction_id
        except Exception:
            conn.rollback()
            raise
        finally:
            self._close_connection(conn)

    def _get_stock_latest_transaction_date(self, conn, stock_id: int) -> Optional[str]:
        """Return latest transaction date for a stock."""
        cursor = conn.cursor()
        cursor.execute(
            "SELECT MAX(transaction_date) FROM transactions WHERE stock_id = ?",
            (stock_id,),
        )
        row = cursor.fetchone()
        return row[0] if row and row[0] else None

    def _compute_fifo_realized_for_sell(
        self,
        conn,
        stock_id: int,
        sell_quantity: int,
        sell_price: float,
    ) -> Tuple[float, float, List[Dict]]:
        """Compute FIFO realized P/L and lot-level matches for a sell transaction."""
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT transaction_id, transaction_type, quantity, price_per_share
            FROM transactions
            WHERE stock_id = ?
            ORDER BY transaction_date ASC, transaction_id ASC
            """,
            (stock_id,),
        )
        rows = cursor.fetchall()

        lots: List[Dict] = []
        for tx_id, tx_type, qty, price in rows:
            t = (tx_type or "").upper()
            if t == "BUY":
                lots.append({
                    "buy_transaction_id": tx_id,
                    "remaining_qty": int(qty or 0),
                    "buy_price_per_share": float(price or 0.0),
                })
            elif t == "SELL":
                remaining_to_match = int(qty or 0)
                for lot in lots:
                    if remaining_to_match <= 0:
                        break
                    available = lot["remaining_qty"]
                    if available <= 0:
                        continue
                    matched = min(available, remaining_to_match)
                    lot["remaining_qty"] -= matched
                    remaining_to_match -= matched

        available_qty = sum(max(0, lot["remaining_qty"]) for lot in lots)
        if sell_quantity > available_qty:
            raise ValueError(
                f"Sell quantity {sell_quantity} exceeds available holdings {available_qty}"
            )

        lot_matches: List[Dict] = []
        to_sell = sell_quantity
        realized_pnl = 0.0
        realized_cost_basis = 0.0
        for lot in lots:
            if to_sell <= 0:
                break
            available = lot["remaining_qty"]
            if available <= 0:
                continue
            matched = min(available, to_sell)
            buy_price = float(lot["buy_price_per_share"])
            pnl = (sell_price - buy_price) * matched
            cost = buy_price * matched
            realized_pnl += pnl
            realized_cost_basis += cost
            lot_matches.append({
                "buy_transaction_id": lot["buy_transaction_id"],
                "matched_quantity": matched,
                "buy_price_per_share": buy_price,
                "sell_price_per_share": sell_price,
                "realized_pnl": pnl,
            })
            to_sell -= matched

        if to_sell != 0:
            raise ValueError("Sell matching failed due to insufficient FIFO lots")

        return realized_pnl, realized_cost_basis, lot_matches
    
    def get_stock_transactions(self, stock_id: int) -> List[Dict]:
        """Get all transactions for a stock"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT transaction_id, transaction_type, quantity, price_per_share,
                   transaction_date, investment_horizon, target_price, thesis,
                   setup_type, confidence_score, risk_tags, mistake_tags, reflection_note,
                   realized_pnl, realized_cost_basis, realized_match_method, sell_note
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
                'thesis': row[7],
                'setup_type': row[8],
                'confidence_score': row[9],
                'risk_tags': row[10],
                'mistake_tags': row[11],
                'reflection_note': row[12],
                'realized_pnl': row[13],
                'realized_cost_basis': row[14],
                'realized_match_method': row[15],
                'sell_note': row[16],
            })
        
        self._close_connection(conn)
        return transactions

    def get_user_journal_notes(self, user_id: int) -> List[Dict]:
        """Get latest non-empty thesis note per stock for a user."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.stock_id, s.symbol, s.company_name,
                   t.transaction_id, t.transaction_date, t.thesis,
                   t.setup_type, t.confidence_score, t.risk_tags, t.mistake_tags, t.reflection_note
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
                "setup_type": row[6],
                "confidence_score": row[7],
                "risk_tags": row[8],
                "mistake_tags": row[9],
                "reflection_note": row[10],
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

    @staticmethod
    def get_indian_financial_year_bounds(ref_date: Optional[date] = None) -> Tuple[date, date, str]:
        """Return India FY start/end dates and label for a reference date."""
        d = ref_date or date.today()
        fy_start_year = d.year if d.month >= 4 else d.year - 1
        start = date(fy_start_year, 4, 1)
        end = date(fy_start_year + 1, 3, 31)
        label = f"FY{str(fy_start_year)[-2:]}-{str(fy_start_year + 1)[-2:]}"
        return start, end, label

    def get_realized_pnl_summary(
        self,
        user_id: int,
        fy_start: Optional[date] = None,
        fy_end: Optional[date] = None,
    ) -> Dict:
        """Get realized P/L rollup for a user in the selected Indian FY window."""
        if fy_start is None or fy_end is None:
            fy_start, fy_end, fy_label = self.get_indian_financial_year_bounds()
        else:
            fy_label = f"FY{str(fy_start.year)[-2:]}-{str(fy_end.year)[-2:]}"

        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                COALESCE(SUM(t.realized_pnl), 0),
                COUNT(*)
            FROM transactions t
            JOIN stocks s ON s.stock_id = t.stock_id
            WHERE s.user_id = ?
              AND UPPER(t.transaction_type) = 'SELL'
              AND t.transaction_date >= ?
              AND t.transaction_date <= ?
            """,
            (user_id, fy_start.isoformat(), fy_end.isoformat()),
        )
        total_row = cursor.fetchone() or (0.0, 0)
        total_realized = float(total_row[0] or 0.0)
        sell_count = int(total_row[1] or 0)

        cursor.execute(
            """
            SELECT
                s.stock_id,
                s.symbol,
                s.company_name,
                COALESCE(SUM(t.realized_pnl), 0) AS realized_pnl,
                COUNT(*) AS sell_count
            FROM transactions t
            JOIN stocks s ON s.stock_id = t.stock_id
            WHERE s.user_id = ?
              AND UPPER(t.transaction_type) = 'SELL'
              AND t.transaction_date >= ?
              AND t.transaction_date <= ?
            GROUP BY s.stock_id, s.symbol, s.company_name
            ORDER BY realized_pnl DESC, s.symbol ASC
            """,
            (user_id, fy_start.isoformat(), fy_end.isoformat()),
        )
        per_stock = [
            {
                "stock_id": row[0],
                "symbol": row[1],
                "company_name": row[2],
                "realized_pnl": float(row[3] or 0.0),
                "sell_count": int(row[4] or 0),
            }
            for row in cursor.fetchall()
        ]
        self._close_connection(conn)

        return {
            "fy_label": fy_label,
            "fy_start": fy_start.isoformat(),
            "fy_end": fy_end.isoformat(),
            "total_realized_pnl": total_realized,
            "sell_transaction_count": sell_count,
            "per_stock": per_stock,
        }
    
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
        cursor.execute("BEGIN IMMEDIATE")

        user_id = self._get_user_id_for_transaction(conn, int(transaction_id))
        if user_id is None:
            conn.rollback()
            self._close_connection(conn)
            return False
        
        # Build UPDATE query dynamically based on provided fields
        valid_fields = [
            'transaction_type', 'quantity', 'price_per_share', 'transaction_date',
            'investment_horizon', 'target_price', 'thesis',
            'setup_type', 'confidence_score', 'risk_tags', 'mistake_tags', 'reflection_note'
        ]
        
        update_fields = []
        values = []
        for field, value in updates.items():
            if field in valid_fields:
                update_fields.append(f"{field} = ?")
                values.append(value)
        
        if not update_fields:
            conn.rollback()
            self._close_connection(conn)
            return False
        
        query = f"UPDATE transactions SET {', '.join(update_fields)} WHERE transaction_id = ?"
        values.append(transaction_id)
        
        cursor.execute(query, values)

        # Keep ledger in sync for every transaction mutation.
        self._reconcile_user_cash_ledger_conn(conn, int(user_id))

        conn.commit()
        self._close_connection(conn)
        
        return True

    def delete_transaction(self, transaction_id: int) -> bool:
        '''Delete a transaction'''
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")

        user_id = self._get_user_id_for_transaction(conn, int(transaction_id))
        if user_id is None:
            conn.rollback()
            self._close_connection(conn)
            return False

        cursor.execute(
            "DELETE FROM transaction_lot_matches WHERE sell_transaction_id = ? OR buy_transaction_id = ?",
            (int(transaction_id), int(transaction_id)),
        )
        
        cursor.execute("DELETE FROM transactions WHERE transaction_id = ?", 
                    (transaction_id,))

        self._reconcile_user_cash_ledger_conn(conn, int(user_id))
        
        conn.commit()
        self._close_connection(conn)
        
        return True

    def delete_stock(self, stock_id: int) -> bool:
        """Delete a stock and all related records."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")

        user_id = self._get_user_id_for_stock(conn, int(stock_id))
        if user_id is None:
            conn.rollback()
            self._close_connection(conn)
            return False

        cursor.execute(
            """
            DELETE FROM transaction_lot_matches
            WHERE sell_transaction_id IN (SELECT transaction_id FROM transactions WHERE stock_id = ?)
               OR buy_transaction_id IN (SELECT transaction_id FROM transactions WHERE stock_id = ?)
            """,
            (int(stock_id), int(stock_id)),
        )

        cursor.execute("DELETE FROM ai_summaries WHERE alert_id IN (SELECT alert_id FROM alerts WHERE stock_id = ?)", (stock_id,))
        cursor.execute("DELETE FROM alerts WHERE stock_id = ?", (stock_id,))
        cursor.execute("DELETE FROM transactions WHERE stock_id = ?", (stock_id,))
        cursor.execute("DELETE FROM price_history WHERE stock_id = ?", (stock_id,))
        cursor.execute("DELETE FROM stocks WHERE stock_id = ?", (stock_id,))

        self._reconcile_user_cash_ledger_conn(conn, int(user_id))

        conn.commit()
        self._close_connection(conn)
        return True

    # Cash ledger operations
    @staticmethod
    def _capital_setting_key(user_id: int) -> str:
        """Return app-setting key used for user editable deposit capital."""
        return f"user:{int(user_id)}:capital_deposit"

    def _get_or_init_capital_deposit_for_user_conn(self, conn, user_id: int) -> float:
        """
        Read user deposit capital from app_settings, initializing default on first use.

        This must stay aligned with UI sidebar semantics:
        Deposit = editable user capital baseline.
        """
        key = self._capital_setting_key(int(user_id))
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM app_settings WHERE key = ? LIMIT 1", (key,))
        row = cursor.fetchone()
        if row and row[0] is not None:
            try:
                return float(row[0])
            except Exception:
                pass

        default_deposit = float(config.LEDGER_INITIAL_CREDIT or 0.0)
        cursor.execute(
            """
            INSERT INTO app_settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
            """,
            (key, f"{default_deposit:.2f}"),
        )
        return default_deposit

    def _deployed_capital_for_user_conn(self, conn, user_id: int) -> float:
        """
        Compute deployed capital from current open holdings.

        Mirrors UI logic based on portfolio summary:
        deployed = SUM(current_quantity * avg_buy_price)
        """
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COALESCE(SUM(h.total_quantity * h.avg_price), 0)
            FROM (
                SELECT
                    SUM(CASE WHEN t.transaction_type = 'BUY' THEN t.quantity ELSE -t.quantity END) AS total_quantity,
                    SUM(CASE WHEN t.transaction_type = 'BUY' THEN t.quantity * t.price_per_share ELSE 0 END) /
                        NULLIF(SUM(CASE WHEN t.transaction_type = 'BUY' THEN t.quantity ELSE 0 END), 0) AS avg_price
                FROM stocks s
                LEFT JOIN transactions t ON s.stock_id = t.stock_id
                WHERE s.user_id = ?
                GROUP BY s.stock_id
                HAVING total_quantity > 0
            ) h
            """,
            (int(user_id),),
        )
        row = cursor.fetchone()
        return float((row[0] if row else 0.0) or 0.0)

    def _capital_available_for_user_conn(self, conn, user_id: int) -> float:
        """
        Return available capital aligned with UI sidebar model.

        available = user_deposit - deployed_open_holdings
        """
        deposit = self._get_or_init_capital_deposit_for_user_conn(conn, int(user_id))
        deployed = self._deployed_capital_for_user_conn(conn, int(user_id))
        return float(deposit - deployed)

    def _sync_ledger_balance_for_buy_conn(self, conn, user_id: int, trade_amount: float, entry_date: Optional[str] = None) -> None:
        """
        Ensure ledger has enough balance for BUY_DEBIT after capital-model validation.

        This keeps cash_ledger non-negative and consistent when user-edited capital
        deposit is higher than historical ledger cash.
        """
        available = self._cash_balance_for_user(conn, int(user_id))
        needed = float(trade_amount or 0.0) - float(available or 0.0)
        if needed <= 1e-9:
            return
        self._add_cash_ledger_entry_conn(
            conn=conn,
            user_id=int(user_id),
            entry_type="DEPOSIT",
            amount=float(needed),
            entry_date=(entry_date or datetime.now().date().isoformat()),
            note="Auto-sync ledger to capital deposit model",
            enforce_balance=False,
        )

    @staticmethod
    def _cash_ledger_sign(entry_type: str) -> int:
        """Return +/- sign for cash ledger entry type."""
        et = (entry_type or "").strip().upper()
        if et in {"INIT_DEPOSIT", "DEPOSIT", "SELL_CREDIT"}:
            return 1
        if et in {"WITHDRAWAL", "BUY_DEBIT"}:
            return -1
        raise ValueError(f"Unsupported cash ledger entry_type: {entry_type}")

    def _get_user_id_for_stock(self, conn, stock_id: int) -> Optional[int]:
        """Resolve owner user_id for a stock."""
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM stocks WHERE stock_id = ? LIMIT 1", (stock_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return int(row[0])

    def _get_user_id_for_transaction(self, conn, transaction_id: int) -> Optional[int]:
        """Resolve owner user_id for a transaction."""
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT s.user_id
            FROM transactions t
            JOIN stocks s ON s.stock_id = t.stock_id
            WHERE t.transaction_id = ?
            LIMIT 1
            """,
            (int(transaction_id),),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return int(row[0])

    def _cash_balance_for_user(self, conn, user_id: int) -> float:
        """Compute available cash balance from ledger entries."""
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COALESCE(SUM(
                CASE
                    WHEN entry_type IN ('INIT_DEPOSIT', 'DEPOSIT', 'SELL_CREDIT') THEN amount
                    WHEN entry_type IN ('WITHDRAWAL', 'BUY_DEBIT') THEN -amount
                    ELSE 0
                END
            ), 0)
            FROM cash_ledger
            WHERE user_id = ?
            """,
            (user_id,),
        )
        row = cursor.fetchone()
        return float(row[0] or 0.0)

    def _rebuild_internal_ledger_entries_conn(self, conn, user_id: int) -> None:
        """
        Rebuild BUY_DEBIT/SELL_CREDIT entries from current transactions for one user.

        External cash entries (INIT_DEPOSIT/DEPOSIT/WITHDRAWAL) are preserved.
        """
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM cash_ledger WHERE user_id = ? AND entry_type IN ('BUY_DEBIT', 'SELL_CREDIT')",
            (int(user_id),),
        )
        cursor.execute(
            """
            SELECT t.transaction_id, t.transaction_type, t.quantity, t.price_per_share, t.transaction_date
            FROM transactions t
            JOIN stocks s ON s.stock_id = t.stock_id
            WHERE s.user_id = ?
            ORDER BY t.transaction_date ASC, t.transaction_id ASC
            """,
            (int(user_id),),
        )
        rows = cursor.fetchall()
        for tx_id, tx_type, qty, price, tx_date in rows:
            tx_upper = (tx_type or "").strip().upper()
            if tx_upper not in {"BUY", "SELL"}:
                continue
            amount = float((qty or 0) * (price or 0.0))
            if amount <= 0:
                continue
            self._add_cash_ledger_entry_conn(
                conn=conn,
                user_id=int(user_id),
                entry_type="BUY_DEBIT" if tx_upper == "BUY" else "SELL_CREDIT",
                amount=amount,
                entry_date=(tx_date or datetime.now().date().isoformat()),
                note="Rebuilt from transactions",
                reference_transaction_id=int(tx_id),
                enforce_balance=False,
            )

    def _reconcile_user_cash_ledger_conn(self, conn, user_id: int) -> None:
        """Reconcile a user's ledger to current transaction state."""
        self._bootstrap_cash_ledger_for_user(conn, int(user_id))
        self._rebuild_internal_ledger_entries_conn(conn, int(user_id))

    def reconcile_user_cash_ledger(self, user_id: int) -> None:
        """Public entry point to reconcile ledger for one user."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        try:
            self._reconcile_user_cash_ledger_conn(conn, int(user_id))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._close_connection(conn)

    def _add_cash_ledger_entry_conn(
        self,
        conn,
        user_id: int,
        entry_type: str,
        amount: float,
        entry_date: Optional[str] = None,
        note: Optional[str] = None,
        reference_transaction_id: Optional[int] = None,
        enforce_balance: bool = True,
    ) -> int:
        """Insert one ledger entry on an existing open DB connection."""
        entry_type = (entry_type or "").strip().upper()
        sign = self._cash_ledger_sign(entry_type)
        amount = float(amount or 0.0)
        if amount <= 0:
            raise ValueError("Ledger amount must be > 0")

        if sign < 0 and enforce_balance:
            available = self._cash_balance_for_user(conn, user_id)
            if available + 1e-9 < amount:
                shortfall = amount - available
                raise ValueError(
                    f"Insufficient available cash. "
                    f"Available: ₹{available:,.2f}, Required: ₹{amount:,.2f}, Shortfall: ₹{shortfall:,.2f}"
                )

        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO cash_ledger
            (user_id, entry_type, amount, entry_date, note, reference_transaction_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                int(user_id),
                entry_type,
                amount,
                (entry_date or datetime.now().date().isoformat()),
                note,
                reference_transaction_id,
            ),
        )
        return int(cursor.lastrowid)

    def _bootstrap_cash_ledger_for_user(self, conn, user_id: int) -> None:
        """
        Initialize ledger once for existing users by replaying historical transactions.

        This keeps legacy portfolios functional while enforcing ledger checks for new buys.
        """
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM cash_ledger WHERE user_id = ?", (user_id,))
        existing = int((cursor.fetchone() or [0])[0] or 0)
        if existing > 0:
            self._ensure_initial_credit_floor(conn, user_id)
            return

        cursor.execute(
            """
            SELECT t.transaction_id, t.transaction_type, t.quantity, t.price_per_share, t.transaction_date
            FROM transactions t
            INNER JOIN stocks s ON s.stock_id = t.stock_id
            WHERE s.user_id = ?
            ORDER BY t.transaction_date ASC, t.transaction_id ASC
            """,
            (user_id,),
        )
        tx_rows = cursor.fetchall()
        bootstrap_date = datetime.now().date().isoformat()
        if tx_rows and tx_rows[0][4]:
            bootstrap_date = tx_rows[0][4]

        initial_credit = float(config.LEDGER_INITIAL_CREDIT or 0.0)
        if initial_credit > 0:
            self._add_cash_ledger_entry_conn(
                conn=conn,
                user_id=user_id,
                entry_type="INIT_DEPOSIT",
                amount=initial_credit,
                entry_date=bootstrap_date,
                note="Bootstrap opening capital",
                enforce_balance=False,
            )

        for tx_id, tx_type, qty, price, tx_date in tx_rows:
            amount = float((qty or 0) * (price or 0.0))
            if amount <= 0:
                continue
            tx_upper = (tx_type or "").upper()
            if tx_upper == "BUY":
                entry_type = "BUY_DEBIT"
            elif tx_upper == "SELL":
                entry_type = "SELL_CREDIT"
            else:
                continue
            self._add_cash_ledger_entry_conn(
                conn=conn,
                user_id=user_id,
                entry_type=entry_type,
                amount=amount,
                entry_date=(tx_date or datetime.now().date().isoformat()),
                note="Bootstrap from historical transaction",
                reference_transaction_id=int(tx_id),
                enforce_balance=False,
            )
        self._ensure_initial_credit_floor(conn, user_id)

    def _ensure_initial_credit_floor(self, conn, user_id: int) -> None:
        """
        Ensure legacy bootstraps align to configured opening credit floor.

        Safety rule:
        - Apply only when there are no manual external entries (DEPOSIT/WITHDRAWAL).
        """
        desired = float(config.LEDGER_INITIAL_CREDIT or 0.0)
        if desired <= 0:
            return
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                COALESCE(SUM(CASE WHEN entry_type = 'INIT_DEPOSIT' THEN amount ELSE 0 END), 0) AS init_total,
                COALESCE(SUM(CASE WHEN entry_type IN ('DEPOSIT', 'WITHDRAWAL') THEN 1 ELSE 0 END), 0) AS external_entries
            FROM cash_ledger
            WHERE user_id = ?
            """,
            (int(user_id),),
        )
        row = cursor.fetchone() or [0, 0]
        init_total = float(row[0] or 0.0)
        external_entries = int(row[1] or 0)
        if external_entries > 0:
            return
        if init_total + 1e-9 >= desired:
            return
        delta = desired - init_total
        self._add_cash_ledger_entry_conn(
            conn=conn,
            user_id=int(user_id),
            entry_type="INIT_DEPOSIT",
            amount=delta,
            entry_date=datetime.now().date().isoformat(),
            note="One-time top-up to configured opening capital",
            enforce_balance=False,
        )

    def ensure_cash_ledger_bootstrap(self, user_id: int) -> None:
        """Ensure a user cash ledger is initialized once."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        try:
            self._bootstrap_cash_ledger_for_user(conn, int(user_id))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._close_connection(conn)

    def add_cash_ledger_entry(
        self,
        user_id: int,
        entry_type: str,
        amount: float,
        entry_date: Optional[str] = None,
        note: Optional[str] = None,
        reference_transaction_id: Optional[int] = None,
        enforce_balance: bool = True,
    ) -> int:
        """Add one cash ledger entry with optional balance enforcement."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        try:
            self._bootstrap_cash_ledger_for_user(conn, int(user_id))
            ledger_id = self._add_cash_ledger_entry_conn(
                conn=conn,
                user_id=int(user_id),
                entry_type=entry_type,
                amount=float(amount),
                entry_date=entry_date,
                note=note,
                reference_transaction_id=reference_transaction_id,
                enforce_balance=enforce_balance,
            )
            conn.commit()
            return ledger_id
        except Exception:
            conn.rollback()
            raise
        finally:
            self._close_connection(conn)

    def add_cash_deposit(self, user_id: int, amount: float, note: Optional[str] = None, entry_date: Optional[str] = None) -> int:
        """Add funds to user ledger."""
        return self.add_cash_ledger_entry(
            user_id=user_id,
            entry_type="DEPOSIT",
            amount=amount,
            entry_date=entry_date,
            note=note,
            enforce_balance=False,
        )

    def add_cash_withdrawal(self, user_id: int, amount: float, note: Optional[str] = None, entry_date: Optional[str] = None) -> int:
        """Withdraw funds from user ledger (fails when insufficient balance)."""
        return self.add_cash_ledger_entry(
            user_id=user_id,
            entry_type="WITHDRAWAL",
            amount=amount,
            entry_date=entry_date,
            note=note,
            enforce_balance=True,
        )

    def get_cash_ledger_summary(self, user_id: int) -> Dict:
        """Return available/consumed cash summary for a user."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        try:
            self._bootstrap_cash_ledger_for_user(conn, int(user_id))
            cursor.execute(
                """
                SELECT
                    COALESCE(SUM(CASE WHEN entry_type IN ('INIT_DEPOSIT', 'DEPOSIT') THEN amount ELSE 0 END), 0) AS total_funded,
                    COALESCE(SUM(CASE WHEN entry_type = 'WITHDRAWAL' THEN amount ELSE 0 END), 0) AS total_withdrawn,
                    COALESCE(SUM(CASE WHEN entry_type = 'BUY_DEBIT' THEN amount ELSE 0 END), 0) AS total_buy_debit,
                    COALESCE(SUM(CASE WHEN entry_type = 'SELL_CREDIT' THEN amount ELSE 0 END), 0) AS total_sell_credit
                FROM cash_ledger
                WHERE user_id = ?
                """,
                (int(user_id),),
            )
            row = cursor.fetchone() or [0, 0, 0, 0]
            total_funded = float(row[0] or 0.0)
            total_withdrawn = float(row[1] or 0.0)
            total_buy_debit = float(row[2] or 0.0)
            total_sell_credit = float(row[3] or 0.0)
            available = (total_funded + total_sell_credit) - (total_buy_debit + total_withdrawn)
            consumed = total_buy_debit
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._close_connection(conn)

        return {
            "user_id": int(user_id),
            "total_funded": total_funded,
            "total_withdrawn": total_withdrawn,
            "total_buy_debit": total_buy_debit,
            "total_sell_credit": total_sell_credit,
            "available_cash": available,
            "consumed_cash": consumed,
        }

    def get_user_capital_snapshot(self, user_id: int) -> Dict:
        """
        Return sidebar capital snapshot from source-of-truth model.

        Model:
        - deposit: user editable capital baseline (`app_settings`)
        - deployed: current open-holdings buy value
        - available: deposit - deployed
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        try:
            self._bootstrap_cash_ledger_for_user(conn, int(user_id))
            deposit = self._get_or_init_capital_deposit_for_user_conn(conn, int(user_id))
            deployed = self._deployed_capital_for_user_conn(conn, int(user_id))
            available = float(deposit - deployed)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._close_connection(conn)

        return {
            "user_id": int(user_id),
            "deposit": float(deposit),
            "deployed": float(deployed),
            "available": float(available),
        }

    def get_cash_balance_as_of(self, user_id: int, as_of_date: str) -> float:
        """Return ledger cash balance as of end of given date."""
        self.ensure_cash_ledger_bootstrap(int(user_id))
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COALESCE(SUM(
                CASE
                    WHEN entry_type IN ('INIT_DEPOSIT', 'DEPOSIT', 'SELL_CREDIT') THEN amount
                    WHEN entry_type IN ('WITHDRAWAL', 'BUY_DEBIT') THEN -amount
                    ELSE 0
                END
            ), 0)
            FROM cash_ledger
            WHERE user_id = ?
              AND entry_date <= ?
            """,
            (int(user_id), as_of_date),
        )
        row = cursor.fetchone()
        self._close_connection(conn)
        return float(row[0] or 0.0)

    def get_cash_ledger_entries(self, user_id: int, limit: int = 200) -> List[Dict]:
        """Get latest ledger entries for a user."""
        self.ensure_cash_ledger_bootstrap(int(user_id))
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT ledger_id, user_id, entry_type, amount, entry_date, note, reference_transaction_id, created_at
            FROM cash_ledger
            WHERE user_id = ?
            ORDER BY entry_date DESC, ledger_id DESC
            LIMIT ?
            """,
            (int(user_id), max(1, int(limit))),
        )
        rows = cursor.fetchall()
        self._close_connection(conn)
        return [
            {
                "ledger_id": int(row[0]),
                "user_id": int(row[1]),
                "entry_type": row[2],
                "amount": float(row[3] or 0.0),
                "entry_date": row[4],
                "note": row[5],
                "reference_transaction_id": row[6],
                "created_at": row[7],
            }
            for row in rows
        ]

    # Symbol master operations
    def upsert_symbol_master(
        self,
        symbol: str,
        company_name: str,
        exchange: str = 'NSE',
        bse_code: str = None,
        nse_code: str = None,
        sector: str = None,
        industry_group: str = None,
        industry: str = None,
        source: str = 'MANUAL',
        quote_symbol_yahoo: str = None
    ) -> int:
        """Insert or update a symbol master record and return symbol_id."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO symbol_master
            (symbol, company_name, exchange, bse_code, nse_code, sector, industry_group, industry, source, quote_symbol_yahoo, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(symbol) DO UPDATE SET
                company_name = excluded.company_name,
                exchange = excluded.exchange,
                bse_code = COALESCE(excluded.bse_code, symbol_master.bse_code),
                nse_code = COALESCE(excluded.nse_code, symbol_master.nse_code),
                sector = COALESCE(excluded.sector, excluded.industry_group, excluded.industry, symbol_master.sector),
                industry_group = COALESCE(excluded.industry_group, symbol_master.industry_group),
                industry = COALESCE(excluded.industry, symbol_master.industry),
                source = excluded.source,
                quote_symbol_yahoo = COALESCE(excluded.quote_symbol_yahoo, symbol_master.quote_symbol_yahoo),
                is_active = 1,
                last_updated = CURRENT_TIMESTAMP
        """, (
            symbol.upper().strip(),
            company_name.strip(),
            exchange.strip(),
            bse_code,
            nse_code,
            sector or industry_group or industry,
            industry_group,
            industry,
            source,
            quote_symbol_yahoo
        ))

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
            SELECT symbol_id, symbol, company_name, exchange, bse_code, nse_code, sector, industry_group, industry, quote_symbol_yahoo
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
                'industry_group': row[7],
                'industry': row[8],
                'quote_symbol_yahoo': row[9]
            }
            for row in rows
        ]

    def get_symbol_by_symbol(self, symbol: str) -> Optional[Dict]:
        """Get symbol master record by symbol."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT symbol_id, symbol, company_name, exchange, bse_code, nse_code, sector, industry_group, industry, quote_symbol_yahoo
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
            'industry_group': row[7],
            'industry': row[8],
            'quote_symbol_yahoo': row[9]
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

    def get_bse_announcements_since_id(self, last_announcement_id: int = 0, limit: int = 5000) -> List[Dict]:
        """Fetch announcements newer than a given announcement_id in ascending order."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT announcement_id, symbol_id, scrip_code, headline, category, announcement_date,
                   attachment_url, exchange_ref_id, rss_guid, raw_payload, processed, fetched_at
            FROM bse_announcements
            WHERE announcement_id > ?
            ORDER BY announcement_id ASC
            LIMIT ?
        """, (int(last_announcement_id or 0), limit))
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
            SELECT symbol_id, symbol, company_name, exchange, bse_code, nse_code, sector, industry_group, industry, quote_symbol_yahoo
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
            'industry_group': row[7],
            'industry': row[8],
            'quote_symbol_yahoo': row[9]
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
        industry: str = None,
        limit: int = 500
    ) -> List[Dict]:
        """Get filings for user's portfolio with optional filters."""
        conn = self.get_connection()
        cursor = conn.cursor()

        query = """
            SELECT f.filing_id, f.category, f.headline, f.announcement_summary, f.announcement_date,
                   f.pdf_link, f.source_exchange, f.source_ref, f.symbol_id,
                   f.category_override, f.override_locked, COALESCE(f.category_override, f.category) AS effective_category,
                   s.stock_id, s.symbol, s.company_name, s.exchange,
                   sm.bse_code, sm.nse_code, sm.industry, sm.industry_group, sm.sector
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
            query += " AND COALESCE(f.category_override, f.category) = ?"
            params.append(category)
        if industry and industry != "ALL":
            query += " AND COALESCE(sm.industry, sm.industry_group, sm.sector, 'Unknown') = ?"
            params.append(industry)

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
                'symbol_id': row[8],
                'category_override': row[9],
                'override_locked': bool(row[10]) if row[10] is not None else False,
                'effective_category': row[11],
                'stock_id': row[12],
                'symbol': row[13],
                'company_name': row[14],
                'exchange': row[15],
                'bse_code': row[16],
                'nse_code': row[17],
                'industry': row[18],
                'industry_group': row[19],
                'sector': row[20],
            }
            for row in rows
        ]

    def set_filing_category_override(self, filing_id: int, category_override: Optional[str], locked: bool = True) -> bool:
        """Set/clear filing category override."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE filings
            SET category_override = ?,
                override_locked = ?,
                override_updated_at = CURRENT_TIMESTAMP
            WHERE filing_id = ?
        """, (category_override, 1 if locked else 0, filing_id))
        conn.commit()
        changed = cursor.rowcount > 0
        self._close_connection(conn)
        return changed

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

    # Global insight snapshot operations (shared across users)
    def upsert_global_insight_snapshot(
        self,
        symbol_id: int,
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
        """Insert/update one shared quarter insight snapshot and return snapshot_id."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO global_insight_snapshots
            (symbol_id, quarter_label, insight_type, source_filing_id, source_ref, summary_text, sentiment,
             status, provider, model_version, generated_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(symbol_id, quarter_label, insight_type) DO UPDATE SET
                source_filing_id = COALESCE(excluded.source_filing_id, global_insight_snapshots.source_filing_id),
                source_ref = COALESCE(excluded.source_ref, global_insight_snapshots.source_ref),
                summary_text = COALESCE(excluded.summary_text, global_insight_snapshots.summary_text),
                sentiment = COALESCE(excluded.sentiment, global_insight_snapshots.sentiment),
                status = COALESCE(excluded.status, global_insight_snapshots.status),
                provider = COALESCE(excluded.provider, global_insight_snapshots.provider),
                model_version = COALESCE(excluded.model_version, global_insight_snapshots.model_version),
                updated_at = CURRENT_TIMESTAMP
        """, (
            symbol_id, quarter_label, insight_type, source_filing_id, source_ref, summary_text, sentiment,
            status, provider, model_version
        ))
        conn.commit()
        cursor.execute("""
            SELECT snapshot_id
            FROM global_insight_snapshots
            WHERE symbol_id = ? AND quarter_label = ? AND insight_type = ?
            LIMIT 1
        """, (symbol_id, quarter_label, insight_type))
        row = cursor.fetchone()
        self._close_connection(conn)
        return row[0]

    def get_global_insight_snapshot(self, symbol_id: int, quarter_label: str, insight_type: str) -> Optional[Dict]:
        """Get one global insight snapshot if exists."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT snapshot_id, symbol_id, quarter_label, insight_type, source_filing_id, source_ref,
                   summary_text, sentiment, status, provider, model_version, generated_at, updated_at
            FROM global_insight_snapshots
            WHERE symbol_id = ? AND quarter_label = ? AND insight_type = ?
            LIMIT 1
        """, (symbol_id, quarter_label, insight_type))
        row = cursor.fetchone()
        self._close_connection(conn)
        if not row:
            return None
        return {
            "snapshot_id": row[0],
            "symbol_id": row[1],
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

    def get_user_global_insight_snapshots(self, user_id: int, quarter_label: str = None, limit: int = 500) -> List[Dict]:
        """List shared insight snapshots for companies in user's portfolio."""
        conn = self.get_connection()
        cursor = conn.cursor()
        query = """
            SELECT gi.snapshot_id, gi.symbol_id, gi.quarter_label, gi.insight_type,
                   gi.source_filing_id, gi.source_ref, gi.summary_text, gi.sentiment,
                   gi.status, gi.provider, gi.model_version, gi.generated_at, gi.updated_at,
                   s.stock_id, s.symbol, s.company_name, s.exchange
            FROM stocks s
            LEFT JOIN symbol_master sm
                ON sm.symbol = s.symbol
               OR sm.symbol = REPLACE(REPLACE(UPPER(s.symbol), '.NS', ''), '.BO', '')
            JOIN global_insight_snapshots gi ON gi.symbol_id = sm.symbol_id
            WHERE s.user_id = ?
        """
        params = [user_id]
        if quarter_label:
            query += " AND gi.quarter_label = ?"
            params.append(quarter_label)
        query += " ORDER BY gi.quarter_label DESC, s.symbol ASC, gi.insight_type ASC LIMIT ?"
        params.append(limit)
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        self._close_connection(conn)
        return [
            {
                "snapshot_id": row[0],
                "symbol_id": row[1],
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
                "stock_id": row[13],
                "symbol": row[14],
                "company_name": row[15],
                "exchange": row[16],
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

    # AI cache operations
    def get_ai_response_cache(self, task_type: str, provider: str, model: str, prompt_hash: str) -> Optional[Dict]:
        """Get cached AI response by task/provider/model/prompt hash."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT cache_id, response_text, sentiment, created_at, updated_at
            FROM ai_response_cache
            WHERE task_type = ? AND provider = ? AND model = ? AND prompt_hash = ?
            LIMIT 1
        """, (task_type, provider, model, prompt_hash))
        row = cursor.fetchone()
        self._close_connection(conn)
        if not row:
            return None
        return {
            "cache_id": row[0],
            "response_text": row[1],
            "sentiment": row[2],
            "created_at": row[3],
            "updated_at": row[4],
        }

    def upsert_ai_response_cache(
        self,
        task_type: str,
        provider: str,
        model: str,
        prompt_hash: str,
        response_text: str,
        sentiment: str = None,
    ) -> int:
        """Insert/update cached AI response and return cache_id."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ai_response_cache
            (task_type, provider, model, prompt_hash, response_text, sentiment, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(task_type, provider, model, prompt_hash) DO UPDATE SET
                response_text = excluded.response_text,
                sentiment = COALESCE(excluded.sentiment, ai_response_cache.sentiment),
                updated_at = CURRENT_TIMESTAMP
        """, (task_type, provider, model, prompt_hash, response_text, sentiment))
        conn.commit()
        cursor.execute("""
            SELECT cache_id
            FROM ai_response_cache
            WHERE task_type = ? AND provider = ? AND model = ? AND prompt_hash = ?
            LIMIT 1
        """, (task_type, provider, model, prompt_hash))
        row = cursor.fetchone()
        self._close_connection(conn)
        return row[0]

    def get_transaction_by_id(self, transaction_id: int) -> Optional[Dict]:
        '''Get a single transaction by ID'''
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT transaction_id, stock_id, transaction_type, quantity, 
                price_per_share, transaction_date, investment_horizon,
                target_price, thesis, setup_type, confidence_score,
                risk_tags, mistake_tags, reflection_note,
                realized_pnl, realized_cost_basis, realized_match_method, sell_note
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
                'thesis': row[8],
                'setup_type': row[9],
                'confidence_score': row[10],
                'risk_tags': row[11],
                'mistake_tags': row[12],
                'reflection_note': row[13],
                'realized_pnl': row[14],
                'realized_cost_basis': row[15],
                'realized_match_method': row[16],
                'sell_note': row[17],
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

    # Background jobs
    def enqueue_background_job(self, job_type: str, requested_by: Optional[int], payload: Optional[Dict] = None) -> int:
        """Queue a background job and return job_id."""
        conn = self.get_connection()
        cursor = conn.cursor()
        payload_json = json.dumps(payload or {})
        cursor.execute("""
            INSERT INTO background_jobs
            (job_type, requested_by, status, payload_json, progress, created_at, updated_at)
            VALUES (?, ?, 'QUEUED', ?, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, (job_type, requested_by, payload_json))
        job_id = cursor.lastrowid
        conn.commit()
        self._close_connection(conn)
        return job_id

    def claim_next_background_job(self) -> Optional[Dict]:
        """Atomically claim next queued background job."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute("""
            SELECT job_id
            FROM background_jobs
            WHERE status = 'QUEUED'
            ORDER BY created_at ASC, job_id ASC
            LIMIT 1
        """)
        row = cursor.fetchone()
        if not row:
            conn.commit()
            self._close_connection(conn)
            return None
        job_id = row[0]
        cursor.execute("""
            UPDATE background_jobs
            SET status = 'RUNNING',
                started_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE job_id = ?
        """, (job_id,))
        cursor.execute("""
            SELECT job_id, job_type, requested_by, status, payload_json, progress,
                   result_json, error_message, created_at, started_at, completed_at, updated_at
            FROM background_jobs
            WHERE job_id = ?
        """, (job_id,))
        job_row = cursor.fetchone()
        conn.commit()
        self._close_connection(conn)
        if not job_row:
            return None
        payload = {}
        if job_row[4]:
            try:
                payload = json.loads(job_row[4])
            except Exception:
                payload = {}
        return {
            "job_id": job_row[0],
            "job_type": job_row[1],
            "requested_by": job_row[2],
            "status": job_row[3],
            "payload": payload,
            "progress": job_row[5],
            "result_json": job_row[6],
            "error_message": job_row[7],
            "created_at": job_row[8],
            "started_at": job_row[9],
            "completed_at": job_row[10],
            "updated_at": job_row[11],
        }

    def complete_background_job(
        self,
        job_id: int,
        status: str,
        progress: int = 100,
        result: Optional[Dict] = None,
        error_message: Optional[str] = None
    ) -> None:
        """Complete a running job with SUCCESS or FAILED."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE background_jobs
            SET status = ?,
                progress = ?,
                result_json = ?,
                error_message = ?,
                completed_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE job_id = ?
        """, (
            status,
            max(0, min(int(progress), 100)),
            json.dumps(result or {}) if result is not None else None,
            error_message,
            job_id
        ))
        conn.commit()
        self._close_connection(conn)

    # Notifications
    def add_notification(
        self,
        user_id: Optional[int],
        notif_type: str,
        title: str,
        message: str,
        metadata: Optional[Dict] = None,
        dedupe_key: Optional[str] = None,
    ) -> int:
        """Create a user/global notification."""
        conn = self.get_connection()
        cursor = conn.cursor()
        user_scope = str(int(user_id)) if user_id is not None else "GLOBAL"

        # De-duplication guard: if key already seen for this user/notif_type, reuse notification_id.
        dedupe_key = (dedupe_key or "").strip() or None
        if dedupe_key:
            cursor.execute(
                """
                SELECT notification_id
                FROM notification_dedupe_keys
                WHERE user_scope = ? AND notif_type = ? AND dedupe_key = ?
                LIMIT 1
                """,
                (user_scope, notif_type, dedupe_key),
            )
            row = cursor.fetchone()
            if row and row[0]:
                self._close_connection(conn)
                return int(row[0])

        cursor.execute("""
            INSERT INTO notifications
            (user_id, notif_type, title, message, metadata_json, is_read, created_at)
            VALUES (?, ?, ?, ?, ?, 0, CURRENT_TIMESTAMP)
        """, (
            user_id,
            notif_type,
            title,
            message,
            json.dumps(metadata or {}) if metadata is not None else None,
        ))
        notif_id = cursor.lastrowid
        if dedupe_key:
            cursor.execute(
                """
                INSERT OR IGNORE INTO notification_dedupe_keys
                (user_scope, user_id, notif_type, dedupe_key, notification_id, created_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (user_scope, user_id, notif_type, dedupe_key, notif_id),
            )
        conn.commit()
        self._close_connection(conn)
        return notif_id

    def has_notification_dedupe(self, user_id: Optional[int], notif_type: str, dedupe_key: str) -> bool:
        """Return True if a dedupe-key has already been used for notification creation."""
        key = (dedupe_key or "").strip()
        if not key:
            return False
        scope = str(int(user_id)) if user_id is not None else "GLOBAL"
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 1
            FROM notification_dedupe_keys
            WHERE user_scope = ? AND notif_type = ? AND dedupe_key = ?
            LIMIT 1
            """,
            (scope, notif_type, key),
        )
        row = cursor.fetchone()
        self._close_connection(conn)
        return bool(row)

    def get_user_notifications(self, user_id: int, unread_only: bool = False, limit: int = 100) -> List[Dict]:
        """List notifications for user (including global notifications)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        query = """
            SELECT notification_id, user_id, notif_type, title, message, metadata_json, is_read, created_at, read_at
            FROM notifications
            WHERE (user_id = ? OR user_id IS NULL)
        """
        params = [user_id]
        if unread_only:
            query += " AND is_read = 0"
        query += " ORDER BY created_at DESC, notification_id DESC LIMIT ?"
        params.append(limit)
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        self._close_connection(conn)
        out = []
        for row in rows:
            metadata = {}
            if row[5]:
                try:
                    metadata = json.loads(row[5])
                except Exception:
                    metadata = {}
            out.append({
                "notification_id": row[0],
                "user_id": row[1],
                "notif_type": row[2],
                "title": row[3],
                "message": row[4],
                "metadata": metadata,
                "is_read": bool(row[6]),
                "created_at": row[7],
                "read_at": row[8],
            })
        return out

    def get_unread_notifications_count(self, user_id: int) -> int:
        """Count unread notifications for user (including global)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*)
            FROM notifications
            WHERE (user_id = ? OR user_id IS NULL) AND is_read = 0
        """, (user_id,))
        row = cursor.fetchone()
        self._close_connection(conn)
        return int(row[0] if row else 0)

    def mark_notification_read(self, notification_id: int) -> None:
        """Mark one notification as read."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE notifications
            SET is_read = 1, read_at = CURRENT_TIMESTAMP
            WHERE notification_id = ?
        """, (notification_id,))
        conn.commit()
        self._close_connection(conn)

    def mark_all_notifications_read(self, user_id: int) -> None:
        """Mark all user/global notifications as read for a user."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE notifications
            SET is_read = 1, read_at = CURRENT_TIMESTAMP
            WHERE (user_id = ? OR user_id IS NULL) AND is_read = 0
        """, (user_id,))
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

    def get_portfolio_value_as_of(self, user_id: int, as_of_date: str) -> float:
        """
        Compute portfolio market value as-of a date.

        Logic:
        - Quantity per stock: net BUY/SELL transactions with transaction_date <= as_of_date
        - Price per stock: latest BSE close_price with trade_date <= as_of_date
        - Fallback price (if no BSE row): cached latest price, then avg_price
        """
        if not as_of_date:
            return 0.0

        stocks = self.get_user_stocks_with_symbol_master(user_id)
        if not stocks:
            return 0.0

        conn = self.get_connection()
        cursor = conn.cursor()
        total_value = 0.0

        for stock in stocks:
            stock_id = int(stock["stock_id"])
            bse_code = (stock.get("bse_code") or "").strip()
            avg_price = float(stock.get("avg_price") or 0.0)

            cursor.execute(
                """
                SELECT COALESCE(SUM(
                    CASE
                        WHEN UPPER(transaction_type) = 'BUY' THEN quantity
                        WHEN UPPER(transaction_type) = 'SELL' THEN -quantity
                        ELSE 0
                    END
                ), 0)
                FROM transactions
                WHERE stock_id = ?
                  AND transaction_date <= ?
                """,
                (stock_id, as_of_date),
            )
            qty_row = cursor.fetchone()
            quantity = float((qty_row[0] if qty_row else 0.0) or 0.0)
            if quantity <= 0:
                continue

            price = None
            if bse_code:
                cursor.execute(
                    """
                    SELECT close_price
                    FROM bse_daily_prices
                    WHERE bse_code = ?
                      AND trade_date <= ?
                    ORDER BY trade_date DESC
                    LIMIT 1
                    """,
                    (bse_code, as_of_date),
                )
                p_row = cursor.fetchone()
                if p_row and p_row[0] is not None:
                    price = float(p_row[0])

            if price is None:
                cached = self.get_latest_price(stock_id)
                if cached is not None:
                    price = float(cached)
                else:
                    price = avg_price

            total_value += quantity * float(price or 0.0)

        self._close_connection(conn)
        return float(total_value)

    def get_portfolio_external_cash_flow(
        self,
        user_id: int,
        start_date: str,
        end_date: str
    ) -> float:
        """
        Sum net external cash-flow for a user between two dates (inclusive).

        Convention:
        - DEPOSIT   => positive
        - WITHDRAWAL => negative

        Internal portfolio events (BUY_DEBIT / SELL_CREDIT) are excluded.
        """
        if not start_date or not end_date:
            return 0.0

        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COALESCE(SUM(
                CASE
                    WHEN entry_type = 'DEPOSIT' THEN amount
                    WHEN entry_type = 'WITHDRAWAL' THEN -amount
                    ELSE 0
                END
            ), 0)
            FROM cash_ledger
            WHERE user_id = ?
              AND entry_date >= ?
              AND entry_date <= ?
            """,
            (user_id, start_date, end_date),
        )
        row = cursor.fetchone()
        self._close_connection(conn)
        return float(row[0] or 0.0)

    def get_portfolio_net_transaction_cash_flow(
        self,
        user_id: int,
        start_date: str,
        end_date: str
    ) -> float:
        """
        Sum net transaction contribution between two dates (inclusive).

        Convention:
        - BUY  => positive contribution (capital moved into holdings)
        - SELL => negative contribution (capital moved out of holdings)

        Formula equivalent:
            sum(BUY quantity * price_per_share) - sum(SELL quantity * price_per_share)
        """
        if not start_date or not end_date:
            return 0.0

        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COALESCE(SUM(
                CASE
                    WHEN UPPER(t.transaction_type) = 'BUY' THEN (t.quantity * t.price_per_share)
                    WHEN UPPER(t.transaction_type) = 'SELL' THEN -(t.quantity * t.price_per_share)
                    ELSE 0
                END
            ), 0)
            FROM transactions t
            JOIN stocks s ON t.stock_id = s.stock_id
            WHERE s.user_id = ?
              AND t.transaction_date > ?
              AND t.transaction_date <= ?
            """,
            (user_id, start_date, end_date),
        )
        row = cursor.fetchone()
        self._close_connection(conn)
        return float(row[0] or 0.0)
