"""Conversation action classifier.

Classifies what *kind* of conversational action the user intends,
independent of the lower-level query intent (filter_search, count, …).

The five actions are:

* REFINE_SEARCH  — tweak the *current* search (add/narrow a filter)
* MODIFY_SEARCH  — change a core axis (city, rent↔buy) of the search
* NEW_SEARCH     — start a brand-new search from scratch
* GENERAL_CHAT   — non-search conversation (neighbourhood info, etc.)
* NEED_CLARIFICATION — too vague to act on

This module is intentionally read-only w.r.t. the rest of the system:
it does **not** modify SQL generation, memory persistence, or the
LangGraph agent graph.
"""

from __future__ import annotations

import json
import re
from enum import Enum

from app.infrastructure.llm.base import LLMProvider


# ---------------------------------------------------------------------------
# Enum
# ---------------------------------------------------------------------------

class ConversationAction(str, Enum):
    """High-level action the user wants to perform."""

    REFINE_SEARCH = "refine_search"
    MODIFY_SEARCH = "modify_search"
    NEW_SEARCH = "new_search"
    GENERAL_CHAT = "general_chat"
    NEED_CLARIFICATION = "need_clarification"


_VALID_ACTIONS = frozenset(e.value for e in ConversationAction)


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_CLASSIFY_SYSTEM = """\
You are classifying the user's conversation action for a real-estate search.

Global rules:
- Use only the provided schema and allowed columns.
- Never invent latitude, longitude, city_centers, ST_Distance, ST_MakePoint, or geography joins.
- Never reuse old search context unless the user is explicitly modifying the current search.
- If the request is vague or missing a required search dimension, ask for clarification instead of inventing filters.
- For words like cheapest, largest, closest, nearest, or farthest, prefer ranking behavior, not clarification.
- For explicit "within X km" requests, use distance_from_city_km <= X.

Choose exactly one action:
- refine_search       : add or narrow a filter without changing the core search
- modify_search       : change a fundamental axis such as city or rent/buy
- new_search          : start a fresh standalone search
- general_chat        : not a property search
- need_clarification  : too vague to act on

Rules:
- "switch to Berlin", "instead in Berlin", "change city to Berlin", "move the search to Berlin" => modify_search
- "rent instead of buy" or "buy instead of rent" => modify_search
- "add 2 bedrooms", "make it cheaper", "show only apartments" => refine_search
- "find me something affordable" with no city and no other concrete filter => need_clarification
- Do NOT send a modify_search request to need_clarification just because the city changed.
- Do NOT ask for more details when the user has already clearly named a city and a search change.
- If the user explicitly mentions a city switch or filter change, ALWAYS return modify_search, NEVER need_clarification.
- If the user asks a structured analytical question (average, count, compare), return new_search, NEVER need_clarification.

Reply with ONLY valid JSON. Example: {"action": "refine_search"}"""


_CLASSIFY_USER = """\
Current search context: {context}
User message: {user_message}"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def determine_action(
    user_message: str,
    current_context: dict | None,
    *,
    llm: LLMProvider,
) -> ConversationAction:
    """Classify the user's message into a high-level conversation action.

    Parameters
    ----------
    user_message:
        The raw text the user typed.
    current_context:
        Serialised ``SearchContext`` dict (or ``None`` for a fresh session).
    llm:
        Any concrete ``LLMProvider`` — the same singleton used elsewhere.

    Returns
    -------
    ConversationAction
        One of the five enum members.
    """
    context_str = _format_context(current_context)

    messages = [
        {"role": "system", "content": _CLASSIFY_SYSTEM},
        {
            "role": "user",
            "content": _CLASSIFY_USER.format(
                context=context_str,
                user_message=user_message,
            ),
        },
    ]

    return await _extract_action(llm, messages)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _format_context(ctx: dict | None) -> str:
    """Build a human-readable summary of the current search context."""
    if not ctx:
        return "none (new session)"

    parts: list[str] = []
    for key in ("city", "intent", "property_type", "bedrooms",
                "max_price", "radius_km", "sort_by", "sort_order", "limit"):
        value = ctx.get(key)
        if value is not None:
            parts.append(f"{key}={value}")

    return ", ".join(parts) if parts else "none (no active filters)"


async def _extract_action(
    llm: LLMProvider,
    messages: list[dict],
) -> ConversationAction:
    """Extract the action using JSON parsing with robust fallbacks."""
    # 1. Structured JSON
    try:
        result = await llm.invoke_json(messages)
        if isinstance(result, dict) and "action" in result:
            action = str(result["action"]).strip().lower()
            if action in _VALID_ACTIONS:
                return ConversationAction(action)
    except Exception:
        pass

    # 2. Plain text fallback
    try:
        raw = await llm.invoke(messages)
        return _parse_action_from_text(raw)
    except Exception:
        return ConversationAction.NEED_CLARIFICATION


def _parse_action_from_text(raw: str) -> ConversationAction:
    """Parse a ``ConversationAction`` from unstructured LLM text."""
    text = raw.strip()

    # Try JSON
    try:
        data = json.loads(text)
        if isinstance(data, dict) and "action" in data:
            action = str(data["action"]).strip().lower()
            if action in _VALID_ACTIONS:
                return ConversationAction(action)
    except json.JSONDecodeError:
        pass

    # Try embedded JSON
    match = re.search(r'\{[^}]*"action"\s*:\s*"([^"]+)"[^}]*\}', text)
    if match:
        action = match.group(1).strip().lower()
        if action in _VALID_ACTIONS:
            return ConversationAction(action)

    # Try plain label
    label = text.lower().strip().rstrip(".")
    if label in _VALID_ACTIONS:
        return ConversationAction(label)

    # Search for any valid action within the text
    for valid in _VALID_ACTIONS:
        if valid in label:
            return ConversationAction(valid)

    return ConversationAction.NEED_CLARIFICATION
