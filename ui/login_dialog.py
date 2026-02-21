"""
Login and Registration Dialog
"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QMessageBox, QTabWidget, QWidget, QFrame, QGraphicsDropShadowEffect)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QPixmap, QColor
from pathlib import Path
from database.db_manager import DatabaseManager
from services.auth_service import AuthService
from utils.config import config

class LoginDialog(QDialog):
    """Login and registration dialog"""
    
    # Signal emitted when user successfully logs in
    login_successful = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        """Init.

        Args:
            parent: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        super().__init__(parent)
        self.db = DatabaseManager()
        self.auth_service = AuthService(self.db)
        self.user_data = None
        
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the UI"""
        self.setWindowTitle(f"{config.APP_NAME} - Login")
        self.setFixedWidth(400)
        self.setObjectName("loginDialog")

        layout = QVBoxLayout()
        self.setStyleSheet("""
            QDialog {
                background: qradialgradient(cx:0.5, cy:0.2, radius:1.2, stop:0 #1B2430, stop:0.6 #11161D, stop:1 #0B0F14);
                color: #E2E8F0; font-family: "Roboto", "Segoe UI", sans-serif;
            }
            QFrame#loginCard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #151D27, stop:1 #10161F);
                border: 1px solid rgba(120,160,200,0.2);
                border-radius: 16px;
            }
            QWidget {
                background: transparent;
                color: #DCE5EF;
            }
            QLabel { color: #DCE5EF; }
            QLineEdit, QTextEdit {
                background: #1B2531; color: #E2E8F0;
                border: 1px solid #314255; border-radius: 8px; padding: 8px;
            }
            QLineEdit:focus {
                border: 1px solid #60A5FA;
            }
            QLineEdit::placeholder {
                color: #8EA2B6;
            }
            QTabWidget::pane { border: 1px solid #2A394B; border-radius: 10px; background: #141C25; }
            QTabBar::tab { background: #1A2430; color: #BFD0E3; padding: 8px 12px; border-top-left-radius: 8px; border-top-right-radius: 8px; }
            QTabBar::tab:selected { background: #3D5AFE; color: white; }
            QTabBar::tab:hover:!selected { background: #243445; color: #D8E4F1; }
            QMessageBox {
                background: #11161D;
            }
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3D5AFE, stop:1 #60A5FA);
                border: 1px solid #4D8FD2; border-radius: 8px; color: white; padding: 9px 12px; font-weight: 600;
            }
            QPushButton:hover { background: #3D5AFE; }
        """)
        card = QFrame()
        card.setObjectName("loginCard")
        card_layout = QVBoxLayout()
        card_layout.setContentsMargins(16, 14, 16, 16)
        card.setLayout(card_layout)
        shadow = QGraphicsDropShadowEffect()
        blur, offset, alpha = self._shadow_values()
        shadow.setBlurRadius(blur)
        shadow.setOffset(0, offset)
        shadow.setColor(QColor(0, 0, 0, alpha))
        card.setGraphicsEffect(shadow)
        layout.addWidget(card)

        # Brand row
        brand_row = QHBoxLayout()
        logo = QLabel()
        images_dir = Path(__file__).resolve().parent.parent / "assets" / "images"
        logo_path = images_dir / "logo_dark_theme.png"
        if logo_path.exists():
            logo.setPixmap(QPixmap(str(logo_path)).scaled(28, 28, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        brand_row.addStretch()
        brand_row.addWidget(logo)

        # Title
        title = QLabel(config.APP_NAME)
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        brand_row.addWidget(title)
        brand_row.addStretch()
        card_layout.addLayout(brand_row)
        
        # Subtitle
        subtitle = QLabel("Track your investments with AI-powered insights")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #9FB0C4; margin-bottom: 20px;")
        card_layout.addWidget(subtitle)
        
        # Tab widget for Login/Register
        tabs = QTabWidget()
        tabs.addTab(self.create_login_tab(), "Login")
        tabs.addTab(self.create_register_tab(), "Register")
        card_layout.addWidget(tabs)
        
        self.setLayout(layout)

    @staticmethod
    def _shadow_values():
        """Shadow values.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        mapping = {
            "subtle": (22, 4, 110),
            "medium": (34, 8, 160),
            "bold": (46, 10, 190),
        }
        return mapping.get(config.UI_GLOW_PRESET, mapping["medium"])
    
    def create_login_tab(self):
        """Create login tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Mobile number
        layout.addWidget(QLabel("Mobile Number:"))
        self.login_mobile = QLineEdit()
        self.login_mobile.setPlaceholderText("Enter 10-digit mobile number")
        layout.addWidget(self.login_mobile)
        
        # Password
        layout.addWidget(QLabel("Password:"))
        self.login_password = QLineEdit()
        self.login_password.setPlaceholderText("Enter password")
        self.login_password.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.login_password)
        
        # Login button
        login_btn = QPushButton("Login")
        login_btn.clicked.connect(self.handle_login)
        layout.addWidget(login_btn)
        
        layout.addStretch()
        widget.setLayout(layout)
        return widget
    
    def create_register_tab(self):
        """Create registration tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Name
        layout.addWidget(QLabel("Full Name:"))
        self.reg_name = QLineEdit()
        self.reg_name.setPlaceholderText("Enter your name")
        layout.addWidget(self.reg_name)
        
        # Mobile number
        layout.addWidget(QLabel("Mobile Number:"))
        self.reg_mobile = QLineEdit()
        self.reg_mobile.setPlaceholderText("Enter 10-digit mobile number")
        layout.addWidget(self.reg_mobile)
        
        # Email (optional)
        layout.addWidget(QLabel("Email (Optional):"))
        self.reg_email = QLineEdit()
        self.reg_email.setPlaceholderText("Enter email address")
        layout.addWidget(self.reg_email)
        
        # Password
        layout.addWidget(QLabel("Password:"))
        self.reg_password = QLineEdit()
        self.reg_password.setPlaceholderText("At least 6 characters")
        self.reg_password.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.reg_password)
        
        # Confirm password
        layout.addWidget(QLabel("Confirm Password:"))
        self.reg_confirm_password = QLineEdit()
        self.reg_confirm_password.setPlaceholderText("Re-enter password")
        self.reg_confirm_password.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.reg_confirm_password)
        
        # Register button
        register_btn = QPushButton("Create Account")
        register_btn.clicked.connect(self.handle_register)
        layout.addWidget(register_btn)
        
        layout.addStretch()
        widget.setLayout(layout)
        return widget
    
    def handle_login(self):
        """Handle login button click"""
        mobile = self.login_mobile.text().strip()
        password = self.login_password.text()
        
        if not mobile or not password:
            QMessageBox.warning(self, "Error", "Please fill in all fields")
            return
        
        success, message, user_data = self.auth_service.login(mobile, password)
        
        if success:
            self.user_data = user_data
            self.login_successful.emit(user_data)
            self.accept()
        else:
            QMessageBox.warning(self, "Login Failed", message)
    
    def handle_register(self):
        """Handle registration button click"""
        name = self.reg_name.text().strip()
        mobile = self.reg_mobile.text().strip()
        email = self.reg_email.text().strip()
        password = self.reg_password.text()
        confirm_password = self.reg_confirm_password.text()
        
        # Validation
        if not name or not mobile or not password:
            QMessageBox.warning(self, "Error", "Please fill in all required fields")
            return
        
        if password != confirm_password:
            QMessageBox.warning(self, "Error", "Passwords do not match")
            return
        
        # Register user
        success, message, user_id = self.auth_service.register_user(
            mobile, name, password, email if email else None
        )
        
        if success:
            QMessageBox.information(self, "Success", "Account created successfully! Please login.")
            # Clear registration fields
            self.reg_name.clear()
            self.reg_mobile.clear()
            self.reg_email.clear()
            self.reg_password.clear()
            self.reg_confirm_password.clear()
        else:
            QMessageBox.warning(self, "Registration Failed", message)
