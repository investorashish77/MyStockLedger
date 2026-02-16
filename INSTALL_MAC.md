# EQUITY TRACKER - Installation Guide for macOS

## Prerequisites ✅
- [x] MacBook (macOS 10.14 or later)
- [x] Python 3.8+ (usually pre-installed)
- [ ] Internet connection

---

## QUICK CHECK: Do You Have Python?

Open **Terminal** (Cmd + Space → type "Terminal") and run:

```bash
python3 --version
```

✅ **If you see**: `Python 3.8.x` or higher → You're good!  
❌ **If you see**: `command not found` → Install Python (see below)

---

## INSTALLATION (Choose One Method)

### Method 1: Automated Setup (RECOMMENDED) 🚀

**Step 1:** Download all files to a folder
```bash
# Example: Create folder on Desktop
mkdir ~/Desktop/equity-tracker
cd ~/Desktop/equity-tracker
# Download files here
```

**Step 2:** Make the setup script executable
```bash
chmod +x SETUP.sh
```

**Step 3:** Run the setup
```bash
./SETUP.sh
```

**That's it!** The script will:
- ✓ Check your Python version
- ✓ Install all dependencies
- ✓ Create project structure
- ✓ Set up database
- ✓ Create configuration files

---

### Method 2: Manual Setup

**Step 1:** Navigate to project folder
```bash
cd ~/Desktop/equity-tracker
```

**Step 2:** Install dependencies
```bash
pip3 install -r requirements.txt
```

**Step 3:** Run setup agent
```bash
python3 setup_agent.py
```

---

## INSTALLING PYTHON (If Needed)

### Option A: Official Python
1. Visit: https://www.python.org/downloads/
2. Download Python 3.10+ for macOS
3. Install the .pkg file
4. Run: `/Applications/Python\ 3.10/Install\ Certificates.command`

### Option B: Homebrew (Recommended for developers)
```bash
# Install Homebrew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python
brew install python3

# Verify
python3 --version
```

---

## WHAT GETS INSTALLED

### Python Packages (automatically installed):
| Package | Purpose | Size |
|---------|---------|------|
| PyQt5 | Desktop UI framework | ~50 MB |
| requests | API communication | ~500 KB |
| python-dotenv | Environment config | ~30 KB |
| yfinance | Stock price data | ~500 KB |
| beautifulsoup4 | Web scraping | ~400 KB |
| pandas | Data analysis | ~30 MB |
| anthropic | Claude AI API | ~200 KB |
| groq | Groq AI API (free) | ~150 KB |
| schedule | Task automation | ~50 KB |
| cryptography | Security | ~5 MB |

**Total Download Size**: ~100 MB  
**Installation Time**: 2-3 minutes

### Project Structure:
```
equity-tracker/
├── SETUP.sh                ← Run this first
├── setup_agent.py          
├── main.py                 ← Run this to start app
├── requirements.txt        
├── .env                    ← Add your API keys here
├── README.md
├── database/
│   ├── __init__.py
│   ├── db_manager.py
│   └── schema.sql
├── services/
│   ├── __init__.py
│   ├── auth_service.py
│   ├── stock_service.py
│   ├── alert_service.py
│   └── ai_summary_service.py
├── ui/
│   ├── __init__.py
│   ├── main_window.py
│   ├── portfolio_view.py
│   ├── alerts_view.py
│   └── summary_dialog.py
├── utils/
│   ├── __init__.py
│   └── config.py
├── data/
│   └── equity_tracker.db   ← Your database
└── logs/
    └── app.log
```

---

## POST-INSTALLATION SETUP

### 1. Configure API Keys (Optional but recommended)

Edit the `.env` file:

**Option 1: Using TextEdit**
```bash
open -a TextEdit .env
```

**Option 2: Using nano (Terminal)**
```bash
nano .env
```

**Option 3: Using VS Code**
```bash
code .env
```

Add your API key:

**For Free Groq API** (Recommended for development):
```env
AI_PROVIDER=groq
GROQ_API_KEY=your_key_here
```

Get free key from: https://console.groq.com

**For Claude API** (Better quality, minimal cost):
```env
AI_PROVIDER=claude
CLAUDE_API_KEY=your_key_here
```

Get key from: https://console.anthropic.com

### 2. Verify Installation

```bash
python3 test_installation.py
```

You should see: `✅ ALL TESTS PASSED!`

---

## RUNNING THE APP

### First Time:
```bash
python3 main.py
```

This will:
1. Open the desktop application
2. Show login/registration screen
3. Ask you to create your first user account

### Subsequent Times:
```bash
cd ~/Desktop/equity-tracker
python3 main.py
```

**Pro Tip**: Create an alias in your `~/.zshrc` or `~/.bash_profile`:
```bash
alias equity="cd ~/Desktop/equity-tracker && python3 main.py"
```

Then just type: `equity` 🚀

---

## TROUBLESHOOTING

### Issue: "python3: command not found"
**Solution**: Install Python 3 (see Installing Python section above)

