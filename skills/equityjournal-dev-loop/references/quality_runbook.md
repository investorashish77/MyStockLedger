# Quality Runbook

## Tests

Targeted services tests:
```bash
PYTHONPYCACHEPREFIX=.pycache_local python tests/test_services.py
```

Optional full suites (project specific):
```bash
python3 tests/run_tests.py --quick
python3 tests/run_tests.py --unit
python3 tests/run_tests.py --integration
```

## AI Code Review Loop

Run local AI review:
```bash
python scripts/ai_code_review.py --base main
```

Provider override examples:
```bash
python scripts/ai_code_review.py --base main --provider ollama
python scripts/ai_code_review.py --base main --provider groq
python scripts/ai_code_review.py --base main --provider openai
```

Reference:
- `DesignDocuments/AI_CODE_REVIEW_LOOP.md`

## Parser Verification

Generate parser quality report:
```bash
python3 scripts/run_error_verification.py --limit 200
```

Useful options:
```bash
python3 scripts/run_error_verification.py --since "YYYY-MM-DD HH:MM:SS"
python3 scripts/run_error_verification.py --all-events
python3 scripts/run_error_verification.py --out logs/parser_verification_manual.md
```

Report format:
- `Company | Output | Score | Notes`

Use low-score rows first for manual parser quality review.

## Financial Calculation Verification

Weekly gain one-file reconciliation export:
```bash
python3 scripts/export_weekly_gain_recon.py --user-id <USER_ID> --end-date YYYY-MM-DD
```

This produces a single CSV with columns:
- `Date (Buy), Stock, Quantity (Buy), Buy Price, Date (Sell), Quantity (Sell), Sell Price, Today's Price`

Deep-dive weekly KPI debug export:
```bash
python3 scripts/dump_weekly_gain_debug.py --user-id <USER_ID>
```

Use when reconciling KPI values from UI with raw data snapshots.

Expected KPI formula:
- `Gain = V_end - V_start - (Buys - Sells)` for `(start_date, end_date]`.
- `V_start` and `V_end` must be as-of portfolio valuations using latest BSE close on-or-before date.
