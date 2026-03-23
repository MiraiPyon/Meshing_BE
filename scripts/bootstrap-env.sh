#!/usr/bin/env sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
EXAMPLE_ENV="$PROJECT_ROOT/docker/.env.example"
LOCAL_ENV="$PROJECT_ROOT/docker/.env"

if [ ! -f "$EXAMPLE_ENV" ]; then
  echo "Missing template file: docker/.env.example"
  exit 1
fi

if [ -f "$LOCAL_ENV" ]; then
  echo "docker/.env already exists. No changes made."
  exit 0
fi

cp "$EXAMPLE_ENV" "$LOCAL_ENV"
echo "Created docker/.env from docker/.env.example"
echo "Update docker/.env with your local secrets before running the app."
