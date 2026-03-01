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

## Prompt Tuning
- Editable AI prompts file: `prompts/ai_prompt_templates.md`
- Configure path via `.env`: `AI_PROMPT_FILE=prompts/ai_prompt_templates.md`

## Cash Ledger (Deposits/Withdrawals + Buy/Sell Flow)
- Ledger behavior:
  - `BUY` debits available cash.
  - `SELL` credits available cash.
  - `DEPOSIT` adds funds.
  - `WITHDRAWAL` removes funds (only if balance is available).
- Performance flow logic:
  - `Net Cash Flow = Deposits - Withdrawals`
  - Internal portfolio events (`BUY_DEBIT`, `SELL_CREDIT`) are **excluded** from gain/loss cash-flow adjustment.
- Existing portfolios are bootstrapped once from historical transactions.
- Default opening credit is `₹18,00,000` (configurable via `LEDGER_INITIAL_CREDIT` in `.env`).
- Add Transaction dialog now shows:
  - `Available Cash`
  - `Consumed Cash`
  - `Add Funds` action.

## Codex Skill Draft
- Skill path: `skills/equityjournal-dev-loop`
- Purpose: reusable implementation/review/test workflow for this codebase.
- Invoke in Codex prompts with: `$equityjournal-dev-loop`
- Included references:
  - `skills/equityjournal-dev-loop/references/workflow.md`
  - `skills/equityjournal-dev-loop/references/ui_dark_theme.md`
  - `skills/equityjournal-dev-loop/references/data_sync_runbook.md`
  - `skills/equityjournal-dev-loop/references/quality_runbook.md`
- Additional skill:
  - `skills/calculate-gains-loss` (timeframe gain/loss formula + contract template)

## Data Sync Runbook (Bhavcopy + Announcements)

### BSE Bhavcopy (daily OHLCV)
- Script: `scripts/sync_bse_bhavcopy.py`
- Cache folder: `BhavCopy` (configurable via `.env` with `BSE_BHAVCOPY_CACHE_DIR`)
- Behavior: if daily CSV already exists in cache, it is reused before any download.

Run:
```bash
python3 scripts/sync_bse_bhavcopy.py --from-date 2026-02-01 --to-date 2026-02-25
```

Useful options:
```bash
python3 scripts/sync_bse_bhavcopy.py --from-date 2026-02-01 --to-date 2026-02-25 --include-weekends
python3 scripts/sync_bse_bhavcopy.py --from-date 2026-02-01 --to-date 2026-02-25 --fail-fast
```

Expected output:
- `BSE bhavcopy sync completed. Rows upserted: <count>`

### BSE Announcements (recommended: CSV repository + DB sync)
- Step 1 script (download daily CSV snapshots): `bse_announcement_fetch.py`
- Step 2 script (sync CSV snapshots to DB): `scripts/sync_bse_announcements_from_csv.py`
- Snapshot folder: `announcements`

Step 1:
```bash
python3 bse_announcement_fetch.py --from-date 20260101 --to-date 20260225
```

Step 2:
```bash
python3 scripts/sync_bse_announcements_from_csv.py --input-dir announcements
```

Expected output:
- Per-file read/upsert attempts
- Final summary: `Completed CSV sync. files=<n>, read_rows=<n>, upsert_attempts=<n>`

### BSE Announcements (direct API mode fallback)
- Script: `scripts/sync_bse_announcements.py`
- Endpoint defaults from `.env` (`BSE_API_ENDPOINT`)

Run:
```bash
python3 scripts/sync_bse_announcements.py --from-date 20260219 --to-date 20260225
```

Diagnostics mode:
```bash
python3 scripts/sync_bse_announcements.py --from-date 20260219 --to-date 20260225 --debug-api
```

Expected output:
- `Ingested <count> item(s) from API: <url> [YYYYMMDD..YYYYMMDD]`

## Parser Error Verification (Manual QA Aid)
- Purpose: review financial parser quality before improving extraction logic.
- Service: `services/error_verification_service.py`
- CLI runner: `scripts/run_error_verification.py`

Run:
```bash
python3 scripts/run_error_verification.py --limit 200
```

Useful options:
```bash
python3 scripts/run_error_verification.py --since "2026-02-24 00:00:00"
python3 scripts/run_error_verification.py --all-events
python3 scripts/run_error_verification.py --out logs/parser_verification_manual.md
```

Output:
- Markdown report at `logs/parser_verification_YYYYMMDD_HHMMSS.md`
- Table format:
  - `Company | Output | Score | Notes`
- `Notes` highlights what did not get reviewed (missing metrics, missing quarter, weak source, validation flags).

## License
Personal use only (for now)
