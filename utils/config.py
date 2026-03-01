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
        """Init.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        env_path = Path(__file__).parent.parent / '.env'
        load_dotenv(env_path)
        
        # Database settings
        self.DATABASE_PATH = os.getenv('DATABASE_PATH', 'data/equity_tracker.db')
        
        # AI settings
        self.AI_PROVIDER = os.getenv('AI_PROVIDER', 'groq')
        self.GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')
        self.CLAUDE_API_KEY = os.getenv('CLAUDE_API_KEY', '')
        self.OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
        self.ANALYST_AI_PROVIDER = os.getenv('ANALYST_AI_PROVIDER', 'groq').strip().lower()
        self.OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://127.0.0.1:11434').strip()
        self.OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'qwen2.5:14b').strip()
        self.OLLAMA_FALLBACK_MODELS = [
            model.strip()
            for model in os.getenv('OLLAMA_FALLBACK_MODELS', '').split(',')
            if model.strip()
        ]
        self.OLLAMA_TIMEOUT_PRIMARY_SEC = int(os.getenv('OLLAMA_TIMEOUT_PRIMARY_SEC', '120'))
        self.OLLAMA_TIMEOUT_FALLBACK_SEC = int(os.getenv('OLLAMA_TIMEOUT_FALLBACK_SEC', '60'))
        self.AI_CACHE_ENABLED = os.getenv('AI_CACHE_ENABLED', 'true').lower() == 'true'
        self.AI_PROMPT_FILE = os.getenv('AI_PROMPT_FILE', 'prompts/ai_prompt_templates.md').strip()
        
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
        self.BSE_ATTACH_PRIMARY_BASE = os.getenv(
            'BSE_ATTACH_PRIMARY_BASE',
            'https://www.bseindia.com/xml-data/corpfiling/AttachHis/'
        ).strip()
        self.BSE_ATTACH_SECONDARY_BASE = os.getenv(
            'BSE_ATTACH_SECONDARY_BASE',
            'https://www.bseindia.com/xml-data/corpfiling/AttachLive/'
        ).strip()
        self.BSE_HISTORY_START_DATE = os.getenv('BSE_HISTORY_START_DATE', '20260101')
        self.BSE_API_MAX_PAGES = int(os.getenv('BSE_API_MAX_PAGES', '200'))
        
        # App settings
        self.APP_NAME = os.getenv('APP_NAME', 'EquityJournal')
        self.DEBUG_MODE = os.getenv('DEBUG_MODE', 'True').lower() == 'true'
        self.UI_GLOW_PRESET = os.getenv('UI_GLOW_PRESET', 'medium').strip().lower()
        self.ENABLE_ADMIN_REGENERATE = os.getenv('ENABLE_ADMIN_REGENERATE', 'true').lower() == 'true'
        self.WATCHMAN_AUTO_RUN_ON_LOGIN = os.getenv('WATCHMAN_AUTO_RUN_ON_LOGIN', 'false').lower() == 'true'
        self.FILINGS_OVERRIDE_ADMIN_ONLY = os.getenv('FILINGS_OVERRIDE_ADMIN_ONLY', 'true').lower() == 'true'
        self.ADMIN_SYNC_ADMIN_ONLY = os.getenv('ADMIN_SYNC_ADMIN_ONLY', 'true').lower() == 'true'
        self.ADMIN_USER_IDS = [
            int(x.strip()) for x in os.getenv('ADMIN_USER_IDS', '').split(',') if x.strip().isdigit()
        ]
        self.ADMIN_USER_MOBILES = [
            x.strip() for x in os.getenv('ADMIN_USER_MOBILES', '').split(',') if x.strip()
        ]
        self.SHOW_ONBOARDING_HELP = os.getenv('SHOW_ONBOARDING_HELP', 'true').lower() == 'true'
        self.NOTIFICATION_POLL_INTERVAL_SEC = int(os.getenv('NOTIFICATION_POLL_INTERVAL_SEC', '8'))
        self.WATCHMAN_MATERIAL_SCAN_ON_LOGIN = os.getenv('WATCHMAN_MATERIAL_SCAN_ON_LOGIN', 'true').lower() == 'true'
        self.QUOTE_REFRESH_ASYNC_ON_LOGIN = os.getenv('QUOTE_REFRESH_ASYNC_ON_LOGIN', 'true').lower() == 'true'
        self.QUOTE_REFRESH_START_DELAY_MS = int(os.getenv('QUOTE_REFRESH_START_DELAY_MS', '1200'))
        self.QUOTE_REFRESH_MAX_WORKERS = int(os.getenv('QUOTE_REFRESH_MAX_WORKERS', '4'))
        self.LEDGER_INITIAL_CREDIT = float(os.getenv('LEDGER_INITIAL_CREDIT', '1800000'))
    
    def is_ai_enabled(self):
        """Check if AI features are configured"""
        if self.AI_PROVIDER == 'groq':
            return bool(self.GROQ_API_KEY)
        elif self.AI_PROVIDER == 'claude':
            return bool(self.CLAUDE_API_KEY)
        elif self.AI_PROVIDER == 'openai':
            return bool(self.OPENAI_API_KEY)
        elif self.AI_PROVIDER == 'ollama':
            return bool(self.OLLAMA_BASE_URL and self.OLLAMA_MODEL)
        return False

# Global config instance
config = Config()
