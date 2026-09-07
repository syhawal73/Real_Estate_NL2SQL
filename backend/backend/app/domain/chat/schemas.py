"""Pydantic schemas for the real-estate conversational assistant."""

import uuid as _uuid
from datetime import datetime
from enum import Enum
from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class QueryIntent(str, Enum):
    LOOKUP = "lookup"
    LISTING = "listing"
    FILTER_SEARCH = "filter_search"
    RANGE_SEARCH = "range_search"
    COUNT = "count"
    DISTINCT = "distinct"
    AGGREGATION = "aggregation"
    COMPARISON = "comparison"
    RANKING = "ranking"
    RADIUS_SEARCH = "radius_search"
    PATTERN_SEARCH = "pattern_search"
    CLARIFICATION_NEEDED = "clarification_needed"
    UNSUPPORTED = "unsupported"


class ChatRequest(BaseModel):
    session_id: str | None = None
    user_id: str | None = Field(default=None, min_length=1, max_length=128)
    message: str = Field(..., min_length=1, max_length=2000)


class SearchContext(BaseModel):
    intent: str | None = None
    city: str | None = None
    neighbourhood: str | None = None
    property_type: str | None = None
    bedrooms: int | None = None
    bathrooms: int | None = None
    budget: float | None = Field(default=None, validation_alias=AliasChoices("budget", "max_price"))
    min_budget: float | None = None
    rent_or_buy: str | None = None
    ranking_type: str | None = None
    radius_km: float | None = None
    search_term: str | None = None
    aggregation: str | None = None
    limit: int | None = None
    sort_by: str | None = None
    sort_order: str | None = None
    # Cities explicitly named for a comparison ("compare Berlin and Paris").
    cities: list[str] | None = None

    @property
    def max_price(self) -> float | None:
        """Backward-compatible read alias for the old search state name."""
        return self.budget

    def to_context_string(self) -> str:
        parts = []
        for key, label in (("city", "city"), ("rent_or_buy", "rent_or_buy"), ("property_type", "type"),
                           ("bedrooms", "bedrooms"), ("bathrooms", "bathrooms"), ("min_budget", "min_budget"),
                           ("budget", "max_budget"), ("radius_km", "radius_km"), ("neighbourhood", "neighbourhood"),
                           ("ranking_type", "ranking_type"), ("search_term", "search_term"), ("aggregation", "aggregation")):
            value = getattr(self, key)
            if value is not None:
                parts.append(f"{label}={value}")
        return ", ".join(parts) if parts else "none"

    # Extractors have historically emitted alternate names for the same
    # search-state field. Map those aliases onto the canonical field names so
    # a constraint is never silently dropped when merged into the context.
    _MERGE_ALIASES = {"max_price": "budget"}

    def merge(self, new_constraints: dict) -> "SearchContext":
        import logging

        data = self.model_dump()
        for raw_key, value in new_constraints.items():
            if value is None:
                continue
            key = self._MERGE_ALIASES.get(raw_key, raw_key)
            if key in data:
                data[key] = value
            else:
                logging.getLogger(__name__).warning(
                    "SearchContext.merge: dropping unrecognised constraint %r", raw_key
                )
        return SearchContext(**data)


class ActiveSearchSession(BaseModel):
    search_id: str = Field(default_factory=lambda: str(_uuid.uuid4()))
    intent: str | None = None
    city: str | None = None
    neighbourhood: str | None = None
    property_type: str | None = None
    bedrooms: int | None = None
    bathrooms: int | None = None
    budget: float | None = Field(default=None, validation_alias=AliasChoices("budget", "max_price"))
    min_budget: float | None = None
    rent_or_buy: str | None = None
    ranking_type: str | None = None
    radius_km: float | None = None
    search_term: str | None = None
    aggregation: str | None = None
    limit: int | None = None
    sort_by: str | None = None
    sort_order: str | None = None
    cities: list[str] | None = None

    @classmethod
    def from_search_context(cls, ctx: SearchContext, search_id: str | None = None) -> "ActiveSearchSession":
        return cls(
            search_id=search_id or str(_uuid.uuid4()),
            intent=ctx.intent, city=ctx.city, neighbourhood=ctx.neighbourhood,
            property_type=ctx.property_type, bedrooms=ctx.bedrooms, bathrooms=ctx.bathrooms,
            budget=ctx.budget, min_budget=ctx.min_budget, rent_or_buy=ctx.rent_or_buy,
            ranking_type=ctx.ranking_type, radius_km=ctx.radius_km, search_term=ctx.search_term,
            aggregation=ctx.aggregation, limit=ctx.limit, sort_by=ctx.sort_by, sort_order=ctx.sort_order,
            cities=ctx.cities,
        )


class SessionMemory(BaseModel):
    search_context: SearchContext = Field(default_factory=SearchContext)
    previous_context: dict | None = None
    active_search: dict | None = None
    last_sql: str | None = None
    last_result_count: int | None = None
    last_intent: str | None = None

    def to_context_string(self) -> str:
        return self.search_context.to_context_string()


class PropertyResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    city: str
    neighbourhood: str
    intent: str
    price: int
    bedrooms: int
    bathrooms: int
    size_sqm: int
    property_type: str
    distance_from_city_km: float
    description: str = ""
    property_url: str
    currency: str = "USD"


class ChatResponse(BaseModel):
    session_id: str
    user_message: str
    assistant_message: str
    intent: str | None = None
    generated_sql: str | None = None
    properties: list[PropertyResult] = []
    clarification_needed: bool = False
    clarification_question: str | None = None
    result_count: int = 0
    error_message: str | None = None
    fallback_applied: bool = False
    fallback_message: str | None = None
    more_results_url: str | None = None


class ChatSessionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    session_id: str
    user_id: str
    created_at: datetime
    last_active: datetime
    memory: dict


class ChatMessageSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    session_id: str
    role: str
    content: str
    intent: str | None = None
    generated_sql: str | None = None
    result_count: int | None = None
    created_at: datetime


class Level3QueryPlan(BaseModel):
    query_type: str
    sort_field: str | None = None
    sort_direction: str | None = None
    limit: int | None = None
    max_distance_km: float | None = None
    field: str | None = None
    term: str | None = None
    aggregation: str | None = None
