"""Unit and integration tests for NEW_SEARCH handling.

Validates that:
1. Old search filters (city, intent, bedrooms, budget, radius) are cleared
2. New constraints extracted from the message are applied fresh
3. Conversation metadata and session_id are preserved
4. Other conversation actions are not affected

These tests use mock LLMs — no running model or database required.
"""

import json
import logging

import pytest

from app.conversation.action_classifier import ConversationAction
from app.conversation.new_search import apply_new_search
from app.domain.chat.schemas import SearchContext
from app.infrastructure.llm.base import LLMProvider


# ---------------------------------------------------------------------------
# Mock LLM
# ---------------------------------------------------------------------------

class _MockLLM(LLMProvider):
    """Deterministic mock for graph integration tests."""

    def __init__(self, action: str = "new_search") -> None:
        self._action = action

    async def invoke(self, messages, **kwargs) -> str:
        system = messages[0]["content"] if messages else ""

        if "conversation classifier" in system.lower():
            return json.dumps({"action": self._action})
        if "query classifier" in system.lower():
            return json.dumps({"intent": "pattern_search"})
        if "parameter extractor" in system.lower():
            # NEW_SEARCH starts fresh — return empty constraints
            return json.dumps({})
        if "postgresql expert" in system.lower():
            return "SELECT * FROM properties WHERE title ILIKE '%modern%' LIMIT 20"
        return "Here are properties with modern in the title."

    async def invoke_json(self, messages, **kwargs) -> dict:
        raw = await self.invoke(messages, **kwargs)
        return json.loads(raw)


class _LLMForExtraction(LLMProvider):
    """Mock LLM that returns extraction results for new_search tests."""

    def __init__(self, extraction_result: dict | None = None) -> None:
        self._extraction = extraction_result or {}

    async def invoke(self, messages, **kwargs) -> str:
        return json.dumps(self._extraction)

    async def invoke_json(self, messages, **kwargs) -> dict:
        return self._extraction


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rich_context() -> dict:
    """A SearchContext with many active filters to verify they get cleared."""
    return {
        "city": "Paris",
        "intent": "rent",
        "property_type": "apartment",
        "bedrooms": 2,
        "max_price": 1500.0,
        "radius_km": 10.0,
        "sort_by": "price",
        "sort_order": "asc",
        "limit": 20,
        "last_result_count": 15,
    }


# ---------------------------------------------------------------------------
# 1. apply_new_search — unit tests
# ---------------------------------------------------------------------------

class TestApplyNewSearch:
    """Direct unit tests for the NEW_SEARCH handler function."""

    @pytest.mark.asyncio
    async def test_clears_city(self):
        """Old city is not carried over."""
        ctx, _ = await apply_new_search(
            "Properties with modern in title",
            llm=_LLMForExtraction(),
        )
        assert ctx["city"] is None

    @pytest.mark.asyncio
    async def test_clears_intent(self):
        """Old intent is not carried over."""
        ctx, _ = await apply_new_search(
            "Properties with modern in title",
            llm=_LLMForExtraction(),
        )
        assert ctx["intent"] is None

    @pytest.mark.asyncio
    async def test_clears_bedrooms(self):
        """Old bedrooms is not carried over."""
        ctx, _ = await apply_new_search(
            "Properties with modern in title",
            llm=_LLMForExtraction(),
        )
        assert ctx["bedrooms"] is None

    @pytest.mark.asyncio
    async def test_clears_budget(self):
        """Old max_price is not carried over."""
        ctx, _ = await apply_new_search(
            "Properties with modern in title",
            llm=_LLMForExtraction(),
        )
        assert ctx["max_price"] is None

    @pytest.mark.asyncio
    async def test_clears_radius(self):
        """Old radius_km is not carried over."""
        ctx, _ = await apply_new_search(
            "Properties with modern in title",
            llm=_LLMForExtraction(),
        )
        assert ctx["radius_km"] is None

    @pytest.mark.asyncio
    async def test_all_search_fields_cleared(self):
        """Every search-specific field starts as None."""
        ctx, _ = await apply_new_search(
            "Find something new",
            llm=_LLMForExtraction(),
        )
        for field in ("city", "intent", "property_type", "bedrooms",
                       "max_price", "radius_km", "sort_by", "sort_order", "limit"):
            assert ctx[field] is None, f"Expected {field} to be None, got {ctx[field]}"

    @pytest.mark.asyncio
    async def test_extracts_new_constraints_via_regex(self):
        """Explicit fields in the new message ARE picked up."""
        ctx, constraints = await apply_new_search(
            "2 bedroom apartments in Berlin",
            llm=_LLMForExtraction(),
        )
        assert ctx["city"] == "Berlin"
        assert ctx["property_type"] == "apartment"
        assert ctx["bedrooms"] == 2
        assert "city" in constraints
        assert "bedrooms" in constraints

    @pytest.mark.asyncio
    async def test_extracts_via_llm_fallback(self):
        """When regex finds little, the LLM fallback is used."""
        # A vague message → regex extracts nothing → LLM fills in
        llm = _LLMForExtraction({"city": "Rome", "intent": "buy"})
        ctx, constraints = await apply_new_search(
            "Show me places to purchase in the Italian capital",
            llm=llm,
        )
        # LLM returned city=Rome, intent=buy
        assert ctx["city"] == "Rome"
        assert ctx["intent"] == "buy"

    @pytest.mark.asyncio
    async def test_old_context_is_irrelevant(self):
        """Even though _rich_context exists, apply_new_search ignores it
        because it doesn't receive it — the node discards it."""
        old = _rich_context()  # noqa: F841 — just proving the point
        ctx, _ = await apply_new_search(
            "Properties with modern in title",
            llm=_LLMForExtraction(),
        )
        # None of the old context leaks through
        assert ctx["city"] is None
        assert ctx["intent"] is None
        assert ctx["bedrooms"] is None
        assert ctx["max_price"] is None


