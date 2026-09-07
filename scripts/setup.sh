#!/usr/bin/env bash
# =============================================================================
# setup.sh — First-time setup for the Real Estate Chatbot (Docker)
# =============================================================================
# Run this ONCE when you first clone the repo. It will:
#   1. Verify Docker & Docker Compose are installed
#   2. Build all Docker images (postgres, backend, frontend)
#   3. Start all containers
#   4. Wait for PostgreSQL to be healthy
#   5. Wait for the backend API to respond
#   6. Print access URLs
#
# Usage:
#   chmod +x scripts/setup.sh
#   ./scripts/setup.sh
#
# On Windows (Git Bash / WSL):
#   bash scripts/setup.sh
# =============================================================================

set -euo pipefail

# ─────────────────────────────────────────────────────────────────────────────
# Resolve project root (parent of scripts/)
# ─────────────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# ─────────────────────────────────────────────────────────────────────────────
# Colors & helpers
# ─────────────────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'  # No Color

step()  { echo -e "\n${CYAN}━━━ $1 ━━━${NC}"; }
ok()    { echo -e "  ${GREEN}✔ $1${NC}"; }
warn()  { echo -e "  ${YELLOW}⚠ $1${NC}"; }
fail()  { echo -e "  ${RED}✖ $1${NC}"; exit 1; }

# ─────────────────────────────────────────────────────────────────────────────
# 1. Check prerequisites
# ─────────────────────────────────────────────────────────────────────────────
step "Checking prerequisites"

# Docker
if command -v docker &> /dev/null; then
    DOCKER_VER=$(docker --version | grep -oP '\d+\.\d+\.\d+' | head -1)
    ok "Docker $DOCKER_VER"
else
    fail "Docker not found. Install Docker Desktop: https://docs.docker.com/get-docker/"
fi

# Docker Compose (v2 — docker compose subcommand)
if docker compose version &> /dev/null; then
    COMPOSE_VER=$(docker compose version --short 2>/dev/null || docker compose version | grep -oP '\d+\.\d+\.\d+' | head -1)
    ok "Docker Compose $COMPOSE_VER"
else
    fail "Docker Compose not found. It's included with Docker Desktop, or install the plugin: https://docs.docker.com/compose/install/"
fi

# Check Docker daemon is running
if docker info &> /dev/null; then
    ok "Docker daemon is running"
else
    fail "Docker daemon is not running. Start Docker Desktop first."
fi

# ─────────────────────────────────────────────────────────────────────────────
# 2. Build Docker images
# ─────────────────────────────────────────────────────────────────────────────
step "Building Docker images (this may take a few minutes on first run)"

docker compose build --no-cache
ok "All images built successfully"

# ─────────────────────────────────────────────────────────────────────────────
# 3. Start all services
# ─────────────────────────────────────────────────────────────────────────────
step "Starting all services"

docker compose up -d
ok "Containers started"

# ─────────────────────────────────────────────────────────────────────────────
# 4. Wait for PostgreSQL to be healthy
# ─────────────────────────────────────────────────────────────────────────────
step "Waiting for PostgreSQL to be healthy"

MAX_WAIT=60
ELAPSED=0
while [ $ELAPSED -lt $MAX_WAIT ]; do
    HEALTH=$(docker inspect --format='{{.State.Health.Status}}' re_chatbot_postgres 2>/dev/null || echo "starting")
    if [ "$HEALTH" = "healthy" ]; then
        ok "PostgreSQL is healthy"
        break
    fi
    echo -ne "  Waiting... (${ELAPSED}s / ${MAX_WAIT}s)\r"
    sleep 2
    ELAPSED=$((ELAPSED + 2))
done

if [ "$HEALTH" != "healthy" ]; then
    fail "PostgreSQL did not become healthy within ${MAX_WAIT}s. Check logs: docker compose logs postgres"
fi

# ─────────────────────────────────────────────────────────────────────────────
# 5. Verify database was seeded
# ─────────────────────────────────────────────────────────────────────────────
step "Verifying database seed"

# Wait for the seed container to finish (it should already be done)
MAX_WAIT=60
ELAPSED=0
while [ $ELAPSED -lt $MAX_WAIT ]; do
    SEED_STATUS=$(docker inspect --format='{{.State.Status}}' re_chatbot_db_seed 2>/dev/null || echo "unknown")
    if [ "$SEED_STATUS" = "exited" ]; then
        SEED_EXIT=$(docker inspect --format='{{.State.ExitCode}}' re_chatbot_db_seed 2>/dev/null || echo "1")
        if [ "$SEED_EXIT" = "0" ]; then
            ok "Database seeded successfully"
        else
            warn "Seed container exited with code $SEED_EXIT — check logs:"
            warn "  docker compose logs db_seed"
        fi
        break
    fi
    echo -ne "  Waiting for seed to finish... (${ELAPSED}s / ${MAX_WAIT}s)\r"
    sleep 2
    ELAPSED=$((ELAPSED + 2))
done

# Print seed container logs for confirmation
echo ""
echo -e "  ${CYAN}Seed output:${NC}"
docker compose logs db_seed 2>/dev/null | tail -5 | sed 's/^/    /'
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# 6. Wait for Backend API to respond
# ─────────────────────────────────────────────────────────────────────────────
step "Waiting for Backend API to respond"

MAX_WAIT=90
ELAPSED=0
while [ $ELAPSED -lt $MAX_WAIT ]; do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>/dev/null || echo "000")
    if [ "$HTTP_CODE" = "200" ]; then
        ok "Backend API is responding (HTTP 200)"
        break
    fi
    echo -ne "  Waiting... (${ELAPSED}s / ${MAX_WAIT}s)\r"
    sleep 3
    ELAPSED=$((ELAPSED + 3))
done

if [ "$HTTP_CODE" != "200" ]; then
    warn "Backend did not respond with HTTP 200 within ${MAX_WAIT}s"
    warn "This may be normal if dependencies are still installing."
    warn "Check logs: docker compose logs backend"
fi

# ─────────────────────────────────────────────────────────────────────────────
# 6. Show status & summary
# ─────────────────────────────────────────────────────────────────────────────
step "Container status"
docker compose ps

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}${BOLD}  SETUP COMPLETE!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "  ${BOLD}Frontend${NC}    →  ${CYAN}http://localhost:5173${NC}"
echo -e "  ${BOLD}Backend API${NC} →  ${CYAN}http://localhost:8000${NC}"
echo -e "  ${BOLD}API Docs${NC}    →  ${CYAN}http://localhost:8000/docs${NC}"
echo -e "  ${BOLD}PostgreSQL${NC}  →  ${CYAN}localhost:5432${NC}  (user: ai_property_demo_user)"
echo ""
echo -e "  ${YELLOW}Note:${NC} Make sure LM Studio (or your LLM provider) is running"
echo -e "        on ${BOLD}localhost:1234${NC} for the chat feature to work."
echo ""
echo -e "  ${BOLD}Useful commands:${NC}"
echo -e "    View logs      →  ${CYAN}docker compose logs -f${NC}"
echo -e "    View logs (be) →  ${CYAN}docker compose logs -f backend${NC}"
echo -e "    Stop all       →  ${CYAN}./scripts/stop.sh${NC}  or  ${CYAN}docker compose down${NC}"
echo -e "    Restart        →  ${CYAN}./scripts/run.sh${NC}"
echo ""
