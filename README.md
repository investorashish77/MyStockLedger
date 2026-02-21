# EquityJournal

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

## AI Review Workflow
- Iteration board: `ENHANCED_FEATURES_DESIGN.md` (Section 11)
- AI code review loop: `DesignDocuments/AI_CODE_REVIEW_LOOP.md`
- Local review script: `python scripts/ai_code_review.py --base main`

## License
Personal use only (for now)
