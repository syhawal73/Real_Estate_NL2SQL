"""Node: extract_constraints — converts user message into structured search filters (Phase 4.1).

Uses a two-tier approach:
1. Regex/rule fast-path for common patterns (e.g. "400k", "3 bedrooms", "houses")
2. LLM fallback for more complex requests

Extracted constraints are merged into the existing SearchContext.

T22: Dual-writes to active_search (canonical) in addition to search_context
(backward compat).  The existing search_id is preserved on REFINE_SEARCH;
a fresh UUID is only generated on NEW_SEARCH (handled by reset_search_context_node).
TODO T22 cleanup: once all downstream nodes read from active_search, remove
the search_context return value from this node.
"""

import json
import re
from typing import Any

from langchain_core.runnables import RunnableConfig

from app.agents.free_chat.prompts import EXTRACT_CONSTRAINTS_SYSTEM, EXTRACT_CONSTRAINTS_USER
from app.agents.free_chat.state import AgentState
from app.domain.chat.schemas import ActiveSearchSession, SearchContext
from app.infrastructure.llm.base import LLMProvider


# ---------------------------------------------------------------------------
# Regex fast-path rules
# ---------------------------------------------------------------------------

_CITIES = {"london", "paris", "berlin", "amsterdam", "rome"}
_CITY_PROPER = {"london": "London", "paris": "Paris", "berlin": "Berlin",
                "amsterdam": "Amsterdam", "rome": "Rome"}

_PRICE_PATTERN = re.compile(
    r"(?:under|below|max|less\s+than|up\s+to|budget)\s*"
    r"[£€$]?\s*(\d+)\s*k?\b",
    re.IGNORECASE,
)
_PRICE_K_PATTERN = re.compile(r"(\d+)\s*k\b", re.IGNORECASE)
_BEDROOMS_PATTERN = re.compile(r"(\d+)\s*[-\s]?(?:bed(?:room)?s?|br)\b", re.IGNORECASE)
_BATHROOMS_PATTERN = re.compile(r"(\d+)\s*[-\s]?(?:bath(?:room)?s?|ba)\b", re.IGNORECASE)
_RADIUS_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*km\b", re.IGNORECASE)
_LIMIT_PATTERN = re.compile(
    r"\b(?:top|first)\s*(\d+)\b|"
    r"\bshow\s+(?:me\s+)?(?:the\s+)?(?:top\s+)?(\d+)\b",
    re.IGNORECASE,
)


def _regex_extract(message: str) -> dict[str, Any]:
    """Fast-path constraint extraction using regex patterns."""
    constraints: dict[str, Any] = {}
    msg_lower = message.lower()

    # City detection (primary city = first mentioned)
    for city_lower, city_proper in _CITY_PROPER.items():
        if city_lower in msg_lower:
            constraints["city"] = city_proper
            break

    # Multi-city detection — used by comparison ("compare Berlin and Paris").
    found_cities = [proper for low, proper in _CITY_PROPER.items() if low in msg_lower]
    if len(found_cities) >= 2:
        constraints["cities"] = found_cities

    # Intent detection (rent/buy)
    if any(w in msg_lower for w in ("rent", "rental", "renting", "to rent")):
        constraints["intent"] = "rent"
    elif any(w in msg_lower for w in ("buy", "purchase", "buying", "to buy")):
        constraints["intent"] = "buy"

    # Property type
    if any(w in msg_lower for w in ("house", "houses", "home", "homes", "only houses")):
        constraints["property_type"] = "house"
    elif any(w in msg_lower for w in ("apartment", "apartments", "flat", "flats", "only apartments")):
        constraints["property_type"] = "apartment"

    # Price extraction
    match = _PRICE_PATTERN.search(message)
    if match:
        price = int(match.group(1))
        # Check if "k" follows
        remaining = message[match.end():]
        if "k" in message[match.start():match.end() + 2].lower() or price < 1000:
            price *= 1000
        constraints["max_price"] = price
    else:
        match = _PRICE_K_PATTERN.search(message)
        if match:
            constraints["max_price"] = int(match.group(1)) * 1000

    # Price range: "between 1000 and 2000", "from 1k to 2k"
    range_match = re.search(
        r"(?:between|from)\s*[£€$]?\s*(\d+(?:\.\d+)?)\s*k?\s*(?:and|to|-|–)\s*[£€$]?\s*(\d+(?:\.\d+)?)\s*k?",
        message, re.IGNORECASE,
    )
    if range_match:
        a, b = float(range_match.group(1)), float(range_match.group(2))
        if a < 1000:
            a *= 1000
        if b < 1000:
            b *= 1000
        lo, hi = sorted((a, b))
        constraints["min_budget"] = lo
        constraints["max_price"] = hi

    # Approximate budget: "around 1500", "about 1.5k"
    around = re.search(
        r"\b(?:around|about|roughly|approximately)\s*[£€$]?\s*(\d+(?:\.\d+)?)\s*k?\b",
        message, re.IGNORECASE,
    )
    if around:
        value = float(around.group(1))
        if value < 1000:
            value *= 1000
        constraints["min_budget"] = value * 0.9
        constraints["max_price"] = value * 1.1

    # Bedrooms
    match = _BEDROOMS_PATTERN.search(message)
    if match:
        constraints["bedrooms"] = int(match.group(1))

    # Bathrooms (T22: added to align with ActiveSearchSession)
    match = _BATHROOMS_PATTERN.search(message)
    if match:
        constraints["bathrooms"] = int(match.group(1))

    # Radius
    match = _RADIUS_PATTERN.search(message)
    if match:
        constraints["radius_km"] = float(match.group(1))

    # Limit
    match = _LIMIT_PATTERN.search(message)
    if match:
        limit_value = next((g for g in match.groups() if g is not None), None)
        if limit_value is not None:
            constraints["limit"] = int(limit_value)

    # Sort hints
    if any(w in msg_lower for w in ("cheapest", "lowest price", "cheaper")):
        constraints["sort_by"] = "price"
        constraints["sort_order"] = "asc"
    elif any(w in msg_lower for w in ("most expensive", "highest price", "priciest")):
        constraints["sort_by"] = "price"
        constraints["sort_order"] = "desc"
    elif any(w in msg_lower for w in ("biggest", "largest")):
        constraints["sort_by"] = "size_sqm"
        constraints["sort_order"] = "desc"
    elif any(w in msg_lower for w in ("closest", "nearest")) or re.search(
        r"close to (?:the )?(?:city )?cent(?:er|re)|near (?:the )?(?:city )?cent(?:er|re)|city cent(?:er|re)",
        msg_lower,
    ):
        constraints["sort_by"] = "distance_from_city_km"
        constraints["sort_order"] = "asc"

    return constraints


