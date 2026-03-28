#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Starting Temporal server (Podman)..."
podman compose -f "$SCRIPT_DIR/docker-compose.yml" up -d

echo "==> Waiting for Temporal server on localhost:7233 (max 60s)..."
for i in $(seq 1 60); do
    if nc -z localhost 7233 2>/dev/null; then
        echo "    Temporal server is ready (${i}s)"
        break
    fi
    if [ "$i" -eq 60 ]; then
        echo "ERROR: Temporal server not ready after 60s, aborting."
        exit 1
    fi
    sleep 1
done

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
echo "==> Stack is running:"
echo "    Frontend    | http://localhost:5173"
echo "    API         | http://localhost:8001"
echo "    Temporal UI | http://localhost:8233"
