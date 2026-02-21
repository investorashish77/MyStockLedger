# Copilot Review Instructions

Review this repository in a strict code-review mode.

## Priorities
1. Correctness and data integrity first.
2. Background job safety (duplicate runs, race conditions, idempotency).
3. Database migration/backward compatibility for SQLite.
4. UI behavior consistency (dark/light themes, non-blocking operations).
5. Test coverage for changed behavior.

## Output expectations
- Findings should be ordered by severity: Critical, High, Medium, Low.
- Each finding should include file path and concrete fix suggestion.
- Flag missing tests when logic changes.

## Domain context
- App: EquityJournal (PyQt desktop app)
- Core areas: filings sync, bhavcopy sync, watchman insights, background jobs, alerts UI
- Avoid destructive suggestions for data migration unless explicitly requested.
