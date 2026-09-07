"""Node: needs_clarification — rules-based check for missing context (Phase 4.1).

Examines SearchContext + intent to determine if clarification is needed.
Uses deterministic rules, no LLM call.

Runs after extract_constraints, before generate_sql.

Strict clarification rules:
- Clarification IS needed when the request is too vague:
  "find me a property", "something affordable", "show rentals", "I want a place"
- Clarification is NOT needed when the user has already provided enough:
  city + one strong filter, city + rent/buy, city + price/budget,
  city + bedrooms or property type, a clear ranking request
- Vague words (affordable, cheap, nice place, good option, modern home) require
  clarification UNLESS the user has also provided concrete filters.
"""

import re

from langchain_core.runnables import RunnableConfig

from app.agents.free_chat.state import AgentState
from app.domain.chat.schemas import QueryIntent, SearchContext


# Intents that require at least a city to be useful
_CITY_REQUIRED_INTENTS = frozenset({
    "property_search",
    "radius_search",
    "listing",
})

# Intents that can proceed without a city
_CITY_OPTIONAL_INTENTS = frozenset({
    QueryIntent.COUNT.value,
    QueryIntent.DISTINCT.value,
    QueryIntent.AGGREGATION.value,
    QueryIntent.COMPARISON.value,
    QueryIntent.RANKING.value,
    QueryIntent.PATTERN_SEARCH.value,
    QueryIntent.LOOKUP.value,
})

# Vague words that indicate the user hasn't provided concrete filters.
# These alone (even with a city) are NOT enough to execute a search.
_VAGUE_WORDS = re.compile(
    r"\b(affordable|cheap|nice\s+place|good\s+option|modern\s+home)\b",
    re.IGNORECASE,
)

# Ranking signal words — if present, NEVER ask for clarification.
_RANKING_WORDS = re.compile(
    r"\b(cheapest|most\s+expensive|largest|smallest|biggest|closest|"
    r"nearest|farthest|furthest|top\s+\d+|priciest)\b",
    re.IGNORECASE,
)


def _has_strong_filter(search_context: SearchContext, constraints: dict) -> bool:
    """Return True if the user has at least one concrete, actionable filter.

    A "strong filter" is any of: budget, bedrooms, bathrooms, radius_km, ranking_type.
    City alone is NOT a strong filter. rent_or_buy and property_type are NOT
    strong enough on their own to bypass clarification if a city is missing.
    """
    # Check constraints from current turn (level1_entities)
    strong_keys = {"bedrooms", "bathrooms", "budget", "radius_km", "ranking_type"}
    if any(k in constraints and constraints[k] is not None for k in strong_keys):
        return True

    # Check accumulated search context
    if search_context.bedrooms is not None:
        return True
    if search_context.bathrooms is not None:
        return True
    if search_context.budget is not None:
        return True
    if search_context.radius_km is not None:
        return True
    if search_context.ranking_type is not None:
        return True

    return False


