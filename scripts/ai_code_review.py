#!/usr/bin/env python3
"""AI-assisted code review runner for current git branch/changes.

Generates a markdown review report by sending git diff to configured AI provider.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.config import config


DEFAULT_TEST_CMD = "PYTHONPYCACHEPREFIX=.pycache_local python3 tests/test_services.py"
MAX_DIFF_CHARS_DEFAULT = 50000


def _run_cmd(cmd: str) -> Tuple[int, str, str]:
    """Run shell command and return code/stdout/stderr."""
    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def _resolve_provider(preferred: str) -> str:
    """Resolve provider from arg/config with deterministic fallback."""
    p = (preferred or "auto").strip().lower()
    if p != "auto":
        return p

    if config.OLLAMA_BASE_URL and config.OLLAMA_MODEL:
        return "ollama"
    if config.GROQ_API_KEY:
        return "groq"
    if config.OPENAI_API_KEY:
        return "openai"
    return "none"


def _get_changed_files(base_ref: str, include_worktree: bool) -> str:
    """Get changed files list compared to base ref and optional worktree."""
    files = []
    rc, out, err = _run_cmd(f"git diff --name-only {base_ref}...HEAD")
    if rc == 0 and out:
        files.extend([x.strip() for x in out.splitlines() if x.strip()])
    elif rc != 0:
        raise RuntimeError(f"Failed to get changed files: {err or out}")

    if include_worktree:
        rc2, out2, err2 = _run_cmd("git diff --name-only HEAD")
        if rc2 == 0 and out2:
            files.extend([x.strip() for x in out2.splitlines() if x.strip()])
        elif rc2 != 0:
            raise RuntimeError(f"Failed to get working-tree changed files: {err2 or out2}")

    unique = sorted(set(files))
    return "\n".join(unique) if unique else "(no changed files found)"


def _get_diff(base_ref: str, max_chars: int, include_worktree: bool) -> str:
    """Get unified git diff clipped to max chars for token control."""
    chunks = []
    rc, out, err = _run_cmd(f"git diff --unified=2 --no-color {base_ref}...HEAD")
    if rc != 0:
        raise RuntimeError(f"Failed to get git diff: {err or out}")
    if out:
        chunks.append(out)

    if include_worktree:
        rc2, out2, err2 = _run_cmd("git diff --unified=2 --no-color HEAD")
        if rc2 != 0:
            raise RuntimeError(f"Failed to get working-tree diff: {err2 or out2}")
        if out2:
            chunks.append("\n\n# Working tree changes\n\n")
            chunks.append(out2)

    merged = "".join(chunks)
    if not merged:
        return ""
    if len(merged) > max_chars:
        return f"{merged[:max_chars]}\n\n[DIFF TRUNCATED TO {max_chars} CHARS]"
    return merged


def _build_prompt(changed_files: str, diff_text: str) -> str:
    """Build strict review prompt for actionable findings."""
    return (
        "You are a strict senior code reviewer. Review the patch below.\n"
        "Focus only on concrete issues with evidence from diff.\n"
        "Prioritize: correctness, data integrity, async/job safety, regressions, test gaps, security.\n"
        "Output markdown with sections exactly in this order:\n"
        "1) Findings (ordered by severity: Critical, High, Medium, Low)\n"
        "2) Test Gaps\n"
        "3) Suggested Fix Plan\n"
        "If no findings, say: 'No material findings.'\n"
        "For each finding include:\n"
        "- Severity\n"
        "- File path\n"
        "- Why it matters\n"
        "- Minimal fix suggestion\n\n"
        f"Changed files:\n{changed_files}\n\n"
        f"Patch:\n```diff\n{diff_text}\n```\n"
    )


def _call_ollama(prompt: str, model: str, timeout_sec: int) -> str:
    """Call Ollama generate endpoint."""
    url = f"{config.OLLAMA_BASE_URL.rstrip('/')}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_predict": 1800,
        },
    }
    resp = requests.post(url, json=payload, timeout=timeout_sec)
    resp.raise_for_status()
    data = resp.json()
    return (data.get("response") or "").strip()


def _call_openai_compatible(prompt: str, endpoint: str, api_key: str, model: str, timeout_sec: int) -> str:
    """Call OpenAI-compatible chat completions endpoint."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": "You are a precise software code reviewer."},
            {"role": "user", "content": prompt},
        ],
    }
    resp = requests.post(endpoint, headers=headers, json=payload, timeout=timeout_sec)
    resp.raise_for_status()
    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        raise RuntimeError(f"Unexpected response shape: {json.dumps(data)[:500]} | {exc}") from exc


