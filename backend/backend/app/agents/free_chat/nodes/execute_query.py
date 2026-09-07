"""Deterministic database execution plus intelligent zero-result fallback."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from langchain_core.runnables import RunnableConfig
from app.agents.free_chat.state import AgentState
from app.agents.free_chat.utils import rows_to_dicts
from app.agents.free_chat.deterministic_builder import build_sql

_MAX_ROWS = 50


async def _run(engine: AsyncEngine, sql: str, params: dict) -> list[dict]:
    async with engine.connect() as conn:
        result = await conn.execute(text(sql), params)
        keys = list(result.keys())
        return rows_to_dicts(result.fetchmany(_MAX_ROWS), keys)


async def execute_query_node(state: AgentState, config: RunnableConfig) -> dict:
    engine: AsyncEngine = config["configurable"]["db_engine"]
    plan = state.get("query_plan", {})
    context = dict(state.get("search_context") or {})
    try:
        sql, params = build_sql(plan, context)
        data = await _run(engine, sql, params)
        result = {
            "query_results": data,
            "result_count": len(data),
            "sql_error": "",
            "generated_sql": sql,
            "fallback_applied": False,
            "fallback_message": "",
        }
        if data or plan.get("query_type") in {"count", "aggregation", "comparison"}:
            return result

        # Intelligent fallback: preserve city/transaction type, relax one
        # constraint at a time. This never invents properties or changes the
        # user's search silently; the response explicitly reports the fallback.
        fallback_candidates = []
        for label, field in [
            ("a wider radius", "radius_km"),
            ("a slightly higher budget", "budget"),
            ("a slightly lower minimum budget", "min_budget"),
            ("one fewer bedroom", "bedrooms"),
            ("more flexible property type", "property_type"),
        ]:
            if context.get(field) is None:
                continue
            relaxed = dict(context)
            if field == "radius_km":
                relaxed[field] = float(context[field]) * 1.5
            elif field == "budget":
                relaxed[field] = float(context[field]) * 1.2
            elif field == "min_budget":
                relaxed[field] = float(context[field]) * 0.8
            elif field == "bedrooms":
                if int(context[field]) <= 1:
                    continue
                relaxed[field] = int(context[field]) - 1
            elif field == "property_type":
                relaxed[field] = None
            try:
                fsql, fparams = build_sql(plan, relaxed)
                fdata = await _run(engine, fsql, fparams)
                if fdata:
                    fallback_candidates.append((label, fsql, fdata, relaxed))
                    break
            except Exception:
                continue

        if fallback_candidates:
            label, fsql, fdata, relaxed = fallback_candidates[0]
            return {
                "query_results": fdata,
                "result_count": len(fdata),
                "sql_error": "",
                "generated_sql": fsql,
                "fallback_applied": True,
                "fallback_message": f"No exact matches were found, so I widened the search using {label}.",
                "search_context": relaxed,
            }
        return result
    except Exception as exc:
        return {"query_results": [], "result_count": 0, "sql_error": f"Database execution error: {exc}", "fallback_applied": False, "fallback_message": ""}