_FORGET_VERB = r"(?:forget|remove|drop|clear|ignore|without|scrap|get rid of|don't (?:care about|need|want)|dont (?:care about|need|want)|no longer (?:care about|need|want))"


def _fields_to_clear(message: str) -> list[str]:
    """Detect a request to drop specific filters ("forget the budget",
    "no bedroom limit", "any price", "ignore the city") and return the
    SearchContext field names to null out. Whole-search resets are handled
    elsewhere; this is per-field.
    """
    m = message.lower()
    fields: list[str] = []

    def forgets(field_regex: str) -> bool:
        return re.search(rf"{_FORGET_VERB}\s+(?:the\s+|my\s+|any\s+|a\s+)?{field_regex}", m) is not None

    if (forgets(r"budget|price|cost|max\s*price")
            or re.search(r"\bno\s+(?:budget|price|cost)(?:\s+(?:limit|cap|range|max))?\b", m)
            or re.search(r"\bany\s+price\b", m)
            or re.search(r"\bprice\s+(?:doesn'?t|does not)\s+matter\b", m)):
        fields += ["budget", "min_budget"]
    if forgets(r"bed(?:room)?s?") or re.search(r"\bno\s+bed(?:room)?s?(?:\s+limit)?\b", m):
        fields.append("bedrooms")
    if forgets(r"bath(?:room)?s?") or re.search(r"\bno\s+bath(?:room)?s?(?:\s+limit)?\b", m):
        fields.append("bathrooms")
    if forgets(r"neighbourhood|neighborhood|area"):
        fields.append("neighbourhood")
    if forgets(r"city|location"):
        fields += ["city", "neighbourhood"]
    if forgets(r"property\s*type|type|apartment|flat|house|home"):
        fields.append("property_type")
    if forgets(r"radius|distance|range|proximity"):
        fields.append("radius_km")
    if forgets(r"sort|order|ranking|sorting"):
        fields += ["sort_by", "sort_order"]

    # de-dup, preserve order
    return list(dict.fromkeys(fields))


def _normalize_constraints(raw: dict) -> dict:
    """Normalize and validate extracted constraint values."""
    result = {}

    if "city" in raw and raw["city"]:
        city = str(raw["city"]).strip().lower()
        if city in _CITY_PROPER:
            result["city"] = _CITY_PROPER[city]

    if "intent" in raw and raw["intent"] in ("rent", "buy"):
        # Canonical field consumed by the SQL builder is `rent_or_buy`.
        result["rent_or_buy"] = raw["intent"]

    if "property_type" in raw and raw["property_type"] in ("apartment", "house"):
        result["property_type"] = raw["property_type"]

    if "bedrooms" in raw and raw["bedrooms"] is not None:
        try:
            result["bedrooms"] = int(raw["bedrooms"])
        except (ValueError, TypeError):
            pass

    if "bathrooms" in raw and raw["bathrooms"] is not None:
        try:
            result["bathrooms"] = int(raw["bathrooms"])
        except (ValueError, TypeError):
            pass

    if "max_price" in raw and raw["max_price"] is not None:
        # Canonical field consumed by the SQL builder is `budget`.
        try:
            result["budget"] = float(raw["max_price"])
        except (ValueError, TypeError):
            pass

    if "radius_km" in raw and raw["radius_km"] is not None:
        try:
            result["radius_km"] = float(raw["radius_km"])
        except (ValueError, TypeError):
            pass

    if "min_budget" in raw and raw["min_budget"] is not None:
        try:
            result["min_budget"] = float(raw["min_budget"])
        except (ValueError, TypeError):
            pass

    if "sort_by" in raw and raw["sort_by"] in (
        "price", "size_sqm", "bedrooms", "distance_from_city_km"
    ):
        result["sort_by"] = raw["sort_by"]

    if "sort_order" in raw and raw["sort_order"] in ("asc", "desc"):
        result["sort_order"] = raw["sort_order"]

    if "limit" in raw and raw["limit"] is not None:
        try:
            result["limit"] = int(raw["limit"])
        except (ValueError, TypeError):
            pass

    if raw.get("cities"):
        valid_cities = [c for c in raw["cities"] if c in _CITY_PROPER.values()]
        if len(valid_cities) >= 2:
            result["cities"] = valid_cities

    return result


