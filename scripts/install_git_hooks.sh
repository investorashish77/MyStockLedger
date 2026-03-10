#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "${REPO_ROOT}"

if [[ ! -f ".githooks/pre-push" ]]; then
  echo "Missing .githooks/pre-push hook file."
  exit 1
fi

chmod +x .githooks/pre-push
git config core.hooksPath .githooks

echo "Installed git hooks path: $(git config --get core.hooksPath)"
echo "Pre-push gate enabled."
