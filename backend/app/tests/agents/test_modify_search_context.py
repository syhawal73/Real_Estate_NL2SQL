"""Tests for MODIFY_SEARCH context replacement via modify_search_context_node.

Validates the core requirements:
  • Only explicitly mentioned fields are replaced.
  • All other fields are preserved unchanged.
  • No duplicate values (no lists, no old_* prefixes).
  • State contains only the latest value for modified slots.
  • Conditional routing sends MODIFY_SEARCH to the dedicated node.
  • No regressions: non-MODIFY_SEARCH actions still go through extract_constraints.

All tests are pure unit tests — no LLM, no database required.
"""

import pytest

from app.agents.free_chat.graph import (
    _route_after_classify_action,
    _route_after_needs_clarification,
    build_graph,
)
from app.agents.free_chat.nodes.modify_search_context import (
    _REPLACEABLE_FIELDS,
    modify_search_context_node,
)
from app.domain.chat.schemas import SearchContext


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
        "radius_km": 10.0,
        "sort_by": "price",
        "sort_order": "asc",
        "limit": 20,
        "last_result_count": 10,
    }
    base.update(overrides)
    return base


# ===================================================================
# 1. Routing: _route_after_classify_action
# ===================================================================

class TestRouteAfterClassifyAction:
    """Verify conditional routing after classify_action."""

    def test_modify_search_routes_to_dedicated_node(self):
        """MODIFY_SEARCH → modify_search_context node."""
        state = {"conversation_action": "modify_search"}
        assert _route_after_classify_action(state) == "modify_search_context"

    def test_refine_search_routes_to_extract_constraints(self):
        """REFINE_SEARCH → extract_constraints (default path)."""
        state = {"conversation_action": "refine_search"}
        assert _route_after_classify_action(state) == "extract_constraints"

    def test_new_search_routes_to_reset_search_context(self):
        """NEW_SEARCH → reset_search_context (dedicated reset node)."""
        state = {"conversation_action": "new_search"}
        assert _route_after_classify_action(state) == "reset_search_context"

    def test_need_clarification_routes_to_extract_constraints(self):
        """NEED_CLARIFICATION → extract_constraints (handles it internally)."""
        state = {"conversation_action": "need_clarification"}
        assert _route_after_classify_action(state) == "extract_constraints"

    def test_general_chat_routes_to_extract_constraints(self):
        """GENERAL_CHAT → extract_constraints."""
        state = {"conversation_action": "general_chat"}
        assert _route_after_classify_action(state) == "extract_constraints"

    def test_missing_action_routes_to_extract_constraints(self):
        """No conversation_action set → extract_constraints."""
        state = {}
        assert _route_after_classify_action(state) == "extract_constraints"


# ===================================================================
# 2. Required scenarios: modify_search_context_node
# ===================================================================

