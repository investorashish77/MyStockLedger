---
name: review-gate-agent
description: "Enforce an iterative code-quality gate for this repository after code changes. Use when a task must be handoff-ready for manual QA: run tests, run AI review, fix must-fix findings (Critical/High by default), rerun tests, rerun review, and repeat until the gate is clean."
---

# Review Gate Agent

Run a strict Build -> Test -> Review -> Fix loop until code is ready for user QA.
Use `scripts/ai_code_review.py` as the gate command.

## Core Loop

1. Identify scope of changed files.
2. Run targeted/local tests first.
3. Run AI review gate command.
4. If tests fail, fix tests first.
5. If gate fails on configured severity, implement fixes.
6. Rerun tests.
7. Rerun AI review gate.
8. Repeat until gate passes.

## Gate Command

Default:
```bash
python3 scripts/ai_code_review.py --base main --provider auto --fail-on-severity high
```

When local network/provider may fail:
```bash
python3 scripts/ai_code_review.py --base main --provider auto --fail-on-severity high --allow-review-failure
```

Use explicit tests if needed:
```bash
python3 scripts/ai_code_review.py --base main --run-tests "PYTHONPYCACHEPREFIX=.pycache_local python3 tests/test_services.py" --fail-on-severity high
```

## Exit-Code Policy

- `0`: Tests pass and review gate passes.
- `1`: Tests failed.
- `2`: AI review failed and review failures were not allowed.
- `3`: Review gate failed (findings at/above threshold or indeterminate format).

Treat `1`/`2`/`3` as must-fix before handoff.

## Fixing Rules

- Fix all Critical/High findings by default.
- Either fix Medium/Low findings or record explicit rationale when deferring.
- Never hand off to manual QA with unresolved failing tests.
- Prefer small iterative fixes over large rebases.

## Completion Criteria

- Latest test command passes.
- Latest AI review gate returns exit code `0`.
- No unresolved Critical/High findings in the latest report.
- Residual Medium/Low items (if any) are documented.

## References

- `references/review_gate_runbook.md` for command templates and triage flow.
