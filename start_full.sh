#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Stopping any running processes..."
pkill -f "temporal_agents.workers.worker" 2>/dev/null || true
pkill -f "uvicorn api.main:app" 2>/dev/null || true
lsof -ti:8001 2>/dev/null | xargs -r kill -9 2>/dev/null || true
pkill -f "vite" 2>/dev/null || true
lsof -ti:8003 2>/dev/null | xargs -r kill -9 2>/dev/null || true
sleep 1

echo "==> Restarting Temporal server (Podman)..."
podman compose -f "$SCRIPT_DIR/docker-compose.yml" down
podman compose -f "$SCRIPT_DIR/docker-compose.yml" up -d

echo "==> Waiting for Temporal gRPC on localhost:7233 (max 90s)..."
for i in $(seq 1 90); do
    if temporal operator cluster health 2>/dev/null | grep -qi "SERVING"; then
        echo "    Temporal gRPC ready via CLI (${i}s)"
        break
    elif nc -z localhost 7233 2>/dev/null; then
        # Port open but gRPC may still be initializing — extra buffer
        if [ "$i" -ge 10 ]; then
            echo "    Port 7233 open, assuming gRPC ready (${i}s)"
            break
        fi
    fi
    if [ "$i" -eq 90 ]; then
        echo "ERROR: Temporal not ready after 90s, aborting."
        exit 1
    fi
    sleep 1
done
sleep 2

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

echo "==> Starting frontend (port 8003)..."
cd "$SCRIPT_DIR/frontend" && npm run dev > /tmp/temporal-fe.log 2>&1 &
echo "    Frontend PID: $!"

echo ""
echo "==> Stack is running:"
echo "    Frontend    | http://localhost:8003"
echo "    API         | http://localhost:8001"
echo "    Temporal UI | http://localhost:8002"
