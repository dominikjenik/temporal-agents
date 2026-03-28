#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Stopping worker..."
pkill -f "temporal_agents.workers.worker" 2>/dev/null || true

echo "==> Stopping API (port 8001)..."
pkill -f "uvicorn api.main:app" 2>/dev/null || true
lsof -ti:8001 2>/dev/null | xargs -r kill -9 2>/dev/null || true

echo "==> Stopping frontend (port 8003)..."
pkill -f "vite" 2>/dev/null || true
lsof -ti:8003 2>/dev/null | xargs -r kill -9 2>/dev/null || true

echo "==> Waiting for ports to free..."
sleep 2

echo "==> Stopping Temporal server (Podman)..."
podman compose -f "$SCRIPT_DIR/docker-compose.yml" down

echo "==> Done."
