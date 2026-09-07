"""Node: reset_search_context — clears search-specific context for NEW_SEARCH.

When the conversation action is NEW_SEARCH, this dedicated node:
1. Discards all previous search filters (city, intent, property_type, etc.).
2. Extracts constraints fresh from the user's message.
3. Returns a clean SearchContext with only the new constraints.

Conversation metadata (session_id, messages, thread_id) is NOT touched —
only ``search_context`` and ``constraints`` state keys are updated.

Routing: classify_action ─┬─ NEW_SEARCH      ─→ reset_search_context ─→ needs_clarification
                          ├─ MODIFY_SEARCH    ─→ modify_search_context ─→ needs_clarification
                          └─ (others)         ─→ extract_constraints   ─→ needs_clarification

T22: Also generates a **fresh search_id** for active_search.
The new UUID signals that this is a completely new search, not a refinement.
TODO T22 cleanup: once downstream nodes read from active_search directly,
remove the search_context return value.
"""

from __future__ import annotations

import logging

from langchain_core.runnables import RunnableConfig

from app.agents.free_chat.state import AgentState
from app.domain.chat.schemas import ActiveSearchSession, SearchContext
from app.infrastructure.llm.base import LLMProvider

logger = logging.getLogger(__name__)

# Search-specific fields cleared on NEW_SEARCH.  Maps requirement names to
# SearchContext attribute names where they differ (budget → max_price, etc.).
_SEARCH_FIELDS_TO_CLEAR = frozenset({
    "city",
    "intent",
    "property_type",
    "bedrooms",
    "bathrooms",       # T22: added to align with ActiveSearchSession
    "max_price",       # budget / price_range
    "radius_km",       # radius / distance
    "sort_by",
    "sort_order",
    "limit",
})


async def reset_search_context_node(
    state: AgentState,
    config: RunnableConfig,
) -> dict:
    """Clear old search filters and extract constraints fresh from the message.

    Returns ``constraints`` and ``search_context`` keys — the same shape
    as ``extract_constraints_node`` so downstream nodes work identically.

    T22: Returns ``active_search`` with a brand-new search_id.
    This distinguishes a NEW_SEARCH from any prior MODIFY/REFINE turns.
    """
    from app.conversation.new_search import apply_new_search

    llm_provider: LLMProvider = config["configurable"]["llm"]
    user_message: str = state["user_message"]
    prior_context: dict = state.get("search_context") or {}

    updated_ctx, constraints = await apply_new_search(
        user_message=user_message,
        llm=llm_provider,
    )

    cleared = [f for f in _SEARCH_FIELDS_TO_CLEAR if prior_context.get(f) is not None]

    # T22: Build active_search with a FRESH search_id.
    # No existing search_id is passed → from_search_context generates a new UUID.
    fresh_context = SearchContext(**updated_ctx)
    active_session = ActiveSearchSession.from_search_context(
        fresh_context,
        search_id=None,  # intentionally None → new UUID
    )

    logger.info(
        "reset_search_context_node | cleared_fields=%s | extracted_fields=%s"
        " | new_search_id=%s",
        cleared,
        list(constraints.keys()),
        active_session.search_id,
    )

    return {
        "constraints": constraints,
        "search_context": updated_ctx,
        # T22: canonical search object — fresh search_id signals new search
        "active_search": active_session.model_dump(),
    }
