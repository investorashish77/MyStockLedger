# AI Code Review Loop (Execution Standard)

This document defines the mandatory review loop before merging code.

## Tooling
- Primary PR reviewer: GitHub Copilot Code Review
- Secondary/local fallback: `scripts/ai_code_review.py` (Ollama/Groq/OpenAI)
- Quality gate: `.github/workflows/pr-quality-gate.yml`
- Local auto-gate: `.githooks/pre-push` (install via `scripts/install_git_hooks.sh`)

## Step-by-step loop
1. Create feature branch from `main`.
2. Implement code changes.
3. Run local checks:
   - `PYTHONPYCACHEPREFIX=.pycache_local python tests/test_services.py`
4. Run local AI review:
   - `python3 scripts/ai_code_review.py --base main --fail-on-severity high`
5. Open PR and request Copilot review.
6. Classify findings:
   - Must-fix: Critical/High
   - Optional: Medium/Low (or document rationale)
7. Apply fixes and rerun tests.
8. Run local AI review again for post-fix sanity.
9. Request PR re-review.
10. Merge only after all required checks pass and no unresolved must-fix findings remain.

## Local Hook Enforcement

Install once per clone:
```bash
./scripts/install_git_hooks.sh
```

After this, every `git push` runs:
- `tests/test_services.py`
- `scripts/ai_code_review.py` with provider and severity policy

Configurable env vars for local pushes:
- `AI_REVIEW_PROVIDER` (default: `auto`)
- `AI_REVIEW_FAIL_ON_SEVERITY` (default: `high`)
- `AI_REVIEW_TEST_CMD` (default: `PYTHONPYCACHEPREFIX=.pycache_local python3 tests/test_services.py`)
- `REVIEW_BASE_REF` (default: `main`)

## Local AI review script
Basic usage:
```bash
python3 scripts/ai_code_review.py --base main --fail-on-severity high
```

Useful options:
```bash
python3 scripts/ai_code_review.py --base main --provider ollama --fail-on-severity high
python3 scripts/ai_code_review.py --base main --provider groq --fail-on-severity high
python3 scripts/ai_code_review.py --base main --provider openai --fail-on-severity high
python3 scripts/ai_code_review.py --base main --run-tests "PYTHONPYCACHEPREFIX=.pycache_local python3 tests/test_services.py" --fail-on-severity high
python3 scripts/ai_code_review.py --base main --allow-review-failure --fail-on-severity high   # diagnostics only
python3 scripts/ai_code_review.py --base main --fail-on-severity critical
python3 scripts/ai_code_review.py --base main --fail-on-severity none
```

Output:
- Markdown report at `logs/ai_code_review_YYYYMMDD_HHMMSS.md`
- JSON summary at `logs/ai_code_review_YYYYMMDD_HHMMSS.json`
- Exit code gate:
  - `0`: tests + review gate pass
  - `1`: tests failed
  - `2`: AI provider review failed (without `--allow-review-failure`)
  - `3`: findings at/above threshold (or indeterminate review format)

## Environment settings for local AI review
Optional env vars:
- `AI_REVIEW_OLLAMA_MODEL`
- `AI_REVIEW_GROQ_MODEL`
- `AI_REVIEW_OPENAI_MODEL`
- `AI_REVIEW_FAIL_ON_SEVERITY` (default `high`)
- `ADMIN_SYNC_ADMIN_ONLY` (auth gate for admin sync operations in UI)

Provider credentials are read from existing `.env`:
- `GROQ_API_KEY`
- `OPENAI_API_KEY`
- `OLLAMA_BASE_URL` and `OLLAMA_MODEL`

## Merge policy
A PR is merge-ready when:
1. `PR Quality Gate` is green.
2. AI review loop checklist in PR template is complete.
3. Unresolved Critical/High findings are zero.
4. AI review command exits success without `--allow-review-failure`.

## CI Configuration

`PR Quality Gate` now enforces AI review success in CI using `OPENAI_API_KEY` secret.
Optional repository variables:
- `AI_REVIEW_PROVIDER` (default: `openai`)
- `AI_REVIEW_FAIL_ON_SEVERITY` (default: `high`)
