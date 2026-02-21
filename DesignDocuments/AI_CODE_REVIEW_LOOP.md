# AI Code Review Loop (Execution Standard)

This document defines the mandatory review loop before merging code.

## Tooling
- Primary PR reviewer: GitHub Copilot Code Review
- Secondary/local fallback: `scripts/ai_code_review.py` (Ollama/Groq/OpenAI)
- Quality gate: `.github/workflows/pr-quality-gate.yml`

## Step-by-step loop
1. Create feature branch from `main`.
2. Implement code changes.
3. Run local checks:
   - `PYTHONPYCACHEPREFIX=.pycache_local python tests/test_services.py`
4. Run local AI review:
   - `python scripts/ai_code_review.py --base main`
5. Open PR and request Copilot review.
6. Classify findings:
   - Must-fix: Critical/High
   - Optional: Medium/Low (or document rationale)
7. Apply fixes and rerun tests.
8. Run local AI review again for post-fix sanity.
9. Request PR re-review.
10. Merge only after all required checks pass and no unresolved must-fix findings remain.

## Local AI review script
Basic usage:
```bash
python scripts/ai_code_review.py --base main
```

Useful options:
```bash
python scripts/ai_code_review.py --base main --provider ollama
python scripts/ai_code_review.py --base main --provider groq
python scripts/ai_code_review.py --base main --provider openai
python scripts/ai_code_review.py --base main --run-tests "PYTHONPYCACHEPREFIX=.pycache_local python tests/test_services.py"
python scripts/ai_code_review.py --base main --allow-review-failure   # diagnostics only
```

Output:
- Markdown report at `logs/ai_code_review_YYYYMMDD_HHMMSS.md`

## Environment settings for local AI review
Optional env vars:
- `AI_REVIEW_OLLAMA_MODEL`
- `AI_REVIEW_GROQ_MODEL`
- `AI_REVIEW_OPENAI_MODEL`
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
