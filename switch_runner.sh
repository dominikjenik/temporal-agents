#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"

current() {
    grep "^TEMPORAL_RUNNER=" "$ENV_FILE" 2>/dev/null | cut -d= -f2 || echo "claude"
}

usage() {
    echo "Usage: ./switch_runner.sh [claude|cline|status]"
    echo "  claude  — use Claude CLI (default)"
    echo "  cline   — use Cline CLI"
    echo "  status  — show current runner"
    echo ""
    echo "Current: $(current)"
}

case "${1:-status}" in
    claude|cline)
        if grep -q "^TEMPORAL_RUNNER=" "$ENV_FILE" 2>/dev/null; then
            sed -i "s/^TEMPORAL_RUNNER=.*/TEMPORAL_RUNNER=${1}/" "$ENV_FILE"
        else
            echo "TEMPORAL_RUNNER=${1}" >> "$ENV_FILE"
        fi
        echo "Switched to: ${1}"
        echo "Restart worker to apply: ./restart.sh"
        ;;
    status)
        echo "Current runner: $(current)"
        ;;
    *)
        usage
        exit 1
        ;;
esac
