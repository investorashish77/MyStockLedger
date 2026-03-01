# Data Sync Runbook

## Bhavcopy Sync (daily OHLCV)

Script:
- `scripts/sync_bse_bhavcopy.py`

Typical run:
```bash
python3 scripts/sync_bse_bhavcopy.py --from-date 2026-02-01 --to-date 2026-02-25
```

Notes:
- Cache directory: `BhavCopy` (config: `BSE_BHAVCOPY_CACHE_DIR`).
- Reuse cached CSV before download.

## Announcements Sync (recommended CSV-first)

Step 1:
- Download daily snapshots with `bse_announcement_fetch.py` into `announcements/`.

Step 2:
- Sync CSV snapshots to DB:
```bash
python3 scripts/sync_bse_announcements_from_csv.py --input-dir announcements
```

## Announcements Direct API Fallback

Script:
- `scripts/sync_bse_announcements.py`

Typical run:
```bash
python3 scripts/sync_bse_announcements.py --from-date 20260219 --to-date 20260225
```

Diagnostics:
```bash
python3 scripts/sync_bse_announcements.py --from-date 20260219 --to-date 20260225 --debug-api
```

## URL Base Config

Use configurable attach bases from env/template when forming filing URLs:
- Primary and secondary BSE attachment base URLs.