class TestModifySearchContextNode:
    """Core test cases from the requirements."""

    @pytest.mark.asyncio
    async def test_paris_to_berlin(self):
        """Paris → Berlin: only city changes, everything else preserved."""
        state = {
            "user_message": "Switch to Berlin",
            "conversation_action": "modify_search",
            "search_context": _full_context(city="Paris"),
            "constraints": {},
        }
        config = {"configurable": {}}

        result = await modify_search_context_node(state, config)

        ctx = result["search_context"]
        assert ctx["city"] == "Berlin", f"FAIL: expected 'Berlin', got '{ctx['city']}'"
        assert ctx["intent"] == "rent", "FAIL: intent should be preserved"
        assert ctx["property_type"] == "apartment", "FAIL: property_type should be preserved"
        assert ctx["bedrooms"] == 2, "FAIL: bedrooms should be preserved"
        assert ctx["max_price"] == 1500.0, "FAIL: max_price should be preserved"
        assert ctx["radius_km"] == 10.0, "FAIL: radius_km should be preserved"

        # Only city in constraints
        assert result["constraints"] == {"city": "Berlin"}

    @pytest.mark.asyncio
    async def test_rent_to_buy(self):
        """rent → buy: only intent changes, everything else preserved."""
        state = {
            "user_message": "Now I want to buy",
            "conversation_action": "modify_search",
            "search_context": _full_context(intent="rent"),
            "constraints": {},
        }
        config = {"configurable": {}}

        result = await modify_search_context_node(state, config)

        ctx = result["search_context"]
        assert ctx["intent"] == "buy", f"FAIL: expected 'buy', got '{ctx['intent']}'"
        assert ctx["city"] == "Paris", "FAIL: city should be preserved"
        assert ctx["property_type"] == "apartment", "FAIL: property_type should be preserved"
        assert ctx["bedrooms"] == 2, "FAIL: bedrooms should be preserved"

        assert result["constraints"] == {"intent": "buy"}

    @pytest.mark.asyncio
    async def test_apartment_to_house(self):
        """apartment → house: only property_type changes."""
        state = {
            "user_message": "Make it houses",
            "conversation_action": "modify_search",
            "search_context": _full_context(property_type="apartment"),
            "constraints": {},
        }
        config = {"configurable": {}}

        result = await modify_search_context_node(state, config)

        ctx = result["search_context"]
        assert ctx["property_type"] == "house", f"FAIL: expected 'house', got '{ctx['property_type']}'"
        assert ctx["city"] == "Paris", "FAIL: city should be preserved"
        assert ctx["intent"] == "rent", "FAIL: intent should be preserved"
        assert ctx["bedrooms"] == 2, "FAIL: bedrooms should be preserved"
        assert ctx["max_price"] == 1500.0, "FAIL: max_price should be preserved"

        assert result["constraints"] == {"property_type": "house"}

    @pytest.mark.asyncio
    async def test_radius_10_to_15(self):
        """radius 10 → radius 15: only radius_km changes."""
        state = {
            "user_message": "Increase radius to 15km",
            "conversation_action": "modify_search",
            "search_context": _full_context(radius_km=10.0),
            "constraints": {},
        }
        config = {"configurable": {}}

        result = await modify_search_context_node(state, config)

        ctx = result["search_context"]
        assert ctx["radius_km"] == 15.0, f"FAIL: expected 15.0, got {ctx['radius_km']}"
        assert ctx["city"] == "Paris", "FAIL: city should be preserved"
        assert ctx["intent"] == "rent", "FAIL: intent should be preserved"
        assert ctx["property_type"] == "apartment", "FAIL: property_type should be preserved"
        assert ctx["bedrooms"] == 2, "FAIL: bedrooms should be preserved"

        assert result["constraints"] == {"radius_km": 15.0}


# ===================================================================
# 3. No duplicate values / no stale values
# ===================================================================

class TestNoDuplicateValues:
    """Verify that modified fields contain ONLY the latest value."""

    @pytest.mark.asyncio
    async def test_city_is_scalar_not_list(self):
        """City must be a string, never a list like ['Paris', 'Berlin']."""
        state = {
            "user_message": "Switch to Berlin",
            "conversation_action": "modify_search",
            "search_context": _full_context(city="Paris"),
            "constraints": {},
        }
        config = {"configurable": {}}

        result = await modify_search_context_node(state, config)

        city = result["search_context"]["city"]
        assert isinstance(city, str), f"FAIL: city should be str, got {type(city)}"
        assert city == "Berlin"
        assert "Paris" not in str(result["search_context"]).replace("max_price", "")

    @pytest.mark.asyncio
    async def test_no_old_prefix_keys(self):
        """Context must NOT contain old_city, old_intent, etc."""
        state = {
            "user_message": "Switch to Berlin",
            "conversation_action": "modify_search",
            "search_context": _full_context(city="Paris"),
            "constraints": {},
        }
        config = {"configurable": {}}

        result = await modify_search_context_node(state, config)

        ctx = result["search_context"]
        for key in ctx:
            assert not key.startswith("old_"), f"FAIL: found old_* key: {key}"

    @pytest.mark.asyncio
    async def test_intent_is_scalar_not_list(self):
        """Intent must be a string, never ['rent', 'buy']."""
        state = {
            "user_message": "Now I want to buy",
            "conversation_action": "modify_search",
            "search_context": _full_context(intent="rent"),
            "constraints": {},
        }
        config = {"configurable": {}}

        result = await modify_search_context_node(state, config)

        intent = result["search_context"]["intent"]
        assert isinstance(intent, str), f"FAIL: intent should be str, got {type(intent)}"
        assert intent == "buy"


