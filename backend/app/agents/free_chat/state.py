"""LangGraph state for the real-estate conversational agent."""
from typing import Any
from typing_extensions import TypedDict

class AgentState(TypedDict, total=False):
    session_id: str
    user_id: str
    user_message: str
    memory: dict
    intent: str
    level1_entities: dict
    conversation_action: str
    search_context: dict
    active_search: dict
    clarification_needed: bool
    clarification_question: str
    query_plan: dict
    sql_error: str
    query_results: list[dict[str, Any]]
    result_count: int
    assistant_message: str
    properties: list[dict[str, Any]]
    error_message: str
    generated_sql: str
    fallback_applied: bool
    fallback_message: str
    constraints: dict
    retry_count: int
    sql_valid: bool
    history: list[dict]
    clear_fields: list[str]
