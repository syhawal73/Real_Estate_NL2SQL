"""Node: modify_search_context — replaces explicitly changed search fields.

When the conversation action is MODIFY_SEARCH, this dedicated node:
1. Extracts only fields the user *explicitly* mentioned (regex-only, no LLM).
2. Replaces those fields in the current SearchContext in-place.
3. Preserves all other fields unchanged.

Key invariant: each SearchContext slot holds **exactly one value** — never
a list, never an "old_*" prefix.  Only the latest value survives.

This node is inserted via conditional routing after ``classify_action``
and merges back into the pipeline at ``needs_clarification``.

Routing: classify_action ─┬─ MODIFY_SEARCH ─→ modify_search_context ─→ needs_clarification
                          └─ (others)      ─→ extract_constraints    ─→ needs_clarification

T22: Dual-writes to active_search (canonical) in addition to search_context
(backward compat).  The search_id is PRESERVED on MODIFY_SEARCH — only
NEW_SEARCH (reset_search_context_node) generates a fresh UUID.
TODO T22 cleanup: once all downstream nodes read from active_search,
drop the search_context return value.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.runnables import RunnableConfig

from app.agents.free_chat.state import AgentState
from app.domain.chat.schemas import ActiveSearchSession, SearchContext

logger = logging.getLogger(__name__)

# Fields that can be replaced by MODIFY_SEARCH.
# Matches the requirement list: city, intent, property_type, bedrooms,
# bathrooms (T22), budget (max_price), radius (radius_km),
# distance (distance maps to radius_km in our schema).
_REPLACEABLE_FIELDS = frozenset({
    "city",
    "intent",
    "property_type",
    "bedrooms",
    "bathrooms",       # T22: added to align with ActiveSearchSession
    "max_price",       # budget
    "radius_km",       # radius / distance
    "sort_by",
    "sort_order",
    "limit",
})


async def modify_search_context_node(
    state: AgentState,
    config: RunnableConfig,
) -> dict:
    """Replace only explicitly mentioned fields in the SearchContext.

    Returns ``constraints`` and ``search_context`` keys — the same shape
    as ``extract_constraints_node`` so downstream nodes (needs_clarification,
    generate_sql, etc.) work identically.

    T22: Also returns ``active_search`` with the same search_id preserved.
    """
    # Lazy import to avoid circular dependency at module load-time.
    from app.agents.free_chat.nodes.extract_constraints import (
        _normalize_constraints,
        _regex_extract,
    )

    user_message: str = state["user_message"]
    current_context_dict: dict = state.get("search_context") or {}
    search_context = SearchContext(**current_context_dict)

    # ── 1. Extract ONLY fields the user literally typed (regex-only) ──
    raw_constraints: dict[str, Any] = _regex_extract(user_message)
    normalized: dict = _normalize_constraints(raw_constraints)

    # ── 2. Filter to replaceable fields only ──────────────────────────
    replacements: dict = {
        k: v for k, v in normalized.items()
        if k in _REPLACEABLE_FIELDS
    }

    # ── 3. Merge: replace mentioned fields, preserve everything else ──
    updated_context = search_context.merge(replacements)

    # ── 3b. Drop any fields the user asked to forget (per-field forget) ──
    clear_fields = state.get("clear_fields") or []
    if clear_fields:
        data = updated_context.model_dump()
        for field in clear_fields:
            if field in data:
                data[field] = None
        updated_context = SearchContext(**data)

    # ── 4. T22: Dual-write to active_search (search_id PRESERVED) ────
    existing_id: str | None = (state.get("active_search") or {}).get("search_id")
    active_session = ActiveSearchSession.from_search_context(
        updated_context,
        search_id=existing_id,  # preserve across MODIFY_SEARCH turns
    )

    # ── 5. Log for observability ──────────────────────────────────────
    logger.info(
        "modify_search_context_node | changed=%s | preserved=%s | search_id=%s",
        list(replacements.keys()),
        search_context.to_context_string(),
        active_session.search_id,
    )

    return {
        "constraints": replacements,
        "search_context": updated_context.model_dump(),
        # T22: canonical search object (search_id unchanged)
        "active_search": active_session.model_dump(),
    }
