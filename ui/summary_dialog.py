"""
Summary Dialog
Displays AI-generated summaries of corporate announcements
"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QLabel, QPushButton,
                             QTextBrowser, QHBoxLayout)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

class SummaryDialog(QDialog):
    """Dialog for displaying AI summary"""
    
    def __init__(self, stock_symbol: str, summary_text: str, 
                 sentiment: str, parent=None):
        """Init.

        Args:
            stock_symbol: Input parameter.
            summary_text: Input parameter.
            sentiment: Input parameter.
            parent: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        super().__init__(parent)
        self.stock_symbol = stock_symbol
        self.summary_text = summary_text
        self.sentiment = sentiment
        self.is_dark = self._detect_dark_theme(parent)
        
        self.setup_ui()
    
    def setup_ui(self):
        """Setup UI"""
        self.setWindowTitle(f"AI Summary - {self.stock_symbol}")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Header
        header = QLabel(f"🤖 AI-Generated Summary: {self.stock_symbol}")
        header_font = QFont()
        header_font.setPointSize(14)
        header_font.setBold(True)
        header.setFont(header_font)
        header_bg = "#1D2B39" if self.is_dark else "#f5f5f5"
        header_fg = "#E2E8F0" if self.is_dark else "#1F2A36"
        header.setStyleSheet(f"padding: 10px; background-color: {header_bg}; color: {header_fg}; border-radius: 4px;")
        layout.addWidget(header)
        
        # Sentiment indicator
        sentiment_color = {
            'POSITIVE': '#4CAF50',
            'NEGATIVE': '#F44336',
            'NEUTRAL': '#FF9800'
        }.get(self.sentiment, '#666')
        
        sentiment_label = QLabel(f"Overall Sentiment: {self.sentiment}")
        sentiment_label.setStyleSheet(f"""
            padding: 8px;
            background-color: {sentiment_color};
            color: white;
            border-radius: 4px;
            font-weight: bold;
        """)
        layout.addWidget(sentiment_label)
        
        # Summary text browser
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser_bg = "#141C25" if self.is_dark else "white"
        browser_fg = "#E2E8F0" if self.is_dark else "#1F2A36"
        border = "#2A394B" if self.is_dark else "#ddd"
        browser.setStyleSheet("""
            QTextBrowser {
                border: 1px solid %s;
                border-radius: 4px;
                padding: 15px;
                background-color: %s;
                color: %s;
                font-size: 13px;
                line-height: 1.6;
            }
        """ % (border, browser_bg, browser_fg))
        
        # Format the summary text
        formatted_summary = self.format_summary(self.summary_text)
        browser.setHtml(formatted_summary)
        
        layout.addWidget(browser)
        
        # Disclaimer
        disclaimer = QLabel(
            "⚠️ Disclaimer: This is an AI-generated summary. "
            "Always verify information and do your own research before making investment decisions."
        )
        disclaimer_color = "#AAB6C3" if self.is_dark else "#666"
        disclaimer.setStyleSheet(f"color: {disclaimer_color}; font-size: 11px; padding: 10px;")
        disclaimer.setWordWrap(True)
        layout.addWidget(disclaimer)
        
        # Close button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
    
    def format_summary(self, text: str) -> str:
        """Format summary text with HTML"""
        # Convert markdown-style formatting to HTML
        fg = "#E2E8F0" if self.is_dark else "#1F2A36"
        heading = "#E2E8F0" if self.is_dark else "#333"
        html = f"<div style='font-family: Roboto, Segoe UI, sans-serif; color: {fg};'>"
        
        lines = text.split('\n')
        in_list = False
        
        for line in lines:
            line = line.strip()
            
            if not line:
                if in_list:
                    html += "</ul>"
                    in_list = False
                html += "<br>"
                continue
            
            # Headers (lines starting with **)
            if line.startswith('**') and line.endswith('**'):
                if in_list:
                    html += "</ul>"
                    in_list = False
                header_text = line.strip('*').strip()
                html += f"<h3 style='color: {heading}; margin-top: 15px; margin-bottom: 5px;'>{header_text}</h3>"
            
            # Bullet points
            elif line.startswith('- ') or line.startswith('• '):
                if not in_list:
                    html += "<ul style='margin-left: 20px;'>"
                    in_list = True
                list_text = line[2:].strip()
                html += f"<li style='margin-bottom: 5px;'>{list_text}</li>"
            
            # Regular text
            else:
                if in_list:
                    html += "</ul>"
                    in_list = False
                
                # Bold text
                line = line.replace('**', '<b>').replace('**', '</b>')
                
                html += f"<p style='margin-bottom: 10px;'>{line}</p>"
        
        if in_list:
            html += "</ul>"
        
        html += "</div>"
        
        return html

    @staticmethod
    def _detect_dark_theme(parent) -> bool:
        """Detect dark theme.

        Args:
            parent: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        if parent and hasattr(parent, "window"):
            win = parent.window()
            if hasattr(win, "current_theme"):
                return getattr(win, "current_theme") == "dark"
        return False
