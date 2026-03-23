#!/usr/bin/env sh
set -eu

BLOCKED_FILE="docker/.env"
PLACEHOLDER_PATTERN='replace-with|change-this-password|example|dummy|sample|test'
SUSPICIOUS_KEY_PATTERN='(SECRET|PASSWORD|PASS|API_KEY|TOKEN|PRIVATE_KEY)'

if git diff --cached --name-only --diff-filter=ACM | grep -qx "$BLOCKED_FILE"; then
  echo "ERROR: Do not commit $BLOCKED_FILE. Commit docker/.env.example instead."
  exit 1
fi

failed=0

for file in $(git diff --cached --name-only --diff-filter=ACM); do
  [ -f "$file" ] || continue

  staged_content=$(git show ":$file" || true)
  [ -n "$staged_content" ] || continue

  hits=$(printf '%s\n' "$staged_content" | grep -nE "$SUSPICIOUS_KEY_PATTERN[[:space:]]*=" || true)
  [ -n "$hits" ] || continue

  real_hits=$(printf '%s\n' "$hits" | grep -viE "$PLACEHOLDER_PATTERN" || true)
  [ -n "$real_hits" ] || continue

  echo "ERROR: Potential secret detected in staged file: $file"
  printf '%s\n' "$real_hits"
  failed=1
done

if [ "$failed" -ne 0 ]; then
  echo "Commit blocked. Replace secrets with placeholders or move values to untracked env files."
  exit 1
fi

exit 0
