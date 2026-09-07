"""Final response composer.

Property SELECTION stays fully deterministic: the same search state produces the
same rows and the same property cards regardless of model/provider. Only the
natural-language WORDING of the reply is delegated to the LLM — and it always
falls back to a deterministic template when the LLM is unavailable, so the
assistant keeps working even with no model configured.
"""

import numbers

from langchain_core.runnables import RunnableConfig

from app.agents.free_chat.prompts import (
    LEVEL4_SYSTEM,
    NATURAL_CLARIFY_SYSTEM,
    NATURAL_CLARIFY_USER,
    NATURAL_FACT_SYSTEM,
    NATURAL_FACT_USER,
    NATURAL_RESPONSE_SYSTEM,
    NATURAL_RESPONSE_USER,
)
from app.agents.free_chat.state import AgentState
from app.infrastructure.llm.base import LLMProvider


_SUMMARY_LABELS = {
    "rent_or_buy": "intent",
    "property_type": "type",
    "city": "city",
    "neighbourhood": "area",
    "bedrooms": "bedrooms",
    "bathrooms": "bathrooms",
    "budget": "max budget",
    "min_budget": "min budget",
    "radius_km": "within km",
}
_SUMMARY_ORDER = [
    "rent_or_buy", "property_type", "city", "neighbourhood",
    "bedrooms", "bathrooms", "budget", "min_budget", "radius_km",
]


def _search_summary(ctx: dict) -> str:
    parts = []
    for key in _SUMMARY_ORDER:
        value = ctx.get(key)
        if value not in (None, ""):
            parts.append(f"{_SUMMARY_LABELS[key]}={value}")
    return ", ".join(parts) if parts else "no filters yet"


def _missing_useful(ctx: dict) -> str:
    missing = []
    if not ctx.get("budget") and not ctx.get("min_budget"):
        missing.append("budget")
    if ctx.get("bedrooms") is None:
        missing.append("number of bedrooms")
    if not ctx.get("property_type"):
        missing.append("apartment or house")
    return ", ".join(missing) if missing else "none"


def _history(state: AgentState) -> str:
    lines = []
    for m in (state.get("history") or [])[-6:]:
        who = "User" if m.get("role") == "user" else "Assistant"
        lines.append(f"{who}: {m.get('content', '')}")
    return "\n".join(lines) if lines else "(no prior conversation)"


def _listing_message(state: AgentState, results: list[dict]) -> str:
    """Deterministic fallback wording, used when the LLM is unavailable."""
    count = int(state.get("result_count") or len(results))
    plan = state.get("query_plan") or {}
    fallback = state.get("fallback_message") or ""
    query_type = plan.get("query_type", "listing")

    if not results:
        if fallback:
            return f"{fallback} I still couldn't find any matching properties."
        return "I couldn't find any properties matching your current search."

    prefix = (fallback + " ") if fallback else ""

    if query_type == "ranking":
        direction = plan.get("sort_direction", "asc")
        field = plan.get("sort_field", "price")
        if field == "price":
            label = "cheapest" if direction == "asc" else "most expensive"
        elif field == "size_sqm":
            label = "largest" if direction == "desc" else "smallest"
        elif field == "distance_from_city_km":
            label = "closest"
        else:
            label = "best matching"
        return f"{prefix}I found {count} {label} {('property' if count == 1 else 'properties')}."

    if query_type == "radius":
        return f"{prefix}I found {count} {('property' if count == 1 else 'properties')} within your requested area."

    return f"{prefix}I found {count} matching {('property' if count == 1 else 'properties')}."


async def _llm_text(llm: LLMProvider, system: str, user: str, fallback: str) -> str:
    """Return LLM wording, or the deterministic fallback if the model errors/empty."""
    try:
        out = (await llm.invoke([
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ])).strip()
        return out or fallback
    except Exception:
        return fallback


async def _natural_fact(llm, state, ctx, statement, must_contain=None,
                        follow_up="Offer one helpful next step."):
    """Rephrase an already-correct factual sentence naturally, ending with a
    proactive next-step follow-up.

    Reverts to the exact statement if the LLM errors, returns nothing, or drops
    the key figure (``must_contain``) — so numbers are never silently altered.
    """
    user = NATURAL_FACT_USER.format(
        history=_history(state),
        user_message=state.get("user_message", ""),
        search_summary=_search_summary(ctx),
        statement=statement,
        follow_up=follow_up,
    )
    msg = await _llm_text(llm, NATURAL_FACT_SYSTEM, user, statement)
    if must_contain is not None and must_contain not in msg:
        return statement
    return msg


