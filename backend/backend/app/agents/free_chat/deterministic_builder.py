"""Deterministic SQL builder from Level 3 Query Plan JSON."""

from typing import Any

def build_sql(query_plan: dict, search_context: dict) -> tuple[str, dict[str, Any]]:
    """Build a deterministic SQL query from a Level 3 JSON plan and Search Context.
    
    Returns:
        A tuple of (SQL string, bind_parameters_dict).
    """
    
    q_type = query_plan.get("query_type", "listing")
    
    # Base query
    select_clause = "SELECT *"
    if q_type == "count":
        select_clause = "SELECT COUNT(*) as result_count"
    elif q_type == "aggregation":
        agg_type = query_plan.get("aggregation", "average_price")
        if "size" in agg_type:
            select_clause = "SELECT ROUND(AVG(size_sqm)) as result_value"
        elif "min" in agg_type:
            select_clause = "SELECT MIN(price) as result_value"
        elif "max" in agg_type:
            select_clause = "SELECT MAX(price) as result_value"
        else:
            select_clause = "SELECT ROUND(AVG(price)) as result_value" # fallback
    elif q_type == "comparison":
        select_clause = "SELECT city, ROUND(AVG(price)) as average_price, COUNT(*) as property_count"
            
    query = f"{select_clause} FROM properties WHERE 1=1"
    params = {}
    
    # Apply search context filters
    if search_context.get("city") and q_type != "comparison":
        # Do not filter by city if it's a comparison between cities
        query += " AND city ILIKE :city"
        params["city"] = search_context["city"]
        
    if search_context.get("neighbourhood"):
        query += " AND neighbourhood ILIKE :neighbourhood"
        params["neighbourhood"] = f"%{search_context['neighbourhood']}%"
        
    if search_context.get("property_type"):
        query += " AND property_type = :property_type"
        params["property_type"] = search_context["property_type"].lower()
        
    if search_context.get("rent_or_buy"):
        query += " AND intent = :intent"
        params["intent"] = search_context["rent_or_buy"].lower()
        
    if search_context.get("bedrooms") is not None:
        query += " AND bedrooms = :bedrooms"
        params["bedrooms"] = int(search_context["bedrooms"])
        
    if search_context.get("bathrooms") is not None:
        query += " AND bathrooms = :bathrooms"
        params["bathrooms"] = int(search_context["bathrooms"])
        
    if search_context.get("min_budget") is not None:
        query += " AND price >= :min_budget"
        params["min_budget"] = float(search_context["min_budget"])
    if search_context.get("budget") is not None:
        query += " AND price <= :budget"
        params["budget"] = float(search_context["budget"])
        
    if search_context.get("radius_km") is not None:
        query += " AND distance_from_city_km <= :radius"
        params["radius"] = float(search_context["radius_km"])

    # Apply Level 3 specific filters
    if q_type == "radius":
        max_dist = query_plan.get("max_distance_km")
        if max_dist is not None:
            query += " AND distance_from_city_km <= :plan_radius"
            params["plan_radius"] = float(max_dist)
            
    if q_type == "pattern":
        field = query_plan.get("field", "title")
        term = query_plan.get("term", "")
        if field in ("title", "description", "neighbourhood") and term:
            query += f" AND {field} ILIKE :term"
            params["term"] = f"%{term}%"
            
    # Restrict a comparison to the specific cities the user named, if any.
    if q_type == "comparison" and search_context.get("cities"):
        query += " AND city = ANY(:cities)"
        params["cities"] = list(search_context["cities"])

    # Group By
    if q_type == "comparison":
        query += " GROUP BY city"
            
    # Ordering
    if q_type not in ("count", "aggregation", "comparison"):
        sort_field = query_plan.get("sort_field")
        sort_direction = query_plan.get("sort_direction", "asc").upper()
        
        if sort_direction not in ("ASC", "DESC"):
            sort_direction = "ASC"
            
        valid_sort_fields = {
            "price": "price",
            "size_sqm": "size_sqm",
            "bedrooms": "bedrooms",
            "distance_from_city_km": "distance_from_city_km"
        }
        
        db_sort_field = valid_sort_fields.get(sort_field)
        if db_sort_field:
            query += f" ORDER BY {db_sort_field} {sort_direction}"
            
        # Limits
        limit = query_plan.get("limit")
        if isinstance(limit, int) and limit > 0:
            query += f" LIMIT {min(limit, 50)}"
        else:
            query += " LIMIT 20"
            
    return query, params
