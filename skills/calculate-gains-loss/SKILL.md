---
name: calculate-gains-loss
description: Implement and validate portfolio gain/loss calculations for daily, weekly, and monthly windows using value snapshots and cash-ledger flows (deposits, withdrawals, buy debits, sell credits). Use when adding or fixing performance KPIs, ledger integration, or timeframe analytics.
---

# Calculate Gains/Loss

Use this skill when performance numbers must be cash-flow adjusted and timeframe-based.

## Core Formula

For a timeframe window:

- `v_start`: portfolio value at/before start date
- `v_end`: portfolio value at end date
- `net_cash_flow`: external or ledger cash flow in window

Compute:

- `gain_amount = v_end - v_start - net_cash_flow`
- `gain_percent = gain_amount / (v_start + net_cash_flow) * 100` (if denominator != 0)

## Timeframe Rules

- `daily`: start = end_date - 1 day
- `weekly`: start = end_date - 7 days
- `monthly`: start = first day of end_date month

Always use nearest available valuation at or before start date.

## Data Rules

- Prefer persisted market snapshots for start/end valuation.
- Use ledger-based cash flow where available:
  - deposit => positive
  - withdrawal => negative
  - buy debit => negative for available cash, but include only when implementing transaction-flow adjusted performance model
  - sell credit => positive for available cash, but include only when implementing transaction-flow adjusted performance model
- Keep the chosen cash-flow convention explicit in code and tests.

## Validation Checklist

1. Add tests with multiple buys/sells inside one week.
2. Add tests spanning multiple weeks with mixed transactions.
3. Add an integration assertion on rendered KPI text/value.
4. Verify weekend/holiday behavior (no fixed index assumptions like `[-6]`).

## Function Contract

See `references/function_contract.json` for the tool-style contract used by this project.
