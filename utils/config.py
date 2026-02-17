"""
Configuration Manager
Handles loading and accessing environment variables and app settings
"""

import os
from pathlib import Path
from dotenv import load_dotenv

class Config:
    """Application configuration"""
    
    def __init__(self):
        # Load environment variables
        env_path = Path(__file__).parent.parent / '.env'
        load_dotenv(env_path)
        
        # Database settings
        self.DATABASE_PATH = os.getenv('DATABASE_PATH', 'data/equity_tracker.db')
        
        # AI settings
        self.AI_PROVIDER = os.getenv('AI_PROVIDER', 'groq')
        self.GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')
        self.CLAUDE_API_KEY = os.getenv('CLAUDE_API_KEY', '')
        self.OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
        
        # Alert settings
        self.ALERT_CHECK_INTERVAL = int(os.getenv('ALERT_CHECK_INTERVAL', '3600'))
        
        # Stock data settings
        self.PRICE_UPDATE_INTERVAL = int(os.getenv('PRICE_UPDATE_INTERVAL', '300'))
        self.BSE_RSS_URLS = [
            url.strip() for url in os.getenv('BSE_RSS_URLS', '').split(',')
            if url.strip()
        ]
        self.BSE_API_ENDPOINT = os.getenv(
            'BSE_API_ENDPOINT',
            'https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w'
        )
        self.BSE_HISTORY_START_DATE = os.getenv('BSE_HISTORY_START_DATE', '20260101')
        self.BSE_API_MAX_PAGES = int(os.getenv('BSE_API_MAX_PAGES', '200'))
        
        # App settings
        self.APP_NAME = os.getenv('APP_NAME', 'EquityJournal')
        self.DEBUG_MODE = os.getenv('DEBUG_MODE', 'True').lower() == 'true'
        self.UI_GLOW_PRESET = os.getenv('UI_GLOW_PRESET', 'medium').strip().lower()
    
    def is_ai_enabled(self):
        """Check if AI features are configured"""
        if self.AI_PROVIDER == 'groq':
            return bool(self.GROQ_API_KEY)
        elif self.AI_PROVIDER == 'claude':
            return bool(self.CLAUDE_API_KEY)
        elif self.AI_PROVIDER == 'openai':
            return bool(self.OPENAI_API_KEY)
        return False

# Global config instance
config = Config()
