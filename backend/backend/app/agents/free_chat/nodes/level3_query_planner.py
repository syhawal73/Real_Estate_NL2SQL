"""Deterministic query planner.

The LLM is intentionally not used here. The same structured search state
always produces the same query plan regardless of model/provider.
"""

from app.agents.free_chat.state import AgentState


def level3_query_planner_node(state: AgentState, config=None) -> dict:
    ctx = state.get("search_context") or {}
    intent = state.get("intent", "property_search")
    ranking = ctx.get("ranking_type") or ""
    sort_by = ctx.get("sort_by")
    sort_order = ctx.get("sort_order")

    if intent == "count":
        plan = {"query_type": "count"}
    elif intent == "aggregation":
        msg = (state.get("user_message") or "").lower()
        agg = "average_price"
        if "maximum" in msg or "highest" in msg or "max" in msg:
            agg = "max_price"
        elif "minimum" in msg or "lowest" in msg or "min" in msg:
            agg = "min_price"
        plan = {"query_type": "aggregation", "aggregation": agg}
    elif intent == "comparison":
        plan = {"query_type": "comparison"}
    elif intent == "radius_search":
        plan = {"query_type": "radius", "max_distance_km": ctx.get("radius_km")}
    elif intent == "ranking" or sort_by:
        if not sort_by:
            if "cheap" in ranking or "low" in ranking:
                sort_by, sort_order = "price", "asc"
            elif any(x in ranking for x in ("expensive", "priciest", "high")):
                sort_by, sort_order = "price", "desc"
            elif any(x in ranking for x in ("large", "big", "spacious")):
                sort_by, sort_order = "size_sqm", "desc"
            elif any(x in ranking for x in ("close", "near", "nearest")):
                sort_by, sort_order = "distance_from_city_km", "asc"
        plan = {"query_type": "ranking", "sort_field": sort_by or "price", "sort_direction": sort_order or "asc", "limit": min(int(ctx.get("limit") or 5), 50)}
    elif ctx.get("search_term"):
        plan = {"query_type": "pattern", "field": "description", "term": ctx["search_term"]}
    else:
        plan = {"query_type": "listing", "limit": min(int(ctx.get("limit") or 20), 50)}

    return {"query_plan": plan}
