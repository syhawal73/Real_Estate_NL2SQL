"""MODIFY_SEARCH handler.

When the conversation action is MODIFY_SEARCH the user is changing a
fundamental axis of their search (e.g. switching city or flipping
rent↔buy).  Only **explicitly mentioned** fields should be updated;
everything else in the SearchContext is preserved.

Implementation strategy
-----------------------
Use regex-only extraction (no LLM fallback) so that only fields the
user literally typed end up in the constraint dict.  Then merge into the
existing SearchContext, which already preserves any field not present in
the new constraints.

This module is called from ``modify_search_context_node`` (the dedicated
LangGraph node for MODIFY_SEARCH) which is routed to via conditional
edges after ``classify_action``.
"""

from __future__ import annotations

import logging
from typing import Any

from app.domain.chat.schemas import SearchContext

logger = logging.getLogger(__name__)


def apply_modify_search(
    user_message: str,
    current_context: dict,
) -> tuple[dict, dict]:
    """Extract only explicitly mentioned fields and merge into context.

    Parameters
    ----------
    user_message:
        The raw user text.
    current_context:
        Serialised ``SearchContext`` dict from the state.

    Returns
    -------
    (updated_context_dict, extracted_constraints)
        Ready to be returned by ``extract_constraints_node``.
    """
    # Lazy import to avoid circular dependency at module load-time:
    # extract_constraints → modify_search → extract_constraints
    from app.agents.free_chat.nodes.extract_constraints import (
        _normalize_constraints,
        _regex_extract,
    )

    search_context = SearchContext(**current_context)

    # Regex-only: extracts only fields the user literally mentioned.
    raw_constraints: dict[str, Any] = _regex_extract(user_message)
    normalized: dict = _normalize_constraints(raw_constraints)

    # Merge into existing context (non-mentioned fields preserved).
    updated_context = search_context.merge(normalized)

    logger.info(
        "modify_search | changed_fields=%s | preserved_context=%s",
        list(normalized.keys()),
        search_context.to_context_string(),
    )

    return updated_context.model_dump(), normalized
