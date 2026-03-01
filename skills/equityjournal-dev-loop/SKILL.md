---
name: equityjournal-dev-loop
description: Delivery playbook for EquityJournal (PyQt5 + SQLite + BSE pipelines). Use when implementing, refactoring, testing, or reviewing features in this repository, especially Portfolio/Filings/Insights UI, data sync scripts, parser QA, and AI-summary workflows. Apply it when a task needs scoped code changes, dark-theme UI consistency, test + AI review loop, and documentation updates before completion.
---

# EquityJournal Dev Loop

Use this skill to execute feature work in this repository with consistent quality gates.

## Execute Core Loop

1. Scope the change narrowly and identify touched modules with `rg`.
2. Implement only what the accepted requirement needs.
3. Run local checks for changed area.
4. Run AI review pass.
5. Fix critical/high findings.
6. Re-run tests and review.
7. Update docs when behavior or runbooks changed.
8. Mark done only when DoD is met.

Use this DoD for every feature:
- Acceptance criteria met.
- No unresolved critical/high review findings.
- Tests updated and passing (or explicitly documented if blocked).
- Relevant docs updated.

## Load References On Demand

- Use `references/workflow.md` for feature execution order and completion gates.
- Use `references/ui_dark_theme.md` for UI constraints and styling rules.
- Use `references/data_sync_runbook.md` for Bhavcopy/announcements operations.
- Use `references/quality_runbook.md` for tests, AI review, and parser verification.

Load only the reference needed for the current task.

## Repository-Specific Rules

- Keep dark theme as default and avoid reintroducing light-theme branching.
- Keep long-running operations asynchronous where user interaction must stay responsive.
- Keep announcements workflow CSV-first for reliability; use API mode as fallback.
- Keep prompt templates centralized in `prompts/ai_prompt_templates.md`.
- Keep parser quality observable through verification report generation.
- Financial operations invariants:
  - Weekly/Daily gain uses holdings-performance with net transaction contribution:
    `Gain = V_end - V_start - (Buys - Sells)` for the window `(start_date, end_date]`.
  - Do not use external ledger deposits/withdrawals in holdings performance KPIs.
  - Sidebar capital snapshot semantics:
    - `Deposit` = user-editable configured capital (persisted in `app_settings`).
    - `Deployed` = current holdings buy value (`sum(quantity * avg_price)` for open positions).
    - `Available` = `Deposit - Deployed`.
  - For valuation snapshots, compute as-of date with:
    - quantities from transactions up to date,
    - price from latest BSE close on-or-before date (carry-forward allowed).

## Completion Output

For each completed task, report:
- Changed files.
- Commands run.
- Test/review results.
- Remaining risks or manual checks needed.
