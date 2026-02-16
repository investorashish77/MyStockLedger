"""
Main Window
The main application window with portfolio, alerts, and settings
"""

from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QTabWidget, QLabel, QPushButton, QMessageBox,
                             QStatusBar, QMenuBar, QMenu, QAction,QDialog)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QPixmap, QIcon
from pathlib import Path
from database.db_manager import DatabaseManager
from services.stock_service import StockService
from services.alert_service import AlertService
from services.ai_summary_service import AISummaryService
from ui.login_dialog import LoginDialog
from ui.dashboard_view import DashboardView
from ui.portfolio_view import PortfolioView
from ui.alerts_view import AlertsView
from ui.insights_view import InsightsView
from utils.config import config

class MainWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        
        # Initialize services
        self.db = DatabaseManager()
        self.stock_service = StockService()
        self.alert_service = AlertService(self.db)
        self.ai_service = AISummaryService()
        
        # User data
        self.current_user = None
        self.current_theme = "light"
        
        # Setup UI
        self.setup_ui()
        
        # Show login dialog
        self.show_login()
        
        # Setup auto-refresh timer (every 5 minutes)
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.auto_refresh)
        self.refresh_timer.start(300000)  # 5 minutes
    
    def setup_ui(self):
        """Setup the main UI"""
        self.setWindowTitle(config.APP_NAME)
        self.setGeometry(100, 100, 1200, 800)
        
        # Create menu bar
        self.create_menu_bar()
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # Header
        header = self.create_header()
        main_layout.addWidget(header)
        
        # Tab widget
        self.tabs = QTabWidget()
        
        # Create tabs
        self.dashboard_view = DashboardView(self.db, self.stock_service)
        self.portfolio_view = PortfolioView(self.db, self.stock_service)
        self.alerts_view = AlertsView(self.db, self.alert_service, self.ai_service)
        self.insights_view = InsightsView(self.db, self.alert_service, self.ai_service)
        
        self.tabs.addTab(self.dashboard_view, "🏠 Dashboard")
        self.tabs.addTab(self.portfolio_view, "📊 Portfolio")
        self.tabs.addTab(self.alerts_view, "📄 Filings")
        self.tabs.addTab(self.insights_view, "🧠 Insights")
        self.dashboard_view.open_filings_btn.clicked.connect(lambda: self.tabs.setCurrentWidget(self.alerts_view))
        
        main_layout.addWidget(self.tabs)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
        self.apply_theme()
    
    def create_menu_bar(self):
        """Create menu bar"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu('&File')
        
        refresh_action = QAction('&Refresh', self)
        refresh_action.setShortcut('Ctrl+R')
        refresh_action.triggered.connect(self.refresh_all)
        file_menu.addAction(refresh_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction('&Exit', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Help menu
        help_menu = menubar.addMenu('&Help')
        
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
        
        # Refresh button
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.refresh_all)
        layout.addWidget(refresh_btn)

        self.theme_btn = QPushButton("🌙 Dark")
        self.theme_btn.clicked.connect(self.toggle_theme)
        layout.addWidget(self.theme_btn)
        
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
    
    def show_login(self):
        """Show login dialog"""
        dialog = LoginDialog(self)
        dialog.login_successful.connect(self.on_login_success)
        
        if dialog.exec_() != QDialog.Accepted:
            # User closed dialog without logging in
            self.close()
    
    def on_login_success(self, user_data):
        """Handle successful login"""
        self.current_user = user_data
        self.welcome_label.setText(f"Welcome, {user_data['name']}! 👋")
        
        # Load user data
        self.refresh_all()
        
        self.status_bar.showMessage(f"Logged in as {user_data['name']}", 3000)
    
    def refresh_all(self):
        """Refresh all data"""
        if not self.current_user:
            return
        
        self.status_bar.showMessage("Refreshing...")
        
        # Refresh portfolio
        self.dashboard_view.load_dashboard(self.current_user['user_id'])
        self.portfolio_view.load_portfolio(self.current_user['user_id'])

        # Pull latest material announcements for portfolio and refresh alerts
        self.alerts_view.load_alerts(self.current_user['user_id'], sync_announcements=True)
        self.insights_view.load_for_user(self.current_user['user_id'])
        
        # Check for price target alerts
        triggered = self.alert_service.check_price_targets(self.current_user['user_id'])
        if triggered:
            self.alerts_view.load_alerts(self.current_user['user_id'], sync_announcements=False)
            self.insights_view.load_for_user(self.current_user['user_id'])
        
        self.status_bar.showMessage("Refreshed successfully", 3000)
    
    def auto_refresh(self):
        """Auto-refresh data periodically"""
        if self.current_user:
            self.refresh_all()
    
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

    def apply_theme(self):
        """Load and apply app stylesheet from assets folder."""
        css_name = "theme_dark.qss" if self.current_theme == "dark" else "theme_light.qss"
        css_path = Path(__file__).resolve().parent.parent / "assets" / "css" / css_name
        if css_path.exists():
            self.setStyleSheet(css_path.read_text(encoding="utf-8"))
        self._apply_branding_for_theme()
        self.theme_btn.setText("☀️ Light" if self.current_theme == "dark" else "🌙 Dark")

    def toggle_theme(self):
        self.current_theme = "dark" if self.current_theme == "light" else "light"
        self.apply_theme()

    def _apply_branding_for_theme(self):
        logo_path = self._logo_file_for_theme()
        if logo_path.exists():
            pixmap = QPixmap(str(logo_path)).scaled(26, 26, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.logo_label.setPixmap(pixmap)
            self.setWindowIcon(QIcon(str(logo_path)))
        else:
            self.logo_label.clear()

    def _logo_file_for_theme(self) -> Path:
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
            event.accept()
        else:
            event.ignore()
