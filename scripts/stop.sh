#!/usr/bin/env bash
# =============================================================================
# stop.sh — Stop all Real Estate Chatbot containers
# =============================================================================
# Usage:
#   ./scripts/stop.sh           # stop containers (keep data)
#   ./scripts/stop.sh --clean   # stop containers AND delete database volume
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

CLEAN=false
for arg in "$@"; do
    case "$arg" in
        --clean)  CLEAN=true ;;
        --help|-h)
            echo "Usage: ./scripts/stop.sh [--clean]"
            echo ""
            echo "  --clean  Also remove Docker volumes (deletes all database data!)"
            exit 0
            ;;
    esac
done

if [ "$CLEAN" = true ]; then
    echo -e "${CYAN}━━━ Stopping & cleaning everything ━━━${NC}"
    echo -e "  ${YELLOW}⚠ This will DELETE the PostgreSQL database volume!${NC}"
    read -p "  Are you sure? (y/N): " confirm
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        docker compose down -v --remove-orphans
        echo -e "  ${GREEN}✔ All containers stopped and volumes removed${NC}"
    else
        echo -e "  ${YELLOW}Cancelled.${NC}"
        exit 0
    fi
else
    echo -e "${CYAN}━━━ Stopping all services ━━━${NC}"
    docker compose down --remove-orphans
    echo -e "  ${GREEN}✔ All containers stopped (database data preserved)${NC}"
fi

echo ""
echo -e "  To start again: ${CYAN}./scripts/run.sh${NC}"
echo ""
