"""Tests for NEW_SEARCH context reset via reset_search_context_node.

Validates the core requirements:
  • Stale filters (city, intent, property_type, budget, etc.) are cleared.
  • Fresh constraints are extracted from the new message only.
  • Conversation metadata (session_id) is not touched by the node.
  • Conditional routing sends NEW_SEARCH to the dedicated reset node.
  • No regressions: non-NEW_SEARCH actions still route correctly.

All tests are pure unit tests — no LLM, no database required (mock LLM only).
"""

import json

import pytest

from app.agents.free_chat.graph import (
    _route_after_classify_action,
    build_graph,
)
from app.agents.free_chat.nodes.reset_search_context import (
    _SEARCH_FIELDS_TO_CLEAR,
    reset_search_context_node,
)
from app.domain.chat.schemas import SearchContext
from app.infrastructure.llm.base import LLMProvider


# ---------------------------------------------------------------------------
# Mock LLM
# ---------------------------------------------------------------------------

class _LLMForExtraction(LLMProvider):
    """Mock LLM that returns empty extraction (pattern-search messages)."""

    async def invoke(self, messages, **kwargs) -> str:
        return json.dumps({})

    async def invoke_json(self, messages, **kwargs) -> dict:
        return {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _paris_rent_apartment_context() -> dict:
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
        "last_result_count": 10,
    }


def _berlin_buy_house_context() -> dict:
    return {
        "city": "Berlin",
        "intent": "buy",
        "property_type": "house",
        "bedrooms": 4,
        "max_price": 500000.0,
        "radius_km": 5.0,
        "sort_by": "price",
        "sort_order": "desc",
        "limit": 10,
        "last_result_count": 8,
    }


# ===================================================================
# 1. Routing: _route_after_classify_action
# ===================================================================

class TestRouteAfterClassifyAction:
    """Verify NEW_SEARCH routes to the dedicated reset node."""

    def test_new_search_routes_to_reset_search_context(self):
        """NEW_SEARCH → reset_search_context node."""
        state = {"conversation_action": "new_search"}
        assert _route_after_classify_action(state) == "reset_search_context"

    def test_modify_search_still_routes_to_modify_node(self):
        """MODIFY_SEARCH → modify_search_context (unchanged)."""
        state = {"conversation_action": "modify_search"}
        assert _route_after_classify_action(state) == "modify_search_context"

    def test_refine_search_routes_to_extract_constraints(self):
        """REFINE_SEARCH → extract_constraints (default path)."""
        state = {"conversation_action": "refine_search"}
        assert _route_after_classify_action(state) == "extract_constraints"


# ===================================================================
# 2. Required scenarios: reset_search_context_node
# ===================================================================

class TestResetSearchContextNode:
    """Core test cases from the requirements."""

    @pytest.mark.asyncio
    async def test_paris_rent_apartment_then_modern_in_title(self):
        """Paris rent apartment → 'Properties with modern in title'.

        city, intent, and property_type from the prior search must not survive.
        """
        state = {
            "session_id": "session-paris",
            "user_message": "Properties with modern in title",
            "conversation_action": "new_search",
            "search_context": _paris_rent_apartment_context(),
            "constraints": {},
        }
        config = {"configurable": {"llm": _LLMForExtraction()}}

        result = await reset_search_context_node(state, config)
        ctx = result["search_context"]

        assert ctx.get("city") is None, f"FAIL: city should be cleared, got {ctx.get('city')}"
        assert ctx.get("intent") is None, f"FAIL: intent should be cleared, got {ctx.get('intent')}"
        assert ctx.get("property_type") is None, (
            f"FAIL: property_type should be cleared, got {ctx.get('property_type')}"
        )
        assert ctx.get("bedrooms") is None
        assert ctx.get("max_price") is None
        assert ctx.get("radius_km") is None

    @pytest.mark.asyncio
    async def test_berlin_buy_house_then_attractive_in_description(self):
        """Berlin buy house → 'Listings with attractive in description'.

        Entire prior search context must be discarded for a fresh search.
        """
        state = {
            "session_id": "session-berlin",
            "user_message": "Listings with attractive in description",
            "conversation_action": "new_search",
            "search_context": _berlin_buy_house_context(),
            "constraints": {},
        }
        config = {"configurable": {"llm": _LLMForExtraction()}}

        result = await reset_search_context_node(state, config)
        ctx = result["search_context"]

        for field in _SEARCH_FIELDS_TO_CLEAR:
            assert ctx.get(field) is None, (
                f"FAIL: stale filter '{field}' should be cleared, got {ctx.get(field)}"
            )

    @pytest.mark.asyncio
    async def test_session_id_not_in_node_output(self):
        """Node must not overwrite session_id — metadata is preserved upstream."""
        state = {
            "session_id": "keep-this-id",
            "user_message": "Properties with modern in title",
            "conversation_action": "new_search",
            "search_context": _paris_rent_apartment_context(),
            "constraints": {},
        }
        config = {"configurable": {"llm": _LLMForExtraction()}}

        result = await reset_search_context_node(state, config)

        assert "session_id" not in result
        assert "constraints" in result
        assert "search_context" in result


# ===================================================================
# 3. State shape
# ===================================================================

class TestStateShape:
    """Verify the node returns the correct state keys."""

    @pytest.mark.asyncio
    async def test_returns_constraints_and_search_context(self):
        state = {
            "user_message": "Properties with modern in title",
            "conversation_action": "new_search",
            "search_context": _paris_rent_apartment_context(),
            "constraints": {},
        }
        config = {"configurable": {"llm": _LLMForExtraction()}}

        result = await reset_search_context_node(state, config)

        assert isinstance(result["constraints"], dict)
        assert isinstance(result["search_context"], dict)
        SearchContext(**result["search_context"])

    @pytest.mark.asyncio
    async def test_no_generated_sql_key(self):
        state = {
            "user_message": "Properties with modern in title",
            "conversation_action": "new_search",
            "search_context": _paris_rent_apartment_context(),
            "constraints": {},
        }
        config = {"configurable": {"llm": _LLMForExtraction()}}

        result = await reset_search_context_node(state, config)

        assert "generated_sql" not in result


# ===================================================================
# 4. Graph structure
# ===================================================================

class TestNoRegressions:
    """Ensure the graph includes the reset node and still compiles."""

    def test_graph_compiles(self):
        graph = build_graph()
        assert graph is not None

    def test_graph_has_reset_search_context_node(self):
        graph = build_graph()
        assert "reset_search_context" in graph.get_graph().nodes

    def test_graph_has_modify_search_context_node(self):
        graph = build_graph()
        assert "modify_search_context" in graph.get_graph().nodes


# ===================================================================
# 5. Cleared fields allowlist
# ===================================================================

class TestSearchFieldsToClear:
    """Verify the _SEARCH_FIELDS_TO_CLEAR set covers the requirements."""

    def test_required_fields_are_cleared(self):
        required = {
            "city",
            "intent",
            "property_type",
            "bedrooms",
            "max_price",   # budget / price_range
            "radius_km",   # radius / distance
        }
        assert required.issubset(_SEARCH_FIELDS_TO_CLEAR), (
            f"FAIL: missing fields: {required - _SEARCH_FIELDS_TO_CLEAR}"
        )
