"""Unit and integration tests for MODIFY_SEARCH handling.

Validates that:
1. City replacement works — only city changes, rest preserved
2. Intent replacement works — only intent changes, rest preserved
3. Multiple explicit fields can change at once
4. Non-MODIFY_SEARCH actions are not affected
5. No regressions on the existing extraction pipeline

These tests use mock LLMs — no running model or database required.
"""

import json
import logging

import pytest

from app.conversation.action_classifier import ConversationAction
from app.conversation.modify_search import apply_modify_search
from app.domain.chat.schemas import SearchContext
from app.infrastructure.llm.base import LLMProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _full_context(**overrides) -> dict:
    """Build a realistic SearchContext dict with sensible defaults."""
    base = {
        "city": "Paris",
        "intent": "rent",
        "property_type": "apartment",
        "bedrooms": 2,
        "max_price": 1500.0,
        "radius_km": None,
        "sort_by": None,
        "sort_order": None,
        "limit": None,
        "last_result_count": 10,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# 1. apply_modify_search — unit tests
# ---------------------------------------------------------------------------

class TestApplyModifySearch:
    """Direct unit tests for the MODIFY_SEARCH handler function."""

    def test_city_replacement(self):
        """'Switch to Berlin' updates only city, everything else preserved."""
        ctx, constraints = apply_modify_search(
            "Switch to Berlin",
            _full_context(city="Paris"),
        )

        assert ctx["city"] == "Berlin"
        assert constraints == {"city": "Berlin"}
        # Preserved fields
        assert ctx["intent"] == "rent"
        assert ctx["property_type"] == "apartment"
        assert ctx["bedrooms"] == 2
        assert ctx["max_price"] == 1500.0

    def test_intent_replacement_buy(self):
        """'Now I want to buy' updates only intent."""
        ctx, constraints = apply_modify_search(
            "Now I want to buy",
            _full_context(intent="rent"),
        )

        assert ctx["intent"] == "buy"
        assert constraints == {"intent": "buy"}
        # Preserved fields
        assert ctx["city"] == "Paris"
        assert ctx["property_type"] == "apartment"
        assert ctx["bedrooms"] == 2

    def test_intent_replacement_rent(self):
        """'I want to rent instead' updates only intent."""
        ctx, constraints = apply_modify_search(
            "I want to rent instead",
            _full_context(intent="buy"),
        )

        assert ctx["intent"] == "rent"
        assert constraints == {"intent": "rent"}
        assert ctx["city"] == "Paris"

    def test_city_and_intent_together(self):
        """'Buy in Berlin' updates both city and intent."""
        ctx, constraints = apply_modify_search(
            "Buy in Berlin",
            _full_context(city="Paris", intent="rent"),
        )

        assert ctx["city"] == "Berlin"
        assert ctx["intent"] == "buy"
        assert constraints == {"city": "Berlin", "intent": "buy"}
        # Preserved
        assert ctx["property_type"] == "apartment"
        assert ctx["bedrooms"] == 2

    def test_preserves_all_fields_when_switching_city(self):
        """All non-mentioned fields survive a city switch."""
        original = _full_context(
            city="London",
            intent="buy",
            property_type="house",
            bedrooms=3,
            max_price=500000.0,
        )
        ctx, _ = apply_modify_search("Show me Amsterdam", original)

        assert ctx["city"] == "Amsterdam"
        assert ctx["intent"] == "buy"
        assert ctx["property_type"] == "house"
        assert ctx["bedrooms"] == 3
        assert ctx["max_price"] == 500000.0

    def test_no_explicit_fields_changes_nothing(self):
        """A vague message extracts nothing — context unchanged."""
        original = _full_context()
        ctx, constraints = apply_modify_search("Show me options", original)

        assert constraints == {}
        assert ctx["city"] == "Paris"
        assert ctx["intent"] == "rent"

    def test_empty_context(self):
        """Works even when starting from an empty context."""
        ctx, constraints = apply_modify_search("Switch to Rome", {})

        assert ctx["city"] == "Rome"
        assert constraints == {"city": "Rome"}

    def test_property_type_change_with_city(self):
        """'Houses in Berlin' changes both property_type and city."""
        ctx, constraints = apply_modify_search(
            "Houses in Berlin",
            _full_context(city="London", property_type="apartment"),
        )

        assert ctx["city"] == "Berlin"
        assert ctx["property_type"] == "house"
        assert ctx["intent"] == "rent"  # preserved

    def test_bedrooms_change(self):
        """'3 bedrooms' updates bedrooms only."""
        ctx, constraints = apply_modify_search(
            "3 bedrooms",
            _full_context(bedrooms=2),
        )

        assert ctx["bedrooms"] == 3
        assert constraints == {"bedrooms": 3}
        assert ctx["city"] == "Paris"  # preserved


# ---------------------------------------------------------------------------
# 2. Integration test: MODIFY_SEARCH in the full graph
# ---------------------------------------------------------------------------

class _MockLLM(LLMProvider):
    """Mock LLM for graph integration tests."""

    def __init__(self, action: str = "modify_search") -> None:
        self._action = action

    async def invoke(self, messages, **kwargs) -> str:
        system = messages[0]["content"] if messages else ""

        if "conversation classifier" in system.lower():
            return json.dumps({"action": self._action})
        if "query classifier" in system.lower():
            return json.dumps({"intent": "filter_search"})
        if "parameter extractor" in system.lower():
            return json.dumps({"city": "Berlin"})
        if "postgresql expert" in system.lower():
            return "SELECT * FROM properties WHERE city = 'Berlin' LIMIT 5"
        return "Here are some properties."

    async def invoke_json(self, messages, **kwargs) -> dict:
        raw = await self.invoke(messages, **kwargs)
        return json.loads(raw)


class TestModifySearchInGraph:
    """Integration tests: MODIFY_SEARCH flows through the graph correctly."""

    @pytest.mark.asyncio
    async def test_city_switch_in_graph(self):
        """'Switch to Berlin' with existing Paris context → city=Berlin."""
        from app.agents.free_chat.graph import build_graph

        graph = build_graph()
        config = {"configurable": {"llm": _MockLLM("modify_search"), "db_engine": None}}

        state = {
            "session_id": "test",
            "user_message": "Switch to Berlin",
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

        assert result["conversation_action"] == "modify_search"
        ctx = result["search_context"]
        assert ctx["city"] == "Berlin"
        assert ctx["intent"] == "rent"  # preserved from memory

    @pytest.mark.asyncio
    async def test_intent_switch_in_graph(self):
        """'Now I want to buy' with existing rent context → intent=buy."""
        from app.agents.free_chat.graph import build_graph

        graph = build_graph()
        config = {"configurable": {"llm": _MockLLM("modify_search"), "db_engine": None}}

        state = {
            "session_id": "test",
            "user_message": "Now I want to buy",
            "memory": {"search_context": {"city": "London", "intent": "rent"}},
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
        assert ctx["intent"] == "buy"
        assert ctx["city"] == "London"  # preserved

    @pytest.mark.asyncio
    async def test_non_modify_search_uses_llm_fallback(self):
        """When action is NOT modify_search, the LLM fallback is still used."""
        from app.agents.free_chat.graph import build_graph

        graph = build_graph()
        # Action = refine_search → normal extraction path (LLM may be called)
        config = {"configurable": {"llm": _MockLLM("refine_search"), "db_engine": None}}

        state = {
            "session_id": "test",
            "user_message": "Something vague",
            "memory": {},
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

        # Should still complete — the LLM fallback path was exercised
        assert result["conversation_action"] == "refine_search"
        assert result.get("assistant_message")


# ---------------------------------------------------------------------------
# 3. Logging
# ---------------------------------------------------------------------------

class TestModifySearchLogging:
    """Verify the MODIFY_SEARCH handler produces log output."""

    def test_log_records_changed_fields(self, caplog):
        with caplog.at_level(logging.INFO, logger="app.conversation.modify_search"):
            apply_modify_search("Switch to Berlin", _full_context(city="Paris"))

        modify_logs = [
            r for r in caplog.records
            if "modify_search" in r.message
        ]
        assert len(modify_logs) >= 1
        log_msg = modify_logs[0].message
        assert "city" in log_msg
