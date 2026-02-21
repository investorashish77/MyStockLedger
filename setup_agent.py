"""
EQUITY TRACKER - Intelligent Setup Agent
==========================================
This script will automatically set up your entire development environment.

Features:
- Checks Python version
- Installs all dependencies
- Creates project structure
- Sets up database
- Configures environment
- Verifies installation
"""

import os
import sys
import subprocess
import platform
from pathlib import Path

class SetupAgent:
    def __init__(self):
        """Init.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        self.project_root = Path.cwd()
        self.errors = []
        self.warnings = []
        
    def print_header(self, text):
        """Print header.

        Args:
            text: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        print("\n" + "="*60)
        print(f"  {text}")
        print("="*60 + "\n")
    
    def print_step(self, step_num, total_steps, description):
        """Print step.

        Args:
            step_num: Input parameter.
            total_steps: Input parameter.
            description: Input parameter.

        Returns:
            Any: Method output for caller use.
        """
        print(f"\n[{step_num}/{total_steps}] {description}...")
    
    def check_python_version(self):
        """Verify Python version is compatible"""
        self.print_step(1, 8, "Checking Python version")
        
        version = sys.version_info
        if version.major < 3 or (version.major == 3 and version.minor < 8):
            self.errors.append(f"Python 3.8+ required. You have {version.major}.{version.minor}")
            return False
        
        print(f"✓ Python {version.major}.{version.minor}.{version.micro} detected")
        return True
    
    def create_project_structure(self):
        """Create all necessary folders"""
        self.print_step(2, 8, "Creating project structure")
        
        folders = [
            'database',
            'services',
            'ui',
            'utils',
            'data',
            'logs',
            'tests'
        ]
        
        for folder in folders:
            folder_path = self.project_root / folder
            folder_path.mkdir(exist_ok=True)
            # Create __init__.py for Python packages
            if folder not in ['data', 'logs', 'tests']:
                (folder_path / '__init__.py').touch()
        
        print(f"✓ Created {len(folders)} project folders")
        return True
    
    def install_dependencies(self):
        """Install all required Python packages"""
        self.print_step(3, 8, "Installing dependencies")
        
        packages = [
            'PyQt5',           # Desktop UI framework
            'requests',        # API calls
            'python-dotenv',   # Environment variables
            'anthropic',       # Claude AI API (optional)
            'yfinance',        # Yahoo Finance data
            'beautifulsoup4',  # Web scraping
            'pandas',          # Data manipulation
            'schedule',        # Task scheduling
            'cryptography',    # For password hashing
            'groq',            # Groq AI API (optional)
            'nsetools',        # NSE symbol master adapter
        ]
        
        print("Installing packages (this may take 2-3 minutes)...\n")
        
        # Determine pip command (pip3 on some systems)
        pip_cmd = "pip3" if platform.system() == "Darwin" else "pip"
        
        for package in packages:
            try:
                print(f"  Installing {package}...", end=" ")
                subprocess.check_call(
                    [sys.executable, "-m", pip_cmd, "install", package, "-q"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                print("✓")
            except subprocess.CalledProcessError:
                # Try alternative installation for macOS
                try:
                    subprocess.check_call(
                        [sys.executable, "-m", "pip", "install", package, "--user", "-q"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    print("✓ (user)")
                except subprocess.CalledProcessError:
                    self.warnings.append(f"Failed to install {package}")
                    print("✗")
        
        print(f"\n✓ Dependency installation completed")
        return True
    
    def create_database_schema(self):
        """Create SQLite database schema"""
        self.print_step(4, 8, "Setting up database")
        
        schema_sql = """
-- Users Table
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    mobile_number TEXT UNIQUE NOT NULL,
    name TEXT,
    email TEXT,
    password_hash TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Stocks Table
CREATE TABLE IF NOT EXISTS stocks (
    stock_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    symbol TEXT NOT NULL,
    company_name TEXT,
    exchange TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- Transactions Table
CREATE TABLE IF NOT EXISTS transactions (
    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER,
    transaction_type TEXT,
    quantity INTEGER,
    price_per_share REAL,
    transaction_date DATE,
    investment_horizon TEXT,
    target_price REAL,
    thesis TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (stock_id) REFERENCES stocks(stock_id)
);

-- Alerts Table
CREATE TABLE IF NOT EXISTS alerts (
    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER,
    alert_type TEXT,
    alert_message TEXT,
    announcement_details TEXT,
    announcement_url TEXT,
    triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_read BOOLEAN DEFAULT 0,
    FOREIGN KEY (stock_id) REFERENCES stocks(stock_id)
);

-- AI Summaries Table
CREATE TABLE IF NOT EXISTS ai_summaries (
    summary_id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_id INTEGER,
    summary_text TEXT,
    sentiment TEXT,
    impact_analysis TEXT,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (alert_id) REFERENCES alerts(alert_id)
);

-- Price History Table
CREATE TABLE IF NOT EXISTS price_history (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER,
    price REAL,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (stock_id) REFERENCES stocks(stock_id)
);
"""
        
        schema_file = self.project_root / 'database' / 'schema.sql'
        schema_file.write_text(schema_sql)
        
        # Create the actual database
        import sqlite3
        db_path = self.project_root / 'data' / 'equity_tracker.db'
        conn = sqlite3.connect(db_path)
        conn.executescript(schema_sql)
        conn.commit()
        conn.close()
        
        print(f"✓ Database created at: {db_path}")
        return True
    
    def create_env_template(self):
        """Create environment variables template"""
        self.print_step(5, 8, "Creating configuration files")
        
        env_template = """# EquityJournal - Environment Configuration
# Copy this file to .env and fill in your values

# AI Provider (choose one: groq, claude, openai, local)
AI_PROVIDER=groq

# API Keys (only fill in the one you're using)
# Groq API (Free tier - recommended for development)
GROQ_API_KEY=your_groq_api_key_here

# Claude API (Anthropic - recommended for production)
CLAUDE_API_KEY=your_claude_api_key_here

# OpenAI API (optional)
OPENAI_API_KEY=your_openai_api_key_here

# Database Path
DATABASE_PATH=data/equity_tracker.db

# Alert Settings
ALERT_CHECK_INTERVAL=3600  # Check for alerts every hour (in seconds)

# Stock Data Settings
PRICE_UPDATE_INTERVAL=300  # Update prices every 5 minutes (in seconds)
BSE_RSS_URLS=

# App Settings
APP_NAME=EquityJournal
DEBUG_MODE=True
"""
        
        env_file = self.project_root / '.env.template'
        env_file.write_text(env_template)
        
        # Create actual .env if it doesn't exist
        actual_env = self.project_root / '.env'
        if not actual_env.exists():
            actual_env.write_text(env_template)
        
        print("✓ Configuration files created")
        print("  → Edit .env file to add your API keys")
        return True
    
    def create_gitignore(self):
        """Create .gitignore file"""
        gitignore_content = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/

# Environment variables
.env

# Database
*.db
*.sqlite
*.sqlite3

# IDE
.vscode/
.idea/
*.swp
*.swo

# Logs
logs/
*.log

# OS
.DS_Store
Thumbs.db

# Data files
data/*.csv
data/*.json
"""
        
        gitignore_file = self.project_root / '.gitignore'
        gitignore_file.write_text(gitignore_content)
        return True
    
    def create_requirements_file(self):
        """Create requirements.txt for easy installation"""
        self.print_step(6, 8, "Creating requirements.txt")
        
        requirements = """PyQt5>=5.15.9
requests>=2.31.0
python-dotenv>=1.0.0
anthropic>=0.25.0
yfinance>=0.2.40
beautifulsoup4>=4.12.0
pandas>=2.0.0
schedule>=1.2.0
cryptography>=41.0.0
lxml>=4.9.0
nsetools>=2.0.1
"""
        
        req_file = self.project_root / 'requirements.txt'
        req_file.write_text(requirements)
        
        print("✓ requirements.txt created")
        return True
    
    def create_readme(self):
        """Create README.md file"""
        self.print_step(7, 8, "Creating documentation")
        
        readme = """# EquityJournal

A desktop application for tracking equity investments with AI-powered analysis.

## Features
- Portfolio management with buy/sell tracking
- Investment thesis documentation
- Short/Medium/Long term categorization
- Real-time price updates
- Corporate announcement alerts
- AI-powered summary generation

## Setup

1. Clone/download this repository
2. Run setup: `python setup_agent.py`
3. Edit `.env` file with your API keys
4. Run the app: `python main.py`

## Requirements
- Python 3.8+
- Internet connection for stock data

## Tech Stack
- PyQt5 (UI)
- SQLite (Database)
- Yahoo Finance (Stock data)
- Anthropic Claude/Groq (AI summaries)

## Development Roadmap
- [x] Desktop application
- [ ] Web application
- [ ] Mobile app
- [ ] Multi-user support
- [ ] Cloud deployment

## License
Personal use only (for now)
"""
        
        readme_file = self.project_root / 'README.md'
        readme_file.write_text(readme)
        
        print("✓ README.md created")
        return True
    
    def verify_installation(self):
        """Verify all components are properly installed"""
        self.print_step(8, 8, "Verifying installation")
        
        checks = [
            ("Database file exists", (self.project_root / 'data' / 'equity_tracker.db').exists()),
            (".env file exists", (self.project_root / '.env').exists()),
            ("Project folders created", (self.project_root / 'services').exists()),
        ]
        
        all_good = True
        for check_name, check_result in checks:
            status = "✓" if check_result else "✗"
            print(f"  {status} {check_name}")
            if not check_result:
                all_good = False
        
        return all_good
    
    def run(self):
        """Run.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        self.print_header("EQUITY TRACKER - Setup Agent")
        print("This will set up your development environment automatically.\n")
        
        steps = [
            self.check_python_version,
            self.create_project_structure,
            self.install_dependencies,
            self.create_database_schema,
            self.create_env_template,
            self.create_gitignore,
            self.create_requirements_file,
            self.create_readme,
            self.verify_installation,
        ]
        
        for step in steps:
            if not step():
                self.errors.append(f"Step failed: {step.__name__}")
                break
        
        # Print summary
        self.print_header("Setup Summary")
        
        if self.errors:
            print("❌ ERRORS:")
            for error in self.errors:
                print(f"  - {error}")
            return False
        
        if self.warnings:
            print("⚠️  WARNINGS:")
            for warning in self.warnings:
                print(f"  - {warning}")
        
        print("\n✅ Setup completed successfully!\n")
        print("Next steps:")
        print("  1. Edit the .env file and add your API keys")
        print("  2. Run: python main.py")
        print("\nHappy trading! 📈\n")
        
        return True

if __name__ == "__main__":
    agent = SetupAgent()
    success = agent.run()
    sys.exit(0 if success else 1)