# ---------------------------------------------------------------------------
# 2. Integration tests: NEW_SEARCH in the full graph
# ---------------------------------------------------------------------------

class TestNewSearchInGraph:
    """Integration tests: the graph correctly clears context for NEW_SEARCH."""

    @pytest.mark.asyncio
    async def test_old_filters_not_applied(self):
        """A NEW_SEARCH with rich prior context produces a clean SearchContext."""
        from app.agents.free_chat.graph import build_graph

        graph = build_graph()
        config = {"configurable": {"llm": _MockLLM("new_search"), "db_engine": None}}

        state = {
            "session_id": "test-new-search",
            "user_message": "Properties with modern in title",
            "memory": {"search_context": _rich_context()},
            "search_context": {},
            "constraints": {},
            "retry_count": 0,
            "sql_valid": False,
            "sql_error": "",
            "properties": [],
            "result_count": 0,
            "query_results": [],
        }

        result = await graph.ainvoke(state, config=config)

        assert result["conversation_action"] == "new_search"
        ctx = result["search_context"]

        # Old filters must NOT be carried over
        assert ctx.get("city") is None, f"city should be cleared, got {ctx.get('city')}"
        assert ctx.get("intent") is None
        assert ctx.get("bedrooms") is None
        assert ctx.get("max_price") is None
        assert ctx.get("radius_km") is None

    @pytest.mark.asyncio
    async def test_session_id_preserved(self):
        """Session ID must survive a NEW_SEARCH."""
        from app.agents.free_chat.graph import build_graph

        graph = build_graph()
        config = {"configurable": {"llm": _MockLLM("new_search"), "db_engine": None}}

        state = {
            "session_id": "keep-this-id",
            "user_message": "Properties with garden",
            "memory": {"search_context": _rich_context()},
            "search_context": {},
            "constraints": {},
            "retry_count": 0,
            "sql_valid": False,
            "sql_error": "",
            "properties": [],
            "result_count": 0,
            "query_results": [],
        }

        result = await graph.ainvoke(state, config=config)
        assert result["session_id"] == "keep-this-id"

    @pytest.mark.asyncio
    async def test_new_search_extracts_fresh_constraints(self):
        """New constraints from the message should be present in the
        fresh context."""
        from app.agents.free_chat.graph import build_graph

        # This LLM returns new_search action AND recognises "Berlin"
        class _BerlinLLM(_MockLLM):
            async def invoke(self, messages, **kwargs) -> str:
                system = messages[0]["content"] if messages else ""
                if "parameter extractor" in system.lower():
                    return json.dumps({"city": "Berlin"})
                return await super().invoke(messages, **kwargs)

        graph = build_graph()
        config = {"configurable": {"llm": _BerlinLLM("new_search"), "db_engine": None}}

        state = {
            "session_id": "test",
            "user_message": "Apartments in Berlin",
            "memory": {"search_context": {"city": "Paris", "intent": "rent"}},
            "search_context": {},
            "constraints": {},
            "retry_count": 0,
            "sql_valid": False,
            "sql_error": "",
            "properties": [],
            "result_count": 0,
            "query_results": [],
        }

        result = await graph.ainvoke(state, config=config)
        ctx = result["search_context"]

        # Fresh constraint from the new message
        assert ctx["city"] == "Berlin"
        assert ctx["property_type"] == "apartment"
        # Old intent=rent should NOT carry over
        assert ctx.get("intent") is None

    @pytest.mark.asyncio
    async def test_non_new_search_preserves_context(self):
        """REFINE_SEARCH should still carry over existing context
        (regression guard)."""
        from app.agents.free_chat.graph import build_graph

        graph = build_graph()
        config = {"configurable": {"llm": _MockLLM("refine_search"), "db_engine": None}}

        state = {
            "session_id": "test",
            "user_message": "Only houses",
            "memory": {"search_context": {"city": "Paris", "intent": "rent"}},
            "search_context": {},
            "constraints": {},
            "retry_count": 0,
            "sql_valid": False,
            "sql_error": "",
            "properties": [],
            "result_count": 0,
            "query_results": [],
        }

        result = await graph.ainvoke(state, config=config)
        ctx = result["search_context"]

        # Existing context preserved under REFINE_SEARCH
        assert ctx["city"] == "Paris"
        assert ctx["intent"] == "rent"


# ---------------------------------------------------------------------------
# 3. Logging
# ---------------------------------------------------------------------------

class TestNewSearchLogging:
    """Verify the NEW_SEARCH handler produces log output."""

    @pytest.mark.asyncio
    async def test_log_records_new_search(self, caplog):
        with caplog.at_level(logging.INFO, logger="app.conversation.new_search"):
            await apply_new_search(
                "Properties with modern in title",
                llm=_LLMForExtraction(),
            )

        new_search_logs = [
            r for r in caplog.records
            if "new_search" in r.message
        ]
        assert len(new_search_logs) >= 1
        assert "cleared_context" in new_search_logs[0].message
