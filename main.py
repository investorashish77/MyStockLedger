"""
EquityJournal - Main Application
Desktop app for tracking equity investments with AI-powered insights
"""

import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from ui.main_window import MainWindow
from utils.config import config
from utils.logger import get_logger

def main():
    """Main application entry point"""
    logger = get_logger(__name__)
    logger.info("Starting application: %s", config.APP_NAME)
    
    # Enable High DPI scaling
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName(config.APP_NAME)
    app.setOrganizationName("EquityJournal")
    
    # Set application style
    app.setStyle('Fusion')
    
    # Create and show main window
    window = MainWindow()
    window.show()
    logger.info("Main window shown")
    
    # Run application
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
