#!/usr/bin/env sh
set -eu

BLOCKED_FILE="docker/.env"
PLACEHOLDER_PATTERN='replace-with|change-this-password|example|dummy|sample|test'
# Match env-style keys only, e.g. SECRET_KEY=value or export SECRET_KEY=value.
# This avoids false positives on Python code like token_hash=... or constants.
SUSPICIOUS_KEY_PATTERN='^[[:space:]]*(export[[:space:]]+)?[A-Z][A-Z0-9_]*(SECRET|PASSWORD|PASS|API_KEY|TOKEN|PRIVATE_KEY)[A-Z0-9_]*='

if git diff --cached --name-only --diff-filter=ACM | grep -qx "$BLOCKED_FILE"; then
  echo "ERROR: Do not commit $BLOCKED_FILE. Commit docker/.env.example instead."
  exit 1
fi

failed=0

for file in $(git diff --cached --name-only --diff-filter=ACM); do
  [ -f "$file" ] || continue

  # Only scan newly added lines in the staged diff to reduce noise.
  added_lines=$(git diff --cached -U0 -- "$file" | grep '^+' | grep -v '^+++' | sed 's/^+//' || true)
  [ -n "$added_lines" ] || continue

  hits=$(printf '%s\n' "$added_lines" | grep -nE "$SUSPICIOUS_KEY_PATTERN" || true)
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