# ===================================================================
# 4. Preservation: unrelated fields remain unchanged
# ===================================================================

class TestFieldPreservation:
    """Verify all non-mentioned fields survive modification."""

    @pytest.mark.asyncio
    async def test_full_context_preserved_on_city_switch(self):
        """Switching city preserves every other field."""
        original = _full_context(
            city="London",
            intent="buy",
            property_type="house",
            bedrooms=3,
            max_price=500000.0,
            radius_km=5.0,
            sort_by="price",
            sort_order="desc",
            limit=10,
        )
        state = {
            "user_message": "Show me Amsterdam",
            "conversation_action": "modify_search",
            "search_context": original,
            "constraints": {},
        }
        config = {"configurable": {}}

        result = await modify_search_context_node(state, config)
        ctx = result["search_context"]

        assert ctx["city"] == "Amsterdam"
        assert ctx["intent"] == "buy"
        assert ctx["property_type"] == "house"
        assert ctx["bedrooms"] == 3
        assert ctx["max_price"] == 500000.0
        assert ctx["radius_km"] == 5.0
        assert ctx["sort_by"] == "price"
        assert ctx["sort_order"] == "desc"
        assert ctx["limit"] == 10

    @pytest.mark.asyncio
    async def test_vague_message_changes_nothing(self):
        """A message with no extractable fields changes nothing."""
        original = _full_context()
        state = {
            "user_message": "Show me more options",
            "conversation_action": "modify_search",
            "search_context": original.copy(),
            "constraints": {},
        }
        config = {"configurable": {}}

        result = await modify_search_context_node(state, config)
        ctx = result["search_context"]

        # Everything stays the same
        assert ctx["city"] == "Paris"
        assert ctx["intent"] == "rent"
        assert ctx["property_type"] == "apartment"
        assert ctx["bedrooms"] == 2
        assert result["constraints"] == {}

    @pytest.mark.asyncio
    async def test_empty_context_still_works(self):
        """Modification works even from an empty starting context."""
        state = {
            "user_message": "Switch to Rome",
            "conversation_action": "modify_search",
            "search_context": {},
            "constraints": {},
        }
        config = {"configurable": {}}

        result = await modify_search_context_node(state, config)

        assert result["search_context"]["city"] == "Rome"
        assert result["constraints"] == {"city": "Rome"}


# ===================================================================
# 5. Multiple fields changed at once
# ===================================================================

class TestMultipleFieldChanges:
    """Verify multi-field updates work correctly."""

    @pytest.mark.asyncio
    async def test_city_and_intent_together(self):
        """'Buy in Berlin' changes both city and intent."""
        state = {
            "user_message": "Buy in Berlin",
            "conversation_action": "modify_search",
            "search_context": _full_context(city="Paris", intent="rent"),
            "constraints": {},
        }
        config = {"configurable": {}}

        result = await modify_search_context_node(state, config)
        ctx = result["search_context"]

        assert ctx["city"] == "Berlin"
        assert ctx["intent"] == "buy"
        assert ctx["property_type"] == "apartment"  # preserved
        assert ctx["bedrooms"] == 2  # preserved

    @pytest.mark.asyncio
    async def test_property_type_and_city(self):
        """'Houses in Berlin' changes both property_type and city."""
        state = {
            "user_message": "Houses in Berlin",
            "conversation_action": "modify_search",
            "search_context": _full_context(city="London", property_type="apartment"),
            "constraints": {},
        }
        config = {"configurable": {}}

        result = await modify_search_context_node(state, config)
        ctx = result["search_context"]

        assert ctx["city"] == "Berlin"
        assert ctx["property_type"] == "house"
        assert ctx["intent"] == "rent"  # preserved


