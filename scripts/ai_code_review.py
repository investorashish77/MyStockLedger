#!/usr/bin/env python3
"""AI-assisted code review runner for current git branch/changes.

Generates a markdown review report by sending git diff to configured AI provider.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.config import config


DEFAULT_TEST_CMD = "PYTHONPYCACHEPREFIX=.pycache_local python3 tests/test_services.py"
MAX_DIFF_CHARS_DEFAULT = 50000
SEVERITY_LEVELS = ("critical", "high", "medium", "low")
FAIL_ON_SEVERITY_CHOICES = ("none", "critical", "high", "medium", "low")


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
        "- Severity: <Critical|High|Medium|Low>\n"
        "- File path\n"
        "- Why it matters\n"
        "- Minimal fix suggestion\n\n"
        f"Changed files:\n{changed_files}\n\n"
        f"Patch:\n```diff\n{diff_text}\n```\n"
    )


def _extract_severity_counts(review_text: str) -> Dict[str, int]:
    """Extract finding counts by severity from AI review markdown."""
    counts = {level: 0 for level in SEVERITY_LEVELS}
    text = (review_text or "").strip()
    if not text:
        return counts

    strict_hits = re.findall(
        r"(?im)^\s*(?:[-*]\s*)?severity\s*[:\-]\s*(critical|high|medium|low)\b",
        text,
    )
    if strict_hits:
        for sev in strict_hits:
            counts[sev.lower()] += 1
        return counts

    # Fallback for compact bullets like: "- High: <message>"
    fallback_hits = re.findall(
        r"(?im)^\s*(?:[-*]\s*)?(critical|high|medium|low)\s*[:\-|]",
        text,
    )
    for sev in fallback_hits:
        counts[sev.lower()] += 1
    return counts


def _is_no_material_findings(review_text: str) -> bool:
    """Detect explicit clean signal from AI review output."""
    return "no material findings" in (review_text or "").strip().lower()


def _should_fail_from_counts(severity_counts: Dict[str, int], fail_on_severity: str) -> bool:
    """Return True if counts violate configured fail threshold."""
    threshold = (fail_on_severity or "high").strip().lower()
    if threshold == "none":
        return False

    rank = {level: idx for idx, level in enumerate(SEVERITY_LEVELS)}
    cutoff = rank.get(threshold, rank["high"])
    for level, idx in rank.items():
        if idx <= cutoff and int(severity_counts.get(level, 0)) > 0:
            return True
    return False


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
        "--fail-on-severity",
        default="high",
        choices=list(FAIL_ON_SEVERITY_CHOICES),
        help="Fail gate if findings at/above this severity exist (default: high)",
    )
    parser.add_argument(
        "--allow-indeterminate-pass",
        action="store_true",
        help="Allow pass when review output has neither severity-tagged findings nor 'No material findings.'",
    )
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
    parser.add_argument("--json-output", default="", help="Optional explicit output json path")
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

    severity_counts = _extract_severity_counts(review_text)
    severity_total = int(sum(severity_counts.values()))
    no_material_findings = _is_no_material_findings(review_text)
    indeterminate_review = (not review_failed) and (severity_total == 0) and (not no_material_findings)

    gate_reason = "clean"
    gate_failed = False
    if review_failed:
        if args.allow_review_failure:
            gate_reason = "review_failed_allowed"
            gate_failed = False
        else:
            gate_reason = "review_failed"
            gate_failed = True
    elif _should_fail_from_counts(severity_counts, args.fail_on_severity):
        gate_reason = f"findings_at_or_above_{args.fail_on_severity}"
        gate_failed = True
    elif indeterminate_review and not args.allow_indeterminate_pass:
        gate_reason = "indeterminate_review_output"
        gate_failed = True
    elif indeterminate_review:
        gate_reason = "indeterminate_allowed"

    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = Path(args.output) if args.output else Path("logs") / f"ai_code_review_{ts}.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    json_output_path = Path(args.json_output) if args.json_output else output_path.with_suffix(".json")

    review_gate_passed = bool(tests_ok and not gate_failed)
    header = (
        f"# AI Code Review Report\n\n"
        f"- Timestamp: {dt.datetime.now().isoformat(timespec='seconds')}\n"
        f"- Provider: {provider}\n"
        f"- Base Ref: {args.base}\n"
        f"- Tests Passed: {'Yes' if tests_ok else 'No'}\n"
        f"- Fail Threshold: {args.fail_on_severity}\n"
        f"- Review Gate Passed: {'Yes' if review_gate_passed else 'No'}\n"
        f"- Gate Reason: {gate_reason}\n\n"
        f"## Gate Summary\n\n"
        f"- Critical findings: {severity_counts['critical']}\n"
        f"- High findings: {severity_counts['high']}\n"
        f"- Medium findings: {severity_counts['medium']}\n"
        f"- Low findings: {severity_counts['low']}\n"
        f"- No material findings signal: {'Yes' if no_material_findings else 'No'}\n"
        f"- Indeterminate review format: {'Yes' if indeterminate_review else 'No'}\n\n"
        f"## Test Output (latest)\n\n"
        f"```text\n{test_output}\n```\n\n"
        f"## AI Review Findings\n\n"
    )
    output_path.write_text(f"{header}{review_text}\n", encoding="utf-8")

    json_output = {
        "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
        "provider": provider,
        "base_ref": args.base,
        "include_working_tree": include_worktree,
        "tests_passed": bool(tests_ok),
        "review_failed": bool(review_failed),
        "allow_review_failure": bool(args.allow_review_failure),
        "fail_on_severity": args.fail_on_severity,
        "severity_counts": severity_counts,
        "no_material_findings": bool(no_material_findings),
        "indeterminate_review": bool(indeterminate_review),
        "review_gate_passed": bool(review_gate_passed),
        "gate_reason": gate_reason,
        "markdown_report_path": str(output_path),
    }
    json_output_path.write_text(json.dumps(json_output, indent=2), encoding="utf-8")

    print(f"Review report written: {output_path}")
    print(f"Review summary written: {json_output_path}")
    if not tests_ok:
        print("Tests failed. Fix tests before merge.")
        return 1
    if review_failed and not args.allow_review_failure:
        print("AI review failed. Resolve provider connectivity/config or rerun with --allow-review-failure.")
        return 2
    if gate_failed:
        print(f"Review gate failed ({gate_reason}). Address findings and rerun.")
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
