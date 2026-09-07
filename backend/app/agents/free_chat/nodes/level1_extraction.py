"""Deterministic Level 1 extraction.

The search contract is deliberately model-independent: common real-estate
entities and intent are derived from rules, not from an LLM. An LLM is only
used later for natural-language presentation/general conversation.
"""

import re
from sqlalchemy import text
from langchain_core.runnables import RunnableConfig
from app.agents.free_chat.state import AgentState


_PROPERTY_WORDS = re.compile(r"\b(apartment|apartments|flat|flats|house|houses|home|homes)\b", re.I)
_SEARCH_WORDS = re.compile(r"\b(find|show|search|looking for|look for|options|properties|homes|apartments|houses|listing|listings)\b", re.I)
_ANALYTIC_WORDS = re.compile(r"\b(average|avg|mean|minimum|maximum|lowest|highest|how many|count|compare|comparison|cheapest|priciest|largest|smallest|closest|nearest|farthest)\b", re.I)
_GENERAL_REAL_ESTATE = re.compile(r"\b(lease|mortgage|rent|buy|bedroom|bathroom|property|apartment|house|home|neighbourhood|neighborhood|listing|deposit|viewing)\b", re.I)


def _intent(message: str, constraints: dict) -> str:
    m = message.lower()
    if re.search(r"\b(start over|new search|fresh search|forget .*search)\b", m):
        return "property_search"
    if re.search(r"\b(compare|comparison|versus|vs\.? )\b", m) or m.startswith("compare"):
        return "comparison"
    if re.search(r"\b(how many|count of|number of)\b", m):
        return "count"
    if re.search(r"\b(average|avg|mean|minimum price|maximum price|highest price|lowest price)\b", m):
        return "aggregation"
    if any(x in m for x in ("cheapest", "most expensive", "priciest", "largest", "biggest", "smallest", "closest", "nearest", "farthest", "top ")):
        return "ranking"
    if re.search(r"\bwithin\s+\d+(?:\.\d+)?\s*km\b|\b\d+(?:\.\d+)?\s*km\b", m):
        return "radius_search"
    if re.search(r"\b(tell me|what is|what does|explain|how does|should I|advice)\b", m) and not _SEARCH_WORDS.search(m):
        return "general_chat"
    if _PROPERTY_WORDS.search(m) or constraints:
        return "property_search"
    # An explicit search verb ("find me a property", "show me options") is a
    # search request even without concrete filters — it must reach the
    # clarification gate, not be answered as general chat.
    if _SEARCH_WORDS.search(m):
        return "property_search"
    if _GENERAL_REAL_ESTATE.search(m):
        return "general_chat"
    return "general_chat"


def _extract(message: str, known_neighbourhoods: list[tuple[str, str]]) -> dict:
    from app.agents.free_chat.nodes.extract_constraints import _normalize_constraints, _regex_extract

    raw = _regex_extract(message)
    lower = message.lower()
    # Support natural range language while preserving the existing property schema.
    range_match = re.search(r"(?:between|from)\s*[£€$]?\s*(\d+(?:\.\d+)?)\s*k?\s*(?:and|to|-)\s*[£€$]?\s*(\d+(?:\.\d+)?)\s*k?", message, re.I)
    if range_match:
        a, b = float(range_match.group(1)), float(range_match.group(2))
        if a < 1000: a *= 1000
        if b < 1000: b *= 1000
        raw["min_budget"], raw["max_price"] = sorted((a, b))

    around = re.search(r"\b(?:around|about|roughly|approximately)\s*[£€$]?\s*(\d+(?:\.\d+)?)\s*k?\b", message, re.I)
    if around:
        value = float(around.group(1))
        if value < 1000: value *= 1000
        raw["min_budget"], raw["max_price"] = value * 0.9, value * 1.1

    if re.search(r"\b(larger|more spacious|bigger)\b", lower):
        raw["sort_by"], raw["sort_order"] = "size_sqm", "desc"
    if re.search(r"\b(cheaper|lowest priced|low price)\b", lower):
        raw["sort_by"], raw["sort_order"] = "price", "asc"

    for neighbourhood, city in known_neighbourhoods:
        if neighbourhood.lower() in lower:
            raw["neighbourhood"] = neighbourhood
            if not raw.get("city"):
                raw["city"] = city
            break

    return _normalize_constraints(raw) | ({"min_budget": raw.get("min_budget")} if raw.get("min_budget") is not None else {})


async def level1_extraction_node(state: AgentState, config: RunnableConfig) -> dict:
    engine = config["configurable"]["db_engine"]
    message = state["user_message"]
    neighbourhoods: list[tuple[str, str]] = []
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT DISTINCT neighbourhood, city FROM properties ORDER BY city, neighbourhood"))
            neighbourhoods = [(r[0], r[1]) for r in result.fetchall()]
    except Exception:
        pass

    entities = _extract(message, neighbourhoods)
    intent = _intent(message, entities)
    # Search-context action language is interpreted independently by the action node.
    if re.search(r"\b(switch to|change city|move .* to|instead in|rent instead|buy instead)\b", message, re.I):
        intent = "modify_search"

    return {"intent": intent, "level1_entities": {**entities, "intent": intent}}
