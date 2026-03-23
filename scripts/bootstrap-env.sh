#!/usr/bin/env sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
EXAMPLE="$PROJECT_ROOT/env.example"
LOCAL="$PROJECT_ROOT/.env"

if [ ! -f "$EXAMPLE" ]; then
  echo "Missing: env.example"
  exit 1
fi

if [ -f "$LOCAL" ]; then
  echo ".env already exists. No changes made."
  exit 0
fi

cp "$EXAMPLE" "$LOCAL"
echo "Created .env from env.example"
echo "Update .env with your real secrets before running."
