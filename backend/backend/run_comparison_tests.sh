#!/usr/bin/env bash
#
# run_comparison_tests.sh — verification runner for the COMPARISON query path
# (Sprint 3.x deterministic comparison builder).
#
# WHAT THIS RUNS
# --------------
#   1. The dedicated comparison suite        (app/tests/agents/test_comparison_builder.py)
#   2. The count/aggregation builder suite    (regression — shared query_builders.py)
#   3. The SQL-utility / clarification suites  (regression — routing + validation)
#
# None of the above require a database: the comparison integration tests use a
# city-aware MOCK engine, so they run anywhere.
#
# DATABASE-DEPENDENT TESTS
# ------------------------
# The repository / API / conversation suites (and two pre-existing agent
# integration tests) require a live PostgreSQL instance. They are NOT run by
# the default target. To run the full suite against a real DB, export
# TEST_DATABASE_URL (and DATABASE_URL) first, then pass `--with-db`:
#
#   export DATABASE_URL='postgresql+asyncpg://postgres:postgres@localhost:5432/test_property_db'
#   export TEST_DATABASE_URL="$DATABASE_URL"
#   ./run_comparison_tests.sh --with-db
#
# Usage:
#   ./run_comparison_tests.sh            # comparison + regression (no DB needed)
#   ./run_comparison_tests.sh --with-db  # also run DB-backed suites
#
set -euo pipefail

cd "$(dirname "$0")"

# A dummy DATABASE_URL satisfies app.config.settings import; the no-DB tests
# never actually open a connection.
export DATABASE_URL="${DATABASE_URL:-postgresql+asyncpg://u:p@localhost:5432/db}"

echo "=================================================================="
echo " COMPARISON PATH — comparison suite + regression (no DB required)"
echo "=================================================================="
python -m pytest \
    app/tests/agents/test_comparison_builder.py \
    app/tests/agents/test_count_aggregation_builders.py \
    app/tests/agents/test_sql_utils.py \
    app/tests/agents/test_clarification_gate.py \
    -v

if [[ "${1:-}" == "--with-db" ]]; then
    echo
    echo "=================================================================="
    echo " FULL SUITE (requires live PostgreSQL at TEST_DATABASE_URL)"
    echo "=================================================================="
    : "${TEST_DATABASE_URL:?Set TEST_DATABASE_URL to a live Postgres test DB}"
    python -m pytest app/tests/ -v
fi
