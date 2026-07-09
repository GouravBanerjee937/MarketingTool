#!/usr/bin/env bash
# Start Postgres (if needed), backend, and frontend for local dev.
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"

brew services start postgresql@16 >/dev/null 2>&1 || true

echo "→ backend on :8000"
(cd "$ROOT/backend" && uv run alembic upgrade head && uv run uvicorn app.main:app --reload --port 8000) &
BACK=$!

echo "→ frontend on :5173"
(cd "$ROOT/frontend" && npm run dev) &
FRONT=$!

trap "kill $BACK $FRONT 2>/dev/null" EXIT
wait
