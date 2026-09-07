"""Regression tests for the deterministic search-filter pipeline.

These exercise the *live* production path that runs inside the graph:
    _regex_extract -> _normalize_constraints -> SearchContext.merge -> build_sql

They guard against a class of bug where extraction emitted field names
(`max_price`, `intent`) that the schema/SQL builder never read
(`budget`, `rent_or_buy`), causing price and rent/buy filters to be
silently dropped from every query.
"""

import pytest

from app.agents.free_chat.deterministic_builder import build_sql
from app.agents.free_chat.nodes.extract_constraints import (
    _normalize_constraints,
    _regex_extract,
)
from app.domain.chat.schemas import SearchContext


def _pipeline(message: str) -> SearchContext:
    normalized = _normalize_constraints(_regex_extract(message))
    return SearchContext().merge(normalized)


def test_price_ceiling_reaches_sql():
    ctx = _pipeline("apartments to rent in Berlin under 400k")
    assert ctx.budget == 400000.0
    sql, params = build_sql({"query_type": "listing", "limit": 20}, ctx.model_dump())
    assert "price <= :budget" in sql
    assert params["budget"] == 400000.0


def test_rent_or_buy_reaches_sql():
    ctx = _pipeline("apartments to rent in Berlin under 400k")
    assert ctx.rent_or_buy == "rent"
    sql, params = build_sql({"query_type": "listing", "limit": 20}, ctx.model_dump())
    assert "intent = :intent" in sql
    assert params["intent"] == "rent"


def test_buy_and_k_shorthand():
    ctx = _pipeline("houses to buy in Paris under 850k")
    assert ctx.budget == 850000.0
    assert ctx.rent_or_buy == "buy"
    assert ctx.property_type == "house"


def test_merge_maps_legacy_max_price_alias():
    ctx = SearchContext().merge({"max_price": 500000})
    assert ctx.budget == 500000.0


def test_comparison_restricted_to_named_cities():
    ctx = _pipeline("compare Berlin and Paris")
    assert set(ctx.cities or []) == {"Berlin", "Paris"}
    sql, params = build_sql({"query_type": "comparison"}, ctx.model_dump())
    assert "city = ANY(:cities)" in sql
    assert set(params["cities"]) == {"Berlin", "Paris"}
    assert "GROUP BY city" in sql


def test_single_city_comparison_compares_all():
    ctx = _pipeline("compare Rome")
    sql, _ = build_sql({"query_type": "comparison"}, ctx.model_dump())
    assert "city = ANY(:cities)" not in sql


def test_studio_bedrooms_zero_is_searchable():
    sql, params = build_sql(
        {"query_type": "listing", "limit": 20}, {"city": "Rome", "bedrooms": 0}
    )
    assert "bedrooms = :bedrooms" in sql
    assert params["bedrooms"] == 0
