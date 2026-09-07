"""NEW_SEARCH handler.

When the conversation action is NEW_SEARCH the user is starting a
completely new property search.  All previous search-specific context
(city, intent, bedrooms, budget, radius, etc.) is discarded.

The handler:
1. Creates a **blank** SearchContext.
2. Extracts constraints from the message using the normal pipeline
   (regex fast-path + LLM fallback) — so a message like
   "Properties with modern in title" still gets parsed properly.
3. Returns the fresh context.

Conversation metadata (session_id, message history, etc.) is NOT
touched — only search filters are cleared.

This module is called from ``reset_search_context_node`` when the
``conversation_action`` state key equals ``"new_search"``.
"""

from __future__ import annotations

import logging
from typing import Any

from app.domain.chat.schemas import SearchContext
from app.infrastructure.llm.base import LLMProvider

logger = logging.getLogger(__name__)


async def apply_new_search(
    user_message: str,
    llm: LLMProvider,
) -> tuple[dict, dict]:
    """Clear old context and extract constraints fresh from the message.

    Parameters
    ----------
    user_message:
        The raw user text.
    llm:
        The LLMProvider instance (used for LLM fallback extraction).

    Returns
    -------
    (new_context_dict, extracted_constraints)
        Ready to be returned by ``extract_constraints_node``.
    """
    # Lazy imports to avoid circular dependency at module load-time.
    from app.agents.free_chat.nodes.extract_constraints import (
        _llm_extract,
        _normalize_constraints,
        _regex_extract,
    )

    # Start completely fresh — no carryover from previous search.
    blank_context = SearchContext()

    # Extract constraints from the user's message using the full
    # pipeline (regex + LLM), identical to the default path but
    # operating against a blank context.
    raw_constraints: dict[str, Any] = _regex_extract(user_message)

    if len(raw_constraints) <= 1:
        llm_constraints = await _llm_extract(llm, user_message, blank_context)
        for key, value in llm_constraints.items():
            if key not in raw_constraints and value is not None:
                raw_constraints[key] = value

    normalized: dict = _normalize_constraints(raw_constraints)
    new_context = blank_context.merge(normalized)

    logger.info(
        "new_search | cleared_context | extracted_fields=%s",
        list(normalized.keys()),
    )

    return new_context.model_dump(), normalized