def _run_optional_tests(test_cmd: str) -> Tuple[bool, str]:
    """Run optional test command and return pass/fail with output snippet."""
    if not test_cmd.strip():
        return True, "Skipped (no test command provided)."
    rc, out, err = _run_cmd(test_cmd)
    merged = "\n".join([s for s in [out, err] if s]).strip()
    snippet = merged[-6000:] if merged else "(no output)"
    return rc == 0, snippet


def main() -> int:
    """Entrypoint."""
    parser = argparse.ArgumentParser(description="Run AI code review for current branch diff.")
    parser.add_argument("--base", default="main", help="Base branch/ref for diff (default: main)")
    parser.add_argument("--provider", default="auto", choices=["auto", "ollama", "groq", "openai"], help="AI provider")
    parser.add_argument("--ollama-model", default=os.getenv("AI_REVIEW_OLLAMA_MODEL", config.OLLAMA_MODEL))
    parser.add_argument("--groq-model", default=os.getenv("AI_REVIEW_GROQ_MODEL", "llama-3.3-70b-versatile"))
    parser.add_argument("--openai-model", default=os.getenv("AI_REVIEW_OPENAI_MODEL", "gpt-4o-mini"))
    parser.add_argument("--run-tests", default=DEFAULT_TEST_CMD, help="Command to run tests before review")
    parser.add_argument("--max-diff-chars", type=int, default=MAX_DIFF_CHARS_DEFAULT)
    parser.add_argument(
        "--include-working-tree",
        action="store_true",
        default=True,
        help="Include uncommitted/staged local changes in review (default: enabled).",
    )
    parser.add_argument(
        "--no-include-working-tree",
        action="store_true",
        help="Disable local working-tree diff review and use committed branch diff only.",
    )
    parser.add_argument(
        "--allow-review-failure",
        action="store_true",
        help="Do not fail the command when AI provider call fails (diagnostic mode).",
    )
    parser.add_argument("--output", default="", help="Optional explicit output markdown path")
    args = parser.parse_args()

    provider = _resolve_provider(args.provider)
    if provider == "none":
        print("No AI provider configured. Set Ollama/Groq/OpenAI settings in .env.")
        return 2

    include_worktree = bool(args.include_working_tree and not args.no_include_working_tree)
    changed_files = _get_changed_files(args.base, include_worktree=include_worktree)
    diff_text = _get_diff(args.base, max_chars=max(5000, args.max_diff_chars), include_worktree=include_worktree)
    if not diff_text.strip():
        print("No diff found between base and HEAD. Nothing to review.")
        return 0

    tests_ok, test_output = _run_optional_tests(args.run_tests)
    prompt = _build_prompt(changed_files, diff_text)

    review_text = ""
    review_failed = False
    try:
        if provider == "ollama":
            review_text = _call_ollama(prompt, model=args.ollama_model, timeout_sec=max(60, config.OLLAMA_TIMEOUT_PRIMARY_SEC))
        elif provider == "groq":
            if not config.GROQ_API_KEY:
                raise RuntimeError("GROQ_API_KEY not configured")
            review_text = _call_openai_compatible(
                prompt,
                endpoint="https://api.groq.com/openai/v1/chat/completions",
                api_key=config.GROQ_API_KEY,
                model=args.groq_model,
                timeout_sec=120,
            )
        elif provider == "openai":
            if not config.OPENAI_API_KEY:
                raise RuntimeError("OPENAI_API_KEY not configured")
            review_text = _call_openai_compatible(
                prompt,
                endpoint="https://api.openai.com/v1/chat/completions",
                api_key=config.OPENAI_API_KEY,
                model=args.openai_model,
                timeout_sec=120,
            )
        else:
            raise RuntimeError(f"Unsupported provider: {provider}")
    except Exception as exc:
        review_failed = True
        review_text = f"AI review call failed: {exc}"

    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = Path(args.output) if args.output else Path("logs") / f"ai_code_review_{ts}.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    header = (
        f"# AI Code Review Report\n\n"
        f"- Timestamp: {dt.datetime.now().isoformat(timespec='seconds')}\n"
        f"- Provider: {provider}\n"
        f"- Base Ref: {args.base}\n"
        f"- Tests Passed: {'Yes' if tests_ok else 'No'}\n\n"
        f"## Test Output (latest)\n\n"
        f"```text\n{test_output}\n```\n\n"
        f"## AI Review Findings\n\n"
    )
    output_path.write_text(f"{header}{review_text}\n", encoding="utf-8")

    print(f"Review report written: {output_path}")
    if not tests_ok:
        print("Tests failed. Fix tests before merge.")
        return 1
    if review_failed and not args.allow_review_failure:
        print("AI review failed. Resolve provider connectivity/config or rerun with --allow-review-failure.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
