"""Unit tests for the needs_clarification node and constraint extraction (Phase 4.1).

These tests do not require a database or running LLM.
"""

import pytest
import pytest_asyncio

from app.agents.free_chat.nodes.needs_clarification import needs_clarification_node
from app.agents.free_chat.nodes.extract_constraints import _regex_extract, _normalize_constraints
from app.domain.chat.schemas import QueryIntent


# ---------------------------------------------------------------------------
# Clarification decision tests
# ---------------------------------------------------------------------------

class TestNeedsClarification:
    """Test the rules-based clarification logic."""

    @pytest.mark.asyncio
    async def test_vague_query_needs_clarification(self):
        """'Find me a property' → should ask for clarification."""
        state = {
            "intent": QueryIntent.CLARIFICATION_NEEDED.value,
            "search_context": {},
            "constraints": {},
        }
        result = await needs_clarification_node(state, {"configurable": {}})
        assert result["clarification_needed"] is True
        assert result["clarification_question"]

    @pytest.mark.asyncio
    async def test_no_city_filter_search(self):
        """Filter search with no city and no other constraints → clarify."""
        state = {
            "intent": QueryIntent.FILTER_SEARCH.value,
            "search_context": {},
            "constraints": {},
        }
        result = await needs_clarification_node(state, {"configurable": {}})
        assert result["clarification_needed"] is True
        assert "city" in result["clarification_question"].lower()

    @pytest.mark.asyncio
    async def test_sufficient_context_proceeds(self):
        """'Show 3-bedroom homes in Paris' → should proceed."""
        state = {
            "intent": QueryIntent.FILTER_SEARCH.value,
            "search_context": {"city": "Paris", "bedrooms": 3, "property_type": "house"},
            "constraints": {"city": "Paris", "bedrooms": 3, "property_type": "house"},
        }
        result = await needs_clarification_node(state, {"configurable": {}})
        assert result["clarification_needed"] is False

    @pytest.mark.asyncio
    async def test_unsupported_does_not_clarify(self):
        """Unsupported intent → goes to handle_error, not clarify."""
        state = {
            "intent": QueryIntent.UNSUPPORTED.value,
            "search_context": {},
            "constraints": {},
        }
        result = await needs_clarification_node(state, {"configurable": {}})
        assert result["clarification_needed"] is False

    @pytest.mark.asyncio
    async def test_count_without_city_proceeds(self):
        """Count queries can proceed without a city."""
        state = {
            "intent": QueryIntent.COUNT.value,
            "search_context": {},
            "constraints": {},
        }
        result = await needs_clarification_node(state, {"configurable": {}})
        assert result["clarification_needed"] is False

    @pytest.mark.asyncio
    async def test_comparison_without_city_proceeds(self):
        """Comparison queries don't require a pre-set city."""
        state = {
            "intent": QueryIntent.COMPARISON.value,
            "search_context": {},
            "constraints": {},
        }
        result = await needs_clarification_node(state, {"configurable": {}})
        assert result["clarification_needed"] is False

    @pytest.mark.asyncio
    async def test_radius_search_without_radius_clarifies(self):
        """Radius search with no radius_km → ask for radius."""
        state = {
            "intent": QueryIntent.RADIUS_SEARCH.value,
            "search_context": {"city": "London"},
            "constraints": {"city": "London"},
        }
        result = await needs_clarification_node(state, {"configurable": {}})
        assert result["clarification_needed"] is True
        assert "km" in result["clarification_question"].lower() or "far" in result["clarification_question"].lower()

    @pytest.mark.asyncio
    async def test_filter_with_constraints_but_no_city_proceeds(self):
        """Filter search with bedrooms but no city → proceed if has constraints."""
        state = {
            "intent": QueryIntent.FILTER_SEARCH.value,
            "search_context": {"bedrooms": 3},
            "constraints": {"bedrooms": 3},
        }
        result = await needs_clarification_node(state, {"configurable": {}})
        # Should proceed because there are meaningful constraints
        assert result["clarification_needed"] is False


# ---------------------------------------------------------------------------
# Regex constraint extraction tests
# ---------------------------------------------------------------------------

class TestRegexExtract:
    def test_city_detection(self):
        assert _regex_extract("Show apartments in Paris")["city"] == "Paris"
        assert _regex_extract("Properties in london")["city"] == "London"
        assert _regex_extract("Berlin houses")["city"] == "Berlin"

    def test_intent_rent(self):
        assert _regex_extract("I want to rent")["intent"] == "rent"

    def test_intent_buy(self):
        assert _regex_extract("Looking to buy a house")["intent"] == "buy"

    def test_property_type_house(self):
        assert _regex_extract("Only houses")["property_type"] == "house"

    def test_property_type_apartment(self):
        assert _regex_extract("Show me apartments")["property_type"] == "apartment"

    def test_bedrooms(self):
        assert _regex_extract("3 bedroom apartments")["bedrooms"] == 3
        assert _regex_extract("2-bed house")["bedrooms"] == 2

    def test_radius(self):
        result = _regex_extract("Within 20km of city centre")
        assert result["radius_km"] == 20.0

    def test_sort_cheapest(self):
        result = _regex_extract("Show cheapest first")
        assert result["sort_by"] == "price"
        assert result["sort_order"] == "asc"

    def test_sort_biggest(self):
        result = _regex_extract("Show biggest properties")
        assert result["sort_by"] == "size_sqm"
        assert result["sort_order"] == "desc"

    def test_limit_extraction(self):
        result = _regex_extract("Show me top 5 properties")
        assert result["limit"] == 5

    def test_complex_query(self):
        result = _regex_extract("3 bedroom houses in Paris under 400k")
        assert result.get("city") == "Paris"
        assert result.get("bedrooms") == 3
        assert result.get("property_type") == "house"

    def test_empty_message(self):
        assert _regex_extract("") == {}

    def test_no_matches(self):
        result = _regex_extract("Hello, how are you?")
        assert len(result) == 0


class TestNormalizeConstraints:
    def test_valid_city(self):
        assert _normalize_constraints({"city": "paris"})["city"] == "Paris"

    def test_invalid_city_rejected(self):
        assert "city" not in _normalize_constraints({"city": "new york"})

    def test_valid_intent(self):
        assert _normalize_constraints({"intent": "rent"})["intent"] == "rent"

    def test_invalid_intent_rejected(self):
        assert "intent" not in _normalize_constraints({"intent": "sell"})

    def test_valid_property_type(self):
        assert _normalize_constraints({"property_type": "house"})["property_type"] == "house"

    def test_invalid_property_type_rejected(self):
        assert "property_type" not in _normalize_constraints({"property_type": "villa"})

    def test_bedrooms_conversion(self):
        assert _normalize_constraints({"bedrooms": "3"})["bedrooms"] == 3

    def test_max_price_conversion(self):
        assert _normalize_constraints({"max_price": "400000"})["max_price"] == 400000.0

    def test_invalid_bedrooms_rejected(self):
        assert "bedrooms" not in _normalize_constraints({"bedrooms": "abc"})
