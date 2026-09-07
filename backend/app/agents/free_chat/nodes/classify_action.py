"""Deterministic-first conversation-action routing, with an LLM fallback.

Clear cases (reset / switch / refine / general / forget) are decided by fast,
provider-independent rules. Only when the rules are unsure about a turn that has
an active search do we consult the LLM to interpret intent — so routing stays
stable and cheap while still handling natural, unanticipated phrasings.
Property selection and SQL remain fully deterministic downstream.
"""

import re

from langchain_core.runnables import RunnableConfig

from app.agents.free_chat.nodes.extract_constraints import _fields_to_clear
from app.agents.free_chat.prompts import INTERPRET_SYSTEM, INTERPRET_USER
from app.agents.free_chat.state import AgentState
from app.conversation.action_classifier import ConversationAction


# Constraint fields that mark a turn as a search action even without a verb.
_CONSTRAINT_KEYS = (
    "city", "neighbourhood", "property_type", "bedrooms", "bathrooms",
    "budget", "min_budget", "max_price", "rent_or_buy", "radius_km",
    "sort_by", "limit",
)

_WHOLE_RESET = re.compile(
    r"\b(start over|start again|start fresh|fresh start|new search|start a new search|"
    r"forget (everything|it all|all of it|the search|this search|that search|"
    r"the current search|the previous search|what i said)|"
    r"clear (everything|all|the search|it all)|reset( everything| the search)?|"
    r"scrap (everything|it all|that|this)|let'?s start (over|again|fresh)|"
    r"from scratch|wipe (it|everything))\b",
    re.IGNORECASE,
)
_SWITCH = re.compile(
    r"\b(switch|change|move)\s+(to|over to)\b|\binstead\s+(in|to)\b|\b(rent|buy) instead\b",
    re.IGNORECASE,
)
_SEARCHY = re.compile(
    r"\b(show me|find|search|looking for|compare|how many|average|cheapest|largest|"
    r"closest|nearest|properties|apartments|houses|homes|rent|buy)\b",
    re.IGNORECASE,
)
_GENERALQ = re.compile(
    r"\b(what is|what does|explain|how does|should i|tell me about|why|is it worth)\b",
    re.IGNORECASE,
)


def _transcript(history) -> str:
    lines = []
    for m in (history or [])[-6:]:
        who = "User" if m.get("role") == "user" else "Assistant"
        lines.append(f"{who}: {m.get('content', '')}")
    return "\n".join(lines) if lines else "(no prior conversation)"


def _state_summary(ctx: dict) -> str:
    keys = ("city", "rent_or_buy", "property_type", "bedrooms", "bathrooms",
            "budget", "min_budget", "radius_km", "neighbourhood")
    parts = [f"{k}={ctx[k]}" for k in keys if ctx.get(k) is not None]
    return ", ".join(parts) if parts else "empty"


async def classify_action_node(state: AgentState, config: RunnableConfig = None) -> dict:
    message = state["user_message"].lower().strip()
    search_ctx = state.get("search_context") or {}
    active = state.get("active_search") or {}
    has_context = bool(
        search_ctx.get("city") or active.get("city")
        or any(search_ctx.get(k) is not None for k in _CONSTRAINT_KEYS)
    )
    entities = state.get("level1_entities") or {}
    has_new_constraints = any(entities.get(k) is not None for k in _CONSTRAINT_KEYS)

    whole_reset = bool(_WHOLE_RESET.search(message))
    clear_fields = [] if whole_reset else _fields_to_clear(message)

    if whole_reset:
        action = ConversationAction.NEW_SEARCH
    elif clear_fields and has_context:
        action = ConversationAction.MODIFY_SEARCH
    elif _SWITCH.search(message):
        action = ConversationAction.MODIFY_SEARCH if has_context else ConversationAction.NEW_SEARCH
    elif _SEARCHY.search(message) or has_new_constraints:
        action = ConversationAction.REFINE_SEARCH if has_context else ConversationAction.NEW_SEARCH
    elif _GENERALQ.search(message):
        action = ConversationAction.GENERAL_CHAT
    else:
        # Ambiguous turn. If there's an active search, let the LLM interpret it
        # (hybrid fallback); otherwise treat as general chat.
        action = ConversationAction.GENERAL_CHAT
        if has_context and config is not None:
            interp = await _llm_interpret(config, state)
            if interp:
                mapping = {
                    "refine_search": ConversationAction.REFINE_SEARCH,
                    "modify_search": ConversationAction.MODIFY_SEARCH,
                    "new_search": ConversationAction.NEW_SEARCH,
                    "forget": ConversationAction.MODIFY_SEARCH,
                    "general_chat": ConversationAction.GENERAL_CHAT,
                }
                a = str(interp.get("action", "")).strip().lower()
                if a in mapping:
                    action = mapping[a]
                    if a == "new_search":
                        clear_fields = []
                    else:
                        extra = [c for c in (interp.get("clear") or []) if isinstance(c, str)]
                        clear_fields = list(dict.fromkeys([*clear_fields, *extra]))

    return {"conversation_action": action.value, "clear_fields": clear_fields}


async def _llm_interpret(config: RunnableConfig, state: AgentState) -> dict | None:
    """Ask the LLM to classify an ambiguous turn. Returns None on any failure."""
    try:
        llm = config["configurable"]["llm"]
    except Exception:
        return None
    user = INTERPRET_USER.format(
        history=_transcript(state.get("history")),
        search_state=_state_summary(state.get("search_context") or {}),
        user_message=state.get("user_message", ""),
    )
    try:
        result = await llm.invoke_json([
            {"role": "system", "content": INTERPRET_SYSTEM},
            {"role": "user", "content": user},
        ])
        return result if isinstance(result, dict) else None
    except Exception:
        return None