# ===================================================================
# 6. State shape: correct keys returned
# ===================================================================

class TestStateShape:
    """Verify the node returns the correct state keys."""

    @pytest.mark.asyncio
    async def test_returns_constraints_and_search_context(self):
        """Node must return both 'constraints' and 'search_context' keys."""
        state = {
            "user_message": "Switch to Berlin",
            "conversation_action": "modify_search",
            "search_context": _full_context(),
            "constraints": {},
        }
        config = {"configurable": {}}

        result = await modify_search_context_node(state, config)

        assert "constraints" in result
        assert "search_context" in result
        assert isinstance(result["constraints"], dict)
        assert isinstance(result["search_context"], dict)

    @pytest.mark.asyncio
    async def test_no_generated_sql_key(self):
        """Node must NOT return a generated_sql key — no SQL generated."""
        state = {
            "user_message": "Switch to Berlin",
            "conversation_action": "modify_search",
            "search_context": _full_context(),
            "constraints": {},
        }
        config = {"configurable": {}}

        result = await modify_search_context_node(state, config)

        assert "generated_sql" not in result

    @pytest.mark.asyncio
    async def test_search_context_is_serializable(self):
        """search_context must be a plain dict (serializable), not a Pydantic model."""
        state = {
            "user_message": "Switch to Berlin",
            "conversation_action": "modify_search",
            "search_context": _full_context(),
            "constraints": {},
        }
        config = {"configurable": {}}

        result = await modify_search_context_node(state, config)
        ctx = result["search_context"]

        assert isinstance(ctx, dict)
        # Must be reconstructible as SearchContext
        sc = SearchContext(**ctx)
        assert sc.city == "Berlin"


# ===================================================================
# 7. No regressions: non-MODIFY_SEARCH still works
# ===================================================================

class TestNoRegressions:
    """Ensure the graph structure didn't break other action types."""

    def test_graph_compiles(self):
        """The graph must compile without errors."""
        graph = build_graph()
        assert graph is not None

    def test_graph_has_modify_search_context_node(self):
        """The graph must include the new modify_search_context node."""
        graph = build_graph()
        # LangGraph stores nodes; verify the name is in the graph
        assert "modify_search_context" in graph.get_graph().nodes

    def test_routing_after_clarification_unchanged(self):
        """Existing clarification routing must still work."""
        assert _route_after_needs_clarification(
            {"intent": "clarification_needed", "clarification_needed": True}
        ) == "clarify"
        assert _route_after_needs_clarification(
            {"intent": "filter_search", "clarification_needed": False}
        ) == "generate_sql"
        assert _route_after_needs_clarification(
            {"intent": "unsupported", "clarification_needed": False}
        ) == "handle_error"


# ===================================================================
# 8. Replaceable fields allowlist
# ===================================================================

class TestReplaceableFields:
    """Verify the _REPLACEABLE_FIELDS set covers the requirements."""

    def test_required_fields_are_replaceable(self):
        """All fields from the requirements must be in _REPLACEABLE_FIELDS."""
        required = {"city", "intent", "property_type", "bedrooms", "max_price", "radius_km"}
        assert required.issubset(_REPLACEABLE_FIELDS), (
            f"FAIL: missing fields: {required - _REPLACEABLE_FIELDS}"
        )

    def test_last_result_count_not_replaceable(self):
        """Metadata fields like last_result_count should NOT be replaceable."""
        assert "last_result_count" not in _REPLACEABLE_FIELDS
