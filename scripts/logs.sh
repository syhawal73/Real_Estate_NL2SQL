#!/usr/bin/env bash
# =============================================================================
# logs.sh — View container logs for the Real Estate Chatbot
# =============================================================================
# Usage:
#   ./scripts/logs.sh                # follow all logs
#   ./scripts/logs.sh backend        # follow backend logs only
#   ./scripts/logs.sh frontend       # follow frontend logs only
#   ./scripts/logs.sh postgres       # follow postgres logs only
#   ./scripts/logs.sh --tail 100     # show last 100 lines then follow
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# Default: follow all services
SERVICE=""
TAIL_LINES="200"

while [[ $# -gt 0 ]]; do
    case "$1" in
        backend|frontend|postgres)
            SERVICE="$1"
            shift
            ;;
        --tail)
            TAIL_LINES="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: ./scripts/logs.sh [service] [--tail N]"
            echo ""
            echo "  service   One of: backend, frontend, postgres (default: all)"
            echo "  --tail N  Show last N lines (default: 200)"
            exit 0
            ;;
        *)
            shift
            ;;
    esac
done

echo -e "\033[0;36m━━━ Logs ${SERVICE:+(${SERVICE})} ━━━\033[0m"
echo -e "  Press Ctrl+C to stop following.\n"

docker compose logs -f --tail "$TAIL_LINES" $SERVICE
