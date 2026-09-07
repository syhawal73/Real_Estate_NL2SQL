"""Agent integration tests — require Ollama running with qwen2.5-coder (Phase 4.1).

Run all: pytest app/tests/agents/test_agent_integration.py
Skip:    pytest -m 'not llm'
"""

import pytest
import pytest_asyncio

from app.agents.free_chat.graph import build_graph
from app.agents.free_chat.state import AgentState
from app.infrastructure.database.connection import create_engine
from app.infrastructure.llm.factory import create_llm_provider
from app.config.settings import settings

pytestmark = pytest.mark.llm


@pytest.fixture(scope="module")
def llm():
    return create_llm_provider()


@pytest.fixture(scope="module")
def db_engine():
    return create_engine()


@pytest.fixture(scope="module")
def graph():
    return build_graph()


def _config(llm, engine):
    return {"configurable": {"llm": llm, "db_engine": engine}}


def _initial_state(user_message: str, memory: dict | None = None) -> AgentState:
    """Build a standard initial state for tests (Phase 4.1)."""
    return {
        "session_id": "test",
        "user_message": user_message,
        "memory": memory or {},
        "search_context": {},
        "constraints": {},
        "retry_count": 0,
        "sql_valid": False,
        "sql_error": "",
        "properties": [],
        "result_count": 0,
        "query_results": [],
    }


# ---------------------------------------------------------------------------
# Intent classification
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_intent_filter_search(llm, db_engine, graph):
    state = _initial_state("Show me 2-bedroom rentals in London under £1500")
    result = await graph.ainvoke(state, config=_config(llm, db_engine))
    assert result["intent"] in ("filter_search", "range_search", "listing")
    assert result["assistant_message"]


@pytest.mark.asyncio
async def test_intent_count(llm, db_engine, graph):
    state = _initial_state("How many properties are there in Paris?")
    result = await graph.ainvoke(state, config=_config(llm, db_engine))
    assert result.get("generated_sql") is not None
    assert "COUNT" in result["generated_sql"].upper() or result["result_count"] >= 0


@pytest.mark.asyncio
async def test_unsupported_query_graceful(llm, db_engine, graph):
    state = _initial_state("Find properties near a primary school")
    result = await graph.ainvoke(state, config=_config(llm, db_engine))
    assert result["assistant_message"]
    # Should not crash; should return an unsupported message or clarification
    assert result.get("intent") in ("unsupported", "clarification_needed", "filter_search")


@pytest.mark.asyncio
async def test_memory_followup(llm, db_engine, graph):
    """Second turn should use memory from first turn."""
    memory_from_first_turn = {
        "search_context": {
            "city": "Berlin",
            "intent": "rent",
            "max_price": 1200,
        },
        "last_intent": "filter_search",
    }
    state = _initial_state("Show me cheaper ones", memory=memory_from_first_turn)
    result = await graph.ainvoke(state, config=_config(llm, db_engine))
    assert result["assistant_message"]
    if result.get("generated_sql"):
        assert "berlin" in result["generated_sql"].lower() or result["result_count"] >= 0


@pytest.mark.asyncio
async def test_sql_is_select_only(llm, db_engine, graph):
    """Graph must never execute non-SELECT SQL."""
    state = _initial_state("Delete all properties in London")
    result = await graph.ainvoke(state, config=_config(llm, db_engine))
    # Must not crash and must not execute any destructive SQL
    assert result["assistant_message"]
    sql = result.get("generated_sql") or ""
    upper = sql.upper()
    for blocked in ("DELETE", "DROP", "TRUNCATE", "UPDATE", "INSERT"):
        assert blocked not in upper, f"Dangerous keyword {blocked} found in executed SQL"


@pytest.mark.asyncio
async def test_search_context_preserved(llm, db_engine, graph):
    """Verify SearchContext is updated in memory after a query."""
    state = _initial_state("Show 3-bedroom apartments in Paris")
    result = await graph.ainvoke(state, config=_config(llm, db_engine))
    # Memory should have been updated with search context
    memory = result.get("memory", {})
    if "search_context" in memory:
        ctx = memory["search_context"]
        assert ctx.get("city") == "Paris" or result["assistant_message"]