async def level4_response_node(state: AgentState, config: RunnableConfig) -> dict:
    llm: LLMProvider = config["configurable"]["llm"]
    ctx = state.get("search_context") or {}

    # ── Clarification: ask one natural follow-up (falls back to canned Q) ──
    if state.get("clarification_needed"):
        deterministic_q = state.get("clarification_question") or "Which city would you like me to search in?"
        user = NATURAL_CLARIFY_USER.format(
            history=_history(state),
            user_message=state.get("user_message", ""),
            search_summary=_search_summary(ctx),
            suggested=deterministic_q,
        )
        msg = await _llm_text(llm, NATURAL_CLARIFY_SYSTEM, user, deterministic_q)
        return {"assistant_message": msg, "clarification_question": deterministic_q, "properties": []}

    if state.get("sql_error"):
        return {
            "assistant_message": "I ran into a problem while searching the property inventory. Please try that search again.",
            "properties": [],
        }

    results = state.get("query_results", [])
    query_type = (state.get("query_plan") or {}).get("query_type", "listing")

    # ── General real-estate chat ──
    if state.get("conversation_action") == "general_chat":
        messages = [
            {
                "role": "system",
                "content": LEVEL4_SYSTEM
                + "\nOnly answer within real estate/property context. If asked about unrelated tasks, politely redirect to property discovery.",
            },
        ]
        for h in (state.get("history") or [])[-6:]:
            role = h.get("role") if h.get("role") in ("user", "assistant") else "user"
            messages.append({"role": role, "content": h.get("content", "")})
        messages.append({"role": "user", "content": state.get("user_message", "")})
        try:
            return {"assistant_message": (await llm.invoke(messages)).strip(), "properties": []}
        except Exception:
            return {
                "assistant_message": "I can help with property searches, comparisons, rankings, and real-estate questions. What would you like to find?",
                "properties": [],
            }

    # ── Deterministic numeric answers (counts/aggregates must be exact) ──
    if query_type == "count":
        n = int(results[0].get("property_count", results[0].get("result_count", 0))) if results else 0
        answer = f"I found {n:,} matching properties." if n != 1 else "I found 1 matching property."
        msg = await _natural_fact(
            llm, state, ctx, answer,
            must_contain=(f"{n:,}" if n != 1 else "1"),
            follow_up="Offer to show these properties (for example the cheapest few) or to narrow the search.",
        )
        return {"assistant_message": msg, "properties": []}

    if query_type == "aggregation":
        plan = state.get("query_plan") or {}
        label = {
            "average_price": "average price",
            "min_price": "lowest price",
            "max_price": "highest price",
        }.get(plan.get("aggregation", "average_price"), "value")
        value = None
        if results:
            row = results[0]
            value = row.get("result_value")
            if value is None:
                for key in ("avg_price", "min_price", "max_price"):
                    if row.get(key) is not None:
                        value = row[key]
                        break
        if isinstance(value, numbers.Number):
            answer = f"The {label} is {value:,}."
            msg = await _natural_fact(
                llm, state, ctx, answer, must_contain=f"{value:,}",
                follow_up="Offer to show matching listings, such as the cheapest few.",
            )
        else:
            answer = "I couldn't calculate that from the current inventory."
            msg = await _natural_fact(
                llm, state, ctx, answer,
                follow_up="Ask what they'd like to search for instead.",
            )
        return {"assistant_message": msg, "properties": []}

    if query_type == "comparison":
        if not results:
            return {
                "assistant_message": "I couldn't find enough matching data to compare those locations.",
                "properties": [],
            }
        pieces = [
            f"{r.get('city')}: average price {r.get('average_price'):,} across {r.get('property_count')} properties"
            for r in results
            if r.get("average_price") is not None
        ]
        answer = "Here is the comparison: " + "; ".join(pieces) + "."
        msg = await _natural_fact(
            llm, state, ctx, answer,
            follow_up="Offer to show the listings in one of the compared cities.",
        )
        return {"assistant_message": msg, "properties": []}

    # ── Listing / ranking / radius / pattern: natural, grounded wording ──
    # Property cards are rendered from these deterministic rows; only the
    # accompanying sentence is phrased by the LLM.
    sample = results[:5]
    count = int(state.get("result_count") or len(results))
    fallback_msg = _listing_message(state, results)

    if not results:
        extra = ("No properties matched exactly. Gently tell the user nothing matched "
                 "and invite them to broaden or change a filter.")
    elif state.get("fallback_applied"):
        extra = (f"Note: there were no exact matches, so the search was automatically "
                 f"widened ({state.get('fallback_message', '')}). Mention this briefly.")
    else:
        extra = ""

    user = NATURAL_RESPONSE_USER.format(
        history=_history(state),
        user_message=state.get("user_message", ""),
        search_summary=_search_summary(ctx),
        result_count=count,
        missing=_missing_useful(ctx),
        extra=extra,
    )
    msg = await _llm_text(llm, NATURAL_RESPONSE_SYSTEM, user, fallback_msg)
    return {"assistant_message": msg, "properties": sample}