async def needs_clarification_node(state: AgentState, config: RunnableConfig) -> dict:
    """Determine if clarification is needed based on SearchContext and intent.

    Rules:
    1. If upstream already flagged clarification → honour it
    2. If conversation_action is need_clarification → clarify
    3. If intent is clarification_needed → clarify
    4. If intent is unsupported → let handle_error deal with it
    5. If ranking words are present → NEVER clarify (proceed)
    6. If city-required intent but no city and no strong filters → ask for city
    7. If radius_search without radius → ask for radius
    8. If user only used vague words without concrete filters → clarify
    9. If no constraints at all and vague intent → clarify
    10. Otherwise → proceed
    """
    intent = state.get("intent", "")
    search_context = SearchContext(**(state.get("search_context") or {}))
    constraints = state.get("level1_entities") or {}
    user_message = state.get("user_message", "")

    # Rule -1: If the user explicitly modified an existing search, never clarify
    if intent == "modify_search":
        return {
            "clarification_needed": False,
        }

    # Rule 0: Upstream gate (extract_constraints) already flagged clarification
    if state.get("clarification_needed") and state.get("clarification_question"):
        return {
            "clarification_needed": True,
            "clarification_question": state["clarification_question"],
        }

    # Rule 0b: intent is clarification but upstream didn't set flag
    if intent == "clarification":
        return {
            "clarification_needed": True,
            "clarification_question": _generate_question(search_context, intent),
        }

    # Rule 1: Intent classifier already flagged as needing clarification
    if intent == QueryIntent.CLARIFICATION_NEEDED.value:
        return {
            "clarification_needed": True,
            "clarification_question": _generate_question(search_context, intent),
        }

    # Rule 2: Unsupported intent — don't clarify, let handle_error deal with it
    if intent == QueryIntent.UNSUPPORTED.value:
        return {
            "clarification_needed": False,
        }

    # Rule 2.5: Skip clarification for fully-formed structured queries
    _STRUCTURED_INTENTS = {
        QueryIntent.PATTERN_SEARCH.value,
        QueryIntent.AGGREGATION.value,
        QueryIntent.COMPARISON.value,
        QueryIntent.COUNT.value,
    }
    if intent in _STRUCTURED_INTENTS:
        return {
            "clarification_needed": False,
        }

    # Rule 3: Ranking words present → NEVER ask for clarification.
    # cheapest, largest, closest, nearest, etc. are actionable on their own.
    if _RANKING_WORDS.search(user_message):
        return {
            "clarification_needed": False,
        }

    # Rule 4: City-required intent without city
    if intent in _CITY_REQUIRED_INTENTS and not search_context.city:
        # Only ask if the user hasn't provided other meaningful constraints
        if not _has_strong_filter(search_context, constraints):
            return {
                "clarification_needed": True,
                "clarification_question": "Which city are you interested in? I can search in London, Paris, Berlin, Amsterdam, or Rome.",
            }

    # Rule 5: Radius search without radius
    if intent == QueryIntent.RADIUS_SEARCH.value and search_context.radius_km is None:
        return {
            "clarification_needed": True,
            "clarification_question": "How far from the city centre would you like to search? (e.g., 5km, 10km, 20km)",
        }

    # Rule 6: Vague words without concrete filters → clarify.
    # "affordable", "cheap", "nice place", "good option", "modern home"
    # are too vague to act on unless the user also provided concrete filters.
    if _VAGUE_WORDS.search(user_message):
        if not _has_strong_filter(search_context, constraints):
            return {
                "clarification_needed": True,
                "clarification_question": _generate_question(search_context, intent),
            }

    # Rule 7: No meaningful constraints at all and vague intent
    meaningful_constraints = {k: v for k, v in constraints.items() if k != "intent" and v is not None}
    if (
        not meaningful_constraints
        and not search_context.city
        and not search_context.bedrooms
        and not search_context.budget
        and not search_context.property_type
        and intent in _CITY_REQUIRED_INTENTS
    ):
        return {
            "clarification_needed": True,
            "clarification_question": "I'd love to help! Could you tell me which city you're interested in, and whether you're looking to buy or rent?",
        }

    # All good — proceed
    return {
        "clarification_needed": False,
    }


def _generate_question(context: SearchContext, intent: str) -> str:
    """Generate a contextual clarification question based on what's missing.

    Priority order: city → rent/buy → budget → property type → bedrooms.
    Ask exactly ONE question targeting the highest-priority missing piece.
    """
    if not context.city:
        return "Which city are you interested in? I can search in London, Paris, Berlin, Amsterdam, or Rome."

    if not context.rent_or_buy:
        return "Would you like to buy or rent?"

    if not context.budget and not context.min_budget:
        return "What is your approximate budget?"

    if not context.property_type:
        return "Are you looking for an apartment or a house?"

    if context.bedrooms is None:
        return "How many bedrooms do you need?"

    return "Could you provide a few more details about what you're looking for?"
