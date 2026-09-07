#!/usr/bin/env python
"""verify_comparison_end_to_end.py — real-database smoke test for COMPARISON.

The comparison integration tests in the pytest suite use a MOCK engine and
need no database. This script is the optional counterpart that exercises the
exact same graph path against a REAL, seeded PostgreSQL instance, so you can
confirm the two per-city queries execute and compare correctly end to end.

PREREQUISITES
-------------
A PostgreSQL database reachable via DATABASE_URL, with the `properties` table
populated for at least two supported cities (London, Paris, Berlin, Amsterdam,
Rome). The schema matches app/domain/property/models.py.

USAGE
-----
    export DATABASE_URL='postgresql+asyncpg://postgres:postgres@localhost:5432/property_db'
    python verify_comparison_end_to_end.py

The script does NOT modify any data — it only issues read-only SELECT/COUNT
queries through the deterministic comparison builder.

It bypasses the LLM by invoking the comparison node directly with a fixed
COMPARISON intent, so no model server is required.
"""

from __future__ import annotations

import asyncio
import os
import sys

from sqlalchemy.ext.asyncio import create_async_engine

from app.agents.free_chat.nodes.build_comparison import build_comparison_query_node

# The six representative prompts (mirrors the required test cases).
PROMPTS = [
    "Compare average sale prices in London vs Berlin",
    "Which city has more rental apartments, Paris or Amsterdam?",
    "Compare the cheapest apartments in Rome and Paris",
    "Compare houses in Berlin vs London by average price",
    "Are houses in Berlin or London more expensive on average?",
    "Compare average prices in Rome and Paris",
]


async def _run_one(engine, prompt: str) -> dict:
    state = {"user_message": prompt, "session_id": "verify", "retry_count": 0}
    config = {"configurable": {"db_engine": engine}}
    return await build_comparison_query_node(state, config)


async def main() -> int:
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("ERROR: set DATABASE_URL to a live PostgreSQL instance first.")
        return 2

    engine = create_async_engine(db_url, echo=False)
    failures = 0
    try:
        for prompt in PROMPTS:
            out = await _run_one(engine, prompt)
            msg = out.get("assistant_message", "")
            sql = out.get("generated_sql", "")

            ok = bool(msg) and "wasn't able to complete" not in msg.lower()
            # Comparison answers must be numeric and SQL-free.
            ok = ok and "SELECT" not in msg.upper()
            ok = ok and "latitude" not in sql.lower() and "longitude" not in sql.lower()

            status = "PASS" if ok else "FAIL"
            if not ok:
                failures += 1
            print(f"[{status}] {prompt}")
            print(f"        → {msg}")
    finally:
        await engine.dispose()

    print()
    print(f"{len(PROMPTS) - failures}/{len(PROMPTS)} prompts produced a clean comparison answer.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