### Issue: "pip3: command not found"
**Solution**: 
```bash
python3 -m ensurepip --upgrade
python3 -m pip install --upgrade pip
```

### Issue: "Permission denied" when running SETUP.sh
**Solution**: 
```bash
chmod +x SETUP.sh
```

### Issue: PyQt5 installation fails
**Solution 1**: Install via Homebrew
```bash
brew install pyqt5
```

**Solution 2**: Use pip with user flag
```bash
pip3 install PyQt5 --user
```

### Issue: SSL Certificate Error
**Solution**: Run the certificate installer
```bash
# For Python 3.10
/Applications/Python\ 3.10/Install\ Certificates.command

# Or for Python 3.11
/Applications/Python\ 3.11/Install\ Certificates.command
```

### Issue: "xcrun: error: invalid active developer path"
**Solution**: Install Xcode Command Line Tools
```bash
xcode-select --install
```

### Issue: Can't see .env file in Finder
**Solution**: Show hidden files
- Press: **Cmd + Shift + .**
- Or use Terminal: `ls -la`

### Issue: Database error
**Solution**: Delete and recreate database
```bash
rm data/equity_tracker.db
python3 setup_agent.py
```

---

## MAC-SPECIFIC NOTES

### Python Commands on Mac:
✅ Use `python3` (not `python`)  
✅ Use `pip3` (not `pip`)

### Terminal Shortcuts:
- **Cmd + T**: New tab
- **Cmd + N**: New window
- **Cmd + K**: Clear screen
- **Ctrl + C**: Stop running program
- **↑/↓ arrows**: Previous/next commands

### Finding Files:
```bash
# Show hidden files in Finder
defaults write com.apple.finder AppleShowAllFiles YES
killall Finder

# Hide them again
defaults write com.apple.finder AppleShowAllFiles NO
killall Finder
```

---

## CREATING A LAUNCHER (Optional)

### Option 1: Terminal Alias
Add to `~/.zshrc`:
```bash
echo 'alias equity="cd ~/Desktop/equity-tracker && python3 main.py"' >> ~/.zshrc
source ~/.zshrc
```

Now just type: `equity`

### Option 2: AppleScript App
1. Open **Script Editor**
2. Paste:
```applescript
do shell script "cd ~/Desktop/equity-tracker && python3 main.py"
```
3. Save as Application
4. Add to Dock

### Option 3: Automator App
1. Open **Automator**
2. New Document → Application
3. Add "Run Shell Script"
4. Paste:
```bash
cd ~/Desktop/equity-tracker
python3 main.py
```
5. Save as "Equity Tracker.app"
6. Add to Applications folder

---

## NEXT STEPS AFTER INSTALLATION

1. ✅ Run the app: `python3 main.py`
2. ✅ Create your user account
3. ✅ Add your first stock (e.g., AAPL, RELIANCE.NS)
4. ✅ Test AI summary feature
5. ✅ Set up price alerts

---

## UPDATING THE APP

When new features are added:

```bash
cd ~/Desktop/equity-tracker
git pull  # If using git
python3 setup_agent.py  # Re-run setup
python3 main.py  # Start app
```

---

## UNINSTALLING

To completely remove:

```bash
# Delete project folder
rm -rf ~/Desktop/equity-tracker

# (Optional) Uninstall packages
pip3 uninstall -r requirements.txt -y
```

---

## COST BREAKDOWN

| Component | Cost/Month |
|-----------|------------|
| Development tools | $0 (all free) |
| Python packages | $0 (all free) |
| Database (SQLite) | $0 |
| Stock data (Yahoo Finance) | $0 |
| AI Summaries (Groq free tier) | $0 |
| AI Summaries (Claude Haiku) | ~$0.15 for 50 summaries |

**Total Monthly Cost**: $0 - $0.15 🎉

---

## SYSTEM REQUIREMENTS

### Minimum:
- macOS 10.14 (Mojave) or later
- 2 GB RAM
- 500 MB free disk space
- Internet connection

### Recommended:
- macOS 12.0 (Monterey) or later
- 4 GB RAM
- 1 GB free disk space
- Broadband internet

### Tested On:
- ✅ M1/M2/M3 Macs (Apple Silicon)
- ✅ Intel Macs
- ✅ macOS Monterey, Ventura, Sonoma

---

## GETTING HELP

If you encounter issues:
1. Check this troubleshooting section
2. Run: `python3 test_installation.py`
3. Review: `logs/app.log`
4. Check: `.env` configuration

---

## PERFORMANCE NOTES FOR MAC

### M1/M2/M3 Macs (Apple Silicon):
- PyQt5 runs natively (very fast!)
- All Python packages support ARM64
- Battery efficient
- Instant app launch

### Intel Macs:
- Full compatibility
- Slightly slower than Apple Silicon
- All features work perfectly

---

Ready to start? Run:
```bash
cd ~/Desktop/equity-tracker
chmod +x SETUP.sh
./SETUP.sh
python3 main.py
```

🎉 Happy trading on your Mac! 📈
