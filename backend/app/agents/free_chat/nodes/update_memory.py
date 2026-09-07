"""Node: update_memory — persists SearchContext and metadata after query (Phase 4.1).

Runs after summarize_results. Updates the memory dict with:
- Current SearchContext (merged constraints)
- Previous SearchContext snapshot
- last_sql, last_intent, last_result_count

T22: Also persists active_search so it survives across sessions.
TODO T22 cleanup: once readers migrate to active_search, the redundant
search_context persistence here can be removed.
"""

from langchain_core.runnables import RunnableConfig

from app.agents.free_chat.state import AgentState
from app.domain.chat.schemas import ActiveSearchSession, SearchContext, SessionMemory


async def update_memory_node(state: AgentState, config: RunnableConfig) -> dict:
    """Update session memory with current search state."""
    # Load current memory
    memory_data = state.get("memory") or {}
    if "search_context" in memory_data:
        memory = SessionMemory(**memory_data)
    else:
        memory = SessionMemory()

    # Snapshot the previous context
    previous_context = memory.search_context.model_dump()

    # Get the updated search context from the current turn
    current_context = SearchContext(**(state.get("search_context") or {}))

    # T22: persist active_search — keep in sync with search_context.
    # Use whatever active_search the turn nodes produced; fall back to
    # deriving it fresh if the turn somehow left it unset.
    raw_active = state.get("active_search")
    if raw_active:
        active_session = ActiveSearchSession(**raw_active)
    else:
        # TODO T22: This fallback should not be needed once all nodes dual-write.
        active_session = ActiveSearchSession.from_search_context(
            current_context,
            search_id=None,
        )

    # Build updated memory
    updated_memory = SessionMemory(
        search_context=current_context,
        previous_context=previous_context,
        last_sql=state.get("generated_sql"),
        last_result_count=state.get("result_count", 0),
        last_intent=state.get("intent"),
        # T22: persist canonical search object
        active_search=active_session.model_dump(),
    )

    return {
        "memory": updated_memory.model_dump(),
    }
