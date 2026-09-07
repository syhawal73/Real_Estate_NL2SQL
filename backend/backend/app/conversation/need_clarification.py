"""NEED_CLARIFICATION handler.

When the conversation action is NEED_CLARIFICATION the user's request is
too vague to execute — e.g. "Find me a property" or "I want something
affordable".  No SQL should be generated; instead, the system must return
a targeted clarification question asking for the missing details.

The handler:
1. Inspects the (usually empty) SearchContext to see what is already known.
2. Builds a list of missing *essential* fields (city, rent/buy, budget).
3. Returns a structured clarification question covering the gaps.

This module is called from ``extract_constraints_node`` when the
``conversation_action`` state key equals ``"need_clarification"``.

**Key invariant**: no SQL is generated or executed when this handler fires.
"""

from __future__ import annotations

import logging

from app.domain.chat.schemas import SearchContext

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Essential fields the user should provide before we can search
# ---------------------------------------------------------------------------
_ESSENTIAL_FIELDS: list[tuple[str, str]] = [
    ("intent", "Are you looking to rent or buy?"),
    ("city", "Which city are you interested in? (London, Paris, Berlin, Amsterdam, or Rome)"),
    ("max_price", "What is your budget?"),
]


def build_clarification_question(current_context: dict | None) -> tuple[str, list[str]]:
    """Build a clarification question based on what's missing in the context.

    Parameters
    ----------
    current_context:
        Serialised ``SearchContext`` dict (or ``None`` for a fresh session).

    Returns
    -------
    (question_text, missing_fields)
        A human-readable question string and the list of field names that
        were identified as missing.
    """
    ctx = SearchContext(**(current_context or {}))
    missing: list[tuple[str, str]] = []

    for field_name, prompt in _ESSENTIAL_FIELDS:
        value = getattr(ctx, field_name, None)
        if value is None:
            missing.append((field_name, prompt))

    if not missing:
        # Everything essential is present but the classifier still flagged
        # need_clarification — ask a generic follow-up.
        question = (
            "Could you provide a few more details about what you're looking for? "
            "For example, the number of bedrooms or property type (apartment/house)."
        )
        return question, []

    # Build a friendly, consolidated question
    missing_field_names = [f for f, _ in missing]
    prompts = [p for _, p in missing]

    question = prompts[0]

    return question, missing_field_names


def apply_need_clarification(
    user_message: str,
    current_context: dict | None,
) -> tuple[dict, dict, str]:
    """Handle a NEED_CLARIFICATION action — no SQL, return question.

    Parameters
    ----------
    user_message:
        The raw user text (logged, but not parsed for constraints).
    current_context:
        Serialised ``SearchContext`` dict (or ``None``).

    Returns
    -------
    (context_dict, empty_constraints, clarification_question)
        * context_dict — the unchanged context (no extraction performed).
        * empty_constraints — always ``{}``, since we skip extraction.
        * clarification_question — the question to return to the user.
    """
    question, missing_fields = build_clarification_question(current_context)

    logger.info(
        "need_clarification | user_message=%r | missing_fields=%s",
        user_message,
        missing_fields,
    )

    # Preserve existing context (don't clear anything)
    context_dict = (current_context or {}).copy()

    return context_dict, {}, question
