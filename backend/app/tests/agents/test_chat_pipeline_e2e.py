"""End-to-end tests for the conversational agent through the compiled graph.

These run the real ``free_chat_graph`` against the seeded Postgres test
database (see conftest.py) with a stub LLM, so they exercise the full
deterministic pipeline: intent -> action routing -> extraction -> SQL ->
results -> response. They guard the behaviours that were previously broken:
price / rent-buy filtering, comparison scoping, general-chat routing, and
the clarification gate.
"""

import pytest

from app.agents.free_chat.graph import free_chat_graph
from app.domain.chat.schemas import SessionMemory
from app.infrastructure.llm.base import LLMProvider

pytestmark = pytest.mark.asyncio


class _StubLLM(LLMProvider):
    """The deterministic search path never needs the LLM; general chat does."""

    CANNED = "Happy to help with property questions!"

    async def invoke(self, messages, **kwargs) -> str:
        return self.CANNED

    async def invoke_json(self, messages, **kwargs) -> dict:
        return {}


async def _run(engine, user_message: str, memory: dict | None = None) -> dict:
    state = {
        "session_id": "s", "user_id": "u", "user_message": user_message,
        "memory": memory or SessionMemory().model_dump(),
        "search_context": {}, "active_search": {}, "constraints": {},
        "retry_count": 0, "sql_valid": False, "sql_error": "",
        "properties": [], "result_count": 0, "query_results": [],
    }
    cfg = {"configurable": {"llm": _StubLLM(), "db_engine": engine}}
    return await free_chat_graph.ainvoke(state, config=cfg)


async def test_rent_query_returns_only_rent_rows(db_engine, seed_data):
    r = await _run(db_engine, "apartments for rent in London")
    rows = r["query_results"]
    assert rows, "expected at least one London rental"
    assert all(x["intent"] == "rent" and x["city"] == "London" for x in rows)
    assert "intent = :intent" in r["generated_sql"]


async def test_price_and_type_filters_reach_sql(db_engine, seed_data):
    r = await _run(db_engine, "houses to buy in London under 500k")
    rows = r["query_results"]
    assert rows and all(
        x["intent"] == "buy" and x["property_type"] == "house" and x["price"] <= 500_000
        for x in rows
    )
    assert "price <= :budget" in r["generated_sql"]


async def test_comparison_scoped_to_named_cities(db_engine, seed_data):
    r = await _run(db_engine, "compare London and Paris")
    cities = {row["city"] for row in r["query_results"]}
    assert cities <= {"London", "Paris"} and cities
    assert "city = ANY(:cities)" in r["generated_sql"]


async def test_general_chat_runs_no_sql(db_engine, seed_data):
    r = await _run(db_engine, "what is a mortgage?")
    assert not r.get("generated_sql")
    assert not r.get("properties")
    assert r["assistant_message"] == _StubLLM.CANNED


async def test_vague_request_asks_for_clarification(db_engine, seed_data):
    r = await _run(db_engine, "find me a property")
    assert r["clarification_needed"] is True
    assert r["clarification_question"]


async def test_modify_city_preserves_other_filters(db_engine, seed_data):
    first = await _run(db_engine, "apartments for rent in London")
    second = await _run(db_engine, "switch to Paris", memory=first["memory"])
    rows = second["query_results"]
    assert rows and all(x["city"] == "Paris" and x["intent"] == "rent" for x in rows)
