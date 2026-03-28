#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Stopping worker, API, frontend..."
pkill -f "temporal_agents.workers.worker" || true
pkill -f "uvicorn api.main:app" || true
pkill -f "vite" || true
sleep 1

echo "==> Starting worker..."
cd "$SCRIPT_DIR"
[ -f "$SCRIPT_DIR/.env" ] && set -a && source "$SCRIPT_DIR/.env" && set +a
PYTHONUNBUFFERED=1 PYTHONPATH="$SCRIPT_DIR/src" uv run python -m temporal_agents.workers.worker > /tmp/temporal-worker.log 2>&1 &
echo "    Worker PID: $!  | log: /tmp/temporal-worker.log"

echo "==> Starting API (port 8001)..."
PYTHONPATH="$SCRIPT_DIR/src" uv run python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8001 > /tmp/temporal-api.log 2>&1 &
echo "    API PID: $!  | log: /tmp/temporal-api.log"

echo "==> Checking frontend (syntax/build)..."
cd "$SCRIPT_DIR/frontend" && npm run build -- --mode development > /tmp/temporal-fe-build.log 2>&1 \
    && echo "    Build OK" \
    || { echo "    BUILD FAILED — check /tmp/temporal-fe-build.log"; exit 1; }

echo "==> Starting frontend (port 5173)..."
cd "$SCRIPT_DIR/frontend" && npm run dev > /tmp/temporal-fe.log 2>&1 &
echo "    Frontend PID: $!"

echo ""
echo "==> Done. Temporal server (Podman) was NOT restarted."
echo "    Frontend    | http://localhost:5173"
echo "    API         | http://localhost:8001"
echo "    Temporal UI | http://localhost:8233"
