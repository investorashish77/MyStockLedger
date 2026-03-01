# Workflow Reference

## Standard Delivery Sequence

1. Read requirement and confirm objective.
2. Inspect impacted modules (`rg`, targeted file reads).
3. Implement minimal scoped change.
4. Update/add tests for changed behavior.
5. Run tests locally.
6. Run AI code review.
7. Fix critical/high findings.
8. Re-run tests and review.
9. Update design/runbook docs if behavior changed.

For financial/KPI changes, include an explicit reconciliation pass:
- Export weekly reconciliation CSV (`scripts/export_weekly_gain_recon.py`).
- Compare UI KPI vs exported formula inputs before marking done.

## Mandatory Gates

- No unresolved critical/high issues from review.
- Tests pass for changed area.
- User-visible behavior is verified (manual pass if UI).
- Documentation aligns with implemented behavior.

## Feature-by-Feature Cadence

Use this cadence repeatedly rather than batching large unreviewed changes:
- Build -> review -> test -> fix -> verify -> done.

## Key Project Board

Track priorities against:
- `DesignDocuments/ITERATION_EXECUTION_BOARD.md`
