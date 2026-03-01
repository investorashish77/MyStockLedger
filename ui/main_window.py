"""
Main Window
The main application window with portfolio, alerts, and settings
"""

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QStackedWidget, QLabel, QPushButton, QMessageBox,
                             QStatusBar, QMenuBar, QMenu, QAction, QDialog, QFrame, QGraphicsDropShadowEffect,
                             QListWidget, QListWidgetItem, QAbstractItemView, QToolButton, QInputDialog)
from PyQt5.QtCore import Qt, QTimer, QUrl, pyqtSignal
from PyQt5.QtGui import QPixmap, QIcon, QColor, QDesktopServices
from pathlib import Path
from time import perf_counter
from datetime import datetime, timedelta
import threading
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from database.db_manager import DatabaseManager
from services.stock_service import StockService
from services.alert_service import AlertService
from services.ai_summary_service import AISummaryService
from services.background_job_service import BackgroundJobService
from ui.login_dialog import LoginDialog
from ui.dashboard_view import DashboardView
from ui.journal_view import JournalView
from ui.alerts_view import AlertsView
from ui.insights_view import InsightsView
from utils.config import config
from utils.logger import get_logger

class MainWindow(QMainWindow):
    """Main application window"""
    quote_refresh_finished = pyqtSignal(int, int, str, float, str)
    
    def __init__(self):
        """Init.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        super().__init__()
        self.logger = get_logger(__name__)
        init_t0 = perf_counter()
        
        # Initialize services
        t0 = perf_counter()
        self.db = DatabaseManager()
        self.stock_service = StockService()
        self.alert_service = AlertService(self.db)
        self.ai_service = AISummaryService(self.db)
        self.background_jobs = BackgroundJobService(self.db, self.ai_service)
        self.background_jobs.start()
        self.logger.info("MainWindow services initialized in %.2fs", perf_counter() - t0)
        
        # User data
        self.current_user = None
        self.current_theme = "dark"
        self._is_refreshing = False
        self._quote_refresh_in_progress = False
        self.quote_refresh_finished.connect(self._on_quote_refresh_finished)
        
        # Setup UI
        t0 = perf_counter()
        self.setup_ui()
        self.logger.info("MainWindow UI setup completed in %.2fs", perf_counter() - t0)
        
        # Show login dialog
        t0 = perf_counter()
        self.show_login()
        self.logger.info("Login flow completed in %.2fs", perf_counter() - t0)
        
        # Setup auto-refresh timer (every 5 minutes)
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.auto_refresh)
        self.refresh_timer.start(300000)  # 5 minutes
        self.logger.info("MainWindow initialized in %.2fs", perf_counter() - init_t0)
    
    def setup_ui(self):
        """Setup the main UI"""
        self.setWindowTitle(config.APP_NAME)
        self.setGeometry(100, 100, 1200, 800)
        
        # Create menu bar
        self.create_menu_bar()
        
        # Central widget
        central_widget = QWidget()
        central_widget.setObjectName("appRoot")
        self.setCentralWidget(central_widget)

        # App shell layout: fixed sidebar + right working surface.
        root_layout = QHBoxLayout()
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(12)
        central_widget.setLayout(root_layout)

        self.sidebar = self.create_sidebar()
        root_layout.addWidget(self.sidebar, 0)

        self.main_surface = QWidget()
        self.main_surface.setObjectName("mainSurface")
        root_layout.addWidget(self.main_surface, 1)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(2, 2, 2, 2)
        main_layout.setSpacing(12)
        self.main_surface.setLayout(main_layout)

        # Top utility bar
        self.top_bar = self.create_header()
        main_layout.addWidget(self.top_bar)
        self._set_header_meta()

        # KPI strip
        self.kpi_strip = QFrame()
        self.kpi_strip.setObjectName("kpiStrip")
        kpi_row = QHBoxLayout(self.kpi_strip)
        kpi_row.setContentsMargins(10, 8, 10, 8)
        kpi_row.setSpacing(10)
        self.global_daily_kpi = self._build_kpi_card("Daily Gain/Loss")
        self.global_weekly_kpi = self._build_kpi_card("Weekly Gain/Loss")
        self.global_total_kpi = self._build_kpi_card("Total Returns")
        self.global_realized_kpi = self._build_kpi_card("Realized P/L (Current FY)")
        kpi_row.addWidget(self.global_daily_kpi)
        kpi_row.addWidget(self.global_weekly_kpi)
        kpi_row.addWidget(self.global_total_kpi)
        kpi_row.addWidget(self.global_realized_kpi)
        main_layout.addWidget(self.kpi_strip)

        self.content_stack = QStackedWidget()
        self.content_stack.setObjectName("contentStack")
        main_layout.addWidget(self.content_stack, 1)

        # Create views
        self.dashboard_view = DashboardView(self.db, self.stock_service, self.ai_service, show_kpis=False)
        self.journal_view = JournalView(self.db, self.ai_service)
        self.alerts_view = AlertsView(self.db, self.alert_service, self.ai_service, self.background_jobs)
        self.insights_view = InsightsView(self.db, self.alert_service, self.ai_service, self.background_jobs)
        self.settings_view = self._build_placeholder_view(
            title="Settings",
            body="Profile settings and password change will be configured here."
        )
        self.help_view = self._build_placeholder_view(
            title="Help",
            body="Help map and onboarding resources will appear here."
        )

        self.content_stack.addWidget(self.dashboard_view)
        self.content_stack.addWidget(self.journal_view)
        self.content_stack.addWidget(self.alerts_view)
        self.content_stack.addWidget(self.insights_view)
        self.content_stack.addWidget(self.settings_view)
        self.content_stack.addWidget(self.help_view)
        self.show_view("dashboard")
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
        self.apply_theme()
        self._apply_depth_effects()

    @staticmethod
    def _build_kpi_card(title: str) -> QFrame:
        """Build kpi card.

        Args:
            title: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        card = QFrame()
        card.setObjectName("kpiCard")
        layout = QVBoxLayout()
        title_lbl = QLabel(title)
        title_lbl.setObjectName("kpiTitle")
        value_lbl = QLabel("₹0.00")
        value_lbl.setObjectName("kpiValue")
        layout.addWidget(title_lbl)
        layout.addWidget(value_lbl)
        card.setLayout(layout)
        card._value = value_lbl
        return card

    @staticmethod
    def _build_placeholder_view(title: str, body: str) -> QWidget:
        """Build a lightweight placeholder section for upcoming pages."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(8)
        title_lbl = QLabel(title)
        title_lbl.setObjectName("sectionTitle")
        body_lbl = QLabel(body)
        body_lbl.setObjectName("placeholderText")
        body_lbl.setWordWrap(True)
        layout.addWidget(title_lbl)
        layout.addWidget(body_lbl)
        layout.addStretch()
        return page

    def _quote_setting_key(self, user_id: int) -> str:
        """App-settings key for persisted quote update timestamp."""
        return f"user:{int(user_id)}:quotes_last_updated"

    @staticmethod
    def _parse_dt(value: str):
        """Parse datetime from stored value."""
        raw = (value or "").strip()
        if not raw:
            return None
        for parser in (datetime.fromisoformat, lambda x: datetime.strptime(x, "%Y-%m-%d %H:%M:%S")):
            try:
                return parser(raw)
            except Exception:
                continue
        return None

    def _set_header_meta(self, dt: datetime = None):
        """Render FY and last-updated text in top utility bar."""
        current = datetime.now()
        try:
            fy_start, _fy_end, _fy_label = self.db.get_indian_financial_year_bounds(current.date())
            fy_text = f"FY {fy_start.year}-{str(fy_start.year + 1)[-2:]}"
        except Exception:
            fy_text = "FY -"
        if dt is None and self.current_user:
            stored = self.db.get_setting(self._quote_setting_key(self.current_user["user_id"]))
            dt = self._parse_dt(stored)
        stamp = dt.strftime("%d %b %Y, %I:%M %p") if dt else "-"
        self.header_meta_label.setText(f"{fy_text} · Last updated: {stamp}")

    def create_sidebar(self):
        """Create always-visible sidebar navigation."""
        panel = QFrame()
        panel.setObjectName("sidebarShell")
        panel.setMinimumWidth(210)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        brand = QFrame()
        brand.setObjectName("sidebarBrand")
        brand_layout = QHBoxLayout(brand)
        brand_layout.setContentsMargins(10, 10, 10, 10)
        brand_layout.setSpacing(10)
        self.sidebar_logo = QLabel()
        self.sidebar_logo.setObjectName("brandLogo")
        self.sidebar_logo.setAlignment(Qt.AlignCenter)
        self.sidebar_logo.setFixedSize(30, 30)
        brand_layout.addWidget(self.sidebar_logo)
        brand_text = QVBoxLayout()
        brand_text.setSpacing(0)
        self.brand_title = QLabel("EquityJournal")
        self.brand_title.setObjectName("brandTitle")
        self.brand_subtitle = QLabel("PORTFOLIO DESK")
        self.brand_subtitle.setObjectName("brandSubtitle")
        brand_text.addWidget(self.brand_title)
        brand_text.addWidget(self.brand_subtitle)
        brand_layout.addLayout(brand_text)
        layout.addWidget(brand)

        account = QFrame()
        account.setObjectName("accountCard")
        account_layout = QVBoxLayout(account)
        account_layout.setContentsMargins(10, 10, 10, 10)
        account_layout.setSpacing(4)
        tag = QLabel("ACCOUNT")
        tag.setObjectName("accountTag")
        self.sidebar_user_name = QLabel("Guest")
        self.sidebar_user_name.setObjectName("accountName")
        self.sidebar_user_meta = QLabel("Local mode")
        self.sidebar_user_meta.setObjectName("accountMeta")
        self.sidebar_total_deposit = QLabel("Deposit: ₹0.00")
        self.sidebar_total_deposit.setObjectName("accountMeta")
        self.deposit_edit_btn = QToolButton()
        self.deposit_edit_btn.setObjectName("accountEditBtn")
        self.deposit_edit_btn.setText("✎")
        self.deposit_edit_btn.setToolTip("Edit deposit")
        self.deposit_edit_btn.clicked.connect(self._edit_sidebar_deposit)
        self.deposit_edit_btn.setEnabled(False)
        self.sidebar_deployed = QLabel("Deployed: ₹0.00")
        self.sidebar_deployed.setObjectName("accountMeta")
        self.sidebar_available = QLabel("Available: ₹0.00")
        self.sidebar_available.setObjectName("accountMeta")
        account_layout.addWidget(tag)
        account_layout.addWidget(self.sidebar_user_name)
        account_layout.addWidget(self.sidebar_user_meta)

        deposit_row = QHBoxLayout()
        deposit_row.setContentsMargins(0, 0, 0, 0)
        deposit_row.setSpacing(6)
        deposit_row.addWidget(self.sidebar_total_deposit)
        deposit_row.addWidget(self.deposit_edit_btn, 0, Qt.AlignRight)
        account_layout.addLayout(deposit_row)
        account_layout.addWidget(self.sidebar_deployed)
        account_layout.addWidget(self.sidebar_available)
        layout.addWidget(account)

        self.nav_buttons = {}
        entries = [
            ("dashboard", "Dashboard"),
            ("journal", "Journal"),
            ("filings", "Filings"),
            ("insights", "Insights"),
            ("settings", "Settings"),
            ("help", "Help"),
        ]
        for key, label in entries:
            btn = QPushButton(label)
            btn.setObjectName("navBtn")
            btn.setCheckable(True)
            btn.clicked.connect(lambda _=False, k=key: self.show_view(k))
            layout.addWidget(btn)
            self.nav_buttons[key] = btn

        self.new_trade_btn = QPushButton("◧  New Trade")
        self.new_trade_btn.setObjectName("sideTradeBtn")
        self.new_trade_btn.setFocusPolicy(Qt.NoFocus)
        self.new_trade_btn.clicked.connect(self._open_add_transaction_from_sidebar)
        layout.addWidget(self.new_trade_btn)

        layout.addStretch()
        self.logout_btn = QPushButton("Logout")
        self.logout_btn.setObjectName("navBtn")
        self.logout_btn.setCheckable(False)
        self.logout_btn.clicked.connect(self.logout)
        layout.addWidget(self.logout_btn)
        return panel

    def show_view(self, key: str):
        """Show the selected content view."""
        view_index = {
            "dashboard": 0,
            "journal": 1,
            "filings": 2,
            "insights": 3,
            "settings": 4,
            "help": 5,
        }
        index = view_index.get(key, 0)
        self.content_stack.setCurrentIndex(index)
        for k, btn in self.nav_buttons.items():
            btn.setChecked(k == key)

    def logout(self):
        """Logout current user and return to login dialog."""
        if not self.current_user:
            self.show_login(hide_main=True)
            return

        reply = QMessageBox.question(
            self,
            "Confirm Logout",
            "Are you sure you want to logout?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        user_name = self.current_user.get("name", "User")
        self.logger.info("Logout requested for user_id=%s", self.current_user.get("user_id"))
        self.current_user = None
        self.header_meta_label.setText("FY - · Last updated: -")
        self.sidebar_user_name.setText("Guest")
        self.sidebar_user_meta.setText("Local mode")
        self.sidebar_total_deposit.setText("Deposit: ₹0.00")
        self.sidebar_deployed.setText("Deployed: ₹0.00")
        self.sidebar_available.setText("Available: ₹0.00")
        self.deposit_edit_btn.setEnabled(False)
        if self.show_login(hide_main=True):
            self.status_bar.showMessage(f"Logged out: {user_name}", 2500)

    def _open_add_transaction_from_sidebar(self):
        """Open add transaction flow from sidebar quick action."""
        if not self.current_user:
            QMessageBox.information(self, "New Trade", "Login required.")
            return
        self.show_view("dashboard")
        self.dashboard_view.add_transaction()
    
    def create_menu_bar(self):
        """Create menu bar"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu('&File')

        exit_action = QAction('&Exit', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Help menu
        help_menu = menubar.addMenu('&Help')

        onboarding_action = QAction('&Onboarding Checklist', self)
        onboarding_action.triggered.connect(lambda: self.show_onboarding_checklist(force=True))
        help_menu.addAction(onboarding_action)
        
        about_action = QAction('&About', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

        # View menu intentionally omitted while app is dark-theme only.
    
    def create_header(self):
        """Create header with welcome message and actions"""
        header = QFrame()
        header.setObjectName("topUtilityBar")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        self.header_meta_label = QLabel("FY - · Last updated: -")
        self.header_meta_label.setObjectName("topBarMeta")
        layout.addWidget(self.header_meta_label)

        layout.addStretch()

        self.notif_bell_btn = QPushButton("🔔")
        self.notif_bell_btn.setObjectName("actionBlendBtn")
        self.notif_bell_btn.setFixedWidth(44)
        self.notif_bell_btn.clicked.connect(self.open_notifications_panel)
        layout.addWidget(self.notif_bell_btn)

        self.notif_badge = QLabel("0")
        self.notif_badge.setObjectName("notifBadge")
        self.notif_badge.setVisible(False)
        layout.addWidget(self.notif_badge)
        
        # AI status indicator
        self.ai_status_label = QLabel()
        self.ai_status_label.setObjectName("aiStatus")
        self.update_ai_status()
        layout.addWidget(self.ai_status_label)

        return header

    def update_ai_status(self):
        """Update AI status indicator"""
        if self.ai_service.is_available():
            self.ai_status_label.setText(f"AI: {self.ai_service.provider.upper()}")
            self.ai_status_label.setStyleSheet("color: #4ADE80; padding: 4px 8px;")
        else:
            self.ai_status_label.setText("AI: OFF")
            self.ai_status_label.setStyleSheet("color: #8B98A7; padding: 4px 8px;")
    
    def show_login(self, hide_main: bool = False):
        """Show login dialog"""
        was_visible = self.isVisible()
        if hide_main and was_visible:
            self.hide()

        dialog = LoginDialog(self if not hide_main else None)
        dialog.login_successful.connect(self.on_login_success)
        
        if dialog.exec_() != QDialog.Accepted:
            # User closed dialog without logging in
            self.close()
            return False

        if hide_main and was_visible:
            self.show()
            self.raise_()
            self.activateWindow()
        self._schedule_post_login_refresh()
        return True

    def on_login_success(self, user_data):
        """Handle successful login"""
        self.current_user = user_data
        self._set_header_meta()
        self.sidebar_user_name.setText(user_data.get("name", "User"))
        self.sidebar_user_meta.setText(user_data.get("mobile_number", "N/A"))
        self.deposit_edit_btn.setEnabled(True)
        self._refresh_sidebar_cash_summary(user_data.get("user_id"))
        self.logger.info("Login successful for user_id=%s", user_data.get("user_id"))
        self.status_bar.showMessage(f"Logged in as {user_data['name']}", 3000)
        if config.WATCHMAN_MATERIAL_SCAN_ON_LOGIN:
            try:
                job_id = self.background_jobs.enqueue_material_scan_job(user_data["user_id"], daily_only=True)
                self.logger.info("Queued daily material-scan job_id=%s for user_id=%s", job_id, user_data.get("user_id"))
            except Exception as exc:
                self.logger.error("Failed to queue material-scan job for user_id=%s: %s", user_data.get("user_id"), exc)
        if config.SHOW_ONBOARDING_HELP:
            QTimer.singleShot(700, self.show_onboarding_checklist)
        if config.WATCHMAN_AUTO_RUN_ON_LOGIN:
            QTimer.singleShot(1800, self._run_daily_watchman_if_due)

    def _schedule_post_login_refresh(self):
        """Run a fast DB-backed refresh, then async live quote refresh."""
        if not self.current_user:
            return
        QTimer.singleShot(50, lambda: self.refresh_all(
            sync_announcements=False,
            use_live_quotes=False,
            reason="startup-fast"
        ))
        if config.QUOTE_REFRESH_ASYNC_ON_LOGIN:
            QTimer.singleShot(
                max(200, config.QUOTE_REFRESH_START_DELAY_MS),
                lambda: self.start_background_quote_refresh(reason="startup-live")
            )
        self.start_notification_polling()

    def start_background_quote_refresh(self, reason: str = "manual-live"):
        """Fetch live quotes off UI thread and persist latest prices."""
        if not self.current_user:
            return
        if self._quote_refresh_in_progress:
            self.logger.info("Quote refresh skipped (%s): already in progress", reason)
            return

        user_id = int(self.current_user["user_id"])
        self._quote_refresh_in_progress = True
        thread = threading.Thread(
            target=self._background_quote_refresh_worker,
            args=(user_id, reason),
            daemon=True,
            name=f"quote-refresh-{user_id}"
        )
        thread.start()

    def _background_quote_refresh_worker(self, user_id: int, reason: str):
        """Worker: fetch latest prices and persist to DB without blocking UI."""
        t0 = perf_counter()
        updated = 0
        now_iso = datetime.now().isoformat(timespec="seconds")
        try:
            portfolio = self.db.get_portfolio_summary(user_id)
            jobs = []
            for row in portfolio:
                symbol = row.get("symbol")
                exchange = row.get("exchange")
                stock_id = row.get("stock_id")
                if not symbol or not stock_id:
                    continue
                quote_symbol = self.stock_service.to_quote_symbol(symbol, exchange=exchange)
                jobs.append((int(stock_id), quote_symbol))

            if jobs:
                max_workers = max(1, min(config.QUOTE_REFRESH_MAX_WORKERS, len(jobs)))
                with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="quote-live") as pool:
                    future_to_stock = {
                        pool.submit(self.stock_service.get_current_price, quote_symbol): stock_id
                        for stock_id, quote_symbol in jobs
                    }
                    for future in as_completed(future_to_stock):
                        stock_id = future_to_stock[future]
                        try:
                            live = future.result()
                        except Exception as exc:
                            self.logger.debug("Live quote fetch failed for stock_id=%s: %s", stock_id, exc)
                            continue
                        if live is None:
                            continue
                        self.db.save_price(stock_id, float(live))
                        updated += 1
            if updated > 0:
                self.db.set_setting(self._quote_setting_key(user_id), now_iso)
        except Exception as exc:
            self.logger.error("Background quote refresh failed (%s): %s", reason, exc)
        finally:
            elapsed = perf_counter() - t0
            self.quote_refresh_finished.emit(user_id, updated, reason, elapsed, now_iso)

    def _on_quote_refresh_finished(self, user_id: int, updated_count: int, reason: str, elapsed: float, done_iso: str):
        """Apply UI refresh after async quote sync completes."""
        self._quote_refresh_in_progress = False
        self.logger.info(
            "Background quote refresh complete (%s): updated=%s in %.2fs",
            reason, updated_count, elapsed
        )
        if not self.current_user or int(self.current_user.get("user_id") or 0) != int(user_id):
            return

        done_dt = self._parse_dt(done_iso)
        if updated_count > 0:
            self._set_header_meta(done_dt)
            self.status_bar.showMessage("Live quotes updated", 2500)
            self.refresh_all(
                sync_announcements=False,
                use_live_quotes=False,
                reason=f"{reason}-apply",
                run_price_target_checks=True
            )
        else:
            self.status_bar.showMessage("Live quote update skipped (no changes)", 2500)

    def _run_daily_watchman_if_due(self):
        """Trigger daily quarter-insight generation on first login of day."""
        if not self.current_user:
            return
        try:
            result = self.insights_view.watchman.run_daily_if_due(self.current_user["user_id"])
            if not result:
                self.logger.info("Watchman daily run skipped: already executed today.")
                return
            self.logger.info("Watchman daily run result: %s", result)
            self.insights_view.load_for_user(self.current_user["user_id"])
            self.status_bar.showMessage(
                f"Insights updated: +{result['generated']} (missing:{result['not_available']}, failed:{result['failed']})",
                5000
            )
            self.refresh_notifications()
        except Exception as exc:
            self.logger.error("Daily watchman run failed: %s", exc)
    
    def refresh_all(
        self,
        sync_announcements: bool = False,
        use_live_quotes: bool = True,
        reason: str = "manual",
        run_price_target_checks: bool = None
    ):
        """Refresh all data"""
        if not self.current_user:
            return
        if self._is_refreshing:
            self.logger.info("Refresh skipped (%s): refresh already in progress", reason)
            return
        self._is_refreshing = True
        overall_t0 = perf_counter()
        
        self.status_bar.showMessage("Refreshing...")
        try:
            self.logger.info(
                "Refresh started (%s) | sync_announcements=%s, use_live_quotes=%s",
                reason, sync_announcements, use_live_quotes
            )
            t0 = perf_counter()
            self.update_global_kpis(self.current_user['user_id'], use_live_quotes=use_live_quotes)
            self.logger.info("Refresh (%s): global KPIs in %.2fs", reason, perf_counter() - t0)

            t0 = perf_counter()
            self.dashboard_view.load_dashboard(self.current_user['user_id'], use_live_quotes=use_live_quotes)
            self.logger.info("Refresh (%s): dashboard in %.2fs", reason, perf_counter() - t0)

            t0 = perf_counter()
            self.journal_view.load_for_user(self.current_user['user_id'])
            self.logger.info("Refresh (%s): journal in %.2fs", reason, perf_counter() - t0)

            t0 = perf_counter()
            self.alerts_view.load_alerts(self.current_user['user_id'], sync_announcements=sync_announcements)
            self.logger.info("Refresh (%s): filings in %.2fs", reason, perf_counter() - t0)

            t0 = perf_counter()
            self.insights_view.load_for_user(self.current_user['user_id'])
            self.logger.info("Refresh (%s): insights in %.2fs", reason, perf_counter() - t0)

            if run_price_target_checks is None:
                run_price_target_checks = bool(use_live_quotes)
            triggered = []
            if run_price_target_checks:
                t0 = perf_counter()
                triggered = self.alert_service.check_price_targets(
                    self.current_user['user_id'],
                    use_live_quotes=use_live_quotes
                )
                self.logger.info("Refresh (%s): price-target checks in %.2fs", reason, perf_counter() - t0)
            else:
                self.logger.info("Refresh (%s): price-target checks skipped", reason)

            if triggered:
                self.alerts_view.load_alerts(self.current_user['user_id'], sync_announcements=False)
                self.insights_view.load_for_user(self.current_user['user_id'])

            if use_live_quotes:
                self.db.set_setting(
                    self._quote_setting_key(self.current_user["user_id"]),
                    datetime.now().isoformat(timespec="seconds")
                )
            self._refresh_sidebar_cash_summary(self.current_user["user_id"])
            self._set_header_meta()
            self.status_bar.showMessage("Refreshed successfully", 3000)
            elapsed = perf_counter() - overall_t0
            self.logger.info("Refresh completed (%s) in %.2fs", reason, elapsed)
            if elapsed > 20:
                self.logger.warning("Slow refresh detected (%s): %.2fs", reason, elapsed)
        finally:
            self._is_refreshing = False

    def update_global_kpis(self, user_id: int, use_live_quotes: bool = True):
        """Update global kpis.

        Args:
            user_id: Input parameter.
            use_live_quotes: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        portfolio = self.db.get_portfolio_summary(user_id)
        total_invested = 0.0
        total_current = 0.0
        total_daily = 0.0
        total_weekly = 0.0
        series_all = self.db.get_portfolio_performance_series(user_id=user_id)
        for row in portfolio:
            symbol = row["symbol"]
            exchange = row.get("exchange")
            qty = row["quantity"]
            avg = row["avg_price"]
            qsym = self.stock_service.to_quote_symbol(symbol, exchange=exchange)
            current = self.db.get_latest_price(row["stock_id"]) or avg
            if use_live_quotes:
                current = self.stock_service.get_current_price(qsym) or current
            total_invested += avg * qty
            total_current += current * qty
        daily_pct = 0.0
        weekly_pct = 0.0
        if use_live_quotes:
            period_end_dt = datetime.now().date()
            end_holdings_value = float(total_current)
        elif series_all:
            period_end_dt = datetime.strptime(series_all[-1]["trade_date"], "%Y-%m-%d").date()
            end_holdings_value = float(series_all[-1]["portfolio_value"] or 0.0)
        else:
            period_end_dt = datetime.now().date()
            end_holdings_value = float(total_current)

        daily_start = (period_end_dt - timedelta(days=1)).isoformat()
        weekly_start = (period_end_dt - timedelta(days=7)).isoformat()
        period_end = period_end_dt.isoformat()

        total_daily, daily_pct = self._compute_period_gain(
            user_id=user_id,
            series=series_all,
            end_holdings_value=end_holdings_value,
            start_date=daily_start,
            end_date=period_end
        )
        total_weekly, weekly_pct = self._compute_period_gain(
            user_id=user_id,
            series=series_all,
            end_holdings_value=end_holdings_value,
            start_date=weekly_start,
            end_date=period_end
        )
        total_returns = total_current - total_invested
        total_pct = (total_returns / total_invested * 100) if total_invested else 0.0
        self._set_kpi_value(self.global_daily_kpi, total_daily, daily_pct)
        self._set_kpi_value(self.global_weekly_kpi, total_weekly, weekly_pct)
        self._set_kpi_value(self.global_total_kpi, total_returns, total_pct)
        realized = self.db.get_realized_pnl_summary(user_id)
        realized_value = float(realized.get("total_realized_pnl") or 0.0)
        realized_color = "#4ADE80" if realized_value >= 0 else "#FB7185"
        fy_label = realized.get("fy_label", "Current FY")
        self.global_realized_kpi._value.setText(f"₹{realized_value:,.2f}  ({fy_label})")
        self.global_realized_kpi._value.setStyleSheet(f"color: {realized_color};")

    def _compute_period_gain(
        self,
        user_id: int,
        series: list,
        end_holdings_value: float,
        start_date: str,
        end_date: str
    ) -> tuple:
        """
        Compute period gain using:
            gain = v_end - v_start - net_contribution

        where:
            net_contribution = sum(BUY amounts) - sum(SELL proceeds)

        This isolates market/price performance from internal capital movement
        across holdings within the selected period.
        """
        start_value = float(self.db.get_portfolio_value_as_of(user_id, start_date))
        end_value = float(self.db.get_portfolio_value_as_of(user_id, end_date))

        # Fallback to caller-provided end holdings if date-as-of valuation is unavailable.
        if end_value <= 0 and float(end_holdings_value or 0.0) > 0:
            end_value = float(end_holdings_value)

        # Legacy fallback for start_value only when valuation service returns zero.
        if start_value <= 0:
            start_value = float(self._series_value_on_or_before(series, start_date))

        net_contribution = self.db.get_portfolio_net_transaction_cash_flow(user_id, start_date, end_date)
        gain_value = end_value - start_value - float(net_contribution)
        denominator = start_value + float(net_contribution)
        gain_pct = (gain_value / denominator * 100.0) if abs(denominator) > 1e-9 else 0.0
        return gain_value, gain_pct

    def _refresh_sidebar_cash_summary(self, user_id: int = None):
        """Update sidebar capital snapshot.

        Rules:
        - `Deposit` is user-editable and persisted in app settings.
        - `Deployed` is current holdings buy value (sum of quantity * avg_price).
        - `Available` is Deposit - Deployed.
        """
        uid = int(user_id or 0)
        if uid <= 0:
            return
        try:
            deposit = self._get_user_deposit_capital(uid)
            portfolio = self.db.get_portfolio_summary(uid)
            deployed = sum(float(row.get("quantity") or 0.0) * float(row.get("avg_price") or 0.0) for row in portfolio)
            available = deposit - deployed
            self.sidebar_total_deposit.setText(f"Deposit: ₹{deposit:,.2f}")
            self.sidebar_deployed.setText(f"Deployed: ₹{deployed:,.2f}")
            self.sidebar_available.setText(f"Available: ₹{available:,.2f}")
        except Exception:
            self.sidebar_total_deposit.setText("Deposit: ₹0.00")
            self.sidebar_deployed.setText("Deployed: ₹0.00")
            self.sidebar_available.setText("Available: ₹0.00")

    @staticmethod
    def _deposit_setting_key(user_id: int) -> str:
        """App-settings key for user-level editable deposit amount."""
        return f"user:{int(user_id)}:capital_deposit"

    def _get_user_deposit_capital(self, user_id: int) -> float:
        """Get user deposit from settings; initialize once from config default."""
        key = self._deposit_setting_key(user_id)
        stored = (self.db.get_setting(key, "") or "").strip()
        if stored:
            try:
                return float(stored)
            except Exception:
                pass
        default_deposit = float(config.LEDGER_INITIAL_CREDIT or 0.0)
        self.db.set_setting(key, f"{default_deposit:.2f}")
        return default_deposit

    def _save_user_deposit_capital(self, user_id: int, amount: float):
        """Persist user deposit amount in app settings."""
        self.db.set_setting(self._deposit_setting_key(user_id), f"{float(amount):.2f}")

    def _edit_sidebar_deposit(self):
        """Open editable deposit dialog and refresh sidebar snapshot."""
        if not self.current_user:
            return
        user_id = int(self.current_user.get("user_id") or 0)
        if user_id <= 0:
            return
        current_amount = self._get_user_deposit_capital(user_id)
        amount, ok = QInputDialog.getDouble(
            self,
            "Edit Deposit",
            "Deposit amount (₹):",
            current_amount,
            0.0,
            9999999999.0,
            2
        )
        if not ok:
            return
        self._save_user_deposit_capital(user_id, float(amount))
        self._refresh_sidebar_cash_summary(user_id)
        self.status_bar.showMessage("Deposit updated", 2000)

    @staticmethod
    def _series_value_on_or_before(series: list, target_date: str) -> float:
        """Pick portfolio value at the latest trade_date <= target_date."""
        for row in reversed(series or []):
            if (row.get("trade_date") or "") <= target_date:
                return float(row.get("portfolio_value") or 0.0)
        return 0.0

    @staticmethod
    def _set_kpi_value(card: QFrame, value: float, pct: float):
        """Set kpi value.

        Args:
            card: Input parameter.
            value: Input parameter.
            pct: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        color = "#4ADE80" if value >= 0 else "#FB7185"
        card._value.setText(f"₹{value:,.2f}  ({pct:+.2f}%)")
        card._value.setStyleSheet(f"color: {color};")

    def _apply_depth_effects(self):
        """Apply depth effects.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        preset = self._shadow_preset()
        self._apply_shadow(self.sidebar, blur=preset["panel_blur"], y_offset=preset["panel_offset"], alpha=preset["panel_alpha"])
        self._apply_shadow(self.top_bar, blur=preset["panel_blur"], y_offset=preset["panel_offset"], alpha=preset["panel_alpha"])
        self._apply_shadow(self.kpi_strip, blur=preset["panel_blur"], y_offset=preset["panel_offset"], alpha=preset["panel_alpha"])
        self._apply_shadow(
            self.content_stack,
            blur=preset["content_blur"],
            y_offset=preset["content_offset"],
            alpha=preset["content_alpha"]
        )
        self._apply_shadow(
            self.global_daily_kpi,
            blur=preset["kpi_blur"],
            y_offset=preset["kpi_offset"],
            alpha=preset["kpi_alpha"]
        )
        self._apply_shadow(
            self.global_weekly_kpi,
            blur=preset["kpi_blur"],
            y_offset=preset["kpi_offset"],
            alpha=preset["kpi_alpha"]
        )
        self._apply_shadow(
            self.global_total_kpi,
            blur=preset["kpi_blur"],
            y_offset=preset["kpi_offset"],
            alpha=preset["kpi_alpha"]
        )
        self._apply_shadow(
            self.global_realized_kpi,
            blur=preset["kpi_blur"],
            y_offset=preset["kpi_offset"],
            alpha=preset["kpi_alpha"]
        )

    @staticmethod
    def _shadow_preset():
        """Shadow preset.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        presets = {
            "subtle": {
                "panel_blur": 20, "panel_offset": 4, "panel_alpha": 80,
                "content_blur": 24, "content_offset": 5, "content_alpha": 95,
                "kpi_blur": 16, "kpi_offset": 4, "kpi_alpha": 75,
            },
            "medium": {
                "panel_blur": 34, "panel_offset": 6, "panel_alpha": 120,
                "content_blur": 40, "content_offset": 8, "content_alpha": 135,
                "kpi_blur": 28, "kpi_offset": 6, "kpi_alpha": 110,
            },
            "bold": {
                "panel_blur": 46, "panel_offset": 9, "panel_alpha": 150,
                "content_blur": 54, "content_offset": 10, "content_alpha": 165,
                "kpi_blur": 36, "kpi_offset": 8, "kpi_alpha": 145,
            },
        }
        return presets.get(config.UI_GLOW_PRESET, presets["medium"])

    @staticmethod
    def _apply_shadow(widget, blur: int, y_offset: int, alpha: int):
        """Apply shadow.

        Args:
            widget: Input parameter.
            blur: Input parameter.
            y_offset: Input parameter.
            alpha: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        effect = QGraphicsDropShadowEffect()
        effect.setBlurRadius(blur)
        effect.setOffset(0, y_offset)
        effect.setColor(QColor(0, 0, 0, alpha))
        widget.setGraphicsEffect(effect)
    
    def auto_refresh(self):
        """Auto-refresh data periodically"""
        if self.current_user:
            self.refresh_all(sync_announcements=False, use_live_quotes=False, reason="auto-refresh-db")
            self.start_background_quote_refresh(reason="auto-refresh-live")
    
    def show_about(self):
        """Show about dialog"""
        about_text = f"""
        <h2>{config.APP_NAME}</h2>
        <p>Track your equity investments with AI-powered insights.</p>
        <p><b>Features:</b></p>
        <ul>
            <li>Portfolio management</li>
            <li>Real-time price tracking</li>
            <li>Price target alerts</li>
            <li>AI-powered announcement summaries</li>
        </ul>
        <p><b>Version:</b> 1.0.0</p>
        <p><b>AI Provider:</b> {self.ai_service.provider if self.ai_service.is_available() else 'Not configured'}</p>
        """
        
        QMessageBox.about(self, "About", about_text)

    def start_notification_polling(self):
        """Start notification polling.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        if hasattr(self, "notification_timer") and self.notification_timer is not None:
            return
        self.notification_timer = QTimer(self)
        self.notification_timer.timeout.connect(self.refresh_notifications)
        self.notification_timer.start(max(2000, config.NOTIFICATION_POLL_INTERVAL_SEC * 1000))
        self.refresh_notifications()

    def refresh_notifications(self):
        """Refresh notifications.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        if not self.current_user:
            self.notif_badge.setVisible(False)
            self.notif_bell_btn.setStyleSheet("")
            return
        unread = self.db.get_unread_notifications_count(self.current_user["user_id"])
        self.notif_badge.setText(str(unread))
        self.notif_badge.setVisible(unread > 0)
        if unread > 0:
            self.notif_bell_btn.setStyleSheet("color: #4ADE80; font-weight:700;")
        else:
            self.notif_bell_btn.setStyleSheet("")

    def open_notifications_panel(self):
        """Open notifications panel.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        if not self.current_user:
            return
        notifications = self.db.get_user_notifications(self.current_user["user_id"], unread_only=True, limit=100)
        dialog = QDialog(self)
        dialog.setWindowTitle("Notifications")
        dialog.resize(760, 520)
        self._apply_active_theme(dialog)
        dialog.setStyleSheet(
            """
            QFrame#notifCard {
                border: 1px solid rgba(96, 165, 250, 0.28);
                border-radius: 12px;
                background: rgba(13, 28, 44, 0.82);
            }
            QLabel#notifTitle {
                color: #CFE5FF;
                font-weight: 700;
                font-size: 13px;
            }
            QLabel#notifTime {
                color: #87A9CE;
                font-size: 11px;
            }
            QLabel#notifDesc {
                color: #E2ECF8;
                font-size: 13px;
            }
            """
        )
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        info = QLabel("Unread notifications")
        info.setObjectName("sectionTitle")
        layout.addWidget(info)

        list_widget = QListWidget()
        list_widget.setSpacing(10)
        list_widget.setSelectionMode(QAbstractItemView.NoSelection)
        list_widget.setFocusPolicy(Qt.NoFocus)

        if not notifications:
            empty = QLabel("No unread notifications.")
            empty.setObjectName("placeholderText")
            layout.addWidget(empty)
        else:
            for n in notifications:
                item = QListWidgetItem()
                card = self._build_notification_card(n, dialog)
                item.setSizeHint(card.sizeHint())
                list_widget.addItem(item)
                list_widget.setItemWidget(item, card)
            layout.addWidget(list_widget)

        btn_row = QHBoxLayout()
        mark_read_btn = QPushButton("Mark All Read")
        mark_read_btn.clicked.connect(lambda: self._mark_all_notifications_read(dialog))
        btn_row.addWidget(mark_read_btn)
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)
        dialog.exec_()

    def _build_notification_card(self, notification: dict, parent: QWidget) -> QFrame:
        """Build one bordered notification card with compact description and links."""
        card = QFrame(parent)
        card.setObjectName("notifCard")
        root = QVBoxLayout(card)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        header = QHBoxLayout()
        header.setSpacing(8)
        title = QLabel(notification.get("title") or "Notification")
        title.setObjectName("notifTitle")
        title.setWordWrap(True)
        header.addWidget(title, 1)
        ts = QLabel(notification.get("created_at") or "")
        ts.setObjectName("notifTime")
        header.addWidget(ts, 0, Qt.AlignRight | Qt.AlignTop)
        root.addLayout(header)

        desc = QLabel(self._notification_compact_description(notification, max_words=10))
        desc.setObjectName("notifDesc")
        desc.setWordWrap(True)
        root.addWidget(desc)

        primary_url, alternate_url = self._resolve_notification_links(notification)
        links_row = QHBoxLayout()
        links_row.setSpacing(8)

        primary_btn = QPushButton("Open")
        primary_btn.setEnabled(bool(primary_url))
        primary_btn.clicked.connect(lambda _=False, u=primary_url: self._open_direct_url(u))
        links_row.addWidget(primary_btn)

        alternate_btn = QPushButton("Alternate Link")
        alternate_btn.setEnabled(bool(alternate_url))
        alternate_btn.clicked.connect(lambda _=False, u=alternate_url: self._open_direct_url(u))
        links_row.addWidget(alternate_btn)

        links_row.addStretch()
        root.addLayout(links_row)
        return card

    @staticmethod
    def _notification_compact_description(notification: dict, max_words: int = 10) -> str:
        """Return meaningful compact description limited to max_words words."""
        message = (notification.get("message") or "").strip()
        lines = [ln.strip() for ln in message.splitlines() if ln.strip()]
        candidate = ""
        for line in lines:
            lower = line.lower()
            if lower.startswith("company:") or lower.startswith("details:") or lower.startswith("alternate:"):
                continue
            if "summary:" in lower:
                _, _, rhs = line.partition(":")
                candidate = rhs.strip()
                break
            candidate = line
            break
        if not candidate:
            candidate = (notification.get("title") or "Notification").strip()
        candidate = re.sub(r"https?://\S+", "", candidate).strip()
        words = [w for w in re.sub(r"\s+", " ", candidate).split(" ") if w]
        if len(words) <= max_words:
            return " ".join(words)
        return f"{' '.join(words[:max_words])}..."

    def _resolve_notification_links(self, notification: dict) -> tuple:
        """Resolve primary and alternate links from metadata/message."""
        metadata = notification.get("metadata") or {}
        primary = self._normalize_possible_filing_url((metadata.get("detail_url") or "").strip())
        alternate = self._normalize_possible_filing_url((metadata.get("alternate_url") or "").strip())

        for raw in self._extract_notification_url_candidates(notification):
            normalized = self._normalize_possible_filing_url(raw)
            if not normalized:
                continue
            if not primary:
                primary = normalized
                continue
            if not alternate and normalized != primary:
                alternate = normalized
                break
        return primary, alternate

    def _open_direct_url(self, url: str):
        """Open url in browser; show friendly message when unavailable."""
        norm = self._normalize_possible_filing_url(url)
        if not norm:
            QMessageBox.information(self, "No Link", "No valid filing URL found for this notification.")
            return
        if not QDesktopServices.openUrl(QUrl(norm)):
            QMessageBox.warning(self, "Open Failed", "Unable to open link in browser.")

    def _open_notification_urls(self, notification: dict) -> bool:
        """Try opening primary/alternate URL candidates from notification metadata/message."""
        for raw in self._extract_notification_url_candidates(notification):
            url = self._normalize_possible_filing_url(raw)
            if not url:
                continue
            if QDesktopServices.openUrl(QUrl(url)):
                return True
        return False

    def _extract_notification_url_candidates(self, notification: dict) -> list:
        """Collect URL candidates from metadata first, then message text."""
        metadata = notification.get("metadata") or {}
        candidates = []
        for key in ("detail_url", "alternate_url"):
            val = (metadata.get(key) or "").strip()
            if val:
                candidates.append(val)
        msg = notification.get("message") or ""
        for match in re.findall(r"https?://[^\s)]+", msg):
            candidates.append(match.strip())
        # Support legacy messages that stored only a filename.
        for match in re.findall(r"[A-Za-z0-9_-]+(?:-[A-Za-z0-9_-]+)*\.pdf", msg, flags=re.IGNORECASE):
            candidates.append(match.strip())
        return candidates

    @staticmethod
    def _normalize_possible_filing_url(value: str) -> str:
        """Normalize URL/filename into browser-openable BSE filing URL."""
        raw = (value or "").strip().strip(").,]")
        if not raw:
            return ""
        if raw.startswith("http://") or raw.startswith("https://"):
            return raw
        if raw.lower().endswith(".pdf"):
            base = config.BSE_ATTACH_PRIMARY_BASE.strip()
            if not base.endswith("/"):
                base = f"{base}/"
            return f"{base}{raw.split('/')[-1]}"
        if raw.startswith("/"):
            return f"https://www.bseindia.com{raw}"
        return ""

    def _mark_all_notifications_read(self, dialog: QDialog):
        """Mark all notifications read.

        Args:
            dialog: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        if not self.current_user:
            return
        self.db.mark_all_notifications_read(self.current_user["user_id"])
        self.refresh_notifications()
        dialog.accept()

    def show_onboarding_checklist(self, force: bool = False):
        """Show first-run onboarding checklist from Help section."""
        if not self.current_user:
            return
        setting_key = f"onboarding_checklist_seen_user_{self.current_user['user_id']}"
        already_seen = self.db.get_setting(setting_key, "0") == "1"
        if already_seen and not force:
            return

        text = """
        <h3>Quick Start Checklist</h3>
        <ol>
            <li>Add transactions from <b>Dashboard</b> with setup/confidence and notes.</li>
            <li>Open <b>Filings</b> and click <b>Sync Filings</b> to ingest latest announcements.</li>
            <li>Use <b>Insights</b> to review quarter summaries for Results and Earnings Call.</li>
            <li>Review <b>Journal</b> notes and update reflections regularly.</li>
            <li>App uses a consistent <b>Dark Theme</b> across all screens and popups.</li>
        </ol>
        """
        QMessageBox.information(self, "Onboarding Checklist", text)
        self.db.set_setting(setting_key, "1")

    def apply_theme(self):
        """Load and apply app stylesheet from assets folder."""
        self.current_theme = "dark"
        css_name = "theme_dark.qss"
        css_path = Path(__file__).resolve().parent.parent / "assets" / "css" / css_name
        css = ""
        if css_path.exists():
            css = css_path.read_text(encoding="utf-8")
        app = QApplication.instance()
        if app:
            app.setStyleSheet(css)
        self.setStyleSheet(css)
        self._apply_branding_for_theme()

    def _apply_branding_for_theme(self):
        """Apply branding for theme.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        logo_path = self._logo_file_for_theme()
        if logo_path.exists():
            pixmap = QPixmap(str(logo_path)).scaled(28, 28, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            if hasattr(self, "sidebar_logo"):
                self.sidebar_logo.setPixmap(pixmap)
            self.setWindowIcon(QIcon(str(logo_path)))
        elif hasattr(self, "sidebar_logo"):
            self.sidebar_logo.clear()

    def _apply_active_theme(self, widget: QWidget):
        """Apply active theme.

        Args:
            widget: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        widget.setStyleSheet(self.styleSheet())

    def _logo_file_for_theme(self) -> Path:
        """Logo file for theme.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        images_dir = Path(__file__).resolve().parent.parent / "assets" / "images"
        candidates = ["equityjournal_logo_dark.png", "logo_dark_theme.png"]
        for name in candidates:
            path = images_dir / name
            if path.exists():
                return path
        return images_dir / candidates[0]
    
    def closeEvent(self, event):
        """Handle window close event"""
        reply = QMessageBox.question(
            self, 
            'Confirm Exit',
            'Are you sure you want to exit?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.background_jobs.stop()
            event.accept()
        else:
            event.ignore()
