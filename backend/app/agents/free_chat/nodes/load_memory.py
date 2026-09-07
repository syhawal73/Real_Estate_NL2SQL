"""Node: load_memory — deserializes session memory into SearchContext (Phase 4.1).

This is the first node in the graph. It converts the raw memory dict
from the database into a structured SearchContext for use by downstream nodes.
No LLM call — pure data transformation.

T22: Also populates state.active_search from persisted memory when available,
or migrates from pre-T22 sessions by deriving it from search_context.
"""

from langchain_core.runnables import RunnableConfig

from app.agents.free_chat.state import AgentState
from app.domain.chat.schemas import ActiveSearchSession, SessionMemory


async def load_memory_node(state: AgentState, config: RunnableConfig) -> dict:
    memory_data = state.get("memory") or {}

    # Handle both old-format (flat) and new-format (nested) memory
    memory = _parse_memory(memory_data)

    # T22: Restore or derive active_search.
    # Priority order:
    #   1. Persisted active_search in memory (post-T22 sessions)
    #   2. Derive from search_context (pre-T22 migration path)
    if memory.active_search:
        active_session = ActiveSearchSession(**memory.active_search)
    else:
        # Pre-T22 session: derive from search_context, generate new search_id.
        active_session = ActiveSearchSession.from_search_context(
            memory.search_context,
            search_id=None,  # new UUID for migrated sessions
        )

    return {
        "search_context": memory.search_context.model_dump(),
        "memory": memory.model_dump(),
        # T22: canonical search object
        "active_search": active_session.model_dump(),
    }


def _parse_memory(memory_data: dict) -> SessionMemory:
    """Parse memory dict, handling migration from Phase 4 flat format.

    Phase 4 stored flat fields: city, intent, bedrooms, max_price, etc.
    Phase 4.1 stores nested: search_context, previous_context, etc.
    T22 adds: active_search.
    """
    # Check if this is already new format (has search_context key)
    if "search_context" in memory_data:
        return SessionMemory(**memory_data)

    # Migrate from old flat format → new nested format
    search_fields = {}
    meta_fields = {}
    for key, value in memory_data.items():
        if key in ("city", "intent", "property_type", "bedrooms", "bathrooms",
                    "max_price", "radius_km", "sort_by", "sort_order", "limit",
                    "last_result_count", "neighbourhood"):
            search_fields[key] = value
        elif key in ("last_sql", "last_result_count", "last_intent"):
            meta_fields[key] = value

    from app.domain.chat.schemas import SearchContext
    return SessionMemory(
        search_context=SearchContext(**search_fields),
        **meta_fields,
    )
