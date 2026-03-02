#!/usr/bin/env bash
set -euo pipefail

# Activate virtual environment if not already active
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -z "${VIRTUAL_ENV:-}" ] && [ -d "$SCRIPT_DIR/.venv" ]; then
    source "$SCRIPT_DIR/.venv/bin/activate"
fi

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8001}"
WORKERS="${WORKERS:-1}"
ENV="${ENVIRONMENT:-development}"

cleanup() {
    echo "Shutting down DashLink API..."
    kill -- -$$ 2>/dev/null
    exit 0
}
trap cleanup INT TERM EXIT

echo "Starting DashLink API (${ENV}) on ${HOST}:${PORT} with ${WORKERS} worker(s)..."

if [ "$ENV" = "production" ]; then
    granian \
        --interface asgi \
        --host "$HOST" \
        --port "$PORT" \
        --workers "$WORKERS" \
        --http 2 \
        app.main:app &
else
    granian \
        --interface asgi \
        --host "$HOST" \
        --port "$PORT" \
        --workers 1 \
        --reload \
        app.main:app &
fi

wait $!
