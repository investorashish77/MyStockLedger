"""
Main Window
The main application window with portfolio, alerts, and settings
"""

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QStackedWidget, QLabel, QPushButton, QMessageBox,
                             QStatusBar, QMenuBar, QMenu, QAction, QDialog, QFrame, QSlider, QGraphicsDropShadowEffect,
                             QListWidget, QListWidgetItem)
from PyQt5.QtCore import Qt, QTimer, QUrl
from PyQt5.QtGui import QFont, QPixmap, QIcon, QColor, QDesktopServices
from pathlib import Path
from time import perf_counter
import re
from database.db_manager import DatabaseManager
from services.stock_service import StockService
from services.alert_service import AlertService
from services.ai_summary_service import AISummaryService
from services.background_job_service import BackgroundJobService
from ui.login_dialog import LoginDialog
from ui.dashboard_view import DashboardView
from ui.portfolio_view import PortfolioView
from ui.alerts_view import AlertsView
from ui.insights_view import InsightsView
from utils.config import config
from utils.logger import get_logger

class MainWindow(QMainWindow):
    """Main application window"""
    
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
        
        # Main layout
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # Header
        header = self.create_header()
        main_layout.addWidget(header)

        # Global KPI strip above sidebar/content shell
        kpi_row = QHBoxLayout()
        self.global_daily_kpi = self._build_kpi_card("Daily Gain/Loss")
        self.global_weekly_kpi = self._build_kpi_card("Weekly Gain/Loss")
        self.global_total_kpi = self._build_kpi_card("Total Returns")
        kpi_row.addWidget(self.global_daily_kpi)
        kpi_row.addWidget(self.global_weekly_kpi)
        kpi_row.addWidget(self.global_total_kpi)
        main_layout.addLayout(kpi_row)

        # Main shell: fixed sidebar + dynamic center content
        shell = QHBoxLayout()
        main_layout.addLayout(shell, 1)

        self.sidebar = self.create_sidebar()
        shell.addWidget(self.sidebar, 0)

        self.content_stack = QStackedWidget()
        self.content_stack.setObjectName("contentStack")
        shell.addWidget(self.content_stack, 1)

        # Create views
        self.dashboard_view = DashboardView(self.db, self.stock_service, self.ai_service, show_kpis=False)
        self.portfolio_view = PortfolioView(self.db, self.stock_service)
        self.alerts_view = AlertsView(self.db, self.alert_service, self.ai_service, self.background_jobs)
        self.insights_view = InsightsView(self.db, self.alert_service, self.ai_service, self.background_jobs)

        self.content_stack.addWidget(self.dashboard_view)
        self.content_stack.addWidget(self.portfolio_view)
        self.content_stack.addWidget(self.alerts_view)
        self.content_stack.addWidget(self.insights_view)
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
        sub_lbl = QLabel("0.00%")
        sub_lbl.setObjectName("kpiSub")
        layout.addWidget(title_lbl)
        layout.addWidget(value_lbl)
        layout.addWidget(sub_lbl)
        card.setLayout(layout)
        card._value = value_lbl
        card._sub = sub_lbl
        return card

    def create_sidebar(self):
        """Create always-visible sidebar navigation."""
        panel = QFrame()
        panel.setObjectName("navPanel")
        panel.setMinimumWidth(190)
        layout = QVBoxLayout()
        panel.setLayout(layout)

        self.nav_buttons = {}
        entries = [
            ("dashboard", "Dashboard"),
            ("portfolio", "Portfolio"),
            ("filings", "Filings"),
            ("insights", "Insights"),
        ]
        for key, label in entries:
            btn = QPushButton(label)
            btn.setObjectName("navBtn")
            btn.setCheckable(True)
            btn.clicked.connect(lambda _=False, k=key: self.show_view(k))
            layout.addWidget(btn)
            self.nav_buttons[key] = btn

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
            "portfolio": 1,
            "filings": 2,
            "insights": 3,
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
        self.welcome_label.setText("Welcome!")
        if self.show_login(hide_main=True):
            self.status_bar.showMessage(f"Logged out: {user_name}", 2500)
    
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

        # View menu
        view_menu = menubar.addMenu('&View')
        toggle_theme_action = QAction('Toggle &Dark Theme', self)
        toggle_theme_action.setShortcut('Ctrl+T')
        toggle_theme_action.triggered.connect(self.toggle_theme)
        view_menu.addAction(toggle_theme_action)
    
    def create_header(self):
        """Create header with welcome message and actions"""
        header = QWidget()
        layout = QHBoxLayout()
        header.setLayout(layout)

        self.logo_label = QLabel()
        self.logo_label.setFixedSize(30, 30)
        layout.addWidget(self.logo_label)

        # Welcome message
        self.welcome_label = QLabel("Welcome!")
        welcome_font = QFont()
        welcome_font.setPointSize(14)
        welcome_font.setBold(True)
        self.welcome_label.setFont(welcome_font)
        layout.addWidget(self.welcome_label)
        
        layout.addStretch()
        
        self.theme_label = QLabel("Dark Theme")
        self.theme_label.setObjectName("themeLabel")
        layout.addWidget(self.theme_label)

        self.theme_toggle = QSlider(Qt.Horizontal)
        self.theme_toggle.setRange(0, 1)
        self.theme_toggle.setPageStep(1)
        self.theme_toggle.setSingleStep(1)
        self.theme_toggle.setFixedWidth(58)
        self.theme_toggle.setFixedHeight(30)
        self.theme_toggle.setObjectName("themeToggle")
        self.theme_toggle.valueChanged.connect(self.toggle_theme)
        self.theme_toggle.setValue(1)
        layout.addWidget(self.theme_toggle)

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
        self.update_ai_status()
        layout.addWidget(self.ai_status_label)
        
        return header
    
    def update_ai_status(self):
        """Update AI status indicator"""
        if self.ai_service.is_available():
            self.ai_status_label.setText(f"🤖 AI: {self.ai_service.provider.upper()}")
            self.ai_status_label.setStyleSheet("color: #4CAF50; padding: 8px;")
        else:
            self.ai_status_label.setText("🤖 AI: Not configured")
            self.ai_status_label.setStyleSheet("color: #999; padding: 8px;")
    
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
        self.welcome_label.setText(f"Welcome, {user_data['name']}! 👋")
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
        """Run a fast refresh first, then a live-price refresh after UI is visible."""
        if not self.current_user:
            return
        QTimer.singleShot(50, lambda: self.refresh_all(
            sync_announcements=False,
            use_live_quotes=False,
            reason="startup-fast"
        ))
        QTimer.singleShot(900, lambda: self.refresh_all(
            sync_announcements=False,
            use_live_quotes=True,
            reason="startup-live"
        ))
        self.start_notification_polling()

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
    
    def refresh_all(self, sync_announcements: bool = False, use_live_quotes: bool = True, reason: str = "manual"):
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
            self.portfolio_view.load_portfolio(self.current_user['user_id'], use_live_quotes=use_live_quotes)
            self.logger.info("Refresh (%s): portfolio in %.2fs", reason, perf_counter() - t0)

            t0 = perf_counter()
            self.alerts_view.load_alerts(self.current_user['user_id'], sync_announcements=sync_announcements)
            self.logger.info("Refresh (%s): filings in %.2fs", reason, perf_counter() - t0)

            t0 = perf_counter()
            self.insights_view.load_for_user(self.current_user['user_id'])
            self.logger.info("Refresh (%s): insights in %.2fs", reason, perf_counter() - t0)

            t0 = perf_counter()
            triggered = self.alert_service.check_price_targets(self.current_user['user_id'])
            self.logger.info("Refresh (%s): price-target checks in %.2fs", reason, perf_counter() - t0)

            if triggered:
                self.alerts_view.load_alerts(self.current_user['user_id'], sync_announcements=False)
                self.insights_view.load_for_user(self.current_user['user_id'])

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

            if use_live_quotes:
                info = self.stock_service.get_stock_info(qsym) or {}
                prev_close = info.get("previous_close") or info.get("current_price")
                try:
                    prev_close = float(prev_close)
                except Exception:
                    prev_close = None
                if prev_close is not None:
                    total_daily += (current - prev_close) * qty

                history = self.stock_service.get_historical_prices(qsym, period="5d")
                if history and history.get("prices"):
                    try:
                        base = float(history["prices"][0])
                        total_weekly += (current - base) * qty
                    except Exception:
                        pass
        total_returns = total_current - total_invested
        daily_pct = (total_daily / total_current * 100) if total_current else 0.0
        weekly_pct = (total_weekly / total_current * 100) if total_current else 0.0
        total_pct = (total_returns / total_invested * 100) if total_invested else 0.0
        self._set_kpi_value(self.global_daily_kpi, total_daily, daily_pct)
        self._set_kpi_value(self.global_weekly_kpi, total_weekly, weekly_pct)
        self._set_kpi_value(self.global_total_kpi, total_returns, total_pct)

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
        card._value.setText(f"₹{value:,.2f}")
        card._value.setStyleSheet(f"color: {color};")
        card._sub.setText(f"{pct:+.2f}%")
        card._sub.setStyleSheet(f"color: {color};")

    def _apply_depth_effects(self):
        """Apply depth effects.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        preset = self._shadow_preset()
        self._apply_shadow(self.sidebar, blur=preset["panel_blur"], y_offset=preset["panel_offset"], alpha=preset["panel_alpha"])
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
            self.refresh_all(sync_announcements=False, use_live_quotes=True, reason="auto-refresh")
    
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
        notifications = self.db.get_user_notifications(self.current_user["user_id"], unread_only=False, limit=100)
        dialog = QDialog(self)
        dialog.setWindowTitle("Notifications")
        dialog.resize(640, 420)
        self._apply_active_theme(dialog)
        layout = QVBoxLayout(dialog)
        list_widget = QListWidget()
        notice = QLabel("Tip: Double-click a notification to open filing link (if available).")
        layout.addWidget(notice)
        row_map = []
        for n in notifications:
            prefix = "● " if not n.get("is_read") else ""
            item = QListWidgetItem(
                f"{prefix}{n.get('created_at')} | {n.get('title')}\n{n.get('message')}"
            )
            if not n.get("is_read"):
                item.setForeground(self.palette().highlight())
            list_widget.addItem(item)
            row_map.append(n)
        list_widget.itemDoubleClicked.connect(lambda item, rows=row_map, lw=list_widget: self._open_notification_link(item, rows, lw))
        layout.addWidget(list_widget)

        btn_row = QHBoxLayout()
        open_btn = QPushButton("Open Link")
        open_btn.clicked.connect(lambda: self._open_selected_notification_link(row_map, list_widget))
        btn_row.addWidget(open_btn)
        mark_read_btn = QPushButton("Mark All Read")
        mark_read_btn.clicked.connect(lambda: self._mark_all_notifications_read(dialog))
        btn_row.addWidget(mark_read_btn)
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)
        dialog.exec_()

    def _open_notification_link(self, item: QListWidgetItem, rows: list, list_widget: QListWidget):
        """Open detail URL from notification metadata when user double-clicks list row."""
        row = list_widget.row(item)
        if row < 0 or row >= len(rows):
            return
        if not self._open_notification_urls(rows[row]):
            QMessageBox.information(self, "No Link", "No valid filing URL found for this notification.")
            return

    def _open_selected_notification_link(self, rows: list, list_widget: QListWidget):
        """Open link for currently selected notification row."""
        row = list_widget.currentRow()
        if row < 0 or row >= len(rows):
            QMessageBox.information(self, "Select Notification", "Select a notification first.")
            return
        if not self._open_notification_urls(rows[row]):
            QMessageBox.information(self, "No Link", "No valid filing URL found for selected notification.")

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
            <li>Add transactions from <b>Portfolio</b> with setup/confidence and notes.</li>
            <li>Open <b>Filings</b> and click <b>Sync Filings</b> to ingest latest announcements.</li>
            <li>Use <b>Insights</b> to review quarter summaries for Results and Earnings Call.</li>
            <li>Review <b>Journal Notes</b> in Dashboard and update reflections regularly.</li>
            <li>Use dark/light toggle; default mode is <b>Dark Theme</b>.</li>
        </ol>
        """
        QMessageBox.information(self, "Onboarding Checklist", text)
        self.db.set_setting(setting_key, "1")

    def apply_theme(self):
        """Load and apply app stylesheet from assets folder."""
        css_name = "theme_dark.qss" if self.current_theme == "dark" else "theme_light.qss"
        css_path = Path(__file__).resolve().parent.parent / "assets" / "css" / css_name
        css = ""
        if css_path.exists():
            css = css_path.read_text(encoding="utf-8")
        app = QApplication.instance()
        if app:
            app.setStyleSheet(css)
        self.setStyleSheet(css)
        self._apply_branding_for_theme()
        is_dark = self.current_theme == "dark"
        self.theme_label.setText("Dark Theme")
        current_val = self.theme_toggle.value()
        target_val = 1 if is_dark else 0
        if current_val != target_val:
            self.theme_toggle.blockSignals(True)
            self.theme_toggle.setValue(target_val)
            self.theme_toggle.blockSignals(False)

    def toggle_theme(self, checked=False):
        """Toggle theme.

        Args:
            checked: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        if isinstance(checked, bool):
            self.current_theme = "dark" if checked else "light"
        elif isinstance(checked, int):
            self.current_theme = "dark" if checked == 1 else "light"
        else:
            self.current_theme = "dark" if self.current_theme == "light" else "light"
        self.apply_theme()

    def _apply_branding_for_theme(self):
        """Apply branding for theme.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        logo_path = self._logo_file_for_theme()
        if logo_path.exists():
            pixmap = QPixmap(str(logo_path)).scaled(26, 26, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.logo_label.setPixmap(pixmap)
            self.setWindowIcon(QIcon(str(logo_path)))
        else:
            self.logo_label.clear()

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
        candidates = (
            ["equityjournal_logo_dark.png", "logo_dark_theme.png"]
            if self.current_theme == "dark"
            else ["equityjournal_logo_light.png", "logo_light_theme.png"]
        )
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