# ---------------------------------------------------------------------------
# T22 helper
# ---------------------------------------------------------------------------

def _get_active_search_id(state: AgentState) -> str | None:
    """Extract the current search_id from state.active_search if it exists.

    Returns None if active_search is not yet set (e.g. very first turn).
    The caller uses None to let ActiveSearchSession generate a fresh UUID.
    """
    active = state.get("active_search") or {}
    return active.get("search_id") or None


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

async def extract_constraints_node(state: AgentState, config: RunnableConfig) -> dict:
    """Extract and merge constraints from the user message into SearchContext.

    Note: MODIFY_SEARCH and NEW_SEARCH are handled by dedicated nodes
    (modify_search_context_node, reset_search_context_node) via conditional
    routing after classify_action. This node handles NEED_CLARIFICATION and
    the default path (REFINE_SEARCH, GENERAL_CHAT, etc.).

    T22: Returns active_search in addition to search_context.
    """

    # ── NEED_CLARIFICATION: skip extraction, return question ────
    if state.get("conversation_action") == "need_clarification":
        from app.conversation.need_clarification import apply_need_clarification

        ctx_dict, empty_constraints, question = apply_need_clarification(
            user_message=state["user_message"],
            current_context=state.get("search_context") or {},
        )

        # T22: build active_search even on clarification path so it stays in sync
        updated_ctx = SearchContext(**ctx_dict)
        active_session = ActiveSearchSession.from_search_context(
            updated_ctx,
            search_id=_get_active_search_id(state),
        )

        return {
            "constraints": empty_constraints,
            "search_context": ctx_dict,
            "clarification_needed": True,
            "clarification_question": question,
            # T22: canonical search object (unchanged — no constraints extracted)
            "active_search": active_session.model_dump(),
        }

    # ── Default path (REFINE_SEARCH, GENERAL_CHAT, etc.) ─────────
    llm: LLMProvider = config["configurable"]["llm"]
    user_message = state["user_message"]
    search_context = SearchContext(**(state.get("search_context") or {}))

    # 1. Try regex fast-path
    regex_constraints = _regex_extract(user_message)

    # 2. If regex found very little, use LLM fallback
    if len(regex_constraints) <= 1:
        llm_constraints = await _llm_extract(llm, user_message, search_context)
        # Merge: LLM results fill in gaps not covered by regex
        for key, value in llm_constraints.items():
            if key not in regex_constraints and value is not None:
                regex_constraints[key] = value

    # 3. Normalize
    normalized = _normalize_constraints(regex_constraints)

    # 4. Merge into existing SearchContext
    updated_context = search_context.merge(normalized)

    # T22: Dual-write to active_search (preserving existing search_id).
    # search_id is stable across REFINE_SEARCH turns — only NEW_SEARCH resets it.
    active_session = ActiveSearchSession.from_search_context(
        updated_context,
        search_id=_get_active_search_id(state),
    )

    return {
        "constraints": normalized,
        "search_context": updated_context.model_dump(),
        # T22: canonical search object
        "active_search": active_session.model_dump(),
    }


async def _llm_extract(
    llm: LLMProvider,
    user_message: str,
    search_context: SearchContext,
) -> dict:
    """Use the LLM to extract constraints when regex is insufficient."""
    messages = [
        {"role": "system", "content": EXTRACT_CONSTRAINTS_SYSTEM},
        {
            "role": "user",
            "content": EXTRACT_CONSTRAINTS_USER.format(
                memory_context=search_context.to_context_string(),
                user_message=user_message,
            ),
        },
    ]

    try:
        result = await llm.invoke_json(messages)
        if isinstance(result, dict):
            return result
    except Exception:
        # Fallback: try plain invoke and parse
        try:
            raw = await llm.invoke(messages)
            return _parse_json_safe(raw)
        except Exception:
            pass

    return {}


def _parse_json_safe(text: str) -> dict:
    """Attempt to parse JSON from LLM output, handling common issues."""
    text = text.strip()
    # Strip markdown fences
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        # Try to find JSON object in the text
        match = re.search(r"\{[^}]+\}", text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

    return {}
