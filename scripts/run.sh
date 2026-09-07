#!/usr/bin/env bash
# =============================================================================
# run.sh — Start the Real Estate Chatbot (Docker)
# =============================================================================
# Use this for every subsequent run AFTER the first-time setup.
# It starts all containers using the already-built images.
# If images don't exist yet, it builds them automatically.
#
# Usage:
#   ./scripts/run.sh            # start in detached mode (background)
#   ./scripts/run.sh --logs     # start and follow logs
#   ./scripts/run.sh --build    # rebuild images then start
# =============================================================================

set -euo pipefail

# ─────────────────────────────────────────────────────────────────────────────
# Resolve project root
# ─────────────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# ─────────────────────────────────────────────────────────────────────────────
# Colors
# ─────────────────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

# ─────────────────────────────────────────────────────────────────────────────
# Parse arguments
# ─────────────────────────────────────────────────────────────────────────────
FOLLOW_LOGS=false
REBUILD=false

for arg in "$@"; do
    case "$arg" in
        --logs)  FOLLOW_LOGS=true ;;
        --build) REBUILD=true ;;
        --help|-h)
            echo "Usage: ./scripts/run.sh [--logs] [--build]"
            echo ""
            echo "  --logs   Follow container logs after starting"
            echo "  --build  Rebuild images before starting"
            exit 0
            ;;
    esac
done

# ─────────────────────────────────────────────────────────────────────────────
# Quick Docker check
# ─────────────────────────────────────────────────────────────────────────────
if ! docker info &> /dev/null; then
    echo -e "  ${YELLOW}⚠ Docker daemon is not running. Start Docker Desktop first.${NC}"
    exit 1
fi

# ─────────────────────────────────────────────────────────────────────────────
# Start services
# ─────────────────────────────────────────────────────────────────────────────
echo -e "${CYAN}━━━ Starting Real Estate Chatbot ━━━${NC}"

if [ "$REBUILD" = true ]; then
    echo -e "  Rebuilding images..."
    docker compose up -d --build
else
    docker compose up -d
fi

# ─────────────────────────────────────────────────────────────────────────────
# Wait briefly for health
# ─────────────────────────────────────────────────────────────────────────────
echo -e "  Waiting for services to be ready..."
sleep 5

# Quick health check
HEALTH=$(docker inspect --format='{{.State.Health.Status}}' re_chatbot_postgres 2>/dev/null || echo "unknown")
if [ "$HEALTH" = "healthy" ]; then
    echo -e "  ${GREEN}✔ PostgreSQL is healthy${NC}"
else
    echo -e "  ${YELLOW}⚠ PostgreSQL is still starting... (status: $HEALTH)${NC}"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Status
# ─────────────────────────────────────────────────────────────────────────────
echo ""
docker compose ps
echo ""
echo -e "${GREEN}${BOLD}  All services started!${NC}"
echo ""
echo -e "  ${BOLD}Frontend${NC}    →  ${CYAN}http://localhost:5173${NC}"
echo -e "  ${BOLD}Backend API${NC} →  ${CYAN}http://localhost:8000${NC}"
echo -e "  ${BOLD}API Docs${NC}    →  ${CYAN}http://localhost:8000/docs${NC}"
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# Optionally follow logs
# ─────────────────────────────────────────────────────────────────────────────
if [ "$FOLLOW_LOGS" = true ]; then
    echo -e "${CYAN}━━━ Following logs (Ctrl+C to stop) ━━━${NC}"
    docker compose logs -f
fi
