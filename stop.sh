#!/bin/bash

echo "==> Stopping worker..."
pkill -f "temporal_agents.workers.worker" || true

echo "==> Stopping API..."
pkill -f "uvicorn api.main:app" || true

echo "==> Stopping frontend..."
pkill -f "vite" || true

echo "==> Done. Temporal server (Podman) was NOT stopped."
echo "    To stop Podman stack: podman compose -f docker-compose.yml down"
