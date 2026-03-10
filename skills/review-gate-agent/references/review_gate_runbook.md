# Review Gate Runbook

## Standard Command

```bash
python3 scripts/ai_code_review.py --base main --provider auto --fail-on-severity high
```

## Enforce On Every Push

```bash
./scripts/install_git_hooks.sh
```

This installs `.githooks/pre-push`, which blocks pushes when tests or review gate fail.

## Fast Iteration Command

Use this while iterating locally and provider/network is unstable:

```bash
python3 scripts/ai_code_review.py --base main --provider auto --fail-on-severity high --allow-review-failure
```

Note: `--allow-review-failure` suppresses provider-call blocking only. It does not hide test failures.

## Triage Flow

1. If exit code is `1`, fix tests first.
2. If exit code is `2`, fix provider/config/network issue or rerun with `--allow-review-failure`.
3. If exit code is `3`, read latest report in `logs/ai_code_review_*.md` and fix findings at/above threshold.
4. Rerun the same command.
5. Stop only when exit code is `0`.

## Output Files

- Markdown report: `logs/ai_code_review_YYYYMMDD_HHMMSS.md`
- JSON summary: `logs/ai_code_review_YYYYMMDD_HHMMSS.json`

Use JSON summary fields:
- `tests_passed`
- `severity_counts`
- `review_gate_passed`
- `gate_reason`
