"""Unit tests for SearchContext, SessionMemory, and constraint merging (Phase 4.1).

These tests do not require a database or running LLM.
"""

import pytest

from app.domain.chat.schemas import QueryIntent, SearchContext, SessionMemory


class TestQueryIntent:
    def test_all_values_are_strings(self):
        for intent in QueryIntent:
            assert isinstance(intent.value, str)

    def test_contains_required_intents(self):
        required = {
            "lookup", "listing", "filter_search", "range_search", "count",
            "distinct", "aggregation", "comparison", "ranking",
            "radius_search", "pattern_search", "clarification_needed", "unsupported",
        }
        actual = {e.value for e in QueryIntent}
        assert required == actual

    def test_string_comparison(self):
        assert QueryIntent.FILTER_SEARCH == "filter_search"
        assert QueryIntent.UNSUPPORTED == "unsupported"

    def test_from_value(self):
        assert QueryIntent("filter_search") == QueryIntent.FILTER_SEARCH

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            QueryIntent("not_a_real_intent")


class TestSearchContext:
    def test_default_empty(self):
        ctx = SearchContext()
        assert ctx.city is None
        assert ctx.intent is None
        assert ctx.bedrooms is None
        assert ctx.max_price is None
        assert ctx.property_type is None
        assert ctx.radius_km is None

    def test_to_context_string_empty(self):
        ctx = SearchContext()
        assert ctx.to_context_string() == "none"

    def test_to_context_string_partial(self):
        ctx = SearchContext(city="Paris", bedrooms=3)
        result = ctx.to_context_string()
        assert "city=Paris" in result
        assert "bedrooms=3" in result

    def test_to_context_string_full(self):
        ctx = SearchContext(
            city="London",
            intent="rent",
            property_type="apartment",
            bedrooms=2,
            max_price=1500,
            radius_km=10.0,
        )
        result = ctx.to_context_string()
        assert "city=London" in result
        assert "intent=rent" in result
        assert "type=apartment" in result
        assert "bedrooms=2" in result
        assert "max_price=1500" in result
        assert "radius_km=10.0" in result

    def test_serialization_roundtrip(self):
        ctx = SearchContext(city="Berlin", bedrooms=2, max_price=300000)
        data = ctx.model_dump()
        restored = SearchContext(**data)
        assert restored.city == "Berlin"
        assert restored.bedrooms == 2
        assert restored.max_price == 300000

    def test_merge_new_overrides_old(self):
        ctx = SearchContext(city="Paris", bedrooms=3)
        updated = ctx.merge({"city": "Berlin", "max_price": 400000})
        assert updated.city == "Berlin"
        assert updated.bedrooms == 3  # preserved
        assert updated.max_price == 400000  # new

    def test_merge_none_does_not_override(self):
        ctx = SearchContext(city="Paris", bedrooms=3)
        updated = ctx.merge({"city": None, "max_price": 500000})
        assert updated.city == "Paris"  # None doesn't override
        assert updated.max_price == 500000

    def test_merge_ignores_unknown_fields(self):
        ctx = SearchContext(city="Paris")
        updated = ctx.merge({"unknown_field": "value"})
        assert updated.city == "Paris"

    def test_merge_empty_dict(self):
        ctx = SearchContext(city="Paris", bedrooms=3)
        updated = ctx.merge({})
        assert updated.city == "Paris"
        assert updated.bedrooms == 3


class TestSearchContextFollowUp:
    """Test follow-up conversation patterns."""

    def test_show_cheaper_ones(self):
        """'Show me cheaper ones' → reduce max_price."""
        ctx = SearchContext(city="Paris", max_price=400000, bedrooms=3)
        updated = ctx.merge({"max_price": 300000})
        assert updated.max_price == 300000
        assert updated.city == "Paris"
        assert updated.bedrooms == 3

    def test_only_houses(self):
        """'Only houses' → change property_type."""
        ctx = SearchContext(city="Paris", property_type="apartment")
        updated = ctx.merge({"property_type": "house"})
        assert updated.property_type == "house"
        assert updated.city == "Paris"

    def test_increase_radius(self):
        """'Increase radius to 20km' → update radius."""
        ctx = SearchContext(city="London", radius_km=10.0)
        updated = ctx.merge({"radius_km": 20.0})
        assert updated.radius_km == 20.0
        assert updated.city == "London"

    def test_change_city(self):
        """'What about Paris' → change city."""
        ctx = SearchContext(city="Berlin", bedrooms=2, max_price=1200)
        updated = ctx.merge({"city": "Paris"})
        assert updated.city == "Paris"
        assert updated.bedrooms == 2
        assert updated.max_price == 1200

    def test_add_bedrooms(self):
        """'3 bedrooms' → add bedrooms filter."""
        ctx = SearchContext(city="Paris", property_type="house")
        updated = ctx.merge({"bedrooms": 3})
        assert updated.bedrooms == 3
        assert updated.city == "Paris"
        assert updated.property_type == "house"


class TestSessionMemory:
    def test_default_empty(self):
        mem = SessionMemory()
        assert mem.search_context.city is None
        assert mem.previous_context is None
        assert mem.last_sql is None

    def test_to_context_string_delegates(self):
        mem = SessionMemory(search_context=SearchContext(city="Paris"))
        assert "city=Paris" in mem.to_context_string()

    def test_serialization_roundtrip(self):
        mem = SessionMemory(
            search_context=SearchContext(city="Berlin", bedrooms=2),
            previous_context={"city": "Paris"},
            last_sql="SELECT * FROM properties",
            last_result_count=10,
            last_intent="filter_search",
        )
        data = mem.model_dump()
        restored = SessionMemory(**data)
        assert restored.search_context.city == "Berlin"
        assert restored.previous_context == {"city": "Paris"}
        assert restored.last_sql == "SELECT * FROM properties"

    def test_backward_compatible_flat_memory(self):
        """Old Phase 4 flat memory format should still be usable."""
        from app.agents.free_chat.nodes.load_memory import _parse_memory
        old_format = {
            "city": "London",
            "intent": "rent",
            "bedrooms": 2,
            "max_price": 1500,
            "property_type": "apartment",
        }
        mem = _parse_memory(old_format)
        assert mem.search_context.city == "London"
        assert mem.search_context.intent == "rent"
        assert mem.search_context.bedrooms == 2
